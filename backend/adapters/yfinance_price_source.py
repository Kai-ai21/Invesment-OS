"""Price data via yfinance.

WHY NOT STOOQ. The brief offered Stooq's CSV endpoint as the alternative. It is not
usable: https://stooq.com/q/d/l/?s=nvda.us&i=d answers HTTP 200 with an HTML page
carrying a JavaScript proof-of-work bot challenge instead of CSV — with a browser
User-Agent too. Getting CSV out of it would mean defeating that check, which is not
something to build a product on.

WHY history() FOR BOTH. yfinance exposes `fast_info.last_price`, but on an unknown
ticker fast_info raises `KeyError: 'exchangeTimezoneName'` — an internal shape error
that cannot be told apart from a genuine library fault, so "unknown ticker" would be
indistinguishable from "broken". `history()` instead returns an EMPTY frame for an
unknown ticker, which is an unambiguous signal. Verified against NVDA and a made-up
symbol. It also means the current price and the history come from one source and
cannot disagree: the probe showed fast_info.last_price and the final history close were
the same value, because the last daily row covers the open session.
"""

import warnings
from datetime import date

from backend.ports.price_source import CompanyProfile, PricePoint, PriceSource, Quote

# yfinance performs network I/O with its own internal timeouts; this bounds the call we
# make so a hung upstream cannot pin a request open indefinitely.
REQUEST_TIMEOUT = 15

# A few sessions back, so a Monday still has Friday to compare against across holidays.
_CURRENT_PRICE_WINDOW = "10d"


class PriceError(Exception):
    """Base for every price failure, so callers can catch this one broadly."""


class PriceNetworkError(PriceError):
    """The upstream could not be reached, or timed out."""


class PriceUnavailableError(PriceError):
    """A response arrived but could not be used — missing columns, unparseable rows."""


def _to_date(index_value) -> date:
    """yfinance indexes on a tz-aware DatetimeIndex (America/New_York in the probe).
    Take the calendar date in the exchange's own timezone rather than converting to
    UTC, which would roll an after-hours close onto the following day."""
    return index_value.date()


