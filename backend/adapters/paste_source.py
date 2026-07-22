import hashlib

from backend.domain.document import DocumentData
from backend.ports.document_source import DocumentSource


class PasteSource(DocumentSource):
    def load(self, raw_text: str, title: str | None = None) -> DocumentData:
        content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        return DocumentData(
            source_type="paste",
            title=title,
            content_hash=content_hash,
            raw_text=raw_text,
        )
