# Wicket Oracle — Cricket Betting Analytics Platform
## Specification & Build Guide

---

## Overview

**Site name:** Wicket Oracle  
**Domain suggestion:** wicket-oracle.com  
**Primary focus:** IPL T20 (launch target), expanding to international T20I and BBL  
**Stack:** Streamlit (matching rest of Betting Oracle suite)  
**Launch window:** Build during IPL 2026 season (live through May 31, 2026)

---

## Data Sources

### 1. Cricsheet (Primary Historical / Training Data)
- **URL:** https://cricsheet.org/downloads/
- **Cost:** Free, no API key required
- **Format:** CSV, JSON, or YAML — use CSV for pandas compatibility
- **Coverage relevant to model:**
  - 1,211 IPL matches (2008–2025) — ball-by-ball
  - 5,192 T20 Internationals — ball-by-ball
  - 662 Big Bash League matches
  - 407 Caribbean Premier League matches
  - 469 Bangladesh Premier League matches
  - 119 Lanka Premier League matches
- **Download method:** Direct bulk ZIP download per competition, no scraping needed
- **Key fields per ball:** match_id, season, start_date, venue, innings, over, ball, batting_team, bowling_team, batter, bowler, runs_off_bat, extras, wicket_type, player_dismissed, fielders_involved
- **Python access:** `pandas.read_csv()` after unzipping, or use the `cricketdata` R package's `fetch_cricsheet()` if preferred

### 2. The Odds API (Live Betting Lines)
- **URL:** https://the-odds-api.com
- **Cost:** Free tier (500 requests/month); ~$20/month for 10K requests
- **Cricket coverage:** IPL, Test matches, Big Bash, and more
- **US bookmakers included:** DraftKings, FanDuel, BetMGM, Caesars
- **Endpoints to use:**
  - `/v4/sports/cricket_ipl/odds` — moneyline + match winner
  - `/v4/sports/cricket_ipl/scores` — live scores
  - **Note:** Same API you already use in Betting Cleanup and Betting Baseline — zero new integration work

### 3. CricketData.org (formerly CricAPI) (Live Scores + Squads)
- **URL:** https://cricketdata.org
- **Cost:** Free tier available; paid from $5.99/month
- **Use case:** Live match scores, current squads, player availability, toss results
- **Key free endpoints:**
  - `currentMatches` — live and recent match data
  - `matchInfo` — toss winner, venue, squad lists
