import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.adapters.yfinance_price_source import PriceNetworkError
from backend.models.base import Base
from backend.models.claim import Claim
from backend.models.document import Document
from backend.models.evidence_event import EvidenceEvent
from backend.models.thesis import Thesis
from backend.models.user import User
from backend.ports.price_source import PricePoint, PriceSource
from backend.repositories import alert_repository
from backend.services import price_service
from backend.services.chart_service import build_chart_data

TODAY = datetime.date(2026, 7, 27)


class FakePriceSource(PriceSource):
    """Serves a fixed window of closes, or raises."""

    def __init__(self, points=None, raises=None):
        self._points = points or []
        self._raises = raises

    def get_quote(self, ticker):
        raise NotImplementedError

    def get_company_profile(self, ticker):
        raise NotImplementedError

    def get_current_price(self, ticker):
        raise NotImplementedError

    def get_price_history(self, ticker, days=365):
        if self._raises:
            raise self._raises
        return self._points


def window(start: datetime.date, length: int) -> list[PricePoint]:
    return [
        PricePoint(date=start + datetime.timedelta(days=offset), close=100.0 + offset)
        for offset in range(length)
    ]


@pytest.fixture(autouse=True)
def clean_price_cache():
    # The price cache is module-level; a fake source in one test would otherwise be
    # served from another test's entry.
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
    yield session
    session.close()


@pytest.fixture
def thesis(db):
    user = User(email="demo@local")
    db.add(user)
    db.flush()
    thesis = Thesis(user_id=user.id, ticker="NVDA", reasoning_raw="...", status="weakening")
    db.add(thesis)
    db.flush()
    db.add(
        Claim(
            thesis_id=thesis.id,
            statement="Nvidia sustains high gross margins.",
            proof_condition="Margin stays above 72 percent.",
            break_condition="Margin falls below 65 percent.",
            is_core=True,
            status="broken",
        )
    )
    db.commit()
    return thesis


def add_evidence(db, thesis, *, when: datetime.date, verdict: str, quote="A quote."):
    document = Document(
        source_type="paste",
        title="doc",
        content_hash=f"hash-{when}-{verdict}-{db.query(Document).count()}",
        raw_text=quote,
    )
    db.add(document)
    db.flush()
    event = EvidenceEvent(
        claim_id=thesis.claims[0].id,
        document_id=document.id,
        verdict=verdict,
        confidence=0.9,
        evidence_quote=quote,
        reasoning="because",
    )
    # created_at is a plain DateTime column, so a specific day can be set directly.
    event.created_at = datetime.datetime.combine(when, datetime.time(12, 0))
    db.add(event)
    db.commit()
    return event


# --- the join ---------------------------------------------------------------------


def test_unknown_thesis_returns_none(db, thesis):
    # Arrange / Act / Assert — the endpoint turns this into a 404.
    assert build_chart_data(db, "no-such-thesis", thesis.user_id, source=FakePriceSource()) is None


def test_evidence_and_status_changes_are_both_annotated(db, thesis):
    # Arrange
    prices = window(TODAY - datetime.timedelta(days=10), 11)
    add_evidence(db, thesis, when=TODAY - datetime.timedelta(days=5), verdict="contradicts")
    alert = alert_repository.create_alert(
        db,
        thesis_id=thesis.id,
        user_id=thesis.user_id,
        prev_status="weakening",
        new_status="breaking",
        summary="NVDA moved from weakening to breaking",
    )
    alert.created_at = datetime.datetime.combine(
        TODAY - datetime.timedelta(days=3), datetime.time(12, 0)
    )
    db.commit()

    # Act
    chart = build_chart_data(db, thesis.id, thesis.user_id, source=FakePriceSource(prices))

    # Assert
    assert chart is not None
    assert chart.ticker == "NVDA"
    kinds = [event.type for event in chart.events]
    assert kinds == ["evidence", "status_change"]  # sorted by date
    assert chart.events[0].claim_statement == "Nvidia sustains high gross margins."
    assert chart.events[1].new_status == "breaking"


def test_events_outside_the_price_range_are_excluded(db, thesis):
    # Arrange — the chart has nowhere to place a marker with no matching axis point.
    prices = window(TODAY - datetime.timedelta(days=5), 6)  # covers the last 6 days
    add_evidence(
        db, thesis, when=TODAY - datetime.timedelta(days=200), verdict="contradicts",
        quote="Far too old.",
    )
    add_evidence(
        db, thesis, when=TODAY - datetime.timedelta(days=2), verdict="contradicts",
        quote="Inside the window.",
    )

    # Act
    chart = build_chart_data(db, thesis.id, thesis.user_id, source=FakePriceSource(prices))

    # Assert
    assert [event.quote for event in chart.events] == ["Inside the window."]


def test_neutral_evidence_is_not_annotated(db, thesis):
    # Arrange — a neutral verdict means the document said nothing about the claim.
    prices = window(TODAY - datetime.timedelta(days=5), 6)
    add_evidence(db, thesis, when=TODAY - datetime.timedelta(days=2), verdict="neutral")

    # Act
    chart = build_chart_data(db, thesis.id, thesis.user_id, source=FakePriceSource(prices))

    # Assert
    assert chart.events == []


def test_only_this_thesis_events_are_included(db, thesis):
    # Arrange — a second thesis with its own alert must not bleed into this chart.
    other = Thesis(user_id=thesis.user_id, ticker="AAPL", reasoning_raw="...", status="pending")
    db.add(other)
    db.commit()
    alert_repository.create_alert(
        db, thesis_id=other.id, user_id=thesis.user_id,
        prev_status="pending", new_status="weakening",
        summary="AAPL moved",
    )
    prices = window(TODAY - datetime.timedelta(days=5), 6)

    # Act
    chart = build_chart_data(db, thesis.id, thesis.user_id, source=FakePriceSource(prices))

    # Assert
    assert chart.events == []


# --- price failure is survivable --------------------------------------------------


def test_price_failure_still_returns_events_with_the_flag_set(db, thesis):
    # Arrange — the user's own evidence must not disappear because a third party is
    # down.
    add_evidence(
        db, thesis, when=TODAY - datetime.timedelta(days=2), verdict="contradicts",
        quote="Still mine.",
    )
    failing = FakePriceSource(raises=PriceNetworkError("yahoo unreachable"))

    # Act
    chart = build_chart_data(db, thesis.id, thesis.user_id, source=failing)

    # Assert
    assert chart is not None
    assert chart.prices == []
    assert chart.prices_unavailable is True
    assert [event.quote for event in chart.events] == ["Still mine."]


def test_no_price_data_keeps_every_event(db, thesis):
    # Arrange — with no axis there is no range to filter against, so nothing is
    # dropped for being "outside" a window that does not exist.
    add_evidence(
        db, thesis, when=TODAY - datetime.timedelta(days=900), verdict="supports",
        quote="Ancient but mine.",
    )

    # Act
    chart = build_chart_data(db, thesis.id, thesis.user_id, source=FakePriceSource([]))

    # Assert
    assert chart.prices == []
    assert chart.prices_unavailable is False  # empty is not the same as failed
    assert len(chart.events) == 1


def test_successful_prices_do_not_set_the_unavailable_flag(db, thesis):
    # Arrange
    prices = window(TODAY - datetime.timedelta(days=5), 6)

    # Act
    chart = build_chart_data(db, thesis.id, thesis.user_id, source=FakePriceSource(prices))

    # Assert
    assert chart.prices_unavailable is False
    assert len(chart.prices) == 6
