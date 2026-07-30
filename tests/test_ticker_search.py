import pytest

from backend.domain.ticker_search import TickerEntry, rank_matches
from backend.services.ticker_service import search_tickers

ENTRIES = [
    TickerEntry(ticker="AMD", company_name="Advanced Micro Devices Inc", cik="0000002488"),
    TickerEntry(ticker="AMZN", company_name="Amazon Com Inc", cik="0001018724"),
    TickerEntry(ticker="AMGN", company_name="Amgen Inc", cik="0000318154"),
    TickerEntry(ticker="AMBA", company_name="Ambarella Inc", cik="0001280263"),
    TickerEntry(ticker="NVDA", company_name="NVIDIA CORP", cik="0001045810"),
    TickerEntry(ticker="AAPL", company_name="Apple Inc.", cik="0000320193"),
    # A decoy whose NAME starts with a rival's ticker. Ranking must not let it
    # outrank the real AMD.
    TickerEntry(ticker="XYZQ", company_name="AMD Holdings Corp", cik="0000999999"),
]


class FakeEdgar:
    """Serves a fixed index and counts loads, so cache reuse is observable."""

    def __init__(self, entries=None, raises=None):
        self._entries = entries if entries is not None else ENTRIES
        self._raises = raises
        self.loads = 0

    def load_ticker_index(self):
        self.loads += 1
        if self._raises:
            raise self._raises
        return {e.ticker: e for e in self._entries}


def tickers(matches) -> list[str]:
    return [m.ticker for m in matches]


# --- ranking -----------------------------------------------------------------------


def test_exact_ticker_wins_over_a_company_named_after_it():
    # Arrange — THE case the ranking exists for. "AMD" must not surface
    # "AMD Holdings Corp" above Advanced Micro Devices.
    # Act
    result = rank_matches(ENTRIES, "AMD")

    # Assert
    assert result[0].ticker == "AMD"
    assert result[0].company_name == "Advanced Micro Devices Inc"
    assert "XYZQ" in tickers(result)  # still offered, just not first


def test_ticker_prefixes_come_before_name_matches():
    # Act
    result = tickers(rank_matches(ENTRIES, "AM"))

    # Assert — every ticker starting with AM precedes the name-only match.
    prefix_matches = [t for t in result if t.startswith("AM")]
    assert result[: len(prefix_matches)] == prefix_matches
    assert set(prefix_matches) == {"AMD", "AMZN", "AMGN", "AMBA"}


def test_shorter_tickers_rank_first_within_a_tier():
    # "AM" — AMD (3 chars) is far likelier to be meant than AMBA/AMGN/AMZN.
    assert tickers(rank_matches(ENTRIES, "AM"))[0] == "AMD"


def test_company_name_finds_the_ticker():
    # Arrange / Act — someone who knows the company but not the symbol.
    result = rank_matches(ENTRIES, "amazon")

    # Assert
    assert tickers(result) == ["AMZN"]


def test_name_prefix_beats_name_substring():
    # Arrange — both contain "inc", but only one STARTS with the query.
    entries = [
        TickerEntry(ticker="ZZZA", company_name="Global Apple Supply Co", cik="1"),
        TickerEntry(ticker="ZZZB", company_name="Apple Logistics Ltd", cik="2"),
    ]

    # Act
    result = tickers(rank_matches(entries, "apple"))

    # Assert — the one whose name begins with it comes first.
    assert result[0] == "ZZZB"


def test_matching_is_case_insensitive():
    assert tickers(rank_matches(ENTRIES, "nvda")) == ["NVDA"]
    assert tickers(rank_matches(ENTRIES, "NvDa")) == ["NVDA"]
    assert tickers(rank_matches(ENTRIES, "NVIDIA")) == ["NVDA"]


def test_limit_is_respected():
    assert len(rank_matches(ENTRIES, "AM", limit=2)) == 2


def test_no_match_returns_empty_rather_than_raising():
    # An unlisted symbol is a normal answer — the UI still lets the user submit.
    assert rank_matches(ENTRIES, "ZZZZZZ") == []


# --- the too-broad guard -----------------------------------------------------------


@pytest.mark.parametrize("query", ["", " ", "A", "  a  "])
def test_short_queries_return_nothing(query):
    # One character matches hundreds of companies; the dropdown would open on the
    # first keystroke of every ticker ever typed.
    assert rank_matches(ENTRIES, query) == []


def test_a_short_query_does_not_touch_the_sec_map():
    # Arrange — guarding the index too: a 1-char query must not be what triggers a
    # cold fetch of the whole 10k-row file.
    edgar = FakeEdgar()

    # Act
    assert search_tickers("A", edgar=edgar) == []

    # Assert
    assert edgar.loads == 0


# --- the service --------------------------------------------------------------------


def test_service_reads_the_shared_edgar_index():
    # Arrange — no second data source: search goes through the adapter's cached map.
    edgar = FakeEdgar()

    # Act
    result = search_tickers("AMZN", edgar=edgar)

    # Assert
    assert tickers(result) == ["AMZN"]
    assert edgar.loads == 1


def test_service_propagates_an_index_failure():
    # Arrange — the endpoint turns this into a 502; the input stays usable.
    from backend.adapters.edgar_source import EdgarNetworkError

    edgar = FakeEdgar(raises=EdgarNetworkError("sec.gov unreachable"))

    # Act / Assert
    with pytest.raises(EdgarNetworkError):
        search_tickers("AMD", edgar=edgar)


def test_service_honours_limit():
    assert len(search_tickers("AM", limit=3, edgar=FakeEdgar())) == 3
