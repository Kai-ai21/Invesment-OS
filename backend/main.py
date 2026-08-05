import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.alerts import router as alerts_router
from backend.api.auth import router as auth_router
from backend.api.filings import router as filings_router
from backend.api.holdings import router as holdings_router
from backend.api.market import router as market_router
from backend.api.news import router as news_router
from backend.api.patterns import router as patterns_router
from backend.api.prices import router as prices_router
from backend.api.research import router as research_router
from backend.api.post_mortems import router as post_mortems_router
from backend.api.theses import router as theses_router
from backend.api.tickers import router as tickers_router
from backend.models.database import init_db

load_dotenv()

# The Vite dev server, on both spellings of localhost. This is the whole list for
# local development, and it stays the default so that running the app from a fresh
# clone needs no configuration at all — same behaviour it had when it was hardcoded.
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def cors_origins() -> list[str]:
    """The browser origins allowed to call this API, from CORS_ORIGINS.

    Comma-separated, because that is what fits in an environment variable and every
    host's config UI. Whitespace around entries is ignored, so the value can be
    written with spaces after the commas without silently allowing nothing.

    ⚠️ A TRAILING SLASH IS STRIPPED, because it can only ever be a mistake. An
    `Origin` header is scheme + host + port and NEVER carries a path or a trailing
    slash, and Starlette compares it to this list by exact string equality — so
    "https://app.example.com/" matches nothing, and the symptom is every request
    failing CORS with a list that looks correct to read.

    ⚠️ "*" IS REFUSED, AND THAT IS NOT AN OVERSIGHT. It looks like the obvious way to
    open this up in a hurry, and combined with allow_credentials=True below it does
    something worse than what it says: Starlette does not send a literal "*" in that
    case, it ECHOES BACK the requesting origin (starlette/middleware/cors.py — `if
    self.allow_all_origins and self.allow_credentials`). That is the reflected-origin
    misconfiguration, and it makes every origin on the internet an allowed one.

    It is survivable TODAY only by accident: this app authenticates with a Bearer
    token from localStorage rather than a cookie, so a hostile page has no ambient
    credential to spend and gets a 401. The moment the token moves to a cookie —
    which frontend/src/lib/authToken.ts explicitly contemplates for a public
    deployment — the same setting becomes full account access from any website. A
    startup failure now is much cheaper than that discovery later, and matches how
    JWT_SECRET is already handled in backend/core/security.py: refuse to start rather
    than run in a state nobody would have chosen deliberately.
    """
    raw = (os.getenv("CORS_ORIGINS") or "").strip() or DEFAULT_CORS_ORIGINS
    origins = [origin.strip().rstrip("/") for origin in raw.split(",")]
    origins = [origin for origin in origins if origin]

    if not origins:
        raise RuntimeError(
            "CORS_ORIGINS is set but lists no origins. Either remove it to use the "
            f"local-development default ({DEFAULT_CORS_ORIGINS}), or give it a "
            "comma-separated list such as 'https://app.example.com'."
        )

    if "*" in origins:
        raise RuntimeError(
            "CORS_ORIGINS must not be '*'. This API sends credentials, and Starlette "
            "answers a wildcard by reflecting the caller's own origin back — which "
            "allows every site on the internet rather than opening a public read-only "
            "API. List the origins that should be allowed instead, comma-separated."
        )

    return origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(theses_router)
app.include_router(alerts_router)
app.include_router(news_router)
app.include_router(post_mortems_router)
app.include_router(patterns_router)
app.include_router(prices_router)
app.include_router(holdings_router)
app.include_router(market_router)
app.include_router(research_router)
app.include_router(filings_router)
app.include_router(tickers_router)


@app.get("/health")
def health():
    return {"status": "ok"}
