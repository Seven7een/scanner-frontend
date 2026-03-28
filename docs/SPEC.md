# SPEC.md — Scanner Frontend

## Purpose
Provide a web interface for triggering and viewing results from the `repo-security-scanner` Docker image. Users can scan GitHub/GitLab accounts for leaked secrets and PII, view findings with severity breakdown, and track scan history.

## Components
1. **FastAPI Backend** — REST API for scan management, serves PWA static files
2. **PostgreSQL** — Stores scan metadata and findings
3. **PWA Frontend** — Single-page app with dark theme, mobile-first design

## API
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serve PWA |
| GET | `/api/v1/health` | Health check (no auth) |
| POST | `/api/v1/scans` | Trigger a new scan |
| GET | `/api/v1/scans` | List scans (paginated) |
| GET | `/api/v1/scans/{id}` | Get scan details |
| GET | `/api/v1/scans/{id}/findings` | Get findings (filterable) |
| DELETE | `/api/v1/scans/{id}` | Delete scan + findings |

## Authentication
- API key via `X-API-Key` header or `?key=` query param
- All `/api/` routes protected except `/api/v1/health`
- Key prompted on first visit, stored in localStorage

## Scan Flow
1. POST creates scan record (status=pending), returns 202
2. Background task runs `docker run repo-security-scanner`
3. Results parsed from `findings.json`, stored in DB
4. Frontend polls for status updates

## Security Considerations
- **Docker socket mount**: The backend container mounts `/var/run/docker.sock` to spawn scanner containers. This grants the container effective root access to the host Docker daemon. Mitigated by:
  - Container runs as non-root where possible
  - Only spawns the specific `repo-security-scanner` image
  - No user-controlled command injection (inputs are passed as env vars, not shell args)
- **API key auth**: Single shared key, not per-user. Acceptable for private deployment.
- **No secrets in code**: All config via environment variables.
- **Scanner output isolation**: Each scan gets its own output directory by UUID.

## Database
Two tables: `scans` (metadata + stats) and `findings` (individual results). CASCADE delete from scan to findings.