class YFinancePriceSource(PriceSource):
    def _info(self, ticker: str) -> dict:
        """One get_info() call, with library failures translated into our errors."""
        import yfinance

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return yfinance.Ticker(ticker).get_info()
        except Exception as exc:  # noqa: BLE001 - yfinance raises a wide variety
            raise PriceNetworkError(f"Could not fetch data for {ticker}: {exc}") from exc

    def get_company_profile(self, ticker: str) -> CompanyProfile | None:
        """Descriptive detail, from the same get_info() payload the quote uses.

        Field coverage was probed on 2026-07-29 — see CompanyProfile for what is
        reliably present and where it thins out. Nothing here substitutes a default
        for a missing value: a fund genuinely has no sector, and inventing "N/A"
        would put a non-answer where the UI expects a fact.
        """
        info = self._info(ticker)
        if not info:
            raise PriceUnavailableError(f"Empty profile response for {ticker}")

        # The one-key dict is the unknown-symbol shape. A real company always carries
        # at least a name; a fund with no sector still has one.
        name = info.get("longName") or info.get("shortName")
        if name is None and info.get("regularMarketPrice") is None:
            return None

        price = info.get("regularMarketPrice")
        previous_close = info.get("regularMarketPreviousClose")
        change = (
            price - previous_close
            if price is not None and previous_close is not None
            else None
        )

        employees = info.get("fullTimeEmployees")

        return CompanyProfile(
            ticker=ticker.strip().upper(),
            name=name,
            # `or None` collapses the empty string to absent. The probe never saw ""
            # from this provider, but a blank sector rendered as a labelled empty gap
            # is worse than the field simply not being there.
            sector=info.get("sector") or None,
            industry=info.get("industry") or None,
            employees=int(employees) if employees is not None else None,
            website=info.get("website") or None,
            long_business_summary=info.get("longBusinessSummary") or None,
            market_cap=float(info["marketCap"]) if info.get("marketCap") else None,
            price=float(price) if price is not None else None,
            previous_close=float(previous_close) if previous_close is not None else None,
            change=change,
            change_percent=(
                (change / previous_close * 100)
                if change is not None and previous_close
                else None
            ),
        )

    def get_quote(self, ticker: str) -> Quote | None:
        """A full quote, via get_info().

        WHY get_info() AND NOT fast_info, given the module note above warns off it.
        Market cap is simply not available from history(), so the choice was between
        the two metadata paths, and a probe on 2026-07-29 settled it:

          * fast_info raises `KeyError: 'exchangeTimezoneName'` on an unknown symbol
            — the same opaque failure documented at the top of this file, which
            cannot be told apart from a library fault.
          * get_info() returns a dict with ONE key for an unknown symbol and every
            field we want present for a real one. That is an unambiguous signal, so
            the objection that rules fast_info out does not apply here.

        It is also cheaper: 3.9s for ten tickers against 5.8s for fast_info, because
        one call carries the name, price, previous close and market cap together
        rather than lazily pulling history underneath.

        Reliability check: marketCap came back populated for all 30 candidates
        probed, so this is not a field that goes missing for no clear reason.
        """
        info = self._info(ticker)
        if not info:
            raise PriceUnavailableError(f"Empty quote response for {ticker}")

        price = info.get("regularMarketPrice")
        market_cap = info.get("marketCap")
        # Both absent is the unknown-symbol shape (a one-key dict) — a real answer.
        if price is None and market_cap is None:
            return None
        # One present without the other is a genuinely odd response. Reported as a
        # failure rather than returned as a quote with a hole in it, because the
        # page would otherwise show a company with a price and no size, or a size
        # and no price, with nothing to explain why.
        if price is None or market_cap is None:
            raise PriceUnavailableError(
                f"Incomplete quote for {ticker}: "
                f"price={price!r}, marketCap={market_cap!r}"
            )

        previous_close = info.get("regularMarketPreviousClose")
        change = price - previous_close if previous_close is not None else None
        change_percent = (
            (change / previous_close * 100)
            if change is not None and previous_close
            else None
        )

        return Quote(
            ticker=ticker.strip().upper(),
            # Falls back to the symbol rather than to None: the card always needs
            # something to label itself with.
            company_name=info.get("longName") or info.get("shortName") or ticker.upper(),
            price=float(price),
            previous_close=float(previous_close) if previous_close is not None else None,
            change=change,
            change_percent=change_percent,
            market_cap=float(market_cap),
        )

    def _history_frame(self, ticker: str, period: str):
        """Fetch a daily frame, translating library failures into our own errors."""
        import yfinance

        try:
            with warnings.catch_warnings():
                # yfinance is chatty about delisted symbols; the empty frame is the
                # signal we act on, so the warning adds nothing.
                warnings.simplefilter("ignore")
                frame = yfinance.Ticker(ticker).history(
                    period=period, interval="1d", timeout=REQUEST_TIMEOUT
                )
        except Exception as exc:  # noqa: BLE001 - yfinance raises a wide variety
            # Anything thrown here is a failure, never "no such ticker" — an unknown
            # ticker comes back as an empty frame instead.
            raise PriceNetworkError(f"Could not fetch prices for {ticker}: {exc}") from exc

        if frame is None:
            raise PriceUnavailableError(f"No price frame returned for {ticker}")
        if not frame.empty and "Close" not in frame.columns:
            raise PriceUnavailableError(
                f"Price response for {ticker} has no Close column: {list(frame.columns)}"
            )
        return frame

    def get_current_price(self, ticker: str) -> PricePoint | None:
        frame = self._history_frame(ticker, _CURRENT_PRICE_WINDOW)
        if frame.empty:
            return None  # unknown ticker — a real answer, not a failure

        closes = frame["Close"].dropna()
        if closes.empty:
            return None

        latest_index = closes.index[-1]
        latest = float(closes.iloc[-1])

        # Only present when there IS a prior session; a newly listed ticker has none,
        # and inventing a zero change would read as "flat" rather than "unknown".
        previous = float(closes.iloc[-2]) if len(closes) >= 2 else None
        change = latest - previous if previous is not None else None
        change_percent = (
            (change / previous * 100) if previous not in (None, 0) and change is not None
            else None
        )

        return PricePoint(
            date=_to_date(latest_index),
            close=latest,
            previous_close=previous,
            change=change,
            change_percent=change_percent,
        )

    def get_price_history(self, ticker: str, days: int = 365) -> list[PricePoint]:
        # yfinance takes a period string rather than a day count; ask for the smallest
        # standard window that covers the request and trim to size below.
        frame = self._history_frame(ticker, self._period_for(days))
        if frame.empty:
            return []  # unknown ticker, or nothing in the window

        closes = frame["Close"].dropna()
        points = [
            PricePoint(date=_to_date(index), close=float(value))
            for index, value in closes.items()
        ]
        # Oldest first, capped to the requested span. Trading days are fewer than
        # calendar days, so this only ever trims the leading edge of a wider window.
        return points[-days:]

    @staticmethod
    def _period_for(days: int) -> str:
        for limit, period in ((5, "5d"), (30, "1mo"), (90, "3mo"), (180, "6mo"),
                              (365, "1y"), (730, "2y"), (1825, "5y")):
            if days <= limit:
                return period
        return "max"
