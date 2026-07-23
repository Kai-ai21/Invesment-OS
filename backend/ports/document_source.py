from abc import ABC, abstractmethod

from backend.domain.document import DocumentData


class DocumentSource(ABC):
    @abstractmethod
    def load(self, ref: str, title: str | None = None) -> DocumentData:
        """ref is source-specific — raw text for paste, a filing URL for edgar."""
