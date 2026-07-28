"""Assembles the portfolio view: holdings, live prices, and the derived numbers.

Two things drive the shape of this module.

FAILURE IS PER-HOLDING. Prices are fetched one ticker at a time, and one ticker going
wrong must not blank the other nine. A failure is caught inside the loop, marks that
holding's derived values None, and the rest compute normally.

UNPRICED HOLDINGS ARE EXCLUDED FROM TOTALS, AND SAID SO. The alternative — counting a
holding whose price we could not fetch as zero — would quietly understate the portfolio
and show a loss the user does not have. They are left out of every total instead, and
`holdings_excluded` reports how many, so the figure is legibly partial rather than
silently wrong.
"""

from sqlalchemy.orm import Session

from backend.adapters.yfinance_price_source import PriceError
from backend.domain.portfolio import (
    allocation_percent,
    cost_basis,
    market_value,
    pnl_percent,
    unrealised_pnl,
)
from backend.models.thesis import Thesis
from backend.ports.price_source import PriceSource
from backend.repositories import holding_repository, user_repository
from backend.services.price_service import get_price


def get_portfolio(db: Session, source: PriceSource | None = None) -> dict:
    """Every holding with its computed values, plus totals over the priced ones."""
    user = user_repository.get_demo_user(db)
    holdings = holding_repository.list_holdings_for_user(db, user_id=user.id)
    theses_by_ticker = _theses_by_ticker(db, user_id=user.id)

    rows = [_price_and_compute(holding, theses_by_ticker, source) for holding in holdings]

    # Totals over the PRICED rows only — see the module docstring.
    priced = [row for row in rows if not row["price_unavailable"]]
    total_market_value = round(sum(row["market_value"] for row in priced), 2)
    total_cost_basis = round(sum(row["cost_basis"] for row in priced), 2)
    total_pnl = round(total_market_value - total_cost_basis, 2)

    # Second pass: allocation needs the total, which needs every row's value first.
    for row in rows:
        row["allocation_percent"] = allocation_percent(
            row["market_value"], total_market_value
        )

    return {
        "holdings": rows,
        "totals": {
            "market_value": total_market_value,
            # Deliberately also restricted to the priced rows. A cost basis that
            # included the excluded holdings while market value did not would make the
            # P&L below the difference between two different portfolios.
            "cost_basis": total_cost_basis,
            "unrealised_pnl": total_pnl,
            "pnl_percent": (
                round(total_pnl / total_cost_basis * 100, 2)
                if total_cost_basis
                else None
            ),
            "holdings_counted": len(priced),
            "holdings_excluded": len(rows) - len(priced),
        },
    }


def _price_and_compute(holding, theses_by_ticker: dict, source: PriceSource | None) -> dict:
    """One holding's row. Never raises — a price failure becomes a flag on the row."""
    current_price: float | None = None
    price_error: str | None = None

    try:
        point = get_price(holding.ticker, source=source)
        if point is None:
            # A real answer, not a fault: no such ticker. Kept distinct from the
            # failure below because the fixes differ — correct the symbol vs. wait.
            price_error = f"No price data for {holding.ticker}"
        else:
            current_price = point.close
    except PriceError as exc:
        price_error = str(exc)

    thesis = theses_by_ticker.get(holding.ticker)

    return {
        "id": holding.id,
        "ticker": holding.ticker,
        "shares": holding.shares,
        "average_cost": holding.average_cost,
        "purchased_at": holding.purchased_at,
        "note": holding.note,
        "created_at": holding.created_at,
        "current_price": current_price,
        # All None when there is no price — never 0. See backend/domain/portfolio.py.
        "market_value": market_value(holding.shares, current_price),
        "cost_basis": cost_basis(holding.shares, holding.average_cost),
        "unrealised_pnl": unrealised_pnl(
            holding.shares, holding.average_cost, current_price
        ),
        "pnl_percent": pnl_percent(holding.shares, holding.average_cost, current_price),
        "allocation_percent": None,  # filled in once the portfolio total is known
        "price_unavailable": current_price is None,
        "price_error": price_error,
        # Both None when the user owns something they never wrote a thesis about,
        # which is normal and not a problem to flag.
        "thesis_id": thesis.id if thesis is not None else None,
        "thesis_status": thesis.status if thesis is not None else None,
    }


def _theses_by_ticker(db: Session, user_id: str) -> dict:
    """Ticker -> most recent thesis, for the status badge on each row.

    One query rather than one per holding. Where a ticker has several theses the
    newest wins: it is the user's current thinking, and showing an old thesis's status
    next to a live position would be actively misleading.
    """
    theses = (
        db.query(Thesis)
        .filter(Thesis.user_id == user_id)
        .order_by(Thesis.created_at.desc())
        .all()
    )
    by_ticker: dict[str, Thesis] = {}
    for thesis in theses:
        by_ticker.setdefault(thesis.ticker, thesis)
    return by_ticker
