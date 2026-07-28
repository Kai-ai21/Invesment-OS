import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.adapters.yfinance_price_source import PriceNetworkError
from backend.domain.portfolio import (
    allocation_percent,
    cost_basis,
    market_value,
    pnl_percent,
    unrealised_pnl,
)
from backend.models.base import Base
from backend.models.claim import Claim  # noqa: F401 — Thesis.claims cannot resolve without it
from backend.models.thesis import Thesis
from backend.models.user import User
from backend.ports.price_source import PricePoint, PriceSource
from backend.repositories import holding_repository
from backend.services import price_service
from backend.services.portfolio_service import get_portfolio

TODAY = datetime.date(2026, 7, 28)


# --- pure functions ---------------------------------------------------------------


def test_missing_price_returns_none_everywhere_never_zero():
    # Arrange — 10 shares bought at 100, price unknown.
    shares, average_cost = 10.0, 100.0

    # Act
    values = {
        "market_value": market_value(shares, None),
        "unrealised_pnl": unrealised_pnl(shares, average_cost, None),
        "pnl_percent": pnl_percent(shares, average_cost, None),
    }

    # Assert — the point is not merely that these are falsy. A 0 here would render as
    # a real number: 0 market value, -1000 P&L, -100% on a healthy position. Equality
    # against None is what rules 0 out; `assert not value` would pass on the bug.
    assert values == {"market_value": None, "unrealised_pnl": None, "pnl_percent": None}


def test_cost_basis_survives_a_missing_price():
    # Arrange / Act — cost basis takes no price at all, which is the whole point.
    # Assert
    assert cost_basis(10.0, 100.0) == 1000.0


def test_zero_cost_basis_returns_none_rather_than_dividing():
    # Arrange — shares that cost nothing: a grant, a spin-off. Legitimate, not bad input.
    # Act / Assert — no ZeroDivisionError, and no fabricated percentage.
    assert pnl_percent(5.0, 0.0, 20.0) is None
    # The absolute figures are still real and still shown.
    assert unrealised_pnl(5.0, 0.0, 20.0) == 100.0
    assert cost_basis(5.0, 0.0) == 0.0


def test_negative_pnl_computes_correctly():
    # Arrange — 10 shares at 100 now worth 73.50 each.
    # Act / Assert
    assert market_value(10.0, 73.5) == 735.0
    assert unrealised_pnl(10.0, 100.0, 73.5) == -265.0
    assert pnl_percent(10.0, 100.0, 73.5) == -26.5


def test_positive_pnl_computes_correctly():
    assert unrealised_pnl(10.0, 100.0, 125.0) == 250.0
    assert pnl_percent(10.0, 100.0, 125.0) == 25.0


def test_allocation_percent_guards_both_unknowns():
    # A priced holding against a real total.
    assert allocation_percent(250.0, 1000.0) == 25.0
    # No value to allocate.
    assert allocation_percent(None, 1000.0) is None
    # Nothing to be a fraction OF — 0/0 is not 0.
    assert allocation_percent(250.0, 0.0) is None


# --- the service ------------------------------------------------------------------


class FakePriceSource(PriceSource):
    """Prices per ticker; a ticker mapped to an exception raises it, and one mapped to
    None is an unknown symbol."""

    def __init__(self, prices: dict):
        self._prices = prices

    def get_quote(self, ticker):
        raise NotImplementedError  # the portfolio uses current prices, not quotes

    def get_current_price(self, ticker):
        value = self._prices.get(ticker)
        if isinstance(value, Exception):
            raise value
        if value is None:
            return None
        return PricePoint(date=TODAY, close=value)

    def get_price_history(self, ticker, days=365):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def clean_price_cache():
    # The cache is module-level; without this a fake source in one test would serve
    # another test's holdings.
    price_service.clear_cache()
    yield
    price_service.clear_cache()


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    user = User(email="demo@local")
    session.add(user)
    session.commit()
    yield session
    session.close()


def add(db, ticker, shares, average_cost):
    user = db.query(User).first()
    return holding_repository.create_holding(
        db, user_id=user.id, ticker=ticker, shares=shares, average_cost=average_cost
    )


def rows_by_ticker(portfolio) -> dict:
    return {row["ticker"]: row for row in portfolio["holdings"]}


def test_one_failing_ticker_does_not_break_the_rest(db):
    # Arrange — AAPL's price fetch blows up; the other two are fine.
    add(db, "NVDA", 10.0, 100.0)
    add(db, "AAPL", 5.0, 200.0)
    add(db, "MSFT", 2.0, 300.0)
    source = FakePriceSource(
        {
            "NVDA": 150.0,
            "AAPL": PriceNetworkError("yahoo unreachable"),
            "MSFT": 320.0,
        }
    )

    # Act
    rows = rows_by_ticker(get_portfolio(db, source=source))

    # Assert — the healthy rows computed normally.
    assert rows["NVDA"]["market_value"] == 1500.0
    assert rows["NVDA"]["unrealised_pnl"] == 500.0
    assert rows["MSFT"]["market_value"] == 640.0
    assert rows["MSFT"]["price_unavailable"] is False

    # The failed row is flagged and None throughout — NOT zero.
    failed = rows["AAPL"]
    assert failed["price_unavailable"] is True
    assert failed["market_value"] is None
    assert failed["unrealised_pnl"] is None
    assert failed["pnl_percent"] is None
    assert failed["allocation_percent"] is None
    assert "unreachable" in failed["price_error"]
    assert failed["price_status"] == "source_unavailable"
    # ...except what was paid, which never needed a price.
    assert failed["cost_basis"] == 1000.0


