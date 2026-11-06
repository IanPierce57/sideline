"""The stat catalog: every stat the show can cite, where it comes from, and how
it's checked. This is the only place numbers enter the show.

Each function returns candidate facts: a value fetched by code (never typed by
an AI) plus everything needed to check it later. verify.py does the checking.

Sources and checks (decided Nov 4, 2026; see SOURCES.md):
  NFL basic stats     nflverse, checked against Sleeper (Sleeper wins a disagreement)
  NFL advanced stats  calculated from nflverse, checked against muffed.ai (exact match or dropped)
  NFL team records    nflverse game results, checked against muffed.ai
  NBA stats           Sleeper (trusted on its own), 2017-18 season onward
  Current team        Sleeper (plus nflverse rosters for the NFL)
"""

import re

import polars as pl

from functools import lru_cache

from . import games as nflgames, nflv, players, positions, sleeper, wiki

# ---------- What can be asked for ----------

# NFL counting stats: name -> (nflverse column, Sleeper key, label, definition)
NFL_COUNTS = {
    "games": ("games", "gp", "games played", "Games he played in."),
    "passing_yards": ("passing_yards", "pass_yd", "passing yards", "Yards gained on completed passes."),
    "passing_tds": ("passing_tds", "pass_td", "passing touchdowns", "Touchdown passes thrown."),
    "interceptions": ("passing_interceptions", "pass_int", "interceptions thrown", "Passes intercepted by the defense."),
    "completions": ("completions", "pass_cmp", "completions", "Passes caught."),
    "pass_attempts": ("attempts", "pass_att", "pass attempts", "Passes thrown."),
    "sacks_taken": ("sacks_suffered", "pass_sack", "times sacked", "Times sacked."),
    "rushing_yards": ("rushing_yards", "rush_yd", "rushing yards", "Yards gained running the ball."),
    "rushing_tds": ("rushing_tds", "rush_td", "rushing touchdowns", "Touchdowns scored running the ball."),
    "carries": ("carries", "rush_att", "carries", "Running plays where he carried the ball."),
    "receptions": ("receptions", "rec", "receptions", "Passes he caught."),
    "receiving_yards": ("receiving_yards", "rec_yd", "receiving yards", "Yards gained on catches."),
    "receiving_tds": ("receiving_tds", "rec_td", "receiving touchdowns", "Touchdowns scored on catches."),
    "targets": ("targets", "rec_tgt", "targets", "Passes thrown his way."),
    # Defense. Tested Nov 4, 2026 (2018-2025): these agree 98-100% between the sources.
    "sacks": ("def_sacks", "idp_sack", "sacks", "Times he sacked the quarterback (half sacks count as 0.5)."),
    "def_interceptions": ("def_interceptions", "idp_int", "interceptions", "Passes he intercepted."),
    "passes_defended": ("def_pass_defended", "idp_pass_def", "passes defended", "Passes he broke up or intercepted."),
    "forced_fumbles": ("def_fumbles_forced", "idp_ff", "forced fumbles", "Fumbles he caused."),
    "qb_hits": ("def_qb_hits", "idp_qb_hit", "QB hits", "Times he hit the quarterback as or after he threw."),
    # These agree only 15-77%: the two sources count tackles differently (a scorer's judgment
    # call), so they come from Sleeper alone, which the user trusts (Nov 4, 2026).
    "solo_tackles": (None, "idp_tkl_solo", "solo tackles", "Tackles he made by himself."),
    "total_tackles": (None, "idp_tkl", "total tackles", "Solo tackles plus assisted tackles."),
    "tackles_for_loss": (None, "idp_tkl_loss", "tackles for loss", "Tackles behind the line of scrimmage."),
}
SLEEPER_ONLY = {k for k, v in NFL_COUNTS.items() if v[0] is None}
# Rates built from two verified counts: name -> (top, bottom, multiply, decimals, label, definition)
NFL_RATES = {
    "completion_pct": ("completions", "pass_attempts", 100, 1, "completion percentage", "Share of passes caught, in percent."),
    "yards_per_attempt": ("passing_yards", "pass_attempts", 1, 1, "yards per pass attempt", "Passing yards divided by passes thrown."),
    "yards_per_carry": ("rushing_yards", "carries", 1, 1, "yards per carry", "Rushing yards divided by carries."),
    "yards_per_catch": ("receiving_yards", "receptions", 1, 1, "yards per catch", "Receiving yards divided by catches."),
}
# NFL advanced stats, one regular season at a time (2016 on, so muffed.ai can check them):
# name -> (muffed metric, decimals, label, plain-English definition, how we calculate it)
NFL_ADVANCED = {
    "epa_per_dropback": ("qb_epa.epa_per_dropback", 2, "EPA per dropback",
                         "Expected points added per dropback: how much each pass attempt, sack, or scramble raised or lowered the points his team should expect on that drive.", "pbp"),
    "success_rate": ("qb_epa.success_rate", 1, "dropback success rate",
                     "Share of his dropbacks that raised his team's expected points, in percent.", "pbp"),
    "cpoe_nflfastr": ("qb_cpoe_nflfastr.cpoe_nflfastr", 1, "CPOE (nflverse model)",
                      "Completion percentage over expected, from nflverse's model: how much more often his passes were caught than the difficulty of the throws predicted, in percentage points.", "pbp"),
    "cpoe_ngs": ("qb_cpoe_ngs.cpoe", 1, "CPOE (Next Gen Stats model)",
                 "Completion percentage over expected, from the NFL's Next Gen Stats model, in percentage points.", "ngs_passing"),
    "any_a": ("qb_anya.any_a", 2, "adjusted net yards per attempt (ANY/A)",
              "Passing yards per dropback, with touchdowns worth 20 extra yards, interceptions costing 45, and sack yardage taken off.", "anya"),
    "time_to_throw": ("qb_ngs_passing.avg_time_to_throw", 2, "average time to throw",
                      "Seconds from the snap to the throw, on average (Next Gen Stats).", "ngs_passing"),
    "ryoe_per_carry": ("rb_ryoe.rush_yards_over_expected_per_att", 2, "rush yards over expected per carry",
                       "Rushing yards beyond what the blocking and defenders' positions predicted, per carry (Next Gen Stats).", "ngs_rushing"),
    "avg_separation": ("receiving_ngs.avg_separation", 2, "average separation",
                       "Average distance in yards between him and the nearest defender when the ball arrived (Next Gen Stats).", "ngs_receiving"),
}
# NBA (Sleeper): name -> (Sleeper key, label, definition)
NBA_TOTALS = {
    "games": ("gp", "games played", "Games he played in."),
    "points": ("pts", "points", "Points scored."),
    "rebounds": ("reb", "rebounds", "Rebounds grabbed."),
    "assists": ("ast", "assists", "Assists."),
    "steals": ("stl", "steals", "Steals."),
    "blocks": ("blk", "blocks", "Blocked shots."),
    "turnovers": ("to", "turnovers", "Turnovers."),
    "threes_made": ("tpm", "three-pointers made", "Three-point shots made."),
}
NBA_PER_GAME = {"points_per_game": "points", "rebounds_per_game": "rebounds", "assists_per_game": "assists",
                "steals_per_game": "steals", "blocks_per_game": "blocks", "turnovers_per_game": "turnovers"}
