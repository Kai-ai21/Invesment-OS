from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from backend.api.theses import router as theses_router
from backend.models.database import init_db, seed_demo_user

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_demo_user()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(theses_router)


@app.get("/health")
def health():
    return {"status": "ok"}
