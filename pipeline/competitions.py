"""Configuration-driven competition registry.

The registry is deliberately data-only: fetchers consume these records rather
than embedding competition names or Odds API keys in their logic.
"""
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
    aliases: tuple[str, ...] = ()
    gender: str = "male"
    odds_api_key: str = ""
    historical_dataset: str = ""
    season_window: str = ""
    schedule_formats: tuple[str, ...] = ()
    capabilities: frozenset[str] = frozenset({"h2h"})
    enabled: bool = True

    @property
    def slug_aliases(self) -> tuple[str, ...]:
        return (self.slug, self.display_name, *self.aliases)


COMPETITIONS = {
    "ipl_male": Competition(
        slug="ipl_male",
        display_name="Indian Premier League",
        cricsheet_url="https://cricsheet.org/downloads/ipl_male_csv2.zip",
        format="T20",
        max_overs=20,
        odds_api_key="cricket_ipl",
        historical_dataset="ipl_male",
        season_window="2008-present",
        schedule_formats=("T20",),
        capabilities=frozenset({"h2h", "standings", "playoffs", "research"}),
    ),
    "international_t20": Competition("international_t20", "International T20", "https://cricsheet.org/downloads/t20s_csv2.zip", "T20", 20, aliases=("T20I", "T20 internationals"), odds_api_key="cricket_international_t20", historical_dataset="t20_internationals", season_window="2005-present", schedule_formats=("T20",)),
    "odi_internationals": Competition("odi_internationals", "ODI internationals", "https://cricsheet.org/downloads/odis_csv2.zip", "ODI", 50, aliases=("ODI", "one-day internationals"), odds_api_key="cricket_odi", historical_dataset="odis", season_window="2005-present", schedule_formats=("ODI",)),
    "big_bash": Competition("big_bash", "Big Bash League", "https://cricsheet.org/downloads/bbl_csv2.zip", "T20", 20, aliases=("BBL",), odds_api_key="cricket_big_bash", historical_dataset="big_bash", season_window="2011-present", schedule_formats=("T20",)),
    "the_hundred": Competition("the_hundred", "The Hundred", "", "T20", 20, aliases=("Hundred",), odds_api_key="cricket_the_hundred", historical_dataset="the_hundred", season_window="2021-present", schedule_formats=("T20",), enabled=False),
    "t20_blast": Competition("t20_blast", "T20 Blast", "", "T20", 20, aliases=("Vitality Blast",), odds_api_key="cricket_t20_blast", historical_dataset="t20_blast", season_window="2003-present", schedule_formats=("T20",), enabled=False),
    "psl": Competition("psl", "Pakistan Super League", "https://cricsheet.org/downloads/psl_csv2.zip", "T20", 20, aliases=("PSL",), odds_api_key="cricket_psl", historical_dataset="psl", season_window="2016-present", schedule_formats=("T20",)),
    "cpl": Competition("cpl", "Caribbean Premier League", "https://cricsheet.org/downloads/cpl_csv2.zip", "T20", 20, aliases=("CPL",), odds_api_key="cricket_caribbean_premier_league", historical_dataset="cpl", season_window="2013-present", schedule_formats=("T20",)),
    "sa20": Competition("sa20", "SA20", "", "T20", 20, aliases=("SA 20",), historical_dataset="sa20", season_window="2023-present", schedule_formats=("T20",), enabled=False),
    "t20_world_cup": Competition("t20_world_cup", "ICC T20 World Cup", "https://cricsheet.org/downloads/it20s_csv2.zip", "T20", 20, aliases=("T20 World Cup", "World Twenty20"), odds_api_key="cricket_t20_world_cup", historical_dataset="t20_world_cup", season_window="2007-present", schedule_formats=("T20",)),
    "odi_world_cup": Competition("odi_world_cup", "ICC World Cup", "https://cricsheet.org/downloads/odis_csv2.zip", "ODI", 50, aliases=("ODI World Cup", "World Cup"), odds_api_key="cricket_icc_world_cup", historical_dataset="odi_world_cup", season_window="1975-present", schedule_formats=("ODI",)),
    "mlc": Competition("mlc", "Major League Cricket", "https://cricsheet.org/downloads/mlc_csv2.zip", "T20", 20, aliases=("MLC",), historical_dataset="mlc", season_window="2023-present", schedule_formats=("T20",)),
    "lanka_premier_league": Competition("lanka_premier_league", "Lanka Premier League", "https://cricsheet.org/downloads/lpl_csv2.zip", "T20", 20, aliases=("LPL",), historical_dataset="lanka_premier_league", season_window="2020-present", schedule_formats=("T20",)),
    "test_matches": Competition("test_matches", "Test matches", "https://cricsheet.org/downloads/tests_csv2.zip", "Test", 0, aliases=("Tests",), odds_api_key="cricket_test_match", historical_dataset="tests", season_window="2005-present", schedule_formats=("Test",), capabilities=frozenset({"h2h", "research"})),
    "womens_bbl": Competition("womens_bbl", "Women’s Big Bash", "https://cricsheet.org/downloads/wbbl_csv2.zip", "T20", 20, aliases=("WBBL", "Women's Big Bash"), gender="female", historical_dataset="womens_bbl", season_window="2015-present", schedule_formats=("T20",)),
    "womens_international_t20": Competition("womens_international_t20", "Women’s International T20", "https://cricsheet.org/downloads/wt20s_csv2.zip", "T20", 20, aliases=("WT20I", "Women's T20 internationals"), gender="female", historical_dataset="womens_t20_internationals", season_window="2004-present", schedule_formats=("T20",)),
}


def get_competition(slug: str = "ipl_male") -> Competition:
    """Return a configured competition or fail with an actionable message."""
    try:
        return COMPETITIONS[slug]
    except KeyError as exc:
        raise ValueError(f"Unknown competition '{slug}'. Known: {', '.join(COMPETITIONS)}") from exc


def enabled_competitions() -> list[Competition]:
    return [competition for competition in COMPETITIONS.values() if competition.enabled]


def find_competition(value: object) -> Competition | None:
    needle = str(value or "").strip().casefold()
    for competition in COMPETITIONS.values():
        aliases = {str(alias).casefold() for alias in competition.slug_aliases}
        if needle in aliases or any(alias in needle or needle in alias for alias in aliases if len(alias) >= 4):
            return competition
    return None
