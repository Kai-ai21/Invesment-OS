from backend.domain.bm25 import rank_chunks, score_chunks, tokenize

# --- guards -----------------------------------------------------------------------


def test_no_chunks_returns_no_scores():
    # Arrange
    chunks: list[str] = []

    # Act
    scores = score_chunks("gross margins", chunks)

    # Assert
    assert scores == []


def test_empty_query_scores_every_chunk_zero():
    # Arrange
    chunks = ["gross margins decreased", "the company issued debt"]

    # Act
    scores = score_chunks("", chunks)

    # Assert
    assert scores == [0.0, 0.0]


def test_query_of_only_punctuation_scores_every_chunk_zero():
    # Arrange — tokenises to nothing, same as an empty query.
    chunks = ["gross margins decreased", "the company issued debt"]

    # Act
    scores = score_chunks("--- ... ///", chunks)

    # Assert
    assert scores == [0.0, 0.0]


# --- tokenisation -----------------------------------------------------------------


def test_percentages_survive_tokenisation_intact():
    # Arrange — the naive "split on every non-alphanumeric" behaviour would turn
    # "71.1%" into ["71", "1"], destroying the figure and injecting a junk token.
    text = "Gross margins decreased to 71.1% in fiscal year 2026"

    # Act
    tokens = tokenize(text)

    # Assert
    assert "71.1%" in tokens
    assert "71" not in tokens
    assert "1" not in tokens


def test_thousands_separated_figures_survive_tokenisation_intact():
    # Arrange
    text = "Total revenue was $ 215,938 million"

    # Act
    tokens = tokenize(text)

    # Assert — one figure, not two unrelated numbers.
    assert "215,938" in tokens
    assert "215" not in tokens
    assert "938" not in tokens


def test_percent_token_is_distinct_from_the_bare_number():
    # Arrange — a rate and a page number should not collide.
    rate_tokens = tokenize("margins at or above 72%")
    plain_tokens = tokenize("see page 72 for details")

    # Act / Assert
    assert "72%" in rate_tokens
    assert "72%" not in plain_tokens
    assert "72" in plain_tokens


def test_hyphenated_compounds_stay_whole():
    # WHY this reverses an earlier decision: the tokeniser used to split hyphenated
    # compounds into parts, so "non-GAAP" became ["non", "gaap"]. That made a query
    # about "non-GAAP gross margins" match "Non-marketable equity securities" on the
    # shared fragment "non" — and because "non" was rare in the corpus, IDF weighted
    # that meaningless prefix ABOVE "margins", letting boilerplate out-rank the
    # passage being searched for. Splitting was a theoretical benefit; the false
    # match was a measured one.

    # Arrange / Act
    tokens = tokenize("year-over-year non-GAAP Non-marketable")

    # Assert — compounds survive intact, so unrelated ones no longer collide.
    assert tokens == ["year-over-year", "non-gaap", "non-marketable"]
    assert "non" not in tokens


def test_unrelated_hyphenated_compounds_do_not_match_each_other():
    # Arrange — the exact pair that caused the false match.
    query_tokens = set(tokenize("non-GAAP gross margins"))
    boilerplate_tokens = set(tokenize("Non-marketable equity securities"))

    # Act
    shared = query_tokens & boilerplate_tokens

    # Assert
    assert shared == set()


def test_tokenisation_lowercases():
    # Arrange / Act
    tokens = tokenize("Gross Margins DECREASED")

    # Assert
    assert tokens == ["gross", "margins", "decreased"]


# --- ranking basics ---------------------------------------------------------------


def test_chunk_containing_the_query_term_outscores_one_that_does_not():
    # Arrange
    chunks = ["gross margins decreased this year", "the debt schedule was refinanced"]

    # Act
    scores = score_chunks("margins", chunks)

    # Assert
    assert scores[0] > 0
    assert scores[1] == 0


# --- idea 1: IDF ------------------------------------------------------------------


def test_term_present_in_every_chunk_contributes_almost_nothing():
    # Arrange — "company" is in all four chunks, so it cannot discriminate between
    # them; "margins" is in only one. Same chunk, same single occurrence, same
    # length: the only variable is how surprising the term is.
    chunks = [
        "the company reported results",
        "the company issued debt",
        "the company hired staff",
        "the company margins improved",
    ]

    # Act
    ubiquitous_term_score = score_chunks("company", chunks)[3]
    rare_term_score = score_chunks("margins", chunks)[3]

    # Assert
    assert ubiquitous_term_score < 0.5  # near-zero contribution
    assert rare_term_score > 5 * ubiquitous_term_score


def test_a_rare_term_drives_the_ranking():
    # Arrange — every chunk shares the common words; only one holds the rare term.
    chunks = [
        "the company reported quarterly results for the fiscal year",
        "the company reported quarterly guidance for the fiscal year",
        "the company reported quarterly margins for the fiscal year",
    ]

    # Act
    ranked = rank_chunks("the company quarterly margins", chunks, k=3)

    # Assert — the shared words cannot separate the chunks, so the rare one wins.
    assert ranked[0][0] == 2


