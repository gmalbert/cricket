# Wicket Oracle — Model Suggested Enhancements

## Priority 1: Match Winner Model

### Current Limitations
- XGBoost and LightGBM ensemble is trained on team-level features only.
- Missing individual player impact (star batter / match-winning bowler availability).

### Improvements

**Player Impact Score**
- Encode presence/absence of top-3 run scorers and top-2 wicket takers for each team.
- Add `batting_impact_delta` and `bowling_impact_delta` features: sum of BCCI performance ratings for available XI vs. standard XI.

**Toss Effect**
- Toss winner decision (bat/field) is available pre-match. In certain high-dew venues (Eden Gardens, DY Patil), toss win + field first has a measurable edge.
- Add `toss_winner` and `toss_decision` as pre-match features.

**Phase-Level Features**
- Add rolling powerplay (overs 1–6), middle overs (7–15), and death overs (16–20) averages per team and venue.

## Priority 2: Total Score Model

### Current Limitations
- Venue average used as a single number; ignores seasonal variance.

### Improvements

**Seasonal Pitch Evolution**
- IPL tracks deteriorate across the tournament. Add `match_number_in_venue_this_season` as a proxy for pitch wear.

**Bowling Attack Strength**
- Add `bowling_attack_economy_rate_l5` and `avg_powerplay_wickets_l5` to complement batting-side features.

**DLS Awareness**
- Flag weather-affected matches from historical data; exclude them from training (distorts totals model).

## Priority 3: Monte Carlo Calibration

- Current playoff simulator uses raw win probabilities without confidence intervals.
- Bootstrap the Monte Carlo (run 1000× with sampled model parameters) to get 90% CI on playoff probabilities.

## Priority 4: Model Monitoring

### Accuracy Dashboard
- Add a `reconcile_predictions.py` step that compares match winner predictions to actual results nightly and writes to `cache/prediction_log.json`.
- Surface rolling accuracy and Brier score on the dashboard.

### Data Drift Detection
- Alert if any team's `avg_score_last5` shifts by > 20% week-over-week (injury/pitch change signal).
