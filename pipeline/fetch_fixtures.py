"""
Fetch today's IPL fixtures, live scores, toss results, and squad info
from CricketData.org (formerly CricAPI).
Requires CRICKET_DATA_API_KEY environment variable.
"""

import logging
import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from pipeline.competitions import Competition, enabled_competitions, find_competition
from pipeline.normalization import canonical_team, unordered_team_match_key

logger = logging.getLogger(__name__)

load_dotenv()

BASE_URL = "https://api.cricapi.com/v1"

IPL_KEYWORD = "Indian Premier League"


def _get_api_key() -> str:
    key = os.environ.get("CRICKET_DATA_API_KEY", "")
    if not key:
        raise OSError("CRICKET_DATA_API_KEY not set. Add it as a GitHub secret and env var.")
    return key


def fetch_current_matches() -> list[dict]:
    """Fetch live and upcoming matches from CricketData."""
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
    logger.info("Found %d current matches", len(matches))
    return matches


def select_registered_matches(matches: list[dict], competitions: list[Competition] | None = None) -> list[dict]:
    """Select and annotate matches recognized by the competition registry."""
    selected = []
    for match in matches:
        competition = find_competition(match.get("name") or match.get("series") or match.get("competition"))
        if competition is None or (competitions is not None and competition not in competitions):
            continue
        row = dict(match)
        row["competition"] = competition.slug
        row["competition_name"] = competition.display_name
        row["format"] = competition.format
        row["gender"] = competition.gender
        row["teams"] = [canonical_team(team) for team in row.get("teams", [])]
        selected.append(row)
    return selected


def fetch_match_info(match_id: str) -> dict:
    """Fetch detailed match info: toss, venue, squads."""
    key = _get_api_key()
    url = f"{BASE_URL}/match_info"
    params = {"apikey": key, "id": match_id}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", {})


def fetch_series(limit: int = 100) -> list[dict]:
    """Fetch series metadata used to discover non-IPL competitions."""
    key = _get_api_key()
    resp = requests.get(f"{BASE_URL}/series", params={"apikey": key, "offset": 0}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])[:limit] if data.get("status") == "success" else []


def fetch_series_matches(series_id: str) -> list[dict]:
    """Fetch all matches for one discovered series."""
    key = _get_api_key()
    resp = requests.get(f"{BASE_URL}/series_info", params={"apikey": key, "id": series_id}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        return []
    payload = data.get("data", {})
    return payload.get("matchList", payload.get("matches", []))


def discover_registered_series(competitions: list[Competition] | None = None) -> list[dict]:
    """Discover registry competitions through the series endpoint."""
    discovered = []
    for series in fetch_series():
        competition = find_competition(series.get("name") or series.get("seriesName"))
        if competition is None or (competitions is not None and competition not in competitions):
            continue
        row = dict(series)
        row["competition"] = competition.slug
        row["competition_name"] = competition.display_name
        row["format"] = competition.format
        row["gender"] = competition.gender
        discovered.append(row)
    return discovered


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
            match_time_ist = match_dt.astimezone(UTC)
            time_label = match_time_ist.strftime("%H:%M IST")
        except Exception:
            time_label = "TBD"

        fixtures.append(
            {
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
                "competition": m.get("competition", "ipl_male"),
                "competition_name": m.get("competition_name", m.get("name", "")),
                "format": m.get("format", "T20"),
                "gender": m.get("gender", "male"),
                "scheduled_start": m.get("dateTimeGMT", date_str),
                "city": m.get("city", ""),
                "fixture_source": m.get("fixture_source", "cricketdata"),
                "fixture_status": m.get("fixture_status", "confirmed"),
            }
        )
    return fixtures


def filter_current_fixtures(fixtures: list[dict], reference_date=None) -> list[dict]:
    """Keep fixtures scheduled for today or later.

    CricketData's ``currentMatches`` response can include recently completed
    matches. Those records are valid fixtures, but they do not belong on the
    Today's Matches board. Fixtures without a parseable date are retained so
    an upstream schema change does not silently hide a match.
    """
    today = reference_date or datetime.now(ZoneInfo("America/New_York")).date()
    current = []
    for fixture in fixtures:
        scheduled_start = fixture.get("scheduled_start") or ""
        try:
            scheduled_date = datetime.fromisoformat(scheduled_start.replace("Z", "+00:00")).date()
        except (TypeError, ValueError):
            current.append(fixture)
            continue
        if scheduled_date >= today:
            current.append(fixture)
        else:
            logger.info(
                "Skipping past fixture from Today's Matches: %s vs %s (%s)",
                fixture.get("team1"),
                fixture.get("team2"),
                scheduled_start,
            )
    return current


def add_odds_provisional_fixtures(fixtures: list[dict], odds: list[dict]) -> list[dict]:
    """Add DraftKings-backed events absent from the schedule provider.

    Odds events are sufficient to expose a market for monitoring, but the
    explicit provisional marker lets downstream consumers distinguish them
    from schedule-confirmed fixtures.
    """
    known = {unordered_team_match_key(f.get("team1"), f.get("team2")) for f in fixtures}
    provisional = list(fixtures)
    for event in odds:
        if event.get("event_status") != "draftkings_available":
            continue
        key = unordered_team_match_key(event.get("team1"), event.get("team2"))
        if not event.get("team1") or not event.get("team2") or key in known:
            continue
        provisional.append(
            {
                "match_id": event.get("event_id", ""),
                "team1": canonical_team(event.get("team1", "")),
                "team2": canonical_team(event.get("team2", "")),
                "venue": "",
                "city": "",
                "time": event.get("commence_time", "TBD"),
                "scheduled_start": event.get("commence_time", ""),
                "status": "Scheduled from DraftKings market",
                "matchStarted": False,
                "matchEnded": False,
                "competition": event.get("competition", "ipl_male"),
                "competition_name": event.get("competition_name", ""),
                "format": event.get("format", "T20"),
                "gender": event.get("gender", "male"),
                "fixture_source": "odds_api",
                "fixture_status": "provisional",
            }
        )
        known.add(key)
    return provisional


def run() -> list[dict]:
    """Full fixtures pipeline: fetch → parse → return."""
    registered = enabled_competitions()
    raw = select_registered_matches(fetch_current_matches(), registered)
    if not raw:
        # The currentMatches endpoint is not a reliable discovery mechanism
        # for scheduled international series, so use the registry-aware path.
        for series in discover_registered_series(registered):
            try:
                series_matches = fetch_series_matches(series.get("id", series.get("seriesId", "")))
            except Exception as exc:
                logger.warning("Could not fetch series %s: %s", series.get("name", series.get("id")), exc)
                continue
            for match in series_matches:
                annotated = dict(match)
                annotated.update({key: series[key] for key in ("competition", "competition_name", "format", "gender")})
                raw.append(annotated)
    fixtures = filter_current_fixtures(parse_fixtures(raw))
    logger.info("Parsed %d registered fixtures", len(fixtures))
    return fixtures


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fixtures = run()
    for f in fixtures:
        logger.info("%s vs %s @ %s (%s)", f["team1"], f["team2"], f["venue"], f["time"])
