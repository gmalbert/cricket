# Wicket Oracle — Copilot Instructions

## What this project is

IPL T20 cricket betting analytics app. A nightly pipeline fetches live data, runs ML models, and writes results to `cache/*.json`. A Streamlit app reads those files and renders seven pages. The app always works — if cache is missing it falls back to mock data.

## Key architecture rules

- **Cache-first, always.** Every page reads from `cache/*.json` via `utils/cache.py`. Never hit an API or do heavy computation inside a Streamlit page.
- **Mock fallbacks are for development only.** Mock data lives in `utils/data.py`. Never save mock data to cache files.
- **Pipeline writes cache; app only reads it.** No page should call any `save_cache` or write to disk.
- **One file per page.** Each `pages_app/*.py` exports a single `render()` function with no arguments.

## Project layout

```
predictions.py          # Streamlit entry point — sidebar + tab layout
pages_app/              # One render() function per page
pipeline/               # Data pipeline (run nightly, not by Streamlit)
  run_pipeline.py       # Step orchestrator
  fetch_cricsheet.py    # Historical ball-by-ball → team_form, player_stats, venue_stats
  fetch_fixtures.py     # CricketData.org → today's fixtures + schedule
  fetch_odds.py         # The Odds API → DraftKings implied probabilities
  fetch_weather.py      # Open-Meteo (no key) → venue weather
  feature_engineering.py
  run_models.py         # XGBoost + LightGBM predictions
  monte_carlo.py        # 10,000-trial playoff simulator
  reconcile_predictions.py  # Nightly: match predictions to actual results
utils/
  cache.py              # load_cache / save_cache / cache_exists / cache_status
  data.py               # IPL team/venue constants + mock fallback functions
fetch_data.py           # CLI wrapper to run the pipeline manually
cache/                  # Runtime JSON outputs (gitignored for large files)
.github/workflows/
  nightly.yml           # Runs fetch_data.py at 06:00 UTC daily
```

## Cache file registry

All known cache keys are declared in `CACHE_FILES` in `utils/cache.py`. Add new cache files there before using them. Current keys:

| Key | File | Written by |
|---|---|---|
| `todays_matches` | todays_matches.json | pipeline |
| `player_props` | player_props.json | pipeline |
| `schedule` | schedule.json | pipeline (raw fixtures) |
| `team_form` | team_form.json | fetch_cricsheet |
| `venue_stats` | venue_stats.json | fetch_cricsheet |
| `player_stats` | player_stats.json | fetch_cricsheet |
| `value_bets` | value_bets.json | pipeline |
| `playoff_probabilities` | playoff_probabilities.json | monte_carlo |
| `matchup_edge_history` | matchup_edge_history.json | pipeline |
| `prediction_log` | prediction_log.json | reconcile_predictions |
| `last_updated` | last_updated.json | pipeline (summary metadata) |

## Data conventions

- **Team names.** Use Cricsheet spellings in historical data (e.g. `"Royal Challengers Bangalore"` for pre-2024, `"Royal Challengers Bengaluru"` for 2024+). Normalise to the current name when displaying.
- **Match IDs.** Format: `"TEAM1_vs_TEAM2_YYYY-MM-DD"` (lowercase, underscores).
- **Win probabilities.** Always a float 0–1. `team1_win_prob + team2_win_prob == 1.0`.
- **Dates/times.** Store as ISO 8601 strings. Timestamps in cache include UTC offset or `Z` suffix.
- **Serialisation.** `json.dump(..., default=str)` is used everywhere — pandas Timestamps serialise to strings automatically.

## Streamlit patterns

- Use `st.tabs()` within a page for sub-sections, not nested expanders.
- Use `width='stretch'` on `st.dataframe()` and `st.plotly_chart()` (not the deprecated `use_container_width`).
- Load data at the top of `render()` with `load_cache("key")` and return early with `st.info(...)` if it is `None`.
- Keep `st.sidebar` usage only in `predictions.py`.

## Pipeline conventions

- Each `step_*` function in `run_pipeline.py` returns clean Python objects (lists/dicts), never writes to disk itself.
- `fetch_data.py` owns all disk writes via its `save()` helper.
- Pipeline steps must not raise unhandled exceptions — wrap in try/except, log the error, and return a safe empty value.
- `--skip-cricsheet` reuses the existing parquet if it is less than 23 hours old.
- `--dry-run` skips all disk writes and is safe to run in CI for smoke tests.

## ML models

- Trained models are stored in `cache/models/` (gitignored).
- If a model file is missing, `run_models.py` falls back to heuristic predictions so the pipeline never hard-fails.
- Feature vectors are built by `feature_engineering.py` and keyed on `match_id`.

## Environment variables

| Variable | Purpose |
|---|---|
| `ODDS_API_KEY` | The Odds API — DraftKings lines |
| `CRICKET_DATA_API_KEY` | CricketData.org — live fixtures |

Weather (Open-Meteo) needs no key. Missing keys produce warnings, not errors — the pipeline continues with empty data for that step.

## GitHub Actions

The nightly workflow (`.github/workflows/nightly.yml`) runs `python fetch_data.py --skip-cricsheet` and commits updated `cache/*.json` files back to `main`. Do not add steps that push to other branches or modify source files.
