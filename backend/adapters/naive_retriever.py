from backend.ports.evidence_retriever import EvidenceRetriever


class NaiveRetriever(EvidenceRetriever):
    """The M2 behaviour made explicit: hand the whole document back as a single
    passage, no retrieval. Kept deliberately as the baseline RAG is measured
    against — do not delete it when RagRetriever becomes the default.
    """

    # The whole document is the single "passage", so there is nothing to rank; the
    # score is a fixed sentinel (maximal similarity), never a real measurement.
    _FIXED_SCORE = 1.0

    def retrieve(
        self, claim_text: str, document_text: str, document_id: str, k: int = 4
    ) -> list[str]:
        return [document_text]

    def retrieve_scored(
        self, claim_text: str, document_text: str, document_id: str, k: int = 4
    ) -> list[tuple[str, float]]:
        return [(document_text, self._FIXED_SCORE)]
