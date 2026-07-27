import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from backend.domain.claim import ClaimData
from backend.domain.pattern import PatternData
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


REFLECTION_PROMPT = """An investor wrote an investment thesis. One of its claims has since been \
contradicted by evidence. Write ONE question that helps them examine the reasoning they used \
when they FIRST wrote it.

Their original reasoning:
\"\"\"{original_reasoning}\"\"\"

The claim that broke:
- statement: {statement}
- proof_condition (what would have CONFIRMED it): {proof_condition}
- break_condition (what would have INVALIDATED it): {break_condition}

Evidence that contradicted it:
{evidence_quotes}

Write two to three sentences of context, then one question. Rules:

1. BE SPECIFIC. Reference this claim and at least one of the evidence quotes above. Generic \
questions are forbidden — never write "what did you learn?", "what would you do differently?", \
or anything that would fit any thesis unchanged. If your question would still make sense for a \
different company, it is wrong.

2. ASK ABOUT THEIR THINKING AT THE TIME, not about what to do now. Good: "What made you \
confident that margins would hold above 72%?" or "What were you reading that suggested \
competitors could not close the gap?" Bad: anything asking what they should do next.

3. BE FACTUAL AND DIRECT, NEVER JUDGEMENTAL. Describe what happened; do not evaluate the person. \
Never write "you should have", "your mistake was", "you failed to", or "you overlooked". State \
what the evidence showed and ask about the reasoning — the investor draws their own conclusions.

4. NEVER GIVE INVESTMENT ADVICE. Do not suggest buying, selling, holding, or adjusting anything. \
Do not predict what happens next. Do not evaluate whether the thesis is still valid. This is a \
hard rule with no exceptions.

5. USE ONLY THE MATERIAL ABOVE. Every figure, date, company and fact you mention must appear in \
the reasoning, the claim, or the evidence quotes. Invent nothing. If you quote, copy the words \
VERBATIM from an evidence quote — do not paraphrase inside quotation marks.

Return only the context and the question."""


PATTERNS_PROMPT = """You are reviewing an investor's own written reflections on theses that \
went wrong. Identify recurring behaviours ACROSS them.

The reflections:
{post_mortems}

Rules:

1. CITE YOUR EVIDENCE. Every pattern must list the post_mortem_ids it is drawn from, and \
must be supported by AT LEAST TWO of them. One reflection is an anecdote, not a pattern — do \
not emit it. Use only ids that appear above; never invent one.

2. DESCRIBE, DO NOT JUDGE. Write about the behaviour visible in the text, not about the \
person's character or competence. Good: "Three of these reflections mention trusting \
management guidance without seeking independent confirmation." Forbidden: "You are gullible", \
"you repeatedly fail to", "your weakness is", or any sentence whose subject is what the \
investor IS rather than what they DID.

3. NEVER GIVE INVESTMENT ADVICE. Do not suggest buying, selling, holding, or changing a \
process. Do not recommend what to do differently. Patterns describe the past only. This is a \
hard rule with no exceptions.

4. USE ONLY THE MATERIAL ABOVE. Every ticker, claim and quotation must come from the \
reflections provided. Invent nothing.

5. RETURN AN EMPTY LIST IF THERE IS NO GENUINE RECURRING BEHAVIOUR. This is a valid and \
EXPECTED answer. A handful of reflections about different companies usually share nothing \
real. Do not manufacture a pattern to fill the space — a false pattern about someone's own \
behaviour is worse than saying nothing.

6. AT MOST THREE patterns. Quality over volume. Two well-evidenced observations beat three \
where the last is padding.

Return the patterns as a list, or an empty list."""


class ClaimsResponse(BaseModel):
    claims: list[ClaimData]


class PatternsResponse(BaseModel):
    """Wrapper so the model can return an empty list cleanly."""

    patterns: list[PatternData]


class ReflectionQuestion(BaseModel):
    """Structured output so the model returns the question alone, with no preamble."""

    question: str


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
