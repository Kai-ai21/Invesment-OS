from pydantic import BaseModel, Field


class PatternData(BaseModel):
    """A recurring behaviour the AI claims to see across several reflections."""

    statement: str = Field(
        description="The observed pattern, describing behaviour rather than judging "
        "the person."
    )
    source_post_mortem_ids: list[str] = Field(
        description="The post_mortem_ids this pattern is drawn from. At least two — "
        "one reflection is an anecdote, not a pattern. Every id must be one that was "
        "actually supplied; the caller rejects the pattern otherwise."
    )
