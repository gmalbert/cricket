"""
Feature engineering for match-level and player-level ML models.
Consumes outputs from the Cricsheet, fixtures, odds, and weather pipelines.
"""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent.parent / "cache" / "raw"

VENUE_PITCH_TYPE = {
    "Wankhede Stadium": "flat",
    "MA Chidambaram Stadium": "turning",
    "M. Chinnaswamy Stadium": "flat",
    "Eden Gardens": "balanced",
    "Arun Jaitley Stadium": "flat",
    "Narendra Modi Stadium": "flat",
    "Rajiv Gandhi Intl Cricket Stadium": "flat",
    "Sawai Mansingh Stadium": "balanced",
    "BRSABV Ekana Cricket Stadium": "balanced",
    "Himachal Pradesh Cricket Association Stadium": "seaming",
}

TEAM_HOME_VENUES = {
    "Mumbai Indians": "Wankhede Stadium",
    "Chennai Super Kings": "MA Chidambaram Stadium",
    "Royal Challengers Bengaluru": "M. Chinnaswamy Stadium",
    "Kolkata Knight Riders": "Eden Gardens",
    "Delhi Capitals": "Arun Jaitley Stadium",
    "Gujarat Titans": "Narendra Modi Stadium",
    "Sunrisers Hyderabad": "Rajiv Gandhi Intl Cricket Stadium",
    "Rajasthan Royals": "Sawai Mansingh Stadium",
    "Lucknow Super Giants": "BRSABV Ekana Cricket Stadium",
    "Punjab Kings": "Himachal Pradesh Cricket Association Stadium",
}


def build_match_features(
    fixtures: list[dict],
    team_form: dict,
    venue_stats: dict,
    weather: dict,
    odds: list[dict],
) -> list[dict]:
    """
    Combine all data sources into a match-level feature vector for each fixture.
    Returns a list of feature dicts ready for model inference.
    """
    odds_lookup = {}
    for o in odds:
        key = (o.get("team1", ""), o.get("team2", ""))
        odds_lookup[key] = o
        odds_lookup[(o.get("team2", ""), o.get("team1", ""))] = {
            **o,
            "team1": o["team2"],
            "team2": o["team1"],
            "dk_implied_prob_team1": o.get("dk_implied_prob_team2"),
            "dk_implied_prob_team2": o.get("dk_implied_prob_team1"),
        }

    feature_rows = []
    for fix in fixtures:
        t1 = fix["team1"]
        t2 = fix["team2"]
        venue = fix.get("venue", "")

        form1 = team_form.get(t1, [])
        form2 = team_form.get(t2, [])

        def avg_score(form, n=5):
            scores = [m["score"] for m in form[:n] if m.get("score")]
            return round(np.mean(scores), 1) if scores else None

        def avg_pp(form, n=10):
            pp = [m["powerplay_runs"] for m in form[:n] if m.get("powerplay_runs")]
            return round(np.mean(pp), 1) if pp else None

        def avg_death_econ(form, n=10):
            de = [m["death_economy"] for m in form[:n] if m.get("death_economy")]
            return round(np.mean(de), 2) if de else None

        vs = venue_stats.get(venue, {})
        wx = weather.get(venue, {})
        dk = odds_lookup.get((t1, t2), {})

        toss_winner = fix.get("toss_winner")
        toss_decision = fix.get("toss_decision")

        features = {
            "match_id": fix.get("match_id", ""),
            "team1": t1,
            "team2": t2,
            "venue": venue,
            "time": fix.get("time", ""),
            "toss_winner": toss_winner,
            "toss_decision": toss_decision,
            "toss_winner_is_team1": 1 if toss_winner == t1 else (0 if toss_winner == t2 else None),
            "toss_decision_bat": 1 if toss_decision == "bat" else (0 if toss_decision else None),
            "team1_avg_score_last5": avg_score(form1),
            "team2_avg_score_last5": avg_score(form2),
            "team1_powerplay_avg": avg_pp(form1),
            "team2_powerplay_avg": avg_pp(form2),
            "team1_death_economy": avg_death_econ(form1),
            "team2_death_economy": avg_death_econ(form2),
            "venue_avg_first_innings": vs.get("avg_first_innings"),
            "venue_chase_win_rate": vs.get("chase_win_rate"),
            "pitch_type": VENUE_PITCH_TYPE.get(venue, "balanced"),
            "is_home_ground_t1": 1 if TEAM_HOME_VENUES.get(t1) == venue else 0,
            "is_home_ground_t2": 1 if TEAM_HOME_VENUES.get(t2) == venue else 0,
            "temperature": wx.get("temperature"),
            "humidity": wx.get("humidity"),
            "dewpoint": wx.get("dewpoint"),
            "windspeed": wx.get("windspeed"),
            "dew_flag": wx.get("dew_flag", False),
            "dk_implied_prob_team1": dk.get("dk_implied_prob_team1"),
            "dk_implied_prob_team2": dk.get("dk_implied_prob_team2"),
            "dk_odds_team1": dk.get("dk_odds_team1"),
            "dk_odds_team2": dk.get("dk_odds_team2"),
        }
        feature_rows.append(features)

    logger.info("Built feature vectors for %d matches", len(feature_rows))
    return feature_rows


def build_player_features(
    fixtures: list[dict],
    player_stats: dict,
    match_features: list[dict],
) -> list[dict]:
    """
    Build player-level features for batter/bowler prop models.
    """
    batters_stats = player_stats.get("batters", {})
    bowlers_stats = player_stats.get("bowlers", {})

    from utils.data import TEAM_PLAYERS

    prop_rows = []
    for fix in fixtures:
        mf = next((m for m in match_features if m["match_id"] == fix.get("match_id")), {})

        for team in [fix["team1"], fix["team2"]]:
            team_players = TEAM_PLAYERS.get(team, {})
            for player in team_players.get("batters", []):
                stats = batters_stats.get(player, {})
                prop_rows.append(
                    {
                        "match_id": fix.get("match_id", ""),
                        "player": player,
                        "team": team,
                        "role": "Batter",
                        "recent_avg": stats.get("recent_avg"),
                        "recent_sr": stats.get("recent_sr"),
                        "recent_scores": stats.get("recent_scores", []),
                        "venue_avg_first_innings": mf.get("venue_avg_first_innings"),
                        "dew_flag": mf.get("dew_flag"),
                        "is_home": 1 if TEAM_HOME_VENUES.get(team) == fix.get("venue") else 0,
                    }
                )
            for player in team_players.get("bowlers", []):
                stats = bowlers_stats.get(player, {})
                prop_rows.append(
                    {
                        "match_id": fix.get("match_id", ""),
                        "player": player,
                        "team": team,
                        "role": "Bowler",
                        "recent_economy": stats.get("recent_economy"),
                        "recent_wickets_pm": stats.get("recent_wickets_per_match"),
                        "wickets_last5": stats.get("wickets_last5", []),
                        "pitch_type": mf.get("pitch_type"),
                        "dew_flag": mf.get("dew_flag"),
                        "is_home": 1 if TEAM_HOME_VENUES.get(team) == fix.get("venue") else 0,
                    }
                )

    logger.info("Built player feature vectors for %d entries", len(prop_rows))
    return prop_rows
