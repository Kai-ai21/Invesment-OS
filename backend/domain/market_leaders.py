"""The ten largest US-listed companies by market capitalisation.

WHAT IS CURATED AND WHAT IS LIVE — the distinction matters, because half of this
page is a hand-maintained fact and half is not:

  * MEMBERSHIP (which ten tickers appear) is MANUALLY CURATED. It is a snapshot of
    a ranking that drifts, and nothing in this codebase re-derives it. It goes
    stale silently — a company can leave the top ten without anything here
    noticing. The UI says so in a footer note rather than implying the list
    maintains itself.
  * PRICES and MARKET CAPS are LIVE on every request (15-minute cache), and the
    ORDER shown is re-sorted from those live caps. So the ranking among these ten
    is always current even though the ten themselves are fixed.

LAST REVIEWED: 2026-07-29, against live market caps pulled from yfinance across a
30-company candidate set. The order below is that day's ranking.

⚠️ THE BOUNDARY IS TIGHT. At review time Berkshire Hathaway held tenth at $1.105T
with Eli Lilly (LLY) immediately behind at $1.089T — a gap of about 1.5%, well
inside a normal month's movement. Treat tenth place as the least stable entry
here and the first thing to check when re-reviewing.

Tickers, not company names: the names come back live from the quote, so keeping a
second copy here would just be something else to go stale.
"""

import datetime

# Bump this whenever MARKET_LEADERS is re-checked against real market caps. This is
# the canonical record of when that last happened; the API deliberately returns a
# bare quote list, so today the UI states that membership is curated without
# quoting this date.
LAST_REVIEWED = datetime.date(2026, 7, 29)

# Ordered by market cap as of LAST_REVIEWED. market_service re-sorts by the live
# figures, so this order is documentation of the review, not something relied on.
MARKET_LEADERS: tuple[str, ...] = (
    "AAPL",   # Apple
    "NVDA",   # NVIDIA
    "GOOGL",  # Alphabet
    "MSFT",   # Microsoft
    "AMZN",   # Amazon
    "TSM",    # Taiwan Semiconductor (US-listed ADR)
    "AVGO",   # Broadcom
    "META",   # Meta Platforms
    "TSLA",   # Tesla
    "BRK-B",  # Berkshire Hathaway (class B — the liquid, US-listed line)
)
