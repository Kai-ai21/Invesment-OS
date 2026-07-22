from pydantic import BaseModel, Field


class ClaimData(BaseModel):
    """A single falsifiable claim extracted from an investor's reasoning."""

    statement: str = Field(description="The specific claim being made.")
    proof_condition: str = Field(
        description="A concrete, observable condition that would CONFIRM this claim."
    )
    break_condition: str = Field(
        description="A concrete, observable condition that would INVALIDATE this claim."
    )
    is_core: bool = Field(
        description="True if central to the thesis, false if a minor supporting point."
    )
