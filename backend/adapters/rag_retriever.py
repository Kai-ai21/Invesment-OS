"""RAG retriever: chunk a document, embed it locally, and pull the passages most
relevant to a claim out of a persistent vector store.

Both heavy dependencies (sentence-transformers/torch and chromadb) are imported
lazily, inside the loaders below, so merely importing this adapter at app wiring
time costs nothing — the model and the DB are only touched on the first retrieve.
"""

import os
import threading

from backend.domain.chunking import chunk_text
from backend.ports.evidence_retriever import EvidenceRetriever

# Small, local, free. Chroma also *ships* an all-MiniLM-L6-v2 embedder, but we run
# the model ourselves and pass embeddings in explicitly so retrieval stays under
# our control and the model is loaded exactly once (see _get_model).
_EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
_COLLECTION_NAME = "evidence_chunks"
_DEFAULT_CHROMA_PATH = "./chroma_store"

# Process-wide singleton. The model pulls in torch and reads weights from disk, so
# it must never load at import time and must load only once per process even if
# several requests race for it.
_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:  # double-checked: another thread may have won the race
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(_EMBEDDING_MODEL_NAME)
    return _model


class RagRetriever(EvidenceRetriever):
    def __init__(self, chroma_path: str | None = None):
        # Precedence: explicit arg (tests pass an isolated tmp path) > env > default.
        self._chroma_path = chroma_path or os.getenv("CHROMA_PATH") or _DEFAULT_CHROMA_PATH
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            import chromadb

            client = chromadb.PersistentClient(path=self._chroma_path)
            # Cosine space (not Chroma's default squared-L2) so distances map cleanly
            # onto a bounded, interpretable similarity — see retrieve_scored.
            self._collection = client.get_or_create_collection(
                name=_COLLECTION_NAME,
                configuration={"hnsw": {"space": "cosine"}},
            )
        return self._collection

    def retrieve(
        self, claim_text: str, document_text: str, document_id: str, k: int = 4
    ) -> list[str]:
        # Same result as retrieve_scored, with the scores dropped.
        return [
            chunk
            for chunk, _ in self.retrieve_scored(
                claim_text, document_text, document_id, k
            )
        ]

    def retrieve_scored(
        self, claim_text: str, document_text: str, document_id: str, k: int = 4
    ) -> list[tuple[str, float]]:
        if not document_text.strip():
            return []

        collection = self._get_collection()
        model = _get_model()

        # (1) Embed once per document. Same instinct as content-hash dedup: if this
        # document_id is already in the store, reuse its chunks rather than re-embed.
        already_stored = collection.get(where={"document_id": document_id}, limit=1)
        if not already_stored["ids"]:
            # (2) Chunk verbatim, embed, and store with locating metadata.
            chunks = chunk_text(document_text)
            if not chunks:
                return []
            embeddings = model.encode(chunks).tolist()
            collection.add(
                ids=[f"{document_id}:{i}" for i in range(len(chunks))],
                embeddings=embeddings,
                documents=chunks,
                metadatas=[
                    {"document_id": document_id, "chunk_index": i}
                    for i in range(len(chunks))
                ],
            )

        # (3) Query with the claim, scoped to this document, top-k in relevance
        # order. Chroma returns min(k, available) results, so a k larger than the
        # chunk count simply yields everything that exists.
        query_embedding = model.encode([claim_text]).tolist()
        result = collection.query(
            query_embeddings=query_embedding,
            n_results=k,
            where={"document_id": document_id},
            include=["documents", "distances"],
        )

        # Both are column-major (one list per query); we sent one query. Texts come
        # straight from what was stored — verbatim, never normalised, so the citation
        # check can still locate them in the source.
        documents = (result.get("documents") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        # CONVENTION: the collection uses the cosine space, so Chroma returns cosine
        # DISTANCE in [0, 2] (0 = identical direction). We report cosine SIMILARITY =
        # 1 - distance, range [-1, 1], where HIGHER = more similar. Chroma already
        # orders results nearest-first, so these pairs come out best-first.
        return [(doc, 1.0 - dist) for doc, dist in zip(documents, distances)]
