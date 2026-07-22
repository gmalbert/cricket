"""Tests for cache-first rivalry and Match Hub features."""
from __future__ import annotations

import pandas as pd
import pytest

from pipeline.build_match_hubs import build_match_hubs, top_rivalries
from pipeline.build_rivalries import build_rivalries
from pipeline.competitions import get_competition
from pipeline.normalization import canonical_team
from pipeline.shot_locations import ShotLocation, empty_shot_locations, serialize_locations
import pipeline.run_pipeline as run_pipeline


def _delivery(**overrides):
    row = {
        "match_id": "m1",
        "start_date": "2026-04-01",
        "striker": "A Batter",
        "bowler": "B Bowler",
        "ball": 1.1,
        "runs_off_bat": 0,
        "wides": 0,
        "noballs": 0,
        "wicket_type": None,
        "player_dismissed": None,
    }
    row.update(overrides)
    return row


def test_rivalry_counts_runs_legal_balls_and_credited_dismissals():
    frame = pd.DataFrame([
        _delivery(ball=1.1, runs_off_bat=4),
        _delivery(ball=1.2, wicket_type="caught", player_dismissed="A Batter"),
        _delivery(ball=1.3, wides=1),
        _delivery(ball=1.4, noballs=1, runs_off_bat=1),
    ])
    row = build_rivalries(frame)["rivalries"][0]
    assert row["runs_off_bat"] == 5
    assert row["legal_balls"] == 2
    assert row["dismissals"] == 1
    assert row["phase_splits"]["powerplay"]["legal_balls"] == 2


def test_rivalry_excludes_run_out_from_bowler_dismissals():
    frame = pd.DataFrame([_delivery(wicket_type="run out", player_dismissed="A Batter")])
    assert build_rivalries(frame)["rivalries"][0]["dismissals"] == 0


def test_rivalry_returns_labelled_empty_payload_when_required_columns_missing():
    payload = build_rivalries(pd.DataFrame([{"bowler": "B Bowler"}]))
    assert payload["rivalries"] == []
    assert "Missing required columns" in payload["error"]


def test_match_hub_is_cache_only_and_selects_cross_team_rivalries():
    rivalry = {
        "key": "a__b", "batter": "A Batter", "bowler": "B Bowler", "sample_tier": "high",
        "matchup_score": 70, "legal_balls": 40, "runs_off_bat": 60, "dismissals": 1,
    }
    match = {
        "match_id": "m1", "team1": "Team A", "team2": "Team B", "venue": "Venue",
        "team1_win_prob": 0.6, "team2_win_prob": 0.4, "predicted_total": 180,
        "dk_total_line": 175, "temperature": 29,
    }
    result = build_match_hubs(
        [match], [{"match_id": "m1", "player": "A Batter", "edge": 5}],
        {"Team A": [], "Team B": []}, {"Venue": {"avg_first_innings": 170}},
        {"rivalries": [rivalry]},
        {"Team A": {"batters": ["A Batter"], "bowlers": []}, "Team B": {"batters": [], "bowlers": ["B Bowler"]}},
    )
    hub = result["matches"]["m1"]
    assert hub["key_rivalries"] == [rivalry]
    assert hub["data_status"]["rivalries"] == "available"


def test_top_rivalries_ignores_same_team_pairings():
    rows = [
        {"key": "same", "batter": "A", "bowler": "C", "sample_tier": "high", "matchup_score": 90, "legal_balls": 50},
        {"key": "cross", "batter": "A", "bowler": "B", "sample_tier": "medium", "matchup_score": 60, "legal_balls": 20},
    ]
    assert top_rivalries(rows, {"A", "C"}, {"B"}) == [rows[1]]


def test_competition_and_team_alias_configuration():
    assert get_competition().max_overs == 20
    assert canonical_team("Royal Challengers Bangalore") == "Royal Challengers Bengaluru"
    with pytest.raises(ValueError):
        get_competition("unknown")


def test_shot_location_contract_is_explicit_when_no_provider_is_configured():
    assert empty_shot_locations()["status"] == "unavailable"
    location = ShotLocation("m1", 1, "A", "B", 3, 4, 0.2, -0.3, "licensed-provider")
    assert serialize_locations([location])["locations"][0]["source"] == "licensed-provider"


def test_pipeline_writes_match_intelligence_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pipeline, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(run_pipeline, "step_reconcile", lambda dry_run: ([], 0))
    monkeypatch.setattr(run_pipeline, "step_cricsheet", lambda skip: {
        "team_form": {"Team A": [], "Team B": []},
        "player_stats": {"batters": {}, "bowlers": {}},
        "venue_stats": {"Venue": {"avg_first_innings": 170, "chase_win_rate": 0.5}},
    })
    monkeypatch.setattr(run_pipeline, "step_rivalries", lambda: {"schema_version": 1, "rivalries": []})
    monkeypatch.setattr(run_pipeline, "step_fixtures", lambda: [])
    monkeypatch.setattr(run_pipeline, "step_odds", lambda: [])
    monkeypatch.setattr(run_pipeline, "step_weather", lambda fixtures: {})
    monkeypatch.setattr(run_pipeline, "step_features", lambda *args: ([], []))
    monkeypatch.setattr(run_pipeline, "step_models", lambda *args: ([], [], []))
    monkeypatch.setattr(run_pipeline, "step_monte_carlo", lambda *args: {})
    monkeypatch.setattr(run_pipeline, "step_matchup_edge", lambda *args: {})

    run_pipeline.run(dry_run=False)

    assert (tmp_path / "rivalries.json").exists()
    assert (tmp_path / "match_hubs.json").exists()
    assert (tmp_path / "shot_locations.json").exists()