def test_totals_exclude_unavailable_holdings_and_report_the_count(db):
    # Arrange — one of three cannot be priced.
    add(db, "NVDA", 10.0, 100.0)  # 1500 value, 1000 basis
    add(db, "MSFT", 2.0, 300.0)  # 640 value, 600 basis
    add(db, "AAPL", 5.0, 200.0)  # unpriceable, 1000 basis
    source = FakePriceSource(
        {"NVDA": 150.0, "MSFT": 320.0, "AAPL": PriceNetworkError("down")}
    )

    # Act
    totals = get_portfolio(db, source=source)["totals"]

    # Assert — AAPL contributes to NOTHING, including the cost basis. Counting its
    # 1000 basis while its market value is absent would show a fake 1140 loss.
    assert totals["market_value"] == 2140.0
    assert totals["cost_basis"] == 1600.0
    assert totals["unrealised_pnl"] == 540.0
    assert totals["pnl_percent"] == 33.75
    assert totals["holdings_counted"] == 2
    assert totals["holdings_excluded"] == 1


def test_unknown_ticker_is_excluded_and_distinguished_from_a_failure(db):
    # Arrange — a typo'd symbol is a real answer ("no such ticker"), not a fault, and
    # the fix is different, so the message must differ.
    add(db, "NVDA", 10.0, 100.0)
    add(db, "NVDAA", 1.0, 100.0)
    source = FakePriceSource({"NVDA": 150.0, "NVDAA": None})

    # Act
    portfolio = get_portfolio(db, source=source)
    rows = rows_by_ticker(portfolio)

    # Assert — same `price_unavailable`, DIFFERENT status, so the UI can say which.
    assert rows["NVDAA"]["price_unavailable"] is True
    assert rows["NVDAA"]["price_status"] == "unknown_ticker"
    assert "No price data" in rows["NVDAA"]["price_error"]
    assert rows["NVDA"]["price_status"] == "ok"
    assert portfolio["totals"]["holdings_excluded"] == 1


def test_allocation_percentages_cover_the_priced_portfolio(db):
    # Arrange
    add(db, "NVDA", 10.0, 100.0)  # 1500
    add(db, "MSFT", 2.0, 250.0)  # 500
    source = FakePriceSource({"NVDA": 150.0, "MSFT": 250.0})

    # Act
    rows = rows_by_ticker(get_portfolio(db, source=source))

    # Assert
    assert rows["NVDA"]["allocation_percent"] == 75.0
    assert rows["MSFT"]["allocation_percent"] == 25.0


def test_thesis_status_is_attached_when_one_exists_and_null_otherwise(db):
    # Arrange — a holding with a thesis, and one without. The second is normal.
    user = db.query(User).first()
    db.add(Thesis(user_id=user.id, ticker="NVDA", reasoning_raw="...", status="breaking"))
    db.commit()
    add(db, "NVDA", 10.0, 100.0)
    add(db, "MSFT", 2.0, 300.0)
    source = FakePriceSource({"NVDA": 150.0, "MSFT": 320.0})

    # Act
    rows = rows_by_ticker(get_portfolio(db, source=source))

    # Assert
    assert rows["NVDA"]["thesis_status"] == "breaking"
    assert rows["MSFT"]["thesis_id"] is None
    assert rows["MSFT"]["thesis_status"] is None


def test_empty_portfolio_totals_are_zero_not_none(db):
    # Arrange — no holdings at all. Zero here is CORRECT: an empty portfolio really is
    # worth nothing, unlike an unpriced one.
    # Act
    portfolio = get_portfolio(db, source=FakePriceSource({}))

    # Assert
    assert portfolio["holdings"] == []
    assert portfolio["totals"]["market_value"] == 0
    assert portfolio["totals"]["holdings_counted"] == 0
    assert portfolio["totals"]["holdings_excluded"] == 0
    # No cost basis means no denominator, so no percentage.
    assert portfolio["totals"]["pnl_percent"] is None


def test_every_holding_failing_leaves_totals_visibly_partial(db):
    # Arrange — the worst case: the price source is entirely down.
    add(db, "NVDA", 10.0, 100.0)
    add(db, "MSFT", 2.0, 300.0)
    source = FakePriceSource(
        {"NVDA": PriceNetworkError("down"), "MSFT": PriceNetworkError("down")}
    )

    # Act
    totals = get_portfolio(db, source=source)["totals"]

    # Assert — 0 with a count of 0 and 2 excluded reads as "nothing could be priced",
    # which is recoverable; 0 with 2 counted would read as "your portfolio is worthless".
    assert totals["market_value"] == 0
    assert totals["holdings_counted"] == 0
    assert totals["holdings_excluded"] == 2


# --- repository -------------------------------------------------------------------


def test_update_distinguishes_an_omitted_note_from_an_explicit_null(db):
    # Arrange
    holding = add(db, "NVDA", 10.0, 100.0)
    holding_repository.update_holding(
        db, holding.id, note="conviction buy", fields_set={"note"}
    )

    # Act — a shares-only edit, with `note` omitted.
    holding_repository.update_holding(db, holding.id, shares=12.0, fields_set={"shares"})

    # Assert — the note survived an unrelated edit.
    assert holding.shares == 12.0
    assert holding.note == "conviction buy"

    # Act — now clear it explicitly.
    holding_repository.update_holding(db, holding.id, note=None, fields_set={"note"})

    # Assert
    assert holding.note is None


def test_update_and_delete_report_a_missing_holding(db):
    assert holding_repository.update_holding(db, "no-such-id", shares=1.0) is None
    assert holding_repository.delete_holding(db, "no-such-id") is False
