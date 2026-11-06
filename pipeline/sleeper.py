"""Sleeper's free API (non-commercial use; approved Nov 4, 2026).

Documented: players (team, position, injury), the current week, trending players.
Undocumented, approved by the user: season and weekly stats for the NFL and NBA.
Sleeper asks that the full player list be fetched at most once a day."""

from functools import lru_cache

from .net import get_json

BASE = "https://api.sleeper.app/v1"


@lru_cache(maxsize=4)
def players(sport: str) -> dict:
    """Every player Sleeper knows for 'nfl' or 'nba', keyed by Sleeper player ID."""
    return get_json(f"{BASE}/players/{sport}", f"sleeper/players_{sport}", max_age_hours=24)


def state(sport: str) -> dict:
    """The current season and week, e.g. {'season': '2026', 'week': 9, ...}."""
    return get_json(f"{BASE}/state/{sport}", f"sleeper/state_{sport}", max_age_hours=1)


def season_stats(sport: str, season: int, season_type: str = "regular") -> dict:
    """Season totals for every player, keyed by Sleeper player ID.
    season_type is 'regular' or 'post'. For the NBA, 2025 means the 2025-26 season."""
    current = int(state(sport)["season"])
    max_age = 3 if season >= current else 24 * 30   # this season changes; old ones don't
    return get_json(f"{BASE}/stats/{sport}/{season_type}/{season}",
                    f"sleeper/stats_{sport}_{season_type}_{season}", max_age_hours=max_age)


def trending(sport: str, kind: str = "add", limit: int = 10) -> list:
    """Most added (or dropped) players across Sleeper leagues in the last day. Credit Sleeper."""
    return get_json(f"{BASE}/players/{sport}/trending/{kind}?lookback_hours=24&limit={limit}",
                    f"sleeper/trending_{sport}_{kind}", max_age_hours=1)


def week_stats(sport: str, season: int, week: int, season_type: str = "regular") -> dict:
    """One week's stats for every player, keyed by Sleeper player ID. NFL team
    defenses are keyed by team code ("NE") and carry pts_allow: the other team's score."""
    return get_json(f"{BASE}/stats/{sport}/{season_type}/{season}/{week}",
                    f"sleeper/stats_{sport}_{season_type}_{season}_w{week}", max_age_hours=3)


def nfl_schedule(season: int, season_type: str = "regular") -> list:
    """Every NFL game of a season: date, week, home, away, status (undocumented; approved Nov 4, 2026)."""
    return get_json(f"https://api.sleeper.app/schedule/nfl/{season_type}/{season}",
                    f"sleeper/schedule_nfl_{season_type}_{season}", max_age_hours=6)
