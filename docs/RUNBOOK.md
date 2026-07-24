# Operational Runbook

## Overview

This runbook provides operational procedures for running Wicket Oracle in production. Follow these procedures to maintain uptime, handle incidents, and ensure data quality.

## Table of Contents

1. [Environment Setup](#environment-setup)
2. [Daily Operations](#daily-operations)
3. [Monitoring](#monitoring)
4. [Incident Response](#incident-response)
5. [Rollback Procedures](#rollback-procedures)
6. [Troubleshooting](#troubleshooting)

---

## Environment Setup

### Required Environment Variables

| Variable | Purpose | Required | Example |
|---|---|---|---|
| `APP_ENV` | Environment mode | Yes | `production` |
| `ODDS_API_KEY` | The Odds API access | Yes | `abc123...` |
| `CRICKET_DATA_API_KEY` | CricketData.org access | Yes | `xyz789...` |

### Environment Modes

- **production**: Live mode. Never shows mock data. Returns None if cache is missing.
- **development**: Dev mode. Shows mock data with warnings when cache is missing.
- **test**: Test mode. Used in CI/CD, similar to production but allows test fixtures.

### Deployment Checklist

- [ ] Set `APP_ENV=production` in production environment
- [ ] Configure API keys in secure environment secrets (never commit to git)
- [ ] Verify cache directory is writable (`cache/`)
- [ ] Verify backup directory exists (`cache/backup/`)
- [ ] Verify runs directory exists (`cache/runs/`)
- [ ] Test pipeline dry-run: `python fetch_data.py --dry-run --skip-cricsheet`
- [ ] Verify Streamlit starts: `streamlit run predictions.py`
- [ ] Check logs for warnings/errors
- [ ] Verify competition status shows correct states
- [ ] Test with no cache (should show "No data available" in production)

---

## Daily Operations

### Nightly Pipeline Execution

The pipeline runs automatically via GitHub Actions at 06:00 UTC daily. To run manually:

```bash
# Full run (downloads latest Cricsheet data)
python fetch_data.py

# Skip Cricsheet download if < 23 hours old
python fetch_data.py --skip-cricsheet

# Dry run (no cache writes)
python fetch_data.py --dry-run
```

### Pipeline Success Criteria

A successful pipeline run must:
- ✅ Complete all steps without errors
- ✅ Generate a run manifest in `cache/runs/{run_id}/manifest.json`
- ✅ Write required cache files: `todays_matches.json`, `value_bets.json`, `competition_status.json`
- ✅ Pass model validation (predictions valid, probabilities sum to 1.0)
- ✅ Promote outputs to production cache atomically
- ✅ Update `last_updated.json` with run metadata

### Verifying Pipeline Success

```bash
# Check last run status
cat cache/last_updated.json

# Check latest run manifest
ls -lt cache/runs/ | head -n 2

# View manifest details
cat cache/runs/{run_id}/manifest.json | jq .

# Check competition status
cat cache/competition_status.json | jq .
```

### Expected Output Files

After a successful run, these cache files should exist:

- `cache/todays_matches.json` - Today's match predictions
- `cache/value_bets.json` - Qualifying bets (if any)
- `cache/competition_status.json` - Production readiness per competition
- `cache/last_updated.json` - Pipeline run summary
- `cache/team_form.json` - Historical team performance
- `cache/venue_stats.json` - Venue statistics
- `cache/player_stats.json` - Player performance data
- `cache/playoff_probabilities.json` - Monte Carlo playoff simulation

---

## Monitoring

### Key Metrics

Monitor these metrics to ensure health:

| Metric | Healthy Range | Alert Threshold |
|---|---|---|
| Pipeline success rate | > 95% | < 90% |
| Data age (hours) | < 24 | > 36 |
| Fixture count | > 0 (during season) | 0 for 3+ days |
| DraftKings event count | > 0 (during season) | 0 for 3+ days |
| Qualifying bet count | Variable | N/A (depends on edge) |
| API error rate | < 5% | > 20% |
| Cache file count | 8-10 files | < 5 files |

### Health Check Endpoints

```bash
# Check app is running
curl -I http://localhost:8501

# Verify cache status via Python
python -c "
from utils.cache import get_cache_metadata, is_cache_stale
meta = get_cache_metadata('last_updated')
print('Last run:', meta.get('generated_at') if meta else 'MISSING')
print('Stale:', is_cache_stale('last_updated', max_age_hours=24))
"

# Check production status
python -c "
from utils.data import get_competition_status
status = get_competition_status()
for comp, data in status.get('competitions', {}).items():
    print(f\"{comp}: {data.get('status')}\")
"
```

### Log Monitoring

Monitor these log patterns:

**Success patterns:**
- `✅ Pipeline run {run_id} completed successfully`
- `✅ Promoted run {run_id} to production`
- `Competition {slug} status: ready`

**Warning patterns:**
- `⚠️ No DraftKings market found for {competition}`
- `⚠️ Historical data insufficient for {competition}`
- `⚠️ Data is stale (age: {hours}h)`

**Error patterns:**
- `❌ Failed to fetch {source}: {error}`
- `❌ Model validation failed: {reason}`
- `❌ Cache promotion failed, restoring backup`
- `❌ API key missing: {variable}`

---

## Incident Response

### Scenario 1: Pipeline Failure

**Symptoms:** No new predictions, stale data warning, error in logs

**Diagnosis:**
```bash
# Check last run manifest
ls -lt cache/runs/ | head -n 2
cat cache/runs/{run_id}/manifest.json | jq '.errors'

# Check cache status
python -c "from utils.cache import cache_status; print(cache_status())"
```

**Resolution:**
1. Check API keys are set and valid
2. Review error details in manifest
3. If transient error (network timeout), re-run pipeline
4. If data source issue, verify API status:
   - The Odds API: https://the-odds-api.com/
   - CricketData.org: https://cricketdata.org/
5. Last known good cache is preserved automatically (no manual restoration needed)

### Scenario 2: No Qualifying Bets

**Symptoms:** "No qualifying bets today" message, `qualifying_bets: 0` in status

**Diagnosis:**
```bash
# Check competition status
cat cache/competition_status.json | jq '.competitions'

# Check why no bets
cat cache/value_bets.json | jq .
```

**This is expected when:**
- No matches scheduled today
- No DraftKings market available
- Model edge < 5% threshold
- Competition not enabled for production

**This is NOT an error** - the system is working as designed.

### Scenario 3: Stale Data

**Symptoms:** "Data is stale" warning, old timestamps

**Diagnosis:**
```bash
# Check data age
python -c "
from utils.cache import get_cache_metadata
meta = get_cache_metadata('last_updated')
print('Generated:', meta.get('generated_at'))
print('Run ID:', meta.get('source_run_id'))
"
```

**Resolution:**
1. Verify nightly job is running (check GitHub Actions)
2. If job is disabled, re-enable in `.github/workflows/nightly.yml`
3. Run pipeline manually if needed
4. If data is intentionally old (off-season), this is expected

### Scenario 4: Mock Data Showing in Production

**Symptoms:** "SIMULATED DATA" warning when `APP_ENV=production`

**This should NEVER happen.** If it does:

**Diagnosis:**
```bash
# Verify environment
echo $APP_ENV

# Check cache metadata
python -c "
from utils.cache import is_mock_data
print('Is mock:', is_mock_data('todays_matches'))
"
```

**Resolution:**
1. Verify `APP_ENV=production` is set
2. If `APP_ENV` is correct but mock showing, this is a critical bug
3. Immediately stop the app and investigate
4. Check cache files were not manually written with `is_mock: true`

---

## Rollback Procedures

### Rollback to Last Known Good Cache

If the latest pipeline run produced bad data, restore from backup:

```bash
# List available backups
ls -lt cache/backup/

# Restore from backup (manual process)
# 1. Stop the app
# 2. Move current cache to a safe location
mkdir cache/quarantine/{timestamp}
mv cache/*.json cache/quarantine/{timestamp}/

# 3. Copy backup to production
cp cache/backup/{timestamp}/*.json cache/

# 4. Verify restored data
cat cache/last_updated.json

# 5. Restart the app
```

### Rollback Code Deployment

```bash
# If new code caused issues, revert to previous commit
git log --oneline -10
git revert {commit_hash}
git push origin main

# Or reset to known good commit (use with caution)
git reset --hard {commit_hash}
git push --force origin main
```

---

## Troubleshooting

### Pipeline Skips All Predictions

**Check:**
- Are fixtures available? `cat cache/schedule.json | jq '.fixtures | length'`
- Is DraftKings returning data? `cat cache/runs/{latest}/odds_raw.json`
- Is model trained? `ls cache/models/`

### Predictions Look Wrong

**Check:**
- Model version: Look for `model_version` in prediction
- Feature values: Check `cache/runs/{run_id}/features.json`
- Historical data: Verify `team_form.json`, `venue_stats.json` are recent

### App Won't Start

**Check:**
- Python version: `python --version` (should be 3.11+)
- Dependencies: `pip install -r requirements.txt`
- Import errors: `python -c "import streamlit; import pipeline.run_pipeline"`
- Port conflict: `lsof -i :8501`

### API Rate Limits

**Symptoms:** 429 errors, "quota exceeded" in logs

**Resolution:**
- The Odds API: Free tier is 500 requests/month. Upgrade if needed.
- CricketData.org: Check your plan limits
- Use `--skip-cricsheet` to reduce API calls during development

### Cache Files Corrupt

**Symptoms:** JSON parse errors, invalid data structures

**Resolution:**
```bash
# Validate cache files
for f in cache/*.json; do
    echo "Checking $f"
    python -c "import json; json.load(open('$f'))"
done

# Remove corrupt files (will be regenerated on next run)
rm cache/{corrupt_file}.json

# Run pipeline to regenerate
python fetch_data.py
```

---

## Maintenance Windows

### Recommended Schedule

- **Daily:** Nightly pipeline runs at 06:00 UTC
- **Weekly:** Review logs, check for warnings
- **Monthly:** Update dependencies, review model performance
- **Quarterly:** Retrain models with new data, validate publish gates

### Pre-Season Checklist

- [ ] Update competition registry in `pipeline/competitions.py`
- [ ] Verify team aliases in `pipeline/normalization.py`
- [ ] Run historical data refresh (full Cricsheet download)
- [ ] Retrain models with pre-season data
- [ ] Test fixture ingestion with sample matches
- [ ] Verify DraftKings markets are available for new season

### Off-Season Operations

During off-season (no matches):
- ✅ Pipeline will run but produce empty fixtures (expected)
- ✅ Status will show "no_fixtures" (correct behavior)
- ✅ No bets will be published (correct)
- ⚠️ Last cache will become stale (acceptable)

**Do not disable the pipeline** - it should continue running to immediately catch new fixtures when season starts.

---

## Support Contacts

| Issue Type | Contact |
|---|---|
| Pipeline failures | Check GitHub Actions logs |
| API issues | The Odds API support, CricketData.org support |
| Model bugs | Review `tests/` and raise issue |
| UI bugs | Check Streamlit logs, raise issue |

---

## Change Log

| Date | Change | Author |
|---|---|---|
| 2026-07-22 | Initial runbook created | Production Readiness Phase 8 |