- **Caching strategy:** 10-minute cache on live data (same pattern as Betting Cleanup's 30-min ESPN cache)

### 4. ESPNCricinfo / Statsguru (Supplemental Player Stats)
- **URL:** https://stats.espncricinfo.com/ci/engine/stats/
- **Cost:** Free (scraping, no official API)
- **Use case:** Career batting/bowling averages, surface splits, recent form (last 10 innings)
- **Scraping approach:** BeautifulSoup + requests, target Statsguru query URLs
  - Example: `https://stats.espncricinfo.com/ci/engine/stats/index.html?class=6;template=results;type=batting` (T20 batting stats)
- **Rate limit:** Be conservative — 1 request/2 seconds, cache aggressively to disk

### 5. Open-Meteo (Weather — same as Fairway Oracle)
- **URL:** https://open-meteo.com/en/docs
- **Cost:** Free, no API key
- **Use case:** Temperature, humidity, dew point, wind speed at venue coordinates
- **Why it matters:** Dew in evening matches significantly affects chasing — a known +1.4 RPO swing in humid conditions (confirmed by IPL analytics community)

---

## Data Model & Feature Engineering

### Match-Level Features (for win probability and match totals)

| Feature | Source | Notes |
|---|---|---|
| `team1_avg_score_last5` | Cricsheet | Rolling 5-match average first innings score |
| `team2_avg_score_last5` | Cricsheet | Rolling 5-match average first innings score |
| `team1_win_rate_venue` | Cricsheet | Win % at this specific ground, last 3 seasons |
| `team2_win_rate_venue` | Cricsheet | Same |
| `team1_win_rate_vs_team2` | Cricsheet | H2H win rate, T20 format only |
| `toss_winner_is_team1` | CricketData | Binary: 1 if team1 won toss |
| `toss_decision` | CricketData | bat/field — encode as binary |
| `venue_avg_first_innings_score` | Cricsheet | Historical average at ground |
| `venue_chasing_win_rate` | Cricsheet | % of matches won chasing at this venue |
| `team1_powerplay_avg_runs` | Cricsheet | Overs 1–6 average runs scored, last 10 matches |
| `team2_powerplay_avg_runs` | Cricsheet | Same |
| `team1_death_overs_economy` | Cricsheet | Overs 16–20 economy rate (bowling), last 10 |
| `team2_death_overs_economy` | Cricsheet | Same |
| `team1_top3_batting_form` | Cricsheet + Cricinfo | Avg runs of top-3 batters in last 5 innings each |
| `team2_top3_batting_form` | Cricsheet + Cricinfo | Same |
| `temperature` | Open-Meteo | At match start time |
| `humidity` | Open-Meteo | High humidity = dew factor |
| `dew_flag` | Derived | Binary: humidity > 75% AND evening match |
| `days_rest_team1` | Cricsheet | Days since last match |
| `days_rest_team2` | Cricsheet | Same |
| `is_knockout_stage` | CricketData | Playoff/final flag — pressure game adjustment |
| `ground_altitude` | Static lookup | Same approach as Gridlocked Oracle |

### Player-Level Features (for player props — runs scored, wickets taken)

| Feature | Source | Notes |
|---|---|---|
| `batter_avg_last10_t20` | Cricsheet | Rolling average runs in last 10 T20 innings |
| `batter_strike_rate_last10` | Cricsheet | Balls faced / runs * 100 |
| `batter_vs_bowler_type` | Cricsheet | Avg vs pace vs spin, derived from ball-by-ball |
| `batter_powerplay_avg` | Cricsheet | Avg runs in overs 1–6 when opening |
| `bowler_economy_last5` | Cricsheet | Rolling economy rate |
| `bowler_wickets_per_match_last5` | Cricsheet | Rolling wicket rate |
| `bowler_vs_left_right_handers` | Cricsheet | Ball-by-ball split |
| `bowler_death_over_economy` | Cricsheet | Overs 16–20 only |
| `pitch_type` | Static lookup + Cricinfo | Flat/turning/seaming per ground |
| `is_home_ground` | Static lookup | IPL franchise home venues |
| `batting_position` | Cricsheet | Expected position 1–11 from squad order |

### Target Variables

- **Match winner:** Binary classification (team1 wins = 1)
- **Total runs (over/under):** Regression on combined first + second innings runs
- **First innings score:** Regression — useful for totals betting
- **Individual batter runs:** Regression (for player props — "player to score 30+")
- **Individual bowler wickets:** Regression (for "bowler to take 2+ wickets")
- **Player of the Match:** Multi-class classification (stretch goal)

---

## ML Model Architecture

### Model 1: Match Winner (Win Probability)
- **Algorithm:** XGBoost classifier + LightGBM soft-voting ensemble (same as Pitch Oracle soccer suite)
- **Input:** Match-level features above
- **Output:** P(team1 wins), P(team2 wins)
- **Training split:** Temporal — train on IPL 2008–2023, validate on 2024, test on 2025
- **Key risk:** Toss leakage — exclude toss result from pre-toss predictions; add it as a live feature post-toss
- **Calibration:** Platt scaling to convert raw probabilities to well-calibrated betting probabilities

### Model 2: First Innings Total (Runs Regression)
- **Algorithm:** XGBoost regressor
- **Input:** Pre-match features only (no toss/live data)
- **Output:** Predicted first innings runs ± confidence interval
- **Use case:** Compare to DraftKings over/under line for value detection

### Model 3: Player Props (Batter Runs Over/Under)
- **Algorithm:** Separate XGBoost regressors per role (opener, middle-order, finisher)
- **Input:** Player-level features + match context features
- **Output:** Predicted runs; flag if model disagrees with DraftKings prop line by >15%
- **Training data:** Ball-by-ball Cricsheet — aggregate per batter per innings

### Model 4: Bowler Wickets (Over/Under)
- **Algorithm:** XGBoost regressor + Poisson rate model (wickets are count data)
- **Input:** Bowler features + batter lineup features
- **Output:** Expected wickets; compare to DraftKings "2+ wickets" prop

### Feature Selection
- Use SHAP (same as Gridlocked Oracle) for interpretability
- Apply temporal cross-validation — never train on future data
- RFE to trim low-importance features before final model

---

## App Pages (Streamlit)

### Page 1: Today's Matches
- Live IPL fixtures for today with predicted win probabilities (pre-toss and post-toss versions)
- Model probability vs. DraftKings implied probability — green highlight when edge > 5%
- Venue weather card (temperature, humidity, dew flag)
- Toss tracker: update predictions live after toss is announced
- "Elite Pick" badge when model edge > 10% (matching Gridiron Oracle's Elite/Strong tiers)

### Page 2: Player Props
- Per-match batter runs projections vs. DraftKings highest score / over-under lines
- Per-match bowler wicket projections vs. DraftKings lines
- Green/red edge indicator (same UI pattern as Oracle on Ice's Value Finder)
- Filter by: match, role (opener/middle/bowler), confidence tier

### Page 3: Team Deep Dive
- Rolling form table: last 10 T20 results, avg score, powerplay avg, death overs economy
- Phase-by-phase scoring breakdown: powerplay / middle overs / death overs
- Venue record for each team
- Head-to-head history (last 10 meetings, T20 format only)

### Page 4: Fixtures & Tournament Table
- Full IPL 2026 schedule with predicted win probabilities for each remaining match
- Points table with NRR (Net Run Rate)
- Playoff probability for each team (Monte Carlo simulation — same approach as Gridlocked Oracle's Monte Carlo feature selection)

### Page 5: Value Bets
- Aggregated best-bet table across all today's and upcoming matches
- Sorted by model edge over implied probability
- Includes match winner, total runs over/under, and player prop bets
- Kelly Criterion bet sizing (fractional Kelly at 25%, matching Fairway Oracle)

### Page 6: Model Performance & Backtesting
- Historical accuracy table: IPL 2024 and 2025 seasons
- ROI tracker by bet type (match winner, totals, props)
- Calibration curve: how well model probabilities match actual outcomes
- Confusion matrix for match winner classification

### Page 7: Statistics
- Venue profiles: avg scores, chasing success rate, dew impact at each IPL ground
- Batter profiles: career T20 stats, surface splits, recent form chart
- Bowler profiles: economy trends, phase-by-phase analysis
- Referee/umpire equivalent: umpire run-rate tendencies (wide calling, LBW rates)

---

## GitHub Actions Pipeline

```yaml
# Suggested nightly pipeline (matching Betting Cleanup / Gridiron Oracle pattern)
schedule: "0 6 * * *"  # 6 AM UTC = before first IPL match of day

jobs:
  update_predictions:
    - Download latest Cricsheet IPL data (check for new matches)
    - Fetch today's fixtures from CricketData.org free API
    - Pull current DraftKings IPL odds from The Odds API
    - Fetch weather for each venue from Open-Meteo
    - Run feature engineering pipeline
    - Generate today's match predictions (pre-toss)
    - Generate player prop projections
    - Cache results to JSON (same pattern as other Betting Oracle apps)
    - Update tournament table and playoff probabilities
```

---

## DraftKings Market Coverage for Value Detection

Based on confirmed DraftKings IPL market structure:

| DK Market | Wicket Oracle Model | Edge Detection Method |
|---|---|---|
| Match Winner (moneyline) | Model 1 win probability | Compare P(model) vs P(implied from DK odds) |
| Total Runs Over/Under | Model 2 first innings total | Model projected total vs DK line |
| Highest Score (player prop) | Model 3 batter runs | Model projected runs vs DK over/under |
| Most Wickets (player prop) | Model 4 bowler wickets | Model projected wickets vs DK over/under |
| Tournament Winner (future) | Playoff probability model | Monte Carlo tournament simulation |

---

## Scope Decisions & Rationale

**Why T20 / IPL first, not Test or ODI:**
- IPL has the most Cricsheet historical data (1,211 matches), the most DraftKings markets, and is live right now through May 31, 2026
- T20 matches complete in ~3 hours so the feedback loop for model validation is fast
- Test matches require a fundamentally different model (5-day state, weather over multiple days, draw outcomes) — treat as a future expansion

**Why not IPL DFS / Pick 6:**
- DraftKings does not currently offer a cricket Pick 6 product; focus on sportsbook markets
- Could add fantasy points projection as a future page

**Expansion roadmap after IPL:**
1. ICC T20 World Cup (next major tournament)
2. Big Bash League (Australian summer — Dec–Feb)
3. T20 Internationals year-round
4. Pakistan Super League

---

## Key Differences from Existing Soccer/NFL Models

1. **Innings structure:** Unlike soccer (90 min continuous), cricket has discrete innings. Model 1 (pre-match) and Model 1b (post-first-innings, in-game update) should be separate.
2. **Toss is a feature, not leakage:** Toss outcome is genuinely predictive (chasing win rate varies significantly by venue) — include it as a live feature after toss, exclude from pre-toss predictions.
3. **No draws in T20:** Binary outcome only (unlike soccer 1X2), simplifying the classification task.
4. **Phase segmentation:** Powerplay (1–6), middle overs (7–15), death overs (16–20) are distinct tactical phases. Aggregate features by phase, not just match totals.
5. **DLS method:** In rain-affected matches, DLS-adjusted targets make historical totals non-comparable. Flag and exclude DLS matches from totals model training data.
