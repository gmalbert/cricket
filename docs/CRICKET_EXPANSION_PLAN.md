# Cricket Expansion Plan: Beyond IPL

## Objective

Expand the cricket pipeline from an IPL-only system into a competition-aware system that can publish reliable DraftKings-backed picks across the cricket markets visible in the sportsbook.

The expansion must preserve three distinctions:

1. A competition can have fixtures but no DraftKings market.
2. A competition can have a market but insufficient historical/model data.
3. A competition can have both, but no bet may pass the value threshold.

An empty export must identify which of these occurred.

## Current limitation

The cricket repository is IPL-specific in all three major data paths:

- `pipeline/fetch_fixtures.py` calls the current-matches endpoint and filters names for `Indian Premier League`.
- `pipeline/fetch_odds.py` requests only the `cricket_ipl` sport key.
- `pipeline/fetch_cricsheet.py` downloads only the IPL ball-by-ball archive.
- Team, venue, Monte Carlo, and documentation assumptions are also IPL-specific.

Therefore, the dashboard cannot currently discover or model the other DraftKings competitions even when they are available.

## Target competition registry

The registry should be configuration-driven rather than hard-coded into the fetchers.

| Priority | Competition / format | Odds API key to verify | Historical data path | Initial recommendation |
|---|---|---|---|---|
| 1 | International T20 | `cricket_international_t20` | T20 internationals | Add first; broad player/team coverage |
| 1 | ODI internationals | `cricket_odi` | One-day internationals | Add as a separate ODI model |
| 1 | Big Bash League | `cricket_big_bash` | Big Bash | Strong domestic T20 candidate |
| 1 | The Hundred | `cricket_the_hundred` | The Hundred | Good sportsbook alignment |
| 1 | T20 Blast | `cricket_t20_blast` | T20 Blast | Large historical sample |
| 2 | Pakistan Super League | `cricket_psl` | PSL | Add after team/player mapping |
| 2 | Caribbean Premier League | `cricket_caribbean_premier_league` | CPL | Add after venue and roster mapping |
| 2 | SA20 | Verify current key | SA20 | Good candidate, smaller sample |
| 2 | ICC T20 World Cup | `cricket_t20_world_cup` | T20 World Cup | Event-based model and limited sample |
| 2 | ICC World Cup | `cricket_icc_world_cup` / verify key | ODI World Cup | Event-based model and limited sample |
| 3 | Test matches | `cricket_test_match` | Tests | Separate long-format model; not a T20 extension |
| 3 | Women’s competitions | Verify competition-specific keys | Women’s BBL, women’s internationals, women’s T20 leagues | Add only with gender-specific calibration |

