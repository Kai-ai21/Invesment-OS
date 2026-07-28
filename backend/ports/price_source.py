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


class PriceSource(ABC):
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
