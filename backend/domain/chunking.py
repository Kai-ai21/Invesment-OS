"""Sentence-aware text chunking for the evidence pipeline. Pure, no I/O.

WHY sentence-awareness matters here: downstream, the citation check verifies that
each piece of evidence quotes its source *verbatim* — the quoted span has to be
found character-for-character inside a chunk. If a chunk boundary fell in the
middle of a sentence, a quote straddling that boundary would exist in the source
yet live in no single chunk, so the citation check could never confirm it. We
therefore prefer to cut on sentence boundaries (. ! ?).

For the same reason we never normalise: chunks are exact substrings of the input
(no lowercasing, no whitespace collapsing), so verbatim quotes survive intact.
Normalisation happens later, and only inside the citation check itself.
"""

import bisect
import re

# A sentence terminator ('.', '!', '?', possibly repeated), any closing quote or
# bracket that rides along with it, then the whitespace separating it from the
# next sentence. The END of such a match is a clean place to cut.
_SENTENCE_BOUNDARY = re.compile(r"[.!?]+[\"')\]]*\s+")


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """Contiguous (start, end) spans, one per sentence, covering the whole text.

    Gap-free by construction — each span runs from the end of the previous
    sentence (including its trailing whitespace) to the end of this one — so
    ``"".join(text[s:e] for s, e in spans) == text``.
    """
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        spans.append((start, match.end()))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def chunk_text(text: str, target_size: int = 800, overlap: int = 150) -> list[str]:
    """Split ``text`` into overlapping, roughly ``target_size``-character chunks.

    Cuts land on sentence boundaries where possible. A single sentence longer than
    ``target_size`` — or text with no sentence punctuation at all — is hard-split
    on size, so we never emit one enormous chunk. Consecutive chunks share about
    ``overlap`` characters (whole sentences where possible) so a passage near a
    boundary still appears intact in at least one chunk.

    Chunks are exact substrings of ``text``; nothing is normalised.
    """
    # Empty or whitespace-only: nothing to chunk.
    if not text.strip():
        return []
    # Whole thing already fits: one chunk, returned verbatim.
    if len(text) <= target_size:
        return [text]

    overlap = max(0, overlap)  # a negative overlap would skip text and lose content

    # Positions a chunk may start or end on without splitting a sentence: index 0,
    # plus the end of every sentence (the last of which is len(text)).
    cuts = [0] + [end for _, end in _sentence_spans(text)]

    n = len(text)
    chunks: list[str] = []
    pos = 0
    while pos < n:
        hard_end = pos + target_size
        if hard_end >= n:
            chunks.append(text[pos:n])
            break

        # Largest sentence boundary at or before the size limit, but past `pos`.
        boundary = cuts[bisect.bisect_right(cuts, hard_end) - 1]
        if boundary <= pos:
            # No sentence boundary within reach (long sentence / no punctuation):
            # hard-split on size rather than overshoot.
            boundary = hard_end
        chunks.append(text[pos:boundary])

        # Start the next chunk ~overlap characters back, snapped to a sentence
        # boundary when one is available, and always strictly after `pos`.
        target_next = boundary - overlap
        if target_next <= pos:
            next_pos = boundary  # sentence shorter than the overlap window: no overlap
        else:
            snapped = cuts[bisect.bisect_right(cuts, target_next) - 1]
            next_pos = snapped if snapped > pos else target_next
        pos = next_pos

    return chunks
