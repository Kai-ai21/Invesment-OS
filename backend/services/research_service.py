"""Company research: a profile, plus the company's own latest filing restated in
plain language.

WHAT THIS IS NOT. There is no valuation, no rating, no target and no assessment
anywhere in this pipeline — see backend/domain/research.py. The value on offer is
that the summary is drawn from THIS company's most recent filing and says which
one, not that it reaches a conclusion.

WHY RETRIEVAL RATHER THAN THE WHOLE FILING. A 10-K runs to roughly 360k characters.
Sending that to the model would be slow, expensive, and worse: the passages that
actually describe the business would be buried among exhibits and boilerplate. The
existing HybridRetriever already solves this — it is the same pipeline claim
verification uses, so a filing is chunked and embedded once and both features
benefit from the same cache.

FAILURE IS LAYERED, AND THE LAYERS ARE INDEPENDENT:
  * No profile and no filing -> nothing to show, the caller 502s.
  * Profile but no filing -> a perfectly useful page. EDGAR being down, or a
    company having no filings on record, must not produce an error screen when we
    already know who the company is.
  * Profile and filing but the AI call fails -> same again: the page renders with
    a note instead of an error.
"""

import time

from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.adapters.edgar_source import EdgarSource
from backend.adapters.llm_factory import create_llm_provider
from backend.adapters.hybrid_retriever import HybridRetriever
from backend.adapters.yfinance_price_source import PriceError, YFinancePriceSource
from backend.domain.research import ResearchSummary
from backend.ports.evidence_retriever import EvidenceRetriever
from backend.ports.llm_provider import LLMProvider
from backend.ports.price_source import CompanyProfile, PriceSource

# The two retrieval queries. Deliberately written as descriptions of what we want to
# READ, not as questions — the retriever matches passages, and a filing contains
# prose like "we design and sell", never "here is how we make money".
BUSINESS_QUERY = "business description, products, how the company makes money"
RISK_QUERY = "principal risk factors and competitive threats"

# Passages per query. Eight matches RETRIEVAL_K's tuned default in verification: enough
# for the model to have real material, few enough that the prompt stays focused.
PASSAGES_PER_QUERY = 8

# Filing preference, best first. A 10-K carries the full business description and risk
# factors; a 10-Q is thinner but has both in summary; an 8-K is an event notice and is
# the last resort, used only so a company with no annual filing on record still gets
# something.
FILING_PREFERENCE: tuple[tuple[str, ...], ...] = (("10-K",), ("10-Q",), ("8-K",))

# Research is the most expensive thing this app does — a filing fetch, two retrieval
# passes and an AI call. A filing does not change between requests, so a long TTL costs
# nothing in freshness. The live price is NOT served from here; the frontend has the
# market and portfolio endpoints for that.
RESEARCH_TTL_SECONDS = 24 * 60 * 60

_cache: dict[str, tuple[float, "ResearchData"]] = {}


def clear_cache() -> None:
    """Drop every cached research entry. For tests and manual refresh."""
    _cache.clear()


class ResearchData(BaseModel):
    ticker: str
    profile: CompanyProfile | None = None
    summary: ResearchSummary | None = None

    # Provenance. Set by THIS SERVICE from the filing it actually fetched, never by
    # the model — the one thing on the page that must be exactly right is which
    # document the words came from, and a model asked to echo a title can get the
    # date wrong. Asking it would add a failure mode for a fact we already hold.
    source_filing_title: str | None = None
    source_filing_date: str | None = None
    source_filing_url: str | None = None

    # True when the profile is present but the filing summary is not, for whatever
    # reason. The page renders normally and says so quietly.
    filing_summary_unavailable: bool = False
    filing_summary_error: str | None = None


