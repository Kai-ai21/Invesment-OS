import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from backend.domain.claim import ClaimData
from backend.domain.pattern import PatternData
from backend.domain.research import ResearchSummary
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


ENHANCE_PROMPT = """An investor has written why they believe in {ticker}. Rewrite it so it \
is sharper and more checkable — WITHOUT adding anything they did not say.

Their reasoning:
\"\"\"{raw_reasoning}\"\"\"

Rules:

1. SHARPEN, DO NOT INVENT. Every idea in your rewrite must be traceable to something \
they actually wrote. Do not add a new reason, a new metric, a new competitor, a new \
risk, or a new belief. If you are adding an idea rather than tightening one of theirs, \
you have already broken this rule. You are editing their sentence, not writing yours.

2. NEVER INVENT A NUMBER. This is the way this task goes wrong, so it gets its own \
rule. Making "margins are good" into "gross margins remain high" is exactly right. \
Making it "gross margins above 72%" is FORBIDDEN — 72% is a threshold they never chose, \
and this app will later test their claims against reality, so a number you made up \
becomes a bar they never set. If they gave no figure, your rewrite has no figure. If \
they gave one, keep it exactly as they wrote it. The same goes for timeframes: do not \
turn "for a while" into "over the next four quarters".

3. THEIR VOICE, FIRST PERSON. This is their thesis and it stays theirs. Keep "I think", \
"I expect", "I'm betting". Do not switch to "the investor believes" or to a neutral \
report. Keep their vocabulary — if they wrote "chips", do not upgrade it to \
"semiconductor products".

4. SIMILAR LENGTH. A tightened version of their paragraph, not an essay built from it. \
Roughly the same number of sentences. Never more than about 30% longer.

5. NO ADVICE, NO VERDICT. Do not say whether the thesis is good, strong, weak, risky or \
well-reasoned. Do not suggest buying, selling, sizing or hedging. Do not add \
counterarguments or caveats they did not raise. You are not commenting on their \
thinking, only sharpening how it is written.

6. IF YOU CANNOT SHARPEN IT WITHOUT INVENTING, RETURN IT UNCHANGED. Some input is too \
thin to work with — "amazon good" contains one idea and no reasoning, and any \
"improvement" would be you writing a thesis for them. In that case return their text \
EXACTLY as given, character for character. Returning the input unchanged is a correct, \
expected answer and is always better than fabricating.

Return only the rewritten reasoning."""


RESEARCH_PROMPT = """You are restating a company's own SEC filing in plain language, for \
someone who wants to understand what {ticker} does before forming their own view.

The company's profile description:
\"\"\"{profile_summary}\"\"\"

Passages retrieved from the filing about the BUSINESS:
{business_passages}

Passages retrieved from the filing about RISK FACTORS:
{risk_passages}

Produce:
- what_the_company_does: 2 to 3 sentences, plain language
- how_it_makes_money: 2 to 3 sentences on where revenue actually comes from
- key_risks: 3 to 5 short bullet points, each drawn from the RISK passages above

Rules:

1. USE ONLY THE MATERIAL ABOVE. Every product, segment, customer, figure and risk you \
mention must appear in the profile description or the passages. You may well recognise this \
company — ignore everything you know about it. Invent no numbers, no dates, no market shares, \
no customer names. If a figure is not in the text above, it does not go in your answer.

2. NEVER EVALUATE THE COMPANY AS AN INVESTMENT. This is a hard rule with no exceptions. Do \
not write "well-positioned", "attractive", "strong", "concerning", "impressive", "dominant", \
"challenged", or any other word that grades the business. Do not say whether a risk is likely, \
serious, or manageable. Do not compare the company favourably or unfavourably to competitors. \
Do not mention valuation, price, whether shares are cheap or expensive, or what an investor \
should do. Describe WHAT THE FILING SAYS and stop there.

3. PLAIN LANGUAGE. Explain jargon instead of repeating it. If the filing says "hyperscale \
CSPs", write "the largest cloud computing providers". If it says "design wins", explain that \
a customer chose the company's chip for a product. Someone who does not work in the industry \
should understand every sentence.

4. OMIT WHAT IS NOT COVERED. If the passages do not explain how the company earns revenue, \
return null for how_it_makes_money. If no risk passages were supplied, return an empty list. \
A missing field is correct and expected; a guessed one is a failure. Never write "the filing \
does not say" as the field's value — return null instead.

5. RISKS ARE THE COMPANY'S OWN STATED RISKS, not yours. Each bullet paraphrases something the \
risk passages actually raise. Do not add risks you think apply. Do not rank them.

Return the structured summary."""


class ClaimsResponse(BaseModel):
    claims: list[ClaimData]


class PatternsResponse(BaseModel):
    """Wrapper so the model can return an empty list cleanly."""

    patterns: list[PatternData]


class ReflectionQuestion(BaseModel):
    """Structured output so the model returns the question alone, with no preamble."""

    question: str


class EnhancedReasoning(BaseModel):
    """Structured output so the model returns the rewrite alone — no "Here is a
    sharper version:" preamble, which would otherwise end up in the user's thesis."""

    reasoning: str


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
        def numbered(passages: list[str]) -> str:
            # Numbered blocks so the model can tell the passages apart and cannot
            # blur several into one invented composite.
            return (
                "\n\n".join(
                    f"[{index}] {passage}"
                    for index, passage in enumerate(passages, start=1)
                )
                or "(none retrieved)"
            )

        prompt = RESEARCH_PROMPT.format(
            ticker=ticker,
            profile_summary=profile_summary or "(none available)",
            business_passages=numbered(business_passages),
            risk_passages=numbered(risk_passages),
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
