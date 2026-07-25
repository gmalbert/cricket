#!/usr/bin/env python3
"""
Health monitoring script for Wicket Oracle.

Run this script periodically to check system health and alert on issues.
Exit codes: 0 = healthy, 1 = warning, 2 = critical
"""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.cache import APP_ENV, get_cache_metadata, is_cache_stale, is_mock_data
from utils.data import get_competition_status


class HealthStatus:
    """Health status levels."""

    OK = 0
    WARNING = 1
    CRITICAL = 2


def check_environment() -> tuple[HealthStatus, str]:
    """Check APP_ENV is set correctly."""
    if APP_ENV not in ("production", "development", "test"):
        return HealthStatus.CRITICAL, f"Invalid APP_ENV: {APP_ENV}"

    if APP_ENV == "development":
        return HealthStatus.WARNING, "Running in development mode"

    return HealthStatus.OK, f"Environment: {APP_ENV}"


def check_cache_freshness(max_age_hours: int = 24) -> tuple[HealthStatus, str]:
    """Check cache is fresh enough."""
    metadata = get_cache_metadata("last_updated")

    if not metadata:
        return HealthStatus.CRITICAL, "No cache data found (never run)"

    is_stale = is_cache_stale("last_updated", max_age_hours=max_age_hours)
    generated_at = metadata.get("generated_at", "Unknown")

    if is_stale:
        return HealthStatus.CRITICAL, f"Cache is stale (last updated: {generated_at})"

    # Warning if approaching stale threshold (> 18 hours)
    if is_cache_stale("last_updated", max_age_hours=18):
        return HealthStatus.WARNING, f"Cache aging (last updated: {generated_at})"

    return HealthStatus.OK, f"Cache is fresh (last updated: {generated_at})"


def check_mock_data() -> tuple[HealthStatus, str]:
    """Check for mock data in production."""
    if APP_ENV == "production" and is_mock_data("todays_matches"):
        return HealthStatus.CRITICAL, "Mock data detected in production mode!"

    if is_mock_data("todays_matches"):
        return HealthStatus.WARNING, "Using mock data (development mode)"

    return HealthStatus.OK, "Using production data"


def check_competition_status() -> tuple[HealthStatus, str]:
    """Check competition readiness status."""
    status_data = get_competition_status()
    competitions = status_data.get("competitions", {})

    if not competitions:
        return HealthStatus.WARNING, "No competition data available"

    ready_count = sum(1 for comp in competitions.values() if comp.get("status") == "ready")
    total_count = len(competitions)

    if ready_count == 0:
        # This is OK if off-season
        return HealthStatus.WARNING, f"No competitions ready (0/{total_count})"

    return HealthStatus.OK, f"Competitions ready: {ready_count}/{total_count}"


def check_required_cache_files() -> tuple[HealthStatus, str]:
    """Check required cache files exist."""
    cache_dir = Path("cache")
    required_files = [
        "todays_matches.json",
        "value_bets.json",
        "competition_status.json",
        "last_updated.json",
    ]

    missing = [f for f in required_files if not (cache_dir / f).exists()]

    if missing:
        return HealthStatus.CRITICAL, f"Missing cache files: {', '.join(missing)}"

    return HealthStatus.OK, f"All required cache files present ({len(required_files)} files)"


def check_pipeline_errors() -> tuple[HealthStatus, str]:
    """Check for errors in latest pipeline run."""
    runs_dir = Path("cache/runs")

    if not runs_dir.exists():
        return HealthStatus.WARNING, "No pipeline runs found"

    # Find latest run
    run_dirs = sorted(runs_dir.glob("*"), key=os.path.getmtime, reverse=True)

    if not run_dirs:
        return HealthStatus.WARNING, "No pipeline runs found"

    latest_run = run_dirs[0]
    manifest_file = latest_run / "manifest.json"

    if not manifest_file.exists():
        return HealthStatus.WARNING, f"No manifest in latest run: {latest_run.name}"

    with open(manifest_file) as f:
        manifest = json.load(f)

    errors = manifest.get("errors", {})
    warnings = manifest.get("warnings", {})

    if errors:
        error_summary = ", ".join(f"{k}: {v}" for k, v in list(errors.items())[:3])
        return HealthStatus.CRITICAL, f"Pipeline errors: {error_summary}"

    if warnings:
        warning_summary = ", ".join(f"{k}: {v}" for k, v in list(warnings.items())[:3])
        return HealthStatus.WARNING, f"Pipeline warnings: {warning_summary}"

    return HealthStatus.OK, f"Latest pipeline run successful (run: {latest_run.name[:8]})"


def check_api_keys() -> tuple[HealthStatus, str]:
    """Check API keys are configured."""
    odds_key = os.getenv("ODDS_API_KEY")
    cricket_key = os.getenv("CRICKET_DATA_API_KEY")

    if not odds_key and not cricket_key:
        return HealthStatus.CRITICAL, "No API keys configured"

    if not odds_key:
        return HealthStatus.WARNING, "ODDS_API_KEY not set"

    if not cricket_key:
        return HealthStatus.WARNING, "CRICKET_DATA_API_KEY not set"

    return HealthStatus.OK, "API keys configured"


def main():
    """Run all health checks and report status."""
    print("=" * 60)
    print("Wicket Oracle Health Check")
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print("=" * 60)

    checks = [
        ("Environment", check_environment),
        ("Cache Freshness", check_cache_freshness),
        ("Mock Data", check_mock_data),
        ("Competition Status", check_competition_status),
        ("Required Cache Files", check_required_cache_files),
        ("Pipeline Errors", check_pipeline_errors),
        ("API Keys", check_api_keys),
    ]

    overall_status = HealthStatus.OK
    results = []

    for name, check_func in checks:
        try:
            status, message = check_func()
            results.append((name, status, message))

            # Track worst status
            if status > overall_status:
                overall_status = status

        except Exception as e:
            results.append((name, HealthStatus.CRITICAL, f"Check failed: {str(e)}"))
            overall_status = HealthStatus.CRITICAL

    # Print results
    status_icons = {
        HealthStatus.OK: "✅",
        HealthStatus.WARNING: "⚠️",
        HealthStatus.CRITICAL: "❌",
    }

    for name, status, message in results:
        icon = status_icons[status]
        print(f"{icon} {name}: {message}")

    print("=" * 60)

    if overall_status == HealthStatus.OK:
        print("✅ Overall Status: HEALTHY")
    elif overall_status == HealthStatus.WARNING:
        print("⚠️ Overall Status: WARNING - Review issues above")
    else:
        print("❌ Overall Status: CRITICAL - Immediate attention required")

    print("=" * 60)

    # Exit with status code
    sys.exit(overall_status)


if __name__ == "__main__":
    main()
