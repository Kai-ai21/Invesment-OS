"""Which LLM adapter the app runs on, decided by one environment variable.

⚠️ THE POINT OF THIS MODULE IS THAT SWITCHING BACK IS ONE VARIABLE. Groq's
structured output is enforced by constrained decoding and should hold, but
"should" is why the Gemini adapter is still here and still tested. If Groq
disappoints in real use, `LLM_PROVIDER=gemini` restores the previous behaviour
without a deploy of new code.
"""

import os

from backend.ports.llm_provider import LLMProvider

DEFAULT_PROVIDER = "gemini"

SUPPORTED = ("gemini", "groq")


def create_llm_provider(name: str | None = None) -> LLMProvider:
    """Build the configured provider. `name` overrides the environment, for tests.

    ⚠️ AN UNRECOGNISED NAME RAISES rather than falling back to the default. A
    typo — `grok`, `GROQ `, `openai` — would otherwise start the app cleanly on
    a provider the operator did not choose, and the only symptom would be a bill
    on the wrong account. Failing here means a misconfiguration is discovered at
    startup, which is the same stance core/security.py takes on JWT_SECRET.

    The SDK imports are deliberately INSIDE the branches: an install that only
    ever runs Groq should not need google-genai present, and vice versa.
    """
    raw = name if name is not None else os.getenv("LLM_PROVIDER") or DEFAULT_PROVIDER
    choice = raw.strip().lower()

    if choice == "gemini":
        from backend.adapters.gemini_provider import GeminiProvider

        return GeminiProvider()

    if choice == "groq":
        from backend.adapters.groq_provider import GroqProvider

        return GroqProvider()

    raise ValueError(
        f"LLM_PROVIDER={raw!r} is not a provider this app has an adapter for. "
        f"Supported: {', '.join(SUPPORTED)}."
    )