NBA_PCTS = {"fg_pct": ("fgm", "fga", "field goal percentage"), "three_pct": ("tpm", "tpa", "three-point percentage"),
            "ft_pct": ("ftm", "fta", "free throw percentage")}

# NBA rates built from Sleeper's own numbers (added Nov 5, 2026):
# name -> (label, definition, decimals, percent?)
NBA_RATES = {
    "true_shooting_pct": ("true shooting percentage", "Scoring efficiency counting threes and free throws: points / (2 x (shots + 0.44 x free throws)), in percent.", 1, True),
    "effective_fg_pct": ("effective field goal percentage", "Field goal percentage with threes worth 1.5 makes, in percent.", 1, True),
    "assist_to_turnover": ("assist-to-turnover ratio", "Assists for every turnover.", 1, False),
    "minutes_per_game": ("minutes per game", "Minutes played per game, on average.", 1, False),
    "plus_minus_per_game": ("plus-minus per game", "Points his team outscored opponents by while he was on the court, per game.", 1, False),
    "games_started": ("games started", "Games he started.", 0, False),
}
# Which column of the Wikipedia career-stats table each stat is checked against.
NBA_WIKI = {"games": "gp", "games_started": "gs", "minutes_per_game": "mpg", "fg_pct": "fg", "three_pct": "3p", "ft_pct": "ft",
            "rebounds": "rpg", "rebounds_per_game": "rpg", "assists": "apg", "assists_per_game": "apg",
            "steals": "spg", "steals_per_game": "spg", "blocks": "bpg", "blocks_per_game": "bpg",
            "points": "ppg", "points_per_game": "ppg"}

NBA_FIRST_SEASON = 2017          # Sleeper's NBA stats start with 2017-18
SLEEPER_NFL_FIRST_SEASON = 2009  # Sleeper's NFL stats start with 2009
MUFFED_FIRST_SEASON = 2016

# nflverse writes a few team codes differently from Sleeper
NFLVERSE_TEAM = {"LAR": "LA"}


def stat_menu() -> str:
    """The list of stats, for the research agent's instructions."""
    lines = ["NFL player stats (scope: one season, or career; regular season or playoffs):"]
    lines += [f"  {k}: {v[2]}" for k, v in NFL_COUNTS.items()]
    lines += [f"  {k}: {v[4]}" for k, v in NFL_RATES.items()]
    lines.append("NFL advanced stats (one regular season, 2016 or later):")
    lines += [f"  {k}: {v[2]}" for k, v in NFL_ADVANCED.items()]
    lines.append("NFL team stats (one regular season, 2016 or later): team_record, "
                 + ", ".join(f"{k} ({v[3]})" for k, v in NFL_TEAM_STATS.items()))
    lines.append("NBA player stats (one regular season, 2017-18 or later; season 2025 means 2025-26):")
    lines += [f"  {k}: {v[1]}" for k, v in NBA_TOTALS.items()]
    lines += [f"  {k}: {k.replace('_', ' ')}" for k in NBA_PER_GAME]
    lines += [f"  {k}: {v[2]}" for k, v in NBA_PCTS.items()]
    lines += [f"  {k}: {v[0]}" for k, v in NBA_RATES.items()]
    lines.append("  (NBA playoffs: playoffs=true, 2017-18 or later)")
    lines.append("NBA team stats (this season; see get_team_stats): team_record, home_road, scoring, last_five, streak, "
                 "conference_rank, head_coach")
    return "\n".join(lines)


# ---------- Helpers ----------

def half_up(value: float, decimals: int = 1) -> float:
    """Round the way box scores do (33.15 -> 33.2), not the way computers do (33.1)."""
    from decimal import ROUND_HALF_UP, Decimal
    return float(Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))


def say(value, decimals=0, pct=False) -> str:
    """How a number should look (and be said): 5,097 / 64.5% / +0.17."""
    if value is None:
        return ""
    if decimals == 0:
        text = f"{int(round(value)):,}"
    else:
        text = f"{value:,.{decimals}f}"
    return text + ("%" if pct else "")


def _season_label(league: str, season: int) -> str:
    return f"{season}-{str(season + 1)[-2:]}" if league == "NBA" else str(season)


def _as_of(league: str, season: int) -> str:
    sport = league.lower()
    current = int(sleeper.state(sport)["season"])
    if season < current:
        return "final"
    if league == "NFL":
        return f"through Week {nflv.latest_week(season)}"
    return "season in progress"


def _fact(**fields) -> dict:
    base = {"status": "unchecked", "checked_against": None, "check_value": None, "note": ""}
    base.update(fields)
    return base


# ---------- NFL player stats ----------

def _nfl_seasons(card: dict, scope: dict) -> list[int]:
    df = nflv.player_stats_by_season().filter(pl.col("player_id") == card["gsis_id"])
    stype = "POST" if scope.get("playoffs") else "REG"
    df = df.filter(pl.col("season_type") == stype)
    if scope.get("season"):
        return [scope["season"]] if scope["season"] in df["season"].to_list() else []
    return sorted(df["season"].to_list())


