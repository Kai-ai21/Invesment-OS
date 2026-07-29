import pytest

from backend.adapters.edgar_source import EdgarNetworkError
from backend.adapters.yfinance_price_source import PriceNetworkError
from backend.domain.research import ResearchSummary
from backend.ports.price_source import CompanyProfile, PriceSource
from backend.services import research_service
from backend.services.research_service import (
    BUSINESS_QUERY,
    RISK_QUERY,
    ResearchUnavailableError,
    get_research,
)

TEN_K = {
    "form": "10-K",
    "filingDate": "2026-02-26",
    "accessionNumber": "0001045810-26-000023",
    "primaryDocument": "nvda-20260126.htm",
    "url": "https://sec.gov/Archives/nvda-10k.htm",
    "title": "NVDA 10-K 2026-02-26",
}
TEN_Q = {**TEN_K, "form": "10-Q", "filingDate": "2026-05-20", "title": "NVDA 10-Q 2026-05-20"}
EIGHT_K = {**TEN_K, "form": "8-K", "filingDate": "2026-07-01", "title": "NVDA 8-K 2026-07-01"}


class FakeProfileSource(PriceSource):
    def __init__(self, profile=None, raises=None):
        self._profile = profile
        self._raises = raises

    def get_company_profile(self, ticker):
        if self._raises:
            raise self._raises
        return self._profile

    def get_quote(self, ticker):
        raise NotImplementedError

    def get_current_price(self, ticker):
        raise NotImplementedError

    def get_price_history(self, ticker, days=365):
        raise NotImplementedError


class FakeEdgar:
    """Serves filings by form type, so preference order is observable."""

    def __init__(self, by_form=None, cik="0001045810", text="filing text", raises=None):
        self._by_form = by_form if by_form is not None else {"10-K": [TEN_K]}
        self._cik = cik
        self._text = text
        self._raises = raises
        self.fetched: list[str] = []

    def resolve_cik(self, ticker):
        if self._raises:
            raise self._raises
        return self._cik

    def list_recent_filings(self, cik, form_types=("8-K",), limit=5, ticker=None):
        if self._raises:
            raise self._raises
        found = []
        for form in form_types:
            found.extend(self._by_form.get(form.upper(), []))
        return found[:limit]

    def fetch_filing_text(self, url):
        self.fetched.append(url)
        if self._raises:
            raise self._raises
        return self._text


class FakeRetriever:
    """Records the queries it was asked for, and the document_id used."""

    def __init__(self, passages=None, raises=None):
        self._passages = passages if passages is not None else ["a passage"]
        self._raises = raises
        self.queries: list[str] = []
        self.document_ids: list[str] = []

    def retrieve(self, claim_text, document_text, document_id, k=4):
        if self._raises:
            raise self._raises
        self.queries.append(claim_text)
        self.document_ids.append(document_id)
        return self._passages

    def retrieve_scored(self, claim_text, document_text, document_id, k=4):
        raise NotImplementedError


class FakeProvider:
    def __init__(self, summary=None, raises=None):
        self._summary = summary or ResearchSummary(
            what_the_company_does="It designs chips.",
            how_it_makes_money="It sells them to data centres.",
            key_risks=["Supply concentration.", "Competition.", "Export controls."],
        )
        self._raises = raises
        self.calls = 0

    def summarise_company(self, ticker, profile_summary, business_passages, risk_passages):
        self.calls += 1
        if self._raises:
            raise self._raises
        self.last = {
            "ticker": ticker,
            "profile_summary": profile_summary,
            "business_passages": business_passages,
            "risk_passages": risk_passages,
        }
        return self._summary


def profile_for(ticker="NVDA", **overrides) -> CompanyProfile:
    fields = {
        "ticker": ticker,
        "name": "NVIDIA Corporation",
        "sector": "Technology",
        "industry": "Semiconductors",
        "employees": 42000,
        "website": "https://www.nvidia.com",
        "long_business_summary": "NVIDIA operates as an AI infrastructure company.",
        "market_cap": 4.77e12,
        "price": 197.01,
    }
    fields.update(overrides)
    return CompanyProfile(**fields)


def run(**kwargs):
    """get_research with every dependency faked unless overridden."""
    defaults = {
        "db": None,
        "ticker": "NVDA",
        "source": FakeProfileSource(profile_for()),
        "edgar": FakeEdgar(),
        "retriever": FakeRetriever(),
        "provider": FakeProvider(),
    }
    defaults.update(kwargs)
    return get_research(**defaults)


@pytest.fixture(autouse=True)
def clean_research_cache():
    research_service.clear_cache()
    yield
    research_service.clear_cache()


# --- the happy path ----------------------------------------------------------------


def test_returns_profile_summary_and_provenance():
    # Act
    data = run()

    # Assert
    assert data.profile.name == "NVIDIA Corporation"
    assert data.summary.what_the_company_does == "It designs chips."
    assert len(data.summary.key_risks) == 3
    assert data.filing_summary_unavailable is False
    # Provenance comes from the filing we actually fetched, not from the model.
    assert data.source_filing_title == "NVDA 10-K 2026-02-26"
    assert data.source_filing_date == "2026-02-26"


