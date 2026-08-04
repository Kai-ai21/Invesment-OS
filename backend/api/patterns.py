from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.api.schemas import PatternGenerateOut, PatternOut, PatternSourceOut
from backend.models.database import get_db
from backend.models.user import User
from backend.models.pattern import Pattern
from backend.repositories import pattern_repository, post_mortem_repository
from backend.services.pattern_service import MINIMUM_POST_MORTEMS, generate_patterns

router = APIRouter(prefix="/patterns", tags=["patterns"])


def _to_out(db: Session, patterns: list[Pattern], user_id: str) -> list[PatternOut]:
    """Resolve cited post-mortem ids to tickers and questions.

    Looked up once for the whole set rather than per pattern, since patterns overlap in
    the reflections they cite. A cited post-mortem the user has since DELETED simply
    drops out of `sources` — the pattern is still shown, with one fewer citation, rather
    than the endpoint failing over a row that was theirs to remove.
    """
    by_id = {
        item.id: item
        for item in post_mortem_repository.list_post_mortems(db, user_id)
    }

    resolved: list[PatternOut] = []
    for pattern in patterns:
        sources = [
            PatternSourceOut(
                post_mortem_id=item.id,
                ticker=item.ticker,
                prompt_question=item.prompt_question,
            )
            for post_mortem_id in pattern.evidence_post_mortem_ids
            if (item := by_id.get(post_mortem_id)) is not None
        ]
        resolved.append(
            PatternOut(
                id=pattern.id,
                statement=pattern.statement,
                sources=sources,
                generated_at=pattern.generated_at,
                dismissed=pattern.dismissed,
            )
        )
    return resolved


@router.get("", response_model=list[PatternOut])
def list_patterns(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return _to_out(db, pattern_repository.list_patterns(db, user.id), user.id)


@router.post("/generate", response_model=PatternGenerateOut)
def regenerate_patterns(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Rebuild the pattern set. Replaces the previous one.

    Having too few reflections is a normal state, not a failure — it returns 200 with an
    empty list and a reason, so the UI can explain rather than show an error.
    """
    patterns = generate_patterns(db, user.id)
    if patterns:
        return PatternGenerateOut(patterns=_to_out(db, patterns, user.id))

    answered = post_mortem_repository.count_answered(db, user.id)
    if answered < MINIMUM_POST_MORTEMS:
        reason = (
            f"Not enough reflections yet — {answered} of {MINIMUM_POST_MORTEMS} "
            "answered. Patterns need enough material to be real."
        )
    else:
        reason = "No recurring behaviour found across your reflections."
    return PatternGenerateOut(patterns=[], reason=reason)


@router.patch("/{pattern_id}/dismiss", response_model=PatternOut)
def dismiss_pattern(
    pattern_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pattern = pattern_repository.dismiss_pattern(db, pattern_id, user.id)
    if pattern is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return _to_out(db, [pattern], user.id)[0]
