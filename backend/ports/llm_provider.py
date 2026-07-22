from abc import ABC, abstractmethod

from domain.claim import ClaimData


class LLMProvider(ABC):
    @abstractmethod
    def extract_claims(self, ticker: str, reasoning: str) -> list[ClaimData]:
        """Extract falsifiable claims from an investor's reasoning about a ticker."""
