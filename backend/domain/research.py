"""Shapes for the company research page.

The whole feature is a SUMMARY OF FREE DATA — a company's own filing, restated in
plain language. It is deliberately not an analysis engine: nothing here holds a
valuation, a rating, a target, or any field an assessment could be written into.
That constraint is enforced by the shape as much as by the prompt, because a field
called `outlook` would eventually get filled with one.
"""

from pydantic import BaseModel, Field


class ResearchSummary(BaseModel):
    """The AI's restatement of a filing. Every field is OPTIONAL BY DESIGN.

    A summary is only worth showing if the passages actually covered the subject,
    so the model is told to omit anything the filing did not support rather than
    reach for general knowledge. A null here means "the filing did not say" — the
    UI leaves that card out instead of printing a confident paragraph about a
    company the model happens to know from training.
    """

    what_the_company_does: str | None = Field(
        default=None, description="2-3 plain-language sentences on the business."
    )
    how_it_makes_money: str | None = Field(
        default=None, description="2-3 plain-language sentences on revenue sources."
    )
    key_risks: list[str] = Field(
        default_factory=list,
        description="3-5 risks the filing itself names. Empty when none were retrieved.",
    )
