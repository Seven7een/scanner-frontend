# WORKFLOW.md — Scanner Frontend

## Prerequisites
- Docker + Docker Compose
- mkcert (for local HTTPS certs)

## Setup

```bash
# 1. Generate TLS certs
mkdir -p certs && cd certs
mkcert -key-file local-key.pem -cert-file local-cert.pem localhost 127.0.0.1
cd ..

# 2. Configure environment
cp .env.example .env
# Edit .env: set DB_USER, DB_PASS, DB_NAME, API_KEY

# 3. Build and start
docker compose up -d --build

# 4. Verify
curl -k https://localhost:8445/api/v1/health
```

## Development

```bash
# Rebuild after code changes
docker compose up -d --build

# Watch logs
docker compose logs -f app

# Database shell
docker exec -it scanner_frontend_db psql -U $DB_USER -d $DB_NAME

# Stop everything
docker compose down

# Stop and remove volumes (destructive!)
docker compose down -v
```

## Testing

```bash
# Health check
curl -k https://localhost:8445/api/v1/health

# Trigger a scan
curl -k -X POST https://localhost:8445/api/v1/scans \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"github_users": "testuser", "scan_type": "gitleaks"}'

# List scans
curl -k https://localhost:8445/api/v1/scans -H "X-API-Key: YOUR_KEY"
```

## Deployment Notes
- The app container needs Docker socket access (`/var/run/docker.sock`)
- The `repo-security-scanner:latest` image must be available on the host
- Port 8445 (configurable via APP_PORT env var)
