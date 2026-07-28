"""Assembles the thesis chart: prices, plus the evidence and status changes to
annotate them with.

The annotations are the point of this feature — the price line is only the canvas they
sit on. That shapes two decisions here: a price failure must NOT suppress the events
(the user's own data survives a broken third party), and events that fall outside the
price window are dropped, because the chart has nowhere to put them.
"""

import datetime

from sqlalchemy.orm import Session

from backend.adapters.yfinance_price_source import PriceError
from backend.api.schemas import ChartDataOut, ChartEventOut, ChartPricePointOut
from backend.models.claim import Claim
from backend.models.evidence_event import EvidenceEvent
from backend.ports.price_source import PriceSource
from backend.repositories import alert_repository, thesis_repository
from backend.services.price_service import get_history

# Verdicts worth drawing. "neutral" is deliberately excluded: it means the document had
# nothing to say about the claim, so plotting it would add marks that carry no signal.
_ANNOTATED_VERDICTS = {"supports", "contradicts"}


def _as_date(value: datetime.datetime) -> datetime.date:
    return value.date()


def build_chart_data(
    db: Session,
    thesis_id: str,
    days: int = 365,
    source: PriceSource | None = None,
) -> ChartDataOut | None:
    """Chart payload for one thesis, or None when the thesis does not exist."""
    thesis = thesis_repository.get_thesis(db, thesis_id)
    if thesis is None:
        return None

    # Prices first, but a failure here is survivable — see prices_unavailable.
    prices: list[ChartPricePointOut] = []
    prices_unavailable = False
    try:
        prices = [
            ChartPricePointOut(date=point.date, close=point.close)
            for point in get_history(thesis.ticker, days=days, source=source)
        ]
    except PriceError as exc:
        # Logged, not raised: the events below are the user's own record and must
        # still reach them.
        print(f"Price history unavailable for {thesis.ticker}: {exc}")
        prices_unavailable = True

    events = _collect_events(db, thesis_id)

    # Only events the chart can actually place. With no prices there is no axis at
    # all, so everything is kept and the frontend renders the events without a line
    # rather than silently dropping them.
    if prices:
        first, last = prices[0].date, prices[-1].date
        events = [event for event in events if first <= event.date <= last]

    events.sort(key=lambda event: event.date)

    return ChartDataOut(
        ticker=thesis.ticker,
        prices=prices,
        events=events,
        prices_unavailable=prices_unavailable,
    )


def _collect_events(db: Session, thesis_id: str) -> list[ChartEventOut]:
    """Evidence and status changes, flattened into one annotation list."""
    events: list[ChartEventOut] = []

    # Evidence, joined to its claim so the tooltip can show what the quote was about.
    rows = (
        db.query(EvidenceEvent, Claim)
        .join(Claim, EvidenceEvent.claim_id == Claim.id)
        .filter(Claim.thesis_id == thesis_id)
        .order_by(EvidenceEvent.created_at.asc())
        .all()
    )
    for evidence, claim in rows:
        if evidence.verdict not in _ANNOTATED_VERDICTS:
            continue
        events.append(
            ChartEventOut(
                date=_as_date(evidence.created_at),
                type="evidence",
                verdict=evidence.verdict,
                quote=evidence.evidence_quote,
                claim_statement=claim.statement,
                confidence=evidence.confidence,
            )
        )

    # Status changes come from the alerts table, which is already the record of every
    # meaningful transition — no second source to keep in step.
    for alert in alert_repository.list_alerts(db):
        if alert.thesis_id != thesis_id:
            continue
        events.append(
            ChartEventOut(
                date=_as_date(alert.created_at),
                type="status_change",
                prev_status=alert.prev_status,
                new_status=alert.new_status,
            )
        )

    return events
