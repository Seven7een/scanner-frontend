"""Scanner Frontend — FastAPI application."""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.database import engine, Base
from app.routes import health, scans

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("API_KEY", "")
PUBLIC_PATHS = {"/api/v1/health", "/", "/favicon.ico"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured.")
    yield


app = FastAPI(title="Scanner Frontend", version="0.1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# API Key middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """Enforce API key auth on /api/ routes (except health)."""
    path = request.url.path

    if path.startswith("/api/") and path not in PUBLIC_PATHS:
        key = request.headers.get("X-API-Key", "") or request.query_params.get("key", "")
        if not API_KEY:
            logger.warning("API_KEY not set — rejecting authenticated requests")
            return JSONResponse(
                status_code=500,
                content={"detail": "Server misconfigured: API_KEY not set."},
            )
        if key != API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key."},
            )

    response = await call_next(request)
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix="/api/v1")
app.include_router(scans.router, prefix="/api/v1")

# Serve static files (PWA frontend)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    """Serve the PWA index page."""
    return FileResponse("app/static/index.html")