def test_both_retrieval_queries_run_against_one_document():
    # Arrange
    retriever = FakeRetriever()

    # Act
    run(retriever=retriever)

    # Assert — the two specified queries...
    assert retriever.queries == [BUSINESS_QUERY, RISK_QUERY]
    # ...and ONE document_id, so the filing is chunked and embedded only once.
    assert len(set(retriever.document_ids)) == 1


def test_the_model_is_given_only_passages_and_the_profile():
    # Arrange — the guard against sending a 360k-char filing to the AI.
    provider = FakeProvider()
    retriever = FakeRetriever(passages=["business para", "risk para"])

    # Act
    run(provider=provider, retriever=retriever)

    # Assert
    assert provider.last["business_passages"] == ["business para", "risk para"]
    assert provider.last["profile_summary"] == (
        "NVIDIA operates as an AI infrastructure company."
    )
    assert provider.calls == 1  # ONE AI call, as specified


# --- filing preference -------------------------------------------------------------


def test_prefers_a_10k():
    edgar = FakeEdgar(by_form={"10-K": [TEN_K], "10-Q": [TEN_Q], "8-K": [EIGHT_K]})
    assert run(edgar=edgar).source_filing_title == "NVDA 10-K 2026-02-26"


def test_falls_back_to_a_10q_then_an_8k():
    # A 10-Q when there is no annual filing...
    edgar = FakeEdgar(by_form={"10-Q": [TEN_Q], "8-K": [EIGHT_K]})
    assert run(edgar=edgar).source_filing_title == "NVDA 10-Q 2026-05-20"

    # ...and an 8-K as the last resort, so a company with neither still gets something.
    research_service.clear_cache()
    edgar = FakeEdgar(by_form={"8-K": [EIGHT_K]})
    assert run(edgar=edgar).source_filing_title == "NVDA 8-K 2026-07-01"


# --- failure isolation -------------------------------------------------------------


def test_edgar_failure_keeps_the_profile():
    # Arrange — the central promise: a page with the profile beats an error page.
    edgar = FakeEdgar(raises=EdgarNetworkError("sec.gov unreachable"))

    # Act
    data = run(edgar=edgar)

    # Assert
    assert data.profile.name == "NVIDIA Corporation"
    assert data.summary is None
    assert data.filing_summary_unavailable is True
    assert "unreachable" in data.filing_summary_error


def test_no_filings_on_record_keeps_the_profile():
    data = run(edgar=FakeEdgar(by_form={}))
    assert data.profile is not None
    assert data.filing_summary_unavailable is True
    assert "No recent SEC filings" in data.filing_summary_error


def test_retrieval_failure_keeps_the_profile():
    # Retrieval loads a model and a vector store; neither is worth the page over.
    data = run(retriever=FakeRetriever(raises=RuntimeError("chroma is unhappy")))
    assert data.profile is not None
    assert data.summary is None
    assert data.filing_summary_unavailable is True


def test_ai_failure_keeps_the_profile():
    data = run(provider=FakeProvider(raises=RuntimeError("gemini 503")))
    assert data.profile is not None
    assert data.summary is None
    assert data.filing_summary_unavailable is True


def test_an_empty_filing_is_not_summarised():
    # Arrange — a filing that fetched but yielded no text would otherwise send an
    # empty prompt to the model and get a confidently invented answer back.
    data = run(edgar=FakeEdgar(text="   \n  "))

    # Assert
    assert data.summary is None
    assert "no readable text" in data.filing_summary_error


# --- unknown tickers and total failure ---------------------------------------------


def test_unknown_ticker_returns_none():
    # Arrange / Act / Assert — the endpoint turns this into a 404.
    assert run(source=FakeProfileSource(profile=None)) is None


def test_blank_ticker_returns_none():
    assert run(ticker="   ") is None


def test_everything_failing_raises_so_the_endpoint_can_502():
    # Arrange — no profile AND no filing means there is nothing to render.
    with pytest.raises(ResearchUnavailableError):
        run(
            source=FakeProfileSource(raises=PriceNetworkError("yahoo down")),
            edgar=FakeEdgar(raises=EdgarNetworkError("sec down")),
        )


# --- caching -----------------------------------------------------------------------


def test_a_complete_result_is_cached():
    # Arrange
    provider = FakeProvider()

    # Act
    run(provider=provider)
    run(provider=provider)

    # Assert — research is the most expensive call in the app; once is enough.
    assert provider.calls == 1


def test_a_partial_result_is_not_cached():
    # Arrange — caching a page whose filing summary failed would freeze it in front
    # of the user for a day over a transient EDGAR blip.
    failing_edgar = FakeEdgar(raises=EdgarNetworkError("blip"))
    first = run(edgar=failing_edgar)
    assert first.filing_summary_unavailable is True

    # Act — the retry succeeds.
    second = run(edgar=FakeEdgar())

    # Assert
    assert second.filing_summary_unavailable is False
    assert second.summary is not None


def test_the_ticker_is_normalised_for_the_cache():
    # Arrange
    provider = FakeProvider()

    # Act
    run(ticker="nvda", provider=provider)
    run(ticker="  NVDA  ", provider=provider)

    # Assert — one entry, not two.
    assert provider.calls == 1
