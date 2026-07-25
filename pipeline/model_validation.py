"""Model versioning, validation, and publish gates.

This module provides infrastructure for tracking model versions,
validating predictions, and enforcing publish gates.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Metadata for a trained model artifact."""

    model_name: str
    version: str
    training_date: str
    data_range_start: str
    data_range_end: str
    competition: str
    format: str
    gender: str
    feature_schema_version: int
    training_samples: int
    validation_samples: int
    brier_score: float | None = None
    log_loss: float | None = None
    accuracy: float | None = None
    calibration_slope: float | None = None
    calibration_intercept: float | None = None
    baseline_comparison: dict[str, float] = field(default_factory=dict)
    artifact_hash: str | None = None
    metadata_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "model_name": self.model_name,
            "version": self.version,
            "training_date": self.training_date,
            "data_range_start": self.data_range_start,
            "data_range_end": self.data_range_end,
            "competition": self.competition,
            "format": self.format,
            "gender": self.gender,
            "feature_schema_version": self.feature_schema_version,
            "training_samples": self.training_samples,
            "validation_samples": self.validation_samples,
            "brier_score": self.brier_score,
            "log_loss": self.log_loss,
            "accuracy": self.accuracy,
            "calibration_slope": self.calibration_slope,
            "calibration_intercept": self.calibration_intercept,
            "baseline_comparison": self.baseline_comparison,
            "artifact_hash": self.artifact_hash,
            "metadata_version": self.metadata_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelMetadata:
        """Deserialize from dict."""
        return cls(
            model_name=data["model_name"],
            version=data["version"],
            training_date=data["training_date"],
            data_range_start=data["data_range_start"],
            data_range_end=data["data_range_end"],
            competition=data["competition"],
            format=data["format"],
            gender=data["gender"],
            feature_schema_version=data["feature_schema_version"],
            training_samples=data["training_samples"],
            validation_samples=data["validation_samples"],
            brier_score=data.get("brier_score"),
            log_loss=data.get("log_loss"),
            accuracy=data.get("accuracy"),
            calibration_slope=data.get("calibration_slope"),
            calibration_intercept=data.get("calibration_intercept"),
            baseline_comparison=data.get("baseline_comparison", {}),
            artifact_hash=data.get("artifact_hash"),
            metadata_version=data.get("metadata_version", 1),
        )


def generate_model_version(
    model_name: str,
    training_date: datetime,
    competition: str,
) -> str:
    """Generate a unique model version string.

    Format: {model_name}_{competition}_{date}_{hash}
    Example: t20_h2h_ipl_male_20260722_a1b2c3
    """
    date_str = training_date.strftime("%Y%m%d")
    hash_input = f"{model_name}_{competition}_{training_date.isoformat()}"
    short_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:6]
    return f"{model_name}_{competition}_{date_str}_{short_hash}"


def validate_model_predictions(
    predictions: list[dict[str, Any]],
    model_metadata: ModelMetadata,
) -> tuple[bool, list[str]]:
    """Validate model predictions before publishing.

    Args:
        predictions: List of prediction dicts
        model_metadata: Model metadata

    Returns:
        Tuple of (is_valid, list of validation errors)
    """
    errors = []

    # Check prediction structure
    if not predictions:
        errors.append("No predictions to validate")
        return False, errors

    # Check required fields
    required_fields = ["match_id", "team1_win_prob", "team2_win_prob", "model_version"]
    for i, pred in enumerate(predictions[:10]):  # Sample first 10
        missing = [f for f in required_fields if f not in pred]
        if missing:
            errors.append(f"Prediction {i} missing fields: {missing}")

    # Check probability bounds
    for i, pred in enumerate(predictions):
        p1 = pred.get("team1_win_prob")
        p2 = pred.get("team2_win_prob")

        if p1 is None or p2 is None:
            errors.append(f"Prediction {i} has None probabilities")
            continue

        if not (0 <= p1 <= 1):
            errors.append(f"Prediction {i} team1_win_prob out of bounds: {p1}")
        if not (0 <= p2 <= 1):
            errors.append(f"Prediction {i} team2_win_prob out of bounds: {p2}")

        # Probabilities should sum to ~1.0
        total = p1 + p2
        if not (0.95 <= total <= 1.05):
            errors.append(f"Prediction {i} probabilities don't sum to 1: {total}")

    # Check model version consistency
    versions = {pred.get("model_version") for pred in predictions}
    if len(versions) > 1:
        errors.append(f"Multiple model versions in predictions: {versions}")

    # Check metadata quality thresholds
    if model_metadata.brier_score is not None and model_metadata.brier_score > 0.30:
        errors.append(f"Brier score too high: {model_metadata.brier_score:.4f}")

    if model_metadata.training_samples < 100:
        errors.append(f"Insufficient training samples: {model_metadata.training_samples}")

    return len(errors) == 0, errors


