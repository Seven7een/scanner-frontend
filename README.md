# Scanner Frontend

Web UI for the Repo Security Scanner. Trigger scans, view findings, track history.

## Quick Start

```bash
# Generate certs
mkdir -p certs && cd certs
mkcert -key-file local-key.pem -cert-file local-cert.pem localhost 127.0.0.1
cd ..

# Configure
cp .env.example .env
# Edit .env with real values

# Run
docker compose up -d --build
```

Open `https://localhost:8445`

## Architecture

FastAPI backend + vanilla JS PWA + PostgreSQL. The backend spawns `docker run repo-security-scanner` containers to perform scans, parses results, and stores them in the database.

See `docs/SPEC.md` for full details.
