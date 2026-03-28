# CLAUDE.md — Scanner Frontend

## Project Overview
Web frontend for the Repo Security Scanner. FastAPI backend + PWA frontend + PostgreSQL.

## Forge Conventions (MANDATORY)
- **Priority:** Privacy/Security > Functionality > Don't Reinvent > Extensibility > Elegance
- **Never commit:** secrets, API keys, tokens, PII, .env files
- `.internal/` is gitignored scratch space
- Update `docs/STATE.md` before every commit
- gitleaks pre-commit: treat findings as hard blockers

## Key Architecture Decisions
- Backend spawns `docker run repo-security-scanner` via subprocess (needs Docker socket mount)
- Async background tasks via `asyncio.create_task()` — scans don't block requests
- API key auth via middleware (X-API-Key header or ?key= query param)
- SQLAlchemy async with asyncpg for PostgreSQL

## Development
```bash
docker compose up -d --build    # Start everything
docker compose logs -f app      # Watch logs
docker compose down             # Stop
```

## File Structure
- `app/main.py` — FastAPI app, middleware, lifespan
- `app/models.py` — SQLAlchemy models (Scan, Finding)
- `app/database.py` — Async DB connection
- `app/scanner.py` — Docker subprocess wrapper
- `app/routes/scans.py` — Scan CRUD + trigger endpoints
- `app/routes/health.py` — Health check
- `app/static/` — PWA frontend (vanilla JS + Tailwind CDN)
