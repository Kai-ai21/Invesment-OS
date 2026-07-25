import pytest

# These are real retrieval-quality tests: they load a local embedding model and a
# Chroma store. Skip cleanly until the heavy deps are installed rather than hard-
# failing the rest of the suite.
pytest.importorskip("chromadb")
pytest.importorskip("sentence_transformers")

from backend.adapters.rag_retriever import RagRetriever  # noqa: E402
from backend.domain.chunking import chunk_text  # noqa: E402

# Two "needles" — a gross-margin figure and a revenue-growth figure — buried in a
# long stretch of generic filing boilerplate. They are distinct sentences so the
# chunker keeps each one whole, and they sit far apart so they land in different
# chunks.
MARGIN_NEEDLE = (
    "Gross margin for the fiscal quarter expanded to 74.2 percent, "
    "up from 71.8 percent in the prior-year period."
)
REVENUE_NEEDLE = (
    "Data center segment revenue grew 55 percent year over year to a record "
    "30.8 billion dollars in the quarter."
)

# Varied risk-factor / MD&A boilerplate across many distinct topics. It has to be
# long enough to produce well more than `k` chunks (see the guard test), and it
# deliberately avoids the needles' topics — gross margin, data-center revenue
# growth, and dividends — so those stay distinctive rather than blending in.
_BOILERPLATE = [
    # Competition
    "The company operates in a highly competitive industry characterized by rapid technological change and evolving customer requirements.",
    "We face intense competition from established firms as well as new entrants and in-house silicon efforts by several large customers.",
    "Some of our competitors have substantially greater financial, engineering, and marketing resources than we do.",
    "Consolidation among our competitors or customers could reshape the competitive landscape to our disadvantage.",
    "The market can shift rapidly as customers adopt alternative architectures, interfaces, or programming models.",
    # Supply chain / manufacturing
    "We rely on a limited number of third-party foundries and subcontractors to manufacture, assemble, and test our products.",
    "Constraints in component supply and manufacturing capacity have in the past limited our ability to meet demand.",
    "We generally place non-cancelable inventory and capacity orders well in advance of anticipated customer demand.",
    "Longer manufacturing lead times increase the risk that our purchase commitments will exceed actual demand in a period.",
    "We depend on a small number of suppliers for critical materials, and the loss of any of them could interrupt production.",
    "Disruptions to global logistics and freight capacity can delay shipments and raise our distribution costs.",
    "We may face difficulty obtaining sufficient wafer capacity during periods of industry-wide shortage.",
    # Intellectual property / litigation
    "Third parties have asserted, and may in the future assert, intellectual property claims against us that are costly to defend.",
    "We are involved from time to time in legal proceedings and claims arising in the ordinary course of business.",
    "An unfavorable outcome in pending or future litigation could result in substantial damages or injunctions against product sales.",
    "Protecting our proprietary technology through patents and trade secrets is expensive and may not be fully effective.",
    "Our reliance on open-source software carries license-compliance and security obligations that we must actively manage.",
    # Governance
    "Our board of directors has established audit, compensation, and nominating and corporate governance committees.",
    "Certain provisions of our charter documents may delay or prevent a change in control of the company.",
    "The board periodically reviews the company's enterprise risk management framework and internal control environment.",
    "Government investigations or audits, even those without merit, can be costly and divert management attention.",
    # Human capital
    "Our future success depends on our ability to attract, retain, and motivate qualified engineers and other key personnel.",
    "Competition for skilled technical talent in the regions where we operate is intense and may increase our compensation costs.",
    "The loss of one or more members of our senior management team could disrupt our operations and strategic direction.",
    "Equity-based compensation is a significant part of our pay, and stock-price declines may impair our ability to retain employees.",
    # Currency / tax / accounting
    "A significant portion of our revenue and expenses is denominated in currencies other than the U.S. dollar.",
    "Fluctuations in foreign currency exchange rates may adversely affect our reported results.",
    "We may use derivative instruments to hedge a portion of our currency exposure, though such hedges may not be effective.",
    "Changes in tax laws or in the interpretation of existing tax laws could increase our effective tax rate.",
    "Changes in accounting standards could materially affect how we recognize revenue and report our financial position.",
    # Cybersecurity / IT / privacy
    "Our information systems and those of our vendors face cybersecurity threats that are increasing in frequency and sophistication.",
    "A significant breach of our systems could disrupt operations, compromise confidential data, and harm our reputation.",
    "We maintain business continuity and disaster recovery plans, but these may not prevent all interruptions to our operations.",
    "We are subject to a growing body of data-privacy laws that govern how we collect, use, and store personal information.",
    # Regulatory / trade / environmental
    "We are subject to export-control and sanctions laws that restrict sales of certain products to specified countries and end users.",
    "New or expanded trade restrictions could limit our addressable market and increase our compliance costs.",
    "Environmental regulations govern the materials, energy, and water used in our operations and products.",
    "Failure to comply with applicable regulations could result in fines, penalties, or restrictions on our business.",
    "Increasing attention to environmental, social, and governance matters may result in additional costs and scrutiny.",
    "Physical and transition risks associated with climate change could affect our operations and supply chain over time.",
    # Demand / macro / seasonality
    "Adverse global macroeconomic conditions, including inflation and higher interest rates, may reduce demand across our end markets.",
    "A slowdown in enterprise or consumer spending could reduce orders from our customers and channel partners.",
    "Seasonal patterns in certain end markets may cause our results to vary from quarter to quarter.",
    "Public health crises, including pandemics, could disrupt our workforce, our suppliers, and demand for our products.",
    "Rising interest rates increase our cost of borrowing and may compress the valuation multiples investors assign to our shares.",
    # Customers / channel
    "A limited number of customers account for a substantial portion of our sales, and losing any of them could harm our business.",
    "We sell through distributors, add-in-board partners, and directly to large operators of computing infrastructure.",
    "Excess inventory held in our sales channel can reduce orders for our products in subsequent periods.",
    "We are exposed to credit risk from accounts receivable, particularly where sales are concentrated among few customers.",
    "Our contractual relationships with cloud service providers may change as those customers develop their own capabilities.",
    # Products / quality / R&D
    "We invest heavily in research and development, and there is no assurance these investments will yield commercially successful products.",
    "Delays in new product introductions or transitions could weaken our competitive position.",
    "Defects or errors in our products could result in warranty claims, product recalls, and reputational damage.",
    "A failure of our quality controls could lead to increased costs, delayed shipments, and loss of customer confidence.",
    "The complexity of our products increases the risk of undetected design or manufacturing defects.",
    "Our long-term competitiveness depends on advancing our technology roadmap ahead of competitors.",
    "Industry standards and interfaces continue to evolve, and our products must remain compatible with them to compete.",
    # Balance sheet / operations
    "We have outstanding indebtedness that requires us to dedicate a portion of our cash flow to debt service.",
    "The agreements governing our indebtedness contain covenants that may limit our operating and financial flexibility.",
    "Goodwill and intangible assets recorded in connection with acquisitions are subject to periodic impairment testing.",
    "We have made and may continue to make acquisitions and strategic investments that involve integration and impairment risk.",
    "We may be required to record charges for the impairment of long-lived assets if business conditions deteriorate.",
    "We lease most of our facilities and may be unable to renew leases on favorable terms or secure additional space when needed.",
    "A substantial portion of our operations and personnel are concentrated in a limited number of geographic regions.",
    "Our insurance coverage may be insufficient to cover all potential losses from business interruption or liability claims.",
    "Our visibility into future demand is limited, and inaccurate forecasts can lead to either shortages or excess inventory.",
    "Negative publicity, whether accurate or not, can quickly damage our brand and reduce demand for our products.",
]


