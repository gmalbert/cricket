"""Build cacheable historical batter-versus-bowler rivalry summaries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from pipeline.normalization import audit_player_names, canonical_player

SCHEMA_VERSION = 1
PHASES = ("powerplay", "middle", "death")
BOWLER_CREDITED_WICKETS = {
    "bowled",
    "caught",
    "caught and bowled",
    "lbw",
    "stumped",
    "hit wicket",
}


def phase_for_over(over: int) -> str:
    if over <= 5:
        return "powerplay"
    if over <= 14:
        return "middle"
    return "death"


def _empty_payload(error: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "competition": "ipl_male",
        "source": {"provider": "Cricsheet", "dataset": "ipl_male_csv2"},
        "rivalries": [],
    }
    if error:
        payload["error"] = error
    return payload


def _source_column(frame: pd.DataFrame, *names: str) -> str | None:
    return next((name for name in names if name in frame.columns), None)


def _is_legal_ball(row: pd.Series) -> bool:
    """A wide or no-ball is not a legal delivery for over/ball-count metrics."""
    return float(row.get("wides", 0) or 0) == 0 and float(row.get("noballs", 0) or 0) == 0


def _credited_dismissal(row: pd.Series) -> bool:
    wicket_type = str(row.get("wicket_type", "") or "").lower().strip()
    return wicket_type in BOWLER_CREDITED_WICKETS and bool(row.get("dismissed_batter", False))


def _sample_tier(legal_balls: int, dismissals: int) -> str:
    if legal_balls >= 36 or dismissals >= 3:
        return "high"
    if legal_balls >= 12 or dismissals >= 2:
        return "medium"
    return "low"


def _matchup_score(runs: int, legal_balls: int, dismissals: int) -> float:
    """Descriptive 0–100 score; deliberately not a probability or model feature."""
    if legal_balls == 0:
        return 50.0
    return round(max(0.0, min(100.0, 50 + 12 * ((runs / legal_balls) - 1.2) - 8 * dismissals)), 1)


def build_rivalries(
    ball_by_ball: pd.DataFrame,
    competition: str = "ipl_male",
    rosters: dict[str, dict[str, list[str]]] | None = None,
) -> dict[str, Any]:
    """Aggregate raw Cricsheet deliveries into display-ready rivalry records.

    CSV2 variants use either ``striker`` or ``batter``. The function supports
    both and returns a labelled empty payload when required fields are absent.
    """
    batter_col = _source_column(ball_by_ball, "batter", "striker")
    required = {"bowler", "runs_off_bat", "match_id"}
    missing = required - set(ball_by_ball.columns)
    if batter_col is None:
        missing.add("batter/striker")
    if missing:
        return _empty_payload(f"Missing required columns: {sorted(missing)}")

    df = ball_by_ball.copy()
    df["batter"] = df[batter_col].map(canonical_player)
    df["bowler"] = df["bowler"].map(canonical_player)
    historical_players = set(df["batter"]) | set(df["bowler"])
    if rosters is not None:
        # The interactive product is fixture research, so retain matchups that
        # can actually occur for a configured squad. This keeps the JSON cache
        # practical for nightly commits while raw parquet remains the full
        # historical source for future roster/competition expansions.
        active_players = {
            canonical_player(player)
            for squad in rosters.values()
            for player in squad.get("batters", []) + squad.get("bowlers", [])
        }
        df = df[df["batter"].isin(active_players) & df["bowler"].isin(active_players)].copy()
    df["runs_off_bat"] = pd.to_numeric(df["runs_off_bat"], errors="coerce").fillna(0).astype(int)
    for column in ("wides", "noballs"):
        if column not in df:
            df[column] = 0
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
    # Vectorized instead of ``DataFrame.apply``: the IPL archive has >500k
    # deliveries, so row-wise Python execution makes the nightly job unusable.
    df["legal_ball"] = df["wides"].eq(0) & df["noballs"].eq(0)
    dismissed_col = _source_column(df, "player_dismissed", "dismissed_player")
    if dismissed_col:
        df["dismissed_batter"] = df[dismissed_col].map(canonical_player).eq(df["batter"])
    else:
        df["dismissed_batter"] = False
    wicket_type = df.get("wicket_type", pd.Series("", index=df.index)).fillna("").astype(str).str.lower().str.strip()
    df["credited_dismissal"] = wicket_type.isin(BOWLER_CREDITED_WICKETS) & df["dismissed_batter"]
    df["over_number"] = pd.to_numeric(df.get("ball", 0), errors="coerce").fillna(0).astype(int)
    df["phase"] = df["over_number"].map(phase_for_over)

    keys = ["batter", "bowler"]
    df = df[df["batter"].ne("") & df["bowler"].ne("")]
    # Keep all expensive work in pandas groupbys. There are hundreds of
    # thousands of deliveries but only a few thousand player pairings.
    summary = df.groupby(keys, sort=False).agg(
        balls=("match_id", "size"),
        legal_balls=("legal_ball", "sum"),
        runs_off_bat=("runs_off_bat", "sum"),
        dismissals=("credited_dismissal", "sum"),
    )
    legal = df[df["legal_ball"]].copy()
    legal["dot"] = legal["runs_off_bat"].eq(0)
    legal["boundary"] = legal["runs_off_bat"].ge(4)
    legal_summary = legal.groupby(keys, sort=False).agg(dots=("dot", "sum"), boundaries=("boundary", "sum"))
    summary = summary.join(legal_summary, how="left").fillna({"dots": 0, "boundaries": 0})

    phase_agg = df.groupby(keys + ["phase"], sort=False).agg(
        runs_off_bat=("runs_off_bat", "sum"), dismissals=("credited_dismissal", "sum")
    )
    phase_legal = legal.groupby(keys + ["phase"], sort=False).size().rename("legal_balls")
    phase_agg = phase_agg.join(phase_legal, how="left").fillna({"legal_balls": 0})
    phase_map: dict[tuple[str, str], dict[str, dict[str, int]]] = {}
    for (batter, bowler, phase), phase_row in phase_agg.iterrows():
        phase_map.setdefault((batter, bowler), {})[phase] = {
            "legal_balls": int(phase_row["legal_balls"]),
            "runs_off_bat": int(phase_row["runs_off_bat"]),
            "dismissals": int(phase_row["dismissals"]),
        }

    dismissal_types: dict[tuple[str, str], dict[str, int]] = {}
    if "wicket_type" in df:
        credited = df[df["credited_dismissal"]].copy()
        if not credited.empty:
            grouped_types = credited.groupby(keys + ["wicket_type"], sort=False).size()
            for (batter, bowler, wicket_type), count in grouped_types.items():
                dismissal_types.setdefault((batter, bowler), {})[str(wicket_type).lower()] = int(count)

    date_column = _source_column(df, "start_date", "date")
    encounter_agg = df.groupby(keys + ["match_id"], sort=False).agg(
        runs=("runs_off_bat", "sum"),
        dismissed=("credited_dismissal", "max"),
        date=(date_column, "first") if date_column else ("match_id", "first"),
    )
    encounter_legal = legal.groupby(keys + ["match_id"], sort=False).size().rename("balls")
    encounter_agg = encounter_agg.join(encounter_legal, how="left").fillna({"balls": 0})
    encounter_agg = encounter_agg.sort_values("date", ascending=False)
    recent_map: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for (batter, bowler), encounters in encounter_agg.groupby(level=[0, 1], sort=False):
        recent_map[(batter, bowler)] = [
            {
                "match_id": str(match_id),
                "date": str(row["date"]) if date_column else None,
                "balls": int(row["balls"]),
                "runs": int(row["runs"]),
                "dismissed": bool(row["dismissed"]),
            }
            for (_, _, match_id), row in encounters.head(5).iterrows()
        ]

    records: list[dict[str, Any]] = []
    for (batter, bowler), row in summary.iterrows():
        legal_balls, runs, dismissals = int(row["legal_balls"]), int(row["runs_off_bat"]), int(row["dismissals"])
        score = _matchup_score(runs, legal_balls, dismissals)
        phases = phase_map.get((batter, bowler), {})
        for phase in PHASES:
            phases.setdefault(phase, {"legal_balls": 0, "runs_off_bat": 0, "dismissals": 0})
        records.append(
            {
                "key": f"{batter.lower().replace(' ', '_')}__{bowler.lower().replace(' ', '_')}",
                "batter": batter,
                "bowler": bowler,
                "balls": int(row["balls"]),
                "legal_balls": legal_balls,
                "runs_off_bat": runs,
                "dismissals": dismissals,
                "strike_rate": round(100 * runs / legal_balls, 1) if legal_balls else None,
                "runs_per_ball": round(runs / legal_balls, 3) if legal_balls else None,
                "dot_ball_pct": round(100 * int(row["dots"]) / legal_balls, 1) if legal_balls else None,
                "boundary_count": int(row["boundaries"]),
                "boundary_pct": round(100 * int(row["boundaries"]) / legal_balls, 1) if legal_balls else None,
                "dismissal_types": dismissal_types.get((batter, bowler), {}),
                "phase_splits": phases,
                "recent_encounters": recent_map.get((batter, bowler), []),
                "sample_tier": _sample_tier(legal_balls, dismissals),
                "matchup_score": score,
                "score_label": "Batter advantage" if score >= 62 else "Bowler advantage" if score <= 38 else "Neutral",
            }
        )

    records.sort(key=lambda record: (record["legal_balls"], record["dismissals"]), reverse=True)
    payload = _empty_payload()
    payload["competition"] = competition
    payload["rivalries"] = records
    if rosters is not None:
        payload["unmatched_players"] = audit_player_names(rosters, historical_players)
    return payload
