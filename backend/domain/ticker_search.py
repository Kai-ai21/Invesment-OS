"""Ranking for ticker autocomplete. PURE — no network, no I/O.

The corpus is the SEC's own company_tickers.json (~10k rows) which the EDGAR
adapter already fetches and caches, so searching it is a plain in-process filter.
Nothing here knows that; it takes a list of entries and sorts them.

WHY RANKING IS THE WHOLE PROBLEM. Substring matching on 10k companies is trivial
and useless on its own: typing "AMD" against a naive filter buries Advanced Micro
Devices under every company whose NAME contains "amd". Someone typing a ticker
almost always means that ticker, so the tiers below are ordered by how strong a
signal each kind of match is, not by how many results it produces.
"""

from pydantic import BaseModel, Field


class TickerEntry(BaseModel):
    """One row of the SEC map, as the adapter caches it."""

    ticker: str
    company_name: str
    cik: str


class TickerMatch(BaseModel):
    """One suggestion. Deliberately NOT carrying the CIK — the frontend has no use
    for it, and an autocomplete response is not the place to leak internal ids."""

    ticker: str = Field(description="Upper-case symbol, e.g. 'AMD'.")
    company_name: str = Field(description="As the SEC lists it, e.g. 'Advanced Micro Devices Inc.'")


# One character matches hundreds of companies, which is noise rather than help —
# and the dropdown would open on the first keystroke of every ticker ever typed.
MIN_QUERY_LENGTH = 2

# Ranking tiers, strongest signal first. The number is only a sort key.
_EXACT_TICKER = 0
_TICKER_PREFIX = 1
_NAME_PREFIX = 2
_NAME_SUBSTRING = 3


def _tier(entry: TickerEntry, query: str) -> int | None:
    """Which tier this entry matches in, or None if it does not match at all."""
    ticker = entry.ticker.lower()
    name = entry.company_name.lower()

    if ticker == query:
        return _EXACT_TICKER
    if ticker.startswith(query):
        return _TICKER_PREFIX
    # A name PREFIX beats a name substring: "amazon" should reach Amazon.com before
    # a company merely mentioning it somewhere in a longer legal name.
    if name.startswith(query):
        return _NAME_PREFIX
    if query in name:
        return _NAME_SUBSTRING
    return None


def rank_matches(
    entries: list[TickerEntry], query: str, limit: int = 8
) -> list[TickerMatch]:
    """The best `limit` matches for `query`, strongest match first.

    Empty or single-character queries return nothing — see MIN_QUERY_LENGTH.
    """
    normalised = query.strip().lower()
    if len(normalised) < MIN_QUERY_LENGTH or limit <= 0:
        return []

    scored: list[tuple[int, int, str, TickerEntry]] = []
    for entry in entries:
        tier = _tier(entry, normalised)
        if tier is None:
            continue
        # Within a tier, the SHORTER ticker wins: against "AM", AMD is far more
        # likely to be what was meant than AMBAC, and a short symbol is almost
        # always the better-known company. Ticker breaks remaining ties so the
        # order is stable rather than dependent on the SEC's row order.
        scored.append((tier, len(entry.ticker), entry.ticker, entry))

    scored.sort(key=lambda row: (row[0], row[1], row[2]))
    return [
        TickerMatch(ticker=entry.ticker, company_name=entry.company_name)
        for _, _, _, entry in scored[:limit]
    ]
