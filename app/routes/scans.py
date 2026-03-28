"""Scan management endpoints."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Scan, Finding
from app.scanner import run_scan, normalize_finding

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scans"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class ScanRequest(BaseModel):
    """Request body for triggering a new scan."""
    github_users: str = ""
    gitlab_users: str = ""
    repo_urls: str = ""
    scan_type: str = "gitleaks"


class ScanSummary(BaseModel):
    """Scan summary for list responses."""
    id: str
    status: str
    scan_type: str
    github_users: str | None
    gitlab_users: str | None
    repos_scanned: int | None
    total_findings: int | None
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    duration_seconds: float | None
    error_message: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Background scan task
# ---------------------------------------------------------------------------
async def _execute_scan(scan_id: uuid.UUID, github_users: str, gitlab_users: str, repo_urls: str, scan_type: str) -> None:
    """Background task: run scanner, parse results, update DB."""
    from app.database import async_session

    async with async_session() as db:
        # Mark as running
        scan = await db.get(Scan, scan_id)
        if not scan:
            logger.error("Scan %s not found in DB", scan_id)
            return

        scan.status = "running"
        scan.started_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            result = await run_scan(
                scan_id=str(scan_id),
                github_users=github_users or None,
                gitlab_users=gitlab_users or None,
                repo_urls=repo_urls or None,
                scan_type=scan_type,
            )

            # Store findings
            severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            for raw_finding in result["findings"]:
                normalized = normalize_finding(raw_finding)
                severity_counts[normalized["severity"]] = severity_counts.get(normalized["severity"], 0) + 1
                finding = Finding(scan_id=scan_id, **normalized)
                db.add(finding)

            # Update scan record
            scan.status = "completed" if result["exit_code"] != 2 else "failed"
            scan.repos_scanned = result["repos_scanned"]
            scan.total_findings = len(result["findings"])
            scan.critical_count = severity_counts["critical"]
            scan.high_count = severity_counts["high"]
            scan.medium_count = severity_counts["medium"]
            scan.low_count = severity_counts["low"]
            scan.duration_seconds = result["duration_seconds"]
            scan.error_message = result["error"]
            scan.completed_at = datetime.now(timezone.utc)

            await db.commit()
            logger.info("Scan %s completed: %d findings", scan_id, len(result["findings"]))

        except Exception as e:
            logger.exception("Scan %s failed: %s", scan_id, e)
            scan.status = "failed"
            scan.error_message = str(e)[:1000]
            scan.completed_at = datetime.now(timezone.utc)
            await db.commit()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
def _scan_to_dict(scan: Scan) -> dict:
    """Convert a Scan ORM object to a response dict."""
    return {
        "id": str(scan.id),
        "status": scan.status,
        "scan_type": scan.scan_type,
        "github_users": scan.github_users,
        "gitlab_users": scan.gitlab_users,
        "repo_urls": scan.repo_urls,
        "repos_scanned": scan.repos_scanned,
        "total_findings": scan.total_findings,
        "critical_count": scan.critical_count,
        "high_count": scan.high_count,
        "medium_count": scan.medium_count,
        "low_count": scan.low_count,
        "duration_seconds": scan.duration_seconds,
        "error_message": scan.error_message,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
    }


def _finding_to_dict(f: Finding) -> dict:
    """Convert a Finding ORM object to a response dict."""
    return {
        "id": str(f.id),
        "scan_id": str(f.scan_id),
        "repo": f.repo,
        "tool": f.tool,
        "rule_id": f.rule_id,
        "severity": f.severity,
        "category": f.category,
        "file": f.file,
        "line": f.line,
        "commit_hash": f.commit_hash,
        "snippet": f.snippet,
        "description": f.description,
        "recommendation": f.recommendation,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


@router.post("/scans", status_code=202)
async def create_scan(body: ScanRequest, db: AsyncSession = Depends(get_db)):
    """Trigger a new security scan."""
    if body.scan_type not in ("gitleaks", "ai", "all"):
        return JSONResponse(status_code=400, content={"detail": "scan_type must be gitleaks, ai, or all"})

    if not body.github_users.strip() and not body.gitlab_users.strip() and not body.repo_urls.strip():
        return JSONResponse(status_code=400, content={"detail": "Provide at least one GitHub/GitLab username or repo URL"})

    scan = Scan(
        status="pending",
        scan_type=body.scan_type,
        github_users=body.github_users.strip() or None,
        gitlab_users=body.gitlab_users.strip() or None,
        repo_urls=body.repo_urls.strip() or None,
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    # Spawn background task
    asyncio.create_task(
        _execute_scan(scan.id, body.github_users.strip(), body.gitlab_users.strip(), body.repo_urls.strip(), body.scan_type)
    )

    return JSONResponse(status_code=202, content={"id": str(scan.id), "status": "pending"})


@router.get("/scans")
async def list_scans(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all scans, newest first."""
    result = await db.execute(
        select(Scan).order_by(Scan.created_at.desc()).offset(offset).limit(limit)
    )
    scans = result.scalars().all()

    count_result = await db.execute(select(func.count(Scan.id)))
    total = count_result.scalar()

    return JSONResponse({
        "scans": [_scan_to_dict(s) for s in scans],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: str, db: AsyncSession = Depends(get_db)):
    """Get scan details by ID."""
    try:
        uid = uuid.UUID(scan_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Invalid scan ID"})

    scan = await db.get(Scan, uid)
    if not scan:
        return JSONResponse(status_code=404, content={"detail": "Scan not found"})

    return JSONResponse(_scan_to_dict(scan))


@router.get("/scans/{scan_id}/findings")
async def get_findings(
    scan_id: str,
    severity: Optional[str] = Query(default=None),
    repo: Optional[str] = Query(default=None),
    tool: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get findings for a scan, with optional filters."""
    try:
        uid = uuid.UUID(scan_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Invalid scan ID"})

    query = select(Finding).where(Finding.scan_id == uid)

    if severity:
        query = query.where(Finding.severity == severity.lower())
    if repo:
        query = query.where(Finding.repo == repo)
    if tool:
        query = query.where(Finding.tool == tool)

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    findings = result.scalars().all()

    count_query = select(func.count(Finding.id)).where(Finding.scan_id == uid)
    if severity:
        count_query = count_query.where(Finding.severity == severity.lower())
    if repo:
        count_query = count_query.where(Finding.repo == repo)
    if tool:
        count_query = count_query.where(Finding.tool == tool)

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return JSONResponse({
        "findings": [_finding_to_dict(f) for f in findings],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a scan and all its findings."""
    try:
        uid = uuid.UUID(scan_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Invalid scan ID"})

    scan = await db.get(Scan, uid)
    if not scan:
        return JSONResponse(status_code=404, content={"detail": "Scan not found"})

    await db.delete(scan)
    await db.commit()

    return JSONResponse({"detail": "Scan deleted"})
