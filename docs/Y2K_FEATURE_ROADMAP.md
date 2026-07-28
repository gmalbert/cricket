# Wicket Oracle: Match Intelligence Roadmap

## Objective

Build the high-value product ideas observed in Y2K Sports into Wicket Oracle without weakening the existing cache-first architecture:

1. IPL **Batter vs Bowler Rivalry Analyzer** (head-to-head evidence, dismissal history, phase splits, matchup rating).
2. A single **Match Hub** that explains every prediction with recent form, venue, weather, odds, top props, and key rivalries.
3. An optional **shot-map / wagon-wheel layer**, only after confirming that a licensed or public source provides reliable ball-location data.
4. A deliberate, config-driven path from IPL to additional competitions, beginning with women’s cricket or international T20s.

This is an implementation roadmap, not a commitment to scrape or copy Y2K Sports. The UX concepts are independent; all data must be sourced and used under the applicable provider terms.

## Product decisions

### What we will build now

| Feature | Why it matters | Existing data fit |
|---|---|---|
| Rivalry Analyzer | Turns raw ball-by-ball data into a repeatable betting/research workflow | Strong: Cricsheet has batter, bowler, runs, extras, wickets, date and match context |
| Match Hub | Keeps prediction evidence in one place rather than split across three tabs | Strong: consumes current caches only |
| Key rivalry callouts in props | Explains a projection in context | Strong after rivalry cache exists |
| Competition configuration | Removes IPL-only constants from feature code | Medium: start after core views are stable |

### Explicitly deferred

| Feature | Reason | Gate to start |
|---|---|---|
| True wagon wheels / scoring zones | The current Cricsheet CSV ingest does not establish reliable x/y shot locations | Identify a legitimate source, document its license, and add a representative sample fixture |
| AI-generated news | Less decision-useful than model evidence and difficult to quality-control | Only consider after a source/citation policy and editorial review design exist |
| Real-time in-play prediction | Requires higher-frequency data, model validation, and a different failure policy | Stable live feed plus calibrated in-play model |

## Architecture constraints

- **Pipeline writes; Streamlit pages read.** No new page may call a remote API.
- **Cache-first.** Every new UI must show the latest cached result and a helpful empty state when data is absent.
- **No invented statistics.** Existing mock helpers may support local visual development, but live cache output must be derived from source data and include sufficient sample-size context.
- **Stable names are mandatory.** Player aliases and team renames must be normalized before aggregation.
- **Feature work is additive.** Do not change existing cache schemas without backward-compatible defaults.

## Target data flow

```text
Cricsheet IPL CSV archive
        |
        v
pipeline/fetch_cricsheet.py ------> cache/raw/ipl_ball_by_ball.parquet
        |
        +--> pipeline/build_rivalries.py --> cache/rivalries.json
        |                                  --> cache/match_hubs.json
        |
fixtures + odds + weather + existing model outputs
        |
        +--> pipeline/build_match_hubs.py --> cache/match_hubs.json
                                               |
                                               v
                                  pages_app/match_hub.py
                                  pages_app/rivalry_analyzer.py
                                  pages_app/player_props.py (context links)
```

`rivalries.json` is historical, while `match_hubs.json` is fixture-specific and is regenerated nightly. Each is independently useful if the other fails.

## Phase 0 — Foundations and data audit

### Deliverables

1. Record the exact Cricsheet CSV columns present in a current cached parquet.
2. Add name normalization shared by the historical pipeline and fixture/squad layers.
3. Confirm which player names from `utils.data.TEAM_PLAYERS` join successfully to Cricsheet names.
4. Establish a minimum sample policy: do not label a matchup as an actionable advantage with fewer than **12 legal balls** or **2 dismissals** unless clearly marked as low-sample.

### New module: `pipeline/normalization.py`

