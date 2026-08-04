"""Browse a company's recent SEC filings, and read any one of them back in plain
language on request.

⚠️ READ-ONLY, AND THAT IS THE WHOLE DESIGN. Nothing in this module writes to the
database. It creates no evidence events, touches no claim status, moves no thesis
and opens no alert or post-mortem. The one place it reads the user's own work is to
resolve the claim ids the model cites, and that read is a lookup — see
`_resolve_relevance`, which can only ever narrow what the model returned.

Compare check_service, which reads the SAME filings from the SAME adapter and does
the opposite: it verifies each one against every claim, writes evidence, and
recomputes the thesis status. The two must never be confused, so this module
deliberately imports neither verification_service nor evidence_repository, and the
summary it produces has no field a verdict could be written into (domain/filing.py).

WHY RETRIEVAL RATHER THAN THE WHOLE FILING. A 10-K runs to roughly 360k characters.
Sending that to the model would be slow, expensive, and worse: what the filing
actually reports would be buried among exhibits and boilerplate. The existing
HybridRetriever already solves this, and going through it means a filing already
chunked and embedded for a claim check is reused here for free.
"""

import time

from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.adapters.edgar_source import EdgarError, EdgarSource
from backend.adapters.gemini_provider import GeminiProvider
from backend.adapters.hybrid_retriever import HybridRetriever
from backend.domain.filing import FilingSummary, NotableNumber
from backend.ports.evidence_retriever import EvidenceRetriever
from backend.ports.llm_provider import LLMProvider
from backend.repositories import thesis_repository

# ⚠️ THE WIDER SET IS THIS FEATURE'S ALONE.
#
# EdgarSource.list_recent_filings still defaults to ("8-K",) and check_service still
# takes that default, deliberately. Widening the default would have silently changed
# what "Check now" verifies: a 10-K is ~40x the length of an 8-K and gets chunked into
# hundreds of passages, so every check would have become slower and more expensive
# without anyone asking for it. Browsing is a different job from verifying, and only
# browsing wants the annual and quarterly reports in the list.
BROWSE_FORM_TYPES: tuple[str, ...] = ("10-K", "10-Q", "8-K")

# The two retrieval queries. Written as descriptions of what we want to READ rather
# than as questions, for the same reason research_service's are: the retriever matches
# passages, and a filing contains prose like "revenue increased", never "here are the
# results".
RESULTS_QUERY = "key financial results, revenue, margins, guidance"
EVENTS_QUERY = "material events, risks, changes disclosed in this filing"

# Passages per query, matching research_service and RETRIEVAL_K's tuned default in
# verification: enough material to summarise from, few enough to stay focused.
PASSAGES_PER_QUERY = 8

# How deep to look when resolving the URL a client asked us to summarise.
#
# ⚠️ THIS IS A SECURITY BOUNDARY, not a convenience. The URL arrives from the client,
# and the service fetches it — so it is checked against the filings the SEC actually
# lists for that ticker before anything is fetched, and a URL that is not one of them
# is refused. That makes it impossible to point this endpoint at an arbitrary host.
# Deeper than any list the UI shows, so a filing that has scrolled off the visible
# list can still be summarised.
LOOKUP_LIMIT = 40

# The filing INDEX is live data — a new 8-K can land any day — so six hours.
LIST_TTL_SECONDS = 6 * 60 * 60

# A filing's CONTENTS, by contrast, are fixed the moment it is filed. Thirty days is
# not a freshness compromise; there is nothing to be fresh about.
SUMMARY_TTL_SECONDS = 30 * 24 * 60 * 60

# Keyed by (ticker, limit) — a cached 5-row response cannot serve a later request for
# 10 without silently truncating it. Same rule as news_service.
_list_cache: dict[tuple[str, int], tuple[float, list["FilingRef"]]] = {}

# Keyed by (ticker, accession number), as the filing itself is immutable.
#
# ⚠️ WHAT IS CACHED IS THE MODEL'S RAW ANSWER, claim ids and all — NOT the resolved
# relevance shown to the user. Those ids are re-validated against the user's CURRENT
# claims on every read (`_resolve_relevance`), so a claim deleted since the summary was
# written disappears from it rather than lingering as a dead link. The converse does
# not hold and is a deliberate limit: a thesis written AFTER a filing was summarised
# will not appear in that summary's relevance until the entry expires, because
# discovering it would need the AI call this cache exists to avoid.
_summary_cache: dict[tuple[str, str], tuple[float, "FilingRef", FilingSummary]] = {}


def clear_cache() -> None:
    """Drop every cached filing list and summary. For tests and manual refresh."""
    _list_cache.clear()
    _summary_cache.clear()


