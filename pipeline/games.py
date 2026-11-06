"""Single-game previews (NFL only for now; decided Nov 5, 2026).

A game has to be real before the show previews it: code finds it on nflverse's
schedule and confirms the date, home team, and away team on Sleeper's schedule.
If the two disagree, or there's no such game coming up, the topic is turned away
with real upcoming games to pick from instead."""

from datetime import date, timedelta

import polars as pl

from . import nflv, sleeper

# Sleeper-style code -> (full name, nickname). nflverse writes the Rams as "LA".
TEAMS = {
    "ARI": ("Arizona Cardinals", "Cardinals"), "ATL": ("Atlanta Falcons", "Falcons"),
    "BAL": ("Baltimore Ravens", "Ravens"), "BUF": ("Buffalo Bills", "Bills"),
    "CAR": ("Carolina Panthers", "Panthers"), "CHI": ("Chicago Bears", "Bears"),
    "CIN": ("Cincinnati Bengals", "Bengals"), "CLE": ("Cleveland Browns", "Browns"),
    "DAL": ("Dallas Cowboys", "Cowboys"), "DEN": ("Denver Broncos", "Broncos"),
    "DET": ("Detroit Lions", "Lions"), "GB": ("Green Bay Packers", "Packers"),
    "HOU": ("Houston Texans", "Texans"), "IND": ("Indianapolis Colts", "Colts"),
    "JAX": ("Jacksonville Jaguars", "Jaguars"), "KC": ("Kansas City Chiefs", "Chiefs"),
    "LV": ("Las Vegas Raiders", "Raiders"), "LAC": ("Los Angeles Chargers", "Chargers"),
    "LAR": ("Los Angeles Rams", "Rams"), "MIA": ("Miami Dolphins", "Dolphins"),
    "MIN": ("Minnesota Vikings", "Vikings"), "NE": ("New England Patriots", "Patriots"),
    "NO": ("New Orleans Saints", "Saints"), "NYG": ("New York Giants", "Giants"),
    "NYJ": ("New York Jets", "Jets"), "PHI": ("Philadelphia Eagles", "Eagles"),
    "PIT": ("Pittsburgh Steelers", "Steelers"), "SF": ("San Francisco 49ers", "49ers"),
    "SEA": ("Seattle Seahawks", "Seahawks"), "TB": ("Tampa Bay Buccaneers", "Buccaneers"),
    "TEN": ("Tennessee Titans", "Titans"), "WAS": ("Washington Commanders", "Commanders"),
}
TO_NFLVERSE = {"LAR": "LA"}
FROM_NFLVERSE = {v: k for k, v in TO_NFLVERSE.items()}
LOOK_AHEAD_DAYS = 14          # "this Sunday", "tonight", "next week": games in the next two weeks


def team_code(name: str):
    """'Patriots', 'New England', 'NE' -> 'NE'. None if it isn't an NFL team."""
    low = name.strip().lower()
    for code, (full, nick) in TEAMS.items():
        city = full[: -len(nick)].strip().lower()
        if low in (code.lower(), full.lower(), nick.lower(), city) or low == "niners" and code == "SF":
            return code
    return None


def nickname(code: str) -> str:
    return TEAMS[code][1]


def _season() -> int:
    return int(sleeper.state("nfl")["season"])


def _upcoming(today: date) -> pl.DataFrame:
    end = (today + timedelta(days=LOOK_AHEAD_DAYS)).isoformat()
    return nflv.schedules().filter((pl.col("season") == _season()) & pl.col("result").is_null() &
                                   (pl.col("gameday") >= today.isoformat()) & (pl.col("gameday") <= end))


def find_game(code_a: str, code_b: str, today: date | None = None):
    """The next game between two teams in the next two weeks, confirmed on both
    schedules. Returns (game, problem): game is None when there's a problem."""
    today = today or date.today()
    a, b = TO_NFLVERSE.get(code_a, code_a), TO_NFLVERSE.get(code_b, code_b)
    games = _upcoming(today).filter(((pl.col("home_team") == a) & (pl.col("away_team") == b)) |
                                    ((pl.col("home_team") == b) & (pl.col("away_team") == a))).sort("gameday")
    if not games.height:
        return None, f"The {nickname(code_a)} and {nickname(code_b)} don't play each other in the next two weeks."
    g = games.row(0, named=True)
    home, away = FROM_NFLVERSE.get(g["home_team"], g["home_team"]), FROM_NFLVERSE.get(g["away_team"], g["away_team"])
    stype = "post" if g["game_type"] != "REG" else "regular"
    other = [s for s in sleeper.nfl_schedule(g["season"], stype)
             if {s.get("home"), s.get("away")} == {home, away} and s.get("week") == g["week"]]
    if not other:
        return None, "That game is on one schedule but not the other, so it can't be confirmed."
    s = other[0]
    if (s["home"], s["away"], s["date"]) != (home, away, g["gameday"]):
        return None, (f"The two schedules disagree about that game (nflverse: {away} at {home} on {g['gameday']}; "
                      f"Sleeper: {s['away']} at {s['home']} on {s['date']}), so it can't be confirmed.")
    return {"season": g["season"], "week": g["week"], "game_type": g["game_type"], "date": g["gameday"],
            "weekday": g["weekday"], "time_et": g["gametime"], "home": home, "away": away,
            "stadium": g["stadium"], "neutral": g["location"] == "Neutral",
            "away_rest": g["away_rest"], "home_rest": g["home_rest"], "div_game": bool(g["div_game"])}, ""


def upcoming_games(codes: list[str], today: date | None = None, limit: int = 3) -> list[str]:
    """Real upcoming games for these teams (or any teams), as suggested topics."""
    today = today or date.today()
    nv = [TO_NFLVERSE.get(c, c) for c in codes]
    games = _upcoming(today).sort("gameday")
    if nv:
        mine = games.filter(pl.col("home_team").is_in(nv) | pl.col("away_team").is_in(nv))
        games = mine if mine.height else games
    out = []
    for g in games.head(limit).iter_rows(named=True):
        h, a = FROM_NFLVERSE.get(g["home_team"], g["home_team"]), FROM_NFLVERSE.get(g["away_team"], g["away_team"])
        d = date.fromisoformat(g["gameday"])
        out.append(f"Who wins {nickname(a)} at {nickname(h)} on {g['weekday']}, {d:%b}. {d.day}?")
    return out


def next_game(code: str, today: date | None = None):
    """A team's next game in the next two weeks, confirmed on both schedules."""
    today = today or date.today()
    c = TO_NFLVERSE.get(code, code)
    nxt = _upcoming(today).filter((pl.col("home_team") == c) | (pl.col("away_team") == c)).sort("gameday")
    if not nxt.height:
        return None, f"The {nickname(code)} don't have a game in the next two weeks."
    r = nxt.row(0, named=True)
    other = r["away_team"] if r["home_team"] == c else r["home_team"]
    return find_game(code, FROM_NFLVERSE.get(other, other), today)