def check_publish_gates(
    predictions: list[dict[str, Any]],
    model_metadata: ModelMetadata,
    fixtures: list[dict[str, Any]],
    odds: list[dict[str, Any]],
    historical_coverage: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Check all publish gates before allowing predictions to go live.

    Args:
        predictions: List of predictions
        model_metadata: Model metadata
        fixtures: Fixture data
        odds: Odds data
        historical_coverage: Historical data coverage info

    Returns:
        Tuple of (can_publish, list of blocking reasons)
    """
    blockers = []

    # Gate 1: Model validation
    valid, errors = validate_model_predictions(predictions, model_metadata)
    if not valid:
        blockers.extend(errors)

    # Gate 2: Historical coverage
    min_matches = 100
    completed = historical_coverage.get("completed_matches", 0)
    if completed < min_matches:
        blockers.append(f"Insufficient historical data: {completed} < {min_matches}")

    # Gate 3: Identity coverage
    team_rate = historical_coverage.get("team_identity_rate", 0)
    player_rate = historical_coverage.get("player_identity_rate", 0)
    if team_rate < 0.80:
        blockers.append(f"Team identity rate too low: {team_rate:.2%}")
    if player_rate < 0.70:
        blockers.append(f"Player identity rate too low: {player_rate:.2%}")

    # Gate 4: Fixture-odds matching
    {f.get("match_id") for f in fixtures if f.get("match_id")}
    predictions_with_odds = [p for p in predictions if p.get("dk_implied_prob_team1") is not None]
    if len(predictions_with_odds) == 0 and len(odds) > 0:
        blockers.append("No predictions matched to odds")

    # Gate 5: Market freshness
    # Check if odds timestamps are recent (within 48 hours)
    now = datetime.now(UTC)
    stale_odds = []
    for odd in odds:
        ts_str = odd.get("odds_timestamp")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                age_hours = (now - ts).total_seconds() / 3600
                if age_hours > 48:
                    stale_odds.append(age_hours)
            except (ValueError, AttributeError):
                pass

    if stale_odds and len(stale_odds) > len(odds) * 0.5:
        blockers.append(f"More than 50% of odds are stale (>{max(stale_odds):.1f}h old)")

    # Gate 6: Model artifact exists
    if model_metadata.artifact_hash is None:
        blockers.append("Model artifact hash not recorded")

    return len(blockers) == 0, blockers


def save_model_metadata(metadata: ModelMetadata, cache_dir: Path) -> None:
    """Save model metadata to cache."""
    models_dir = cache_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = models_dir / f"{metadata.version}_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata.to_dict(), f, indent=2)

    logger.info("Saved model metadata: %s", metadata.version)


def load_model_metadata(version: str, cache_dir: Path) -> ModelMetadata | None:
    """Load model metadata from cache."""
    models_dir = cache_dir / "models"
    metadata_path = models_dir / f"{version}_metadata.json"

    if not metadata_path.exists():
        return None

    try:
        with open(metadata_path) as f:
            data = json.load(f)
        return ModelMetadata.from_dict(data)
    except Exception as e:
        logger.error("Failed to load model metadata %s: %s", version, e)
        return None


def list_available_models(cache_dir: Path, competition: str | None = None) -> list[ModelMetadata]:
    """List all available model metadata files.

    Args:
        cache_dir: Cache directory path
        competition: Optional filter by competition slug

    Returns:
        List of ModelMetadata objects
    """
    models_dir = cache_dir / "models"
    if not models_dir.exists():
        return []

    metadatas = []
    for path in models_dir.glob("*_metadata.json"):
        try:
            with open(path) as f:
                data = json.load(f)
            metadata = ModelMetadata.from_dict(data)

            if competition is None or metadata.competition == competition:
                metadatas.append(metadata)
        except Exception as e:
            logger.warning("Failed to load metadata from %s: %s", path, e)

    return sorted(metadatas, key=lambda m: m.training_date, reverse=True)
