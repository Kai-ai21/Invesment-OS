from abc import ABC, abstractmethod

from backend.domain.claim import ClaimData
from backend.domain.filing import FilingSummary
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
    def enhance_reasoning(self, ticker: str, raw_reasoning: str) -> str:
        """Rewrite an investor's own reasoning to be sharper and more checkable.

        EDITS, NEVER AUTHORS. Every idea in the result must be traceable to the
        input: no new reasons, no new metrics, and above all no invented numbers or
        timeframes — this app later tests the user's claims against reality, so a
        threshold the model made up would become a bar the user never set.

        Returns the input UNCHANGED when it is too thin to sharpen without
        inventing. That is a correct answer, not a failure, and the caller reports
        it as "already specific enough" rather than pretending something happened.
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
    def summarise_filing(
        self,
        ticker: str,
        form: str,
        filing_title: str,
        results_passages: list[str],
        events_passages: list[str],
        claims: list[dict],
    ) -> FilingSummary:
        """Read one SEC filing back in plain language, from retrieved passages only.

        READS, NEVER JUDGES. This is the softest output in the product — it is not
        checked against anything, so the discipline has to come from the prompt and
        from the shape: no verdict, no confidence, and above all no view on whether
        what the filing says is good or bad. A summary that grades the news would be
        mistaken for evidence, which is scored, cited and validated.

        Each `claims` dict carries claim_id and statement, for the user's own theses
        on this ticker. Pass an EMPTY list when they have none — the model is then
        told there is nothing to match against, rather than being handed an empty
        list to be creative with.

        `relevant_claim_ids` comes back EMPTY most of the time and that is the
        expected answer. Every id it does return must be one supplied here; the
        caller drops the rest.
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
