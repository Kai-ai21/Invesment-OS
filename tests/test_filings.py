import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.adapters.edgar_source import EdgarNetworkError
from backend.domain.filing import FilingSummary, NotableNumber
from backend.models.base import Base
from backend.models.claim import Claim

# Imported for its side effect as much as its use: create_all only builds the tables
# Base has seen, and test_summarising_writes_nothing asserts on an empty evidence log.
from backend.models.evidence_event import EvidenceEvent
from backend.models.thesis import Thesis
from backend.models.user import User
from backend.services import filing_service
from backend.services.filing_service import (
    BROWSE_FORM_TYPES,
    EVENTS_QUERY,
    RESULTS_QUERY,
    FilingNotListedError,
    FilingSourceError,
    list_filings,
    summarise_filing,
)

TEN_K = {
    "form": "10-K",
    "filingDate": "2026-02-26",
    "accessionNumber": "0001045810-26-000023",
    "primaryDocument": "nvda-20260126.htm",
    "url": "https://sec.gov/Archives/nvda-10k.htm",
    "title": "NVDA 10-K 2026-02-26",
}
TEN_Q = {
    **TEN_K,
    "form": "10-Q",
    "filingDate": "2026-05-20",
    "accessionNumber": "0001045810-26-000031",
    "url": "https://sec.gov/Archives/nvda-10q.htm",
    "title": "NVDA 10-Q 2026-05-20",
}
EIGHT_K = {
    **TEN_K,
    "form": "8-K",
    "filingDate": "2026-07-01",
    "accessionNumber": "0001045810-26-000040",
    "url": "https://sec.gov/Archives/nvda-8k.htm",
    "title": "NVDA 8-K 2026-07-01",
}


class FakeEdgar:
    """Serves filings by form type, and records how it was asked for them."""

    def __init__(self, by_form=None, cik="0001045810", text="filing text", raises=None):
        self._by_form = (
            by_form
            if by_form is not None
            else {"10-K": [TEN_K], "10-Q": [TEN_Q], "8-K": [EIGHT_K]}
        )
        self._cik = cik
        self._text = text
        self._raises = raises
        self.fetched: list[str] = []
        self.form_types_asked: list[tuple[str, ...]] = []

    def resolve_cik(self, ticker):
        if self._raises:
            raise self._raises
        return self._cik

    def list_recent_filings(self, cik, form_types=("8-K",), limit=5, ticker=None):
        if self._raises:
            raise self._raises
        self.form_types_asked.append(tuple(form_types))
        found = []
        for form in form_types:
            found.extend(self._by_form.get(form.upper(), []))
        return found[:limit]

    def fetch_filing_text(self, url):
        if self._raises:
            raise self._raises
        self.fetched.append(url)
        return self._text


class FakeRetriever:
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
        self._summary = summary or FilingSummary(
            filing_type_explained="A 10-K is a company's annual report to the SEC.",
            key_points=["Revenue rose.", "A new segment was disclosed."],
            notable_numbers=[
                NotableNumber(figure="$26.0 billion", what_it_measures="revenue")
            ],
            relevant_claim_ids=[],
        )
        self._raises = raises
        self.calls = 0
        self.last = None

    def summarise_filing(
        self, ticker, form, filing_title, results_passages, events_passages, claims
    ):
        self.calls += 1
        if self._raises:
            raise self._raises
        self.last = {
            "ticker": ticker,
            "form": form,
            "filing_title": filing_title,
            "results_passages": results_passages,
            "events_passages": events_passages,
            "claims": claims,
        }
        return self._summary


@pytest.fixture(autouse=True)
def _clear_cache():
    """Both caches are module-level, so a test's entries would leak into the next."""
    filing_service.clear_cache()
    yield
    filing_service.clear_cache()


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    user = User(email="demo@local")
    session.add(user)
    session.commit()
    yield session
    session.close()


def add_claims(db, *, ticker="NVDA", statements=("Margins hold above 70%.",)):
    """A thesis on `ticker` with one claim per statement. Returns the claims."""
    user = db.query(User).filter(User.email == "demo@local").first()
    thesis = Thesis(user_id=user.id, ticker=ticker, reasoning_raw="...")
    db.add(thesis)
    db.flush()
    claims = [
        Claim(
            thesis_id=thesis.id,
            statement=statement,
            proof_condition="p",
            break_condition="b",
            is_core=True,
        )
        for statement in statements
    ]
    db.add_all(claims)
    db.commit()
    return claims


def run(db, **kwargs):
    """summarise_filing with every dependency faked unless overridden."""
    defaults = {
        "ticker": "NVDA",
        "user_id": db.query(User).filter(User.email == "demo@local").one().id,
        "url": TEN_K["url"],
        "edgar": FakeEdgar(),
        "retriever": FakeRetriever(),
        "provider": FakeProvider(),
    }
    defaults.update(kwargs)
    return summarise_filing(db, **defaults)


