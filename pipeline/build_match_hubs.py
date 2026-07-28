"""Build fixture-specific, cache-first research views for the Match Hub."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _team_players(team: str, team_players: dict[str, dict[str, list[str]]]) -> set[str]:
    roster = team_players.get(team, {})
    return set(roster.get("batters", []) + roster.get("bowlers", []))


def top_rivalries(
    rivalries: list[dict[str, Any]], team1_players: set[str], team2_players: set[str], limit: int = 5
) -> list[dict[str, Any]]:
    """Choose deterministic, well-sampled cross-team historical matchups."""
    cross_team = [
        rivalry
        for rivalry in rivalries
        if (rivalry.get("batter") in team1_players and rivalry.get("bowler") in team2_players)
        or (rivalry.get("batter") in team2_players and rivalry.get("bowler") in team1_players)
    ]
    tier_rank = {"high": 3, "medium": 2, "low": 1}
    return sorted(
        cross_team,
        key=lambda rivalry: (
            tier_rank.get(rivalry.get("sample_tier"), 0),
            abs(float(rivalry.get("matchup_score", 50)) - 50),
            int(rivalry.get("legal_balls", 0)),
            rivalry.get("key", ""),
        ),
        reverse=True,
    )[:limit]


def build_match_hubs(
    matches: list[dict[str, Any]],
    props: list[dict[str, Any]],
    team_form: dict[str, list[dict[str, Any]]],
    venue_stats: dict[str, dict[str, Any]],
    rivalries_payload: dict[str, Any],
    team_players: dict[str, dict[str, list[str]]],
) -> dict[str, Any]:
    """Create a local-only match research object for every predicted fixture."""
    rivalries = rivalries_payload.get("rivalries", [])
    hubs: dict[str, dict[str, Any]] = {}
    for match in matches:
        match_id = str(match.get("match_id", ""))
        if not match_id:
            continue
        team1, team2 = match.get("team1", ""), match.get("team2", "")
        selected_rivalries = top_rivalries(
            rivalries, _team_players(team1, team_players), _team_players(team2, team_players)
        )
        top_props = sorted(
            (prop for prop in props if prop.get("match_id") == match_id),
            key=lambda prop: abs(float(prop.get("edge", 0) or 0)),
            reverse=True,
        )[:5]
        hubs[match_id] = {
            "match": {key: match.get(key) for key in ("match_id", "team1", "team2", "venue", "time", "status")},
            "prediction": {
                key: match.get(key)
                for key in ("team1_win_prob", "team2_win_prob", "predicted_total", "predicted_first_innings")
            },
            "market": {
                "team1_implied_prob": match.get("dk_implied_prob_team1"),
                "team2_implied_prob": match.get("dk_implied_prob_team2"),
                "total_line": match.get("dk_total_line"),
            },
            "venue": venue_stats.get(match.get("venue", ""), {}),
            "weather": {key: match.get(key) for key in ("temperature", "humidity", "dew_flag", "windspeed")},
            "team_form": {"team1": team_form.get(team1, [])[:5], "team2": team_form.get(team2, [])[:5]},
            "key_rivalries": selected_rivalries,
            "top_props": top_props,
            "data_status": {
                "fixtures": "available",
                "odds": "available" if match.get("dk_total_line") is not None else "unavailable",
                "weather": "available" if match.get("temperature") is not None else "unavailable",
                "rivalries": "available" if selected_rivalries else "unavailable",
            },
        }
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "matches": hubs,
    }