```python
"""Canonical identifiers for joins across Cricsheet, fixtures, odds, and UI."""
from __future__ import annotations

import re
import unicodedata

TEAM_ALIASES = {
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "Delhi Daredevils": "Delhi Capitals",
    "Kings XI Punjab": "Punjab Kings",
}

# Populate from audit findings. Keys and values must be canonical display names.
PLAYER_ALIASES: dict[str, str] = {
    # "V Kohli": "V Kohli",
}


def canonical_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\\s+", " ", text).strip()


def canonical_team(team: object) -> str:
    name = canonical_text(team)
    return TEAM_ALIASES.get(name, name)


def canonical_player(player: object) -> str:
    name = canonical_text(player)
    return PLAYER_ALIASES.get(name, name)
```

### Audit command

```bash
python - <<'PY'
import pandas as pd
from pathlib import Path

path = Path("cache/raw/ipl_ball_by_ball.parquet")
df = pd.read_parquet(path)
print("columns:", sorted(df.columns.tolist()))
for col in ("batter", "bowler", "wicket_type", "player_dismissed", "ball", "runs_off_bat"):
    if col in df:
        print(f"{col}: non-null={df[col].notna().sum():,}")
PY
```

### Acceptance criteria

- A fixture player can be joined to a historical player or reported in a `unmatched_players` audit list.
- All new aggregations use `canonical_player()` and `canonical_team()`.
- The pipeline does not fail when optional Cricsheet columns are absent; it returns an empty rivalry cache with a reason.

## Phase 1 — Historical Rivalry Analyzer

### Cache contract: `rivalries.json`

Register the cache key in `utils/cache.py`:

```python
CACHE_FILES = {
    # existing keys ...
    "rivalries": "rivalries.json",
    "match_hubs": "match_hubs.json",
}
```

Recommended schema (versioned to permit future migrations):

```json
{
  "schema_version": 1,
  "generated_at": "2026-07-12T10:00:00+00:00",
  "competition": "ipl_male",
  "source": {"provider": "Cricsheet", "dataset": "ipl_male_csv2"},
  "rivalries": [
    {
      "key": "v_kohli__jj_bumrah",
      "batter": "V Kohli",
      "bowler": "JJ Bumrah",
      "balls": 42,
      "legal_balls": 40,
      "runs_off_bat": 51,
      "extras": 3,
      "dismissals": 2,
      "strike_rate": 127.5,
      "runs_per_ball": 1.275,
      "dot_ball_pct": 35.0,
      "boundary_count": 6,
      "boundary_pct": 15.0,
      "dismissal_types": {"caught": 1, "bowled": 1},
      "phase_splits": {
        "powerplay": {"legal_balls": 16, "runs_off_bat": 23, "dismissals": 0},
        "middle": {"legal_balls": 20, "runs_off_bat": 22, "dismissals": 1},
        "death": {"legal_balls": 4, "runs_off_bat": 6, "dismissals": 1}
      },
      "recent_encounters": [
        {"date": "2025-05-03", "match_id": "...", "balls": 8, "runs": 9, "dismissed": false}
      ],
      "sample_tier": "medium",
      "matchup_score": 54.2,
      "score_label": "Neutral",
      "updated_through": "2026-05-31"
    }
  ]
}
```

### Metric definitions

| Metric | Definition |
|---|---|
| legal balls | Deliveries excluding wides; a no-ball counts as a ball faced only if the source’s delivery semantics support it—verify against sample rows first |
| runs off bat | Sum of `runs_off_bat`; do not attribute extras to the batter |
| strike rate | `100 * runs_off_bat / legal_balls`; return `None` when no legal balls |
| dot-ball % | `100 * (legal balls with 0 runs off bat) / legal_balls` |
| dismissal | Count only wickets where `player_dismissed == batter` and dismissal type is credited to the bowler; exclude run out, retired hurt, obstructing the field |
| phase | Powerplay overs 0–5, middle 6–14, death 15–19 for standard IPL T20; retain the raw over to make this configurable |

### New module: `pipeline/build_rivalries.py`

