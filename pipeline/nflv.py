"""nflverse (via nflreadpy): NFL play-by-play, player stats, schedules, rosters,
and Next Gen Stats. Open data (CC BY). Credit: "Data via nflverse"."""

from functools import lru_cache

import nflreadpy as nfl
import polars as pl
from nflreadpy import config

from .net import CACHE

config.update_config(cache_mode="filesystem", cache_dir=CACHE / "nflverse")


@lru_cache(maxsize=4)
def player_stats(seasons: tuple) -> pl.DataFrame:
    """One row per player per game (weekly), for the given seasons."""
    return nfl.load_player_stats(seasons=list(seasons))


@lru_cache(maxsize=8)
def pbp(season: int) -> pl.DataFrame:
    """Every play of one season."""
    return nfl.load_pbp(seasons=[season])


@lru_cache(maxsize=2)
def schedules() -> pl.DataFrame:
    """Every game since 1999, with scores and starting quarterbacks."""
    return nfl.load_schedules()


@lru_cache(maxsize=4)
def nextgen(stat_type: str) -> pl.DataFrame:
    """NFL Next Gen Stats ('passing', 'rushing', 'receiving'); week 0 is the full season."""
    return nfl.load_nextgen_stats(seasons=True, stat_type=stat_type)


@lru_cache(maxsize=2)
def rosters_weekly(season: int) -> pl.DataFrame:
    return nfl.load_rosters_weekly(seasons=[season])


def latest_week(season: int) -> int:
    """The last regular-season week nflverse has stats for."""
    df = player_stats((season,)).filter(pl.col("season_type") == "REG")
    return int(df["week"].max()) if df.height else 0


@lru_cache(maxsize=1)
def player_stats_by_season() -> pl.DataFrame:
    """Season totals for every player since 1999: one row per player, season, and
    season type (REG or POST), with a games column."""
    reg = nfl.load_player_stats(seasons=True, summary_level="reg")
    # this season's playoffs haven't happened yet, so only load finished seasons
    last_finished = int(reg["season"].max()) - 1
    post = nfl.load_player_stats(seasons=list(range(1999, last_finished + 1)), summary_level="post")
    return pl.concat([reg, post], how="diagonal_relaxed")


@lru_cache(maxsize=1)
def sleeper_to_gsis() -> dict:
    """nflverse's ID crosswalk: Sleeper player ID -> nflverse (gsis) ID. A backup for
    players whose Sleeper record is missing the nflverse ID."""
    x = nfl.load_ff_playerids().filter(pl.col("sleeper_id").is_not_null() & pl.col("gsis_id").is_not_null())
    return {str(int(s)): g for s, g in zip(x["sleeper_id"].to_list(), x["gsis_id"].to_list())}
