from abc import ABC, abstractmethod
import datetime

from pydantic import BaseModel, Field


class PricePoint(BaseModel):
    """One daily close.

    The three change fields are populated only for a CURRENT price, where there is a
    prior close to compare against; history rows leave them None rather than carrying
    a meaningless zero.
    """

    # `datetime.date`, not a bare `date` import: a field NAMED date would shadow the
    # type in its own annotation, which pydantic cannot resolve.
    date: datetime.date = Field(description="Trading day this close belongs to.")
    close: float = Field(description="Closing price, or the latest price if the session is open.")
    previous_close: float | None = Field(
        default=None, description="The prior trading day's close. Current price only."
    )
    change: float | None = Field(
        default=None, description="close - previous_close. Current price only."
    )
    change_percent: float | None = Field(
        default=None, description="Percentage change from previous_close. Current price only."
    )


class Quote(BaseModel):
    """A live quote: what a company is worth and how it moved today.

    ⚠️ EVERY NUMERIC FIELD IS OPTIONAL, AND None NEVER MEANS ZERO. Same rule as
    backend/domain/portfolio.py: a missing price is a gap in what we know, while a
    zero is a claim about the world, and a $0.00 share price beside a real company
    name reads as a catastrophe rather than a failed HTTP call.

    A source's get_quote() returns either a FULLY populated quote or None. The
    half-filled shape — `unavailable` set, numbers None — is built by the service
    layer for a ticker it could not fetch, so a failed company still occupies its
    place on the page instead of vanishing from it.
    """

    ticker: str = Field(description="The symbol as requested, upper-cased.")
    company_name: str | None = Field(
        default=None, description="Full legal name, e.g. 'Apple Inc.'."
    )
    price: float | None = Field(default=None, description="Latest regular-market price.")
    previous_close: float | None = Field(
        default=None, description="The prior session's official close."
    )
    change: float | None = Field(default=None, description="price - previous_close.")
    change_percent: float | None = Field(
        default=None, description="Percentage move from previous_close."
    )
    market_cap: float | None = Field(
        default=None, description="Market capitalisation in USD."
    )

    # Set by the SERVICE, never by an adapter — see the class docstring.
    unavailable: bool = Field(
        default=False, description="True when this quote could not be fetched."
    )
    error: str | None = Field(
        default=None, description="Why, in words, when unavailable."
    )


class PriceSource(ABC):
    @abstractmethod
    def get_quote(self, ticker: str) -> Quote | None:
        """A full quote for `ticker`, or None when the ticker is unknown.

        Same contract as get_current_price: None is the real answer "no such
        symbol", while anything that WENT WRONG raises. A returned Quote always has
        its price and market cap populated — a partial quote is reported as a
        failure rather than shipped with holes in it.
        """

    @abstractmethod
    def get_current_price(self, ticker: str) -> PricePoint | None:
        """The latest price for `ticker`, or None when the ticker is unknown.

        None means "no such ticker" — a real answer. Anything that went WRONG (network
        failure, an unusable response) raises instead, so a caller can never mistake a
        failure for an empty market.
        """

    @abstractmethod
    def get_price_history(self, ticker: str, days: int = 365) -> list[PricePoint]:
        """Daily closes for roughly the last `days`, oldest first.

        An empty list means the ticker is unknown or has no data in the window; a
        failure raises, for the same reason as above.
        """
