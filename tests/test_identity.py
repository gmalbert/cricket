"""Tests for identity resolution and confidence scoring."""

from pipeline.identity import (
    calculate_identity_coverage,
    match_player_name,
    match_team_name,
)


def test_match_team_name_exact():
    """Test exact team name match."""
    result = match_team_name("Mumbai Indians", ["Mumbai Indians", "Chennai Super Kings"])

    assert result is not None
    assert result.source == "Mumbai Indians"
    assert result.target == "Mumbai Indians"
    assert result.confidence == 1.0
    assert result.method == "exact"


def test_match_team_name_alias():
    """Test team name match via alias."""
    # Kings XI Punjab -> Punjab Kings is the canonical alias in TEAM_ALIASES
    result = match_team_name("Kings XI Punjab", ["Punjab Kings", "Chennai Super Kings"])

    assert result is not None
    assert result.target == "Punjab Kings"
    assert result.confidence == 1.0
    assert result.method == "exact"


def test_match_team_name_substring():
    """Test team name match via partial/substring containment."""
    # 'mumbai' is contained in 'mumbai indians' → partial match with 0.80
    result = match_team_name("Mumbai", ["Mumbai Indians", "Chennai Super Kings"])

    assert result is not None
    assert result.target == "Mumbai Indians"
    assert result.confidence == 0.80
    assert result.method == "partial"


def test_match_team_name_partial():
    """Test team name match via partial overlap."""
    # 'Bengaluru' is contained in 'Royal Challengers Bengaluru'
    result = match_team_name("Bengaluru", ["Royal Challengers Bengaluru", "Chennai Super Kings"])

    assert result is not None
    assert result.target == "Royal Challengers Bengaluru"
    assert result.confidence == 0.80
    assert result.method == "partial"


def test_match_team_name_no_match():
    """Test team name with no match."""
    result = match_team_name("Kolkata Knight Riders", ["Mumbai Indians", "Chennai Super Kings"])

    assert result is None


def test_match_player_name_exact():
    """Test exact player name match."""
    result = match_player_name("Virat Kohli", ["Virat Kohli", "MS Dhoni"])

    assert result is not None
    assert result.source == "Virat Kohli"
    assert result.target == "Virat Kohli"
    assert result.confidence == 1.0
    assert result.method == "exact"


def test_match_player_name_surname_initials():
    """Test player name match via surname + initials."""
    result = match_player_name("V Kohli", ["Virat Kohli", "MS Dhoni"])

    assert result is not None
    assert result.target == "Virat Kohli"
    assert result.confidence == 0.90
    assert result.method == "surname+initials"


def test_match_player_name_fuzzy():
    """Test player name match via surname matching."""
    result = match_player_name("Kohli", ["Virat Kohli", "MS Dhoni"])

    assert result is not None
    assert result.target == "Virat Kohli"
    assert result.confidence >= 0.80
    assert result.method == "surname+initials"


def test_calculate_identity_coverage():
    """Test identity coverage calculation."""
    source_items = ["Mumbai Indians", "Chennai Super Kings", "Royal Challengers Bangalore", "Unknown Team"]
    target_items = ["Mumbai Indians", "Chennai Super Kings", "Royal Challengers Bengaluru"]

    matches = []
    for source in source_items:
        match = match_team_name(source, target_items)
        matches.append(match)

    coverage = calculate_identity_coverage(matches)

    assert coverage["total"] == 4
    assert coverage["matched"] == 3
    assert coverage["unmatched"] == 1
    assert coverage["rate"] == 0.75
    assert coverage["high_confidence"] >= 2  # Exact and alias matches


def test_calculate_identity_coverage_empty():
    """Test identity coverage with no matches."""
    coverage = calculate_identity_coverage([])

    assert coverage["total"] == 0
    assert coverage["matched"] == 0
    assert coverage["unmatched"] == 0
    assert coverage["rate"] == 0.0
