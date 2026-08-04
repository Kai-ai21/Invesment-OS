from sqlalchemy.orm import Session

from backend.domain.claim import ClaimData
from backend.models.claim import Claim
from backend.models.thesis import Thesis

# ⚠️ EVERY FUNCTION IN THIS PACKAGE TAKES user_id, AND IT IS NEVER OPTIONAL.
#
# The alternative — remembering to add `.filter(user_id == ...)` at each call site —
# was measured before this change: 4 of 29 user-owned repository functions filtered,
# and the 25 that did not were reachable from 17 endpoints. Nobody had been careless;
# a fetch-by-id simply LOOKS finished without the check, which is exactly why this
# class of bug (IDOR) is so common. A required positional argument cannot be
# forgotten — the call does not run, so the failure mode moves from "silently returns
# someone else's row" to "TypeError, in the first test that touches it".
#
# The scoping rule for nested rows: a claim is reachable only through a thesis you
# own, evidence only through a claim you own. Those joins live in the repositories,
# not in the callers, so there is one place to audit rather than fifty.


def create_thesis(db: Session, *, user_id: str, ticker: str, reasoning_raw: str) -> Thesis:
    thesis = Thesis(user_id=user_id, ticker=ticker, reasoning_raw=reasoning_raw)
    db.add(thesis)
    db.commit()
    db.refresh(thesis)
    return thesis


def add_claims(
    db: Session, *, thesis_id: str, user_id: str, claims: list[ClaimData]
) -> list[Claim]:
    """Attach claims to a thesis. Returns [] if the thesis is not this user's.

    Scoped even though today's only caller passes a thesis it just created for this
    very user: the argument is a bare id, and an unscoped write keyed on a caller's id
    is how claims end up appended to someone else's thesis the first time this gets
    called from somewhere new.
    """
    if get_thesis(db, thesis_id, user_id) is None:
        return []

    db_claims = [
        Claim(
            thesis_id=thesis_id,
            statement=claim.statement,
            proof_condition=claim.proof_condition,
            break_condition=claim.break_condition,
            is_core=claim.is_core,
        )
        for claim in claims
    ]
    db.add_all(db_claims)
    db.commit()
    return db_claims


def set_status(db: Session, *, thesis_id: str, user_id: str, status: str) -> None:
    thesis = get_thesis(db, thesis_id, user_id)
    if thesis is None:
        return
    thesis.status = status
    db.commit()


def get_thesis(db: Session, thesis_id: str, user_id: str) -> Thesis | None:
    """One thesis, ONLY if this user owns it.

    ⚠️ NOT `db.get(Thesis, thesis_id)`, WHICH IS WHAT THIS USED TO BE. A primary-key
    fetch reads as complete — it returns the right row, the endpoint 404s when it is
    missing, every test passes — and it hands any thesis to anyone holding a uuid.

    None for "not yours" and None for "does not exist" is deliberate, and it is what
    lets callers turn both into a 404: a 403 would confirm the row is real, which
    tells an attacker their guessed id was a hit.
    """
    return (
        db.query(Thesis)
        .filter(Thesis.id == thesis_id, Thesis.user_id == user_id)
        .first()
    )


def list_theses_for_user(db: Session, user_id: str) -> list[Thesis]:
    return db.query(Thesis).filter(Thesis.user_id == user_id).order_by(Thesis.created_at.desc()).all()


def owned_thesis_ids(db: Session, user_id: str, thesis_ids: list[str]) -> list[str]:
    """The subset of `thesis_ids` this user actually owns.

    The gate for the bulk readers (summarise_for_theses, events_by_claim), which are
    handed a list of ids by their caller and would otherwise aggregate over whatever
    they were given.
    """
    if not thesis_ids:
        return []
    rows = (
        db.query(Thesis.id)
        .filter(Thesis.id.in_(thesis_ids), Thesis.user_id == user_id)
        .all()
    )
    return [row[0] for row in rows]
