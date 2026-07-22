import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models.base import Base
from models.claim import Claim  # noqa: F401 (registers mapper with Base)
from models.thesis import Thesis  # noqa: F401 (registers mapper with Base)
from models.user import User

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "investment_os.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def seed_demo_user() -> None:
    with SessionLocal() as db:
        if not db.query(User).first():
            db.add(User(email="demo@local"))
            db.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
