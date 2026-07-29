"""The twelve largest US-listed companies by market capitalisation.

TWELVE, NOT TEN, for a layout reason as much as a market one: the market page is a
three-column grid, and twelve fills it evenly where ten left a ragged final row.

WHAT IS CURATED AND WHAT IS LIVE — the distinction matters, because half of this
page is a hand-maintained fact and half is not:

  * MEMBERSHIP (which twelve tickers appear) is MANUALLY CURATED. It is a snapshot of
    a ranking that drifts, and nothing in this codebase re-derives it. It goes
    stale silently — a company can leave the top twelve without anything here
    noticing. The UI says so in a footer note rather than implying the list
    maintains itself.
  * PRICES and MARKET CAPS are LIVE on every request (15-minute cache), and the
    ORDER shown is re-sorted from those live caps. So the ranking among these twelve
    is always current even though the twelve themselves are fixed.

LAST REVIEWED: 2026-07-30, against live market caps pulled from yfinance. The
figures beside each ticker below are that day's measurement, and the order is that
day's ranking.

Candidates weighed for the two added places, measured the same day:
    LLY   1.079T  <- added
    JPM   0.916T  <- added
    WMT   0.909T
    V     0.701T
    ORCL  0.339T

⚠️ TWO BOUNDARIES ARE TIGHT, and both are near the bottom where it matters most:
  * BRK-B (1.098T) over LLY (1.079T) — under 2% apart. These two can swap in a
    week; they are simply adjacent now rather than one being in and one out.
  * JPM (0.916T) over WMT (0.909T) — under 1% apart, and WMT is the first name
    NOT on this list. Twelfth place is the least stable entry here and the first
    thing to re-check; on another day Walmart is as defensible a twelfth.

Tickers, not company names: the names come back live from the quote, so keeping a
second copy here would just be something else to go stale.
"""

import datetime

# Bump this whenever MARKET_LEADERS is re-checked against real market caps. This is
# the canonical record of when that last happened; the API deliberately returns a
# bare quote list, so today the UI states that membership is curated without
# quoting this date.
LAST_REVIEWED = datetime.date(2026, 7, 30)

# Ordered by market cap as of LAST_REVIEWED. market_service re-sorts by the live
# figures, so this order is documentation of the review, not something relied on.
MARKET_LEADERS: tuple[str, ...] = (
    "AAPL",   # 4.967T  Apple
    "NVDA",   # 4.602T  NVIDIA
    "GOOGL",  # 4.118T  Alphabet
    "MSFT",   # 2.901T  Microsoft
    "AMZN",   # 2.438T  Amazon
    "TSM",    # 1.943T  Taiwan Semiconductor (US-listed ADR)
    "AVGO",   # 1.762T  Broadcom
    "META",   # 1.487T  Meta Platforms
    "TSLA",   # 1.178T  Tesla
    "BRK-B",  # 1.098T  Berkshire Hathaway (class B — the liquid, US-listed line)
    "LLY",    # 1.079T  Eli Lilly
    "JPM",    # 0.916T  JPMorgan Chase
)
