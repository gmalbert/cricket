# Wicket Odds — Production Readiness Plan

## Production goal

The product should only show a competition or prediction when its data pipeline has successfully produced and validated it. Empty, stale, simulated, and unavailable data must be visibly distinct.

Production readiness means:

- No silent mock data in the live environment.
- Every published prediction has valid fixture identity, historical coverage, model version, odds timestamp, and source provenance.
- Competition status accurately explains why no prediction exists.
- The UI prioritizes trustworthy live output over feature breadth.
- Pipeline failures are observable and recoverable.
- A prediction can later be settled and scored.

## Phase 0 — Freeze the truth contract

Define the production states:

```text
not_enabled
not_run
fetch_failed
no_fixtures
no_draftkings_market
historical_data_insufficient
model_not_ready
no_qualifying_bets
ready
stale
```

Each competition should expose:

- Last successful pipeline run
- Fixture count
- DraftKings event count
- Historical match count and seasons
- Team/player identity rates
- Model version
- Qualifying bet count
- Error details
- Data age

Initially enable only competitions that pass the complete gate. International T20 is the likely first candidate, subject to a verified end-to-end run. Keep the remaining registry entries visible as planned or disabled, not as active coverage.

### Exit criteria

- A reviewer can distinguish live, stale, simulated, unavailable, and not-yet-enabled data immediately.
- A competition cannot be marked ready without evidence from every required stage.

## Phase 1 — Remove misleading behavior

Primary files:

- `utils/data.py`
- `predictions.py`
- `utils/cache.py`

Actions:

1. Add an explicit environment mode:
   - `APP_ENV=development`
   - `APP_ENV=production`
2. In production, never fall back to mock matches, bets, props, team form, standings, or model history.
3. In development, allow mock data only with a prominent `SIMULATED DATA` badge.
4. Add cache metadata to every output:
   - `generated_at`
   - `source_run_id`
   - `source_status`
   - `data_as_of`
   - `schema_version`
   - `is_mock`
5. Treat empty caches and stale caches differently.

### Exit criteria

- An empty pipeline cannot produce realistic-looking live matches.
- No page presents simulated content as a verified recommendation.

## Phase 2 — Make the pipeline deterministic and reliable

Primary file:

- `pipeline/run_pipeline.py`

Current problems include inconsistent cache freshness, empty current outputs, and broad exception handling that allows a run to continue without a usable product result.

Actions:

1. Give every run a unique `run_id`.
2. Write a run manifest containing:
   - Start and end time
   - Git commit
   - Environment
   - API source results
   - Counts at every stage
   - Errors and warnings
   - Output hashes
3. Separate fetch errors, empty valid responses, unmatched data, model failures, and publish-gate failures.
4. Use atomic cache publication:
   - Write to a temporary run directory.
   - Validate all outputs.
   - Promote the run only if required outputs pass.
5. Preserve the last known good production cache if a new run fails.
6. Apply freshness thresholds appropriate to fixtures, odds, historical data, and model artifacts.
7. Do not treat a pipeline run that produced zero publishable matches as a successful product run.

### Exit criteria

- A failed run cannot overwrite a valid production cache.
- Every run has an auditable manifest.
- The app can state exactly which pipeline stage failed.

## Phase 3 — Finish competition-aware ingestion

Primary files:

- `pipeline/competitions.py`
- `pipeline/fetch_fixtures.py`
- `pipeline/fetch_odds.py`
- `pipeline/fetch_cricsheet.py`
- `pipeline/normalization.py`

Actions:

1. Make the registry the single source of truth for competition slug, format, gender, odds key, historical dataset, supported markets, enablement state, and minimum thresholds.
2. Fixtures:
   - Use series/schedule endpoints where available.
   - Preserve source competition identifiers.
   - Normalize team, venue, timezone, date, and match status.
   - Handle postponed, abandoned, and completed matches.
3. Odds:
   - Fetch each enabled sport key independently.
   - Preserve sport key, event ID, bookmaker, market, selection, price, and timestamp.
   - Never assume a sport key guarantees DraftKings coverage.
4. Identity resolution:
   - Build explicit team aliases.
   - Build player aliases.
   - Add confidence scores.
   - Reject low-confidence fixture matches rather than guessing.
5. Historical coverage:
   - Record seasons, matches, teams, players, and identity rates per competition.
   - Separate T20, ODI, Test, women’s, and men’s datasets.

### Exit criteria

- A non-IPL fixture can flow through without code changes.
- A DraftKings event is matched to the correct fixture with alias tests.
- Every competition produces a truthful status report even when it produces no picks.

## Phase 4 — Establish model validity

Historical availability must not be treated as equivalent to model readiness.

Actions:

1. Define model boundaries:
   - Shared T20 base model with competition calibration
   - Separate ODI model
   - Separate Test model
   - Separate women’s calibration/model
   - Tournament shrinkage for small samples
