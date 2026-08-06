"""Gemini adapter. Schema enforcement via `response_schema`, which takes a
Pydantic model directly — the SDK derives the schema and the model is decoded
against it.

The prompts are NOT here; they are shared with every other adapter in
adapters/prompts.py. See that module for why.
"""

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from backend.adapters.prompts import (
    ENHANCE_PROMPT,
    EXTRACTION_PROMPT,
    FILING_PROMPT,
    PATTERNS_PROMPT,
    REFLECTION_PROMPT,
    RESEARCH_PROMPT,
    VERIFICATION_PROMPT,
    ClaimsResponse,
    EnhancedReasoning,
    PatternsResponse,
    ReflectionQuestion,
    numbered_passages,
)
from backend.domain.claim import ClaimData
from backend.domain.filing import FilingSummary
from backend.domain.pattern import PatternData
from backend.domain.research import ResearchSummary
from backend.domain.verification import VerdictData
from backend.ports.llm_provider import LLMProvider

load_dotenv()

MODEL_NAME = "gemini-3.6-flash"


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def extract_claims(self, ticker: str, reasoning: str) -> list[ClaimData]:
        prompt = EXTRACTION_PROMPT.format(ticker=ticker, reasoning=reasoning)

        response = self._client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ClaimsResponse,
            ),
        )

        parsed = ClaimsResponse.model_validate_json(response.text)
        return parsed.claims

    def verify_claim(
        self, claim_statement: str, proof_condition: str, break_condition: str, document_text: str
    ) -> VerdictData:
        prompt = VERIFICATION_PROMPT.format(
            statement=claim_statement,
            proof_condition=proof_condition,
            break_condition=break_condition,
            document_text=document_text,
        )

        response = self._client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VerdictData,
            ),
        )

        return VerdictData.model_validate_json(response.text)

    def generate_reflection_question(
        self,
        original_reasoning: str,
        broken_claim_statement: str,
        broken_claim_proof: str,
        broken_claim_break: str,
        evidence_quotes: list[str],
    ) -> str:
        # Numbered and quoted so the model can point at a specific one, and so the
        # caller's grounding check has exactly these strings to compare against.
        formatted_quotes = "\n".join(
            f'{index}. "{quote}"' for index, quote in enumerate(evidence_quotes, start=1)
        )

        prompt = REFLECTION_PROMPT.format(
            original_reasoning=original_reasoning,
            statement=broken_claim_statement,
            proof_condition=broken_claim_proof,
            break_condition=broken_claim_break,
            evidence_quotes=formatted_quotes or "(none recorded)",
        )

        response = self._client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ReflectionQuestion,
            ),
        )

        return ReflectionQuestion.model_validate_json(response.text).question

    def enhance_reasoning(self, ticker: str, raw_reasoning: str) -> str:
        prompt = ENHANCE_PROMPT.format(ticker=ticker, raw_reasoning=raw_reasoning)

        response = self._client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EnhancedReasoning,
            ),
        )

        return EnhancedReasoning.model_validate_json(response.text).reasoning

    def summarise_company(
        self,
        ticker: str,
        profile_summary: str | None,
        business_passages: list[str],
        risk_passages: list[str],
    ) -> ResearchSummary:
        prompt = RESEARCH_PROMPT.format(
            ticker=ticker,
            profile_summary=profile_summary or "(none available)",
            business_passages=numbered_passages(business_passages),
            risk_passages=numbered_passages(risk_passages),
        )

        response = self._client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ResearchSummary,
            ),
        )

        return ResearchSummary.model_validate_json(response.text)

    def summarise_filing(
        self,
        ticker: str,
        form: str,
        filing_title: str,
        results_passages: list[str],
        events_passages: list[str],
        claims: list[dict],
    ) -> FilingSummary:
        # One labelled block per claim, so the model can cite an id exactly. The
        # no-claims case says so in words rather than leaving the section blank —
        # an empty list under a heading invites the model to populate it.
        formatted_claims = (
            "\n\n".join(
                f"claim_id: {claim['claim_id']}\nstatement: {claim['statement']}"
                for claim in claims
            )
            or "(the reader has no claims about this company — relevant_claim_ids "
            "must be an empty list)"
        )

        prompt = FILING_PROMPT.format(
            ticker=ticker,
            form=form,
            filing_title=filing_title,
            results_passages=numbered_passages(results_passages),
            events_passages=numbered_passages(events_passages),
            claims=formatted_claims,
        )

        response = self._client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FilingSummary,
            ),
        )

        return FilingSummary.model_validate_json(response.text)

    def generate_patterns(self, post_mortems: list[dict]) -> list[PatternData]:
        # Rendered as a labelled block per reflection so the model can cite ids exactly.
        formatted = "\n\n".join(
            "\n".join(
                [
                    f"post_mortem_id: {item['post_mortem_id']}",
                    f"ticker: {item['ticker']}",
                    f"date: {item['created_at']}",
                    f"claim that broke: {item['broken_claim_statement']}",
                    f"question asked: {item['prompt_question']}",
                    f"their answer: {item['user_response']}",
                ]
            )
            for item in post_mortems
        )

        prompt = PATTERNS_PROMPT.format(post_mortems=formatted)

        response = self._client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PatternsResponse,
            ),
        )

        return PatternsResponse.model_validate_json(response.text).patterns
