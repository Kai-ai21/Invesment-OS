from sqlalchemy.orm import Session

from models.user import User


def get_demo_user(db: Session) -> User:
    user = db.query(User).filter(User.email == "demo@local").first()
    if user is None:
        raise RuntimeError("Demo user not seeded")
    return user
