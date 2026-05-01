"""
Fetch and process IPL ball-by-ball data from Cricsheet.
Downloads the latest IPL CSV pack and extracts match-level and
player-level aggregates needed for feature engineering.
"""
import io
import zipfile
import logging
import requests
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)

CRICSHEET_IPL_URL = "https://cricsheet.org/downloads/ipl_male_csv2.zip"
RAW_DIR = Path(__file__).parent.parent / "cache" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def download_ipl_data() -> pd.DataFrame:
    """Download the Cricsheet IPL CSV zip and return a combined ball-by-ball DataFrame."""
    logger.info("Downloading Cricsheet IPL data from %s", CRICSHEET_IPL_URL)
    resp = requests.get(CRICSHEET_IPL_URL, timeout=120)
    resp.raise_for_status()

    frames = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_files = [f for f in zf.namelist() if f.endswith(".csv") and not f.startswith("_")]
        logger.info("Found %d CSV files in archive", len(csv_files))
        for name in csv_files:
            try:
                with zf.open(name) as f:
                    df = pd.read_csv(f, low_memory=False)
                    frames.append(df)
            except Exception as e:
                logger.warning("Could not parse %s: %s", name, e)

    if not frames:
        raise RuntimeError("No valid CSVs found in Cricsheet zip")

    combined = pd.concat(frames, ignore_index=True)
    logger.info("Loaded %d rows of ball-by-ball data", len(combined))

    out_path = RAW_DIR / "ipl_ball_by_ball.parquet"
    combined.to_parquet(out_path, index=False)
    logger.info("Saved raw data to %s", out_path)
    return combined


def compute_team_form(bbb: pd.DataFrame, last_n: int = 10) -> dict:
    """
    For each team, compute rolling form over their last N T20 matches.
    Returns dict keyed by team name.
    """
    required = {"match_id", "start_date", "batting_team", "bowling_team",
                "runs_off_bat", "extras", "wicket_type", "innings"}
    missing = required - set(bbb.columns)
    if missing:
        logger.warning("Missing columns for team form: %s", missing)
        return {}

    bbb = bbb.copy()
    bbb["start_date"] = pd.to_datetime(bbb["start_date"], errors="coerce")

    match_meta = (
        bbb.groupby("match_id")
        .agg(
            start_date=("start_date", "first"),
            team1=("batting_team", "first"),
            team2=("bowling_team", "first"),
        )
        .reset_index()
    )

    innings_agg = (
        bbb.groupby(["match_id", "innings", "batting_team"])
        .agg(
            runs=("runs_off_bat", "sum"),
            extras=("extras", "sum"),
            wickets=("wicket_type", lambda x: x.notna().sum()),
        )
        .reset_index()
    )
    innings_agg["total_runs"] = innings_agg["runs"] + innings_agg["extras"]

    powerplay = bbb[bbb.get("over", pd.Series(dtype=float)).between(0, 5) if "over" in bbb.columns else bbb.index.isin([])]
    death = bbb[bbb.get("over", pd.Series(dtype=float)).between(15, 19) if "over" in bbb.columns else bbb.index.isin([])]

    pp_agg = (
        powerplay.groupby(["match_id", "batting_team"])["runs_off_bat"]
        .sum()
        .reset_index()
        .rename(columns={"runs_off_bat": "powerplay_runs"})
    ) if not powerplay.empty else pd.DataFrame(columns=["match_id", "batting_team", "powerplay_runs"])

    death_bowl = (
        death.groupby(["match_id", "bowling_team"])
        .agg(
            death_runs=("runs_off_bat", "sum"),
            death_extras=("extras", "sum"),
        )
        .reset_index()
    ) if not death.empty else pd.DataFrame(columns=["match_id", "bowling_team", "death_runs", "death_extras"])

    all_teams = set(bbb["batting_team"].dropna().unique())
    form_by_team = {}

    for team in all_teams:
        team_innings = innings_agg[innings_agg["batting_team"] == team].copy()
        team_innings = team_innings.merge(match_meta[["match_id", "start_date"]], on="match_id", how="left")
        team_innings = team_innings.sort_values("start_date", ascending=False).head(last_n)

        pp_team = pp_agg[pp_agg["batting_team"] == team] if not pp_agg.empty else pd.DataFrame()
        death_team = death_bowl[death_bowl["bowling_team"] == team] if not death_bowl.empty else pd.DataFrame()

        results = []
        for _, row in team_innings.iterrows():
            inns_pp = pp_team[pp_team["match_id"] == row["match_id"]]
            pp_runs = int(inns_pp["powerplay_runs"].values[0]) if not inns_pp.empty else None

            inns_death = death_team[death_team["match_id"] == row["match_id"]]
            if not inns_death.empty:
                d_runs = inns_death["death_runs"].values[0] + inns_death["death_extras"].values[0]
                death_econ = round(d_runs / 4, 2) if d_runs else None
            else:
                death_econ = None

            results.append({
                "match_id": row["match_id"],
                "date": str(row["start_date"].date()) if pd.notna(row["start_date"]) else None,
                "innings": int(row["innings"]),
                "score": int(row["total_runs"]),
                "wickets": int(row["wickets"]),
                "powerplay_runs": pp_runs,
                "death_economy": death_econ,
            })

        form_by_team[team] = results

    return form_by_team


