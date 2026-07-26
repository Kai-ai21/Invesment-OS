from backend.adapters.hybrid_retriever import (
    RRF_K,
    HybridRetriever,
    _FUSION_POOL,
    fuse_rankings,
    order_by_fused_score,
)
from backend.domain.chunking import chunk_text

# Fusion is tested through the pure functions, so the maths is verified without
# loading an embedding model. The adapter tests then use a stub for the vector side.


def _build_document() -> str:
    """Long enough to produce several chunks — chunk_text targets ~800 chars."""
    return " ".join(
        f"Paragraph {i} records operational matter number {i}, setting out the "
        f"considerations that management reviewed during the period."
        for i in range(40)
    )


DOCUMENT = _build_document()
DOC_ID = "doc-hybrid-fixture"


class StubRag:
    """Stands in for RagRetriever: returns the document's own chunks in a fixed order.

    Returning real chunks matters — fusion keys on chunk text, so a stub inventing
    strings would not exercise the same paths.
    """

    def __init__(self, order: list[int] | None = None):
        self.order = order
        self.requested_k: int | None = None

    def retrieve_scored(self, claim_text, document_text, document_id, k=4):
        self.requested_k = k
        chunks = chunk_text(document_text)
        selected = chunks if self.order is None else [chunks[i] for i in self.order]
        # Descending scores; the hybrid only uses the ORDER, not these values.
        return [(chunk, 1.0 - 0.01 * i) for i, chunk in enumerate(selected[:k])]

    def retrieve(self, claim_text, document_text, document_id, k=4):
        return [
            chunk
            for chunk, _ in self.retrieve_scored(
                claim_text, document_text, document_id, k
            )
        ]


# --- fixture guard ----------------------------------------------------------------


def test_fixture_document_produces_several_chunks():
    # Fusion between two rankings is meaningless over a single chunk, so fail loudly
    # here if the fixture (or the chunker's defaults) ever shrinks.
    assert len(chunk_text(DOCUMENT)) >= 3


# --- RRF arithmetic ---------------------------------------------------------------


def test_rrf_arithmetic_matches_a_hand_computed_example():
    # Arrange — "y" is 2nd in the first list and 1st in the second; ranks are 0-based.
    first = ["x", "y"]
    second = ["y", "z"]

    # Act
    fused = fuse_rankings([first, second])

    # Assert — hand-computed with RRF_K = 60.
    assert fused["x"] == 1 / 60
    assert fused["y"] == 1 / 61 + 1 / 60
    assert fused["z"] == 1 / 61
    # Sanity-check the constant the numbers above assume.
    assert RRF_K == 60


def test_a_chunk_ranked_well_by_both_lists_beats_one_ranked_first_by_only_one():
    # Arrange — the core RRF property. "solo" tops the first list outright; "both" is
    # merely second there, but also tops the second list.
    vector_ranking = ["solo", "both"]
    keyword_ranking = ["both"]

    # Act
    fused = fuse_rankings([vector_ranking, keyword_ranking])

    # Assert — agreement across rankers outweighs a single first place.
    assert fused["both"] > fused["solo"]


def test_a_chunk_present_in_only_one_list_still_surfaces():
    # Arrange — absence from a list contributes 0; it is never a penalty or a drop.
    vector_ranking = ["shared", "vector_only"]
    keyword_ranking = ["shared", "keyword_only"]

    # Act
    fused = fuse_rankings([vector_ranking, keyword_ranking])

    # Assert
    assert set(fused) == {"shared", "vector_only", "keyword_only"}
    assert fused["vector_only"] > 0
    assert fused["keyword_only"] > 0


def test_fusing_no_lists_produces_no_scores():
    # Arrange / Act / Assert
    assert fuse_rankings([]) == {}
    assert fuse_rankings([[], []]) == {}


# --- ordering and determinism -----------------------------------------------------


def test_results_are_ordered_best_first():
    # Arrange
    fused = {"low": 0.01, "high": 0.03, "middle": 0.02}
    chunks = ["low", "high", "middle"]

    # Act
    ordered = order_by_fused_score(fused, chunks)

    # Assert
    assert [chunk for chunk, _ in ordered] == ["high", "middle", "low"]


def test_ties_are_broken_by_position_in_the_document():
    # Arrange — an exact tie, which RRF produces whenever two chunks hold mirrored
    # ranks (first in one list, second in the other). "later" is inserted first to
    # prove insertion order does not leak into the result.
    tied_score = 1 / 60 + 1 / 61
    fused = {"later": tied_score, "earlier": tied_score}
    chunks = ["earlier", "later"]

    # Act
    ordered = order_by_fused_score(fused, chunks)

    # Assert
    assert [chunk for chunk, _ in ordered] == ["earlier", "later"]


