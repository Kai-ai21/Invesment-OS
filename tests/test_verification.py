import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.domain.verification import VerdictData
from backend.models.base import Base
from backend.models.claim import Claim
from backend.models.thesis import Thesis
from backend.models.user import User
from backend.ports.evidence_retriever import EvidenceRetriever
from backend.services.verification_service import verify_document_against_thesis

# The passage the fake retriever will return — the only text the AI is allowed to see.
RETRIEVED_PASSAGE = (
    "Gross margin for the fiscal quarter expanded to 74.2 percent, "
    "up from 71.8 percent in the prior-year period."
)

# Text that lives in the document but is NOT retrieved. If any of this reaches the
# provider — or is accepted as grounding for a quote — retrieval has been bypassed.
UNRETRIEVED_TEXT = (
    "The board declared a quarterly cash dividend of ten cents per share. "
    "Our supply chain spans multiple countries and is exposed to geopolitical disruption."
)

DOCUMENT = f"{UNRETRIEVED_TEXT} {RETRIEVED_PASSAGE} {UNRETRIEVED_TEXT}"


class FakeRetriever(EvidenceRetriever):
    """Returns a fixed set of passages and records the queries it was asked."""

    def __init__(self, passages: list[str]):
        self.passages = passages
        self.queries: list[str] = []

    def retrieve(self, claim_text, document_text, document_id, k=4):
        self.queries.append(claim_text)
        return list(self.passages)

    def retrieve_scored(self, claim_text, document_text, document_id, k=4):
        self.queries.append(claim_text)
        return [(p, 1.0) for p in self.passages]


class FakeProvider:
    """Stub LLM: records the document text it was handed, returns a canned verdict."""

    def __init__(self, verdict: VerdictData):
        self.verdict = verdict
        self.seen_document_texts: list[str] = []

    def verify_claim(self, statement, proof_condition, break_condition, document_text):
        self.seen_document_texts.append(document_text)
        return self.verdict

    def extract_claims(self, ticker, reasoning):  # pragma: no cover - unused here
        raise NotImplementedError


def _supporting_verdict(quote: str) -> VerdictData:
    return VerdictData(
        verdict="supports",
        confidence=0.9,
        evidence_quote=quote,
        reasoning="The document reports a margin above the proof threshold.",
    )


@pytest.fixture
def db():
    # In-memory SQLite shared across connections, so the service's commits are visible.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def thesis(db):
    user = User(email="demo@local")
    db.add(user)
    db.flush()
    thesis = Thesis(user_id=user.id, ticker="NVDA", reasoning_raw="...", status="pending")
    db.add(thesis)
    db.flush()
    db.add(
        Claim(
            thesis_id=thesis.id,
            statement="Nvidia sustains high gross margins.",
            proof_condition="Non-GAAP gross margin stays at or above 72 percent.",
            break_condition="Gross margin falls below 65 percent for two quarters.",
            is_core=True,
            status="pending",
        )
    )
    db.commit()
    return thesis


# --- the AI sees only what was retrieved ------------------------------------------


def test_provider_receives_only_the_retrieved_passages_not_the_whole_document(db, thesis):
    # Arrange
    retriever = FakeRetriever([RETRIEVED_PASSAGE])
    provider = FakeProvider(_supporting_verdict(RETRIEVED_PASSAGE))

    # Act
    verify_document_against_thesis(
        db, thesis.id, DOCUMENT, retriever=retriever, provider=provider
    )

    # Assert — the prompt carried the retrieved passage and nothing else from the doc.
    assert len(provider.seen_document_texts) == 1
    sent_to_ai = provider.seen_document_texts[0]
    assert RETRIEVED_PASSAGE in sent_to_ai
    assert UNRETRIEVED_TEXT not in sent_to_ai


def test_multiple_passages_are_joined_with_a_separator(db, thesis):
    # Arrange
    second = "Operating expenses grew more slowly than revenue in the period."
    retriever = FakeRetriever([RETRIEVED_PASSAGE, second])
    provider = FakeProvider(_supporting_verdict(RETRIEVED_PASSAGE))

    # Act
    verify_document_against_thesis(
        db, thesis.id, DOCUMENT, retriever=retriever, provider=provider
    )

    # Assert — both passages present, visibly separated as distinct excerpts.
    sent_to_ai = provider.seen_document_texts[0]
    assert RETRIEVED_PASSAGE in sent_to_ai
    assert second in sent_to_ai
    assert "---" in sent_to_ai


# --- the citation check validates against the passages, not the document ----------


def test_quote_found_only_in_unretrieved_text_is_rejected(db, thesis):
    # Arrange — the model "quotes" real document text it was never shown. Checking
    # against the full document would wrongly accept this; checking against the
    # retrieved passages (as it must) rejects it. This is the regression guard for
    # anyone reverting the citation check to the full raw_text.
    retriever = FakeRetriever([RETRIEVED_PASSAGE])
    quote_from_elsewhere = "The board declared a quarterly cash dividend of ten cents per share."
    assert quote_from_elsewhere in DOCUMENT  # it IS in the document...
    provider = FakeProvider(_supporting_verdict(quote_from_elsewhere))

    # Act
    created = verify_document_against_thesis(
        db, thesis.id, DOCUMENT, retriever=retriever, provider=provider
    )

    # Assert — ...but not in what the model saw, so no evidence is recorded.
    assert created == []


def test_quote_grounded_in_the_retrieved_passage_is_accepted(db, thesis):
    # Arrange
    retriever = FakeRetriever([RETRIEVED_PASSAGE])
    provider = FakeProvider(_supporting_verdict("expanded to 74.2 percent"))

    # Act
    created = verify_document_against_thesis(
        db, thesis.id, DOCUMENT, retriever=retriever, provider=provider
    )

    # Assert
    assert len(created) == 1
    assert created[0].verdict == "supports"


# --- empty retrieval short-circuits ------------------------------------------------


def test_claim_is_skipped_without_calling_the_ai_when_retrieval_returns_nothing(db, thesis):
    # Arrange
    retriever = FakeRetriever([])
    provider = FakeProvider(_supporting_verdict(RETRIEVED_PASSAGE))

    # Act
    created = verify_document_against_thesis(
        db, thesis.id, DOCUMENT, retriever=retriever, provider=provider
    )

    # Assert — no prompt was sent and no evidence recorded.
    assert provider.seen_document_texts == []
    assert created == []


# --- retrieval query covers the whole claim ----------------------------------------


def test_retrieval_query_includes_statement_and_both_conditions(db, thesis):
    # Arrange
    retriever = FakeRetriever([RETRIEVED_PASSAGE])
    provider = FakeProvider(_supporting_verdict(RETRIEVED_PASSAGE))

    # Act
    verify_document_against_thesis(
        db, thesis.id, DOCUMENT, retriever=retriever, provider=provider
    )

    # Assert — evidence is often phrased in the conditions' language, not the
    # statement's, so all three must feed the query.
    assert len(retriever.queries) == 1
    query = retriever.queries[0]
    assert "sustains high gross margins" in query
    assert "at or above 72 percent" in query
    assert "below 65 percent" in query
