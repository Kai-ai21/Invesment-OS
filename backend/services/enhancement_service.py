"""Sharpening an investor's own reasoning before it becomes a thesis.

⚠️ THIS IS AN EDIT, NOT A REWRITE, AND IT IS ALWAYS OPTIONAL. Creating a thesis
never touches this service — the form works exactly the same if the button is
never pressed. The user's original text is never replaced here either: this
returns a candidate, and the frontend makes them choose between it and what they
wrote.

WHY `unchanged` IS COMPUTED HERE. The model is told to return the input verbatim
when it cannot sharpen without inventing, and the UI has to say "already specific
enough" rather than pretending. Detecting that by string equality in the frontend
would be brittle — a model that re-flows whitespace or trims a trailing newline
would look like it had done something. Comparing on normalised whitespace is a
backend job, done once, in the place that knows what was sent.
"""

import re

from pydantic import BaseModel

from backend.adapters.llm_factory import create_llm_provider
from backend.ports.llm_provider import LLMProvider

# Below this there is nothing to sharpen — "amazon good" is a preference, not
# reasoning, and asking the model to improve it invites it to invent a thesis.
MIN_REASONING_LENGTH = 15

_WHITESPACE = re.compile(r"\s+")


class EnhancementError(Exception):
    """The input is not something that can be sharpened. The caller sends a 422."""


class EnhancementResult(BaseModel):
    enhanced: str
    # True when the model handed back what it was given — see the module docstring.
    unchanged: bool


def _normalised(text: str) -> str:
    """Whitespace-insensitive form, for deciding whether anything really changed."""
    return _WHITESPACE.sub(" ", text).strip().lower()


def enhance_reasoning(
    ticker: str, reasoning: str, provider: LLMProvider | None = None
) -> EnhancementResult:
    """A sharper version of `reasoning`, or the same text back.

    `provider` is injectable so tests can exercise this without an AI call.
    """
    trimmed = reasoning.strip()
    if len(trimmed) < MIN_REASONING_LENGTH:
        raise EnhancementError(
            f"Reasoning needs at least {MIN_REASONING_LENGTH} characters to sharpen."
        )
    if not ticker.strip():
        raise EnhancementError("A ticker is required.")

    provider = provider if provider is not None else create_llm_provider()
    enhanced = provider.enhance_reasoning(ticker.strip().upper(), trimmed).strip()

    # An empty or whitespace-only response is a failed rewrite, not an enhancement.
    # Falling back to the original guarantees this can never hand back less than
    # the user already had.
    if not enhanced:
        return EnhancementResult(enhanced=trimmed, unchanged=True)

    return EnhancementResult(
        enhanced=enhanced,
        unchanged=_normalised(enhanced) == _normalised(trimmed),
    )
