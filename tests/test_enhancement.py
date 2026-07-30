import pytest

from backend.services.enhancement_service import (
    MIN_REASONING_LENGTH,
    EnhancementError,
    enhance_reasoning,
)

ORIGINAL = "amazon has good margins and i think aws keeps growing"


class FakeProvider:
    """Returns a canned rewrite and records what it was asked."""

    def __init__(self, returns=None, raises=None):
        self._returns = returns
        self._raises = raises
        self.calls: list[tuple[str, str]] = []

    def enhance_reasoning(self, ticker, raw_reasoning):
        self.calls.append((ticker, raw_reasoning))
        if self._raises:
            raise self._raises
        # Default: echo the input, the "cannot sharpen" answer.
        return self._returns if self._returns is not None else raw_reasoning


# --- the guard ----------------------------------------------------------------------


@pytest.mark.parametrize("reasoning", ["", "   ", "amazon good", "a" * (MIN_REASONING_LENGTH - 1)])
def test_input_too_thin_to_sharpen_is_rejected(reasoning):
    # Arrange — below this there is nothing to tighten, and asking the model to
    # improve it is an invitation to invent a thesis. The endpoint sends a 422.
    provider = FakeProvider()

    # Act / Assert
    with pytest.raises(EnhancementError):
        enhance_reasoning("AMZN", reasoning, provider=provider)

    # The model is never even called — nothing to send.
    assert provider.calls == []


def test_a_missing_ticker_is_rejected():
    with pytest.raises(EnhancementError):
        enhance_reasoning("  ", ORIGINAL, provider=FakeProvider())


# --- the rewrite --------------------------------------------------------------------


def test_a_real_rewrite_is_returned_and_flagged_as_changed():
    # Arrange
    sharper = "I think Amazon's margins stay high and I expect AWS to keep growing."
    provider = FakeProvider(returns=sharper)

    # Act
    result = enhance_reasoning("amzn", ORIGINAL, provider=provider)

    # Assert
    assert result.enhanced == sharper
    assert result.unchanged is False


def test_the_ticker_is_normalised_before_the_model_sees_it():
    provider = FakeProvider(returns="something sharper entirely")
    enhance_reasoning("  amzn  ", ORIGINAL, provider=provider)
    assert provider.calls[0][0] == "AMZN"


def test_the_original_is_passed_trimmed_not_padded():
    provider = FakeProvider(returns="sharper")
    enhance_reasoning("AMZN", f"   {ORIGINAL}   ", provider=provider)
    assert provider.calls[0][1] == ORIGINAL


# --- "could not sharpen" is a real answer -------------------------------------------


def test_an_echoed_input_is_reported_as_unchanged():
    # Arrange — the model is told to return the input verbatim when it cannot
    # sharpen without inventing. The UI says "already specific enough".
    result = enhance_reasoning("AMZN", ORIGINAL, provider=FakeProvider(returns=ORIGINAL))

    # Assert
    assert result.enhanced == ORIGINAL
    assert result.unchanged is True


def test_whitespace_only_differences_still_count_as_unchanged():
    # Arrange — THE reason `unchanged` is computed here rather than by string
    # equality in the frontend: a model that re-flows a line break has not
    # sharpened anything, and must not look like it has.
    reflowed = ORIGINAL.replace(" ", "  ") + "\n"

    # Act
    result = enhance_reasoning("AMZN", ORIGINAL, provider=FakeProvider(returns=reflowed))

    # Assert
    assert result.unchanged is True


def test_case_only_differences_count_as_unchanged():
    result = enhance_reasoning(
        "AMZN", ORIGINAL, provider=FakeProvider(returns=ORIGINAL.upper())
    )
    assert result.unchanged is True


def test_an_empty_response_falls_back_to_the_original():
    # Arrange — a blank rewrite is a failed one. This must never hand back less
    # than the user already had.
    result = enhance_reasoning("AMZN", ORIGINAL, provider=FakeProvider(returns="   "))

    # Assert
    assert result.enhanced == ORIGINAL
    assert result.unchanged is True


def test_a_provider_failure_propagates():
    # Arrange — the route surfaces this inline; the form still submits without it.
    provider = FakeProvider(raises=RuntimeError("gemini 503"))

    # Act / Assert
    with pytest.raises(RuntimeError):
        enhance_reasoning("AMZN", ORIGINAL, provider=provider)