def nfl_player(card: dict, stat: str, scope: dict) -> list[dict]:
    """Counts and rates for one NFL player, for one season or the career."""
    if not card.get("gsis_id"):
        return [_fact(subject=card["name"], stat=stat, status="dropped", note="no nflverse ID for this player")]
    if stat in NFL_ADVANCED:
        return [nfl_advanced(card, stat, scope.get("season"))]
    if stat in NFL_RATES:
        top, bottom, mult, dec, label, definition = NFL_RATES[stat]
        parts = [nfl_player(card, top, scope)[0], nfl_player(card, bottom, scope)[0]]
        fact = _fact(league="NFL", subject=card["name"], subject_key=card["key"], stat=stat, label=label,
                     definition=definition, scope=parts[0].get("scope"), sample=parts[0].get("sample"),
                     source="nflverse", as_of=parts[0].get("as_of"), credit="Data via nflverse",
                     depends_on=parts, rate=(mult, dec), pct=mult == 100)
        return [fact]
    if stat not in NFL_COUNTS:
        return [_fact(subject=card["name"], stat=stat, status="dropped", note=f"unknown stat '{stat}'")]

    col, sl_key, label, definition = NFL_COUNTS[stat]
    if stat in SLEEPER_ONLY:
        return [nfl_sleeper_only(card, stat, scope)]
    seasons = _nfl_seasons(card, scope)
    if not seasons:
        return [_fact(subject=card["name"], stat=stat, status="dropped",
                      note=f"he hasn't played a regular-season game in {scope['season']}" if scope.get("season") else "no games found")]
    stype = "POST" if scope.get("playoffs") else "REG"
    df = nflv.player_stats_by_season().filter((pl.col("player_id") == card["gsis_id"]) &
                                              (pl.col("season_type") == stype) & pl.col("season").is_in(seasons))
    value = float(df[col].sum() or 0)
    value = int(value) if value.is_integer() else value     # half sacks stay as .5
    games = int(df["games"].sum() or 0)
    kind = "playoffs" if scope.get("playoffs") else "regular season"
    if scope.get("season"):
        scope_text = f"{scope['season']} {kind}"
    else:
        scope_text = f"career {kind}, {seasons[0]}-{seasons[-1]}"
    return [_fact(league="NFL", subject=card["name"], subject_key=card["key"], stat=stat, label=label,
                  definition=definition, value=value, say=say(value, 0 if isinstance(value, int) else 1), scope=scope_text,
                  sample=f"{games} games", seasons=seasons, season_type=stype, sleeper_key=sl_key,
                  source="nflverse", as_of=_as_of("NFL", seasons[-1]), credit="Data via nflverse")]


def sleeper_season(season: int, kind: str = "regular") -> dict:
    """Sleeper's season totals. For the season in progress, its weekly numbers are added
    up only through the week nflverse has, so the two sources cover the same games (on
    a Sunday night Sleeper already counts that day's games and nflverse doesn't yet)."""
    if kind != "regular" or season != int(sleeper.state("nfl")["season"]):
        return sleeper.season_stats("nfl", season, kind)
    return _sleeper_through(season, nflv.latest_week(season))


@lru_cache(maxsize=4)
def _sleeper_through(season: int, week: int) -> dict:
    totals = {}
    for w in range(1, week + 1):
        for pid, row in sleeper.week_stats("nfl", season, w).items():
            t = totals.setdefault(pid, {})
            for k, v in row.items():
                if isinstance(v, (int, float)):
                    t[k] = t.get(k, 0) + v
    return totals


def nfl_sleeper_only(card: dict, stat: str, scope: dict) -> dict:
    """Tackle stats: Sleeper alone (the sources define tackles differently)."""
    _, sl_key, label, definition = NFL_COUNTS[stat]
    kind = "post" if scope.get("playoffs") else "regular"
    seasons = [scope["season"]] if scope.get("season") else _nfl_seasons(card, scope)
    base = dict(league="NFL", subject=card["name"], subject_key=card["key"], stat=stat, label=label,
                definition=definition, source="Sleeper", credit="Data via Sleeper")
    if not seasons or min(seasons) < SLEEPER_NFL_FIRST_SEASON:
        return _fact(**base, status="dropped", note=f"Sleeper's NFL stats start in {SLEEPER_NFL_FIRST_SEASON}")
    value = games = 0
    for season in seasons:
        row = sleeper_season(season, kind).get(card["sleeper_id"], {})
        value += row.get(sl_key) or 0
        games += row.get("gp") or 0
    scope_text = (f"{seasons[0]} " if scope.get("season") else f"career {seasons[0]}-{seasons[-1]}, ") + \
        ("playoffs" if scope.get("playoffs") else "regular season")
    return _fact(**base, value=value, say=say(value, 1 if value % 1 else 0), scope=scope_text,
                 sample=f"{int(games)} games", as_of=_as_of("NFL", seasons[-1]), status="trusted",
                 checked_against="Sleeper (trusted on its own; nflverse counts tackles differently)")


def nfl_advanced(card: dict, stat: str, season: int | None, through_week: int | None = None) -> dict:
    """One advanced stat for one regular season. through_week: count only weeks up to this
    one, so it can be compared with a source that's a week behind (verify.py)."""
    metric, dec, label, definition, how = NFL_ADVANCED[stat]
    season = season or int(sleeper.state("nfl")["season"])
    week = through_week or nflv.latest_week(season)
    base = dict(league="NFL", subject=card["name"], subject_key=card["key"], stat=stat, label=label,
                definition=definition, scope=f"{season} regular season", season=season, muffed_metric=metric,
                decimals=dec, source="nflverse", gsis_id=card["gsis_id"], week=week,
                as_of=f"through Week {through_week}" if through_week else _as_of("NFL", season),
                credit="Data via nflverse" + (" · NFL Next Gen Stats via nflverse" if how.startswith("ngs") else ""))
    if season < MUFFED_FIRST_SEASON:
        return _fact(**base, status="dropped", note=f"advanced stats can only be checked from {MUFFED_FIRST_SEASON} on")
    value, sample = None, ""
    g = card["gsis_id"]
    if how == "pbp":
        plays = nflv.pbp(season).filter(pl.col("season_type") == "REG")
        if through_week:
            plays = plays.filter(pl.col("week") <= through_week)
        if stat in ("epa_per_dropback", "success_rate"):
            d = plays.filter((pl.col("qb_dropback") == 1) & (pl.col("id") == g))
            if d.height:
                value = d["epa"].mean() if stat == "epa_per_dropback" else (d["epa"] > 0).mean() * 100
                sample = f"{d.height} dropbacks"
        else:
            d = plays.filter((pl.col("passer_player_id") == g) & pl.col("cpoe").is_not_null())
            if d.height:
                value, sample = d["cpoe"].mean(), f"{d.height} pass attempts"
    elif how == "anya":
        if through_week:            # add up the weeks instead of using the season total
            df = nflv.player_stats((season,)).filter((pl.col("player_id") == g) & (pl.col("season_type") == "REG") &
                                                     (pl.col("week") <= through_week))
            df = df.select([pl.col(c).sum() for c in ("attempts", "sacks_suffered", "passing_yards", "passing_tds",
                                                       "passing_interceptions", "sack_yards_lost")])
        else:
            df = nflv.player_stats_by_season().filter((pl.col("player_id") == g) & (pl.col("season") == season) &
                                                      (pl.col("season_type") == "REG"))
        if df.height:
            r = df.row(0, named=True)
            dropbacks = (r["attempts"] or 0) + (r["sacks_suffered"] or 0)
            if dropbacks:
                value = ((r["passing_yards"] or 0) + 20 * (r["passing_tds"] or 0) - 45 * (r["passing_interceptions"] or 0)
                         - abs(r["sack_yards_lost"] or 0)) / dropbacks   # stored as a negative number
                sample = f"{dropbacks} dropbacks"
    elif through_week:
        return _fact(**base, status="dropped", note=f"Next Gen Stats only publish season averages, so this can't be "
                                                    f"compared through Week {through_week} while the sources are a week apart")
    else:
        kind = how.split("_", 1)[1]
        column = {"cpoe_ngs": "completion_percentage_above_expectation", "time_to_throw": "avg_time_to_throw",
                  "ryoe_per_carry": "rush_yards_over_expected_per_att", "avg_separation": "avg_separation"}[stat]
        df = nflv.nextgen(kind).filter((pl.col("player_gsis_id") == g) & (pl.col("season") == season) &
                                      (pl.col("season_type") == "REG") & (pl.col("week") == 0))
        if df.height:
            value = df[column][0]
            count_col = {"passing": "attempts", "rushing": "rush_attempts", "receiving": "targets"}[kind]
            sample = f"{df[count_col][0]} {count_col.replace('_', ' ')}"
    if value is None:
        return _fact(**base, status="dropped", note="no data for that player and season")
    signed = stat in ("epa_per_dropback", "cpoe_nflfastr", "cpoe_ngs", "ryoe_per_carry")
    shown = say(value, dec, pct=stat == "success_rate")
    if signed and value > 0:
        shown = "+" + shown
    return _fact(**base, value=value, say=shown, sample=sample)