def get_research(
    db: Session,
    ticker: str,
    source: PriceSource | None = None,
    edgar: EdgarSource | None = None,
    retriever: EvidenceRetriever | None = None,
    provider: LLMProvider | None = None,
) -> ResearchData | None:
    """Research for one ticker, or None when the ticker is unknown everywhere.

    `db` is accepted for symmetry with the other services and to keep the door open
    for per-user research notes; nothing here reads from it today.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        return None

    cached = _cache.get(normalised)
    if cached is not None and time.monotonic() - cached[0] < RESEARCH_TTL_SECONDS:
        return cached[1]

    if source is None:
        source = YFinancePriceSource()

    profile: CompanyProfile | None = None
    profile_error: str | None = None
    try:
        profile = source.get_company_profile(normalised)
    except PriceError as exc:
        profile_error = str(exc)

    # An unknown symbol AND no upstream trouble means there is genuinely no such
    # company — the caller turns that into a 404 rather than an empty page.
    if profile is None and profile_error is None:
        return None

    data = ResearchData(ticker=normalised, profile=profile)
    _attach_filing_summary(data, edgar=edgar, retriever=retriever, provider=provider)

    # Nothing worked at all: no profile and no filing. Signalled to the caller as a
    # 502, because an empty research page is worse than saying the sources are down.
    if data.profile is None and data.summary is None:
        raise ResearchUnavailableError(
            profile_error or f"No data available for {normalised}"
        )

    # SUCCESSES ONLY, and only COMPLETE ones. A page whose filing summary failed is
    # served but never cached, so a transient EDGAR outage does not freeze a
    # half-empty page in front of the user for a day.
    if not data.filing_summary_unavailable:
        _cache[normalised] = (time.monotonic(), data)
    return data


class ResearchUnavailableError(Exception):
    """Every upstream failed — there is nothing to show."""


def _attach_filing_summary(
    data: ResearchData,
    edgar: EdgarSource | None,
    retriever: EvidenceRetriever | None,
    provider: LLMProvider | None,
) -> None:
    """Fetch the best available filing, retrieve from it, and summarise.

    Never raises: every failure marks the summary unavailable and leaves the profile
    intact, because a research page with the profile and no filing summary is useful
    and an error page is not.
    """
    try:
        edgar = edgar if edgar is not None else EdgarSource()
        filing = _best_filing(edgar, data.ticker)
        if filing is None:
            _mark_unavailable(data, f"No recent SEC filings found for {data.ticker}")
            return

        text = edgar.fetch_filing_text(filing["url"])
        if not text.strip():
            _mark_unavailable(data, f"The filing for {data.ticker} had no readable text")
            return

        retriever = retriever if retriever is not None else HybridRetriever()
        # One document_id for both queries, so the filing is chunked and embedded
        # ONCE and the second query reuses that work.
        document_id = filing["accessionNumber"]
        business = retriever.retrieve(BUSINESS_QUERY, text, document_id, k=PASSAGES_PER_QUERY)
        risks = retriever.retrieve(RISK_QUERY, text, document_id, k=PASSAGES_PER_QUERY)

        provider = provider if provider is not None else create_llm_provider()
        summary = provider.summarise_company(
            ticker=data.ticker,
            profile_summary=data.profile.long_business_summary if data.profile else None,
            business_passages=business,
            risk_passages=risks,
        )

        data.summary = summary
        data.source_filing_title = filing["title"]
        data.source_filing_date = filing["filingDate"]
        data.source_filing_url = filing["url"]
    except Exception as exc:  # noqa: BLE001 - see the docstring
        # Deliberately broad. Retrieval loads a model and ChromaDB, and the AI call
        # reaches a third party; both can fail in ways this module cannot enumerate.
        # None of them is worth losing the profile over.
        _mark_unavailable(data, str(exc) or type(exc).__name__)


def _mark_unavailable(data: ResearchData, reason: str) -> None:
    data.filing_summary_unavailable = True
    data.filing_summary_error = reason


def _best_filing(edgar: EdgarSource, ticker: str) -> dict | None:
    """The most useful filing on record: 10-K, else 10-Q, else the latest 8-K."""
    cik = edgar.resolve_cik(ticker)
    if cik is None:
        return None

    for form_types in FILING_PREFERENCE:
        filings = edgar.list_recent_filings(
            cik, form_types=form_types, limit=1, ticker=ticker
        )
        if filings:
            return filings[0]
    return None
