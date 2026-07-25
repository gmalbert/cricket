"""Competition readiness, status, and forward odds-history contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pipeline.competitions import Competition, enabled_competitions

MIN_COMPLETED_MATCHES = 100
MIN_TEAM_IDENTITY_RATE = 0.80
MIN_PLAYER_IDENTITY_RATE = 0.90


def competition_status(
    competition: Competition,
    *,
    fixtures: list[dict],
    odds: list[dict],
    historical: dict | None = None,
    model_ready: bool | None = None,
    qualifying_bets: int = 0,
    fetch_error: str | None = None,
) -> dict:
    historical = historical or {}
    fixture_rows = [f for f in fixtures if f.get("competition", "ipl_male") == competition.slug]
    provisional_rows = [f for f in fixture_rows if f.get("fixture_status") == "provisional"]
    odds_rows = [o for o in odds if o.get("competition", "ipl_male") == competition.slug]
    dk_rows = [
        o
        for o in odds_rows
        if o.get("event_status") == "draftkings_available"
        or (o.get("bookmaker") == "draftkings" and o.get("dk_odds_team1") is not None)
    ]
    completed = int(historical.get("completed_matches", 0))
    team_rate = float(historical.get("team_identity_rate", 0))
    player_rate = float(historical.get("player_identity_rate", 0))
    historical_ready = bool(historical.get("ready")) or (
        completed >= MIN_COMPLETED_MATCHES
        and team_rate >= MIN_TEAM_IDENTITY_RATE
        and player_rate >= MIN_PLAYER_IDENTITY_RATE
    )
    if fetch_error:
        reason = "fixtures_fetch_failed" if not fixture_rows else "odds_fetch_failed"
    elif not fixture_rows:
        reason = "no_fixtures"
    elif not dk_rows:
        reason = "no_draftkings_market"
    elif not historical_ready:
        reason = "historical_data_insufficient"
    elif model_ready is False:
        reason = "model_not_ready"
    elif qualifying_bets == 0:
        reason = "no_qualifying_bets"
    else:
        reason = None
    return {
        "competition": competition.slug,
        "competition_name": competition.display_name,
        "format": competition.format,
        "gender": competition.gender,
        "fixtures_found": bool(fixture_rows),
        "fixtures_count": len(fixture_rows),
        "provisional_fixtures": len(provisional_rows),
        "fixture_sources": sorted({f.get("fixture_source", "unknown") for f in fixture_rows}),
        "odds_found": bool(odds_rows),
        "draftkings_available": bool(dk_rows),
        "draftkings_events": len(dk_rows),
        "historical_data_ready": historical_ready,
        "historical_coverage": historical,
        "model_ready": model_ready if model_ready is not None else historical_ready,
        "qualifying_bets": qualifying_bets,
        "reason": reason,
        "status": "ready" if reason is None else reason,
        "updated_at": datetime.now(UTC).isoformat(),
    }


def build_status_report(
    fixtures: list[dict],
    odds: list[dict],
    historical_by_competition: dict | None = None,
    model_ready_by_competition: dict | None = None,
    bets_by_competition: dict | None = None,
    errors: dict | None = None,
) -> dict:
    historical_by_competition = historical_by_competition or {}
    model_ready_by_competition = model_ready_by_competition or {}
    bets_by_competition = bets_by_competition or {}
    errors = errors or {}
    rows = {}
    for competition in enabled_competitions():
        rows[competition.slug] = competition_status(
            competition,
            fixtures=fixtures,
            odds=odds,
            historical=historical_by_competition.get(competition.slug),
            model_ready=model_ready_by_competition.get(competition.slug),
            qualifying_bets=bets_by_competition.get(competition.slug, 0),
            fetch_error=errors.get(competition.slug),
        )
    return {"schema_version": 1, "generated_at": datetime.now(UTC).isoformat(), "competitions": rows}


def inspect_historical_coverage(competition: Competition, raw_dir: Path) -> dict:
    """Inspect an optional normalized parquet without making network calls."""
    path = raw_dir / f"{competition.slug}_ball_by_ball.parquet"
    if not path.exists():
        return {
            "path": str(path),
            "seasons": [],
            "completed_matches": 0,
            "team_identity_rate": 0.0,
            "player_identity_rate": 0.0,
            "ready": False,
        }
    try:
        import pandas as pd

        frame = pd.read_parquet(path)
        seasons = sorted(str(value) for value in frame.get("season", pd.Series(dtype=str)).dropna().unique())
        matches = int(frame.get("match_id", pd.Series(dtype=str)).nunique())
        team_columns = [column for column in ("batting_team", "bowling_team") if column in frame]
        player_columns = [column for column in ("striker", "bowler") if column in frame]
        team_rate = float(frame[team_columns].notna().all(axis=1).mean()) if team_columns else 0.0
        player_rate = float(frame[player_columns].notna().all(axis=1).mean()) if player_columns else 0.0
        return {
            "path": str(path),
            "seasons": seasons,
            "completed_matches": matches,
            "team_identity_rate": round(team_rate, 4),
            "player_identity_rate": round(player_rate, 4),
            "ready": len(seasons) >= 2
            and matches >= MIN_COMPLETED_MATCHES
            and team_rate >= MIN_TEAM_IDENTITY_RATE
            and player_rate >= MIN_PLAYER_IDENTITY_RATE,
        }
    except Exception as exc:
        return {
            "path": str(path),
            "seasons": [],
            "completed_matches": 0,
            "team_identity_rate": 0.0,
            "player_identity_rate": 0.0,
            "ready": False,
            "error": str(exc),
        }