# --- listing ---------------------------------------------------------------------


def test_listing_asks_for_all_three_forms():
    """The browse list widens beyond the 8-K-only default."""
    edgar = FakeEdgar()
    list_filings("NVDA", limit=10, edgar=edgar)
    assert edgar.form_types_asked == [BROWSE_FORM_TYPES]
    assert set(BROWSE_FORM_TYPES) == {"10-K", "10-Q", "8-K"}


def test_check_flow_default_is_untouched():
    """⚠️ Widening the shared default would silently change what "Check now" verifies.

    A 10-K is ~40x an 8-K, so every check would have got slower and more expensive.
    """
    import inspect

    from backend.adapters.edgar_source import EdgarSource

    signature = inspect.signature(EdgarSource.list_recent_filings)
    assert signature.parameters["form_types"].default == ("8-K",)


def test_listing_returns_refs():
    filings = list_filings("NVDA", limit=10, edgar=FakeEdgar())
    assert [f.form for f in filings] == ["10-K", "10-Q", "8-K"]
    assert filings[0].accession_number == TEN_K["accessionNumber"]
    assert filings[0].url == TEN_K["url"]


def test_unknown_ticker_is_none_not_empty():
    """None and [] are different answers: a 404 versus a company that has filed none."""
    assert list_filings("ZZZZ", edgar=FakeEdgar(cik=None)) is None
    assert list_filings("NVDA", edgar=FakeEdgar(by_form={})) == []


def test_listing_failure_raises_rather_than_reading_as_empty():
    with pytest.raises(FilingSourceError):
        list_filings("NVDA", edgar=FakeEdgar(raises=EdgarNetworkError("SEC is down")))


def test_listing_is_cached_per_ticker_and_limit():
    edgar = FakeEdgar()
    list_filings("NVDA", limit=10, edgar=edgar)
    list_filings("NVDA", limit=10, edgar=edgar)
    assert len(edgar.form_types_asked) == 1

    # A cached 10-row answer cannot serve a request for a different limit.
    list_filings("NVDA", limit=3, edgar=edgar)
    assert len(edgar.form_types_asked) == 2


def test_listing_failures_are_not_cached():
    """Caching a blip would extend it into a six-hour outage."""
    with pytest.raises(FilingSourceError):
        list_filings("NVDA", edgar=FakeEdgar(raises=EdgarNetworkError("down")))
    assert list_filings("NVDA", edgar=FakeEdgar()) != []


# --- summarising -----------------------------------------------------------------


def test_summary_uses_the_two_specified_queries(db):
    retriever = FakeRetriever()
    run(db, retriever=retriever)
    assert retriever.queries == [RESULTS_QUERY, EVENTS_QUERY]


def test_both_queries_share_one_document_id(db):
    """So the filing is chunked and embedded once, not twice."""
    retriever = FakeRetriever()
    run(db, retriever=retriever)
    assert retriever.document_ids == [TEN_K["accessionNumber"]] * 2


def test_provenance_comes_from_the_sec_not_the_caller(db):
    summary = run(db)
    assert summary.filing.form == "10-K"
    assert summary.filing.title == TEN_K["title"]
    assert summary.filing.filing_date == "2026-02-26"
    assert summary.filing.accession_number == TEN_K["accessionNumber"]


def test_summary_carries_the_model_prose(db):
    summary = run(db)
    assert summary.filing_type_explained.startswith("A 10-K is")
    assert summary.key_points == ["Revenue rose.", "A new segment was disclosed."]
    assert summary.notable_numbers[0].figure == "$26.0 billion"


def test_unlisted_url_is_refused_before_anything_is_fetched(db):
    """⚠️ The URL arrives from the client and this service fetches it."""
    edgar = FakeEdgar()
    with pytest.raises(FilingNotListedError):
        run(db, url="https://evil.example.com/payload.htm", edgar=edgar)
    assert edgar.fetched == []


def test_unknown_ticker_summarises_to_none(db):
    assert run(db, ticker="ZZZZ", edgar=FakeEdgar(cik=None)) is None


def test_sec_failure_is_a_source_error(db):
    with pytest.raises(FilingSourceError):
        run(db, edgar=FakeEdgar(raises=EdgarNetworkError("SEC is down")))


def test_ai_failure_is_a_source_error(db):
    with pytest.raises(FilingSourceError):
        run(db, provider=FakeProvider(raises=RuntimeError("model unavailable")))


def test_empty_filing_text_is_refused(db):
    """Confident-looking prose summarised from nothing is worse than an error."""
    with pytest.raises(FilingSourceError):
        run(db, edgar=FakeEdgar(text="   "))


# --- relevance validation --------------------------------------------------------


def test_relevance_is_empty_when_the_model_cites_nothing(db):
    add_claims(db)
    assert run(db).relevance == []


