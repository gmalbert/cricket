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


def load_value_bets() -> list[dict]:
    if not VALUE_BETS_PATH.exists():
        print(f"[cricket export] {VALUE_BETS_PATH} not found — writing empty output")
        return []
    with open(VALUE_BETS_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_todays_matches() -> dict[str, dict]:
    """Return a lookup dict keyed by match_id."""
    if not TODAYS_MATCHES_PATH.exists():
        return {}
    with open(TODAYS_MATCHES_PATH, encoding="utf-8") as f:
        matches = json.load(f)
    return {m["match_id"]: m for m in matches}


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
    value_bets = load_value_bets()
    matches = load_todays_matches()
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
    try:
        main()
    except Exception as exc:
        print(f"[cricket export] Unhandled error: {exc} — writing empty fallback output")
        import traceback

        traceback.print_exc()
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        fallback = {
            "meta": {
                "sport": "Cricket",
                "generated_at": datetime.now(UTC).isoformat(),
                "model_version": "1.0.0",
                "season": str(datetime.now(UTC).year),
                "notes": f"Export failed: {exc}",
            },
            "bets": [],
        }
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(fallback, f, indent=2)
        print(f"[cricket export] Wrote fallback (0 bets) → {OUT_PATH}")