def nfl_team_record(team: str, season: int, through_week: int | None = None) -> dict:
    code = NFLVERSE_TEAM.get(team, team)
    games = nflv.schedules().filter((pl.col("season") == season) & (pl.col("game_type") == "REG") &
                                    pl.col("result").is_not_null() &
                                    ((pl.col("home_team") == code) | (pl.col("away_team") == code)))
    if through_week:
        games = games.filter(pl.col("week") <= through_week)
    wins = losses = ties = 0
    for g in games.iter_rows(named=True):
        margin = g["result"] if g["home_team"] == code else -g["result"]   # result = home minus away
        wins += margin > 0
        losses += margin < 0
        ties += margin == 0
    record = f"{wins}-{losses}" + (f"-{ties}" if ties else "")
    name = nflgames.TEAMS.get(team, (team,))[0]
    base = dict(league="NFL", subject=name, subject_key=f"nflteam:{team}", stat="team_record", label="regular-season record",
                definition="Wins and losses in regular-season games.", value={"wins": wins, "losses": losses, "ties": ties},
                say=record, scope=f"{season} regular season", season=season, team_code=code, sample=f"{wins + losses + ties} games",
                source="nflverse", credit="Data via nflverse", week=through_week or nflv.latest_week(season),
                as_of=f"through Week {through_week}" if through_week else _as_of("NFL", season))
    if not games.height:
        return _fact(**base, status="dropped", note="no games found")
    if season < MUFFED_FIRST_SEASON:
        return _fact(**base, status="dropped", note=f"team records can only be checked from {MUFFED_FIRST_SEASON} on")
    return _fact(**base)


# ---------- NFL team stats (nflverse, checked against muffed.ai) ----------

# name -> (muffed metric, decimals shown, percent?, label, definition, higher is better?)
# Definitions matched to muffed.ai's published numbers on Nov 5, 2026 (all 32 teams calculated).
NFL_TEAM_STATS = {
    "points_per_game": ("team_scoring.points_for_per_game", 1, False, "points scored per game",
                        "Points the team scored per regular-season game.", True),
    "points_allowed_per_game": ("team_scoring.points_against_per_game", 1, False, "points allowed per game",
                                "Points opponents scored per regular-season game.", False),
    "offense_epa_per_play": ("team_offense_epa.epa_per_play", 3, False, "offensive EPA per play",
                             "Expected points added per pass or run play on offense: how much each play raised or lowered "
                             "the points the team should expect on that drive. Above zero is better than average.", True),
    "defense_epa_per_play": ("team_defense_epa.epa_allowed_per_play", 3, False, "defensive EPA allowed per play",
                             "Expected points added per opponent pass or run play. For a defense, lower (below zero) is better.", False),
    "takeaways": ("team_takeaways.takeaways", 0, False, "takeaways",
                  "Interceptions plus fumbles recovered from the other team.", True),
    "third_down_pct": ("team_third_down.conversion_rate", 1, True, "third-down conversion rate",
                       "Share of third-down passes and runs that picked up a first down, in percent.", True),
    "red_zone_td_pct": ("team_red_zone.rz_td_rate", 1, True, "red-zone touchdown rate",
                        "Share of drives that reached the other team's 20-yard line and ended in a touchdown, in percent.", True),
}


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


@lru_cache(maxsize=64)
def _team_values(stat: str, season: int, through_week: int | None = None) -> dict:
    """{nflverse team code: (value, sample)} for every team, so ranks can be worked out too."""
    out = {}
    if stat in ("points_per_game", "points_allowed_per_game"):
        sched = nflv.schedules().filter((pl.col("season") == season) & (pl.col("game_type") == "REG") &
                                        pl.col("result").is_not_null())
        if through_week:
            sched = sched.filter(pl.col("week") <= through_week)
        totals = {}
        for g in sched.iter_rows(named=True):
            for team, scored, allowed in ((g["home_team"], g["home_score"], g["away_score"]),
                                          (g["away_team"], g["away_score"], g["home_score"])):
                t = totals.setdefault(team, [0, 0, 0])
                t[0] += scored; t[1] += allowed; t[2] += 1
        for team, (scored, allowed, n) in totals.items():
            out[team] = ((scored if stat == "points_per_game" else allowed) / n, f"{n} games")
        return out
    p = nflv.pbp(season).filter(pl.col("season_type") == "REG")
    if through_week:
        p = p.filter(pl.col("week") <= through_week)
    plays = p.filter(pl.col("play_type").is_in(["pass", "run"]))
    for team in plays["posteam"].drop_nulls().unique().to_list():
        if stat == "offense_epa_per_play":
            d = plays.filter((pl.col("posteam") == team) & pl.col("epa").is_not_null())
            out[team] = (d["epa"].mean(), f"{d.height} plays")
        elif stat == "defense_epa_per_play":
            d = plays.filter((pl.col("defteam") == team) & pl.col("epa").is_not_null())
            out[team] = (d["epa"].mean(), f"{d.height} plays")
        elif stat == "takeaways":
            n = p.filter((pl.col("defteam") == team) & ((pl.col("interception") == 1) | (pl.col("fumble_lost") == 1))).height
            out[team] = (n, f"{through_week or nflv.latest_week(season)} weeks")
        elif stat == "third_down_pct":
            d = plays.filter((pl.col("posteam") == team) & (pl.col("down") == 3))
            out[team] = (100 * d.filter(pl.col("first_down") == 1).height / d.height, f"{d.height} third downs")
        elif stat == "red_zone_td_pct":
            d = p.filter((pl.col("posteam") == team) & pl.col("fixed_drive").is_not_null() & (pl.col("yardline_100") <= 20))
            trips = d.select(["game_id", "fixed_drive", "fixed_drive_result"]).unique()
            tds = trips.filter(pl.col("fixed_drive_result") == "Touchdown").height
            out[team] = (100 * tds / trips.height, f"{trips.height} red-zone trips")
    return out