class FilingSourceError(Exception):
    """EDGAR could not be reached, or the filing could not be read.

    Distinct from "no such ticker", which is None and a 404: "we could not look"
    must never arrive looking like "there is nothing to see".
    """


class FilingNotListedError(Exception):
    """The URL is not one of the SEC's recent filings for that ticker.

    Raised before anything is fetched. See LOOKUP_LIMIT.
    """


class FilingRef(BaseModel):
    """One filing as EDGAR lists it. Provenance, and the row the UI renders."""

    form: str
    filing_date: str
    title: str
    url: str
    accession_number: str


class RelevantClaim(BaseModel):
    """A claim this filing DISCUSSES. Emphatically not a claim it supports.

    Carries the thesis id so the UI can link to the claim in place. There is no
    verdict, confidence or direction field here, and there must never be one — that
    is what an evidence event is, and it is produced by a different pipeline that
    quotes the document verbatim and validates the quote.
    """

    claim_id: str
    thesis_id: str
    statement: str


class FilingSummaryData(BaseModel):
    """A summary, plus the provenance of the document it came from.

    Provenance is set by THIS SERVICE from the filing it actually resolved and
    fetched, never from the request body and never by the model — the one thing that
    has to be exactly right is which document the words came from.
    """

    ticker: str
    filing: FilingRef

    filing_type_explained: str
    key_points: list[str]
    notable_numbers: list[NotableNumber]
    relevance: list[RelevantClaim]


def _to_ref(filing: dict) -> FilingRef:
    return FilingRef(
        form=filing["form"],
        filing_date=filing["filingDate"],
        title=filing["title"],
        url=filing["url"],
        accession_number=filing["accessionNumber"],
    )


