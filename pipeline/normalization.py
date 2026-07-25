"""Canonical identifiers used when joining historical and live cricket data."""

from __future__ import annotations

import re
import unicodedata

TEAM_ALIASES = {
    "Delhi Daredevils": "Delhi Capitals",
    "Kings XI Punjab": "Punjab Kings",
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "England Women": "England Women",
}

# This intentionally starts small. Add aliases only after verifying both names
# identify the same player in the source data; ambiguous surnames must not match.
PLAYER_ALIASES: dict[str, str] = {
    "V Kohli": "V Kohli",
    "RG Sharma": "RG Sharma",
    "JJ Bumrah": "JJ Bumrah",
}


def canonical_text(value: object) -> str:
    """Return a stable display-safe spelling without changing player identity."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip()


def canonical_team(team: object) -> str:
    name = canonical_text(team)
    return TEAM_ALIASES.get(name, name)


def team_match_key(team1: object, team2: object) -> tuple[str, str]:
    """Canonical, order-preserving key used to join fixture and odds records."""
    return canonical_team(team1), canonical_team(team2)


def unordered_team_match_key(team1: object, team2: object) -> frozenset[str]:
    return frozenset(team_match_key(team1, team2))


def canonical_player(player: object) -> str:
    name = canonical_text(player)
    return PLAYER_ALIASES.get(name, name)


def audit_player_names(rosters: dict[str, dict[str, list[str]]], historical_names: set[str]) -> dict[str, list[str]]:
    """Report configured squad names that cannot yet join to historical data."""
    canonical_historical = {canonical_player(name) for name in historical_names}
    unmatched: dict[str, list[str]] = {}
    for team, squad in rosters.items():
        players = squad.get("batters", []) + squad.get("bowlers", [])
        missing = sorted({player for player in players if canonical_player(player) not in canonical_historical})
        if missing:
            unmatched[team] = missing
    return unmatched