def nfl_team_stat(team: str, stat: str, season: int, through_week: int | None = None) -> dict:
    """One team stat for one regular season, with its rank among all 32 teams.
    through_week: count only weeks up to this one (to match a source a week behind)."""
    code = NFLVERSE_TEAM.get(team, team)
    metric, dec, pct, label, definition, higher_better = NFL_TEAM_STATS[stat]
    base = dict(league="NFL", subject=nflgames.TEAMS.get(team, (team,))[0], subject_key=f"nflteam:{team}", stat=stat,
                label=label, definition=definition, scope=f"{season} regular season", season=season, team_code=code,
                muffed_metric=metric, decimals=dec, pct=pct, source="nflverse", credit="Data via nflverse")
    if season < MUFFED_FIRST_SEASON:
        return _fact(**base, status="dropped", note=f"team stats can only be checked from {MUFFED_FIRST_SEASON} on")
    allteams = _team_values(stat, season, through_week)
    if code not in allteams:
        return _fact(**base, status="dropped", note="no games found")
    value, sample = allteams[code]
    better = sum(1 for v, _ in allteams.values() if (v > value if higher_better else v < value))
    shown = say(value, dec, pct=pct)
    if "epa" in stat and value > 0:
        shown = "+" + shown
    week = through_week or nflv.latest_week(season)
    return _fact(**base, value=value, say=shown, sample=sample, our_rank=better + 1, teams=len(allteams),
                 as_of=f"through Week {through_week}" if through_week else _as_of("NFL", season), week=week)


# ---------- One game (NFL): see games.py ----------

def _team_games(team: str, season: int) -> pl.DataFrame:
    code = NFLVERSE_TEAM.get(team, team)
    return nflv.schedules().filter((pl.col("season") == season) & (pl.col("game_type") == "REG") &
                                   pl.col("result").is_not_null() &
                                   ((pl.col("home_team") == code) | (pl.col("away_team") == code))).sort("gameday")


def _result_line(team: str, g: dict):
    code = NFLVERSE_TEAM.get(team, team)
    home = g["home_team"] == code
    ours, theirs = (g["home_score"], g["away_score"]) if home else (g["away_score"], g["home_score"])
    opp = nflgames.FROM_NFLVERSE.get(g["away_team" if home else "home_team"], g["away_team" if home else "home_team"])
    wl = "W" if ours > theirs else "L" if ours < theirs else "T"
    text = f"{wl} {ours}-{theirs} {'vs' if home else 'at'} {nflgames.nickname(opp)} (Week {g['week']})"
    return text, {"week": g["week"], "team": team, "opp": opp, "ours": ours, "theirs": theirs}, wl


def recent_results(team: str, season: int, n: int = 3, opponent: str | None = None) -> dict:
    """The team's last n results (or this season's meetings with one opponent), newest first."""
    df = _team_games(team, season)
    if opponent:
        o = NFLVERSE_TEAM.get(opponent, opponent)
        df = df.filter((pl.col("home_team") == o) | (pl.col("away_team") == o))
    rows = list(reversed(df.rows(named=True)))[: (None if opponent else n)]
    lines, checks, wl = [], [], []
    for g in rows:
        text, check, r = _result_line(team, g)
        lines.append(text); checks.append(check); wl.append(r)
    name = nflgames.TEAMS[team][0]
    if opponent:
        stat, label = "head_to_head", f"this season's games against the {nflgames.nickname(opponent)}"
        definition = "Final scores of their regular-season meetings this season."
    else:
        stat, label = "recent_results", f"last {len(rows)} results"
        definition = "Final scores of the team's most recent regular-season games, newest first."
    base = dict(league="NFL", subject=name, subject_key=f"nflteam:{team}", stat=stat, label=label, definition=definition,
                value={"wins": wl.count("W"), "losses": wl.count("L")}, say="; ".join(lines), scope=f"{season} regular season",
                season=season, games=checks, source="nflverse", credit="Data via nflverse", as_of=_as_of("NFL", season),
                sample=f"{len(rows)} games")
    if not rows:
        return _fact(**base, status="dropped", note="no games yet")
    return _fact(**base)


def qb_last_start(team: str, season: int) -> dict:
    """Who started at quarterback in the team's most recent game."""
    df = _team_games(team, season)
    name = nflgames.TEAMS[team][0]
    base = dict(league="NFL", subject=name, subject_key=f"nflteam:{team}", stat="qb_last_start", label="starting QB in the last game",
                definition="The quarterback who started the team's most recent game.", scope=f"{season} regular season",
                season=season, source="nflverse", credit="Data via nflverse", as_of=_as_of("NFL", season))
    if not df.height:
        return _fact(**base, status="dropped", note="no games yet")
    g = df.row(-1, named=True)
    home = g["home_team"] == NFLVERSE_TEAM.get(team, team)
    qb_id, qb_name = (g["home_qb_id"], g["home_qb_name"]) if home else (g["away_qb_id"], g["away_qb_name"])
    return _fact(**base, value=None, say=f"{qb_name} started at quarterback in Week {g['week']}, their most recent game",
                 qb_gsis=qb_id, qb_name=qb_name, week=g["week"])


INJURY_LIST = ("Out", "Doubtful", "Questionable", "IR", "PUP", "Sus")


def injuries(team: str) -> dict:
    """Starters (first on Sleeper's depth chart) with an injury designation today. Sleeper is trusted."""
    hurt = []
    for p in sleeper.players("nfl").values():
        if p.get("team") == team and p.get("depth_chart_order") == 1 and p.get("injury_status") in INJURY_LIST:
            part = f", {p['injury_body_part'].lower()}" if p.get("injury_body_part") else ""
            hurt.append(f"{p['full_name']} ({p.get('position')}{part}): {p['injury_status']}")
    name = nflgames.TEAMS[team][0]
    return _fact(league="NFL", subject=name, subject_key=f"nflteam:{team}", stat="injuries", label="injured starters",
                 definition="Starters (first on the depth chart) with an injury designation today. IR means injured reserve.",
                 value=None, say="; ".join(sorted(hurt)) or "none of their starters are on the injury report; backups aren't covered", scope="today",
                 source="Sleeper", credit="Data via Sleeper", as_of="today", sample=f"{len(hurt)} starters",
                 status="trusted", checked_against="Sleeper (trusted on its own)")


