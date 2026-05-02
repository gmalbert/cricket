"""
Fetch current IPL odds from The Odds API.
Requires ODDS_API_KEY environment variable.
Endpoint: /v4/sports/cricket_ipl/odds
"""
import os
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "cricket_ipl"
REGIONS = "us"
MARKETS = "h2h"
ODDS_FORMAT = "american"

BOOKMAKERS = {"draftkings", "fanduel", "betmgm", "caesars"}


def _get_api_key() -> str:
    key = os.environ.get("ODDS_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "ODDS_API_KEY not set. Add it as a GitHub secret and env var."
        )
    return key


def fetch_ipl_odds() -> list[dict]:
    """
    Fetch current IPL match odds from The Odds API.
    Returns a list of match dicts with bookmaker lines.
    """
    key = _get_api_key()
    url = f"{BASE_URL}/sports/{SPORT_KEY}/odds"
    params = {
        "apiKey": key,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": ODDS_FORMAT,
    }
    logger.info("Fetching IPL odds from The Odds API")
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    logger.info("Received odds for %d matches", len(data))
    return data


def parse_odds(raw: list[dict]) -> list[dict]:
    """
    Parse raw Odds API response into a clean list of match dicts.
    Each dict contains team names, commence_time, and DraftKings implied probs.
    """
    matches = []
    for event in raw:
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        commence = event.get("commence_time", "")

        dk_prob_home = None
        dk_prob_away = None
        dk_odds_home = None
        dk_odds_away = None

        for bm in event.get("bookmakers", []):
            if bm["key"] not in BOOKMAKERS:
                continue
            for market in bm.get("markets", []):
                if market["key"] != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    price = outcome["price"]
                    if price > 0:
                        imp = 100 / (price + 100)
                    else:
                        imp = abs(price) / (abs(price) + 100)
                    if outcome["name"] == home:
                        dk_prob_home = round(imp, 4)
                        dk_odds_home = price
                    elif outcome["name"] == away:
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
    raw = fetch_ipl_odds()
    matches = parse_odds(raw)
    logger.info("Parsed odds for %d IPL matches", len(matches))
    return matches


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    matches = run()
    for m in matches:
        logger.info("%s vs %s | DK: %.1f%% / %.1f%%",
                    m["team1"], m["team2"],
                    (m["dk_implied_prob_team1"] or 0) * 100,
                    (m["dk_implied_prob_team2"] or 0) * 100)
