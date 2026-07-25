"""Pipeline run management and manifest tracking.

Provides infrastructure for:
- Unique run IDs
- Run manifests with full audit trail
- Atomic cache publication
- Last known good cache preservation
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent / "cache"
RUNS_DIR = CACHE_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


class PipelineRun:
    """Context manager for atomic pipeline runs with full audit trail."""

    def __init__(self, skip_cricsheet: bool = False, dry_run: bool = False):
        self.run_id = str(uuid4())
        self.start_time = datetime.now(UTC)
        self.end_time: datetime | None = None
        self.skip_cricsheet = skip_cricsheet
        self.dry_run = dry_run
        self.success = False
        self.errors: dict[str, Any] = {}
        self.warnings: dict[str, list[str]] = {}
        self.counts: dict[str, int] = {}
        self.output_hashes: dict[str, str] = {}
        self.run_dir = RUNS_DIR / self.run_id

        if not dry_run:
            self.run_dir.mkdir(parents=True, exist_ok=True)

    def __enter__(self) -> PipelineRun:
        logger.info("Starting pipeline run %s", self.run_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.now(UTC)

        if exc_type is not None:
            self.success = False
            self.errors["exception"] = {
                "type": exc_type.__name__ if exc_type else None,
                "message": str(exc_val) if exc_val else None,
            }
            logger.error("Pipeline run %s failed with exception: %s", self.run_id, exc_val)
        else:
            logger.info("Pipeline run %s completed", self.run_id)

        # Save manifest
        if not self.dry_run:
            self.save_manifest()

            # If successful, promote outputs to production cache
            if self.success:
                self.promote_to_production()

        return False  # Don't suppress exceptions

    def write_output(self, key: str, data: Any) -> None:
        """Write output to the run directory.

        Args:
            key: Cache key (e.g., 'todays_matches')
            data: Data to write
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would write %s", key)
            return

        path = self.run_dir / f"{key}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        # Track output hash for integrity verification
        import hashlib

        content = json.dumps(data, sort_keys=True, default=str)
        self.output_hashes[key] = hashlib.sha256(content.encode()).hexdigest()[:16]

        logger.debug("Wrote %s to run directory", key)

    def add_count(self, key: str, value: int) -> None:
        """Record a count metric for this run."""
        self.counts[key] = value

    def add_error(self, category: str, error: dict[str, Any]) -> None:
        """Record an error for this run."""
        if category not in self.errors:
            self.errors[category] = []
        self.errors[category].append(error)

    def add_warning(self, category: str, message: str) -> None:
        """Record a warning for this run."""
        if category not in self.warnings:
            self.warnings[category] = []
        self.warnings[category].append(message)

    def mark_success(self) -> None:
        """Mark this run as successful."""
        self.success = True

    def save_manifest(self) -> None:
        """Save the run manifest with full audit trail."""
        manifest = {
            "run_id": self.run_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": ((self.end_time - self.start_time).total_seconds() if self.end_time else None),
            "success": self.success,
            "skip_cricsheet": self.skip_cricsheet,
            "dry_run": self.dry_run,
            "git_commit": self._get_git_commit(),
            "environment": os.getenv("APP_ENV", "development"),
            "counts": self.counts,
            "errors": self.errors,
            "warnings": self.warnings,
            "output_hashes": self.output_hashes,
        }

        if self.dry_run:
            logger.info("[DRY RUN] Would save manifest: %s", json.dumps(manifest, indent=2, default=str))
            return

        manifest_path = self.run_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, default=str)

        # Also save to cache/run_manifest.json as the latest manifest
        latest_manifest_path = CACHE_DIR / "run_manifest.json"
        with open(latest_manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, default=str)

        logger.info("Saved run manifest for %s", self.run_id)

    def promote_to_production(self) -> None:
        """Atomically promote run outputs to production cache.

        This preserves the last known good cache if promotion fails.
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would promote outputs to production cache")
            return

        # Backup current production cache
        backup_dir = CACHE_DIR / "backup"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Copy current production files to backup
        backed_up_files = []
        for item in CACHE_DIR.iterdir():
            if item.is_file() and item.suffix == ".json":
                shutil.copy2(item, backup_dir / item.name)
                backed_up_files.append(item.name)

        logger.info("Backed up %d production cache files", len(backed_up_files))

        try:
            # Copy run outputs to production cache
            promoted_count = 0
            for output_file in self.run_dir.iterdir():
                if output_file.suffix == ".json" and output_file.name != "manifest.json":
                    if self._should_preserve_existing(output_file):
                        logger.warning("Preserving existing non-empty cache for %s", output_file.name)
                        continue
                    dest = CACHE_DIR / output_file.name
                    shutil.copy2(output_file, dest)
                    promoted_count += 1

            logger.info("Promoted %d outputs to production cache", promoted_count)

        except Exception as e:
            logger.error("Failed to promote outputs, restoring backup: %s", e)
            # Restore backup
            for backup_file in backup_dir.iterdir():
                if backup_file.is_file():
                    shutil.copy2(backup_file, CACHE_DIR / backup_file.name)
            raise

    @staticmethod
    def _should_preserve_existing(output_file: Path) -> bool:
        """Reject empty prediction outputs when a usable production cache exists."""
        if output_file.name not in {"todays_matches.json", "player_props.json", "value_bets.json"}:
            return False
        try:
            with open(output_file) as f:
                candidate = json.load(f)
            candidate_data = candidate.get("data") if isinstance(candidate, dict) and "data" in candidate else candidate
            if candidate_data:
                return False

            existing_path = CACHE_DIR / output_file.name
            if not existing_path.exists():
                return False
            with open(existing_path) as f:
                existing = json.load(f)
            existing_data = existing.get("data") if isinstance(existing, dict) and "data" in existing else existing
            return bool(existing_data)
        except (OSError, TypeError, ValueError):
            return False

    def validate_outputs(self, required_keys: list[str]) -> bool:
        """Validate that required outputs exist and are non-empty.

        Args:
            required_keys: List of cache keys that must be present

        Returns:
            True if all required outputs exist and are valid
        """
        for key in required_keys:
            path = self.run_dir / f"{key}.json"
            if not path.exists():
                self.add_error("validation", {"key": key, "error": "Missing output file"})
                return False

            try:
                with open(path) as f:
                    data = json.load(f)

                # Check if it's wrapped with metadata
                if isinstance(data, dict) and "data" in data:
                    actual_data = data["data"]
                else:
                    actual_data = data

                # Check for non-empty data
                if actual_data is None or (isinstance(actual_data, (list, dict)) and len(actual_data) == 0):
                    self.add_warning("validation", f"{key} is empty")

            except Exception as e:
                self.add_error("validation", {"key": key, "error": str(e)})
                return False

        return True

    @staticmethod
    def _get_git_commit() -> str | None:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None


def get_last_successful_run() -> dict[str, Any] | None:
    """Get the manifest of the last successful run.

    Returns:
        Manifest dict if found, None otherwise
    """
    manifest_path = CACHE_DIR / "run_manifest.json"
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path) as f:
            manifest = json.load(f)

        if manifest.get("success"):
            return manifest
    except Exception:
        pass

    return None


def get_run_history(limit: int = 10) -> list[dict[str, Any]]:
    """Get recent run manifests.

    Args:
        limit: Maximum number of runs to return

    Returns:
        List of manifest dicts, newest first
    """
    manifests = []

    for run_dir in sorted(RUNS_DIR.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue

        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue

        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            manifests.append(manifest)

            if len(manifests) >= limit:
                break
        except Exception:
            continue

    return manifests
