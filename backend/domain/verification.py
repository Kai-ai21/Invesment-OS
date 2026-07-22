from pydantic import BaseModel, Field


class VerdictData(BaseModel):
    """The AI's judgement of how a document bears on a single claim."""

    verdict: str = Field(
        description="One of 'supports', 'contradicts', or 'neutral' for this claim."
    )
    confidence: float = Field(description="Confidence in the verdict, from 0.0 to 1.0.")
    evidence_quote: str = Field(
        description="An EXACT quote copied verbatim from the document, or '' if none is relevant."
    )
    reasoning: str = Field(description="A short explanation of the verdict.")