2. Version all model artifacts with model name, training date, data range, feature schema, competition/format/gender, and calibration metrics.
3. Add validation for Brier score, log loss, calibration, accuracy, and market-implied baseline comparison.
4. Add leakage checks for post-match data, odds timing, and historical cutoff dates.
5. Add publish gates for sample size, identity coverage, model artifact, calibration, fixture/odds match confidence, and market freshness.
6. Remove or isolate synthetic calculations. Generated props and mock player profiles must not be presented as sportsbook-backed recommendations.

### Exit criteria

- Every published prediction can be reproduced from recorded inputs.
- The model is evaluated against a baseline with documented limitations.
- A competition cannot become ready solely because a parquet file exists.

## Phase 5 — Build settlement and performance tracking

Primary areas:

- `pipeline/reconcile_predictions.py`
- `pages_app/model_performance.py`
- Prediction-log and odds-history cache schemas

Actions:

1. Persist each published pick with fixture ID, competition, market, selection, model probability, price, implied probability, edge, timestamp, model version, and source run ID.
2. Fetch and normalize final results.
3. Settle wins, losses, pushes/voids, and abandoned/postponed matches.
4. Preserve first observed, latest pre-match, and closing prices.
5. Report CLV, calibration, ROI, accuracy, sample size, and performance by competition and edge tier.

### Exit criteria

- No pick is included in performance results without a settlement status.
- Missing or bad result data is marked unresolved rather than counted as a loss.

## Phase 6 — Redesign the product UI

Primary files:

- `predictions.py`
- `pages_app/todays_matches.py`
- `pages_app/value_bets.py`

Recommended structure:

1. Replace the cramped nine-tab layout with a focused dashboard, sidebar navigation, and grouped secondary analysis pages.
2. Make the homepage answer immediately:
   - Are there verified matches today?
   - Are there verified value bets?
   - Is the data fresh?
3. Replace the long sidebar list with a compact coverage table:

   | Competition | Status | Fixtures | DK markets | Data age |
   |---|---|---:|---:|---:|

4. Use plain-language statuses:
   - Live and ready
   - Fixtures found, no DraftKings market
   - Historical data not ready
   - Pipeline has not run
   - No qualifying bets today
5. Make unavailable pages useful by explaining why content is unavailable, showing the last successful run, and avoiding fake charts or bets.
6. Improve match cards with verified/live badge, competition and format, timezone, market freshness, model version, and a clear no-market state.
7. Test desktop, tablet, and narrow-width layouts.

### Exit criteria

- No clipped navigation.
- No fake-looking empty charts.
- Users can distinguish live predictions from unavailable or simulated content immediately.

## Phase 7 — Testing and CI

The current test suite must first run from a clean checkout; the present shell does not have `pytest` available.

Add:

1. Unit tests for the registry, aliases, normalization, status classification, cache freshness, probability bounds, model metadata, and settlement rules.
2. Integration tests for fixture-to-odds matching and fixture-to-published-prediction flow.
3. Failure tests proving that a failed fetch preserves the last good cache.
4. Contract tests for cache schemas, required fields, schema versions, and backward compatibility.
5. UI smoke tests for live, empty, stale, unavailable, and mock states.
6. CI checks for formatting, type checking, tests, pipeline dry run, cache validation, security scanning, and deployment smoke tests.

### Exit criteria

- Tests run from a clean checkout.
- CI blocks deployment on schema, pipeline, or UI smoke-test failures.
- At least one live-data scenario and one no-data scenario are covered end to end.

## Phase 8 — Deployment and operations

Actions:

1. Separate local, staging, and production environments.
2. Store API keys only in environment secrets.
3. Schedule the pipeline independently from the UI.
4. Deploy the app from a known artifact or commit.
5. Monitor pipeline success/failure, data age, fixture count, DraftKings match count, published picks, API errors, and app exceptions.
6. Alert on stale runs, sudden zero fixtures, sudden zero odds, schema mismatches, and unexpected model output.
7. Add rollback by promoting the previous known-good cache, reverting the app artifact, or disabling one competition independently.
8. Document an operational runbook for API failure, bad data, stale odds, model failure, settlement failure, and emergency disablement.

### Exit criteria

- A failed nightly job does not take down the dashboard.
- Operators can identify the failure without reading application source code.
- A competition can be disabled without disabling the entire app.

## Recommended rollout order

1. Production truthfulness and mock-data isolation.
2. Atomic cache publication and run manifests.
3. End-to-end International T20 verification.
4. UI redesign around live status.
5. Settlement and model-performance accuracy.
6. CI and integration tests.
7. Staged deployment.
8. Add ODI, Big Bash, The Hundred, and T20 Blast one at a time.
9. Add PSL, CPL, SA20, MLC, and LPL only after the same gates pass.
10. Treat Tests and women’s competitions as separate modeling products, not simple registry additions.

## Definition of done

The first production release is complete when:

- One competition reliably produces verified live predictions.
- Empty days are shown as empty, not simulated.
- Every status is evidence-backed.
- The last known good data survives failed runs.
- Predictions are logged and later settled.
- The UI is readable at normal desktop and narrow widths.
- CI passes from a clean checkout.
- Monitoring and rollback are operational.
- Additional competitions are enabled by passing documented gates, not merely by adding them to the registry.
