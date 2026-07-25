"""Tests for cache system with metadata support."""

import tempfile
from pathlib import Path

import pytest

from utils.cache import (
    get_cache_metadata,
    is_cache_stale,
    is_mock_data,
    load_cache,
    load_cache_data_only,
    save_cache,
    save_cache_with_metadata,
)


@pytest.fixture
def temp_cache_dir(monkeypatch):
    """Create a temporary cache directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir) / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Monkeypatch the CACHE_DIR in utils.cache
        monkeypatch.setattr("utils.cache.CACHE_DIR", cache_dir)

        yield cache_dir


def test_save_and_load_cache(temp_cache_dir):
    """Test basic cache save and load."""
    test_data = {"key": "value", "number": 123}

    save_cache("test_key", test_data)
    loaded = load_cache("test_key")

    assert loaded == test_data


def test_save_cache_with_metadata(temp_cache_dir):
    """Test cache save with metadata wrapper."""
    test_data = [{"match": "Team1 vs Team2"}]

    save_cache_with_metadata(
        "test_matches",
        test_data,
        source_run_id="run-123",
        source_status="ready",
        is_mock=False,
    )

    loaded = load_cache("test_matches")

    assert "data" in loaded
    assert loaded["data"] == test_data
    assert loaded["source_run_id"] == "run-123"
    assert loaded["source_status"] == "ready"
    assert loaded["is_mock"] is False


def test_get_cache_metadata(temp_cache_dir):
    """Test extracting metadata from cache."""
    test_data = {"result": "success"}

    save_cache_with_metadata(
        "test_data",
        test_data,
        source_run_id="run-456",
        is_mock=True,
    )

    metadata = get_cache_metadata("test_data")

    assert metadata is not None
    assert metadata["source_run_id"] == "run-456"
    assert metadata["is_mock"] is True
    assert "generated_at" in metadata


def test_load_cache_data_only(temp_cache_dir):
    """Test loading only the data portion, unwrapping metadata."""
    test_data = {"teams": ["A", "B"]}

    save_cache_with_metadata("test_teams", test_data, is_mock=False)

    data_only = load_cache_data_only("test_teams")

    assert data_only == test_data


def test_load_cache_data_only_no_wrapper(temp_cache_dir):
    """Test load_cache_data_only with non-wrapped data."""
    test_data = {"legacy": "data"}

    save_cache("test_legacy", test_data)

    data_only = load_cache_data_only("test_legacy")

    assert data_only == test_data


def test_is_cache_stale_fresh(temp_cache_dir):
    """Test is_cache_stale with fresh data."""
    test_data = {"value": 42}

    save_cache_with_metadata("fresh_data", test_data)

    assert is_cache_stale("fresh_data", max_age_hours=24) is False


def test_is_cache_stale_missing(temp_cache_dir):
    """Test is_cache_stale with missing cache."""
    assert is_cache_stale("nonexistent", max_age_hours=24) is True


def test_is_mock_data_true(temp_cache_dir):
    """Test is_mock_data with mock data."""
    save_cache_with_metadata("mock_data", {"test": 1}, is_mock=True)

    assert is_mock_data("mock_data") is True


def test_is_mock_data_false(temp_cache_dir):
    """Test is_mock_data with real data."""
    save_cache_with_metadata("real_data", {"test": 1}, is_mock=False)

    assert is_mock_data("real_data") is False


def test_is_mock_data_no_metadata(temp_cache_dir):
    """Test is_mock_data with no metadata."""
    save_cache("no_metadata", {"test": 1})

    assert is_mock_data("no_metadata") is False
