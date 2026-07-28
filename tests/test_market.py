import pytest

from backend.adapters.yfinance_price_source import PriceNetworkError
from backend.domain.market_leaders import LAST_REVIEWED, MARKET_LEADERS
from backend.ports.price_source import PriceSource, Quote
from backend.services import market_service
from backend.services.market_service import get_market_leaders


class FakeQuoteSource(PriceSource):
    """Market caps per ticker. An Exception value raises it; None is an unknown
    symbol. Counts calls so cache behaviour is observable."""

    def __init__(self, caps: dict):
        self._caps = caps
        self.calls: list[str] = []

    def get_quote(self, ticker):
        self.calls.append(ticker)
        value = self._caps.get(ticker)
        if isinstance(value, Exception):
            raise value
        if value is None:
            return None
        return Quote(
            ticker=ticker,
            company_name=f"{ticker} Inc.",
            price=100.0,
            previous_close=90.0,
            change=10.0,
            change_percent=11.11,
            market_cap=value,
        )

    def get_current_price(self, ticker):
        raise NotImplementedError

    def get_price_history(self, ticker, days=365):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def clean_quote_cache():
    # The cache is module-level; without this a fake in one test would serve another.
    market_service.clear_cache()
    yield
    market_service.clear_cache()


def caps_for(**overrides) -> dict:
    """Every leader priced, largest to smallest, unless overridden."""
    base = {
        ticker: float(len(MARKET_LEADERS) - index) * 1e12
        for index, ticker in enumerate(MARKET_LEADERS)
    }
    base.update(overrides)
    return base


# --- the curated list --------------------------------------------------------------


def test_membership_is_ten_unique_tickers():
    # Arrange / Act / Assert — a duplicate would render two identical cards, and the
    # count is the one thing the page's title claims.
    assert len(MARKET_LEADERS) == 10
    assert len(set(MARKET_LEADERS)) == 10


def test_review_date_is_recorded():
    # The membership is hand-curated and goes stale silently; the date it was last
    # checked is the only thing that makes that visible.
    assert LAST_REVIEWED.year >= 2026


# --- ranking -----------------------------------------------------------------------


def test_quotes_are_ranked_by_live_market_cap_not_curated_order():
    # Arrange — invert the curated order: the LAST entry is now the largest company.
    reversed_caps = {
        ticker: float(index + 1) * 1e12 for index, ticker in enumerate(MARKET_LEADERS)
    }

    # Act
    quotes = get_market_leaders(source=FakeQuoteSource(reversed_caps))

    # Assert — the live figures win, which is the whole point of re-sorting.
    assert [quote.ticker for quote in quotes] == list(reversed(MARKET_LEADERS))
    assert quotes[0].market_cap > quotes[-1].market_cap


def test_every_leader_is_returned():
    quotes = get_market_leaders(source=FakeQuoteSource(caps_for()))
    assert {quote.ticker for quote in quotes} == set(MARKET_LEADERS)


# --- per-ticker failure isolation --------------------------------------------------


def test_one_failing_ticker_does_not_empty_the_page():
    # Arrange
    failing = MARKET_LEADERS[0]
    source = FakeQuoteSource(caps_for(**{failing: PriceNetworkError("yahoo down")}))

    # Act
    quotes = get_market_leaders(source=source)
    by_ticker = {quote.ticker: quote for quote in quotes}

    # Assert — the failure is confined to its own card.
    assert len(quotes) == 10
    assert by_ticker[failing].unavailable is True
    assert "yahoo down" in by_ticker[failing].error
    healthy = [q for q in quotes if q.ticker != failing]
    assert all(q.unavailable is False and q.market_cap is not None for q in healthy)


def test_a_failed_quote_is_null_never_zero():
    # Arrange — a zero price beside a real company name reads as a catastrophe.
    failing = MARKET_LEADERS[3]
    source = FakeQuoteSource(caps_for(**{failing: PriceNetworkError("down")}))

    # Act
    quote = next(q for q in get_market_leaders(source=source) if q.ticker == failing)

    # Assert
    assert quote.price is None
    assert quote.market_cap is None
    assert quote.change is None
    assert quote.change_percent is None


def test_unknown_symbol_is_reported_distinctly_from_a_failure():
    # Arrange — None from the source means "no such ticker", a real answer.
    unknown = MARKET_LEADERS[2]
    source = FakeQuoteSource(caps_for(**{unknown: None}))

    # Act
    quote = next(q for q in get_market_leaders(source=source) if q.ticker == unknown)

    # Assert
    assert quote.unavailable is True
    assert "No quote data" in quote.error


def test_unavailable_quotes_sink_to_the_bottom():
    # Arrange — the LARGEST company by curated order fails, so if a missing cap were
    # treated as 0 it would still sort somewhere; it must go last instead.
    failing = MARKET_LEADERS[0]
    source = FakeQuoteSource(caps_for(**{failing: PriceNetworkError("down")}))

    # Act
    quotes = get_market_leaders(source=source)

    # Assert
    assert quotes[-1].ticker == failing
    assert all(q.market_cap is not None for q in quotes[:-1])


def test_every_ticker_failing_still_returns_all_ten():
    # Arrange — the worst case: the upstream is entirely down.
    source = FakeQuoteSource({t: PriceNetworkError("down") for t in MARKET_LEADERS})

    # Act
    quotes = get_market_leaders(source=source)

    # Assert — ten cards saying "unavailable" is recoverable; an empty page is not
    # distinguishable from "there are no large companies".
    assert len(quotes) == 10
    assert all(q.unavailable for q in quotes)


# --- caching -----------------------------------------------------------------------


def test_successful_quotes_are_served_from_cache():
    # Arrange
    source = FakeQuoteSource(caps_for())

    # Act
    get_market_leaders(source=source)
    get_market_leaders(source=source)

    # Assert — ten upstream calls total, not twenty.
    assert len(source.calls) == 10


def test_failures_are_not_cached():
    # Arrange — a cached failure would become a 15-minute outage for that company.
    failing = MARKET_LEADERS[0]
    source = FakeQuoteSource(caps_for(**{failing: PriceNetworkError("blip")}))

    # Act
    get_market_leaders(source=source)
    get_market_leaders(source=source)

    # Assert — the nine successes were cached, the failure was retried.
    assert source.calls.count(failing) == 2
    assert source.calls.count(MARKET_LEADERS[1]) == 1


def test_clear_cache_forces_a_refetch():
    # Arrange — this is what the page's refresh button ultimately relies on.
    source = FakeQuoteSource(caps_for())
    get_market_leaders(source=source)

    # Act
    market_service.clear_cache()
    get_market_leaders(source=source)

    # Assert
    assert len(source.calls) == 20