```python
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from pipeline.normalization import canonical_player

SCHEMA_VERSION = 1
BOWLER_CREDITED_WICKETS = {
    "bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket",
}


def phase_for_over(over: int) -> str:
    if over <= 5:
        return "powerplay"
    if over <= 14:
        return "middle"
    return "death"


def _is_legal_ball(row: pd.Series) -> bool:
    # Verify field names against Phase 0 audit. In the Cricsheet CSV2 format,
    # wides are not legal balls; keep this centralized so semantics are testable.
    return float(row.get("wides", 0) or 0) == 0


def _credited_dismissal(row: pd.Series) -> bool:
    wicket_type = str(row.get("wicket_type", "") or "").lower()
    batter = canonical_player(row.get("batter"))
    dismissed = canonical_player(row.get("player_dismissed"))
    return wicket_type in BOWLER_CREDITED_WICKETS and batter == dismissed


def _tier(legal_balls: int, dismissals: int) -> str:
    if legal_balls >= 36 or dismissals >= 3:
        return "high"
    if legal_balls >= 12 or dismissals >= 2:
        return "medium"
    return "low"


def build_rivalries(ball_by_ball: pd.DataFrame) -> dict[str, Any]:
    required = {"batter", "bowler", "runs_off_bat", "match_id"}
    missing = required - set(ball_by_ball.columns)
    if missing:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rivalries": [],
            "error": f"Missing required columns: {sorted(missing)}",
        }

    df = ball_by_ball.copy()
    df["batter"] = df["batter"].map(canonical_player)
    df["bowler"] = df["bowler"].map(canonical_player)
    df["runs_off_bat"] = pd.to_numeric(df["runs_off_bat"], errors="coerce").fillna(0)
    df["legal_ball"] = df.apply(_is_legal_ball, axis=1)
    df["credited_dismissal"] = df.apply(_credited_dismissal, axis=1)
    df["over_number"] = pd.to_numeric(df.get("ball", 0), errors="coerce").fillna(0).astype(int)
    df["phase"] = df["over_number"].map(phase_for_over)

    rows: list[dict[str, Any]] = []
    for (batter, bowler), group in df.groupby(["batter", "bowler"], dropna=False):
        legal = group[group["legal_ball"]]
        legal_balls = int(len(legal))
        runs = int(group["runs_off_bat"].sum())
        dismissals = int(group["credited_dismissal"].sum())
        phases = {}
        for phase, phase_group in group.groupby("phase"):
            phase_legal = phase_group[phase_group["legal_ball"]]
            phases[phase] = {
                "legal_balls": int(len(phase_legal)),
                "runs_off_bat": int(phase_group["runs_off_bat"].sum()),
                "dismissals": int(phase_group["credited_dismissal"].sum()),
            }

        recent = []
        sort_col = "start_date" if "start_date" in group.columns else "match_id"
        for match_id, encounter in group.sort_values(sort_col, ascending=False).groupby("match_id"):
            encounter_legal = encounter[encounter["legal_ball"]]
            recent.append({
                "match_id": str(match_id),
                "date": str(encounter.get("start_date", pd.Series([""])).iloc[0]),
                "balls": int(len(encounter_legal)),
                "runs": int(encounter["runs_off_bat"].sum()),
                "dismissed": bool(encounter["credited_dismissal"].any()),
            })
            if len(recent) == 5:
                break

        dots = int((legal["runs_off_bat"] == 0).sum())
        boundaries = int((legal["runs_off_bat"] >= 4).sum())
        # A transparent descriptive score, not a probability. Calibrate later.
        score = 50.0 if legal_balls == 0 else max(0.0, min(100.0,
            50 + 12 * ((runs / legal_balls) - 1.2) - 8 * dismissals
        ))
        rows.append({
            "key": f"{batter.lower().replace(' ', '_')}__{bowler.lower().replace(' ', '_')}",
            "batter": batter, "bowler": bowler,
            "balls": int(len(group)), "legal_balls": legal_balls,
            "runs_off_bat": runs, "dismissals": dismissals,
            "strike_rate": round(100 * runs / legal_balls, 1) if legal_balls else None,
            "runs_per_ball": round(runs / legal_balls, 3) if legal_balls else None,
            "dot_ball_pct": round(100 * dots / legal_balls, 1) if legal_balls else None,
            "boundary_count": boundaries,
            "boundary_pct": round(100 * boundaries / legal_balls, 1) if legal_balls else None,
            "dismissal_types": dict(Counter(
                str(v).lower() for v in group.loc[group["credited_dismissal"], "wicket_type"]
            )),
            "phase_splits": phases, "recent_encounters": recent,
            "sample_tier": _tier(legal_balls, dismissals),
            "matchup_score": round(score, 1),
            "score_label": "Batter advantage" if score >= 62 else "Bowler advantage" if score <= 38 else "Neutral",
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "competition": "ipl_male",
        "source": {"provider": "Cricsheet", "dataset": "ipl_male_csv2"},
        "rivalries": rows,
    }
```

