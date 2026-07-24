"""Tests for model validation and publish gates."""
import pytest
from datetime import datetime

from pipeline.model_validation import (
    ModelMetadata,
    generate_model_version,
    validate_model_predictions,
)


def test_generate_model_version():
    """Test model version generation."""
    version = generate_model_version("xgboost", "ipl_male", "abcdef123456")
    
    assert version.startswith("xgboost_ipl_male_")
    assert version.endswith("_abcdef")  # First 6 chars of hash


def test_model_metadata_creation():
    """Test ModelMetadata creation and serialization."""
    metadata = ModelMetadata(
        model_name="xgboost",
        version="xgboost_ipl_male_20260722_abc123",
        training_date="2026-07-22",
        data_range_start="2024-01-01",
        data_range_end="2026-07-21",
        competition="ipl_male",
        format="t20",
        gender="male",
        feature_schema_version=1,
        training_samples=1000,
        validation_samples=200,
        brier_score=0.18,
        log_loss=0.42,
        accuracy=0.65,
        calibration_slope=0.95,
        calibration_intercept=0.02,
        baseline_comparison=0.15,
        artifact_hash="abcdef123456",
    )
    
    # Test serialization
    data = metadata.to_dict()
    assert data["model_name"] == "xgboost"
    assert data["brier_score"] == 0.18
    
    # Test deserialization
    metadata2 = ModelMetadata.from_dict(data)
    assert metadata2.model_name == "xgboost"
    assert metadata2.brier_score == 0.18


def test_validate_model_predictions_valid():
    """Test validation of valid predictions."""
    predictions = [
        {
            "match_id": "match1",
            "team1": "Team A",
            "team2": "Team B",
            "team1_win_prob": 0.65,
            "team2_win_prob": 0.35,
            "model_version": "xgboost_v1",
        },
        {
            "match_id": "match2",
            "team1": "Team C",
            "team2": "Team D",
            "team1_win_prob": 0.55,
            "team2_win_prob": 0.45,
            "model_version": "xgboost_v1",
        },
    ]
    
    is_valid, error_message = validate_model_predictions(predictions, "xgboost_v1")
    
    assert is_valid is True
    assert error_message is None


def test_validate_model_predictions_missing_field():
    """Test validation with missing required field."""
    predictions = [
        {
            "match_id": "match1",
            "team1": "Team A",
            # Missing team2
            "team1_win_prob": 0.65,
            "team2_win_prob": 0.35,
            "model_version": "xgboost_v1",
        },
    ]
    
    is_valid, error_message = validate_model_predictions(predictions, "xgboost_v1")
    
    assert is_valid is False
    assert "missing required field" in error_message.lower()


def test_validate_model_predictions_invalid_probability():
    """Test validation with invalid probability values."""
    predictions = [
        {
            "match_id": "match1",
            "team1": "Team A",
            "team2": "Team B",
            "team1_win_prob": 1.5,  # Invalid > 1.0
            "team2_win_prob": 0.35,
            "model_version": "xgboost_v1",
        },
    ]
    
    is_valid, error_message = validate_model_predictions(predictions, "xgboost_v1")
    
    assert is_valid is False
    assert "probability" in error_message.lower()


def test_validate_model_predictions_not_sum_to_one():
    """Test validation with probabilities not summing to 1.0."""
    predictions = [
        {
            "match_id": "match1",
            "team1": "Team A",
            "team2": "Team B",
            "team1_win_prob": 0.65,
            "team2_win_prob": 0.40,  # Sum > 1.0
            "model_version": "xgboost_v1",
        },
    ]
    
    is_valid, error_message = validate_model_predictions(predictions, "xgboost_v1")
    
    assert is_valid is False
    assert "sum to 1.0" in error_message.lower()


def test_validate_model_predictions_version_mismatch():
    """Test validation with mismatched model versions."""
    predictions = [
        {
            "match_id": "match1",
            "team1": "Team A",
            "team2": "Team B",
            "team1_win_prob": 0.65,
            "team2_win_prob": 0.35,
            "model_version": "xgboost_v1",
        },
        {
            "match_id": "match2",
            "team1": "Team C",
            "team2": "Team D",
            "team1_win_prob": 0.55,
            "team2_win_prob": 0.45,
            "model_version": "lightgbm_v1",  # Different version
        },
    ]
    
    is_valid, error_message = validate_model_predictions(predictions, "xgboost_v1")
    
    assert is_valid is False
    assert "model version" in error_message.lower()


def test_validate_model_predictions_empty():
    """Test validation with empty predictions list."""
    is_valid, error_message = validate_model_predictions([], "xgboost_v1")
    
    assert is_valid is False
    assert "no predictions" in error_message.lower()