def _build_document() -> str:
    """A many-chunk document with the two needles buried in the MIDDLE — near 40%
    and 60% of the way through — so they land nowhere near the first or last chunk
    and recall genuinely depends on ranking, not position."""
    parts = list(_BOILERPLATE)
    # Insert the later needle first so the earlier insertion index stays valid.
    parts.insert(int(len(_BOILERPLATE) * 0.60), REVENUE_NEEDLE)
    parts.insert(int(len(_BOILERPLATE) * 0.40), MARGIN_NEEDLE)
    return " ".join(parts)


DOCUMENT = _build_document()
DOC_ID = "doc-quality-fixture"


@pytest.fixture
def retriever(tmp_path):
    # Isolated Chroma path per test so the real ./chroma_store is never touched.
    return RagRetriever(chroma_path=str(tmp_path / "chroma"))


# --- fixture guard ----------------------------------------------------------------


def test_fixture_produces_more_chunks_than_the_recall_k():
    # A recall@k test only means something when the store holds MORE than k chunks;
    # if the fixture has <= k chunks, every chunk is returned regardless of ranking
    # and the recall tests would pass even for random retrieval. Fail loudly here if
    # the fixture ever shrinks below that.
    assert len(chunk_text(DOCUMENT)) >= 15


# --- recall@k (k=3, so the needle must genuinely rank into the top 3 of 15+) -------


