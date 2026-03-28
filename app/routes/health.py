"""Health check endpoint."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> JSONResponse:
    """Return service health status."""
    return JSONResponse({"status": "ok"})