def list_filings(
    ticker: str,
    limit: int = 10,
    edgar: EdgarSource | None = None,
) -> list[FilingRef] | None:
    """Recent 10-K, 10-Q and 8-K filings for one ticker, newest first.

    None means the SEC does not list that symbol — a 404 at the edge. An EMPTY LIST
    is a different and legitimate answer: a real company that has filed none of these
    three forms. Collapsing the two would tell someone their ticker was wrong when it
    was fine.

    Raises FilingSourceError when EDGAR itself failed.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        return None

    key = (normalised, limit)
    entry = _list_cache.get(key)
    now = time.monotonic()  # monotonic: immune to wall-clock jumps and DST
    if entry is not None and now - entry[0] < LIST_TTL_SECONDS:
        return entry[1]

    edgar = edgar if edgar is not None else EdgarSource()
    try:
        cik = edgar.resolve_cik(normalised)
        if cik is None:
            return None
        filings = edgar.list_recent_filings(
            cik, form_types=BROWSE_FORM_TYPES, limit=limit, ticker=normalised
        )
    except EdgarError as exc:
        raise FilingSourceError(str(exc)) from exc

    refs = [_to_ref(filing) for filing in filings]
    # Successes only. Caching a failure would extend one blip into a six-hour outage.
    _list_cache[key] = (now, refs)
    return refs


def _find_filing(edgar: EdgarSource, ticker: str, url: str) -> FilingRef | None:
    """The SEC's own record of the filing at `url`, or None if it lists no such thing.

    Going through the listing rather than parsing the URL is what makes the fetch
    safe: the URL is matched against documents the SEC actually reports for this
    ticker, so the only thing that can ever be fetched is a real EDGAR filing. It also
    means the form, date and accession number come from the SEC rather than from the
    caller, who has no business naming them.
    """
    cik = edgar.resolve_cik(ticker)
    if cik is None:
        return None

    for filing in edgar.list_recent_filings(
        cik, form_types=BROWSE_FORM_TYPES, limit=LOOKUP_LIMIT, ticker=ticker
    ):
        if filing["url"] == url:
            return _to_ref(filing)
    return None


def _claims_for_ticker(db: Session, ticker: str, user_id: str) -> dict[str, RelevantClaim]:
    """Every claim the user has written about this ticker, by claim id.

    Empty is entirely normal — filings are browsable for any company, including ones
    the user has never written about.
    """
    return {
        claim.id: RelevantClaim(
            claim_id=claim.id, thesis_id=thesis.id, statement=claim.statement
        )
        for thesis in thesis_repository.list_theses_for_user(db, user_id=user_id)
        if thesis.ticker == ticker
        for claim in thesis.claims
    }


def _resolve_relevance(
    cited_ids: list[str], known: dict[str, RelevantClaim]
) -> list[RelevantClaim]:
    """Keep only the cited ids that are real claims of this ticker's, in order.

    THE SAME DISCIPLINE AS THE PATTERN LIBRARY, for the same reason: a model that
    cites an id it was never given has invented its reference, and a UI that renders
    it produces a link to a claim that does not exist — or worse, to somebody's real
    claim the filing never mentioned. A prompt rule is a request; this is the
    guarantee. Deduplicated so a repeated id cannot render twice.

    The bar is lower than a pattern's two-citation minimum, deliberately: one genuine
    claim is a perfectly good answer here, and zero is the expected one.
    """
    seen: set[str] = set()
    resolved: list[RelevantClaim] = []
    for claim_id in cited_ids:
        if claim_id in seen or claim_id not in known:
            continue
        seen.add(claim_id)
        resolved.append(known[claim_id])
    return resolved


def summarise_filing(
    db: Session,
    ticker: str,
    url: str,
    user_id: str,
    edgar: EdgarSource | None = None,
    retriever: EvidenceRetriever | None = None,
    provider: LLMProvider | None = None,
) -> FilingSummaryData | None:
    """Read one filing back in plain language. None when the ticker is unknown.

    SLOW on a cold cache — a filing fetch, two retrieval passes and one AI call, so
    10-20 seconds is normal. Cached for 30 days afterwards; see _summary_cache.

    Raises FilingNotListedError when the URL is not one of the SEC's recent filings
    for this ticker, and FilingSourceError when EDGAR or the AI call failed.

    ⚠️ Writes NOTHING. `db` is read for the user's claims and for nothing else.
    """
    normalised = ticker.strip().upper()
    if not normalised:
        return None

    edgar = edgar if edgar is not None else EdgarSource()

    try:
        filing = _find_filing(edgar, normalised, url)
    except EdgarError as exc:
        raise FilingSourceError(str(exc)) from exc

    if filing is None:
        # Two different causes, and the caller can tell them apart: an unknown symbol
        # resolves to no CIK at all, which is a 404 on the ticker. A known symbol with
        # a URL we do not recognise is a refused fetch.
        try:
            if edgar.resolve_cik(normalised) is None:
                return None
        except EdgarError as exc:
            raise FilingSourceError(str(exc)) from exc
        raise FilingNotListedError(
            f"{url} is not one of the SEC's recent filings for {normalised}"
        )

    known_claims = _claims_for_ticker(db, normalised, user_id)

    cached = _summary_cache.get((normalised, filing.accession_number))
    if cached is not None and time.monotonic() - cached[0] < SUMMARY_TTL_SECONDS:
        return _assemble(normalised, cached[1], cached[2], known_claims)

    try:
        text = edgar.fetch_filing_text(filing.url)
    except EdgarError as exc:
        raise FilingSourceError(str(exc)) from exc
    if not text.strip():
        raise FilingSourceError(f"No readable text in {filing.title}")

    try:
        retriever = retriever if retriever is not None else HybridRetriever()
        # One document_id for both queries, so the filing is chunked and embedded ONCE
        # and the second query reuses that work. The accession number is the same id
        # verification uses, so a filing already indexed by a claim check is free here.
        document_id = filing.accession_number
        results = retriever.retrieve(
            RESULTS_QUERY, text, document_id, k=PASSAGES_PER_QUERY
        )
        events = retriever.retrieve(
            EVENTS_QUERY, text, document_id, k=PASSAGES_PER_QUERY
        )

        provider = provider if provider is not None else GeminiProvider()
        summary = provider.summarise_filing(
            ticker=normalised,
            form=filing.form,
            filing_title=filing.title,
            results_passages=results,
            events_passages=events,
            # Statements only, never the proof and break conditions. Those are the
            # contract a claim is JUDGED against, and handing them to a model asked
            # to describe a document invites it to answer the question this feature
            # exists not to answer.
            claims=[
                {"claim_id": claim.claim_id, "statement": claim.statement}
                for claim in known_claims.values()
            ],
        )
    except Exception as exc:  # noqa: BLE001 - retrieval loads a model, the AI is a third party
        raise FilingSourceError(str(exc) or type(exc).__name__) from exc

    _summary_cache[(normalised, filing.accession_number)] = (
        time.monotonic(),
        filing,
        summary,
    )
    return _assemble(normalised, filing, summary, known_claims)


def _assemble(
    ticker: str,
    filing: FilingRef,
    summary: FilingSummary,
    known_claims: dict[str, RelevantClaim],
) -> FilingSummaryData:
    return FilingSummaryData(
        ticker=ticker,
        filing=filing,
        filing_type_explained=summary.filing_type_explained,
        key_points=summary.key_points,
        notable_numbers=summary.notable_numbers,
        relevance=_resolve_relevance(summary.relevant_claim_ids, known_claims),
    )
