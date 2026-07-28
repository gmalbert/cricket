# Wicket Oracle — Architecture

## Overview
IPL T20 cricket betting analytics app. A nightly pipeline fetches live data, runs ML models, and writes results to `cache/*.json`. The Streamlit app reads those files and renders seven pages. The app always works — if cache is missing it falls back to mock data.

## Data Flow
```
CricketData.org (fixtures)   Cricsheet (ball-by-ball)   The Odds API   Open-Meteo (weather)
        ↓                           ↓                         ↓               ↓
pipeline/fetch_fixtures.py   pipeline/fetch_cricsheet.py  fetch_odds.py  fetch_weather.py
        ↓                           ↓                         ↓               ↓
                            pipeline/run_pipeline.py
                                    ↓
                        pipeline/feature_engineering.py
                                    ↓
                            pipeline/run_models.py
                         (XGBoost + LightGBM predictions)
                                    ↓
                            pipeline/monte_carlo.py
                         (10,000-trial playoff simulator)
                                    ↓
                              cache/*.json
                                    ↓
                          predictions.py (Streamlit entry)
                          pages_app/*.py (7 pages)
```

## Architecture Rule: Cache-First
- Every page reads from `cache/*.json` via `utils/cache.py`
- Pipeline writes cache; app ONLY reads it
- Mock fallbacks in `utils/data.py` for development only (never saved to cache)

## ML Models
- **XGBoost + LightGBM** predictions (win probability per match)
- Fallback heuristic if model file missing (pipeline never hard-fails)
- Features: team form, venue stats, player stats, weather, H2H history
- Trained models stored in `cache/models/` (gitignored)

## Cache File Registry (`CACHE_FILES` in `utils/cache.py`)
| Key | File | Written by |
|-----|------|-----------|
| `todays_matches` | todays_matches.json | pipeline |
| `player_props` | player_props.json | pipeline |
| `team_form` | team_form.json | fetch_cricsheet |
| `venue_stats` | venue_stats.json | fetch_cricsheet |
| `player_stats` | player_stats.json | fetch_cricsheet |
| `value_bets` | value_bets.json | pipeline |
| `playoff_probabilities` | playoff_probabilities.json | monte_carlo |
| `prediction_log` | prediction_log.json | reconcile_predictions |
| `last_updated` | last_updated.json | pipeline summary |

## API Integrations
| Source | Purpose | Key |
|--------|---------|-----|
| CricketData.org | Live fixtures, schedules | `CRICKET_DATA_API_KEY` |
| The Odds API | DraftKings implied odds | `ODDS_API_KEY` |
| Open-Meteo | Venue weather (no key required) | None |
| Cricsheet | Historical ball-by-ball data | None (public) |

## Key Components
- `predictions.py` — Streamlit entry, sidebar + tab layout
- `pages_app/` — one `render()` function per page (no args)
- `pipeline/run_pipeline.py` — step orchestrator
- `pipeline/reconcile_predictions.py` — nightly match vs actuals
- `utils/cache.py` — `load_cache()`, `save_cache()`, `cache_exists()`, `cache_status()`
- `fetch_data.py` — CLI wrapper to run pipeline manually

## Nightly Automation
GitHub Actions (`.github/workflows/nightly.yml`) runs at 06:00 UTC daily: `python fetch_data.py --skip-cricsheet`
