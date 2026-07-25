import re

from backend.domain.chunking import chunk_text

# A block of short, clean sentences — long enough to force several chunks at the
# small sizes these tests use. Every sentence ends in '.' and sits well under the
# target size, so nothing here should ever be hard-split.
PROSE = (
    "Data center revenue rose again this quarter. "
    "Gross margin held above seventy percent. "
    "Management reaffirmed full year guidance. "
    "Networking demand stayed unusually strong. "
    "The backlog grew faster than shipments. "
    "Competitors have not closed the gap. "
    "Supply constraints are finally easing. "
    "Pricing power remained broadly intact. "
    "Free cash flow beat the consensus estimate. "
    "The buyback pace accelerated slightly. "
    "Inventory levels still look healthy going forward. "
    "No customer concentration risk emerged this period."
)


def _longest_shared_seam(a: str, b: str) -> str:
    """The longest suffix of `a` that is also a prefix of `b` — their overlap."""
    for size in range(min(len(a), len(b)), 0, -1):
        if a[-size:] == b[:size]:
            return a[-size:]
    return ""


def _split_sentences(text: str) -> list[str]:
    """Naive sentence split for the reassembly property — independent of the
    module under test, so the test doesn't just mirror the implementation."""
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


# --- edge cases -------------------------------------------------------------------


def test_empty_string_returns_no_chunks():
    # Arrange
    text = ""

    # Act
    chunks = chunk_text(text)

    # Assert
    assert chunks == []


def test_whitespace_only_text_returns_no_chunks():
    # Arrange
    text = "   \n\t  "

    # Act
    chunks = chunk_text(text)

    # Assert
    assert chunks == []


def test_text_shorter_than_target_returns_single_chunk_equal_to_input():
    # Arrange
    text = "Margins held above seventy percent this quarter."

    # Act
    chunks = chunk_text(text, target_size=800)

    # Assert
    assert chunks == [text]


# --- normal chunking --------------------------------------------------------------


def test_long_multi_sentence_text_returns_multiple_chunks():
    # Arrange
    text = PROSE

    # Act
    chunks = chunk_text(text, target_size=150, overlap=50)

    # Assert
    assert len(chunks) > 1


def test_chunks_are_not_split_mid_sentence_in_the_normal_case():
    # Arrange — every sentence is shorter than the target, so no hard-split.
    text = PROSE

    # Act
    chunks = chunk_text(text, target_size=150, overlap=50)

    # Assert — each chunk ends on sentence-terminating punctuation.
    for chunk in chunks:
        assert chunk.rstrip().endswith((".", "!", "?"))


def test_no_chunk_wildly_exceeds_the_target_size():
    # Arrange
    text = PROSE

    # Act
    chunks = chunk_text(text, target_size=150, overlap=50)

    # Assert — sentence-aware cutting keeps every chunk within the target.
    assert all(len(chunk) <= 150 for chunk in chunks)


def test_consecutive_chunks_overlap():
    # Arrange
    text = PROSE

    # Act
    chunks = chunk_text(text, target_size=150, overlap=50)

    # Assert — each neighbouring pair shares a run of text.
    for earlier, later in zip(chunks, chunks[1:]):
        assert _longest_shared_seam(earlier, later) != ""


def test_chunks_are_verbatim_substrings_of_the_input():
    # Arrange — capitalised prose; an exact-substring check proves no lowercasing,
    # whitespace collapsing, or other normalisation happened.
    text = PROSE

    # Act
    chunks = chunk_text(text, target_size=150, overlap=50)

    # Assert
    assert all(chunk in text for chunk in chunks)


# --- hard-split fallbacks ---------------------------------------------------------


def test_single_sentence_longer_than_target_is_hard_split_not_returned_oversized():
    # Arrange — one sentence (no internal punctuation) far longer than the target.
    text = ("lorem ipsum dolor sit amet " * 40).strip() + "."

    # Act
    chunks = chunk_text(text, target_size=200, overlap=50)

    # Assert — it was broken up, and no chunk came back oversized.
    assert len(chunks) > 1
    assert all(len(chunk) <= 200 for chunk in chunks)


def test_text_with_no_sentence_punctuation_is_still_chunked():
    # Arrange
    text = "word " * 100  # 500 chars, no '.', '!' or '?'

    # Act
    chunks = chunk_text(text, target_size=120, overlap=30)

    # Assert
    assert len(chunks) >= 2
    assert all(len(chunk) <= 120 for chunk in chunks)
    assert all(chunk in text for chunk in chunks)


# --- the property the citation check depends on -----------------------------------


def test_every_original_sentence_appears_intact_in_at_least_one_chunk():
    # Arrange
    text = PROSE
    sentences = _split_sentences(text)

    # Act
    chunks = chunk_text(text, target_size=150, overlap=50)

    # Assert — this is exactly what verbatim citation lookup relies on.
    for sentence in sentences:
        assert any(sentence in chunk for chunk in chunks), sentence
