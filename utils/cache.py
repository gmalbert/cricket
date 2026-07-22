import json
import os
from datetime import datetime
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

CACHE_FILES = {
    "todays_matches":      "todays_matches.json",
    "player_props":        "player_props.json",
    "schedule":            "schedule.json",
    "team_form":           "team_form.json",
    "venue_stats":         "venue_stats.json",
    "player_stats":        "player_stats.json",
    "value_bets":          "value_bets.json",
    "playoff_probabilities": "playoff_probabilities.json",
    "matchup_edge_history": "matchup_edge_history.json",
    "rivalries":           "rivalries.json",
    "match_hubs":          "match_hubs.json",
    "shot_locations":      "shot_locations.json",
    "prediction_log":      "prediction_log.json",
    "last_updated":        "last_updated.json",
}


def cache_path(key: str) -> Path:
    filename = CACHE_FILES.get(key, f"{key}.json")
    return CACHE_DIR / filename


def cache_exists(key: str) -> bool:
    return cache_path(key).exists()


def load_cache(key: str):
    path = cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def save_cache(key: str, data) -> None:
    path = cache_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


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
