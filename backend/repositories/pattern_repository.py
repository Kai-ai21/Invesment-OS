from sqlalchemy.orm import Session

from backend.models.pattern import Pattern


def create_pattern(
    db: Session, *, user_id: str, statement: str, evidence_post_mortem_ids: list[str]
) -> Pattern:
    pattern = Pattern(
        user_id=user_id,
        statement=statement,
        evidence_post_mortem_ids=evidence_post_mortem_ids,
    )
    db.add(pattern)
    db.commit()
    db.refresh(pattern)
    return pattern


def list_patterns(
    db: Session, user_id: str, include_dismissed: bool = False
) -> list[Pattern]:
    """Newest first. Dismissed patterns are hidden unless explicitly asked for."""
    query = db.query(Pattern).filter(Pattern.user_id == user_id)
    if not include_dismissed:
        query = query.filter(Pattern.dismissed.is_(False))
    return query.order_by(Pattern.generated_at.desc()).all()


def get_pattern(db: Session, pattern_id: str, user_id: str) -> Pattern | None:
    return (
        db.query(Pattern)
        .filter(Pattern.id == pattern_id, Pattern.user_id == user_id)
        .first()
    )


def dismiss_pattern(db: Session, pattern_id: str, user_id: str) -> Pattern | None:
    """Returns None when no such pattern exists for this user, so callers can 404."""
    pattern = get_pattern(db, pattern_id, user_id)
    if pattern is None:
        return None

    pattern.dismissed = True
    db.commit()
    db.refresh(pattern)
    return pattern


def delete_all_patterns(db: Session, user_id: str) -> int:
    """Clear THIS USER'S set ahead of a regeneration, returning how many were removed.

    Patterns are DERIVED from post-mortems, so the honest model is one current set
    rather than an accumulating history — appending would leave stale observations
    sitting beside fresh ones with no way to tell which reflected the user's current
    record. The post-mortems they cite are untouched.

    ⚠️ THE `user_id` FILTER IS LOAD-BEARING AND ITS ABSENCE WAS DATA LOSS, NOT A LEAK.
    `db.query(Pattern).delete()` with no filter deleted every row in the table, so the
    second user ever to press "Analyse my reflections" would have silently destroyed
    the first user's patterns. Nothing would have errored and nothing would have said
    so — they would simply have been gone.
    """
    removed = db.query(Pattern).filter(Pattern.user_id == user_id).delete()
    db.commit()
    return removed
