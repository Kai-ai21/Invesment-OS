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

    @abstractmethod
    def generate_reflection_question(
        self,
        original_reasoning: str,
        broken_claim_statement: str,
        broken_claim_proof: str,
        broken_claim_break: str,
        evidence_quotes: list[str],
    ) -> str:
        """Write one question inviting the investor to re-examine the thinking that led
        to a claim which has since broken.

        Must reference the specific claim and at least one of `evidence_quotes`, and may
        reference nothing beyond what is passed in — the caller checks that.
        """
