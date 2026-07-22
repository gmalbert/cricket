"""Competition configuration for reusable historical-data pipelines."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Competition:
    slug: str
    display_name: str
    cricsheet_url: str
    format: str
    max_overs: int
    team_aliases: dict[str, str] = field(default_factory=dict)


COMPETITIONS = {
    "ipl_male": Competition(
        slug="ipl_male",
        display_name="Indian Premier League",
        cricsheet_url="https://cricsheet.org/downloads/ipl_male_csv2.zip",
        format="T20",
        max_overs=20,
    ),
}


def get_competition(slug: str = "ipl_male") -> Competition:
    """Return a configured competition or fail with an actionable message."""
    try:
        return COMPETITIONS[slug]
    except KeyError as exc:
        raise ValueError(f"Unknown competition '{slug}'. Known: {', '.join(COMPETITIONS)}") from exc