# --- idea 2: saturating term frequency --------------------------------------------

def test_ten_occurrences_do_not_score_ten_times_one_occurrence():
    # Arrange — both chunks are exactly ten tokens long, so length normalisation is
    # identical and term frequency is the only difference.
    one_occurrence = "margin " + "filler " * 9
    ten_occurrences = "margin " * 10

    # Act
    scores = score_chunks("margin", [one_occurrence, ten_occurrences])
    single, repeated = scores[0], scores[1]

    # Assert — more is better, but far from ten times better.
    assert repeated > single
    assert repeated < 3 * single


# --- idea 3: length normalisation -------------------------------------------------


def test_short_chunk_with_one_hit_beats_a_long_chunk_with_one_hit():
    # Arrange — identical evidence (one mention of "margins"), very different volumes
    # of surrounding text.
    short_chunk = "gross margins improved"
    long_chunk = (
        "gross margins are discussed here among many unrelated regulatory, "
        "operational and administrative matters that this filing describes at "
        "considerable length without adding further detail on the subject "
    ) + ("additional boilerplate text about various other matters " * 8)

    # Act
    scores = score_chunks("margins", [short_chunk, long_chunk])

    # Assert
    assert scores[0] > scores[1]


# --- determinism ------------------------------------------------------------------


def test_identical_inputs_produce_identical_output():
    # Arrange
    chunks = ["gross margins decreased", "revenue grew", "margins improved"]

    # Act
    first = rank_chunks("margins", chunks, k=3)
    second = rank_chunks("margins", chunks, k=3)

    # Assert
    assert first == second


def test_ties_are_broken_by_lower_index():
    # Arrange — the first two chunks are identical, so they must score identically.
    chunks = ["gross margins decreased", "gross margins decreased", "unrelated text"]

    # Act
    ranked = rank_chunks("margins", chunks, k=3)

    # Assert
    assert ranked[0][1] == ranked[1][1]  # genuinely tied
    assert [index for index, _ in ranked[:2]] == [0, 1]  # lower index first


def test_rank_returns_at_most_k_and_is_ordered_best_first():
    # Arrange
    chunks = ["margins fell", "margins margins fell", "unrelated", "also unrelated"]

    # Act
    ranked = rank_chunks("margins", chunks, k=2)

    # Assert
    assert len(ranked) == 2
    assert ranked[0][1] >= ranked[1][1]


def test_non_positive_k_returns_nothing():
    # Arrange
    chunks = ["gross margins decreased"]

    # Act / Assert
    assert rank_chunks("margins", chunks, k=0) == []
    assert rank_chunks("margins", chunks, k=-1) == []


# --- the real case ----------------------------------------------------------------

# The failure that motivated this phase: against a real NVDA 10-K, embedding
# similarity ranked this passage #14 of ~880 chunks for the gross-margin claim,
# behind generic financial prose. BM25 should put it first, because "margins" is
# rare and decisive whereas "financial", "fiscal" and "results" are everywhere.
MARGIN_PASSAGE = (
    "Gross margins decreased to 71.1% in fiscal year 2026 from 75.0% in fiscal "
    "year 2025 as our business model transitioned from offering Hopper HGX systems "
    "to Blackwell full-scale datacenter solutions."
)

# Realistic 10-K filler. Note the last two deliberately compete: the fair-value note
# shares the word "gross", and the risk factor contains "gross margins" outright —
# but as a long hedging passage rather than a reported figure.
RISK_FACTOR = (
    "These risks have increased and may continue to increase as our purchase "
    "obligations and prepaids have grown and are expected to continue to grow and "
    "become a greater portion of our total supply. All of these factors may "
    "negatively impact our gross margins and financial results. We may be unable to "
    "secure sufficient capacity on acceptable terms, and any failure to do so could "
    "adversely affect our business, operating results and financial condition in "
    "ways that we are not able to predict at this time."
)
FAIR_VALUE_NOTE = (
    "Level 3: Unobservable inputs in which little or no market data exists. "
    "Non-marketable equity securities had cumulative gross unrealized gains of "
    "$ 2.7 billion and $ 1.1 billion as of the end of the periods presented."
)
DEBT_SCHEDULE = (
    "Note 11 - Debt Expected Remaining Term Effective Interest Rate aggregate "
    "principal amount of notes outstanding with maturities in 2028, 2030 and 2040."
)
STOCK_PERFORMANCE_GRAPH = (
    "Total return is based on historical results and is not intended to indicate "
    "future performance. $ 100 invested on 1/31/2021 in stock and in indices, "
    "including reinvestment of dividends."
)

