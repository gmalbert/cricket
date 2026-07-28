> **AI Onboarding Guide** — See also `.github/copilot-instructions.md` for full coding conventions.

# Wicket Oracle (IPL Cricket) — Site Summary

## What This App Does

IPL T20 cricket betting analytics app. A nightly pipeline fetches live data, runs XGBoost and LightGBM models, and writes results to `cache/*.json`. The Streamlit app reads those cached files and renders seven pages. The app always works — if cache is missing, it falls back to mock data.

## Quick Start

```bash
# 1. Activate virtual environment
.\.venv\Scripts\Activate.ps1        # Windows
source .venv/bin/activate           # macOS/Linux

# 2. Run the data pipeline (populates cache/)
python fetch_data.py

# 3. Run the app
streamlit run predictions.py
```

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit (multi-page, 7 pages) |
| ML | XGBoost + LightGBM predictions |
| Simulation | Monte Carlo (10,000 iterations) for playoff probabilities |
| Data storage | JSON cache files (`cache/*.json`) |
| Scheduling | GitHub Actions (nightly at 06:00 UTC) |

## Key Files

| File | Purpose |
|---|---|
| `predictions.py` | Streamlit entry point — sidebar + tab layout |
| `pages_app/*.py` | One `render()` function per page — no arguments |
| `pipeline/run_pipeline.py` | Step orchestrator for nightly data fetch |
| `pipeline/fetch_cricsheet.py` | Historical ball-by-ball data → team form, player stats, venue stats |
| `pipeline/fetch_fixtures.py` | CricketData.org → today's fixtures + schedule |
| `pipeline/fetch_odds.py` | The Odds API → DraftKings implied probabilities |
| `pipeline/run_models.py` | XGBoost + LightGBM predictions |
| `pipeline/monte_carlo.py` | 10,000-trial playoff simulator |
| `utils/cache.py` | `load_cache()` / `save_cache()` — **all** data access goes through here |
| `utils/data.py` | IPL team/venue constants + mock fallback functions |
| `fetch_data.py` | CLI wrapper to run the pipeline manually |

## Cache File Registry

All cache keys are declared in `CACHE_FILES` in `utils/cache.py`. Never add a new cache file without registering it there first.

| Key | File | Written by |
|---|---|---|
| `todays_matches` | `todays_matches.json` | pipeline |
| `team_form` | `team_form.json` | fetch_cricsheet |
| `player_stats` | `player_stats.json` | fetch_cricsheet |
| `value_bets` | `value_bets.json` | pipeline |
| `playoff_probabilities` | `playoff_probabilities.json` | monte_carlo |
| `prediction_log` | `prediction_log.json` | reconcile_predictions |

## Data Flow

1. **Historical stats**: `fetch_cricsheet.py` → Cricsheet ball-by-ball data → `team_form.json`, `player_stats.json`, `venue_stats.json`
2. **Today's fixtures**: `fetch_fixtures.py` → CricketData.org → `todays_matches.json`
3. **Odds**: `fetch_odds.py` → The Odds API → DraftKings implied probabilities
4. **Weather**: Open-Meteo API (no key required) → venue weather
5. **Predictions**: `run_models.py` → XGBoost + LightGBM → `value_bets.json`
6. **Simulation**: `monte_carlo.py` → 10,000 playoff simulations → `playoff_probabilities.json`
7. **UI**: Each page calls `load_cache("key")` → renders; returns early with `st.info()` if `None`

## Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `ODDS_API_KEY` | The Odds API — DraftKings lines | Required for live odds |
| `CRICKET_DATA_API_KEY` | CricketData.org — live fixtures | Required for today's games |

## Critical Architecture Rules

- **Cache-first, always** — every page reads from `cache/*.json` via `utils/cache.py`; never hit an API from a page
- **Pipeline writes; app reads** — no page should call `save_cache()` or write to disk
- **Mock fallbacks are for development only** — never save mock data to cache files
- **One file per page** — each `pages_app/*.py` exports a single `render()` function with no arguments

## Common Gotchas

- Open-Meteo (weather) requires no API key and never fails — use it freely
- Missing `CRICKET_DATA_API_KEY` or `ODDS_API_KEY` produces warnings but the pipeline continues with empty data
- Team names in Cricsheet use historical spellings (e.g., "Royal Challengers Bangalore" pre-2024 vs "Royal Challengers Bengaluru" 2024+) — normalize to current name for display
- Match IDs format: `"TEAM1_vs_TEAM2_YYYY-MM-DD"` (lowercase, underscores)
