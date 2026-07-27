from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    """One headline about one ticker."""

    title: str = Field(description="The headline text.")
    url: str = Field(description="Link to the article.")
    source: str = Field(description="Publisher name, e.g. 'Reuters'.")
    source_domain: str | None = Field(
        default=None,
        description="Publisher domain, e.g. 'barrons.com'. None when the feed gave no "
        "usable source URL — never inferred from the publisher's name.",
    )
    favicon_url: str | None = Field(
        default=None,
        description="Publisher favicon, derived from source_domain. None when there is "
        "no domain to derive it from.",
    )
    published_at: datetime | None = Field(
        description="Timezone-aware publication time, or None when the feed omitted it "
        "or gave something unparseable. Never guessed."
    )
    ticker: str = Field(description="The ticker this headline was fetched for.")


class NewsSource(ABC):
    @abstractmethod
    def fetch_headlines(self, ticker: str, limit: int = 10) -> list[NewsItem]:
        """Recent headlines for `ticker`, newest first.

        An empty list means the feed genuinely had nothing — implementations raise
        rather than returning empty on failure, so a caller can tell "no news" apart
        from "the fetch broke".
        """