def test_a_chunk_missing_from_the_document_sorts_last_rather_than_raising():
    # Arrange — only reachable if the vector store holds stale chunks for a
    # document_id, but it must degrade rather than crash.
    fused = {"known": 0.02, "stale": 0.02}
    chunks = ["known"]

    # Act
    ordered = order_by_fused_score(fused, chunks)

    # Assert
    assert [chunk for chunk, _ in ordered] == ["known", "stale"]


def test_identical_inputs_produce_identical_output():
    # Arrange
    retriever = HybridRetriever(rag=StubRag())

    # Act
    first = retriever.retrieve_scored("operational matter", DOCUMENT, DOC_ID, k=5)
    second = retriever.retrieve_scored("operational matter", DOCUMENT, DOC_ID, k=5)

    # Assert
    assert first == second


# --- the adapter ------------------------------------------------------------------


def test_vector_side_is_asked_for_the_fusion_pool_not_the_callers_k():
    # Arrange — fusion can only reward agreement if both rankers were asked for enough
    # candidates to overlap; the caller's small k must not shrink that pool.
    stub = StubRag()
    retriever = HybridRetriever(rag=stub)

    # Act
    retriever.retrieve_scored("operational matter", DOCUMENT, DOC_ID, k=3)

    # Assert
    assert stub.requested_k == _FUSION_POOL


def test_returned_chunks_are_verbatim_substrings_of_the_document():
    # Arrange
    retriever = HybridRetriever(rag=StubRag())

    # Act
    results = retriever.retrieve_scored("operational matter", DOCUMENT, DOC_ID, k=5)

    # Assert — nothing normalised, so the citation check can still locate quotes.
    assert results
    assert all(chunk in DOCUMENT for chunk, _ in results)


def test_results_are_capped_at_k_and_ordered_best_first():
    # Arrange
    retriever = HybridRetriever(rag=StubRag())

    # Act
    results = retriever.retrieve_scored("operational matter", DOCUMENT, DOC_ID, k=3)

    # Assert
    assert len(results) == 3
    scores = [score for _, score in results]
    assert scores == sorted(scores, reverse=True)


def test_k_larger_than_the_number_of_chunks_returns_what_exists():
    # Arrange
    retriever = HybridRetriever(rag=StubRag())
    available = len(chunk_text(DOCUMENT))

    # Act
    results = retriever.retrieve_scored("operational matter", DOCUMENT, DOC_ID, k=500)

    # Assert
    assert 0 < len(results) <= available


def test_empty_document_returns_no_passages():
    # Arrange
    retriever = HybridRetriever(rag=StubRag())

    # Act
    results = retriever.retrieve_scored("any claim", "   \n  ", "doc-empty", k=4)

    # Assert
    assert results == []


def test_non_positive_k_returns_no_passages():
    # Arrange
    retriever = HybridRetriever(rag=StubRag())

    # Act / Assert
    assert retriever.retrieve_scored("operational matter", DOCUMENT, DOC_ID, k=0) == []
    assert retriever.retrieve_scored("operational matter", DOCUMENT, DOC_ID, k=-1) == []


def test_retrieve_returns_the_same_chunks_as_retrieve_scored_without_scores():
    # Arrange
    retriever = HybridRetriever(rag=StubRag())

    # Act
    plain = retriever.retrieve("operational matter", DOCUMENT, DOC_ID, k=4)
    scored = retriever.retrieve_scored("operational matter", DOCUMENT, DOC_ID, k=4)

    # Assert
    assert plain == [chunk for chunk, _ in scored]


def test_a_chunk_found_only_by_the_keyword_side_still_surfaces():
    # Arrange — the vector stub returns a single chunk, deliberately not the one the
    # query's rare term appears in. The keyword side must still contribute it, or the
    # hybrid would be no better than vector search alone.
    chunks = chunk_text(DOCUMENT)
    stub = StubRag(order=[0])
    retriever = HybridRetriever(rag=stub)

    # Act — "39" appears only in the last paragraph.
    results = retriever.retrieve_scored("Paragraph 39", DOCUMENT, DOC_ID, k=10)
    returned = [chunk for chunk, _ in results]

    # Assert
    assert any("Paragraph 39" in chunk for chunk in returned)
    assert chunks[0] in returned  # the vector-only chunk was not dropped either
