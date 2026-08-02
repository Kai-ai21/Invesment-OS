"""News feeds: one ticker at a time, and merged across every thesis the user holds."""

import logging
import re
import time

from sqlalchemy.orm import Session

from backend.adapters.rss_news_source import NewsError, RssNewsSource
from backend.ports.news_source import NewsItem, NewsSource
from backend.repositories import thesis_repository, user_repository

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 15 * 60  # 15 minutes

# What can be a symbol at all: letters and digits, allowing the dot and hyphen that
# real class-share tickers carry (BRK.B, RDS-A). Deliberately SHAPE-ONLY — it is not
# a list of real companies, because "ZZZZ" is a well-formed ticker nobody has written
# about, and that is an empty feed rather than a bad request. This only rejects input
# that could never name one: blank, prose, a path fragment.
_TICKER_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9.\-]{0,9}")

# In-memory TTL cache, keyed by (ticker, limit).
#
# PER-PROCESS and lost on restart, which is fine at this scale: the cost of a miss is
# one HTTP request, and the panel is opened by one user. It is deliberately NOT in the
# database — news is derived data with a short shelf life, and persisting it would mean
# owning invalidation for no benefit.
#
# `limit` is part of the key because a cached 5-item response cannot serve a later
# request for 10; serving the short list would silently truncate the caller's result.
_cache: dict[tuple[str, int], tuple[float, list[NewsItem]]] = {}


def _cached_headlines(source: NewsSource, ticker: str, limit: int) -> list[NewsItem]:
    key = (ticker, limit)
    entry = _cache.get(key)
    now = time.monotonic()  # monotonic: immune to wall-clock jumps and DST
    if entry is not None and now - entry[0] < CACHE_TTL_SECONDS:
        return entry[1]

    headlines = source.fetch_headlines(ticker, limit=limit)
    # Only successful fetches are cached. Caching a failure would extend one blip into
    # a 15-minute outage for that ticker.
    _cache[key] = (now, headlines)
    return headlines


def clear_cache() -> None:
    """Drop every cached entry. For tests and manual refresh."""
    _cache.clear()


def _sort_key(item: NewsItem) -> tuple[int, float]:
    """Newest first, with undated items last.

    Undated items sort to the bottom rather than being dropped or given a made-up
    timestamp — the first element is the bucket (0 = dated, 1 = undated), so no
    comparison between a real datetime and a placeholder ever happens.
    """
    if item.published_at is None:
        return (1, 0.0)
    return (0, -item.published_at.timestamp())


def get_news_for_ticker(
    ticker: str,
    limit: int = 10,
    source: NewsSource | None = None,
) -> list[NewsItem] | None:
    """Headlines for ONE ticker, newest first. None when that is not a symbol.

    ⚠️ None and [] ARE DIFFERENT ANSWERS, which is the whole reason this returns an
    optional list. None means the caller asked about something that could not name a
    company; [] means a real symbol the feed had nothing about this week. The former
    is a 404 at the edge, the latter is a page section that says "no recent news" —
    collapsing them would tell someone their ticker was wrong when it was fine.

    Goes through the SAME cache and the SAME adapter as the portfolio-wide feed
    below; there is no second fetch path. A ticker the news panel already pulled at
    this limit is served from memory here.

    Also unlike that feed, a fetch failure is NOT swallowed. It isolates per-ticker
    failures so the OTHER tickers still render — here there are no others, and
    answering [] would say "no news" when the truth is "we could not look".
    """
    normalised = ticker.strip().upper()
    if not _TICKER_PATTERN.fullmatch(normalised):
        return None

    if source is None:
        source = RssNewsSource()

    # Sorted with the same key as the merged feed, so an undated headline sinks to
    # the bottom in both places rather than sitting wherever the feed happened to
    # put it.
    return sorted(_cached_headlines(source, normalised, limit), key=_sort_key)


def get_news_for_all_theses(
    db: Session,
    limit_per_ticker: int = 5,
    source: NewsSource | None = None,
) -> list[NewsItem]:
    """Headlines for every ticker the user has a thesis on, newest first.

    Injectable `source` so tests can supply a fake instead of hitting the network.
    """
    if source is None:
        source = RssNewsSource()

    user = user_repository.get_demo_user(db)
    theses = thesis_repository.list_theses_for_user(db, user_id=user.id)

    # Distinct tickers, preserving the thesis ordering so the feed is stable between
    # calls. Several theses on the same ticker must not fetch it twice.
    tickers: list[str] = []
    seen: set[str] = set()
    for thesis in theses:
        if thesis.ticker not in seen:
            seen.add(thesis.ticker)
            tickers.append(thesis.ticker)

    # No theses is a legitimate empty feed, not an error.
    if not tickers:
        return []

    merged: list[NewsItem] = []
    for ticker in tickers:
        try:
            merged.extend(_cached_headlines(source, ticker, limit_per_ticker))
        except NewsError as exc:
            # FAILURE ISOLATION: one dead feed must not empty the whole panel. Log and
            # carry on with the tickers that did work.
            logger.warning("News fetch failed for %s: %s", ticker, exc)
        except Exception as exc:  # noqa: BLE001 - a third-party parse bug is not fatal
            logger.warning("Unexpected news failure for %s: %s", ticker, exc)

    merged.sort(key=_sort_key)
    return merged