### Pipeline integration

Add a `step_rivalries()` immediately after the Cricsheet step in `pipeline/run_pipeline.py`, then save its output with existing `_save()` calls:

```python
def step_rivalries() -> dict:
    import pandas as pd
    from pipeline.build_rivalries import build_rivalries
    raw_path = CACHE_DIR / "raw" / "ipl_ball_by_ball.parquet"
    if not raw_path.exists():
        return {"schema_version": 1, "rivalries": [], "error": "Raw Cricsheet cache unavailable"}
    return build_rivalries(pd.read_parquet(raw_path))

# In run(), after step_cricsheet:
rivalries = step_rivalries()

# In cache write section:
_save("rivalries", rivalries)
```

### New UI page: `pages_app/rivalry_analyzer.py`

```python
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from utils.cache import load_cache
from utils.data import get_todays_matches


def render() -> None:
    st.title("⚔️ Batter vs Bowler Rivalries")
    st.caption("Historical IPL ball-by-ball matchups. Sample size matters.")
    payload = load_cache("rivalries") or {}
    rows = payload.get("rivalries", [])
    if not rows:
        st.info("Rivalry data is not available yet. Run the nightly pipeline to build it.")
        return

    df = pd.DataFrame(rows)
    matches = get_todays_matches()
    options = ["All historical IPL matchups"] + [f"{m['team1']} vs {m['team2']}" for m in matches]
    st.selectbox("Match context", options, help="Use this to orient research; team filtering is added in Phase 2.")

    col1, col2 = st.columns(2)
    with col1:
        batter = st.selectbox("Batter", sorted(df["batter"].unique()))
    with col2:
        bowlers = sorted(df.loc[df["batter"] == batter, "bowler"].unique())
        bowler = st.selectbox("Bowler", bowlers)

    row = df[(df["batter"] == batter) & (df["bowler"] == bowler)].iloc[0]
    if row["sample_tier"] == "low":
        st.warning("Small sample: treat this as context, not a predictive signal.")

    a, b, c, d = st.columns(4)
    a.metric("Runs / balls", f"{row['runs_off_bat']} / {row['legal_balls']}")
    b.metric("Strike rate", f"{row['strike_rate'] or 0:.1f}")
    c.metric("Dismissals", int(row["dismissals"]))
    d.metric("Matchup", row["score_label"])

    phase = pd.DataFrame(row["phase_splits"]).T.reset_index(names="Phase")
    phase["Strike rate"] = (100 * phase["runs_off_bat"] / phase["legal_balls"].replace(0, pd.NA)).round(1)
    st.subheader("By phase")
    st.dataframe(phase[["Phase", "legal_balls", "runs_off_bat", "dismissals", "Strike rate"]], hide_index=True, width="stretch")

    fig = go.Figure(go.Bar(x=phase["Phase"], y=phase["Strike rate"], marker_color="#3498db"))
    fig.update_layout(height=260, yaxis_title="Strike rate", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Recent encounters")
    st.dataframe(pd.DataFrame(row["recent_encounters"]), hide_index=True, width="stretch")
```

Add it to `predictions.py`:

