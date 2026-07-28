"""Portfolio arithmetic. PURE — no database, no network, no clock.

THE RULE THAT MATTERS HERE: when `current_price` is None, every value derived from it
returns None. Never 0.

This is not defensive tidiness, it is the difference between a correct screen and a
lying one. A missing price means "we could not find out what this is worth" — a gap in
our knowledge. Zero means "this is worth nothing" — a claim about the world. Substitute
one for the other and a healthy position renders as a total loss: market value 0,
unrealised P&L equal to the full cost basis, and -100%. The user would be looking at a
wipeout that never happened, because a rate-limited HTTP call is not a market event.
None propagates instead, and the caller shows "unavailable" rather than a number.

`cost_basis` is the deliberate exception: it is what was PAID, so it needs no live
price and stays a real number through any outage.

Money is rounded to 2dp here rather than at the display edge, so that a total computed
from these values reconciles exactly with the rows the user can see and add up
themselves — a total that disagrees with the visible rows by a cent reads as a bug.
(Floats, not Decimal, per the agreed types; fine at display precision, and no value
here is used to settle a trade.)
"""


def market_value(shares: float, current_price: float | None) -> float | None:
    """What the position is worth now, or None when the price is unknown."""
    if current_price is None:
        return None
    return round(shares * current_price, 2)


def cost_basis(shares: float, average_cost: float) -> float:
    """What was paid for the position.

    Never None: this depends only on what the user recorded, so it survives a price
    outage intact and is the one figure still worth showing when everything else is
    unavailable.
    """
    return round(shares * average_cost, 2)


def unrealised_pnl(
    shares: float, average_cost: float, current_price: float | None
) -> float | None:
    """Gain or loss not yet realised. Negative on a losing position."""
    if current_price is None:
        return None
    return round(shares * current_price - shares * average_cost, 2)


def pnl_percent(
    shares: float, average_cost: float, current_price: float | None
) -> float | None:
    """Gain or loss as a percentage of what was paid.

    None on a zero cost basis — shares that cost nothing (a gift, a grant, a spin-off
    recorded at zero) have no denominator to be a percentage OF. Any gain on them is
    infinite in percentage terms, which is not a number to put on a screen, and
    dividing anyway would raise. Zero cost is a legitimate holding, not bad input.
    """
    if current_price is None:
        return None

    basis = cost_basis(shares, average_cost)
    if basis == 0:
        return None

    return round(unrealised_pnl(shares, average_cost, current_price) / basis * 100, 2)


def allocation_percent(
    holding_value: float | None, total_value: float
) -> float | None:
    """This holding's share of the portfolio.

    None when the holding has no value to allocate (unknown price), and None when the
    total is zero — with nothing in the portfolio there is no whole to be a fraction
    of, and 0/0 is not 0.
    """
    if holding_value is None:
        return None
    if total_value == 0:
        return None
    return round(holding_value / total_value * 100, 2)
