# Wicket Oracle 🏏

Your personal edge for IPL T20 betting — win probability, player props, value bets, and playoff forecasts, all in one place.

---

## What is Wicket Oracle?

Wicket Oracle is a web app built for IPL cricket bettors who want data on their side. Every day before matches start, it automatically pulls the latest fixtures, weather, and DraftKings lines, then runs its own predictions. You see, side by side, what the model thinks will happen and what the bookmaker is pricing — so you can spot the gaps.

---

## What's inside

**Today's Matches**
Win probabilities for each match, compared against the current DraftKings lines. Includes venue stats and weather conditions at match time so you know when the dew or wind might shift things.

**Player Props**
Projected runs for key batters and wickets for key bowlers, benchmarked against the DraftKings over/under lines. Each prop is labelled Low / Medium / High confidence.

**Value Bets**
A ranked shortlist of the bets where the model's edge over the bookmaker is largest — match winners, run totals, and player props in one place, with suggested Kelly Criterion stake sizes.

**Team Deep Dive**
Recent form, batting and bowling breakdowns by phase of play (powerplay / middle overs / death), head-to-head records, and venue-specific performance for any team in the competition.

**Fixtures & Table**
The full IPL schedule with results, the live points table, and a playoff probability simulator that runs 10,000 season scenarios to show each team's chances of making the top four.

**Model Performance**
A running scorecard of how the predictions have done. Rolling accuracy, cumulative profit/loss at flat -110 odds, performance broken down by the size of the edge, and a full match-by-match log.

**Statistics**
Deep-dive profiles for every IPL venue, batter, bowler, and umpire based on historical ball-by-ball data.

---

## Getting started

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the app
```bash
streamlit run predictions.py --server.port 5000
```

The app works straight away with simulated data so you can explore every page immediately.

### 3. Connect live data (optional)

To see real predictions, add two free API keys:

| Key | Where to get it |
|---|---|
| `ODDS_API_KEY` | [the-odds-api.com](https://the-odds-api.com) |
| `CRICKET_DATA_API_KEY` | [cricketdata.org](https://cricketdata.org) |

Then run the data pipeline once:
```bash
python fetch_data.py
```

After that, the pipeline runs automatically every morning at 06:00 UTC via GitHub Actions, so the app always has fresh data when you open it.

---

## Keeping predictions honest

After every match finishes, the nightly pipeline checks the actual result against what was predicted and logs it. The Model Performance page shows this full history — there's nowhere to hide a bad run. Every bet recommendation you see is backed by a live track record.
