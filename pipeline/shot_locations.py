"""Provider-neutral contract for a future licensed cricket shot-location feed.

Cricsheet's current IPL CSV workflow does not include verified x/y shot
coordinates. This module deliberately contains no scraper or unsupported source
adapter. It lets the UI render cached, licensed locations if one is approved.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True)
class ShotLocation:
    match_id: str
    innings: int
    batter: str
    bowler: str
    over: int
    runs_off_bat: int
    x: float
    y: float
    source: str


class ShotLocationProvider(Protocol):
    def fetch(self, match_id: str) -> list[ShotLocation]: ...


def empty_shot_locations(reason: str = "No licensed shot-location provider configured.") -> dict:
    return {"schema_version": 1, "locations": [], "status": "unavailable", "reason": reason}


def serialize_locations(locations: list[ShotLocation]) -> dict:
    """Serialize validated provider output for cache storage."""
    return {"schema_version": 1, "locations": [asdict(location) for location in locations], "status": "available"}