```python
from pages_app import rivalry_analyzer

PAGES = {
    # existing pages ...
    "Rivalry Analyzer": rivalry_analyzer.render,
}
```

### Tests: `tests/test_rivalries.py`

```python
import pandas as pd
from pipeline.build_rivalries import build_rivalries


def test_rivalry_aggregates_runs_balls_and_bowler_credited_wickets():
    df = pd.DataFrame([
        {"match_id": "m1", "batter": "A Batter", "bowler": "B Bowler", "ball": 1.1,
         "runs_off_bat": 4, "wides": 0, "wicket_type": None, "player_dismissed": None},
        {"match_id": "m1", "batter": "A Batter", "bowler": "B Bowler", "ball": 1.2,
         "runs_off_bat": 0, "wides": 0, "wicket_type": "caught", "player_dismissed": "A Batter"},
        {"match_id": "m1", "batter": "A Batter", "bowler": "B Bowler", "ball": 1.3,
         "runs_off_bat": 0, "wides": 1, "wicket_type": None, "player_dismissed": None},
    ])
    result = build_rivalries(df)
    row = result["rivalries"][0]
    assert row["runs_off_bat"] == 4
    assert row["legal_balls"] == 2
    assert row["dismissals"] == 1


def test_run_out_is_not_credited_to_bowler():
    df = pd.DataFrame([{
        "match_id": "m1", "batter": "A Batter", "bowler": "B Bowler", "ball": 1.1,
        "runs_off_bat": 0, "wides": 0, "wicket_type": "run out", "player_dismissed": "A Batter",
    }])
    assert build_rivalries(df)["rivalries"][0]["dismissals"] == 0
```

### Phase 1 acceptance criteria

- A user can choose any historical batter and an opposing bowler.
- The page shows runs, legal balls, strike rate, dismissals, phase splits, and last five encounters.
- Wide deliveries do not inflate balls faced; run-outs do not inflate bowler wickets.
- Every matchup visibly states its sample tier.
- `pytest -q` passes with new coverage.

## Phase 2 — Fixture-specific Match Hub

### Why a separate cache

The Match Hub must be robust when an upstream source fails. Precomputing it means the page needs only local JSON, mirroring the rest of the application.

### Cache contract: `match_hubs.json`

```json
{
  "schema_version": 1,
  "generated_at": "2026-07-12T10:00:00+00:00",
  "matches": {
    "mumbai_indians_vs_chennai_super_kings_2026-04-10": {
      "match": {"match_id": "...", "team1": "Mumbai Indians", "team2": "Chennai Super Kings", "venue": "Wankhede Stadium", "time": "19:30 IST"},
      "prediction": {"team1_win_prob": 0.58, "team2_win_prob": 0.42, "predicted_total": 178, "model_status": "available"},
      "market": {"team1_implied_prob": 0.51, "team2_implied_prob": 0.49, "total_line": 174.5},
      "venue": {"avg_first_innings": 172, "chase_win_rate": 0.44, "pitch_type": "flat"},
      "weather": {"temperature": 29, "humidity": 72, "dew_flag": true},
      "team_form": {"team1": [], "team2": []},
      "key_rivalries": [],
      "top_props": [],
      "data_status": {"fixtures": "available", "odds": "available", "weather": "available", "rivalries": "available"}
    }
  }
}
```

### New module: `pipeline/build_match_hubs.py`

