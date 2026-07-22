import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from backend.domain.claim import ClaimData
from backend.domain.verification import VerdictData
from backend.ports.llm_provider import LLMProvider

load_dotenv()

MODEL_NAME = "gemini-3.6-flash"

EXTRACTION_PROMPT = """You are analyzing an investor's plain-language reasoning for why they \
believe {ticker} is a good investment.

Break their reasoning down into 2 to 4 distinct, falsifiable claims. Each claim needs:
- statement: the specific claim being made
- proof_condition: a concrete, observable condition that would CONFIRM the claim is playing out
- break_condition: a concrete, observable condition that would INVALIDATE the claim
- is_core: true if this claim is central to the thesis, false if it's a minor supporting point

"Falsifiable" means the condition can be checked against real-world data or events. For example:
GOOD proof_condition: "iPhone revenue grows more than 5% year-over-year in the next two \
quarterly earnings reports"
BAD proof_condition: "the company continues to do well" (too vague to ever confirm or deny)

Investor's reasoning about {ticker}:
\"\"\"{reasoning}\"\"\"
"""

VERIFICATION_PROMPT = """You are checking whether a document bears on a specific investment claim.

The claim:
- statement: {statement}
- proof_condition (would CONFIRM the claim): {proof_condition}
- break_condition (would INVALIDATE the claim): {break_condition}

Decide whether the document SUPPORTS, CONTRADICTS, or is NEUTRAL on the claim:
- "supports": the document provides evidence that the proof_condition is being met
- "contradicts": the document provides evidence that the break_condition is being met
- "neutral": the document says nothing relevant to the claim

Rules:
- evidence_quote MUST be copied VERBATIM (word-for-word) from the document text below, so it can
  later be located in the source. Do not paraphrase, summarize, or fix typos.
- If nothing in the document is relevant, set verdict = "neutral" and evidence_quote = "" (empty).
- confidence is your confidence in the verdict, from 0.0 to 1.0.

Document text:
\"\"\"{document_text}\"\"\"
"""


class ClaimsResponse(BaseModel):
    claims: list[ClaimData]


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
