# Wicket Oracle (IPL Cricket) — Next 5 Features to Implement

> **Based on:** Codebase gap analysis as of July 2025

---

## Feature 1: Player Availability / Impact Score Feature

**Why:** IPL is highly dependent on star player availability. A team missing their primary spinner or power hitter can swing win probability by 10–15%. The `pipeline/` already fetches fixture data — adding player availability would significantly improve pre-match predictions.

**How:**
1. Add `pipeline/fetch_player_availability.py` that calls CricketData.org's squad/playing XI endpoint for each today's match
2. Maintain `utils/key_players.csv` (manually updated per season): team, player_name, role, impact_rating (1–10)
3. Compute `home_impact_score` = sum of available key players' impact ratings; `away_impact_score` = same
4. Write to `cache/todays_matches.json` (extend the schema) — display availability warnings on the Today page

**Complexity:** Medium

---

## Feature 2: Venue Dew Factor Feature

**Why:** IPL matches in India are heavily affected by dew in the second innings (ball becomes slippery → spinners lose effectiveness → chasing teams have a big advantage). Dew probability is a real signal that affects toss strategy and team selection.

**How:**
1. In `pipeline/fetch_weather.py`, add `dew_point_temperature` to the Open-Meteo request (already free, no key)
2. Compute `dew_risk_score`: high dew risk if `dew_point > 15°C` at match time (evening)
3. Add `dew_risk_score` to the feature vector in `pipeline/feature_engineering.py`
4. Display "High Dew Risk — Chasing team favored" contextual badge on the Today page

**Complexity:** Low

---

## Feature 3: First-Innings Score Range Predictor

**Why:** "Will the first innings score be over/under 165?" is a high-interest bet type in IPL. The model currently predicts win probability but not innings total — a separate LightGBM regression on `total_runs` per innings would enable totals bets.

**How:**
1. In `pipeline/feature_engineering.py`, build innings-total feature set: venue run rate, batting team last-5 first innings scores, bowling team economy rate, pitch report (hard/dry/soft)
2. In `pipeline/run_models.py`, train a LightGBM regressor for first-innings total (separate from win probability model)
3. Add `first_innings_predicted_total` to `todays_matches.json`
4. Display on Today page: "Predicted first innings: 172 (Over 165 recommended)"

**Complexity:** Medium

---

## Feature 4: Best Bets JSON Export for Sports-Picks-Grid

**Why:** If `cricket` is to be added to the sports-picks-grid aggregator, a consistent `data_files/best_bets_today.json` export is needed. The pipeline already computes value bets in `value_bets.json` — this is a schema translation step.

**How:**
1. Add `pipeline/export_best_bets.py` that reads `cache/value_bets.json`
2. Translate to the unified schema: `meta` + `bets` array with `game_date`, `game`, `bet_type` (`moneyline`), `pick`, `confidence`, `edge`, `tier`
3. Write to `data_files/best_bets_today.json`
4. Add to the nightly pipeline as the final step in `pipeline/run_pipeline.py`

**Complexity:** Low

---

## Feature 5: Head-to-Head Historical Deep Dive Page

**Why:** IPL franchises have rich head-to-head histories spanning 15+ seasons. The current app shows win probability but no historical context. A dedicated H2H page (when a specific match is selected) would significantly improve user engagement.

**How:**
1. Add a `pages_app/head_to_head.py` page with a `render(home_team, away_team)` function
2. Load from `cache/team_form.json` — filter to matches between these two teams
3. Display: last 10 H2H results, venue-specific win rates, average first innings score in this matchup, toss win advantage
4. Wire into the Today page as a "View H2H" button on each match card that navigates to this page

**Complexity:** Medium