```python
from __future__ import annotations

from datetime import datetime, timezone


def _top_rivalries(rivalries: list[dict], team1_players: set[str], team2_players: set[str]) -> list[dict]:
    pairs = [
        row for row in rivalries
        if (row["batter"] in team1_players and row["bowler"] in team2_players)
        or (row["batter"] in team2_players and row["bowler"] in team1_players)
    ]
    # High sample first, then distance from neutral, then ball volume.
    tier_rank = {"high": 3, "medium": 2, "low": 1}
    return sorted(
        pairs,
        key=lambda r: (tier_rank.get(r.get("sample_tier"), 0), abs(r.get("matchup_score", 50) - 50), r.get("legal_balls", 0)),
        reverse=True,
    )[:5]


def build_match_hubs(matches, props, team_form, venue_stats, rivalries_payload, team_players) -> dict:
    hubs = {}
    rivalries = rivalries_payload.get("rivalries", [])
    for match in matches:
        match_id = match["match_id"]
        t1, t2 = match["team1"], match["team2"]
        t1_players = set(team_players.get(t1, {}).get("batters", []) + team_players.get(t1, {}).get("bowlers", []))
        t2_players = set(team_players.get(t2, {}).get("batters", []) + team_players.get(t2, {}).get("bowlers", []))
        hubs[match_id] = {
            "match": {key: match.get(key) for key in ("match_id", "team1", "team2", "venue", "time", "status")},
            "prediction": {key: match.get(key) for key in ("team1_win_prob", "team2_win_prob", "predicted_total")},
            "market": {
                "team1_implied_prob": match.get("dk_implied_prob_team1"),
                "team2_implied_prob": match.get("dk_implied_prob_team2"),
                "total_line": match.get("dk_total_line"),
            },
            "venue": venue_stats.get(match.get("venue"), {}),
            "weather": {key: match.get(key) for key in ("temperature", "humidity", "dew_flag", "windspeed")},
            "team_form": {"team1": team_form.get(t1, [])[:5], "team2": team_form.get(t2, [])[:5]},
            "key_rivalries": _top_rivalries(rivalries, t1_players, t2_players),
            "top_props": sorted(
                [p for p in props if p.get("match_id") == match_id],
                key=lambda p: abs(float(p.get("edge", 0))), reverse=True,
            )[:5],
            "data_status": {
                "fixtures": "available",
                "odds": "available" if match.get("dk_total_line") is not None else "unavailable",
                "weather": "available" if match.get("temperature") is not None else "unavailable",
                "rivalries": "available" if rivalries else "unavailable",
            },
        }
    return {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "matches": hubs}
```

### Pipeline integration order

Build match hubs **after** `matches_out` and `props_out` exist, and before saving cache files:

```python
from pipeline.build_match_hubs import build_match_hubs
from utils.data import TEAM_PLAYERS

match_hubs = build_match_hubs(
    matches_out, props_out, team_form_serializable, venue_stats, rivalries, TEAM_PLAYERS
)
_save("match_hubs", match_hubs)
```

### UI page: `pages_app/match_hub.py`

```python
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from utils.cache import load_cache


def render() -> None:
    st.title("🧭 Match Hub")
    st.caption("The model, market, conditions, props, and player matchups in one research view.")
    payload = load_cache("match_hubs") or {}
    hubs = payload.get("matches", {})
    if not hubs:
        st.info("No match hub is cached yet. Run the pipeline to generate one.")
        return

    labels = {mid: f"{h['match']['team1']} vs {h['match']['team2']} — {h['match']['venue']}" for mid, h in hubs.items()}
    match_id = st.selectbox("Select match", list(labels), format_func=labels.get)
    hub = hubs[match_id]
    match, prediction, market = hub["match"], hub["prediction"], hub["market"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(match["team1"], f"{100 * prediction['team1_win_prob']:.1f}%")
    c2.metric(match["team2"], f"{100 * prediction['team2_win_prob']:.1f}%")
    c3.metric("Projected total", prediction.get("predicted_total", "N/A"))
    c4.metric("Market total", market.get("total_line", "N/A"))

    st.subheader("Why the model sees the match this way")
    venue, weather = hub["venue"], hub["weather"]
    a, b, c = st.columns(3)
    a.metric("Venue 1st innings", venue.get("avg_first_innings", "N/A"))
    b.metric("Chasing win rate", f"{100 * venue['chase_win_rate']:.0f}%" if venue.get("chase_win_rate") is not None else "N/A")
    c.metric("Dew", "Expected" if weather.get("dew_flag") else "Not expected")

    st.subheader("Key rivalries")
    rivalry_df = pd.DataFrame(hub["key_rivalries"])
    if rivalry_df.empty:
        st.info("No confirmed historical pairings are available for this fixture.")
    else:
        st.dataframe(rivalry_df[["batter", "bowler", "legal_balls", "runs_off_bat", "dismissals", "score_label", "sample_tier"]], hide_index=True, width="stretch")

    st.subheader("Top model-vs-market props")
    props_df = pd.DataFrame(hub["top_props"])
    if not props_df.empty:
        st.dataframe(props_df, hide_index=True, width="stretch")

    unavailable = [k for k, v in hub["data_status"].items() if v != "available"]
    if unavailable:
        st.caption("Unavailable inputs: " + ", ".join(unavailable) + ". The available cached evidence remains usable.")
```

