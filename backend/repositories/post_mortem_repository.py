from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from backend.models.post_mortem import PostMortem


def _with_relations(query):
    """Eager-load thesis and claim so reading `.ticker` / `.broken_claim_statement`
    on each row is one query rather than N."""
    return query.options(
        joinedload(PostMortem.thesis), joinedload(PostMortem.broken_claim)
    )


def create_post_mortem(
    db: Session,
    *,
    thesis_id: str,
    broken_claim_id: str | None,
    status_at_break: str,
) -> PostMortem:
    """Create a PENDING post-mortem: no question yet (the AI writes it in Step 2) and
    no response yet (the user writes that)."""
    post_mortem = PostMortem(
        thesis_id=thesis_id,
        broken_claim_id=broken_claim_id,
        status_at_break=status_at_break,
    )
    db.add(post_mortem)
    db.commit()
    db.refresh(post_mortem)
    return post_mortem


def get_post_mortem(db: Session, post_mortem_id: str) -> PostMortem | None:
    return (
        _with_relations(db.query(PostMortem))
        .filter(PostMortem.id == post_mortem_id)
        .first()
    )


def list_post_mortems(
    db: Session, thesis_id: str | None = None, pending_only: bool = False
) -> list[PostMortem]:
    """Newest first. `pending_only` keeps the ones still awaiting an answer."""
    query = _with_relations(db.query(PostMortem))
    if thesis_id is not None:
        query = query.filter(PostMortem.thesis_id == thesis_id)
    if pending_only:
        # Unanswered is defined by a null response, not by a separate status column —
        # one source of truth, so the two can never disagree.
        query = query.filter(PostMortem.user_response.is_(None))
    return query.order_by(PostMortem.created_at.desc()).all()


def answer_post_mortem(
    db: Session, post_mortem_id: str, user_response: str
) -> PostMortem | None:
    """Returns None when no such post-mortem exists, so the caller can 404."""
    post_mortem = get_post_mortem(db, post_mortem_id)
    if post_mortem is None:
        return None

    post_mortem.user_response = user_response
    post_mortem.answered_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(post_mortem)
    return post_mortem


def delete_post_mortem(db: Session, post_mortem_id: str) -> bool:
    """Post-mortems ARE deletable, unlike evidence events.

    The distinction is whose record it is. An EvidenceEvent is a record of the WORLD —
    what a document said about a claim — and deleting one would falsify the history the
    thesis status is computed from. A post-mortem is the user's private admission about
    THEMSELVES: what they got wrong and why. Nobody should be forced to keep a
    confession they no longer want to have made, and nothing downstream recomputes from
    it. Returns False when there was nothing to delete.
    """
    post_mortem = db.get(PostMortem, post_mortem_id)
    if post_mortem is None:
        return False

    db.delete(post_mortem)
    db.commit()
    return True


def count_answered(db: Session) -> int:
    """How many post-mortems the user has actually answered.

    Feeds the later minimum-data rule: pattern analysis over two or three reflections
    would be noise dressed up as insight, so the feature stays hidden until there is
    enough to say anything real. Pending rows deliberately do not count.
    """
    return db.query(PostMortem).filter(PostMortem.user_response.is_not(None)).count()
