"""BM25 keyword scoring for the evidence pipeline. Pure, no I/O, stdlib only.

WHY this exists: embedding similarity alone kept missing the decisive passage. In a
real NVDA 10-K the sentence "Gross margins decreased to 71.1%..." ranked #14 of ~880
chunks for a gross-margin claim, out-ranked by generic financial prose that merely
*reads* like a filing. Embeddings capture topic, not terminology — every page of a
10-K is "about finance". BM25 scores exact term overlap instead, so a rare, decisive
word like "margins" outweighs a page of boilerplate. The two are complementary, which
is the point of combining them.

HOW BM25 WORKS — three ideas, each fixing a flaw in naive word counting:

  1. IDF (inverse document frequency) — how surprising is this term?
     A word in every chunk ("the", "company") tells you nothing about which chunk to
     pick, so it earns ~0. A word in one chunk ("margins") is highly discriminating
     and earns a lot. This is why no stopword list is needed: IDF suppresses common
     words automatically, and does so per-corpus rather than from a fixed list.

  2. SATURATING TERM FREQUENCY — the tenth mention adds less than the second.
     Naive counting says a chunk saying "margin" 10 times is 10x as relevant as one
     saying it once. It isn't; it is maybe twice as relevant. The f/(f + k1*...)
     shape rises steeply at first and then flattens, so keyword stuffing cannot
     dominate. K1 controls how quickly it flattens.

  3. LENGTH NORMALISATION — a hit in a short chunk means more.
     A long chunk contains more words, so it matches more terms by luck alone.
     Dividing by length relative to the average corrects this. B controls how
     aggressively: 0 disables it, 1 applies it fully.

The scoring formula, per query term q against chunk D:

    idf(q) * ( f(q,D) * (K1 + 1) ) / ( f(q,D) + K1 * (1 - B + B * |D| / avgdl) )

summed over the query's terms.
"""

import math
import re
from collections import Counter

# Conventional BM25 defaults, and what the literature uses unless tuned per-corpus.
K1 = 1.5  # term-frequency saturation: higher = slower to flatten
B = 0.75  # length normalisation strength: 0 = off, 1 = full

# TOKENISATION — the one place this is domain-specific.
#
# Financial claims turn on figures, so a naive split on every non-alphanumeric
# character is actively harmful: "71.1%" becomes ["71", "1"], which not only destroys
# the figure but injects the meaningless high-frequency token "1". "215,938" would
# likewise shatter into ["215", "938"].
#
# So numbers are matched as whole tokens, keeping internal decimal points and
# thousands separators, plus a trailing percent sign:
#     "71.1%"    -> "71.1%"       (intact, and distinct from a bare "71")
#     "215,938"  -> "215,938"     (not two unrelated numbers)
#     "$4.5"     -> "4.5"         ('$' dropped: "$4.5" and "4.5 billion" should match)
#
# Keeping '%' attached is a deliberate precision/recall trade: "72%" (a rate) no
# longer collides with a bare "72" (a page number, a year fragment), at the cost of
# not matching the spelled-out "72 percent". In filings the symbol form dominates.
#
# Hyphenated alphabetic compounds stay WHOLE:
#     "non-GAAP"       -> "non-gaap"
#     "Non-marketable" -> "non-marketable"
#     "year-over-year" -> "year-over-year"
#
# An earlier version split these into parts ("non-GAAP" -> ["non", "gaap"]), which
# was measurably wrong: "non-GAAP" in a query then matched "Non-marketable" in a
# fair-value note via the shared fragment "non". Worse, that fragment was rare in the
# corpus, so IDF handed the meaningless prefix a HIGHER weight than "margins" — the
# boilerplate out-ranked the passage we were looking for on a match that means
# nothing.
#
# The trade: a hyphenated compound no longer matches its spaced spelling, so a query
# saying "year-over-year" misses a chunk saying "year over year". That is a
# speculative loss — filings overwhelmingly use the hyphenated form — traded against
# a measured, reproducible false match. Evidence beats theory.
#
# No stemming and no stopword list: stemming would conflate distinct financial terms,
# and IDF already handles common words (idea 1 above).
_TOKEN_PATTERN = re.compile(r"\d+(?:[.,]\d+)*%?|[a-z]+(?:-[a-z]+)*")


def tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


def _idf(matching_chunks: int, total_chunks: int) -> float:
    """Inverse document frequency, in the standard BM25+1 form.

    The trailing "+ 1" inside the log keeps this non-negative. Without it a term
    appearing in more than half the chunks scores NEGATIVE, so a common word would
    actively push a chunk down the ranking rather than merely failing to lift it.
    """
    return math.log(
        (total_chunks - matching_chunks + 0.5) / (matching_chunks + 0.5) + 1
    )


def score_chunks(query: str, chunks: list[str]) -> list[float]:
    """One BM25 score per chunk, in the same order as the input."""
    if not chunks:
        return []

    query_terms = tokenize(query)
    if not query_terms:
        return [0.0] * len(chunks)

    tokenized = [tokenize(chunk) for chunk in chunks]
    lengths = [len(tokens) for tokens in tokenized]
    total_length = sum(lengths)
    if not total_length:
        # Every chunk tokenised to nothing — no signal, and avgdl would be zero.
        return [0.0] * len(chunks)

    average_length = total_length / len(chunks)
    frequencies = [Counter(tokens) for tokens in tokenized]

    # Precompute IDF once per distinct term rather than per (term, chunk) pair.
    idf_by_term: dict[str, float] = {}
    for term in set(query_terms):
        matching = sum(1 for counts in frequencies if term in counts)
        idf_by_term[term] = _idf(matching, len(chunks))

    scores = [0.0] * len(chunks)
    for index, counts in enumerate(frequencies):
        # Length penalty is per-chunk, so it is computed once here rather than per term.
        length_penalty = K1 * (1 - B + B * lengths[index] / average_length)

        total = 0.0
        # Iterating the query terms as given (duplicates included) is the canonical
        # summation: a term repeated in the query legitimately weighs more.
        for term in query_terms:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            total += (
                idf_by_term[term] * frequency * (K1 + 1) / (frequency + length_penalty)
            )
        scores[index] = total

    return scores


def rank_chunks(query: str, chunks: list[str], k: int) -> list[tuple[int, float]]:
    """The top `k` chunks as (chunk_index, score) pairs, best first.

    Ties break by LOWER index so the output is fully deterministic — two chunks with
    identical scores must not swap places between runs.
    """
    if k <= 0:
        return []

    scores = score_chunks(query, chunks)
    ordered = sorted(enumerate(scores), key=lambda pair: (-pair[1], pair[0]))
    return ordered[:k]
