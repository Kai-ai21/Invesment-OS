from typing import Literal

from pydantic import BaseModel, Field

# The two labels, and there is deliberately no third.
#
# ⚠️ "UNSURE" IS NOT AN OPTION, BECAUSE IT WOULD BECOME THE ANSWER. A middle value is
# where a model puts everything it has not thought hard about, and a flag that fires on
# half the claims tells the investor nothing. Uncertainty has a home here — it is
# CHECKABLE. That makes the label a claim about the WORLD ("no filing carries this
# number") rather than about the model's confidence, which is the only version of it
# worth surfacing.
CHECKABLE = "checkable"
UNVERIFIABLE = "unverifiable"


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

    # ⚠️ THIS FLAGS, IT NEVER REJECTS. An unverifiable claim is still extracted, still
    # saved, and still the investor's. Someone who believes market share is the thing
    # that matters is entitled to keep tracking it by hand; what they are NOT entitled
    # to is a claim that silently never updates because nothing could ever check it.
    # The label is the difference between "no evidence yet" and "no evidence ever", and
    # only the investor can decide what to do about the second one.
    #
    # ⚠️ THE DEFAULT IS CHECKABLE, AND THAT IS THE SAFE DIRECTION. A wrongly-checkable
    # claim costs a retrieval that finds nothing — the status quo for every claim
    # before this field existed. A wrongly-UNVERIFIABLE claim tells the investor to
    # stop expecting evidence for something the next 10-Q would in fact have answered,
    # which is worse and invisible. So the flag has to earn itself; absence of it
    # asserts nothing.
    #
    # It covers the claim's two CONDITIONS, not its statement — a statement is prose
    # and was never the thing being checked. When the two conditions disagree, the
    # claim is checkable: half of it can still be monitored, and that is not nothing.
    verifiability: Literal["checkable", "unverifiable"] = Field(
        default=CHECKABLE,
        description=(
            "'unverifiable' ONLY when confident no SEC filing or standard financial "
            "data could ever check either condition — market share, competitor "
            "comparisons, unreported segment detail, forward guidance, private "
            "company data. Everything else, including anything uncertain, is "
            "'checkable'."
        ),
    )

    # Empty string when checkable, mirroring VerdictData.evidence_quote — the same
    # convention for "this field does not apply here", so a reader who knows one knows
    # the other. It is prose for a human, not a machine-readable reason code: the
    # useful content is WHICH data is missing, and that does not enumerate.
    verifiability_note: str = Field(
        default="",
        description=(
            "One sentence naming the data that does not exist, when verifiability is "
            "'unverifiable'. Empty string otherwise."
        ),
    )