# The corpus has to be big enough, and shaped enough like a real filing, for IDF to
# behave the way it does in production. BM25 relies on the corpus itself to reveal
# which words are uninformative, so a handful of chunks is not merely a smaller test —
# it is a MISLEADING one. Two artifacts were measured against the real NVDA 10-K
# (882 chunks) while building this fixture:
#
#   1. With five chunks, "the" occurred in only one and so scored idf 1.386 — HIGHER
#      than "margins". In the real filing "the" is in 731/882 chunks and scores 0.188.
#      Function words were deciding the ranking purely because the corpus was tiny.
#
#   2. Filler that happens to echo the query's own vocabulary is just as distorting.
#      An early version of these chunks said "over the next several periods"; "next"
#      then appeared in exactly one chunk and scored the highest idf of any term,
#      handing the win to boilerplate. In the real filing "next" is rare too
#      (8/882) — but it is rare EVERYWHERE, so it does not single out one chunk.
#
# So the filler below is ordinary filing prose carrying the genuinely common words
# ("the", "or", "at"), and deliberately avoids the query's distinctive vocabulary
# (quarterly, next, four, quarters, over, above, gross, margins). A guard test below
# asserts that separation, so a future edit cannot silently reintroduce the artifact.
FILLER_BOILERPLATE = [
    "The company operates in a highly competitive industry that is subject to rapid "
    "technological change, and that pace may increase as new entrants entrenched.",
    "We depend on a limited number of third-party foundries, and any disruption at "
    "one of them could delay the shipment of products to our customers.",
    "The board of directors has established an audit committee, a compensation "
    "committee, and a nominating and corporate governance committee.",
    "Our future success depends on the ability to attract and retain qualified "
    "engineers, and competition for that talent is intense at every level.",
    "The company is subject to export control laws that restrict the sale of certain "
    "products to specified countries or end users named by the regulator.",
    "A significant portion of the revenue is denominated in currencies other than "
    "the dollar, and movements in exchange rates may affect the reported results.",
    "The information systems that we operate face cybersecurity threats that are "
    "increasing in frequency, and a breach could disrupt the business at any time.",
    "We lease most of the facilities that we occupy, and we may be unable to renew "
    "the leases on favorable terms or to secure additional space when it is needed.",
    "Changes in the tax law, or in the interpretation of the existing law, could "
    "increase the effective tax rate that we report in future filings.",
    "The results have fluctuated in the past and may continue to fluctuate for "
    "reasons that are largely outside of the control of the company or its board.",
]

# The query's distinctive vocabulary. Filler must not contain these, or the fixture
# stops modelling the real corpus (see artifact 2 above).
_QUERY_SPECIFIC_TERMS = {
    "quarterly",
    "next",
    "four",
    "quarters",
    "over",
    "above",
    "gross",
    "margins",
    "nvidia",
    "maintains",
}


def test_gross_margin_passage_outranks_10k_boilerplate():
    # Arrange — the production query for the gross-margin claim's proof condition,
    # against a corpus large enough that IDF suppresses common words as it does in
    # the real filing.
    query = (
        "Nvidia maintains quarterly non-GAAP gross margins at or above 72% "
        "over the next four quarters"
    )
    chunks = [
        STOCK_PERFORMANCE_GRAPH,
        RISK_FACTOR,
        DEBT_SCHEDULE,
        MARGIN_PASSAGE,
        FAIR_VALUE_NOTE,
        *FILLER_BOILERPLATE,
    ]

    # Act
    ranked = rank_chunks(query, chunks, k=len(chunks))

    # Assert — the reported figure ranks first, ahead of the long risk-factor
    # passage that mentions the same words in passing.
    assert ranked[0][0] == chunks.index(MARGIN_PASSAGE)


def test_filler_does_not_echo_the_querys_distinctive_vocabulary():
    # Guard for the fixture itself. If filler picks up a rare query term, that term
    # becomes uniquely discriminating inside this small corpus and decides the
    # ranking — which is how an earlier version of this fixture silently broke.
    # Failing here names the cause directly instead of surfacing as a ranking flip.
    for chunk in FILLER_BOILERPLATE:
        leaked = _QUERY_SPECIFIC_TERMS & set(tokenize(chunk))
        assert leaked == set(), f"filler leaked query vocabulary {leaked}: {chunk!r}"


def test_function_words_do_not_decide_the_ranking_in_a_realistic_corpus():
    # Arrange — this is the property the fixture size exists to guarantee, asserted
    # directly so a future shrink of the corpus fails here with a clear reason rather
    # than as a confusing ranking flip.
    chunks = [
        STOCK_PERFORMANCE_GRAPH,
        RISK_FACTOR,
        DEBT_SCHEDULE,
        MARGIN_PASSAGE,
        FAIR_VALUE_NOTE,
        *FILLER_BOILERPLATE,
    ]

    # Act — score the margin passage on a query of pure function words vs. on the
    # single decisive domain term.
    function_word_score = score_chunks("the or at over next", chunks)[3]
    domain_term_score = score_chunks("margins", chunks)[3]

    # Assert
    assert domain_term_score > function_word_score
