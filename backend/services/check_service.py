from sqlalchemy.orm import Session

from backend.adapters.edgar_source import EdgarError, EdgarSource
from backend.repositories import thesis_repository
from backend.services.verification_service import verify_document_against_thesis


class CheckError(Exception):
    pass


def check_thesis(db: Session, thesis_id: str, limit: int = 3) -> dict:
    """Pull recent filings for a thesis's ticker and run each one through verification."""
    thesis = thesis_repository.get_thesis(db, thesis_id)
    source = EdgarSource()

    cik = source.resolve_cik(thesis.ticker)
    if cik is None:
        raise CheckError(f"No SEC CIK found for ticker {thesis.ticker!r}")

    filings = source.list_recent_filings(cik, ticker=thesis.ticker, limit=limit)

    status_before = thesis.status
    checked: list[dict] = []
    skipped: list[dict] = []

    for filing in filings:
        try:
            document = source.load(filing["url"], title=filing["title"])
        except EdgarError as exc:
            # Covers DocumentTooLargeError too. One bad filing must not abort the check.
            skipped.append({"title": filing["title"], "reason": str(exc)})
            continue

        # Verification owns dedup, the citation check, and the status recompute.
        events = verify_document_against_thesis(
            db,
            thesis_id,
            document.raw_text,
            title=document.title,
            source_type=document.source_type,
        )
        checked.append({"title": document.title, "evidence_created": len(events)})

    db.refresh(thesis)

    return {
        "ticker": thesis.ticker,
        "filings_found": len(filings),
        "checked": checked,
        "skipped": skipped,
        "status_before": status_before,
        "status_after": thesis.status,
        "total_evidence_created": sum(item["evidence_created"] for item in checked),
    }
