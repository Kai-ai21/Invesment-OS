from abc import ABC, abstractmethod

from backend.domain.document import DocumentData


class DocumentSource(ABC):
    @abstractmethod
    def load(self, raw_text: str, title: str | None = None) -> DocumentData:
        """Load raw input into a normalized DocumentData (computing its content hash)."""
