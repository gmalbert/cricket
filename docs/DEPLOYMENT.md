# Deployment Guide

## Overview

This guide covers deploying Wicket Oracle to different environments: local development, staging, and production.

## Table of Contents

1. [Environment Overview](#environment-overview)
2. [Local Development](#local-development)
3. [Staging Deployment](#staging-deployment)
4. [Production Deployment](#production-deployment)
5. [Environment Variables](#environment-variables)
6. [Post-Deployment Verification](#post-deployment-verification)

---

## Environment Overview

### Environment Comparison

| Aspect | Local | Staging | Production |
|---|---|---|---|
| `APP_ENV` | `development` | `production` | `production` |
| Mock data fallback | ✅ Enabled | ❌ Disabled | ❌ Disabled |
| API keys | Optional | Required | Required |
| Pipeline schedule | Manual | Daily 06:00 UTC | Daily 06:00 UTC |
| Cache persistence | Local disk | Git-committed | Git-committed |
| Monitoring | None | Basic logs | Full monitoring |

---

## Local Development

### Prerequisites

- Python 3.11 or higher
- Git
- Virtual environment tool (venv, conda, etc.)

### Setup Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/cricket.git
   cd cricket
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Set up environment variables (optional for dev):**
   ```bash
   # Create .env file
   echo "APP_ENV=development" > .env
   echo "ODDS_API_KEY=your_key_here" >> .env
   echo "CRICKET_DATA_API_KEY=your_key_here" >> .env
   ```

5. **Run the app:**
   ```bash
   streamlit run predictions.py
   ```

6. **Access the app:**
   Open http://localhost:8501 in your browser

### Development Workflow

```bash
# Run pipeline manually
python fetch_data.py --skip-cricsheet

# Run with dry-run (no cache writes)
python fetch_data.py --dry-run

# Run tests
pytest tests/ -v

# Run linter
ruff check .

# Format code
ruff format .
```

---

## Staging Deployment

Staging mimics production but uses a separate environment for testing.

### GitHub Actions Setup

1. **Configure secrets:**
   - Go to repository Settings → Secrets and variables → Actions
   - Add secrets:
     - `STAGING_ODDS_API_KEY`
     - `STAGING_CRICKET_DATA_API_KEY`

2. **Create staging workflow:**

Create `.github/workflows/staging.yml`:

```yaml
name: Deploy to Staging

on:
  push:
    branches: [develop]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run pipeline
        env:
          APP_ENV: production
          ODDS_API_KEY: ${{ secrets.STAGING_ODDS_API_KEY }}
          CRICKET_DATA_API_KEY: ${{ secrets.STAGING_CRICKET_DATA_API_KEY }}
        run: |
          python fetch_data.py --skip-cricsheet
      
      - name: Commit updated cache
        run: |
          git config user.name "GitHub Actions Bot"
          git config user.email "actions@github.com"
          git add cache/*.json
          git add cache/runs/
          git commit -m "Update staging cache [skip ci]" || echo "No changes to commit"
          git push
```

### Verification

```bash
# Check staging deployment
git checkout develop
git pull

# Verify cache was updated
ls -lt cache/

# Check competition status
cat cache/competition_status.json | jq .
```

---

## Production Deployment

### Prerequisites Checklist

- [ ] All tests passing in CI
- [ ] Staging deployment successful
- [ ] API keys secured in GitHub Secrets
- [ ] Monitoring configured
- [ ] Rollback plan documented

### GitHub Actions Production Setup

1. **Configure production secrets:**
   - Go to repository Settings → Secrets and variables → Actions
   - Add secrets:
     - `PROD_ODDS_API_KEY`
     - `PROD_CRICKET_DATA_API_KEY`

2. **Update nightly workflow:**

Verify `.github/workflows/nightly.yml` has production settings:

```yaml
name: Nightly Pipeline

on:
  schedule:
    - cron: '0 6 * * *'  # 06:00 UTC daily
  workflow_dispatch:  # Allow manual trigger

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run nightly pipeline
        env:
          APP_ENV: production
          ODDS_API_KEY: ${{ secrets.PROD_ODDS_API_KEY }}
          CRICKET_DATA_API_KEY: ${{ secrets.PROD_CRICKET_DATA_API_KEY }}
        run: |
          python fetch_data.py --skip-cricsheet
      
      - name: Commit updated cache
        run: |
          git config user.name "Wicket Oracle Bot"
          git config user.email "bot@wicketoracle.com"
          git add cache/*.json
          git add cache/runs/
          git commit -m "Update production cache - $(date -u '+%Y-%m-%d %H:%M UTC')" || echo "No changes"
          git push
      
      - name: Notify on failure
        if: failure()
        run: |
          echo "❌ Pipeline failed - check logs at ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
```

### Streamlit Cloud Deployment

If deploying to Streamlit Cloud:

1. **Connect GitHub repository:**
   - Log in to https://share.streamlit.io
   - Click "New app"
   - Select your GitHub repository
   - Set main file: `predictions.py`
   - Set branch: `main`

2. **Configure secrets:**
   - In Streamlit Cloud, go to App settings → Secrets
   - Add:
     ```toml
     APP_ENV = "production"
     ODDS_API_KEY = "your_production_key"
     CRICKET_DATA_API_KEY = "your_production_key"
     ```

3. **Deploy:**
   - Click "Deploy!"
   - App will be available at `https://your-app.streamlit.app`

### Self-Hosted Deployment

For self-hosted deployment (VPS, EC2, etc.):

1. **Install system dependencies:**
   ```bash
   sudo apt update
   sudo apt install python3.11 python3-pip git
   ```

2. **Clone repository:**
   ```bash
   cd /opt
   git clone https://github.com/yourusername/cricket.git
   cd cricket
   ```

3. **Set up virtual environment:**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   # Create .env file (NEVER commit this)
   cat > .env << EOF
   APP_ENV=production
   ODDS_API_KEY=your_key_here
   CRICKET_DATA_API_KEY=your_key_here
   EOF
   
   chmod 600 .env
   ```

5. **Set up systemd service:**

Create `/etc/systemd/system/wicket-oracle.service`:

```ini
[Unit]
Description=Wicket Oracle Streamlit App
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/cricket
Environment="PATH=/opt/cricket/venv/bin"
EnvironmentFile=/opt/cricket/.env
ExecStart=/opt/cricket/venv/bin/streamlit run predictions.py --server.port 8501 --server.address 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

6. **Enable and start service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable wicket-oracle
   sudo systemctl start wicket-oracle
   sudo systemctl status wicket-oracle
   ```

7. **Set up pipeline cron job:**
   ```bash
   crontab -e
   
   # Add line:
   0 6 * * * cd /opt/cricket && /opt/cricket/venv/bin/python fetch_data.py --skip-cricsheet >> /var/log/wicket-oracle-pipeline.log 2>&1
   ```

8. **Configure reverse proxy (nginx):**

Create `/etc/nginx/sites-available/wicket-oracle`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and reload:
```bash
sudo ln -s /etc/nginx/sites-available/wicket-oracle /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Environment Variables

### Required Variables

| Variable | Purpose | Example | Environment |
|---|---|---|---|
| `APP_ENV` | Controls mock data behavior | `production` or `development` | All |
| `ODDS_API_KEY` | The Odds API access key | `abc123...` | Staging, Production |
| `CRICKET_DATA_API_KEY` | CricketData.org API key | `xyz789...` | Staging, Production |

### Optional Variables

| Variable | Purpose | Default | Example |
|---|---|---|---|
| `CACHE_DIR` | Override cache location | `./cache` | `/var/cache/wicket-oracle` |

### Setting Environment Variables

**GitHub Actions:**
```yaml
env:
  APP_ENV: production
  ODDS_API_KEY: ${{ secrets.PROD_ODDS_API_KEY }}
```

**Streamlit Cloud:**
```toml
# In Streamlit Cloud Secrets
APP_ENV = "production"
```

**Linux/Mac (.env file):**
```bash
APP_ENV=production
ODDS_API_KEY=your_key
```

**Windows PowerShell:**
```powershell
$env:APP_ENV="production"
$env:ODDS_API_KEY="your_key"
```

---

## Post-Deployment Verification

### Verification Checklist

After deploying to any environment, verify:

1. **App starts successfully:**
   ```bash
   # Check app is running
   curl -I http://your-domain.com
   ```

2. **Environment is correct:**
   - Check sidebar shows "Development Mode" badge only if `APP_ENV=development`
   - In production, should NOT show "SIMULATED DATA" warning

3. **Cache files present:**
   ```bash
   ls cache/*.json
   # Should see: todays_matches.json, value_bets.json, competition_status.json, etc.
   ```

4. **Competition status displayed:**
   - Open app sidebar
   - Expand "Competition Coverage"
   - Verify competitions show appropriate status

5. **Pipeline can run:**
   ```bash
   python fetch_data.py --dry-run
   # Should complete without errors
   ```

6. **Tests pass:**
   ```bash
   pytest tests/ -v
   # All tests should pass
   ```

### Health Check Script

```bash
#!/bin/bash
# health-check.sh

echo "=== Wicket Oracle Health Check ==="

# 1. Check app process
if pgrep -f "streamlit run predictions.py" > /dev/null; then
    echo "✅ App is running"
else
    echo "❌ App is not running"
fi

# 2. Check environment
if [ "$APP_ENV" = "production" ]; then
    echo "✅ Environment: production"
else
    echo "⚠️ Environment: $APP_ENV"
fi

# 3. Check cache age
LAST_UPDATED=$(stat -c %Y cache/last_updated.json 2>/dev/null || echo 0)
NOW=$(date +%s)
AGE_HOURS=$(( (NOW - LAST_UPDATED) / 3600 ))

if [ $AGE_HOURS -lt 24 ]; then
    echo "✅ Cache is fresh (${AGE_HOURS}h old)"
else
    echo "⚠️ Cache is stale (${AGE_HOURS}h old)"
fi

# 4. Check competition status
python -c "
from utils.data import get_competition_status
status = get_competition_status()
ready = sum(1 for c in status.get('competitions', {}).values() if c.get('status') == 'ready')
total = len(status.get('competitions', {}))
print(f'✅ Competitions ready: {ready}/{total}')
"

echo "=== Health Check Complete ==="
```

Make executable and run:
```bash
chmod +x health-check.sh
./health-check.sh
```

---

## Rollback Plan

If deployment fails or issues arise:

### Immediate Rollback

1. **Revert code to last known good commit:**
   ```bash
   git log --oneline -5
   git revert HEAD
   git push origin main
   ```

2. **Restore cache from backup:**
   ```bash
   # Latest backup is in cache/backup/
   cp cache/backup/latest/*.json cache/
   ```

3. **Restart app:**
   ```bash
   # Streamlit Cloud: Will auto-redeploy
   # Self-hosted:
   sudo systemctl restart wicket-oracle
   ```

### Gradual Rollback

For partial issues (e.g., one competition broken):

1. **Disable affected competition:**
   - Edit `pipeline/competitions.py`
   - Set `enabled=False` for affected competition
   - Run pipeline again

2. **Monitor recovery:**
   - Check logs for errors
   - Verify other competitions still working
   - Re-enable when fixed

---

## Monitoring Setup

### Recommended Monitoring

1. **Uptime monitoring:**
   - Use UptimeRobot, Pingdom, or similar
   - Monitor: `https://your-domain.com`
   - Alert on: 5xx errors, downtime > 5 min

2. **Pipeline monitoring:**
   - Monitor GitHub Actions runs
   - Alert on: Failed runs, no runs in 36 hours

3. **Data freshness:**
   - Run health check script hourly
   - Alert on: Cache age > 36 hours

4. **Log aggregation:**
   - Use CloudWatch, Datadog, or similar
   - Monitor patterns from RUNBOOK.md

---

## Support

For deployment issues:
- Check [RUNBOOK.md](RUNBOOK.md) for troubleshooting
- Review GitHub Actions logs
- Check app logs: `sudo journalctl -u wicket-oracle -f`

---

## Change Log

| Date | Change | Author |
|---|---|---|
| 2026-07-22 | Initial deployment guide | Production Readiness Phase 8 |
