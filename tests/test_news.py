from datetime import datetime, timezone

import pytest

from backend.adapters.rss_news_source import NewsUnavailableError
from backend.ports.news_source import NewsItem, NewsSource
from backend.services import news_service
from backend.services.news_service import get_news_for_ticker


class FakeNewsSource(NewsSource):
    """Headlines per ticker. An Exception value raises it; a missing ticker is a
    real feed with nothing in it. Records calls so cache behaviour is observable."""

    def __init__(self, feeds: dict):
        self.feeds = feeds
        self.calls: list[tuple[str, int]] = []

    def fetch_headlines(self, ticker: str, limit: int = 10) -> list[NewsItem]:
        self.calls.append((ticker, limit))
        value = self.feeds.get(ticker, [])
        if isinstance(value, Exception):
            raise value
        return value[:limit]


def headline(ticker: str, title: str, published_at: datetime | None) -> NewsItem:
    return NewsItem(
        title=title,
        url=f"https://example.com/{title}",
        source="Example Wire",
        source_domain="example.com",
        favicon_url="https://icons.example/example.com.ico",
        published_at=published_at,
        ticker=ticker,
    )


def at(day: int) -> datetime:
    return datetime(2026, 3, day, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clean_news_cache():
    # The cache is module-level; without this a fake in one test would serve another.
    news_service.clear_cache()
    yield
    news_service.clear_cache()


def test_returns_headlines_newest_first():
    source = FakeNewsSource(
        {"NVDA": [headline("NVDA", "older", at(1)), headline("NVDA", "newer", at(9))]}
    )

    items = get_news_for_ticker("NVDA", limit=10, source=source)

    assert [item.title for item in items] == ["newer", "older"]


def test_undated_headlines_sink_to_the_bottom():
    source = FakeNewsSource(
        {"NVDA": [headline("NVDA", "undated", None), headline("NVDA", "dated", at(1))]}
    )

    items = get_news_for_ticker("NVDA", limit=10, source=source)

    assert [item.title for item in items] == ["dated", "undated"]


def test_unknown_ticker_is_an_empty_feed_not_an_error():
    """The distinction the endpoint's 404 rule rests on: a well-formed symbol
    nobody wrote about answers [], which is a real answer."""
    source = FakeNewsSource({})

    assert get_news_for_ticker("ZZZZ", limit=10, source=source) == []


@pytest.mark.parametrize("raw", ["", "   ", "hello world", "../etc", "TOOLONGTICKER"])
def test_invalid_ticker_returns_none_without_fetching(raw):
    source = FakeNewsSource({})

    assert get_news_for_ticker(raw, limit=10, source=source) is None
    # None is decided on shape alone — nothing that cannot be a symbol reaches the
    # network, or the cache.
    assert source.calls == []


@pytest.mark.parametrize("raw", ["nvda", "  NVDA  ", "nVdA"])
def test_ticker_is_normalised(raw):
    source = FakeNewsSource({"NVDA": [headline("NVDA", "one", at(1))]})

    items = get_news_for_ticker(raw, limit=10, source=source)

    assert [item.title for item in items] == ["one"]
    assert source.calls == [("NVDA", 10)]


def test_class_share_tickers_are_valid():
    source = FakeNewsSource({"BRK.B": [headline("BRK.B", "one", at(1))]})

    assert len(get_news_for_ticker("brk.b", limit=10, source=source) or []) == 1


def test_second_call_is_served_from_the_shared_cache():
    source = FakeNewsSource({"NVDA": [headline("NVDA", "one", at(1))]})

    get_news_for_ticker("NVDA", limit=10, source=source)
    get_news_for_ticker("NVDA", limit=10, source=source)

    assert source.calls == [("NVDA", 10)]


def test_shares_the_cache_with_the_portfolio_feed():
    """Not a second fetch path: a ticker the merged feed already pulled at this
    limit is served from memory here, and vice versa."""
    source = FakeNewsSource({"NVDA": [headline("NVDA", "one", at(1))]})

    get_news_for_ticker("NVDA", limit=5, source=source)
    # What get_news_for_all_theses calls per ticker, at its default limit.
    news_service._cached_headlines(source, "NVDA", 5)

    assert source.calls == [("NVDA", 5)]


def test_feed_failure_propagates_rather_than_reading_as_no_news():
    """The merged feed swallows this so the OTHER tickers still render. With one
    ticker there is nothing left to show, and [] would be a lie."""
    source = FakeNewsSource({"NVDA": NewsUnavailableError("HTTP 503")})

    with pytest.raises(NewsUnavailableError):
        get_news_for_ticker("NVDA", limit=10, source=source)


def test_a_failed_fetch_is_not_cached():
    source = FakeNewsSource({"NVDA": NewsUnavailableError("HTTP 503")})

    with pytest.raises(NewsUnavailableError):
        get_news_for_ticker("NVDA", limit=10, source=source)

    # Caching the failure would extend one blip into a 15-minute outage.
    source.feeds["NVDA"] = [headline("NVDA", "recovered", at(1))]
    items = get_news_for_ticker("NVDA", limit=10, source=source)
    assert [item.title for item in items] == ["recovered"]
