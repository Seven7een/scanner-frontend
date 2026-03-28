"""Docker subprocess wrapper for repo-security-scanner."""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SCANNER_IMAGE = "repo-security-scanner:latest"
SCANNER_TIMEOUT = 3600  # 60 minutes max per scan

# The output dir inside this container vs the host path for docker run -v
# Docker socket mounts are from the HOST perspective, not the container's.
SCANNER_OUTPUT_DIR = "/data/scanner-output"
SCANNER_OUTPUT_HOST_DIR = os.environ.get("SCANNER_OUTPUT_HOST_DIR", SCANNER_OUTPUT_DIR)
SCANNER_CACHE_HOST_DIR = os.environ.get("SCANNER_CACHE_HOST_DIR", "/data/scanner-cache")


async def run_scan(
    scan_id: str,
    github_users: str | None,
    gitlab_users: str | None,
    repo_urls: str | None,
    scan_type: str,
) -> dict:
    """Run the scanner container and return parsed results.

    Args:
        scan_id: UUID string for this scan run.
        github_users: Comma-separated GitHub usernames.
        gitlab_users: Comma-separated GitLab usernames.
        repo_urls: Comma-separated repo URLs.
        scan_type: One of 'gitleaks', 'ai', 'all'.

    Returns:
        Dict with keys: exit_code, findings, repos_scanned, error, duration_seconds.
    """
    output_dir = os.path.join(SCANNER_OUTPUT_DIR, scan_id)
    host_output_dir = os.path.join(SCANNER_OUTPUT_HOST_DIR, scan_id)
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{host_output_dir}:/output",
        "-v", f"{SCANNER_CACHE_HOST_DIR}:/data/repos",
    ]

    if github_users:
        cmd.extend(["-e", f"GITHUB_USERS={github_users}"])
    if gitlab_users:
        cmd.extend(["-e", f"GITLAB_USERS={gitlab_users}"])
    if repo_urls:
        cmd.extend(["-e", f"REPO_URLS={repo_urls}"])

    # Pass AWS credentials for AI scanning (read from this container's env)
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID"):
        val = os.environ.get(var)
        if val:
            cmd.extend(["-e", f"{var}={val}"])

    flag_map = {"gitleaks": "--gitleaks", "ai": "--ai", "all": "--all"}
    flag = flag_map.get(scan_type, "--gitleaks")
    cmd.extend([SCANNER_IMAGE, flag])

    logger.info("Starting scanner: %s", " ".join(cmd))
    start = time.monotonic()

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=SCANNER_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error("Scanner timed out after %ds for scan %s", SCANNER_TIMEOUT, scan_id)
        # Try to kill the container
        try:
            proc.kill()
        except Exception:
            pass
        return {
            "exit_code": 2,
            "findings": [],
            "repos_scanned": 0,
            "error": f"Scanner timed out after {SCANNER_TIMEOUT}s",
            "duration_seconds": time.monotonic() - start,
        }
    except FileNotFoundError:
        logger.error("Docker CLI not found — is Docker installed in the container?")
        return {
            "exit_code": 2,
            "findings": [],
            "repos_scanned": 0,
            "error": "Docker CLI not found in container",
            "duration_seconds": time.monotonic() - start,
        }

    duration = time.monotonic() - start
    exit_code = proc.returncode
    logger.info("Scanner finished: exit_code=%s, duration=%.1fs", exit_code, duration)

    if stderr:
        logger.debug("Scanner stderr: %s", stderr.decode(errors="replace")[:2000])

    # Parse findings.json
    findings = []
    findings_path = os.path.join(output_dir, "findings.json")
    if os.path.exists(findings_path):
        try:
            with open(findings_path, "r") as f:
                raw = json.load(f)
            # Scanner outputs {"metadata": ..., "findings": [...]} or a flat list
            if isinstance(raw, dict):
                findings = raw.get("findings", [])
            elif isinstance(raw, list):
                findings = raw
            logger.info("Parsed %d findings from %s", len(findings), findings_path)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Failed to parse findings.json: %s", e)

    # Count unique repos
    repos = set()
    for finding in findings:
        repo = finding.get("repo") or finding.get("repository", "")
        if repo:
            repos.add(repo)

    error_msg = None
    if exit_code == 2:
        error_msg = stderr.decode(errors="replace")[:1000] if stderr else "Scanner returned error exit code"

    return {
        "exit_code": exit_code,
        "findings": findings,
        "repos_scanned": len(repos),
        "error": error_msg,
        "duration_seconds": duration,
    }


def _safe_int(val) -> int | None:
    """Convert a value to int, returning None if not possible."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def normalize_finding(raw: dict) -> dict:
    """Normalize a raw finding from the scanner into our DB schema fields.

    Args:
        raw: A single finding dict from findings.json.

    Returns:
        Dict matching Finding model fields (minus id, scan_id, created_at).
    """
    # The scanner outputs varying field names — handle both formats
    severity = (raw.get("severity") or "medium").lower()
    if severity not in ("critical", "high", "medium", "low"):
        severity = "medium"

    return {
        "repo": raw.get("repo") or raw.get("repository") or "unknown",
        "tool": raw.get("tool") or raw.get("scanner") or "gitleaks",
        "rule_id": raw.get("rule_id") or raw.get("ruleID") or raw.get("rule"),
        "severity": severity,
        "category": raw.get("category") or (raw["tags"][0] if raw.get("tags") else None),
        "file": raw.get("file") or raw.get("File"),
        "line": _safe_int(raw.get("line") or raw.get("StartLine")),
        "commit_hash": raw.get("commit_hash") or raw.get("commit") or raw.get("Commit"),
        "snippet": raw.get("snippet") or raw.get("Match") or raw.get("Secret"),
        "description": raw.get("description") or raw.get("Description"),
        "recommendation": raw.get("recommendation"),
    }
