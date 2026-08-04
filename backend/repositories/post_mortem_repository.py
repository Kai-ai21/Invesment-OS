from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from backend.models.post_mortem import PostMortem
from backend.models.thesis import Thesis
from backend.repositories import thesis_repository


def _with_relations(query):
    """Eager-load thesis and claim so reading `.ticker` / `.broken_claim_statement`
    on each row is one query rather than N."""
    return query.options(
        joinedload(PostMortem.thesis), joinedload(PostMortem.broken_claim)
    )


def _owned(query, user_id: str):
    """Constrain a PostMortem query to one user, through its thesis.

    ⚠️ THE JOIN IS SEPARATE FROM THE joinedload ABOVE and neither substitutes for the
    other. `joinedload` decides what gets LOADED alongside each row; this decides
    which rows EXIST. Relying on the eager-load to scope would filter nothing at all.
    """
    return query.join(Thesis, PostMortem.thesis_id == Thesis.id).filter(
        Thesis.user_id == user_id
    )


def create_post_mortem(
    db: Session,
    *,
    thesis_id: str,
    user_id: str,
    broken_claim_id: str | None,
    status_at_break: str,
) -> PostMortem | None:
    """Create a PENDING post-mortem: no question yet (the AI writes it in Step 2) and
    no response yet (the user writes that). None when the thesis is not this user's."""
    if thesis_repository.get_thesis(db, thesis_id, user_id) is None:
        return None

    post_mortem = PostMortem(
        thesis_id=thesis_id,
        broken_claim_id=broken_claim_id,
        status_at_break=status_at_break,
    )
    db.add(post_mortem)
    db.commit()
    db.refresh(post_mortem)
    return post_mortem


def get_post_mortem(db: Session, post_mortem_id: str, user_id: str) -> PostMortem | None:
    return (
        _with_relations(_owned(db.query(PostMortem), user_id))
        .filter(PostMortem.id == post_mortem_id)
        .first()
    )


def list_post_mortems(
    db: Session,
    user_id: str,
    thesis_id: str | None = None,
    pending_only: bool = False,
) -> list[PostMortem]:
    """Newest first. `pending_only` keeps the ones still awaiting an answer.

    ⚠️ user_id IS POSITIONAL AND thesis_id IS NOT. Before A2 the only filter was the
    optional `thesis_id`, so the default call — `list_post_mortems(db)` — returned
    every post-mortem in the database, and that default was what /post-mortems and
    the pattern generator both used. Making the user the required argument means the
    unfiltered call no longer exists.
    """
    query = _with_relations(_owned(db.query(PostMortem), user_id))
    if thesis_id is not None:
        query = query.filter(PostMortem.thesis_id == thesis_id)
    if pending_only:
        # Unanswered is defined by a null response, not by a separate status column —
        # one source of truth, so the two can never disagree.
        query = query.filter(PostMortem.user_response.is_(None))
    return query.order_by(PostMortem.created_at.desc()).all()


def answer_post_mortem(
    db: Session, post_mortem_id: str, user_id: str, user_response: str
) -> PostMortem | None:
    """Returns None when no such post-mortem exists for this user, so callers 404."""
    post_mortem = get_post_mortem(db, post_mortem_id, user_id)
    if post_mortem is None:
        return None

    post_mortem.user_response = user_response
    post_mortem.answered_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(post_mortem)
    return post_mortem


def delete_post_mortem(db: Session, post_mortem_id: str, user_id: str) -> bool:
    """Post-mortems ARE deletable, unlike evidence events.

    The distinction is whose record it is. An EvidenceEvent is a record of the WORLD —
    what a document said about a claim — and deleting one would falsify the history the
    thesis status is computed from. A post-mortem is the user's private admission about
    THEMSELVES: what they got wrong and why. Nobody should be forced to keep a
    confession they no longer want to have made, and nothing downstream recomputes from
    it. Returns False when there was nothing to delete.

    ⚠️ THE MOST DANGEROUS UNSCOPED FUNCTION IN THE OLD CODE. A destructive operation
    keyed on a guessable id, reachable from DELETE /post-mortems/{id}: one user could
    permanently erase another's reflections, and nothing anywhere would record that it
    had happened.
    """
    post_mortem = get_post_mortem(db, post_mortem_id, user_id)
    if post_mortem is None:
        return False

    db.delete(post_mortem)
    db.commit()
    return True


def count_answered(db: Session, user_id: str) -> int:
    """How many post-mortems THIS USER has actually answered.

    Feeds the later minimum-data rule: pattern analysis over two or three reflections
    would be noise dressed up as insight, so the feature stays hidden until there is
    enough to say anything real. Pending rows deliberately do not count.

    Unscoped, this counted everyone's — so a second user signing up would have
    unlocked pattern analysis for a third user who had written nothing.
    """
    return (
        _owned(db.query(PostMortem), user_id)
        .filter(PostMortem.user_response.is_not(None))
        .count()
    )
