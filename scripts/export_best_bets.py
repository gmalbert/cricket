"""
Export daily best bets for the Sports Picks Grid aggregator.

Reads cache/value_bets.json and cache/todays_matches.json and writes
data_files/best_bets_today.json in the unified schema.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
VALUE_BETS_PATH = CACHE_DIR / "value_bets.json"
TODAYS_MATCHES_PATH = CACHE_DIR / "todays_matches.json"
OUT_PATH = ROOT / "data_files" / "best_bets_today.json"

TIER_MAP = {
    "Elite Pick": "Elite",
    "Elite": "Elite",
    "Strong": "Strong",
    "Good": "Good",
}


# Convert DK string odds like "-115" or "+130" to int
def _parse_odds(dk_odds: str | int | None) -> int | None:
    if dk_odds is None:
        return None
    try:
        return int(dk_odds)
    except (ValueError, TypeError):
        return None


def _edge_to_decimal(edge: float | None) -> float | None:
    """edge is already 0–1 in cache (e.g. 0.2573 = 25.73%)"""
    return edge


def _records(payload: object, source: Path) -> list[dict]:
    """Return records from either a legacy list or the pipeline cache envelope."""
    if isinstance(payload, dict):
        payload = payload.get("data", [])
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise TypeError(f"{source} must contain a list or an object with a list-valued 'data' field")
    return payload


def load_value_bets() -> tuple[list[dict], str | None]:
    if not VALUE_BETS_PATH.exists():
        print(f"[cricket export] {VALUE_BETS_PATH} not found — writing empty output")
        return [], None
    with open(VALUE_BETS_PATH, encoding="utf-8") as f:
        payload = json.load(f)
    source_run_id = payload.get("source_run_id") if isinstance(payload, dict) else None
    return _records(payload, VALUE_BETS_PATH), source_run_id


def load_todays_matches() -> tuple[dict[str, dict], str | None]:
    """Return a lookup dict keyed by match_id."""
    if not TODAYS_MATCHES_PATH.exists():
        return {}, None
    with open(TODAYS_MATCHES_PATH, encoding="utf-8") as f:
        payload = json.load(f)
    source_run_id = payload.get("source_run_id") if isinstance(payload, dict) else None
    matches = _records(payload, TODAYS_MATCHES_PATH)
    return {m["match_id"]: m for m in matches}, source_run_id


def build_bets(value_bets: list[dict], matches: dict[str, dict]) -> list[dict]:
    today_str = datetime.now(UTC).strftime("%Y-%m-%d")
    bets: list[dict] = []

    for vb in value_bets:
        match_id = vb.get("match", "")
        match_info = matches.get(match_id, {})

        team1 = match_info.get("team1", "")
        team2 = match_info.get("team2", "")
        game_str = f"{team1} vs {team2}" if team1 and team2 else match_id
        game_time = match_info.get("time", "")

        edge = vb.get("edge", 0.0) or 0.0
        tier_raw = vb.get("tier", "Good")
        tier = TIER_MAP.get(tier_raw, "Good")

        bets.append(
            {
                "game_date": today_str,
                "game": game_str,
                "game_time": game_time,
                "bet_type": vb.get("type", "Match Winner"),
                "pick": vb.get("bet", ""),
                "confidence": round(float(vb.get("model_prob", 0.0)), 4),
                "edge": round(float(edge), 4),
                "odds": _parse_odds(vb.get("dk_odds")),
                "tier": tier,
                "notes": f"Kelly stake: {vb.get('kelly_stake', '')}",
            }
        )

    return bets


def main() -> None:
    value_bets, value_bets_run_id = load_value_bets()
    matches, matches_run_id = load_todays_matches()
    if value_bets_run_id and matches_run_id and value_bets_run_id != matches_run_id:
        print(
            "[cricket export] value_bets and todays_matches come from different pipeline runs — "
            "excluding stale bets"
        )
        value_bets = []
    bets = build_bets(value_bets, matches)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            "sport": "Cricket",
            "generated_at": datetime.now(UTC).isoformat(),
            "model_version": "1.0.0",
            "season": str(datetime.now(UTC).year),
        },
        "bets": bets,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"[cricket export] Wrote {len(bets)} bets → {OUT_PATH}")


if __name__ == "__main__":
    main()