The Odds API’s official sports list currently includes cricket keys for Big Bash, CPL, International T20, IPL, ODI, PSL, T20 Blast, T20 World Cup, Test matches, and The Hundred. Availability and DraftKings coverage must still be checked per event. [The Odds API sports list](https://the-odds-api.com/sports-odds-data/sports-apis.html)

## Data available for expansion

### Live and schedule data

CricketData provides series, schedules, match details, squads, scorecards, and ball-by-ball endpoints. Its current schedule includes international tours, Major League Cricket, Lanka Premier League, The Hundred, and other domestic and women’s competitions. [CricketData schedule](https://cricketdata.org/cricket-data-formats/schedule) · [CricketData series list](https://cricketdata.org/cricket-data-formats/series)

The pipeline should use the series and matches endpoints, not only `currentMatches`. Each fetched record should retain:

- `competition_id` and `competition_name`
- `match_id`
- format: T20, ODI, or Test
- gender
- teams and scheduled start time
- venue and city
- status, toss, and playing XI when available

### Historical performance data

Cricsheet provides ball-by-ball data for more than IPL. Current coverage includes international cricket, Big Bash, CPL, The Hundred, T20 Blast, PSL, SA20, Major League Cricket, Lanka Premier League, Super Smash, Women’s Big Bash, and multiple other competitions. [Cricsheet coverage](https://cricsheet.org/) · [Cricsheet downloads](https://cricsheet.org/downloads/)

The repository should replace the single IPL download with a competition-aware historical loader. The loader should record data coverage before enabling a competition:

```text
competition → seasons available → matches available → players mapped → last update
```

### Market and pricing data

The current model requests only `h2h`. The Odds API supports `h2h`, totals, spreads, and outrights where a bookmaker offers them, but cricket market availability will vary by competition and event. [Odds API odds endpoint](https://the-odds-api.com/liveapi/guides/v4/)

For each event, store:

- DraftKings event and market identifiers
- market type and selection
- American price and implied probability
- bookmaker update timestamp
- first observed price and closing price
- whether the price was pre-match or live

The screenshot confirms that DraftKings exposes competition categories beyond IPL, but the app category alone is not proof that an API-compatible DraftKings line exists for every match.

## Model design

Do not train one undifferentiated cricket model immediately. Use a shared feature layer with format- and competition-specific calibration.

### Shared features

- Team strength and recent form
- Player batting and bowling rates
- Opponent-adjusted performance
- Venue and city effects
- Toss and innings position
- Playing XI availability
- Rest, travel, and schedule density
- Weather and expected conditions
- Market-implied probability

### Separate model boundaries

- T20 leagues: shared base model plus competition calibration
- T20 internationals: separate international/player-availability calibration
- ODIs: separate model because innings length and scoring dynamics differ
- Tests: separate model entirely
- Women’s cricket: gender-specific model or calibration layer
- World Cups and short tournaments: shrink toward the relevant format model because samples are small

Every prediction should include `format`, `gender`, `competition`, `model_version`, and `training_coverage`.

## Pipeline changes

### Phase 1 — Registry and observability

1. Create a competition registry with aliases, format, gender, schedule filters, odds key, historical dataset, and season window.
2. Replace the IPL-only fixture filter with registry-driven series/match selection.
3. Replace `fetch_ipl_odds()` with a loop over enabled odds keys.
4. Preserve the source `sport_key`, competition, event ID, bookmaker, and market in the normalized data.
5. Emit explicit statuses:
   - `fixtures_found`
   - `odds_found`
   - `draftkings_available`
   - `historical_data_ready`
   - `model_ready`
   - `qualifying_bets`
6. Do not report `no_picks` when the real condition is `no_draftkings_market`, `fixtures_fetch_failed`, or `historical_data_insufficient`.

### Phase 2 — Historical data and identity mapping

1. Download and normalize Cricsheet data by competition and format.
2. Normalize team names across CricketData, Cricsheet, and DraftKings.
3. Resolve player aliases and competition transfers.
4. Add coverage checks for players, teams, venues, and seasons.
5. Backfill historical odds where available; otherwise clearly mark the model as unpriced/backtest-only.

### Phase 3 — Match-winner picks

Start with the current supported market: pre-match match winner (`h2h`). Do not add props or totals until match identity, odds timestamps, and settlement are reliable.

For each candidate:

```text
fixture → model probability → DraftKings price → no-vig probability → edge → tier → export
```

### Phase 4 — Additional markets

Only add totals, run lines, player props, or tournament outrights after confirming that the specific competition has stable DraftKings market coverage and sufficient historical labels. These markets require additional inputs such as expected lineup, batting order, innings allocation, and venue-adjusted scoring distributions.

## Rollout recommendation

### Release 1: highest confidence

- International T20
- ODI internationals
- Big Bash
- The Hundred
- T20 Blast

These have the best combination of sportsbook visibility, historical data, and recognizable team/player identities.

### Release 2: broader T20 leagues

- PSL
- CPL
- SA20
- ICC T20 World Cup
- MLC
- Lanka Premier League

Enable only when the per-competition coverage report passes the minimum thresholds.

### Release 3: specialist formats

- Tests
- Women’s competitions
- World Cup outrights
- Lower-volume domestic competitions

These require separate calibration and should not be presented as equivalent to the core T20 picks.

## Minimum enablement criteria

A competition may publish picks only when all conditions are met:

- Current fixtures are available from a successful source.
- DraftKings odds are present for the event and selected market.
- At least two seasons or a documented minimum sample are available for the format/model.
- Team and player identity matching succeeds above an agreed threshold.
- The model is calibrated separately for the competition or format.
- The export records odds timestamp, source commit, competition, format, and model version.
- Results can later be settled using a reliable scorecard source.

## Acceptance tests

1. The pipeline discovers a non-IPL fixture without changing code.
2. A DraftKings event is matched to the correct fixture despite team-name aliases.
3. A competition with fixtures but no DraftKings price is reported as `no_draftkings_market`.
4. A competition with insufficient historical data is reported as `model_not_ready`.
5. T20, ODI, Test, and women’s predictions carry distinct model metadata.
6. A valid no-bet day is distinguishable from a failed schedule or odds fetch.
7. Historical picks retain competition, format, odds, and source timestamps for grading.
8. Hermes can state exactly why a competition did not produce a bet.

## Recommended first implementation

Begin with the registry, broader fixture discovery, and multi-key odds discovery. Then enable International T20, ODI, Big Bash, The Hundred, and T20 Blast one at a time. Keep IPL as a regression case and require a side-by-side comparison of fixture counts, DraftKings matches, model coverage, and settled performance before expanding further.
