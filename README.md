# Wicket Oracle 🏏

**Production-ready cricket betting analytics** — win probability, player props, value bets, and playoff forecasts backed by verified data.

---

## What is Wicket Oracle?

Wicket Oracle is a production-grade web app for cricket bettors who want data-driven insights. Every day before matches start, a nightly pipeline pulls the latest fixtures, weather, and DraftKings lines, then runs validated predictions. You see, side by side, what the model thinks will happen and what the bookmaker is pricing — so you can spot the gaps.

**Production Features:**
- ✅ **No mock data in production** — Never shows simulated predictions as real
- ✅ **Atomic cache updates** — Failed pipeline runs preserve last known good data
- ✅ **Full audit trail** — Every run tracked with manifest, errors, and data lineage
- ✅ **Competition-aware** — Per-competition status tracking (ready/stale/no_fixtures/etc.)
- ✅ **Model validation** — Predictions only published if they pass 6 validation gates
- ✅ **Performance tracking** — Settled predictions scored with Brier, calibration, ROI, CLV
- ✅ **Comprehensive testing** — Unit tests, integration tests, CI/CD with GitHub Actions

---

## What's inside

**Today's Matches**
Win probabilities for each match, compared against current DraftKings lines. Includes venue stats and weather conditions at match time. Each prediction shows model version and verification status.

**Player Props**
Projected runs for key batters and wickets for key bowlers, benchmarked against DraftKings over/under lines. Each prop is labelled Low / Medium / High confidence.

**Value Bets**
A ranked shortlist of bets where the model's edge over the bookmaker is largest — match winners, run totals, and player props in one place, with Kelly Criterion stake sizes. Only shows bets meeting edge threshold (>5%) and data quality gates.

**Team Deep Dive**
Recent form, batting and bowling breakdowns by phase of play (powerplay / middle overs / death), head-to-head records, and venue-specific performance for any team in the competition.

**Fixtures & Table**
The full schedule with results, live points table, and a playoff probability simulator that runs 10,000 season scenarios to show each team's chances of making the top four.

**Model Performance**
A running scorecard of how predictions have performed. Rolling accuracy, Brier score, calibration metrics, cumulative ROI, closing line value (CLV), and full match-by-match settlement log.

**Statistics**
Deep-dive profiles for every venue, batter, bowler, and umpire based on historical ball-by-ball data.

---

## Getting started

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the app
```bash
streamlit run predictions.py
```

The app works straight away in **development mode** with simulated data so you can explore every page immediately.

### 3. Connect live data (production mode)

To see real predictions, you need two free API keys:

| Key | Where to get it |
|---|---|
| `ODDS_API_KEY` | [the-odds-api.com](https://the-odds-api.com) |
| `CRICKET_DATA_API_KEY` | [cricketdata.org](https://cricketdata.org) |

Create a `.env` file (never commit this):
```bash
APP_ENV=production
ODDS_API_KEY=your_key_here
CRICKET_DATA_API_KEY=your_key_here
```

Then run the data pipeline:
```bash
python fetch_data.py
```

After that, the pipeline runs automatically every morning at 06:00 UTC via GitHub Actions, so the app always has fresh data.

**Important:** In production mode (`APP_ENV=production`), the app will never show mock data. If the pipeline hasn't run or cache is missing, pages will display "No data available" instead of fake predictions.

---

## Production Architecture

### Pipeline Workflow

1. **Fetch Cricsheet** — Historical ball-by-ball data → team form, player stats, venue stats
2. **Fetch Fixtures** — CricketData.org → today's matches + full schedule
3. **Fetch Odds** — The Odds API → DraftKings implied probabilities
4. **Fetch Weather** — Open-Meteo (no key required) → venue weather forecasts
5. **Feature Engineering** — Build model features from historical and current data
6. **Run Models** — XGBoost + LightGBM predictions (with validation)
7. **Monte Carlo** — 10,000-trial playoff probability simulator
8. **Reconcile Predictions** — Match predictions to actual results for performance tracking

### Data Flow

```
[APIs] → [Pipeline] → [Atomic Cache] → [Streamlit App]
                          ↓
                    [Run Manifests]
```

- Pipeline writes to `cache/runs/{run_id}/` during execution
- On success, atomically promotes to production cache with backup
- On failure, preserves last known good cache
- Every run tracked with full manifest (errors, warnings, counts, hashes)

### Production States

Each competition tracked with granular status:
- `ready` — Live predictions available
- `stale` — Data > 24 hours old
- `no_fixtures` — No matches scheduled
- `no_draftkings_market` — No betting markets available
- `historical_data_insufficient` — Need 100+ historical matches
- `model_not_ready` — Model failed validation
- `no_qualifying_bets` — No bets meet edge threshold
- `fetch_failed` — API errors
- `not_run` — Pipeline never executed
- `not_enabled` — Competition disabled for production

---

## Deployment

### Local Development
```bash
# Development mode (shows mock data with warnings)
APP_ENV=development streamlit run predictions.py
```

### Production Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for full deployment guide covering:
- Streamlit Cloud deployment
- Self-hosted deployment (VPS, EC2)
- Environment configuration
- Monitoring setup
- Rollback procedures

### Health Monitoring
```bash
# Run health check
python scripts/health_check.py

# Expected output:
# ✅ Environment: production
# ✅ Cache is fresh (last updated: 2026-07-22T06:15:30Z)
# ✅ Using production data
# ✅ Competitions ready: 3/5
# ✅ Overall Status: HEALTHY
```

---

## Testing

Run the full test suite:
```bash
# Unit tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=pipeline --cov=utils --cov-report=term

# Integration test (pipeline dry run)
python fetch_data.py --dry-run
```

CI/CD runs automatically on every push:
- Code quality (ruff, mypy)
- Unit tests
- Integration tests
- Security scanning
- Build verification

---

## Keeping predictions honest

After every match finishes, the nightly pipeline checks the actual result against what was predicted and logs it. The Model Performance page shows this full history with:
- **Brier score** — Calibration quality (lower is better, 0.20 is good)
- **Calibration slope/intercept** — Are 60% predictions winning 60% of the time?
- **ROI by edge bucket** — Are high-edge picks actually more profitable?
- **Closing Line Value (CLV)** — Is the model ahead of market moves?

There's nowhere to hide a bad run. Every bet recommendation is backed by a live, auditable track record.

---

## Documentation

- [PRODUCTION_PLAN.md](PRODUCTION_PLAN.md) — 8-phase production readiness plan
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — Deployment guide for all environments
- [docs/RUNBOOK.md](docs/RUNBOOK.md) — Operational procedures and troubleshooting
- [docs/architecture.md](docs/architecture.md) — System architecture overview
- [pipeline/README.md](pipeline/README.md) — Pipeline component details

---

## Environment Variables

| Variable | Required | Purpose | Example |
|---|---|---|---|
| `APP_ENV` | Yes | Controls mock data behavior | `production` or `development` |
| `ODDS_API_KEY` | Production only | The Odds API access | `abc123...` |
| `CRICKET_DATA_API_KEY` | Production only | CricketData.org access | `xyz789...` |

**Never commit `.env` files** — use environment secrets in production.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Support

- **Issues:** GitHub Issues
- **Deployment:** See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- **Operations:** See [docs/RUNBOOK.md](docs/RUNBOOK.md)
