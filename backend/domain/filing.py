"""Shapes for the filing reader.

WHAT THIS IS. A plain-language restatement of one SEC filing the user asked to
read. It is READING, not evidence: nothing here is scored, nothing is checked
against a claim, and nothing it produces is ever written to the evidence log or
allowed to move a thesis status.

That boundary is enforced by the SHAPE as much as by the prompt, in the same way
domain/research.py has no `outlook` field. There is deliberately no verdict, no
confidence, no sentiment and no recommendation anywhere below — a field called
`assessment` would eventually be filled with one, and the moment a summary
carries a verdict it becomes indistinguishable from an evidence event.

`relevant_claim_ids` is the ONE place the model is allowed to point at the user's
own work, and it points only — it says "this filing talks about the same subject
as that claim", never whether it supports or undermines it. The ids are validated
in code before anything is shown; see services/filing_service.py.
"""

from pydantic import BaseModel, Field


class NotableNumber(BaseModel):
    """One figure the filing reports, with what it is a figure OF.

    The pairing is the point. "$26.0 billion" alone is a number the reader has to
    go and re-derive the meaning of, and a number whose meaning the reader guesses
    is worse than no number at all.
    """

    figure: str = Field(
        description="The figure exactly as the filing states it, e.g. '$26.0 billion' "
        "or '71.1%'. Copied, never recalculated and never converted."
    )
    what_it_measures: str = Field(
        description="What the figure is a measure of, in plain language, e.g. "
        "'revenue for the quarter' or 'gross margin, down from 74.0% a year earlier'."
    )


class FilingSummary(BaseModel):
    """The AI's reading of one filing, from retrieved passages only."""

    filing_type_explained: str = Field(
        description="One sentence on what this KIND of filing is for — what a 10-K, "
        "10-Q or 8-K is — for a reader who has never opened one."
    )
    key_points: list[str] = Field(
        default_factory=list,
        description="4-6 short bullets of what THIS filing actually says. Not what "
        "the form type usually contains.",
    )
    notable_numbers: list[NotableNumber] = Field(
        default_factory=list,
        description="Figures this filing reports, each paired with what it measures. "
        "Empty when the passages carried no figures.",
    )
    relevant_claim_ids: list[str] = Field(
        default_factory=list,
        description="Ids of the user's claims this filing genuinely discusses. AN "
        "EMPTY LIST IS THE EXPECTED ANSWER most of the time. Every id must be one "
        "that was supplied; the caller drops any it does not recognise.",
    )
