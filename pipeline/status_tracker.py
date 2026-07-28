"""Competition status tracking and publishing.

This module provides functions to build, update, and publish competition
status information based on pipeline execution results.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from pipeline.competitions import COMPETITIONS
from pipeline.status import CompetitionStatus, ProductionStatus, determine_status

logger = logging.getLogger(__name__)


def build_competition_status(
    competition_slug: str,
    pipeline_result: dict[str, Any],
    run_timestamp: str | None = None,
) -> CompetitionStatus:
    """Build a CompetitionStatus from pipeline results.

    Args:
        competition_slug: Competition identifier
        pipeline_result: Dictionary containing pipeline execution results
        run_timestamp: ISO timestamp of the pipeline run

    Returns:
        CompetitionStatus with all fields populated from pipeline evidence
    """
    competition = COMPETITIONS.get(competition_slug)
    if not competition:
        return CompetitionStatus(
            competition_slug=competition_slug,
            status=ProductionStatus.NOT_ENABLED,
            error_details={"error": f"Unknown competition: {competition_slug}"},
        )

    # Extract pipeline results
    fixtures = pipeline_result.get("fixtures", [])
    odds = pipeline_result.get("odds", [])
    historical = pipeline_result.get("historical_coverage", {}).get(competition_slug, {})
    model_info = pipeline_result.get("model_info", {}).get(competition_slug, {})
    bets = pipeline_result.get("value_bets", [])
    errors = pipeline_result.get("errors", {}).get(competition_slug, {})

    # Filter to this competition
    comp_fixtures = [f for f in fixtures if f.get("competition") == competition_slug]
    comp_odds = [o for o in odds if o.get("competition") == competition_slug]
    comp_bets = [b for b in bets if b.get("competition") == competition_slug]

    # Calculate data age
    data_age_hours = None
    if run_timestamp:
        try:
            run_dt = datetime.fromisoformat(run_timestamp.replace("Z", "+00:00"))
            age = (datetime.now(UTC) - run_dt).total_seconds() / 3600
            data_age_hours = age
        except (ValueError, AttributeError):
            pass

    # Determine status
    status = determine_status(
        enabled=competition.enabled,
        last_run=run_timestamp,
        fixtures=len(comp_fixtures),
        dk_events=len(comp_odds),
        historical_matches=historical.get("completed_matches", 0),
        model_version=model_info.get("version"),
        qualifying_bets=len(comp_bets),
        data_age_hours=data_age_hours,
        errors=errors,
    )

    # Build the status object
    return CompetitionStatus(
        competition_slug=competition_slug,
        status=status,
        last_successful_run=run_timestamp if status == ProductionStatus.READY else None,
        last_run_attempt=run_timestamp,
        fixture_count=len(comp_fixtures),
        draftkings_event_count=len(comp_odds),
        historical_match_count=historical.get("completed_matches", 0),
        historical_seasons=historical.get("seasons", []),
        team_identity_rate=historical.get("team_identity_rate", 0.0),
        player_identity_rate=historical.get("player_identity_rate", 0.0),
        model_version=model_info.get("version"),
        qualifying_bet_count=len(comp_bets),
        error_details=errors,
        data_age_hours=data_age_hours,
        warnings=pipeline_result.get("warnings", {}).get(competition_slug, []),
    )


def build_all_competition_statuses(
    pipeline_result: dict[str, Any],
    run_timestamp: str | None = None,
) -> list[CompetitionStatus]:
    """Build status for all competitions in the registry.

    Args:
        pipeline_result: Dictionary containing pipeline execution results
        run_timestamp: ISO timestamp of the pipeline run

    Returns:
        List of CompetitionStatus objects for all competitions
    """
    statuses = []
    for competition_slug in COMPETITIONS:
        status = build_competition_status(
            competition_slug=competition_slug,
            pipeline_result=pipeline_result,
            run_timestamp=run_timestamp,
        )
        statuses.append(status)
    return statuses


def serialize_statuses(statuses: list[CompetitionStatus]) -> dict[str, Any]:
    """Serialize competition statuses for JSON cache.

    Args:
        statuses: List of CompetitionStatus objects

    Returns:
        Dictionary ready for JSON serialization
    """
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "competitions": [status.to_dict() for status in statuses],
    }


def load_competition_status(data: dict[str, Any]) -> list[CompetitionStatus]:
    """Deserialize competition statuses from JSON cache.

    Args:
        data: Dictionary from JSON cache

    Returns:
        List of CompetitionStatus objects
    """
    if not data or "competitions" not in data:
        return []

    return [CompetitionStatus.from_dict(comp) for comp in data["competitions"]]
