"""Competition status tracking and production state definitions.

Production states are defined in PRODUCTION_PLAN.md Phase 0.
Each competition must have explicit status before being shown to users.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ProductionStatus(StrEnum):
    """Production readiness states for competitions."""

    NOT_ENABLED = "not_enabled"
    NOT_RUN = "not_run"
    FETCH_FAILED = "fetch_failed"
    NO_FIXTURES = "no_fixtures"
    NO_DRAFTKINGS_MARKET = "no_draftkings_market"
    HISTORICAL_DATA_INSUFFICIENT = "historical_data_insufficient"
    MODEL_NOT_READY = "model_not_ready"
    NO_QUALIFYING_BETS = "no_qualifying_bets"
    READY = "ready"
    STALE = "stale"


@dataclass
class CompetitionStatus:
    """Detailed status for a single competition.

    This is the evidence-backed truth for whether a competition should be shown
    to users and what predictions (if any) can be published.
    """

    competition_slug: str
    status: ProductionStatus
    last_successful_run: str | None = None
    last_run_attempt: str | None = None
    fixture_count: int = 0
    draftkings_event_count: int = 0
    historical_match_count: int = 0
    historical_seasons: list[str] = field(default_factory=list)
    team_identity_rate: float = 0.0
    player_identity_rate: float = 0.0
    model_version: str | None = None
    qualifying_bet_count: int = 0
    error_details: dict[str, Any] = field(default_factory=dict)
    data_age_hours: float | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON cache."""
        return {
            "competition_slug": self.competition_slug,
            "status": self.status.value,
            "last_successful_run": self.last_successful_run,
            "last_run_attempt": self.last_run_attempt,
            "fixture_count": self.fixture_count,
            "draftkings_event_count": self.draftkings_event_count,
            "historical_match_count": self.historical_match_count,
            "historical_seasons": self.historical_seasons,
            "team_identity_rate": self.team_identity_rate,
            "player_identity_rate": self.player_identity_rate,
            "model_version": self.model_version,
            "qualifying_bet_count": self.qualifying_bet_count,
            "error_details": self.error_details,
            "data_age_hours": self.data_age_hours,
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompetitionStatus:
        """Deserialize from JSON cache."""
        return cls(
            competition_slug=data["competition_slug"],
            status=ProductionStatus(data["status"]),
            last_successful_run=data.get("last_successful_run"),
            last_run_attempt=data.get("last_run_attempt"),
            fixture_count=data.get("fixture_count", 0),
            draftkings_event_count=data.get("draftkings_event_count", 0),
            historical_match_count=data.get("historical_match_count", 0),
            historical_seasons=data.get("historical_seasons", []),
            team_identity_rate=data.get("team_identity_rate", 0.0),
            player_identity_rate=data.get("player_identity_rate", 0.0),
            model_version=data.get("model_version"),
            qualifying_bet_count=data.get("qualifying_bet_count", 0),
            error_details=data.get("error_details", {}),
            data_age_hours=data.get("data_age_hours"),
            warnings=data.get("warnings", []),
        )


def determine_status(
    enabled: bool,
    last_run: str | None,
    fixtures: int,
    dk_events: int,
    historical_matches: int,
    model_version: str | None,
    qualifying_bets: int,
    data_age_hours: float | None,
    errors: dict[str, Any],
) -> ProductionStatus:
    """Apply production readiness gates to determine competition status.

    This is the single authoritative function that classifies a competition's
    production state based on pipeline evidence.
    """
    if not enabled:
        return ProductionStatus.NOT_ENABLED

    if last_run is None:
        return ProductionStatus.NOT_RUN

    if errors:
        return ProductionStatus.FETCH_FAILED

    if fixtures == 0:
        return ProductionStatus.NO_FIXTURES

    if dk_events == 0:
        return ProductionStatus.NO_DRAFTKINGS_MARKET

    # Minimum historical threshold: at least 100 matches to train a model
    if historical_matches < 100:
        return ProductionStatus.HISTORICAL_DATA_INSUFFICIENT

    if model_version is None:
        return ProductionStatus.MODEL_NOT_READY

    if qualifying_bets == 0:
        return ProductionStatus.NO_QUALIFYING_BETS

    # Stale if data is older than 36 hours
    if data_age_hours is not None and data_age_hours > 36:
        return ProductionStatus.STALE

    return ProductionStatus.READY


def plain_language_status(status: ProductionStatus) -> str:
    """Convert status enum to user-friendly description."""
    mapping = {
        ProductionStatus.NOT_ENABLED: "Not enabled for production",
        ProductionStatus.NOT_RUN: "Pipeline has not run",
        ProductionStatus.FETCH_FAILED: "Data fetch failed",
        ProductionStatus.NO_FIXTURES: "No fixtures scheduled",
        ProductionStatus.NO_DRAFTKINGS_MARKET: "No DraftKings market available",
        ProductionStatus.HISTORICAL_DATA_INSUFFICIENT: "Historical data not ready",
        ProductionStatus.MODEL_NOT_READY: "Model not ready",
        ProductionStatus.NO_QUALIFYING_BETS: "No qualifying bets today",
        ProductionStatus.READY: "Live and ready",
        ProductionStatus.STALE: "Data is stale",
    }
    return mapping.get(status, str(status))
