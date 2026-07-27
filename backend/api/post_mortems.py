from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.api.schemas import PostMortemAnswerRequest, PostMortemOut
from backend.models.database import get_db
from backend.repositories import post_mortem_repository

router = APIRouter(prefix="/post-mortems", tags=["post-mortems"])


@router.get("", response_model=list[PostMortemOut])
def list_post_mortems(pending_only: bool = False, db: Session = Depends(get_db)):
    return post_mortem_repository.list_post_mortems(db, pending_only=pending_only)


@router.patch("/{post_mortem_id}", response_model=PostMortemOut)
def answer_post_mortem(
    post_mortem_id: str,
    body: PostMortemAnswerRequest,
    db: Session = Depends(get_db),
):
    post_mortem = post_mortem_repository.answer_post_mortem(
        db, post_mortem_id, body.user_response
    )
    if post_mortem is None:
        raise HTTPException(status_code=404, detail="Post-mortem not found")
    return post_mortem


@router.delete("/{post_mortem_id}", status_code=204)
def delete_post_mortem(post_mortem_id: str, db: Session = Depends(get_db)):
    """Deletable by design — see the note in post_mortem_repository.delete_post_mortem."""
    if not post_mortem_repository.delete_post_mortem(db, post_mortem_id):
        raise HTTPException(status_code=404, detail="Post-mortem not found")
    return Response(status_code=204)
