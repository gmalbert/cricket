# Wicket Oracle — Cricket Betting Analytics Platform

## Overview
IPL T20 cricket betting analytics platform built with Streamlit. Provides win probabilities, player props projections, value bet identification, and statistical analysis for IPL 2026 matches.

## Stack
- **Frontend/Backend:** Python + Streamlit (single-process app)
- **Port:** 5000
- **Data:** Simulated/mock data mirroring real sources (Cricsheet, The Odds API, Open-Meteo)
- **Charts:** Plotly

## Project Structure
```
predictions.py            - Main Streamlit entry point
pages_app/
  todays_matches.py       - Page 1: Live fixtures + win probabilities
  player_props.py         - Page 2: Batter/bowler prop projections
  team_deep_dive.py       - Page 3: Team form + phase breakdown + H2H
  fixtures_table.py       - Page 4: Full schedule + points table + playoff probs
  value_bets.py           - Page 5: Aggregated best bets with Kelly sizing
  model_performance.py    - Page 6: Backtesting + calibration + confusion matrix
  statistics.py           - Page 7: Venue/batter/bowler/umpire profiles
utils/
  data.py                 - Data generation and helper functions
data_files/
  logo.png                - Wicket Oracle logo
docs/
  wicket-oracle-spec.md   - Full specification document
.streamlit/
  config.toml             - Streamlit server configuration
```

## Features
- Today's Matches with win probabilities vs DraftKings implied odds
- Toss tracker with live probability adjustment
- Weather card (Open-Meteo integration ready)
- Player props: batter runs + bowler wickets vs DK lines
- Team deep dive: form, phase breakdown, venue record, H2H
- Full IPL schedule with playoff probabilities (Monte Carlo)
- Value bets with Kelly Criterion sizing (25% fractional)
- Model performance backtesting (IPL 2024/2025)
- Venue, batter, bowler, and umpire statistical profiles

## Data Sources (per spec)
- Cricsheet (historical ball-by-ball)
- The Odds API (DraftKings lines)
- CricketData.org (live scores/squads)
- Open-Meteo (weather)
- ESPNCricinfo Statsguru (supplemental stats)

## Running
```bash
streamlit run predictions.py --server.port 5000 --server.address 0.0.0.0
```
