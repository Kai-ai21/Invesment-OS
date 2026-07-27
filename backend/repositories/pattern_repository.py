from sqlalchemy.orm import Session

from backend.models.pattern import Pattern


def create_pattern(
    db: Session, *, statement: str, evidence_post_mortem_ids: list[str]
) -> Pattern:
    pattern = Pattern(
        statement=statement, evidence_post_mortem_ids=evidence_post_mortem_ids
    )
    db.add(pattern)
    db.commit()
    db.refresh(pattern)
    return pattern


def list_patterns(db: Session, include_dismissed: bool = False) -> list[Pattern]:
    """Newest first. Dismissed patterns are hidden unless explicitly asked for."""
    query = db.query(Pattern)
    if not include_dismissed:
        query = query.filter(Pattern.dismissed.is_(False))
    return query.order_by(Pattern.generated_at.desc()).all()


def dismiss_pattern(db: Session, pattern_id: str) -> Pattern | None:
    """Returns None when no such pattern exists, so the caller can 404."""
    pattern = db.get(Pattern, pattern_id)
    if pattern is None:
        return None

    pattern.dismissed = True
    db.commit()
    db.refresh(pattern)
    return pattern


def delete_all_patterns(db: Session) -> int:
    """Clear the set ahead of a regeneration, returning how many were removed.

    Patterns are DERIVED from post-mortems, so the honest model is one current set
    rather than an accumulating history — appending would leave stale observations
    sitting beside fresh ones with no way to tell which reflected the user's current
    record. The post-mortems they cite are untouched.
    """
    removed = db.query(Pattern).delete()
    db.commit()
    return removed
