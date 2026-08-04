from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.api.dependencies import current_user_id
from backend.api.schemas import PostMortemAnswerRequest, PostMortemOut
from backend.models.database import get_db
from backend.repositories import post_mortem_repository
from backend.services.post_mortem_service import (
    PostMortemError,
    PostMortemNotFound,
    generate_question,
)

router = APIRouter(prefix="/post-mortems", tags=["post-mortems"])


@router.get("", response_model=list[PostMortemOut])
def list_post_mortems(
    pending_only: bool = False,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    return post_mortem_repository.list_post_mortems(
        db, user_id, pending_only=pending_only
    )


@router.post("/{post_mortem_id}/question", response_model=PostMortemOut)
def generate_post_mortem_question(
    post_mortem_id: str,
    force: bool = False,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """Write the reflection question, lazily.

    Called by the frontend when it goes to display a post-mortem, deliberately NOT
    during verification — that keeps the AI call off the critical path of a check.
    Idempotent unless `force`, so re-displaying costs nothing and the wording does not
    shift under the user.
    """
    try:
        return generate_question(db, post_mortem_id, user_id, force=force)
    except PostMortemNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PostMortemError as exc:
        # The post-mortem exists but has no broken claim to ask about — unprocessable,
        # not missing.
        raise HTTPException(status_code=422, detail=str(exc))


@router.patch("/{post_mortem_id}", response_model=PostMortemOut)
def answer_post_mortem(
    post_mortem_id: str,
    body: PostMortemAnswerRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    post_mortem = post_mortem_repository.answer_post_mortem(
        db, post_mortem_id, user_id, body.user_response
    )
    if post_mortem is None:
        raise HTTPException(status_code=404, detail="Post-mortem not found")
    return post_mortem


@router.delete("/{post_mortem_id}", status_code=204)
def delete_post_mortem(
    post_mortem_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """Deletable by design — see the note in post_mortem_repository.delete_post_mortem."""
    if not post_mortem_repository.delete_post_mortem(db, post_mortem_id, user_id):
        raise HTTPException(status_code=404, detail="Post-mortem not found")
    return Response(status_code=204)
