"""RSS news adapter.

WHY NOT YAHOO. The spec named Yahoo Finance's per-ticker RSS. It was checked before
writing this and it is NOT usable anonymously: the documented endpoint

    https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA&region=US&lang=en-US

returns HTTP 429 "Too Many Requests" on every attempt, including after backing off,
without an Accept header, and without the region parameters. The older
finance.yahoo.com/rss/headline?s=... path still 301-redirects to that same URL, so the
URL FORMAT is current — Yahoo is simply refusing unauthenticated traffic.

So this uses Google News RSS instead, which was verified working:
    HTTP 200, 100 items for NVDA and for AAPL, valid RSS 2.0.
An unknown ticker returns HTTP 200 with zero items, which is a real "no news" answer
rather than an error, and is reported as such.

WHY NO feedparser. Google News returns well-formed RSS 2.0 with exactly the fields
needed (title, link, pubDate, source), and stdlib xml.etree parses it directly.
Publication dates are RFC 822, which email.utils.parsedate_to_datetime handles,
returning timezone-aware datetimes. A third-party dependency would buy nothing here.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urlparse

import httpx

from backend.ports.news_source import NewsItem, NewsSource

REQUEST_TIMEOUT = 10

# "<ticker> stock" rather than the bare ticker: bare symbols collide with ordinary
# words (GOOG is fine, but "F", "ALL" and "IT" are not), and the qualifier keeps the
# results financial.
_FEED_URL = (
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
)

# Favicons are DERIVED from the publisher domain, never fetched here — turning one
# feed request into a hundred image requests server-side would be far more expensive
# than the feature is worth. The browser loads these lazily and caches them per
# domain, so a list of 20 headlines from 6 publishers costs 6 requests, once.
#
# Behaviour on an unknown domain, measured rather than assumed: the service replies
# 404 but with a real 48x48 PNG placeholder in the BODY, which browsers decode and
# display — the image's onError does NOT fire. So an unrecognised publisher shows a
# neutral generic icon, not a blank space. That is an acceptable outcome here; the
# frontend's onError fallback still covers the cases that produce no image at all
# (DNS failure, the request being blocked, the service being down).
_FAVICON_URL = "https://icons.duckduckgo.com/ip3/{domain}.ico"


class NewsError(Exception):
    """Base for every news failure, so callers can catch this one broadly."""


class NewsNetworkError(NewsError):
    """Timeout or connection failure."""


class NewsUnavailableError(NewsError):
    """The feed responded with a non-200 status."""


class NewsFeedFormatError(NewsError):
    """The response was not parseable RSS."""


class RssNewsSource(NewsSource):
    def fetch_headlines(self, ticker: str, limit: int = 10) -> list[NewsItem]:
        url = _FEED_URL.format(query=quote_plus(f"{ticker} stock"))

        try:
            response = httpx.get(
                url,
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
                # Some feed hosts reject requests without a browser-ish User-Agent.
                headers={"User-Agent": "Investment OS news reader"},
            )
        except httpx.HTTPError as exc:
            raise NewsNetworkError(f"Could not reach the news feed for {ticker}: {exc}")

        if response.status_code != 200:
            raise NewsUnavailableError(
                f"News feed for {ticker} returned HTTP {response.status_code}"
            )

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise NewsFeedFormatError(f"News feed for {ticker} is not valid XML: {exc}")

        items = root.findall("./channel/item")
        if items is None:
            raise NewsFeedFormatError(
                f"News feed for {ticker} has no channel/item structure"
            )

        headlines: list[NewsItem] = []
        for item in items[:limit]:
            title = _text(item, "title")
            link = _text(item, "link")
            # A headline with no title or no link is unusable; skip that entry rather
            # than emitting a broken row or failing the whole feed.
            if not title or not link:
                continue

            domain = _source_domain(item)
            headlines.append(
                NewsItem(
                    title=title,
                    url=link,
                    source=_source_name(item),
                    source_domain=domain,
                    favicon_url=_FAVICON_URL.format(domain=domain) if domain else None,
                    published_at=_published_at(item),
                    ticker=ticker,
                )
            )
        return headlines


def _text(item: ET.Element, tag: str) -> str | None:
    element = item.find(tag)
    if element is None or element.text is None:
        return None
    return element.text.strip() or None


def _source_name(item: ET.Element) -> str:
    """RSS <source> carries the publisher. Fall back rather than fail — a missing
    publisher is cosmetic, not a reason to drop a headline."""
    return _text(item, "source") or "Unknown"


def _source_domain(item: ET.Element) -> str | None:
    """The publisher's domain, from the <source url="..."> attribute.

    None whenever the attribute is absent or does not parse into a host. The
    publisher NAME is never used as a fallback — "The Motley Fool" is not
    "themotleyfool.com" (it is fool.com), so deriving a domain from the name would
    quietly produce a wrong icon, which is worse than no icon.
    """
    source = item.find("source")
    if source is None:
        return None
    url = source.attrib.get("url")
    if not url:
        return None

    try:
        host = urlparse(url).hostname
    except ValueError:
        return None
    if not host:
        return None

    # Strip only "www." — other subdomains are meaningful (finance.yahoo.com has its
    # own icon and is a different property from yahoo.com).
    return host[4:] if host.startswith("www.") else host


def _published_at(item: ET.Element) -> datetime | None:
    """Parse pubDate into a timezone-aware datetime, or None.

    None means "we do not know" — never a guessed timestamp, which would silently
    reorder the merged feed and make stale news look fresh.

    The UTC fallback is not a guess: parsedate_to_datetime returns a NAIVE datetime for
    an RFC 5322 "-0000" offset, which per the spec means the time is UTC but the
    sender's local zone is unknown. Left naive it would blow up the merge in
    news_service, because comparing naive and aware datetimes raises TypeError.
    """
    raw = _text(item, "pubDate")
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
