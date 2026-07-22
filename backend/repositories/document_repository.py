from sqlalchemy.orm import Session

from backend.models.document import Document


def create_document(
    db: Session, *, source_type: str, title: str | None, content_hash: str, raw_text: str
) -> Document:
    document = Document(
        source_type=source_type, title=title, content_hash=content_hash, raw_text=raw_text
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_document_by_hash(db: Session, content_hash: str) -> Document | None:
    return db.query(Document).filter(Document.content_hash == content_hash).first()
