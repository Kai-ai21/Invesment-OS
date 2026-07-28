"""Prices, with a TTL cache in front of the upstream.

Same shape as news_service's cache and the same reasoning: PER-PROCESS, lost on
restart, which is fine at this scale because the cost of a miss is one HTTP request.
"""

import time

from backend.adapters.yfinance_price_source import YFinancePriceSource
from backend.ports.price_source import PricePoint, PriceSource

# Quotes move constantly but nobody is trading off this panel; refetching every 15
# minutes keeps it current without hammering a free endpoint.
CURRENT_PRICE_TTL_SECONDS = 15 * 60
# Daily closes only change once a session, so a long TTL costs nothing in accuracy.
HISTORY_TTL_SECONDS = 6 * 60 * 60

# Keyed by (ticker, days) — a cached 30-day series cannot serve a 365-day request, and
# returning the short one would silently truncate the caller's chart. `days` is 0 for
# the current price, which has no span.
_cache: dict[tuple[str, int], tuple[float, object]] = {}


def clear_cache() -> None:
    """Drop every cached entry. For tests and manual refresh."""
    _cache.clear()


def _cached(key: tuple[str, int], ttl: float, fetch):
    entry = _cache.get(key)
    now = time.monotonic()  # monotonic: immune to wall-clock jumps and DST
    if entry is not None and now - entry[0] < ttl:
        return entry[1]

    value = fetch()
    # Only SUCCESSES are cached — an exception propagates without being stored, so one
    # upstream blip does not become a 15-minute outage for that ticker. A `None`
    # (unknown ticker) IS cached: it is a real answer and will not change.
    _cache[key] = (now, value)
    return value


def get_price(ticker: str, source: PriceSource | None = None) -> PricePoint | None:
    """Latest price, or None when the ticker is unknown. Raises on upstream failure."""
    if source is None:
        source = YFinancePriceSource()
    normalized = ticker.strip().upper()
    return _cached(
        (normalized, 0),
        CURRENT_PRICE_TTL_SECONDS,
        lambda: source.get_current_price(normalized),
    )


def get_history(
    ticker: str, days: int = 365, source: PriceSource | None = None
) -> list[PricePoint]:
    """Daily closes, oldest first. Empty when the ticker is unknown."""
    if source is None:
        source = YFinancePriceSource()
    normalized = ticker.strip().upper()
    return _cached(
        (normalized, days),
        HISTORY_TTL_SECONDS,
        lambda: source.get_price_history(normalized, days=days),
    )
