"""Groq adapter. Same port, same prompts, different schema enforcement.

⚠️ MODEL CHOICE IS NOT FREE HERE. Groq only supports `strict: true` — real
constrained decoding, where the output is GUARANTEED to match the schema — on
`openai/gpt-oss-20b` and `openai/gpt-oss-120b`. Every other model it hosts,
Llama included, offers `strict: false`, which merely attempts the schema and
"may occasionally error". This app decodes every response into a Pydantic model
and treats a parse failure as a failed check, so best-effort is not good enough:
pointing MODEL_NAME at a Llama model silently downgrades the guarantee.

⚠️ AND STRICT MODE FORBIDS OPTIONAL FIELDS. Pydantic emits neither
`additionalProperties: false` nor a fully-populated `required` list, so a schema
that Gemini accepts is REJECTED by Groq until walked — see `harden`.
"""

import os

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel

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

# The larger of the two strict-capable models. The 20b variant is the fallback if
# the 120b's token budget proves too tight; both enforce the schema identically,
# so the choice is quality against throughput, never correctness.
MODEL_NAME = "openai/gpt-oss-120b"

# Low but non-zero: Groq silently coerces 0 to 1e-8, so writing 0 here would only
# disguise what is actually being sent.
TEMPERATURE = 0.1

# The SDK retries connection errors and 429s itself. The free tier's ceiling is
# 8K tokens per MINUTE, and one filing summary is roughly half that, so a burst
# hitting the limit is an expected condition rather than an exceptional one.
MAX_RETRIES = 3

# ⚠️ GROQ-ONLY ADDENDUM, appended to the two prompts that were written when a
# field could simply be left out. Under constrained decoding it CANNOT be: every
# key in the schema is emitted, always. The prompts already said "return null"
# and "return an empty list" in their bodies, so this only removes the ambiguity
# their "OMIT WHAT IS NOT COVERED" headings would otherwise leave for a literal
# reader. It adds no instruction about content — only about how absence is
# spelled — which is why it can live in the adapter without the shared prompts
# and this drifting apart in meaning.
ABSENCE_ADDENDUM = """

HOW TO EXPRESS SOMETHING THE PASSAGES DID NOT COVER: every field listed above \
must appear in your answer, so an uncovered field is written as null (for a \
single value) or as [] (for a list). Never drop the field, and never write a \
sentence such as "not stated" or "the filing does not say" as its value — those \
are text where a null belongs."""


def harden(node: object) -> object:
    """Rewrite a Pydantic-generated JSON schema into one Groq strict mode accepts.

    Two edits, applied to every object at any depth including inside `$defs`:
    `additionalProperties: false`, and `required` listing EVERY property.

    ⚠️ FORCING `required` IS NOT A SEMANTIC CHANGE HERE, but it is worth knowing
    why. `ResearchSummary.how_it_makes_money` is `str | None`, which Pydantic
    renders as `anyOf: [string, null]` — forcing it required means the model must
    emit the key, and null remains a legal value for it, which is exactly the
    "the filing did not say" answer the field was designed to carry. List fields
    default to empty rather than absent for the same reason. What this WOULD
    break is a field whose absence means something different from its null, and
    there is none on this port.
    """
    if isinstance(node, dict):
        walked = {key: harden(value) for key, value in node.items()}
        if walked.get("type") == "object":
            walked["additionalProperties"] = False
            if "properties" in walked:
                walked["required"] = list(walked["properties"].keys())
        return walked
    if isinstance(node, list):
        return [harden(item) for item in node]
    return node


class GroqProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = Groq(api_key=os.getenv("GROQ_API_KEY"), max_retries=MAX_RETRIES)

    def _structured[T: BaseModel](self, prompt: str, schema: type[T]) -> T:
        """One call, decoded into `schema`. Every method below goes through here.

        `include_reasoning=False` because gpt-oss is a reasoning model: its chain
        of thought is returned in a separate `reasoning` field rather than inside
        `content`, so it would not corrupt the JSON, but it is billed as
        completion tokens and this tier is metered per minute. Nothing downstream
        reads it.
        """
        response = self._client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMPERATURE,
            include_reasoning=False,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": harden(schema.model_json_schema()),
                },
            },
        )

        content = response.choices[0].message.content or ""
        # Validated rather than trusted. Constrained decoding makes malformed JSON
        # essentially impossible, but a truncated response (hitting the token
        # ceiling mid-object) is NOT impossible on this tier, and that arrives as
        # invalid JSON. Failing here is correct: the caller treats a provider
        # error as a failed check rather than writing a half-parsed result.
        return schema.model_validate_json(content)

    def extract_claims(self, ticker: str, reasoning: str) -> list[ClaimData]:
        prompt = EXTRACTION_PROMPT.format(ticker=ticker, reasoning=reasoning)
        return self._structured(prompt, ClaimsResponse).claims

    def verify_claim(
        self, claim_statement: str, proof_condition: str, break_condition: str, document_text: str
    ) -> VerdictData:
        prompt = VERIFICATION_PROMPT.format(
            statement=claim_statement,
            proof_condition=proof_condition,
            break_condition=break_condition,
            document_text=document_text,
        )
        return self._structured(prompt, VerdictData)

    def generate_reflection_question(
        self,
        original_reasoning: str,
        broken_claim_statement: str,
        broken_claim_proof: str,
        broken_claim_break: str,
        evidence_quotes: list[str],
    ) -> str:
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
        return self._structured(prompt, ReflectionQuestion).question

    def enhance_reasoning(self, ticker: str, raw_reasoning: str) -> str:
        prompt = ENHANCE_PROMPT.format(ticker=ticker, raw_reasoning=raw_reasoning)
        return self._structured(prompt, EnhancedReasoning).reasoning

    def summarise_company(
        self,
        ticker: str,
        profile_summary: str | None,
        business_passages: list[str],
        risk_passages: list[str],
    ) -> ResearchSummary:
        prompt = (
            RESEARCH_PROMPT.format(
                ticker=ticker,
                profile_summary=profile_summary or "(none available)",
                business_passages=numbered_passages(business_passages),
                risk_passages=numbered_passages(risk_passages),
            )
            + ABSENCE_ADDENDUM
        )
        return self._structured(prompt, ResearchSummary)

    def summarise_filing(
        self,
        ticker: str,
        form: str,
        filing_title: str,
        results_passages: list[str],
        events_passages: list[str],
        claims: list[dict],
    ) -> FilingSummary:
        formatted_claims = (
            "\n\n".join(
                f"claim_id: {claim['claim_id']}\nstatement: {claim['statement']}"
                for claim in claims
            )
            or "(the reader has no claims about this company — relevant_claim_ids "
            "must be an empty list)"
        )

        prompt = (
            FILING_PROMPT.format(
                ticker=ticker,
                form=form,
                filing_title=filing_title,
                results_passages=numbered_passages(results_passages),
                events_passages=numbered_passages(events_passages),
                claims=formatted_claims,
            )
            + ABSENCE_ADDENDUM
        )
        return self._structured(prompt, FilingSummary)

    def generate_patterns(self, post_mortems: list[dict]) -> list[PatternData]:
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
        return self._structured(prompt, PatternsResponse).patterns


__all__ = ["GroqProvider", "harden", "MODEL_NAME"]
