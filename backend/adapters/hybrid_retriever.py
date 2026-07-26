"""Hybrid retrieval: vector search fused with BM25 keyword search.

WHY both. Measured against a real NVDA 10-K (882 chunks), for the gross-margin claim
the decisive passage — "Gross margins decreased to 71.1%..." — ranked #14 by embedding
similarity and #8 by BM25. Neither put it first, and they failed for DIFFERENT reasons:

  * Embeddings match topic, not terminology. Every page of a 10-K is "about finance",
    so fair-value notes and stock-performance graphs score nearly as well as the
    margin discussion. Scores bunch together (the top-30 spanned barely 0.1).
  * BM25 matches exact terms, so it finds "margins" — but it is fooled by long
    risk-factor prose that repeats the same words without reporting a figure.

Because they are wrong in uncorrelated ways, a passage that BOTH rank highly is a much
stronger signal than one either ranks first alone. That is exactly what Reciprocal Rank
Fusion exploits.

WHY RRF rather than adding the scores. Cosine similarity (~0.4-0.5 here) and BM25
scores (unbounded, ~8-12 here) live on incomparable scales, so a weighted sum would be
dominated by whichever happens to be numerically larger, and would need re-tuning per
corpus. RRF throws the magnitudes away and keeps only the RANKS, which are directly
comparable between any two rankers. It needs no normalisation and no tuning.
"""

from backend.domain.bm25 import rank_chunks
from backend.domain.chunking import chunk_text
from backend.ports.evidence_retriever import EvidenceRetriever
from backend.adapters.rag_retriever import RagRetriever

# How many candidates to pull from EACH ranker before fusing. Fusion can only reward a
# chunk both rankers liked if both rankers were asked for enough candidates to express
# that — with a pool of 4 the two lists may not overlap at all. This is internal: the
# caller's `k` still decides how many passages come back.
_FUSION_POOL = 50

# The RRF damping constant, from Cormack et al. (2009), where 60 is the value found to
# work well across test collections and has been the convention since. It flattens the
# difference between adjacent top ranks: 1/(60+0) and 1/(60+1) are nearly equal, so
# being #0 rather than #1 in one list is a small edge, while appearing in BOTH lists is
# a large one. A small constant (say 1) would make rank #0 overwhelmingly dominant and
# defeat the point of fusing.
RRF_K = 60


def fuse_rankings(ranked_lists: list[list[str]]) -> dict[str, float]:
    """Reciprocal Rank Fusion over several ranked lists of chunk texts.

        score(chunk) = sum over lists of 1 / (RRF_K + rank_in_that_list)

    Ranks are 0-based. A chunk missing from a list simply contributes nothing from that
    list — it is never penalised and never dropped, so a passage found by only one
    ranker still surfaces.
    """
    fused: dict[str, float] = {}
    for ranking in ranked_lists:
        for rank, chunk in enumerate(ranking):
            fused[chunk] = fused.get(chunk, 0.0) + 1.0 / (RRF_K + rank)
    return fused


def order_by_fused_score(
    fused: dict[str, float], chunks: list[str]
) -> list[tuple[str, float]]:
    """Sort fused results best-first, breaking ties by position in the document.

    Dict iteration order would otherwise depend on insertion, which depends on which
    ranker saw a chunk first — so equal scores could reorder between runs. Falling back
    to document position makes the output fully deterministic. `setdefault` keeps the
    first position when a document repeats a chunk verbatim, and a chunk absent from
    `chunks` sorts last rather than raising.
    """
    position_of: dict[str, int] = {}
    for index, chunk in enumerate(chunks):
        position_of.setdefault(chunk, index)

    return sorted(
        fused.items(),
        key=lambda item: (-item[1], position_of.get(item[0], len(chunks))),
    )


class HybridRetriever(EvidenceRetriever):
    def __init__(
        self, rag: RagRetriever | None = None, chroma_path: str | None = None
    ):
        # Composed, not reimplemented: the vector side keeps RagRetriever's embedding
        # cache and per-document dedup. Injectable so tests can stub the vector ranking
        # and exercise fusion without loading a model.
        self._rag = rag if rag is not None else RagRetriever(chroma_path=chroma_path)

    def retrieve(
        self, claim_text: str, document_text: str, document_id: str, k: int = 4
    ) -> list[str]:
        return [
            chunk
            for chunk, _ in self.retrieve_scored(
                claim_text, document_text, document_id, k
            )
        ]

    def retrieve_scored(
        self, claim_text: str, document_text: str, document_id: str, k: int = 4
    ) -> list[tuple[str, float]]:
        """Passages ranked by fused score, best first.

        NOTE the returned score is an RRF score (small, ~0.01-0.03), NOT a similarity.
        It is comparable only between chunks of this same call — never against the
        cosine similarities RagRetriever reports.
        """
        if k <= 0 or not document_text.strip():
            return []

        # Both rankers must score the SAME chunks or fusion compares different things.
        # RagRetriever chunks with chunk_text() and default settings internally, so
        # calling it the same way here reproduces its exact chunk list.
        chunks = chunk_text(document_text)
        if not chunks:
            return []

        vector_ranking = [
            chunk
            for chunk, _ in self._rag.retrieve_scored(
                claim_text, document_text, document_id, k=_FUSION_POOL
            )
        ]

        # rank_chunks pads to k with zero-scoring chunks once the matches run out.
        # Those have no keyword overlap at all, so admitting them would hand real RRF
        # weight to chunks ordered only by their position in the document.
        keyword_ranking = [
            chunks[index]
            for index, score in rank_chunks(claim_text, chunks, k=_FUSION_POOL)
            if score > 0
        ]

        fused = fuse_rankings([vector_ranking, keyword_ranking])

        # Chunks are returned exactly as chunk_text produced them — verbatim substrings
        # of the document, never normalised, so the citation check can still locate a
        # quote inside them.
        return order_by_fused_score(fused, chunks)[:k]