def test_margin_claim_retrieves_the_margin_needle_in_top_k(retriever):
    # Arrange
    claim = "The company sustains very high gross margins."

    # Act
    results = retriever.retrieve(claim, DOCUMENT, DOC_ID, k=3)

    # Assert — the margin figure ranks into the top-k (recall@k).
    assert any(MARGIN_NEEDLE in chunk for chunk in results)


def test_revenue_growth_claim_retrieves_the_revenue_needle_in_top_k(retriever):
    # Arrange
    claim = "Data center revenue is growing rapidly year over year."

    # Act
    results = retriever.retrieve(claim, DOCUMENT, DOC_ID, k=3)

    # Assert
    assert any(REVENUE_NEEDLE in chunk for chunk in results)


def test_related_claim_scores_meaningfully_higher_than_an_unrelated_claim(retriever):
    # WHY the old rank-based assertion was invalid: top-k ALWAYS returns k passages
    # regardless of how relevant anything is, so a needle can legitimately appear in
    # the top-k — even land first — for an unrelated query when nothing else is
    # closer. Relevance therefore has to be judged by SCORE, not by rank. We compare
    # the best similarity for a related claim against the best for an unrelated one.
    related_claim = "The company sustains very high gross margins."
    unrelated_claim = "The board approved a large quarterly cash dividend to shareholders."

    # Act
    related = retriever.retrieve_scored(related_claim, DOCUMENT, DOC_ID, k=4)
    unrelated = retriever.retrieve_scored(unrelated_claim, DOCUMENT, DOC_ID, k=4)

    # Assert — the related claim's top passage is a meaningfully stronger match.
    assert related and unrelated
    related_best = related[0][1]
    unrelated_best = unrelated[0][1]
    assert related_best > unrelated_best + 0.1


# --- verbatim + edge cases --------------------------------------------------------


def test_every_returned_chunk_is_a_verbatim_substring_of_the_document(retriever):
    # Arrange
    claim = "Gross margins remain strong."

    # Act
    results = retriever.retrieve(claim, DOCUMENT, DOC_ID, k=4)

    # Assert — nothing was normalised in the round-trip; quotes will still locate.
    assert results
    assert all(chunk in DOCUMENT for chunk in results)


def test_empty_document_returns_no_passages(retriever):
    # Arrange
    empty = "   \n  "

    # Act
    results = retriever.retrieve("any claim", empty, "doc-empty", k=4)

    # Assert
    assert results == []


def test_k_larger_than_chunk_count_returns_what_exists(retriever):
    # Arrange — a short document is a single chunk; ask for far more than exist.
    short_doc = "Gross margin held at 70 percent this quarter."

    # Act
    results = retriever.retrieve("gross margin", short_doc, "doc-short", k=50)

    # Assert
    assert results == [short_doc]


# --- dedup ------------------------------------------------------------------------


def test_re_retrieving_the_same_document_does_not_duplicate_chunks(retriever):
    # Arrange
    claim = "Gross margins are high."
    expected_chunks = len(chunk_text(DOCUMENT))

    # Act — retrieve twice for the same document_id.
    retriever.retrieve(claim, DOCUMENT, DOC_ID, k=4)
    count_after_first = retriever._get_collection().count()
    retriever.retrieve(claim, DOCUMENT, DOC_ID, k=4)
    count_after_second = retriever._get_collection().count()

    # Assert — the document was embedded once and reused, not re-added.
    assert count_after_first == expected_chunks
    assert count_after_second == count_after_first
