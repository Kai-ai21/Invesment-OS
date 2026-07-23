import hashlib

from backend.domain.document import DocumentData
from backend.ports.document_source import DocumentSource


class PasteSource(DocumentSource):
    def load(self, ref: str, title: str | None = None) -> DocumentData:
        # For a paste, `ref` is the raw text itself.
        content_hash = hashlib.sha256(ref.encode("utf-8")).hexdigest()
        return DocumentData(
            source_type="paste",
            title=title,
            content_hash=content_hash,
            raw_text=ref,
        )
