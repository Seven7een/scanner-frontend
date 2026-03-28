FROM python:3.12-slim

WORKDIR /app

# Install Docker CLI (official static binary — no daemon, just the CLI)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz | \
    tar xz --strip-components=1 -C /usr/local/bin docker/docker && \
    apt-get purge -y curl && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create output directory
RUN mkdir -p /data/scanner-output

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