def game_pack(game: dict) -> list[dict]:
    """Everything the show needs for one game, unchecked (verify.py checks each one)."""
    season, home, away = game["season"], game["home"], game["away"]
    from datetime import datetime
    day = datetime.strptime(game["date"], "%Y-%m-%d")
    when = f"{game['weekday']}, {day:%B} {day.day}, {day.year}"
    if game.get("time_et"):
        t = datetime.strptime(game["time_et"], "%H:%M")
        when += f", {t.hour % 12 or 12}:{t:%M} {'a.m.' if t.hour < 12 else 'p.m.'} ET"
    where = "a neutral site" if game["neutral"] else f"the {nflgames.nickname(home)}' home field"
    facts = [_fact(league="NFL", subject=f"{nflgames.TEAMS[away][0]} at {nflgames.TEAMS[home][0]}", subject_key=f"nflgame:{away}@{home}",
                   stat="game", label="the game", value=None,
                   say=f"{nflgames.TEAMS[away][0]} at {nflgames.TEAMS[home][0]}, Week {game['week']}, {when}, at {game['stadium']} ({where})"
                       + (", a division game" if game["div_game"] else ""),
                   definition="Date, place, and home team, confirmed on two schedules (nflverse and Sleeper).",
                   scope=f"{season} Week {game['week']}", source="nflverse and Sleeper schedules", credit="Data via nflverse",
                   as_of="today", status="verified", checked_against="Sleeper schedule")]
    for team in (away, home):
        facts.append(nfl_team_record(team, season))
        facts += [nfl_team_stat(team, stat, season) for stat in NFL_TEAM_STATS]
        facts += [recent_results(team, season), qb_last_start(team, season), injuries(team), head_coach(team)]
    h2h = recent_results(home, season, opponent=away)
    if h2h["status"] != "dropped":
        facts.append(h2h)
    return facts


# ---------- Head coaches, measurables, and the draft (added Nov 5, 2026) ----------

def head_coach(team: str) -> dict:
    """Who coached the team's most recent game (nflverse); checked against Wikipedia's team page."""
    season = int(sleeper.state("nfl")["season"])
    df = _team_games(team, season)
    name = nflgames.TEAMS[team][0]
    base = dict(league="NFL", subject=name, subject_key=f"nflteam:{team}", stat="head_coach", label="head coach",
                definition="The team's head coach, as of its most recent game.", scope="today", source="nflverse",
                credit="Data via nflverse", as_of="today", team_name=name)
    if not df.height:
        return _fact(**base, status="dropped", note="no games yet this season")
    g = df.row(-1, named=True)
    coach = g["home_coach"] if g["home_team"] == NFLVERSE_TEAM.get(team, team) else g["away_coach"]
    return _fact(**base, value=coach, say=coach)


def _feet(inches: float) -> str:
    return f"{int(inches // 12)}-{int(round(inches % 12))}" if inches % 12 < 11.5 else f"{int(inches // 12) + 1}-0"


COMBINE = {  # our name -> (nflverse column, Wikipedia predraft field, label, how to say it)
    "forty": ("forty", "dash", "40-yard dash at the combine", lambda v: f"{v:.2f} seconds"),
    "vertical": ("vertical", "vertical", "vertical jump at the combine", lambda v: f"{v:g} inches"),
    "broad_jump": ("broad_jump", "broad", "broad jump at the combine", lambda v: f"{int(v // 12)} feet {int(v % 12)} inches"),
    "bench": ("bench", "bench", "bench-press reps (225 pounds) at the combine", lambda v: f"{int(v)} reps"),
    "cone": ("cone", "cone drill", "three-cone drill at the combine", lambda v: f"{v:.2f} seconds"),
    "shuttle": ("shuttle", "shuttle", "20-yard shuttle at the combine", lambda v: f"{v:.2f} seconds"),
    "combine_weight": ("wt", "weight", "weight at the combine", lambda v: f"{int(v)} pounds"),
}


def _combine_row(card: dict):
    """His combine row, matched through the draft record's IDs (never by name alone: there are
    two Josh Allens in the 2018-19 combines). Undrafted players: by name, if only one matches."""
    picks = nflv.draft_picks().filter(pl.col("gsis_id") == card.get("gsis_id"))
    comb = nflv.combine()
    if picks.height and picks["pfr_player_id"][0]:
        rows = comb.filter(pl.col("pfr_id") == picks["pfr_player_id"][0])
    else:
        rows = comb.filter(pl.col("player_name") == card["name"])
        rows = rows.filter(pl.col("pos").map_elements(lambda p: positions.can_be(p, card.get("position")),
                                                      return_dtype=pl.Boolean))
    return rows.row(0, named=True) if rows.height == 1 else None


def measurables(card: dict) -> list[dict]:
    """Listed height and weight now (Sleeper), and combine results (nflverse, checked against
    the pre-draft table on his Wikipedia page)."""
    p = sleeper.players("nfl").get(card.get("sleeper_id"), {})
    base = dict(league="NFL", subject=card["name"], subject_key=card["key"], gsis_id=card.get("gsis_id"),
                position=card.get("position"))
    facts = []
    if p.get("height"):
        h = float(p["height"])
        facts.append(_fact(**base, stat="height", label="listed height", value=h, say=_feet(h),
                           definition="His listed height, in feet and inches.", scope="today", source="Sleeper",
                           credit="Data via Sleeper", as_of="today", sample="listed"))
    if p.get("weight"):
        facts.append(_fact(**base, stat="listed_weight", label="listed weight", value=int(p["weight"]),
                           say=f"{int(p['weight'])} pounds", definition="His listed weight today.", scope="today",
                           source="Sleeper", credit="Data via Sleeper", as_of="today", sample="listed",
                           status="trusted", checked_against="Sleeper (trusted on its own)"))
    row = _combine_row(card)
    if not row:
        return facts or [_fact(**base, stat="measurables", status="dropped", note="no combine results found")]
    for key, (col, _, label, fmt) in COMBINE.items():
        v = row.get(col)
        if v is None:
            continue
        facts.append(_fact(**base, stat=f"combine_{key}" if not key.startswith("combine") else key, combine_key=key,
                           label=label, value=float(v), say=fmt(float(v)), scope=f"{row['season']} NFL Scouting Combine",
                           definition=f"His {label}.", source="nflverse", credit="Data via nflverse", as_of="final",
                           sample="one measurement", combine_height=row.get("ht")))
    return facts


