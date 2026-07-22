from abc import ABC, abstractmethod

from backend.domain.claim import ClaimData
from backend.domain.verification import VerdictData


class LLMProvider(ABC):
    @abstractmethod
    def extract_claims(self, ticker: str, reasoning: str) -> list[ClaimData]:
        """Extract falsifiable claims from an investor's reasoning about a ticker."""

    @abstractmethod
    def verify_claim(
        self, claim_statement: str, proof_condition: str, break_condition: str, document_text: str
    ) -> VerdictData:
        """Judge whether a document supports, contradicts, or is neutral on a claim."""