### Phase 2 acceptance criteria

- One selection displays all available evidence for a fixture with no remote calls from Streamlit.
- Missing odds, weather, or rivalry data yields a labelled gap, never an exception.
- The same five highest-priority rivalries are deterministically selected for identical input.
- `Match Hub` appears as a tab in `predictions.py`.

## Phase 3 — Integrate matchup evidence into current pages

### Today’s Matches

Add one compact “Key battle” table per match expander using `match_hubs.json`; do not duplicate analytics calculations in the UI.

```python
from utils.cache import load_cache

hubs = (load_cache("match_hubs") or {}).get("matches", {})
hub = hubs.get(m["match_id"], {})
key_rivalries = hub.get("key_rivalries", [])[:3]
if key_rivalries:
    st.caption("Key historical battles")
    st.dataframe(pd.DataFrame(key_rivalries)[["batter", "bowler", "strike_rate", "dismissals", "sample_tier"]], hide_index=True, width="stretch")
```

### Player Props

Add a `Matchup context` column for prop rows where the player has a top-five opposing rivalry. Use plain language and sample tier:

```python
def rivalry_note(player: str, key_rivalries: list[dict]) -> str:
    relevant = [r for r in key_rivalries if player in (r["batter"], r["bowler"])]
    if not relevant:
        return "No material historical pairing"
    r = relevant[0]
    opponent = r["bowler"] if r["batter"] == player else r["batter"]
    return f"vs {opponent}: {r['score_label']} ({r['sample_tier']} sample)"
```

Do **not** automatically change model projections based on this descriptive score in Phase 3. First log and evaluate whether it improves out-of-sample prop calibration.

### Phase 3 acceptance criteria

- No derived metric in UI differs from the cache contract.
- A user can navigate from a match/prop to the Rivalry Analyzer conceptually (tab label plus prefilled instructions; Streamlit deep linking is optional).
- All labels distinguish `historical descriptive result` from a `model prediction`.

## Phase 4 — Wagon wheel / shot-map feasibility spike

### Research questions

1. Does a source provide per-delivery shot direction or x/y coordinates for IPL matches?
2. Does its license permit display, caching, and derivative visualizations?
3. Can coordinates be normalized across venues and seasons?
4. Can the data be refreshed and attributed without breaking the current nightly job?

### Source adapter interface

Avoid coupling visual code to any provider:

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class ShotLocation:
    match_id: str
    innings: int
    batter: str
    bowler: str
    over: int
    runs_off_bat: int
    x: float  # normalized [-1, 1]
    y: float  # normalized [-1, 1]
    source: str

class ShotLocationProvider(Protocol):
    def fetch(self, match_id: str) -> list[ShotLocation]: ...
```

### Visualization prototype

```python
import plotly.graph_objects as go

def wagon_wheel(locations):
    fig = go.Figure()
    fig.add_shape(type="circle", x0=-1, y0=-1, x1=1, y1=1, line={"color": "#94a3b8"})
    colors = {0: "#94a3b8", 1: "#60a5fa", 2: "#60a5fa", 3: "#60a5fa", 4: "#22c55e", 6: "#f59e0b"}
    for shot in locations:
        fig.add_trace(go.Scatter(x=[0, shot.x], y=[0, shot.y], mode="lines+markers",
            line={"color": colors.get(shot.runs_off_bat, "#94a3b8"), "width": 2},
            marker={"size": 4}, hovertemplate=f"{shot.runs_off_bat} runs<extra></extra>", showlegend=False))
    fig.update_xaxes(visible=False, range=[-1.1, 1.1])
    fig.update_yaxes(visible=False, range=[-1.1, 1.1], scaleanchor="x", scaleratio=1)
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
    return fig
