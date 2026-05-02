"""
Fetch today's IPL fixtures, live scores, toss results, and squad info
from CricketData.org (formerly CricAPI).
Requires CRICKET_DATA_API_KEY environment variable.
"""
import os
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

BASE_URL = "https://api.cricapi.com/v1"

IPL_KEYWORD = "Indian Premier League"


def _get_api_key() -> str:
    key = os.environ.get("CRICKET_DATA_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "CRICKET_DATA_API_KEY not set. Add it as a GitHub secret and env var."
        )
    return key


def fetch_current_matches() -> list[dict]:
    """Fetch live and upcoming IPL matches."""
    key = _get_api_key()
    url = f"{BASE_URL}/currentMatches"
    params = {"apikey": key, "offset": 0}
    logger.info("Fetching current matches from CricketData.org")
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        logger.warning("CricketData API returned non-success: %s", data.get("status"))
        return []
    matches = data.get("data", [])
    ipl = [m for m in matches if IPL_KEYWORD in m.get("name", "")]
    logger.info("Found %d IPL matches (of %d total)", len(ipl), len(matches))
    return ipl


def fetch_match_info(match_id: str) -> dict:
    """Fetch detailed match info: toss, venue, squads."""
    key = _get_api_key()
    url = f"{BASE_URL}/match_info"
    params = {"apikey": key, "id": match_id}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", {})


def parse_fixtures(raw_matches: list[dict]) -> list[dict]:
    """
    Parse CricketData fixtures into a clean format aligned with our data model.
    """
    fixtures = []
    for m in raw_matches:
        teams = m.get("teams", [])
        team1 = teams[0] if len(teams) > 0 else "TBD"
        team2 = teams[1] if len(teams) > 1 else "TBD"

        toss_winner = None
        toss_decision = None
        toss_data = m.get("tossWinner", "")
        toss_choice = m.get("tossChoice", "")
        if toss_data:
            toss_winner = toss_data
            toss_decision = toss_choice.lower() if toss_choice else None

        date_str = m.get("date", "") or m.get("dateTimeGMT", "")
        try:
            match_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            match_time_ist = match_dt.astimezone(timezone.utc)
            time_label = match_time_ist.strftime("%H:%M IST")
        except Exception:
            time_label = "TBD"

        fixtures.append({
            "match_id": m.get("id", ""),
            "team1": team1,
            "team2": team2,
            "venue": m.get("venue", ""),
            "time": time_label,
            "status": m.get("status", ""),
            "toss_winner": toss_winner,
            "toss_decision": toss_decision,
            "matchStarted": m.get("matchStarted", False),
            "matchEnded": m.get("matchEnded", False),
        })
    return fixtures


def run() -> list[dict]:
    """Full fixtures pipeline: fetch → parse → return."""
    raw = fetch_current_matches()
    fixtures = parse_fixtures(raw)
    logger.info("Parsed %d IPL fixtures", len(fixtures))
    return fixtures


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fixtures = run()
    for f in fixtures:
        logger.info("%s vs %s @ %s (%s)", f["team1"], f["team2"], f["venue"], f["time"])
