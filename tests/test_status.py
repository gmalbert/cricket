"""Tests for production status and competition tracking."""
import pytest
from datetime import datetime, timezone

from pipeline.status import (
    ProductionStatus,
    CompetitionStatus,
    determine_status,
    plain_language_status,
)


def test_production_status_enum():
    """Test that all production statuses are defined."""
    assert ProductionStatus.NOT_ENABLED == "not_enabled"
    assert ProductionStatus.READY == "ready"
    assert ProductionStatus.STALE == "stale"


def test_determine_status_not_enabled():
    """Test status determination for disabled competition."""
    status = determine_status(
        enabled=False,
        last_run=None,
        fixtures=0,
        dk_events=0,
        historical_matches=0,
        model_version=None,
        qualifying_bets=0,
        data_age_hours=None,
        errors={},
    )
    assert status == ProductionStatus.NOT_ENABLED


def test_determine_status_not_run():
    """Test status determination for never-run competition."""
    status = determine_status(
        enabled=True,
        last_run=None,
        fixtures=0,
        dk_events=0,
        historical_matches=0,
        model_version=None,
        qualifying_bets=0,
        data_age_hours=None,
        errors={},
    )
    assert status == ProductionStatus.NOT_RUN


def test_determine_status_fetch_failed():
    """Test status determination for failed fetch."""
    status = determine_status(
        enabled=True,
        last_run="2026-07-22T10:00:00Z",
        fixtures=0,
        dk_events=0,
        historical_matches=0,
        model_version=None,
        qualifying_bets=0,
        data_age_hours=1.0,
        errors={"fixtures": "Network error"},
    )
    assert status == ProductionStatus.FETCH_FAILED


def test_determine_status_no_fixtures():
    """Test status determination for no fixtures."""
    status = determine_status(
        enabled=True,
        last_run="2026-07-22T10:00:00Z",
        fixtures=0,
        dk_events=0,
        historical_matches=200,
        model_version="v1",
        qualifying_bets=0,
        data_age_hours=1.0,
        errors={},
    )
    assert status == ProductionStatus.NO_FIXTURES


def test_determine_status_no_draftkings():
    """Test status determination for no DraftKings market."""
    status = determine_status(
        enabled=True,
        last_run="2026-07-22T10:00:00Z",
        fixtures=5,
        dk_events=0,
        historical_matches=200,
        model_version="v1",
        qualifying_bets=0,
        data_age_hours=1.0,
        errors={},
    )
    assert status == ProductionStatus.NO_DRAFTKINGS_MARKET


def test_determine_status_historical_insufficient():
    """Test status determination for insufficient historical data."""
    status = determine_status(
        enabled=True,
        last_run="2026-07-22T10:00:00Z",
        fixtures=5,
        dk_events=5,
        historical_matches=50,  # Less than 100
        model_version="v1",
        qualifying_bets=0,
        data_age_hours=1.0,
        errors={},
    )
    assert status == ProductionStatus.HISTORICAL_DATA_INSUFFICIENT


def test_determine_status_model_not_ready():
    """Test status determination for missing model."""
    status = determine_status(
        enabled=True,
        last_run="2026-07-22T10:00:00Z",
        fixtures=5,
        dk_events=5,
        historical_matches=200,
        model_version=None,  # No model
        qualifying_bets=0,
        data_age_hours=1.0,
        errors={},
    )
    assert status == ProductionStatus.MODEL_NOT_READY


def test_determine_status_no_qualifying_bets():
    """Test status determination for no qualifying bets."""
    status = determine_status(
        enabled=True,
        last_run="2026-07-22T10:00:00Z",
        fixtures=5,
        dk_events=5,
        historical_matches=200,
        model_version="v1",
        qualifying_bets=0,  # No bets meet criteria
        data_age_hours=1.0,
        errors={},
    )
    assert status == ProductionStatus.NO_QUALIFYING_BETS


def test_determine_status_stale():
    """Test status determination for stale data."""
    status = determine_status(
        enabled=True,
        last_run="2026-07-20T10:00:00Z",
        fixtures=5,
        dk_events=5,
        historical_matches=200,
        model_version="v1",
        qualifying_bets=3,
        data_age_hours=48.0,  # Stale
        errors={},
    )
    assert status == ProductionStatus.STALE


def test_determine_status_ready():
    """Test status determination for ready competition."""
    status = determine_status(
        enabled=True,
        last_run="2026-07-22T10:00:00Z",
        fixtures=5,
        dk_events=5,
        historical_matches=200,
        model_version="v1",
        qualifying_bets=3,
        data_age_hours=1.0,
        errors={},
    )
    assert status == ProductionStatus.READY


def test_plain_language_status():
    """Test plain language status conversion."""
    assert plain_language_status(ProductionStatus.READY) == "Live and ready"
    assert plain_language_status(ProductionStatus.NOT_ENABLED) == "Not enabled for production"
    assert plain_language_status(ProductionStatus.NO_FIXTURES) == "No fixtures scheduled"


def test_competition_status_serialization():
    """Test CompetitionStatus serialization."""
    status = CompetitionStatus(
        competition_slug="ipl_male",
        status=ProductionStatus.READY,
        last_successful_run="2026-07-22T10:00:00Z",
        fixture_count=5,
        draftkings_event_count=5,
        qualifying_bet_count=3,
    )
    
    # Serialize
    data = status.to_dict()
    assert data["competition_slug"] == "ipl_male"
    assert data["status"] == "ready"
    assert data["fixture_count"] == 5
    
    # Deserialize
    status2 = CompetitionStatus.from_dict(data)
    assert status2.competition_slug == "ipl_male"
    assert status2.status == ProductionStatus.READY
    assert status2.fixture_count == 5
