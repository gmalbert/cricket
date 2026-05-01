# Wicket Oracle — Nightly Data Pipeline

## Overview

The nightly pipeline fetches all external data, runs ML models, and writes
JSON cache files that the Streamlit app reads on every page load. This means
users never trigger expensive network calls or model inference — they always
see pre-computed results served instantly from `cache/*.json`.

## Pipeline Steps

| Step | Module | Output |
|---|---|---|
| 1 | `fetch_cricsheet` | Ball-by-ball IPL data → team form, player stats, venue stats |
| 2 | `fetch_fixtures` | Today's IPL fixtures from CricketData.org |
| 3 | `fetch_odds` | DraftKings implied probabilities from The Odds API |
| 4 | `fetch_weather` | Venue weather forecasts from Open-Meteo (free) |
| 5 | `feature_engineering` | Match + player feature vectors |
| 6 | `run_models` | XGBoost/LightGBM predictions |
| 7 | `run_pipeline` | Orchestrates all steps, writes `cache/*.json` |

## GitHub Actions

The pipeline runs automatically at **06:00 UTC daily** via
`.github/workflows/nightly.yml` — before the first IPL match of the day
(matches typically start ~09:00–10:00 UTC / 14:30–15:30 IST).

After a successful run the workflow commits updated `cache/*.json` files back
to the repository so the deployed Streamlit app picks them up automatically.

## Required GitHub Secrets

| Secret | Where to get it |
|---|---|
| `ODDS_API_KEY` | https://the-odds-api.com — free tier (500 req/month) |
| `CRICKET_DATA_API_KEY` | https://cricketdata.org — free tier available |

Add secrets at: **Repository → Settings → Secrets and variables → Actions**

Open-Meteo (weather) requires no API key.

## Running Locally

```bash
# Full pipeline (downloads Cricsheet, fetches odds + fixtures + weather, runs models)
python -m pipeline.run_pipeline

# Skip Cricsheet re-download if data is already fresh (<23h old)
python -m pipeline.run_pipeline --skip-cricsheet

# Dry run — run everything but do not write cache files
python -m pipeline.run_pipeline --dry-run
```

## Cache Files Written

| File | Contents |
|---|---|
| `cache/todays_matches.json` | Today's match predictions + DK odds comparison |
| `cache/player_props.json` | Batter runs + bowler wicket projections |
| `cache/team_form.json` | Last 10 T20 results per team |
| `cache/player_stats.json` | Rolling batter/bowler stats from Cricsheet |
| `cache/venue_stats.json` | First innings avg + chase win rate per venue |
| `cache/value_bets.json` | Aggregated best bets with Kelly sizing |
| `cache/model_performance.json` | Backtesting metrics (IPL 2024/2025) |
| `cache/last_updated.json` | Pipeline run timestamp + error summary |

## Fallback Behaviour

If `cache/*.json` files are missing (e.g. first deployment, pipeline hasn't
run yet), every Streamlit page falls back to **simulated mock data** so the
app remains fully functional. A warning banner in the sidebar indicates when
mock data is being used.
