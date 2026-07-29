from abc import ABC, abstractmethod

from backend.domain.claim import ClaimData
from backend.domain.pattern import PatternData
from backend.domain.research import ResearchSummary
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

    @abstractmethod
    def summarise_company(
        self,
        ticker: str,
        profile_summary: str | None,
        business_passages: list[str],
        risk_passages: list[str],
    ) -> ResearchSummary:
        """Restate a company's own filing in plain language.

        DESCRIBES ONLY. Never evaluates the company as an investment, and uses
        nothing beyond the profile text and passages supplied — the passages come
        from a retrieval pass over one filing, so anything outside them would be
        the model's training data rather than the company's disclosure.

        Any field the passages do not cover comes back None, and `key_risks` comes
        back empty rather than padded.
        """

    @abstractmethod
    def generate_patterns(self, post_mortems: list[dict]) -> list[PatternData]:
        """Find recurring behaviours across a set of answered reflections.

        Each input dict carries post_mortem_id, ticker, broken_claim_statement,
        prompt_question, user_response and created_at.

        An EMPTY list is a valid and expected answer — most small sets contain no
        genuine pattern. Every returned pattern must cite at least two of the supplied
        post_mortem_ids; the caller rejects any that cites unknown ids or too few.
        """
