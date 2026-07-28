"""Live quotes for the curated market-leader list.

Three things shape this module, all of them the same decisions made in news_service
and portfolio_service:

FAILURE IS PER-TICKER. Ten separate upstream calls, each caught on its own. One
company failing leaves a card saying so and the other nine intact — never an empty
page because Yahoo hiccuped on one symbol.

THE CACHE IS PER-TICKER, NOT PER-PAGE. Caching the assembled list would freeze a
transient single-ticker failure into the whole page for fifteen minutes. Keyed by
ticker, a failed one is simply retried on the next request while the nine good ones
are still served from cache.

THE ORDER IS LIVE. Membership is hand-curated (see backend/domain/market_leaders.py)
but the ranking is re-sorted from the market caps we just fetched, so the sequence
on screen is correct for today even though the ten names are fixed.
"""

import time

from backend.adapters.yfinance_price_source import PriceError, YFinancePriceSource
from backend.domain.market_leaders import MARKET_LEADERS
from backend.ports.price_source import PriceSource, Quote

# Matches the current-price TTL in price_service: the same data, the same reasoning
# — nobody is trading off this page, and fifteen minutes keeps it current without
# hammering a free endpoint ten times per page view.
QUOTE_TTL_SECONDS = 15 * 60

# ticker -> (fetched_at_monotonic, Quote | None)
_cache: dict[str, tuple[float, Quote | None]] = {}


def clear_cache() -> None:
    """Drop every cached quote. For tests and manual refresh."""
    _cache.clear()


def _cached_quote(ticker: str, source: PriceSource) -> Quote | None:
    entry = _cache.get(ticker)
    now = time.monotonic()  # monotonic: immune to wall-clock jumps and DST
    if entry is not None and now - entry[0] < QUOTE_TTL_SECONDS:
        return entry[1]

    quote = source.get_quote(ticker)
    # SUCCESSES ONLY. An exception propagates to the caller without being stored, so
    # one upstream blip does not become a fifteen-minute outage for that company. A
    # None (unknown symbol) IS cached: it is a real answer and will not change.
    _cache[ticker] = (now, quote)
    return quote


def get_market_leaders(source: PriceSource | None = None) -> list[Quote]:
    """Every curated leader, ranked by live market cap. Always returns all ten."""
    if source is None:
        source = YFinancePriceSource()

    quotes: list[Quote] = []
    for ticker in MARKET_LEADERS:
        try:
            quote = _cached_quote(ticker, source)
        except PriceError as exc:
            quote = None
            error: str | None = str(exc)
        else:
            error = None if quote is not None else f"No quote data for {ticker}"

        # A company that could not be fetched KEEPS ITS PLACE on the page, carrying
        # nulls and a reason rather than disappearing. A silently shorter list would
        # be indistinguishable from the company having left the ranking.
        quotes.append(
            quote
            if quote is not None
            else Quote(ticker=ticker, unavailable=True, error=error)
        )

    # Unavailable quotes sink: an unknown market cap is not the smallest one, and
    # ranking it last-by-value would be inventing a fact. Ticker order breaks ties
    # among them so the grid never reshuffles between refreshes.
    quotes.sort(key=lambda quote: (quote.market_cap is None, -(quote.market_cap or 0), quote.ticker))
    return quotes