```

### Definition of done

- A source decision document includes cost, terms, retention policy, attribution text, and fallback behavior.
- At least 20 verified deliveries reconcile visually and semantically against source records.
- If no compliant data source is approved, close this phase with no production shot map; retain the Rivalry Analyzer as the durable alternative.

## Phase 5 — Multi-competition expansion

### Configuration model

Replace IPL-specific module constants with configuration but preserve `ipl_male` as default.

```python
# pipeline/competitions.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Competition:
    slug: str
    display_name: str
    cricsheet_url: str
    format: str
    max_overs: int
    team_aliases: dict[str, str]

COMPETITIONS = {
    "ipl_male": Competition(
        slug="ipl_male", display_name="Indian Premier League",
        cricsheet_url="https://cricsheet.org/downloads/ipl_male_csv2.zip",
        format="T20", max_overs=20, team_aliases={},
    ),
}
```

### Rollout rules

1. Add one competition at a time, first historical data, then fixtures, then odds.
2. Never present a betting edge when odds or player-name matching is incomplete.
3. Keep cache names namespaced once there is more than one competition, e.g. `rivalries_ipl_male.json`.
4. Add per-competition data freshness and coverage metrics to `last_updated.json`.

### Acceptance criteria

- Selecting an additional competition cannot alter IPL output or cache data.
- All source links and user-facing labels identify the competition and historical cutoff.
- Tests cover different over lengths and team alias maps.

## Delivery plan

| Milestone | Scope | Estimate | Exit signal |
|---|---|---:|---|
| M0 | Audit + canonical names | 1–2 days | Join-rate report and fixtures built |
| M1 | Rivalry cache, UI, unit tests | 3–5 days | Correct aggregate metrics for sample matches |
| M2 | Match Hub cache and UI | 2–4 days | Complete offline match view works from cache |
| M3 | Current-page integration + usability pass | 1–2 days | Rivalry context is discoverable in match and prop workflows |
| M4 | Shot-map feasibility spike | 1–3 days | Go/no-go source decision, not a promised feature |
| M5 | First additional competition | 3–7 days | Isolated, tested competition configuration |

## Verification checklist

```bash
# Unit tests
pytest -q

# Pipeline without external writes
python -m pipeline.run_pipeline --dry-run --skip-cricsheet

# Build history after a successful Cricsheet cache exists
python -m pipeline.run_pipeline --skip-cricsheet

# Run the UI and verify tabs + empty states manually
streamlit run predictions.py --server.port 5000
```

Before merge, check:

- [ ] Every new cache key appears in `CACHE_FILES`.
- [ ] Each cache has `schema_version` and `generated_at`.
- [ ] Invalid/absent raw data returns a safe, labelled empty payload.
- [ ] All user-facing rate metrics state the denominator or sample tier.
- [ ] No live API call exists in `pages_app/`.
- [ ] New code uses canonical player/team functions for cross-source joins.
- [ ] New tests cover wide, no-ball semantics (after audit), run-out exclusion, missing columns, and low samples.
- [ ] A real sample matchup is manually reconciled against several raw delivery rows.

## Success metrics

Track these after launch, without treating engagement as proof of model quality:

- Rivalry cache build duration and number of non-empty pairings.
- Fixture squad-to-history player-name match rate.
- Match Hub data-completeness rate by input (fixtures, odds, weather, rivalries).
- UI usage: Match Hub opens, rivalry selections, and prop-to-rivalry drill-downs.
- Model research: calibration/ROI of props with and without a material historical matchup, evaluated out of sample.

