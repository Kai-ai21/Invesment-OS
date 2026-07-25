from abc import ABC, abstractmethod


class EvidenceRetriever(ABC):
    @abstractmethod
    def retrieve(
        self, claim_text: str, document_text: str, document_id: str, k: int = 4
    ) -> list[str]:
        """Return the passages most relevant to `claim_text`, in relevance order.

        Implementations may cache embeddings per `document_id`: the same document is
        checked against many claims, so it need only be chunked and embedded once.
        """

    @abstractmethod
    def retrieve_scored(
        self, claim_text: str, document_text: str, document_id: str, k: int = 4
    ) -> list[tuple[str, float]]:
        """Like `retrieve()`, but pairs each passage with a similarity score where
        HIGHER = more similar, best first.

        Scores are for testing and observability only. They must NOT be used to
        filter passages out with a threshold: top-k retrieval is meant to always
        return k passages, and dropping "low-scoring" ones would reintroduce the
        exact silent-miss failure this design avoids.
        """
