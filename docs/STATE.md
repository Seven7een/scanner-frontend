# STATE.md — Scanner Frontend

## Current Status: MVP Complete (reviewed)

### Done
- [x] Project scaffolding (Forge conventions, .gitignore, .gitleaks.toml)
- [x] Docker Compose setup (app + PostgreSQL)
- [x] Dockerfile with Docker CLI for subprocess scanning
- [x] FastAPI backend with async lifespan
- [x] SQLAlchemy models (Scan, Finding) with async PostgreSQL
- [x] API key middleware (header + query param, JSONResponse for failures)
- [x] Scan CRUD endpoints (create, list, get, delete)
- [x] Findings endpoint with severity/repo/tool filters
- [x] Background scan execution via asyncio.create_task
- [x] Docker subprocess wrapper with timeout handling
- [x] findings.json parser with field normalization
- [x] PWA frontend: auth gate, new scan form, progress polling
- [x] PWA frontend: scan history view with severity badges
- [x] PWA frontend: findings drill-down with expandable details
- [x] PWA frontend: dark theme, mobile-first, Tailwind CSS
- [x] Service worker for offline shell caching
- [x] Web manifest for PWA install
- [x] **DinD volume mount fix** — host path for scanner output (Docker socket mounts are host-relative)

### Blocked / Future
- [ ] Generate mkcert certs (requires mkcert on host)
- [ ] Integration test with live scanner container
- [ ] Per-user auth (currently single shared API key)
- [ ] Scan scheduling / recurring scans
- [ ] Repo URL scanning (manual repos, not just by username)
- [ ] Export findings as CSV/PDF
- [ ] Webhook notifications on scan completion
