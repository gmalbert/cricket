"""
Fetch current IPL odds from The Odds API.
Requires ODDS_API_KEY environment variable.
Endpoint: /v4/sports/cricket_ipl/odds
"""
import os
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

from pipeline.competitions import Competition, enabled_competitions, get_competition
from pipeline.normalization import canonical_team, unordered_team_match_key

logger = logging.getLogger(__name__)

load_dotenv()

BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "cricket_ipl"
REGIONS = "us"
MARKETS = "h2h"
ODDS_FORMAT = "american"

BOOKMAKERS = {"draftkings"}

# The Odds API key may be shared across multiple repositories. Keep the
# default nightly footprint small; expand explicitly with environment config.
DEFAULT_ODDS_COMPETITIONS = (
    "ipl_male", "international_t20", "odi_internationals", "big_bash",
    "the_hundred", "t20_blast",
)


def _get_api_key() -> str:
    key = os.environ.get("ODDS_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "ODDS_API_KEY not set. Add it as a GitHub secret and env var."
        )
    return key


def fetch_odds_for_competition(competition: Competition) -> list[dict]:
    """
    Fetch current IPL match odds from The Odds API.
    Returns a list of match dicts with bookmaker lines.
    """
    if not competition.odds_api_key:
        logger.info("No verified Odds API key for %s; recording as unpriced", competition.display_name)
        return []
    key = _get_api_key()
    sport_key = competition.odds_api_key or SPORT_KEY
    url = f"{BASE_URL}/sports/{sport_key}/odds"
    params = {
        "apiKey": key,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": ODDS_FORMAT,
    }
    logger.info("Fetching %s odds from The Odds API", competition.display_name)
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    logger.info("Received odds for %d matches", len(data))
    for event in data:
        event["sport_key"] = sport_key
        event["competition"] = competition.slug
        event["competition_name"] = competition.display_name
        event["format"] = competition.format
        event["gender"] = competition.gender
    return data


def fetch_ipl_odds() -> list[dict]:
    """Backward-compatible IPL odds entry point."""
    return fetch_odds_for_competition(get_competition("ipl_male"))


def parse_odds(raw: list[dict]) -> list[dict]:
    """
    Parse raw Odds API response into a clean list of match dicts.
    Each dict contains team names, commence_time, and DraftKings implied probs.
    """
    matches = []
    for event in raw:
        home = canonical_team(event.get("home_team", ""))
        away = canonical_team(event.get("away_team", ""))
        commence = event.get("commence_time", "")

        dk_prob_home = None
        dk_prob_away = None
        dk_odds_home = None
        dk_odds_away = None

        bookmaker_key = None
        bookmaker_updated = None
        market_id = None
        event_recorded = datetime.now().isoformat()
        for bm in event.get("bookmakers", []):
            if bm["key"] not in BOOKMAKERS:
                continue
            bookmaker_key = bm.get("key")
            bookmaker_updated = bm.get("last_update")
            for market in bm.get("markets", []):
                if market["key"] != "h2h":
                    continue
                market_id = market.get("key")
                for outcome in market.get("outcomes", []):
                    price = outcome["price"]
                    if price > 0:
                        imp = 100 / (price + 100)
                    else:
                        imp = abs(price) / (abs(price) + 100)
                    outcome_name = canonical_team(outcome.get("name", ""))
                    if outcome_name == home:
                        dk_prob_home = round(imp, 4)
                        dk_odds_home = price
                    elif outcome_name == away:
                        dk_prob_away = round(imp, 4)
                        dk_odds_away = price
            break

        if dk_prob_home and dk_prob_away:
            total = dk_prob_home + dk_prob_away
            dk_prob_home = round(dk_prob_home / total, 4)
            dk_prob_away = round(dk_prob_away / total, 4)

        matches.append({
            "event_id": event.get("id", ""),
            "team1": home,
            "team2": away,
            "commence_time": commence,
            "dk_implied_prob_team1": dk_prob_home,
            "dk_implied_prob_team2": dk_prob_away,
            "dk_odds_team1": dk_odds_home,
            "dk_odds_team2": dk_odds_away,
            "sport_key": event.get("sport_key", SPORT_KEY),
            "competition": event.get("competition", "ipl_male"),
            "competition_name": event.get("competition_name", "Indian Premier League"),
            "format": event.get("format", "T20"),
            "gender": event.get("gender", "male"),
            "bookmaker": bookmaker_key,
            "market": market_id or "h2h",
            "odds_timestamp": bookmaker_updated or event_recorded,
            "first_observed_price_team1": dk_odds_home,
            "first_observed_price_team2": dk_odds_away,
            "closing_price_team1": dk_odds_home,
            "closing_price_team2": dk_odds_away,
            "event_status": "draftkings_available" if bookmaker_key == "draftkings" and dk_prob_home and dk_prob_away else "no_draftkings_market",
        })
    return matches


def fetch_ipl_scores() -> list[dict]:
    """Fetch live/recent IPL scores from The Odds API scores endpoint."""
    key = _get_api_key()
    url = f"{BASE_URL}/sports/{SPORT_KEY}/scores"
    params = {"apiKey": key, "daysFrom": 1}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def run() -> list[dict]:
    """Full odds pipeline: fetch → parse → return."""
    matches = []
    configured = os.environ.get("ODDS_API_COMPETITIONS", ",".join(DEFAULT_ODDS_COMPETITIONS))
    allowed = {slug.strip() for slug in configured.split(",") if slug.strip()}
    try:
        max_requests = max(1, int(os.environ.get("ODDS_API_MAX_REQUESTS", "6")))
    except ValueError:
        max_requests = 6
    requested = 0
    for competition in enabled_competitions():
        if competition.slug not in allowed:
            continue
        if not competition.odds_api_key:
            continue
        if requested >= max_requests:
            logger.warning("Odds request budget reached (%d); remaining competitions deferred", max_requests)
            break
        try:
            requested += 1
            matches.extend(parse_odds(fetch_odds_for_competition(competition)))
        except requests.HTTPError as exc:
            logger.warning("Odds unavailable for %s: %s", competition.slug, exc)
        except Exception as exc:
            logger.warning("Odds fetch failed for %s: %s", competition.slug, exc)
    logger.info("Parsed odds for %d registered matches", len(matches))
    return matches


def match_odds_for_fixture(fixture: dict, odds: list[dict]) -> dict | None:
    """Find odds despite provider ordering and team-name aliases."""
    key = unordered_team_match_key(fixture.get("team1"), fixture.get("team2"))
    for record in odds:
        if unordered_team_match_key(record.get("team1"), record.get("team2")) == key:
            return record
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    matches = run()
    for m in matches:
        logger.info("%s vs %s | DK: %.1f%% / %.1f%%",
                    m["team1"], m["team2"],
                    (m["dk_implied_prob_team1"] or 0) * 100,
                    (m["dk_implied_prob_team2"] or 0) * 100)
