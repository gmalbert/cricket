"""
Wicket Oracle — Data Pull Script
Run this once to populate all cache files before starting the app.

Usage:
    python fetch_data.py                  # full run
    python fetch_data.py --skip-cricsheet # skip re-downloading ball-by-ball data if fresh
    python fetch_data.py --dry-run        # check API keys and connectivity without writing files

Required environment variables (set in .env or your shell):
    ODDS_API_KEY           — from https://the-odds-api.com
    CRICKET_DATA_API_KEY   — from https://cricketdata.org

Weather (Open-Meteo) is free and needs no key.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Colour helpers (no external dep) ────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✓{RESET}  {msg}")
def fail(msg):  print(f"  {RED}✗{RESET}  {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{RESET}  {msg}")
def info(msg):  print(f"  {CYAN}→{RESET}  {msg}")
def header(msg):print(f"\n{BOLD}{msg}{RESET}")
def divider():  print("─" * 56)


# ── Environment check ────────────────────────────────────────────────────────
def check_env() -> dict:
    """Return dict of available API keys. Warns but does not exit on missing."""
    header("Checking environment variables")
    keys = {}

    odds_key = os.environ.get("ODDS_API_KEY", "")
    if odds_key:
        ok(f"ODDS_API_KEY found ({len(odds_key)} chars)")
        keys["ODDS_API_KEY"] = odds_key
    else:
        warn("ODDS_API_KEY not set — DraftKings odds will be skipped")

    cricket_key = os.environ.get("CRICKET_DATA_API_KEY", "")
    if cricket_key:
        ok(f"CRICKET_DATA_API_KEY found ({len(cricket_key)} chars)")
        keys["CRICKET_DATA_API_KEY"] = cricket_key
    else:
        warn("CRICKET_DATA_API_KEY not set — live fixtures will be skipped")

    ok("Open-Meteo (weather) — no key required")
    return keys


# ── Individual step runners ──────────────────────────────────────────────────
def run_step(label: str, fn, *args, **kwargs):
    """Run a pipeline step, time it, and return (result, elapsed, error)."""
    print(f"\n  Running: {label} ...", end="", flush=True)
    t0 = time.time()
    try:
        result = fn(*args, **kwargs)
        elapsed = time.time() - t0
        print(f"  done ({elapsed:.1f}s)")
        return result, elapsed, None
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  FAILED ({elapsed:.1f}s)")
        return None, elapsed, str(e)


def pull_cricsheet(skip: bool) -> dict:
    from pipeline.run_pipeline import step_cricsheet
    return step_cricsheet(skip=skip)


def pull_fixtures() -> list:
    from pipeline.run_pipeline import step_fixtures
    return step_fixtures()


def pull_odds() -> list:
    from pipeline.run_pipeline import step_odds
    return step_odds()


def pull_weather(fixtures: list) -> dict:
    from pipeline.run_pipeline import step_weather
    return step_weather(fixtures)


def pull_features(fixtures, team_form, venue_stats, weather, odds, player_stats=None):
    from pipeline.run_pipeline import step_features
    return step_features(fixtures, team_form, venue_stats, weather, odds, player_stats=player_stats)


def pull_models(match_features, player_features):
    from pipeline.run_pipeline import step_models
    return step_models(match_features, player_features)


def pull_monte_carlo(fixtures, team_form):
    from pipeline.run_pipeline import step_monte_carlo
    # Never feed simulated standings or schedules into a production run.
    points_table  = []
    full_schedule = fixtures
    return step_monte_carlo(points_table, full_schedule)


def pull_matchup_edge(team_form, venue_stats):
    from pipeline.run_pipeline import step_matchup_edge
    return step_matchup_edge(team_form, venue_stats)


def pull_reconcile():
    from pipeline.run_pipeline import step_reconcile
    log, _n_new = step_reconcile()
    return log


# ── Cache write ──────────────────────────────────────────────────────────────
CACHE_DIR = Path("cache")

def save(name: str, data, dry_run: bool) -> None:
    if dry_run:
        info(f"[dry-run] would write {name}.json")
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{name}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    size_kb = path.stat().st_size / 1024
    ok(f"Saved {name}.json  ({size_kb:.1f} KB)")


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Wicket Oracle data pull")
    parser.add_argument("--skip-cricsheet", action="store_true",
                        help="Skip Cricsheet download if data is less than 23h old")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run all steps but do not write any cache files")
    args = parser.parse_args()

    print(f"\n{BOLD}{'=' * 56}")
    print("  Wicket Oracle — Data Pull")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'=' * 56}{RESET}")

    if args.dry_run:
        warn("DRY RUN — no files will be written")

    # 1. Check env
    check_env()
    divider()

    errors   = {}
    timings  = {}

    # 2. Reconcile yesterday's predictions (step 0)
    header("Step 0 — Reconcile yesterday's predictions")
    prediction_log, t, err = run_step("reconcile_predictions", pull_reconcile)
    timings["reconcile"] = t
    if err:
        fail(f"Reconcile failed: {err}")
        errors["reconcile"] = err
        prediction_log = []
    else:
        n = len(prediction_log) if isinstance(prediction_log, list) else 0
        ok(f"Prediction log: {n} records total")

    # 3. Cricsheet — ball-by-ball historical data
    header("Step 1 — Cricsheet (historical ball-by-ball data)")
    if args.skip_cricsheet:
        info("--skip-cricsheet flag set; will reuse cached parquet if fresh")
    cricsheet, t, err = run_step("fetch_cricsheet", pull_cricsheet, args.skip_cricsheet)
    timings["cricsheet"] = t
    if err:
        fail(f"Cricsheet failed: {err}")
        errors["cricsheet"] = err
        cricsheet = {"team_form": {}, "player_stats": {}, "venue_stats": {}}
    else:
        ok(f"Team form: {len(cricsheet.get('team_form', {}))} teams")
        ok(f"Player stats: {len(cricsheet.get('player_stats', {}))} players")
        ok(f"Venue stats: {len(cricsheet.get('venue_stats', {}))} venues")

    team_form   = cricsheet.get("team_form", {})
    player_stats = cricsheet.get("player_stats", {})
    venue_stats  = cricsheet.get("venue_stats", {})

    # 4. Fixtures
    header("Step 2 — Live fixtures (CricketData.org)")
    fixtures, t, err = run_step("fetch_fixtures", pull_fixtures)
    timings["fixtures"] = t
    if err:
        fail(f"Fixtures failed: {err}")
        errors["fixtures"] = err
        fixtures = []
    else:
        ok(f"{len(fixtures)} fixture(s) fetched")
        if not fixtures:
            warn("No fixtures returned — app will show simulated matches")

    # 5. Odds
    header("Step 3 — DraftKings odds (The Odds API)")
    odds, t, err = run_step("fetch_odds", pull_odds)
    timings["odds"] = t
    if err:
        fail(f"Odds failed: {err}")
        errors["odds"] = err
        odds = []
    else:
        ok(f"{len(odds)} odds record(s) fetched")

    # 6. Weather
    header("Step 4 — Weather (Open-Meteo)")
    weather, t, err = run_step("fetch_weather", pull_weather, fixtures)
    timings["weather"] = t
    if err:
        fail(f"Weather failed: {err}")
        errors["weather"] = err
        weather = {}
    else:
        ok(f"Weather data for {len(weather)} venue(s)")

    # 7. Feature engineering
    header("Step 5 — Feature engineering")
    feats, t, err = run_step(
        "feature_engineering", pull_features,
        fixtures, team_form, venue_stats, weather, odds, player_stats
    )
    timings["features"] = t
    if err:
        fail(f"Feature engineering failed: {err}")
        errors["features"] = err
        match_features = []
        player_features = []
    else:
        match_features, player_features = feats
        ok(f"{len(match_features)} match feature vector(s)")
        ok(f"{len(player_features)} player feature vector(s)")

    # 8. Models
    header("Step 6 — ML models (XGBoost + LightGBM)")
    models_out, t, err = run_step("run_models", pull_models, match_features, player_features)
    timings["models"] = t
    if err:
        fail(f"Models failed: {err}")
        errors["models"] = err
        winner_preds = totals_preds = props_preds = []
    else:
        winner_preds, totals_preds, props_preds = models_out
        ok(f"{len(winner_preds)} winner prediction(s)")
        ok(f"{len(totals_preds)} totals prediction(s)")
        ok(f"{len(props_preds)} player prop(s)")

    # 9. Merge predictions into final match dicts
    header("Step 6b — Merge predictions into match output")
    try:
        from pipeline.run_pipeline import build_player_props_output, build_value_bets, merge_match_predictions
        matches_out = merge_match_predictions(winner_preds, totals_preds, odds)
        props_out   = build_player_props_output(props_preds, matches_out, odds)
        value_bets  = build_value_bets(matches_out, props_out)
        ok(f"{len(matches_out)} match(es) merged")
        ok(f"{len(props_out)} prop(s) merged")
        ok(f"{len(value_bets)} value bet(s) identified")
    except Exception as e:
        fail(f"Merge failed: {e}")
        errors["merge"] = str(e)
        matches_out = []
        props_out   = []
        value_bets  = []

    # 10. Monte Carlo
    header("Step 7 — Monte Carlo playoff simulator")
    mc_result, t, err = run_step("monte_carlo", pull_monte_carlo, fixtures, team_form)
    timings["monte_carlo"] = t
    if err:
        fail(f"Monte Carlo failed: {err}")
        errors["monte_carlo"] = err
        mc_result = {}
    else:
        n_sims = mc_result.get("n_simulations", 0)
        ok(f"{n_sims:,} simulations complete")

    # 11. Matchup edge history
    header("Step 8 — Matchup & venue edge history")
    edge_history, t, err = run_step("matchup_edge", pull_matchup_edge, team_form, venue_stats)
    timings["matchup_edge"] = t
    if err:
        fail(f"Matchup edge failed: {err}")
        errors["matchup_edge"] = err
        edge_history = {}
    else:
        n_matchups = len(edge_history.get("matchups", []))
        ok(f"{n_matchups} matchups analysed")

    # 12. Write cache
    header("Writing cache files")
    divider()

    team_form_serializable = {
        k: [
            {kk: str(vv) if hasattr(vv, 'isoformat') else vv for kk, vv in row.items()}
            for row in v
        ]
        for k, v in team_form.items()
    } if team_form else {}

    save("todays_matches",       matches_out,           args.dry_run)
    save("player_props",         props_out,             args.dry_run)
    save("value_bets",           value_bets,            args.dry_run)
    save("team_form",            team_form_serializable, args.dry_run)
    save("player_stats",         player_stats,          args.dry_run)
    save("venue_stats",          venue_stats,           args.dry_run)
    save("playoff_probabilities",mc_result,             args.dry_run)
    save("matchup_edge_history", edge_history,          args.dry_run)
    save("schedule",             fixtures,              args.dry_run)
    save("prediction_log",       prediction_log or [],  args.dry_run)

    last_updated = {
        "timestamp":               datetime.now(timezone.utc).isoformat(),
        "matches_count":           len(matches_out),
        "props_count":             len(props_out),
        "value_bets_count":        len(value_bets),
        "monte_carlo_sims":        mc_result.get("n_simulations", 0),
        "matchup_bets_analysed":   edge_history.get("total_bets_analysed", 0),
        "prediction_log_records":  len(prediction_log) if prediction_log else 0,
        "errors":                  errors,
    }
    save("last_updated", last_updated, args.dry_run)

    # 13. Summary
    divider()
    header("Summary")
    total_time = sum(timings.values())
    print(f"\n  Steps completed : {8 - len(errors)} / 8")
    print(f"  Total time      : {total_time:.1f}s")

    if errors:
        print(f"\n  {RED}Steps with errors:{RESET}")
        for step, msg in errors.items():
            fail(f"{step}: {msg}")
        print()
        if "ODDS_API_KEY" not in os.environ or "CRICKET_DATA_API_KEY" not in os.environ:
            print(f"  {YELLOW}Tip:{RESET} missing API keys are the most common cause of failures.")
            print("       Set them in your shell before running:")
            print("         export ODDS_API_KEY=your_key_here")
            print("         export CRICKET_DATA_API_KEY=your_key_here\n")
    else:
        print(f"\n  {GREEN}{BOLD}All steps succeeded.{RESET}")

    print("\n  Start the app with:")
    print(f"    {CYAN}streamlit run predictions.py{RESET}\n")

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
