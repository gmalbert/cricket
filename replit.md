# Wicket Oracle — Cricket Betting Analytics Platform

## Overview
IPL T20 cricket betting analytics platform built with Streamlit. Provides win probabilities, player props projections, value bet identification, Monte Carlo playoff simulations, and statistical analysis for IPL 2026 matches. A nightly GitHub Actions pipeline fetches real data and caches it so every page loads instantly.

## Stack
- **Frontend/Backend:** Python + Streamlit (single-process app)
- **Port:** 5000
- **Charts:** Plotly
- **Simulation:** NumPy Monte Carlo (10,000 trials)
- **Data:** Cache-first (real) → mock fallback

## Project Structure
```
predictions.py              - Main Streamlit entry point + sidebar cache status
pages_app/
  todays_matches.py         - Page 1: Live fixtures + win probabilities
  player_props.py           - Page 2: Batter/bowler prop projections
  team_deep_dive.py         - Page 3: Team form + phase breakdown + H2H
  fixtures_table.py         - Page 4: Full schedule + points table + Monte Carlo playoff
  value_bets.py             - Page 5: Aggregated best bets with Kelly sizing
  model_performance.py      - Page 6: Backtesting + calibration + confusion matrix
  statistics.py             - Page 7: Venue/batter/bowler/umpire profiles
utils/
  data.py                   - Cache-first data layer with mock fallbacks
  cache.py                  - Cache read/write helpers + CACHE_FILES registry
pipeline/
  fetch_cricsheet.py        - Ball-by-ball IPL data → team form, player stats, venue stats
  fetch_fixtures.py         - Live fixtures from CricketData.org
  fetch_odds.py             - DraftKings implied probabilities from The Odds API
  fetch_weather.py          - Venue weather from Open-Meteo (free, no key)
  feature_engineering.py   - Match + player feature vectors
  run_models.py             - XGBoost + LightGBM predictions
  monte_carlo.py            - 10,000-trial playoff probability simulator
  run_pipeline.py           - Nightly pipeline orchestrator (7 steps)
  README.md                 - Pipeline documentation + local run instructions
cache/
  *.json                    - Pre-computed predictions (written by nightly pipeline)
  raw/                      - Cricsheet parquet files (gitignored, large)
  models/                   - Trained model binaries (gitignored)
.github/workflows/
  nightly.yml               - GitHub Actions: runs at 06:00 UTC daily
data_files/
  logo.png                  - Wicket Oracle logo
docs/
  wicket-oracle-spec.md     - Full specification document
.streamlit/
  config.toml               - Streamlit server configuration
```

## Features
- Today's Matches with win probabilities vs DraftKings implied odds
- Weather card (Open-Meteo integration)
- Player props: batter runs + bowler wickets vs DK lines
- Team deep dive: form, phase breakdown, venue record, H2H
- Full IPL schedule with filter by team / upcoming only
- Monte Carlo playoff simulator (10,000 simulations):
  - Qualification probability per team
  - Title probability (league stage #1 finish)
  - Per-team finishing position distribution
  - Match importance scores (qualification swing per fixture)
  - Qualification status (guaranteed / contention / long shot / eliminated)
- Value bets with Kelly Criterion sizing (25% fractional)
- Model performance backtesting (IPL 2024/2025)
- H2H betting edge tracker (per-matchup and per-venue ROI vs DraftKings, edge-size bucket analysis, cumulative ROI curve)
- Venue, batter, bowler, and umpire statistical profiles
- Sidebar cache status banner (live data vs simulated)

## Nightly Pipeline (GitHub Actions)
Runs at 06:00 UTC daily via `.github/workflows/nightly.yml`.
Writes updated `cache/*.json` back to the repo after each run.

### Required GitHub Secrets
| Secret | Source |
|---|---|
| `ODDS_API_KEY` | https://the-odds-api.com (free tier) |
| `CRICKET_DATA_API_KEY` | https://cricketdata.org (free tier) |

Open-Meteo (weather) needs no key.

### Cache files written
`todays_matches.json`, `player_props.json`, `team_form.json`, `player_stats.json`,
`venue_stats.json`, `value_bets.json`, `playoff_probabilities.json`, `last_updated.json`

### Local run
```bash
python -m pipeline.run_pipeline                 # full run
python -m pipeline.run_pipeline --skip-cricsheet # skip re-download if fresh
python -m pipeline.run_pipeline --dry-run        # no writes
```

## Data Sources
- Cricsheet (historical ball-by-ball)
- The Odds API (DraftKings lines)
- CricketData.org (live scores/squads)
- Open-Meteo (weather)

## Running
```bash
streamlit run predictions.py --server.port 5000 --server.address 0.0.0.0
```

## Notes
- `style.map()` used instead of deprecated `style.applymap()`
- `use_container_width` deprecation warnings from Streamlit are harmless (upstream issue)
- Cache files in `cache/raw/` and `cache/models/` are gitignored (large binaries)
- All pages fall back to deterministic mock data when cache is absent