PFR_TEAM = {"ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills", "CAR": "Panthers", "CHI": "Bears",
            "CIN": "Bengals", "CLE": "Browns", "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GNB": "Packers",
            "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "KAN": "Chiefs", "LVR": "Raiders", "OAK": "Oakland Raiders",
            "LAC": "Chargers", "SDG": "San Diego Chargers", "LAR": "Rams", "STL": "St. Louis Rams", "MIA": "Dolphins",
            "MIN": "Vikings", "NWE": "Patriots", "NOR": "Saints", "NYG": "Giants", "NYJ": "Jets", "PHI": "Eagles",
            "PIT": "Steelers", "SFO": "49ers", "SEA": "Seahawks", "TAM": "Buccaneers", "TEN": "Titans", "WAS": "Washington"}


def draft(card: dict) -> dict:
    """Where he was drafted (nflverse), checked against his Wikipedia page."""
    base = dict(league="NFL", subject=card["name"], subject_key=card["key"], stat="draft", label="draft position",
                definition="Where he was picked in the NFL Draft.", scope="career", source="nflverse",
                credit="Data via nflverse", as_of="final", gsis_id=card.get("gsis_id"), position=card.get("position"))
    picks = nflv.draft_picks().filter(pl.col("gsis_id") == card.get("gsis_id"))
    if not picks.height:
        return _fact(**base, value=None, say="went undrafted", undrafted=True, sample="undrafted")
    r = picks.row(0, named=True)
    team = PFR_TEAM.get(r["team"], r["team"])
    where = "1st overall pick" if r["pick"] == 1 else f"round {r['round']}, pick {r['pick']} overall"
    return _fact(**base, value={"year": r["season"], "round": r["round"], "pick": r["pick"]},
                 say=f"{where} in the {r['season']} NFL Draft, by the {team}", sample=f"{r['season']} draft",
                 draft_year=r["season"], draft_round=r["round"], draft_pick=r["pick"])


# ---------- NBA player stats (Sleeper, trusted) ----------

def nba_player(card: dict, stat: str, scope: dict) -> list[dict]:
    season = scope.get("season") or int(sleeper.state("nba")["season"])
    label_season = _season_label("NBA", season)
    playoffs = bool(scope.get("playoffs"))
    current = int(sleeper.state("nba")["season"])
    base = dict(league="NBA", subject=card["name"], subject_key=card["key"], stat=stat, season=season,
                playoffs=playoffs, position=card.get("position"),
                scope=f"{label_season} {'playoffs' if playoffs else 'regular season'}", source="Sleeper",
                as_of="final" if playoffs or season < current else "season in progress", credit="Data via Sleeper")
    if playoffs and season >= current:
        return [_fact(**base, status="dropped", note="this season's playoffs haven't happened yet")]
    if season < NBA_FIRST_SEASON:
        return [_fact(**base, status="dropped", note="NBA stats are only available from 2017-18 on")]
    row = sleeper.season_stats("nba", season, "post" if playoffs else "regular").get(card["sleeper_id"])
    if not row or not row.get("gp"):
        return [_fact(**base, status="dropped", note="no games found for that season")]
    gp = int(row["gp"])
    raw = None                                      # the unrounded number, for comparing with Wikipedia
    if stat in NBA_TOTALS:
        key, label, definition = NBA_TOTALS[stat]
        value = int(row.get(key) or 0)
        shown = say(value)
    elif stat in NBA_PER_GAME:
        key, label, definition = NBA_TOTALS[NBA_PER_GAME[stat]]
        raw = (row.get(key) or 0) / gp
        value = half_up(raw, 1)
        label, definition = f"{label} per game", f"{definition[:-1]} per game, on average."
        shown = say(value, 1)
    elif stat in NBA_PCTS:
        made, tried, label = NBA_PCTS[stat]
        if not row.get(tried):
            return [_fact(**base, status="dropped", note="no attempts")]
        raw = 100 * row[made] / row[tried]
        value = half_up(raw, 1)
        definition = f"Share of attempts made, in percent ({int(row[made])} of {int(row[tried])})."
        shown = say(value, 1, pct=True)
    elif stat in NBA_RATES:
        label, definition, dec, pct = NBA_RATES[stat]
        g = lambda k: row.get(k) or 0  # noqa: E731
        minutes = g("min") or g("sp") / 60
        if stat == "true_shooting_pct":
            denom = 2 * (g("fga") + 0.44 * g("fta"))
            value = 100 * g("pts") / denom if denom else None
        elif stat == "effective_fg_pct":
            value = 100 * (g("fgm") + 0.5 * g("tpm")) / g("fga") if g("fga") else None
        elif stat == "assist_to_turnover":
            value = g("ast") / g("to") if g("to") else None
        elif stat == "minutes_per_game":
            value = minutes / gp if minutes else None
        elif stat == "plus_minus_per_game":
            value = g("plus_minus") / gp if "plus_minus" in row else None
        else:
            value = int(g("gs"))
        if value is None:
            return [_fact(**base, status="dropped", note="not enough data for this rate")]
        raw = value
        value = half_up(value, dec) if dec else value
        shown = say(value, dec, pct=pct)
        if stat == "plus_minus_per_game" and value > 0:
            shown = "+" + shown
    else:
        return [_fact(**base, status="dropped", note=f"unknown stat '{stat}'")]
    wiki_col = NBA_WIKI.get(stat)
    per_game = value / gp if stat in NBA_TOTALS and stat != "games" else None
    return [_fact(**base, label=label, definition=definition, value=value, say=shown, sample=f"{gp} games",
                  gp=gp, wiki_col=wiki_col, wiki_value=per_game if per_game is not None else (raw if raw is not None else value))]


# ---------- Current team and status ----------

def current_status(card: dict) -> dict:
    """Which team he's on right now, and whether he's hurt."""
    from . import nba
    teams = nba.TEAMS if card["league"] == "NBA" else nflgames.TEAMS
    team = teams.get(card["team"], (card["team"],))[0] if card["team"] else "no team (free agent or retired)"
    pos = positions.TITLE_WORD.get(positions.label(card.get("position")) or "", "") if card["league"] == "NFL" else \
        {"PG": "point guard", "SG": "shooting guard", "SF": "small forward", "PF": "power forward", "C": "center",
         "G": "guard", "F": "forward"}.get(card.get("position") or "", "")
    raw = sleeper.players(card["league"].lower()).get(card.get("sleeper_id"), {})
    starter = card["league"] == "NFL" and raw.get("depth_chart_order") == 1
    role = ", ".join(x for x in (pos, "starter" if starter else "") if x)
    team = f"{team}{f' ({role})' if role else ''}"
    injury = (f", listed as {card['injury_status']}" if card.get("injury_status")
              else (", no injury designation today" if card["team"] else ""))
    fact = _fact(league=card["league"], subject=card["name"], subject_key=card["key"], stat="current_team",
                 label="current team", value=card["team"], say=f"{team}{injury}",
                 definition="The team he's on right now and his listed position, per the current roster.", scope="today",
                 source="Sleeper", as_of="today", credit="Data via Sleeper", position=card["position"],
                 gsis_id=card.get("gsis_id"))
    return fact


