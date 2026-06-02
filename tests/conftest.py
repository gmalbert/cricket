"""
conftest.py — shared fixtures for cricket pipeline tests.
"""

import json
import pytest
from pathlib import Path

SAMPLE_TEAM_FORM = {
    "Mumbai Indians": {
        "avg_score_last5": 172.4,
        "powerplay_avg": 48.2,
        "death_economy": 9.1,
        "home_ground": "Wankhede Stadium",
    },
    "Chennai Super Kings": {
        "avg_score_last5": 168.1,
        "powerplay_avg": 45.5,
        "death_economy": 8.6,
        "home_ground": "MA Chidambaram Stadium",
    },
}

SAMPLE_VENUE_STATS = {
    "Wankhede Stadium": {
        "avg_first_innings": 175,
        "chase_win_rate": 0.45,
        "city": "Mumbai",
    },
    "MA Chidambaram Stadium": {
        "avg_first_innings": 165,
        "chase_win_rate": 0.48,
        "city": "Chennai",
    },
}

SAMPLE_TODAY_MATCH = {
    "match_id": "MI_vs_CSK_2025-04-10",
    "team1": "Mumbai Indians",
    "team2": "Chennai Super Kings",
    "venue": "Wankhede Stadium",
    "match_date": "2025-04-10",
    "team1_win_prob": 0.55,
    "team2_win_prob": 0.45,
}


@pytest.fixture
def sample_team_form() -> dict:
    return SAMPLE_TEAM_FORM


@pytest.fixture
def sample_venue_stats() -> dict:
    return SAMPLE_VENUE_STATS


@pytest.fixture
def sample_match() -> dict:
    return SAMPLE_TODAY_MATCH


@pytest.fixture
def cache_dir(tmp_path) -> Path:
    """Temporary cache directory mirroring production structure."""
    d = tmp_path / "cache"
    d.mkdir()
    (d / "models").mkdir()
    return d
