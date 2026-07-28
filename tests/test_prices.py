import warnings
from datetime import date

import pytest

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402

from backend.adapters.yfinance_price_source import (  # noqa: E402
    PriceNetworkError,
    PriceUnavailableError,
)
from backend.main import app  # noqa: E402
from backend.ports.price_source import PricePoint, PriceSource  # noqa: E402
from backend.services import price_service  # noqa: E402


class FakeSource(PriceSource):
    """Serves canned prices and counts calls, so cache behaviour is observable."""

    def __init__(self, price=None, history=None, raises=None):
        self._price = price
        self._history = history or []
        self._raises = raises
        self.price_calls = 0
        self.history_calls = 0

    def get_current_price(self, ticker):
        self.price_calls += 1
        if self._raises:
            raise self._raises
        return self._price

    def get_price_history(self, ticker, days=365):
        self.history_calls += 1
        if self._raises:
            raise self._raises
        return self._history


def a_price() -> PricePoint:
    return PricePoint(
        date=date(2026, 7, 27),
        close=196.51,
        previous_close=206.80,
        change=-10.29,
        change_percent=-4.98,
    )


def some_history() -> list[PricePoint]:
    return [
        PricePoint(date=date(2026, 7, 24), close=206.84),
        PricePoint(date=date(2026, 7, 27), close=196.51),
    ]


@pytest.fixture(autouse=True)
def clean_cache():
    # The cache is module-level and per-process, so it leaks between tests otherwise.
    price_service.clear_cache()
    yield
    price_service.clear_cache()


# --- caching ----------------------------------------------------------------------


def test_a_cache_hit_does_not_refetch_the_price():
    # Arrange
    source = FakeSource(price=a_price())

    # Act
    first = price_service.get_price("NVDA", source=source)
    second = price_service.get_price("NVDA", source=source)

    # Assert
    assert first == second
    assert source.price_calls == 1


def test_a_cache_hit_does_not_refetch_history():
    # Arrange
    source = FakeSource(history=some_history())

    # Act
    price_service.get_history("NVDA", days=30, source=source)
    price_service.get_history("NVDA", days=30, source=source)

    # Assert
    assert source.history_calls == 1


def test_history_is_cached_per_day_count():
    # Arrange — a cached 30-day series must not be served for a 365-day request, or the
    # caller silently gets a truncated chart.
    source = FakeSource(history=some_history())

    # Act
    price_service.get_history("NVDA", days=30, source=source)
    price_service.get_history("NVDA", days=365, source=source)

    # Assert
    assert source.history_calls == 2


def test_the_cache_key_is_case_insensitive_on_the_ticker():
    # Arrange
    source = FakeSource(price=a_price())

    # Act
    price_service.get_price("nvda", source=source)
    price_service.get_price("NVDA", source=source)

    # Assert
    assert source.price_calls == 1


def test_failures_are_not_cached():
    # Arrange — one blip must not become a 15-minute outage for that ticker.
    failing = FakeSource(raises=PriceNetworkError("upstream down"))

    # Act
    with pytest.raises(PriceNetworkError):
        price_service.get_price("NVDA", source=failing)
    with pytest.raises(PriceNetworkError):
        price_service.get_price("NVDA", source=failing)

    # Assert — it tried again rather than replaying a stored failure.
    assert failing.price_calls == 2


def test_a_recovered_upstream_is_served_immediately_after_a_failure():
    # Arrange
    failing = FakeSource(raises=PriceUnavailableError("bad response"))
    with pytest.raises(PriceUnavailableError):
        price_service.get_price("NVDA", source=failing)

    # Act — the next call uses a working source.
    working = FakeSource(price=a_price())
    result = price_service.get_price("NVDA", source=working)

    # Assert — no poisoned cache entry standing in the way.
    assert result is not None
    assert result.close == 196.51


def test_an_unknown_ticker_is_cached_because_it_is_a_real_answer():
    # Arrange — None means "no such ticker", which will not change in 15 minutes.
    source = FakeSource(price=None)

    # Act
    assert price_service.get_price("ZQXW", source=source) is None
    assert price_service.get_price("ZQXW", source=source) is None

    # Assert
    assert source.price_calls == 1


# --- the API ----------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


def test_unknown_ticker_returns_404(client, monkeypatch):
    # Arrange
    monkeypatch.setattr(price_service, "get_price", lambda ticker: None)
    monkeypatch.setattr("backend.api.prices.get_price", lambda ticker: None)

    # Act
    response = client.get("/prices/ZQXWNOTREAL")

    # Assert
    assert response.status_code == 404


def test_upstream_failure_surfaces_as_502_not_500(client, monkeypatch):
    # Arrange — a provider outage is not our bug, and a 500 would say it was.
    def explode(ticker):
        raise PriceNetworkError("yahoo unreachable")

    monkeypatch.setattr("backend.api.prices.get_price", explode)

    # Act
    response = client.get("/prices/NVDA")

    # Assert
    assert response.status_code == 502
    assert "unreachable" in response.json()["detail"]


def test_a_known_ticker_returns_the_price(client, monkeypatch):
    # Arrange
    monkeypatch.setattr("backend.api.prices.get_price", lambda ticker: a_price())

    # Act
    response = client.get("/prices/NVDA")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["close"] == 196.51
    assert body["previous_close"] == 206.80
    assert body["date"] == "2026-07-27"


def test_history_returns_points_oldest_first(client, monkeypatch):
    # Arrange
    monkeypatch.setattr(
        "backend.api.prices.get_history", lambda ticker, days: some_history()
    )

    # Act
    response = client.get("/prices/NVDA/history?days=30")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "NVDA"
    assert [point["date"] for point in body["points"]] == ["2026-07-24", "2026-07-27"]
    # History rows carry no change fields.
    assert body["points"][0]["previous_close"] is None


def test_history_for_an_unknown_ticker_returns_404(client, monkeypatch):
    # Arrange — an empty series from the adapter means "no such ticker".
    monkeypatch.setattr("backend.api.prices.get_history", lambda ticker, days: [])

    # Act
    response = client.get("/prices/ZQXWNOTREAL/history")

    # Assert
    assert response.status_code == 404


def test_history_upstream_failure_surfaces_as_502(client, monkeypatch):
    # Arrange
    def explode(ticker, days):
        raise PriceUnavailableError("garbled response")

    monkeypatch.setattr("backend.api.prices.get_history", explode)

    # Act
    response = client.get("/prices/NVDA/history")

    # Assert
    assert response.status_code == 502
