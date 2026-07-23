from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.alerts import router as alerts_router
from backend.api.theses import router as theses_router
from backend.models.database import init_db, seed_demo_user

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_demo_user()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(theses_router)
app.include_router(alerts_router)


@app.get("/health")
def health():
    return {"status": "ok"}