def honors(card: dict) -> list[dict]:
    """Career titles and awards from Wikipedia's infobox; each is checked in verify.py."""
    got = wiki.honors(card["name"], card["league"], card.get("position"))
    base = dict(league=card["league"], subject=card["name"], subject_key=card["key"], source="Wikipedia",
                as_of="today", credit="Honors: Wikipedia (CC BY-SA)", scope="career", qid=got["qid"],
                gsis_id=card.get("gsis_id"))
    if not got["page"]:
        return [_fact(**base, stat="honors", label="career honors", status="dropped", note="no Wikipedia page found")]
    facts = []
    for key, item in got["items"].items():
        # Show the years only when they add up to the count Wikipedia states (a guard
        # against misreading the infobox); otherwise just the count.
        years = f" ({', '.join(item['years'])})" if item["years"] and len(item["years"]) == item["count"] else ""
        shown = f"{item['count']}× {item['label']}" if item["count"] > 1 else item["label"]
        facts.append(_fact(**base, stat=f"honor_{key}", honor=key, label=item["label"], value=item["count"],
                           years=item["years"], say=f"{shown}{years}", wikidata=item["wikidata"], list_page=item["list_page"],
                           definition=f"From his Wikipedia page: {item['line']}", sample=f"{item['count']} time(s)"))
    return facts or [_fact(**base, stat="honors", label="career honors", status="dropped", note="no honors listed")]


def qb_playoff_record(card: dict) -> dict:
    """Playoff wins and losses as the starting quarterback, from official scores."""
    g = card.get("gsis_id")
    games = nflv.schedules().filter((pl.col("game_type") != "REG") & pl.col("result").is_not_null() &
                                    ((pl.col("home_qb_id") == g) | (pl.col("away_qb_id") == g)))
    wins = losses = 0
    seasons = []
    for row in games.iter_rows(named=True):
        margin = row["result"] if row["home_qb_id"] == g else -row["result"]
        wins += margin > 0
        losses += margin < 0
        seasons.append(row["season"])
    base = dict(league="NFL", subject=card["name"], subject_key=card["key"], stat="qb_playoff_record",
                label="playoff record as a starting QB", definition="Playoff wins and losses in games he started at quarterback.",
                value={"wins": wins, "losses": losses}, seasons=sorted(set(seasons)),
                say=f"{wins}-{losses}" + (f" (playoffs after the {', '.join(str(s) for s in sorted(set(seasons)))} season"
                                          f"{'s' if len(set(seasons)) > 1 else ''})" if seasons else ""),
                sample=f"{wins + losses} playoff starts", scope="career playoffs", source="nflverse",
                as_of="final", credit="Data via nflverse", starts=wins + losses)
    if not games.height:
        return _fact(**base, status="dropped", note="no playoff starts")
    return _fact(**base)


def get(card: dict, stat: str, scope: dict) -> list[dict]:
    """Fetch one stat for one player (candidate facts, not yet checked)."""
    if stat == "current_team":
        return [current_status(card)]
    if stat == "honors":
        return honors(card)
    if stat in ("measurables", "draft"):
        if card["league"] == "NBA":
            return nba_measurables(card) if stat == "measurables" else [nba_draft(card)]
        return measurables(card) if stat == "measurables" else [draft(card)]
    if stat == "qb_playoff_record":
        if card["league"] != "NFL":
            return [_fact(subject=card["name"], stat=stat, status="dropped", note="NFL quarterbacks only")]
        return [qb_playoff_record(card)]
    if card["league"] == "NFL":
        return nfl_player(card, stat, scope)
    return nba_player(card, stat, scope)


# ---------- NBA measurables and draft (checked against Wikipedia) ----------

def nba_measurables(card: dict) -> list[dict]:
    p = sleeper.players("nba").get(card.get("sleeper_id"), {})
    base = dict(league="NBA", subject=card["name"], subject_key=card["key"], position=card.get("position"),
                scope="today", source="Sleeper", credit="Data via Sleeper", as_of="today", sample="listed")
    facts = []
    if p.get("height"):
        h = float(p["height"])
        facts.append(_fact(**base, stat="height", label="listed height", value=h, say=_feet(h),
                           definition="His listed height, in feet and inches."))
    if p.get("weight"):
        facts.append(_fact(**base, stat="listed_weight", label="listed weight", value=int(p["weight"]),
                           say=f"{int(p['weight'])} pounds", definition="His listed weight today.",
                           status="trusted", checked_against="Sleeper (trusted on its own)"))
    return facts or [_fact(**base, stat="measurables", status="dropped", note="no listed height or weight")]


def nba_draft(card: dict) -> dict:
    """Draft position from his Wikipedia infobox; checked against that year's draft page."""
    base = dict(league="NBA", subject=card["name"], subject_key=card["key"], stat="draft", label="draft position",
                definition="Where he was picked in the NBA draft.", scope="career", source="Wikipedia",
                credit="Wikipedia (CC BY-SA)", as_of="final", position=card.get("position"))
    page = wiki.find_page(card["name"], "NBA", card.get("position"))
    if not page:
        return _fact(**base, status="dropped", note="no Wikipedia page found")
    info = {k.replace("_", ""): wiki._clean(v) for k, v in
            re.findall(r"\|\s*(draft_?year|draft_?round|draft_?pick|draft_?team)\s*=([^\n]*)", page["text"])}
    year = re.sub(r"\D", "", info.get("draftyear", ""))[:4]
    rnd_text = info.get("draftround", "")
    if "undrafted" in " ".join(info.values()).lower() or (year and not re.sub(r"\D", "", rnd_text)):
        # Wikipedia lists only the year he entered for undrafted players
        return _fact(**base, value=None, say=f"went undrafted in {year}" if year else "went undrafted",
                     undrafted=True, draft_year=int(year) if year else None, sample="undrafted")
    rnd, pick = re.sub(r"\D", "", info.get("draftround", "")), re.sub(r"\D", "", info.get("draftpick", ""))
    if not (year and rnd and pick):
        return _fact(**base, status="dropped", note="his Wikipedia page doesn't list a draft position")
    team = info.get("draftteam", "")
    where = "1st overall pick" if pick == "1" else f"round {rnd}, pick {pick} overall"
    return _fact(**base, value={"year": int(year), "round": int(rnd), "pick": int(pick)},
                 say=f"{where} in the {year} NBA draft" + (f", by the {team}" if team else ""),
                 draft_year=int(year), draft_round=int(rnd), draft_pick=int(pick), sample=f"{year} draft")
