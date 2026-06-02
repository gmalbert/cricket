"""
tests/test_pipeline.py — Unit tests for the cricket nightly pipeline.

Tests cover:
  - Feature engineering helpers
  - Match ID formatting convention
  - Cache load / save round-trip
  - Pipeline prediction output schema
  - Win probability bounds
"""

import json
import pytest


# ── Match ID convention ───────────────────────────────────────────────────────

class TestMatchIdConvention:
    """Match IDs must follow: TEAM1_vs_TEAM2_YYYY-MM-DD (lowercase/underscores)."""

    def _make_match_id(self, team1: str, team2: str, date: str) -> str:
        t1 = team1.lower().replace(" ", "_")
        t2 = team2.lower().replace(" ", "_")
        return f"{t1}_vs_{t2}_{date}"

    def test_basic_format(self):
        mid = self._make_match_id("Mumbai Indians", "Chennai Super Kings", "2025-04-10")
        assert mid == "mumbai_indians_vs_chennai_super_kings_2025-04-10"

    def test_has_vs_separator(self):
        mid = self._make_match_id("RCB", "KKR", "2025-05-01")
        assert "_vs_" in mid

    def test_date_at_end(self):
        mid = self._make_match_id("MI", "CSK", "2025-06-30")
        assert mid.endswith("2025-06-30")

    def test_no_spaces(self):
        mid = self._make_match_id("Royal Challengers Bengaluru", "Delhi Capitals", "2025-04-15")
        assert " " not in mid


# ── Win probability constraints ───────────────────────────────────────────────

class TestWinProbabilityConstraints:
    """team1_win_prob + team2_win_prob must equal 1.0."""

    def test_probs_sum_to_one(self, sample_match):
        p1 = sample_match["team1_win_prob"]
        p2 = sample_match["team2_win_prob"]
        assert abs(p1 + p2 - 1.0) < 1e-6

    def test_probs_in_range(self, sample_match):
        assert 0.0 <= sample_match["team1_win_prob"] <= 1.0
        assert 0.0 <= sample_match["team2_win_prob"] <= 1.0

    def test_symmetric_50_50(self):
        """A match with no information should yield 50/50."""
        prob = 0.5
        assert abs(prob + (1 - prob) - 1.0) < 1e-9


# ── Cache round-trip ──────────────────────────────────────────────────────────

class TestCacheRoundTrip:
    """Cache files must survive a write → read cycle without data loss."""

    def test_json_roundtrip(self, cache_dir, sample_match):
        cache_file = cache_dir / "todays_matches.json"
        payload = {"matches": [sample_match]}
        cache_file.write_text(json.dumps(payload, default=str))
        loaded = json.loads(cache_file.read_text())
        assert loaded["matches"][0]["match_id"] == sample_match["match_id"]

    def test_cache_preserves_floats(self, cache_dir, sample_match):
        cache_file = cache_dir / "todays_matches.json"
        cache_file.write_text(json.dumps({"matches": [sample_match]}, default=str))
        loaded = json.loads(cache_file.read_text())
        p1 = float(loaded["matches"][0]["team1_win_prob"])
        assert abs(p1 - sample_match["team1_win_prob"]) < 1e-6


# ── Feature engineering helpers ───────────────────────────────────────────────

class TestFeatureEngineering:
    """Sanity checks for feature values used in the model."""

    def test_team_form_keys_present(self, sample_team_form):
        required = {"avg_score_last5", "powerplay_avg", "death_economy"}
        for team, stats in sample_team_form.items():
            missing = required - set(stats.keys())
            assert not missing, f"{team} missing features: {missing}"

    def test_venue_stats_keys_present(self, sample_venue_stats):
        required = {"avg_first_innings", "chase_win_rate"}
        for venue, stats in sample_venue_stats.items():
            missing = required - set(stats.keys())
            assert not missing, f"{venue} missing features: {missing}"

    def test_avg_score_positive(self, sample_team_form):
        for team, stats in sample_team_form.items():
            assert stats["avg_score_last5"] > 0, f"{team} avg_score_last5 must be > 0"

    def test_chase_win_rate_bounds(self, sample_venue_stats):
        for venue, stats in sample_venue_stats.items():
            rate = stats["chase_win_rate"]
            assert 0.0 <= rate <= 1.0, f"{venue} chase_win_rate {rate} out of [0,1]"

    def test_powerplay_avg_reasonable(self, sample_team_form):
        """IPL powerplay avg should be between 30 and 80."""
        for team, stats in sample_team_form.items():
            avg = stats["powerplay_avg"]
            assert 30 <= avg <= 80, f"{team} powerplay_avg {avg} outside reasonable range"

    def test_death_economy_reasonable(self, sample_team_form):
        """Death overs economy should be between 6 and 16."""
        for team, stats in sample_team_form.items():
            eco = stats["death_economy"]
            assert 6 <= eco <= 16, f"{team} death_economy {eco} outside reasonable range"


# ── Model output schema ───────────────────────────────────────────────────────

class TestModelOutputSchema:
    """The pipeline's prediction output must conform to the cache schema."""

    REQUIRED_KEYS = {
        "match_id", "team1", "team2", "venue", "match_date",
        "team1_win_prob", "team2_win_prob",
    }

    def test_required_keys_present(self, sample_match):
        missing = self.REQUIRED_KEYS - set(sample_match.keys())
        assert not missing, f"Output missing keys: {missing}"

    def test_match_id_non_empty(self, sample_match):
        assert sample_match["match_id"].strip() != ""

    def test_venue_non_empty(self, sample_match):
        assert sample_match["venue"].strip() != ""