def compute_player_stats(bbb: pd.DataFrame) -> dict:
    """
    Compute rolling batter and bowler stats for the last 10 T20 innings.
    Returns {"batters": {...}, "bowlers": {...}}
    """
    required_bat = {"batter", "runs_off_bat", "match_id", "start_date"}
    required_bowl = {"bowler", "runs_off_bat", "wicket_type", "match_id", "start_date"}

    bbb = bbb.copy()
    bbb["start_date"] = pd.to_datetime(bbb["start_date"], errors="coerce")

    batters = {}
    if required_bat.issubset(bbb.columns):
        bat_agg = (
            bbb.groupby(["match_id", "batter"])
            .agg(
                runs=("runs_off_bat", "sum"),
                balls=("runs_off_bat", "count"),
                start_date=("start_date", "first"),
            )
            .reset_index()
            .sort_values("start_date", ascending=False)
        )
        for player, grp in bat_agg.groupby("batter"):
            last10 = grp.head(10)
            scores = last10["runs"].tolist()
            avg = round(last10["runs"].mean(), 1) if not last10.empty else 0
            sr = round(last10["runs"].sum() / last10["balls"].sum() * 100, 1) if last10["balls"].sum() > 0 else 0
            batters[player] = {
                "recent_scores": scores,
                "recent_avg": avg,
                "recent_sr": sr,
            }

    bowlers = {}
    if required_bowl.issubset(bbb.columns):
        bowl_agg = (
            bbb.groupby(["match_id", "bowler"])
            .agg(
                runs=("runs_off_bat", "sum"),
                extras=("extras", "sum") if "extras" in bbb.columns else ("runs_off_bat", lambda x: 0),
                wickets=("wicket_type", lambda x: x.notna().sum()),
                balls=("runs_off_bat", "count"),
                start_date=("start_date", "first"),
            )
            .reset_index()
            .sort_values("start_date", ascending=False)
        )
        for player, grp in bowl_agg.groupby("bowler"):
            last5 = grp.head(5)
            total_balls = last5["balls"].sum()
            total_runs = last5["runs"].sum()
            economy = round(total_runs / (total_balls / 6), 2) if total_balls > 0 else 0
            wickets_list = last5["wickets"].tolist()
            bowlers[player] = {
                "wickets_last5": wickets_list,
                "recent_economy": economy,
                "recent_wickets_per_match": round(sum(wickets_list) / len(wickets_list), 2) if wickets_list else 0,
            }

    return {"batters": batters, "bowlers": bowlers}


def compute_venue_stats(bbb: pd.DataFrame) -> dict:
    """Compute first-innings avg and chase win rate per venue."""
    required = {"venue", "innings", "batting_team", "bowling_team",
                "runs_off_bat", "extras", "match_id"}
    if not required.issubset(bbb.columns):
        logger.warning("Missing columns for venue stats")
        return {}

    bbb = bbb.copy()
    innings_totals = (
        bbb.groupby(["match_id", "venue", "innings", "batting_team"])
        .agg(runs=("runs_off_bat", "sum"), extras=("extras", "sum"))
        .reset_index()
    )
    innings_totals["total"] = innings_totals["runs"] + innings_totals["extras"]

    first_inn = innings_totals[innings_totals["innings"] == 1]
    venue_avg = first_inn.groupby("venue")["total"].mean().round(1).to_dict()

    match_results = innings_totals.pivot_table(
        index=["match_id", "venue"], columns="innings", values="total"
    ).reset_index()
    match_results.columns = ["match_id", "venue", "inn1", "inn2"]
    match_results = match_results.dropna(subset=["inn1", "inn2"])
    match_results["chaser_won"] = match_results["inn2"] > match_results["inn1"]
    chase_rate = match_results.groupby("venue")["chaser_won"].mean().round(3).to_dict()

    venues = {}
    for v in set(list(venue_avg.keys()) + list(chase_rate.keys())):
        venues[v] = {
            "avg_first_innings": venue_avg.get(v),
            "chase_win_rate": chase_rate.get(v),
        }
    return venues


def run(save_path: Path | None = None) -> dict:
    """Full Cricsheet pipeline: download → process → return aggregates."""
    bbb = download_ipl_data()
    team_form = compute_team_form(bbb)
    player_stats = compute_player_stats(bbb)
    venue_stats = compute_venue_stats(bbb)
    return {
        "team_form": team_form,
        "player_stats": player_stats,
        "venue_stats": venue_stats,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    logger.info("Team form computed for %d teams", len(result["team_form"]))
    logger.info("Player stats: %d batters, %d bowlers",
                len(result["player_stats"]["batters"]),
                len(result["player_stats"]["bowlers"]))
    logger.info("Venue stats: %d venues", len(result["venue_stats"]))