def test_relevance_resolves_real_claims_to_their_thesis(db):
    claims = add_claims(db)
    provider = FakeProvider(
        summary=FilingSummary(
            filing_type_explained="...",
            key_points=[],
            notable_numbers=[],
            relevant_claim_ids=[claims[0].id],
        )
    )
    relevance = run(db, provider=provider).relevance
    assert [item.claim_id for item in relevance] == [claims[0].id]
    assert relevance[0].thesis_id == claims[0].thesis_id
    assert relevance[0].statement == "Margins hold above 70%."


def test_invented_claim_ids_are_dropped(db):
    """The same discipline as the pattern library: a prompt is a request, this is the
    guarantee. An invented id would render a link to a claim that does not exist."""
    claims = add_claims(db)
    provider = FakeProvider(
        summary=FilingSummary(
            filing_type_explained="...",
            key_points=[],
            notable_numbers=[],
            relevant_claim_ids=["not-a-real-id", claims[0].id],
        )
    )
    assert [item.claim_id for item in run(db, provider=provider).relevance] == [
        claims[0].id
    ]


def test_claims_from_another_ticker_are_not_citable(db):
    """A claim about AAPL is not a claim an NVDA filing can address."""
    other = add_claims(db, ticker="AAPL", statements=("Services keep growing.",))
    provider = FakeProvider(
        summary=FilingSummary(
            filing_type_explained="...",
            key_points=[],
            notable_numbers=[],
            relevant_claim_ids=[other[0].id],
        )
    )
    assert run(db, provider=provider).relevance == []


def test_repeated_claim_ids_render_once(db):
    claims = add_claims(db)
    provider = FakeProvider(
        summary=FilingSummary(
            filing_type_explained="...",
            key_points=[],
            notable_numbers=[],
            relevant_claim_ids=[claims[0].id, claims[0].id],
        )
    )
    assert len(run(db, provider=provider).relevance) == 1


def test_the_model_is_given_statements_but_never_the_conditions(db):
    """Proof and break conditions are what a claim is JUDGED against. Handing them to
    a model asked to describe a document invites the answer this feature avoids."""
    add_claims(db)
    provider = FakeProvider()
    run(db, provider=provider)
    assert set(provider.last["claims"][0]) == {"claim_id", "statement"}


def test_no_claims_means_an_empty_list_is_passed(db):
    provider = FakeProvider()
    run(db, provider=provider)
    assert provider.last["claims"] == []


# --- caching ---------------------------------------------------------------------


def test_summary_is_cached_per_filing(db):
    provider = FakeProvider()
    edgar = FakeEdgar()
    run(db, edgar=edgar, provider=provider)
    run(db, edgar=edgar, provider=provider)
    assert provider.calls == 1
    assert edgar.fetched == [TEN_K["url"]]


def test_a_different_filing_is_a_different_entry(db):
    provider = FakeProvider()
    run(db, provider=provider)
    run(db, url=TEN_Q["url"], provider=provider)
    assert provider.calls == 2


def test_summary_failures_are_not_cached(db):
    with pytest.raises(FilingSourceError):
        run(db, provider=FakeProvider(raises=RuntimeError("model unavailable")))
    provider = FakeProvider()
    run(db, provider=provider)
    assert provider.calls == 1


def test_cached_relevance_is_revalidated_against_current_claims(db):
    """A claim deleted since the summary was written must not linger as a dead link.

    The cache holds the model's raw ids, so they are re-resolved on every read.
    """
    claims = add_claims(db)
    provider = FakeProvider(
        summary=FilingSummary(
            filing_type_explained="...",
            key_points=[],
            notable_numbers=[],
            relevant_claim_ids=[claims[0].id],
        )
    )
    assert len(run(db, provider=provider).relevance) == 1

    db.query(Claim).filter(Claim.id == claims[0].id).delete()
    db.commit()

    served = run(db, provider=provider)
    assert provider.calls == 1  # still a cache hit
    assert served.relevance == []


# --- the read-only guarantee -----------------------------------------------------


def test_summarising_writes_nothing(db):
    """⚠️ THE POINT OF THE FEATURE. Evidence is cited, scored and validated; a summary
    is unverified reading. Producing one must never move a status or log an event."""
    claims = add_claims(db)
    thesis = db.get(Thesis, claims[0].thesis_id)
    status_before = thesis.status
    claim_status_before = claims[0].status

    provider = FakeProvider(
        summary=FilingSummary(
            filing_type_explained="...",
            key_points=[],
            notable_numbers=[],
            relevant_claim_ids=[claims[0].id],
        )
    )
    run(db, provider=provider)

    db.expire_all()
    assert db.query(EvidenceEvent).count() == 0
    assert db.get(Thesis, thesis.id).status == status_before
    assert db.get(Claim, claims[0].id).status == claim_status_before
