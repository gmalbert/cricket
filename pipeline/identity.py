"""Identity resolution with confidence scoring for teams and players.

This module provides functions to match team and player names across different
data sources (fixtures, odds, historical data) with confidence scoring.
"""

from __future__ import annotations

import logging
from typing import Any

from pipeline.normalization import canonical_player, canonical_team, canonical_text

logger = logging.getLogger(__name__)


class IdentityMatch:
    """Represents a match between two names with confidence score."""

    def __init__(self, source: str, target: str, confidence: float, method: str):
        self.source = source
        self.target = target
        self.confidence = confidence
        self.method = method

    def __repr__(self) -> str:
        return f"IdentityMatch('{self.source}' -> '{self.target}', {self.confidence:.2f}, {self.method})"


def match_team_name(
    source_name: str,
    known_teams: list[str],
    aliases: dict[str, str] | None = None,
) -> IdentityMatch | None:
    """Match a team name to known teams with confidence scoring.

    Args:
        source_name: Team name to match
        known_teams: List of known canonical team names
        aliases: Optional dict of alias -> canonical mappings

    Returns:
        IdentityMatch if a match is found, None otherwise
    """
    if not source_name:
        return None

    canonical_source = canonical_team(source_name)

    # Exact match after canonicalization
    if canonical_source in known_teams:
        return IdentityMatch(source_name, canonical_source, 1.0, "exact")

    # Alias match
    if aliases:
        for alias, canonical in aliases.items():
            if canonical_text(alias) == canonical_text(source_name):
                if canonical in known_teams:
                    return IdentityMatch(source_name, canonical, 0.95, "alias")

    # Fuzzy match - check for substring containment
    canonical_source_lower = canonical_source.lower()
    for known_team in known_teams:
        known_lower = known_team.lower()

        # Source contains known team name
        if known_lower in canonical_source_lower and len(known_lower) >= 4:
            return IdentityMatch(source_name, known_team, 0.85, "substring")

        # Known team name contains source
        if canonical_source_lower in known_lower and len(canonical_source_lower) >= 4:
            return IdentityMatch(source_name, known_team, 0.80, "partial")

    # No match found
    return None


def match_player_name(
    source_name: str,
    known_players: list[str],
    aliases: dict[str, str] | None = None,
) -> IdentityMatch | None:
    """Match a player name to known players with confidence scoring.

    Args:
        source_name: Player name to match
        known_players: List of known canonical player names
        aliases: Optional dict of alias -> canonical mappings

    Returns:
        IdentityMatch if a match is found, None otherwise
    """
    if not source_name:
        return None

    canonical_source = canonical_player(source_name)

    # Exact match
    if canonical_source in known_players:
        return IdentityMatch(source_name, canonical_source, 1.0, "exact")

    # Alias match
    if aliases:
        for alias, canonical in aliases.items():
            if canonical_text(alias) == canonical_text(source_name):
                if canonical in known_players:
                    return IdentityMatch(source_name, canonical, 0.95, "alias")

    # Surname match (for cricket format like "JJ Bumrah" matching "Bumrah")
    source_parts = canonical_source.split()
    if source_parts:
        last_name = source_parts[-1]
        for known_player in known_players:
            known_parts = known_player.split()
            if known_parts and known_parts[-1] == last_name:
                # Initials + surname match has high confidence
                return IdentityMatch(source_name, known_player, 0.90, "surname+initials")

    # No match found
    return None


def calculate_identity_coverage(
    matches: list[IdentityMatch | None],
    min_confidence: float = 0.80,
) -> dict[str, Any]:
    """Calculate identity coverage metrics from a list of matches.

    Args:
        matches: List of IdentityMatch objects (can include None)
        min_confidence: Minimum confidence threshold for "matched"

    Returns:
        Dict with coverage metrics
    """
    total = len(matches)
    if total == 0:
        return {
            "total": 0,
            "matched": 0,
            "unmatched": 0,
            "rate": 0.0,
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0,
        }

    matched = [m for m in matches if m is not None and m.confidence >= min_confidence]
    high_conf = [m for m in matched if m.confidence >= 0.95]
    medium_conf = [m for m in matched if 0.85 <= m.confidence < 0.95]
    low_conf = [m for m in matched if min_confidence <= m.confidence < 0.85]

    return {
        "total": total,
        "matched": len(matched),
        "unmatched": total - len(matched),
        "rate": len(matched) / total if total > 0 else 0.0,
        "high_confidence": len(high_conf),
        "medium_confidence": len(medium_conf),
        "low_confidence": len(low_conf),
    }


def build_team_aliases_from_competition(competition) -> dict[str, str]:
    """Build team aliases from competition configuration.

    Args:
        competition: Competition object with team_aliases field

    Returns:
        Dict of alias -> canonical name
    """
    return dict(competition.team_aliases) if hasattr(competition, "team_aliases") else {}


def match_fixture_to_odds(
    fixture: dict[str, Any],
    odds: list[dict[str, Any]],
    min_confidence: float = 0.85,
) -> dict[str, Any] | None:
    """Match a fixture to an odds record with confidence tracking.

    Args:
        fixture: Fixture dict with team1, team2
        odds: List of odds dicts
        min_confidence: Minimum confidence for accepting a match

    Returns:
        Matched odds dict with added confidence info, or None
    """
    fixture_team1 = fixture.get("team1", "")
    fixture_team2 = fixture.get("team2", "")

    if not fixture_team1 or not fixture_team2:
        return None

    best_match = None
    best_confidence = 0.0

    for odds_record in odds:
        odds_team1 = odds_record.get("team1", "")
        odds_team2 = odds_record.get("team2", "")

        # Try both team orderings
        for ft1, ft2, ot1, ot2 in [
            (fixture_team1, fixture_team2, odds_team1, odds_team2),
            (fixture_team1, fixture_team2, odds_team2, odds_team1),
        ]:
            # Exact canonical match
            if canonical_team(ft1) == canonical_team(ot1) and canonical_team(ft2) == canonical_team(ot2):
                confidence = 1.0
                if confidence > best_confidence:
                    best_match = {**odds_record, "match_confidence": confidence}
                    best_confidence = confidence
            # Substring match
            elif (
                canonical_team(ft1).lower() in canonical_team(ot1).lower()
                and canonical_team(ft2).lower() in canonical_team(ot2).lower()
            ):
                confidence = 0.85
                if confidence > best_confidence:
                    best_match = {**odds_record, "match_confidence": confidence}
                    best_confidence = confidence

    if best_match and best_confidence >= min_confidence:
        return best_match

    return None
