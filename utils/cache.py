import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# Environment mode: development allows mock data, production does not
APP_ENV = os.getenv("APP_ENV", "development")

CACHE_FILES = {
    "todays_matches": "todays_matches.json",
    "player_props": "player_props.json",
    "schedule": "schedule.json",
    "points_table": "points_table.json",
    "team_form": "team_form.json",
    "venue_stats": "venue_stats.json",
    "player_stats": "player_stats.json",
    "value_bets": "value_bets.json",
    "playoff_probabilities": "playoff_probabilities.json",
    "matchup_edge_history": "matchup_edge_history.json",
    "rivalries": "rivalries.json",
    "match_hubs": "match_hubs.json",
    "shot_locations": "shot_locations.json",
    "prediction_log": "prediction_log.json",
    "last_updated": "last_updated.json",
    "competition_status": "competition_status.json",
    "odds_history": "odds_history.json",
    "run_manifest": "run_manifest.json",
}


def cache_path(key: str) -> Path:
    filename = CACHE_FILES.get(key, f"{key}.json")
    return CACHE_DIR / filename


def cache_exists(key: str) -> bool:
    return cache_path(key).exists()


def load_cache(key: str):
    """Load data from cache.

    Returns the raw data. If data was saved with metadata wrapper,
    returns the entire wrapper (caller can extract 'data' field if needed).
    """
    path = cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def load_cache_data_only(key: str):
    """Load data from cache, unwrapping metadata if present.

    Returns only the 'data' field if metadata wrapper exists,
    otherwise returns the entire content.
    """
    content = load_cache(key)
    if content is None:
        return None

    # If it has metadata wrapper structure, extract data
    if isinstance(content, dict) and "data" in content and "generated_at" in content:
        return content["data"]

    return content


def load_backup_cache_data_only(key: str):
    """Load the last promoted non-empty cache preserved by the pipeline."""
    backup_path = CACHE_DIR / "backup" / CACHE_FILES.get(key, f"{key}.json")
    if not backup_path.exists():
        return None
    try:
        with open(backup_path) as f:
            content = json.load(f)
    except Exception:
        return None
    if isinstance(content, dict) and "data" in content and "generated_at" in content:
        return content["data"]
    return content


def get_cache_metadata(key: str) -> dict[str, Any] | None:
    """Extract metadata from cache file if present.

    Returns:
        Metadata dict if present, None otherwise
    """
    content = load_cache(key)
    if content is None:
        return None

    # If it has metadata structure
    if isinstance(content, dict) and "generated_at" in content and "data" in content:
        metadata = {k: v for k, v in content.items() if k != "data"}
        return metadata

    return None


def is_cache_stale(key: str, max_age_hours: float = 24) -> bool:
    """Check if cache is stale based on age.

    Args:
        key: Cache key
        max_age_hours: Maximum age in hours before considering stale

    Returns:
        True if cache is stale or missing, False if fresh
    """
    metadata = get_cache_metadata(key)
    if metadata and "generated_at" in metadata:
        try:
            gen_time = datetime.fromisoformat(metadata["generated_at"].replace("Z", "+00:00"))
            age_hours = (datetime.now(UTC) - gen_time).total_seconds() / 3600
            return age_hours > max_age_hours
        except (ValueError, AttributeError):
            pass

    # Fallback to file mtime
    path = cache_path(key)
    if not path.exists():
        return True

    age = (datetime.now().timestamp() - path.stat().st_mtime) / 3600
    return age > max_age_hours


def is_mock_data(key: str) -> bool:
    """Check if cached data is marked as mock/simulated.

    Returns:
        True if data is mock, False otherwise
    """
    metadata = get_cache_metadata(key)
    if metadata:
        return metadata.get("is_mock", False)
    return False


def save_cache(key: str, data, metadata: dict[str, Any] | None = None) -> None:
    """Save data to cache with optional metadata.

    Args:
        key: Cache key from CACHE_FILES
        data: Data to save (will be JSON serialized)
        metadata: Optional metadata dict with generated_at, source_run_id, etc.
    """
    path = cache_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Wrap data with metadata if provided
    if metadata:
        output = {
            **metadata,
            "data": data,
        }
    else:
        output = data

    with open(path, "w") as f:
        json.dump(output, f, indent=2, default=str)


def save_cache_with_metadata(
    key: str,
    data,
    source_run_id: str | None = None,
    source_status: str = "unknown",
    is_mock: bool = False,
) -> None:
    """Save cache with standardized metadata.

    Args:
        key: Cache key from CACHE_FILES
        data: Data to save
        source_run_id: Unique identifier of the pipeline run that generated this data
        source_status: Status of the source (e.g., 'ready', 'stale', 'mock')
        is_mock: Whether this is simulated/mock data
    """
    metadata = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_run_id": source_run_id,
        "source_status": source_status,
        "schema_version": 1,
        "is_mock": is_mock,
        "app_env": APP_ENV,
    }
    save_cache(key, data, metadata)


def get_last_updated() -> str | None:
    data = load_cache("last_updated")
    if data:
        return data.get("timestamp")
    return None


def set_last_updated() -> None:
    save_cache("last_updated", {"timestamp": datetime.utcnow().isoformat() + "Z"})


def cache_status() -> dict:
    status = {}
    for key in CACHE_FILES:
        path = cache_path(key)
        if path.exists():
            mtime = datetime.utcfromtimestamp(path.stat().st_mtime)
            status[key] = mtime.strftime("%Y-%m-%d %H:%M UTC")
        else:
            status[key] = None
    return status
