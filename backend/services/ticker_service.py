"""Ticker autocomplete over the SEC's company list.

NO SEPARATE DATA SOURCE. This reuses the exact map the EDGAR adapter already
fetches and caches to resolve CIKs — same file, same process-level cache, one
fetch. There is deliberately no database, no search index and no hardcoded ticker
list here: ~10k rows already in memory is small enough that a linear scan per
keystroke-batch is cheaper than anything that would need keeping in sync.

The ranking itself lives in backend/domain/ticker_search.py, pure and testable.
"""

from backend.adapters.edgar_source import EdgarSource
from backend.domain.ticker_search import TickerMatch, rank_matches


def search_tickers(
    query: str, limit: int = 8, edgar: EdgarSource | None = None
) -> list[TickerMatch]:
    """Best matches for `query`, strongest first. Empty for a query under two
    characters — see MIN_QUERY_LENGTH.

    Raises EdgarError if the SEC map has never been fetched and cannot be. The
    caller turns that into a 502; the frontend degrades to a plain text field,
    because failing autocomplete must never block writing a thesis.
    """
    edgar = edgar if edgar is not None else EdgarSource()

    # Cheap guard BEFORE touching the index: a one-character query returns nothing
    # anyway, so it should not be the thing that triggers a cold 10k-row fetch.
    if len(query.strip()) < 2 or limit <= 0:
        return []

    entries = list(edgar.load_ticker_index().values())
    return rank_matches(entries, query, limit=limit)
