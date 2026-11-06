"""NBA games, teams, and standings (added Nov 5, 2026), built to the same depth as the NFL.

Sources:
  Sleeper's NBA schedule (approved Nov 4, 2026): every game, final scores, starters.
  Wikipedia team-season pages ("2026–27 Golden State Warriors season"): the game log,
    kept by editors independently of Sleeper, with every date, opponent, home or away,
    final score, and running record, plus future games. Wikipedia's standings templates
    give conference order and home and road records.
Every score, record, date, and rank in a fact must match on both, or it's crossed off.
Wikipedia game logs and standings are refreshed every 3 hours (they change daily)."""

import re
from datetime import date, timedelta
from functools import lru_cache

from . import sleeper, wiki
from .net import get_json

# Sleeper code -> (full name, nickname, how Wikipedia's game logs name the city, conference)
TEAMS = {
    "ATL": ("Atlanta Hawks", "Hawks", "Atlanta", "East"), "BOS": ("Boston Celtics", "Celtics", "Boston", "East"),
    "BKN": ("Brooklyn Nets", "Nets", "Brooklyn", "East"), "CHA": ("Charlotte Hornets", "Hornets", "Charlotte", "East"),
    "CHI": ("Chicago Bulls", "Bulls", "Chicago", "East"), "CLE": ("Cleveland Cavaliers", "Cavaliers", "Cleveland", "East"),
    "DAL": ("Dallas Mavericks", "Mavericks", "Dallas", "West"), "DEN": ("Denver Nuggets", "Nuggets", "Denver", "West"),
    "DET": ("Detroit Pistons", "Pistons", "Detroit", "East"), "GSW": ("Golden State Warriors", "Warriors", "Golden State", "West"),
    "HOU": ("Houston Rockets", "Rockets", "Houston", "West"), "IND": ("Indiana Pacers", "Pacers", "Indiana", "East"),
    "LAC": ("Los Angeles Clippers", "Clippers", "L.A. Clippers", "West"), "LAL": ("Los Angeles Lakers", "Lakers", "L.A. Lakers", "West"),
    "MEM": ("Memphis Grizzlies", "Grizzlies", "Memphis", "West"), "MIA": ("Miami Heat", "Heat", "Miami", "East"),
    "MIL": ("Milwaukee Bucks", "Bucks", "Milwaukee", "East"), "MIN": ("Minnesota Timberwolves", "Timberwolves", "Minnesota", "West"),
    "NOP": ("New Orleans Pelicans", "Pelicans", "New Orleans", "West"), "NYK": ("New York Knicks", "Knicks", "New York", "East"),
    "OKC": ("Oklahoma City Thunder", "Thunder", "Oklahoma City", "West"), "ORL": ("Orlando Magic", "Magic", "Orlando", "East"),
    "PHI": ("Philadelphia 76ers", "76ers", "Philadelphia", "East"), "PHX": ("Phoenix Suns", "Suns", "Phoenix", "West"),
    "POR": ("Portland Trail Blazers", "Trail Blazers", "Portland", "West"), "SAC": ("Sacramento Kings", "Kings", "Sacramento", "West"),
    "SAS": ("San Antonio Spurs", "Spurs", "San Antonio", "West"), "TOR": ("Toronto Raptors", "Raptors", "Toronto", "East"),
    "UTA": ("Utah Jazz", "Jazz", "Utah", "West"), "WAS": ("Washington Wizards", "Wizards", "Washington", "East"),
}
ALIASES = {"sixers": "PHI", "blazers": "POR", "cavs": "CLE", "mavs": "DAL", "wolves": "MIN", "t-wolves": "MIN",
           "dubs": "GSW", "okc": "OKC", "la lakers": "LAL", "la clippers": "LAC", "nola": "NOP"}
WIKI_CODES = {"PHO": "PHX", "BRK": "BKN", "CHO": "CHA", "GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS"}
LOOK_AHEAD_DAYS = 7          # NBA teams play every couple of days


def team_code(name: str):
    low = name.strip().lower().replace("’", "'")
    if low in ALIASES:
        return ALIASES[low]
    for code, (full, nick, city, _) in TEAMS.items():
        if low in (code.lower(), full.lower(), nick.lower(), city.lower()):
            return code
    return None


def season() -> int:
    """Sleeper's NBA season: 2026 means 2026-27."""
    return int(sleeper.state("nba")["season"])


def label(season_start: int) -> str:
    return f"{season_start}–{str(season_start + 1)[-2:]}"


# ---------- Source 1: Sleeper's schedule ----------

def schedule(season_start: int | None = None) -> list[dict]:
    s = season_start or season()
    games = get_json(f"https://api.sleeper.app/schedule/nba/regular/{s}", f"sleeper/schedule_nba_regular_{s}", max_age_hours=3)
    return sorted(games, key=lambda g: g["date"])


def played(code: str, season_start: int | None = None) -> list[dict]:
    """The team's finished games, oldest first: {date, opp, home, pf, pa, starters}."""
    out = []
    for g in schedule(season_start):
        if g["status"] != "complete":
            continue
        for me, them, home in (("home", "away", True), ("away", "home", False)):
            if g[me]["team"] == code:
                out.append({"date": g["date"], "opp": g[them]["team"], "home": home, "pf": g[me].get("points"),
                            "pa": g[them].get("points"), "starters": g[me].get("starters") or []})
    return out


# ---------- Source 2: Wikipedia's game logs and standings ----------

def _city_code(text: str):
    link = re.search(r"\[\[\d{4}–\d{2} ([^|\]]+?) season", text)
    if link:
        return next((c for c, t in TEAMS.items() if t[0] == link.group(1).strip()), None)
    city = re.sub(r"[@\[\]]", "", text).strip()
    return next((c for c, t in TEAMS.items() if t[2].lower() == city.lower()), None)


MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], start=1)}


@lru_cache(maxsize=64)
def _game_log_cached(code: str, season_start: int, hour: int) -> tuple:
    page = wiki._page(f"{label(season_start)} {TEAMS[code][0]} season", max_age_hours=3)
    if not page:
        return ()
    text = page["text"]
    heading = re.search(r"=+\s*Regular season\s*=+", text[text.find("Game log"):] if "Game log" in text else text)
    start = (text.find("Game log") if "Game log" in text else 0) + heading.start() if heading else -1
    end = text.find("{{NBA game log end", start)
    if start < 0 or end < 0:
        return ()
    games = []
    for row in re.split(r"\n\|-", text[start:end])[1:]:
        row = row.split("{{NBA game log")[0]          # a month header can follow the last row of a month
        cells = [c.strip() for c in re.findall(r"^\|\s?(.*)$", row, re.M)]
        if len(cells) < 4:
            continue
        m = re.match(r"([A-Z][a-z]+) (\d+)", wiki._clean(cells[1]))   # NBA Cup dates are links
        if not m or m.group(1) not in MONTHS:
            continue
        month = MONTHS[m.group(1)]
        year = season_start if month >= 8 else season_start + 1
        score = re.search(r"pf=(\d+)\|pa=(\d+)", cells[3])
        games.append({"date": date(year, month, int(m.group(2))).isoformat(), "opp": _city_code(cells[2]),
                      "home": not cells[2].lstrip().startswith("@"),
                      "pf": int(score.group(1)) if score and "<!--" not in cells[3] else None,
                      "pa": int(score.group(2)) if score and "<!--" not in cells[3] else None,
                      "record": cells[-1].replace("–", "-").replace("−", "-") if score else None})
    return tuple(games)


def game_log(code: str, season_start: int | None = None) -> list[dict]:
    """Every regular-season game on the team's Wikipedia season page, played or not."""
    from time import time
    return list(_game_log_cached(code, season_start or season(), int(time() // 10800)))


@lru_cache(maxsize=8)
def _standings_cached(conf: str, season_start: int, hour: int) -> tuple:
    page = wiki._page(f"Template:{label(season_start)} NBA {conf} standings", max_age_hours=3)
    rows = []
    for line in (page or {}).get("text", "").splitlines():
        cells = [c.strip() for c in wiki._clean(line).strip().strip("|").split("|")]
        code = WIKI_CODES.get(cells[1], cells[1]) if len(cells) > 1 else ""
        if len(cells) >= 7 and code in TEAMS and all(re.fullmatch(r"\d+", x) for x in cells[2:6]):
            rows.append({"team": code, "home_w": int(cells[2]), "home_l": int(cells[3]),
                         "road_w": int(cells[4]), "road_l": int(cells[5])})
    return tuple(rows)


def standings(conf: str, season_start: int | None = None) -> list[dict]:
    """Wikipedia's conference standings in order: team, home and road wins and losses."""
    from time import time
    return list(_standings_cached(conf, season_start or season(), int(time() // 10800)))


# ---------- Finding a game ----------

def _upcoming(today: date) -> list[dict]:
    end = (today + timedelta(days=LOOK_AHEAD_DAYS)).isoformat()
    return [g for g in schedule() if g["status"] != "complete" and today.isoformat() <= g["date"] <= end]


def _confirm(g: dict):
    """A Sleeper game confirmed on the home team's Wikipedia game log (same date, opponent, home)."""
    home, away = g["home"]["team"], g["away"]["team"]
    log = game_log(home)
    if not log:
        return None, f"The {TEAMS[home][1]}' Wikipedia season page couldn't be read, so the game can't be confirmed."
    same = [x for x in log if x["opp"] == away and x["home"] and x["date"] == g["date"]]
    if not same:
        near = [x for x in log if x["opp"] == away and x["home"]]
        when = ", ".join(x["date"] for x in near[:3]) or "no home games against them"
        return None, (f"Sleeper has {TEAMS[away][1]} at {TEAMS[home][1]} on {g['date']}, but Wikipedia's game log "
                      f"doesn't ({when}), so it can't be confirmed.")
    d = date.fromisoformat(g["date"])
    return {"season": season(), "date": g["date"], "weekday": d.strftime("%A"), "home": home, "away": away,
            "game_id": g["game_id"]}, ""


def find_game(code_a: str, code_b: str, today: date | None = None):
    today = today or date.today()
    for g in _upcoming(today):
        if {g["home"]["team"], g["away"]["team"]} == {code_a, code_b}:
            return _confirm(g)
    return None, f"The {TEAMS[code_a][1]} and {TEAMS[code_b][1]} don't play each other in the next week."


def next_game(code: str, today: date | None = None):
    today = today or date.today()
    for g in _upcoming(today):
        if code in (g["home"]["team"], g["away"]["team"]):
            return _confirm(g)
    return None, f"The {TEAMS[code][1]} don't have a game in the next week."


def upcoming_games(codes: list[str], today: date | None = None, limit: int = 3) -> list[str]:
    today = today or date.today()
    games = _upcoming(today)
    mine = [g for g in games if {g["home"]["team"], g["away"]["team"]} & set(codes)] or games
    out = []
    for g in mine[:limit]:
        d = date.fromisoformat(g["date"])
        out.append(f"Who wins {TEAMS[g['away']['team']][1]} at {TEAMS[g['home']['team']][1]} on {d:%A}, {d:%b}. {d.day}?")
    return out


# ---------- Checked team facts ----------

def agreed_games(code: str):
    """The team's games that both sources agree on, oldest first, and a problem if they
    disagree about any game. If Wikipedia is behind (last night's games not filled in yet),
    the list stops at the last date both have, and through says which date that is."""
    sl = played(code)
    wk = {(g["date"], g["opp"], g["home"]): g for g in game_log(code)}
    if not wk:
        return [], None, "the team's Wikipedia season page couldn't be read"
    finished = [k[0] for k, g in wk.items() if g["pf"] is not None]
    last_wiki = max(finished) if finished else ""
    out = []
    for g in sl:
        w = wk.get((g["date"], g["opp"], g["home"]))
        if g["date"] > last_wiki:
            break                                        # Wikipedia hasn't caught up yet
        if not w or (w["pf"], w["pa"]) != (g["pf"], g["pa"]):
            theirs = f"{w['pf']}-{w['pa']}" if w and w["pf"] is not None else "not listed"
            return out, None, (f"the sources disagree about the {g['date']} game against the {TEAMS[g['opp']][1]} "
                               f"(Sleeper {g['pf']}-{g['pa']}, Wikipedia {theirs})")
        if w["pf"] is None:
            break
        out.append(g)
    return out, (out[-1]["date"] if out else None), ""


def _base(code: str, stat: str, label_: str, definition: str, through: str | None) -> dict:
    d = date.fromisoformat(through) if through else None
    return dict(league="NBA", subject=TEAMS[code][0], subject_key=f"nbateam:{code}", stat=stat, label=label_,
                definition=definition, scope=f"{label(season())} regular season", source="Sleeper and Wikipedia",
                credit="Data via Sleeper; game logs: Wikipedia (CC BY-SA)", status="verified",
                checked_against="Wikipedia game log (every game)", checked_value=None, note="",
                as_of=f"through {d:%b}. {d.day}" if d else "")


def _dropped(code: str, stat: str, label_: str, why: str) -> dict:
    return dict(league="NBA", subject=TEAMS[code][0], subject_key=f"nbateam:{code}", stat=stat, label=label_,
                status="dropped", note=why, scope=f"{label(season())} regular season", say=None)


def _wl(games: list[dict]):
    w = sum(g["pf"] > g["pa"] for g in games)
    return w, len(games) - w


def team_facts(code: str) -> list[dict]:
    """Record, home and road records, scoring, point differential, last five, streak, all
    from games both sources agree on."""
    games, through, problem = agreed_games(code)
    names = ("team_record", "home_road", "scoring", "last_five", "streak")
    if problem or not games:
        return [_dropped(code, n, n.replace("_", " "), problem or "no games yet") for n in names]
    w, l = _wl(games)
    hw, hl = _wl([g for g in games if g["home"]])
    rw, rl = _wl([g for g in games if not g["home"]])
    n = len(games)
    pf, pa = sum(g["pf"] for g in games) / n, sum(g["pa"] for g in games) / n
    diff = pf - pa
    last = games[-5:][::-1]
    lines = [f"{'W' if g['pf'] > g['pa'] else 'L'} {g['pf']}-{g['pa']} {'vs' if g['home'] else 'at'} {TEAMS[g['opp']][1]}"
             f" ({date.fromisoformat(g['date']):%b}. {date.fromisoformat(g['date']).day})" for g in last]
    streak_kind = "W" if games[-1]["pf"] > games[-1]["pa"] else "L"
    streak = 0
    for g in reversed(games):
        if ("W" if g["pf"] > g["pa"] else "L") != streak_kind:
            break
        streak += 1
    return [
        dict(_base(code, "team_record", "record", "Wins and losses this regular season.", through),
             value={"wins": w, "losses": l}, say=f"{w}-{l}", sample=f"{n} games"),
        dict(_base(code, "home_road", "home and road records", "Record at home and on the road.", through),
             value={"home_wins": hw, "home_losses": hl, "road_wins": rw, "road_losses": rl},
             say=f"{hw}-{hl} at home, {rw}-{rl} on the road", sample=f"{n} games"),
        dict(_base(code, "scoring", "points scored and allowed per game",
                   "Average points the team scores and gives up per game; the difference is its point differential.", through),
             value={"for": round(pf, 1), "against": round(pa, 1), "diff": round(diff, 1)},
             say=f"{pf:.1f} points scored and {pa:.1f} allowed per game ({'+' if diff >= 0 else ''}{diff:.1f} differential)",
             sample=f"{n} games"),
        dict(_base(code, "last_five", f"last {len(last)} results", "Final scores of the team's most recent games, newest first.", through),
             value=dict(zip(("wins", "losses"), _wl(last))), say="; ".join(lines), sample=f"{len(last)} games"),
        dict(_base(code, "streak", "current streak", "How many games in a row the team has won or lost.", through),
             value=streak, say=(f"{'won' if streak_kind == 'W' else 'lost'} {streak} straight" if streak > 1 else
                               f"{'won' if streak_kind == 'W' else 'lost'} their last game"), sample=f"{streak} games"),
    ]


def head_to_head(code: str, opp: str) -> dict | None:
    games, through, problem = agreed_games(code)
    meet = [g for g in games if g["opp"] == opp]
    if problem or not meet:
        return None
    lines = [f"{'W' if g['pf'] > g['pa'] else 'L'} {g['pf']}-{g['pa']} {'vs' if g['home'] else 'at'} {TEAMS[opp][1]}"
             f" ({date.fromisoformat(g['date']):%b}. {date.fromisoformat(g['date']).day})" for g in meet]
    return dict(_base(code, "head_to_head", f"this season's games against the {TEAMS[opp][1]}",
                      "Final scores of their meetings this season.", through),
                value=dict(zip(("wins", "losses"), _wl(meet))), say="; ".join(lines), sample=f"{len(meet)} games")


def conference_rank(code: str) -> dict:
    """Place in the conference by winning percentage. Confirmed only when Sleeper's and
    Wikipedia's standings agree on every team's record in that conference."""
    conf = TEAMS[code][3]
    lab = f"place in the {conf}ern Conference"
    mine = {}
    for c, t in TEAMS.items():
        if t[3] == conf:
            mine[c] = _wl(played(c))
    theirs = {r["team"]: (r["home_w"] + r["road_w"], r["home_l"] + r["road_l"]) for r in standings(conf)}
    if theirs != mine:
        off = [c for c in mine if theirs.get(c) != mine[c]]
        return _dropped(code, "conference_rank", lab, f"Wikipedia's standings aren't caught up for {', '.join(off[:4])}")
    pct = {c: (w / (w + l) if w + l else 0) for c, (w, l) in mine.items()}
    better = sum(1 for c in pct if pct[c] > pct[code])
    tied = sum(1 for c in pct if pct[c] == pct[code]) > 1
    place = better + 1
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(place if place < 20 else place % 10, "th")
    w, l = mine[code]
    return dict(_base(code, "conference_rank", lab, "Place in the conference standings by winning percentage.", None),
                value=place, say=f"{'tied for ' if tied else ''}{place}{suffix} in the {conf} at {w}-{l}",
                sample=f"{len(mine)} teams", checked_against="Wikipedia standings (every team's record)", as_of="today")


def rest(game: dict) -> list[dict]:
    """Days since each team's last game before this one, from both schedules."""
    out = []
    for code in (game["away"], game["home"]):
        before_s = [g["date"] for g in schedule() if g["date"] < game["date"] and code in (g["home"]["team"], g["away"]["team"])]
        before_w = [g["date"] for g in game_log(code) if g["date"] < game["date"]]
        if not before_s or not before_w or before_s[-1] != before_w[-1]:
            out.append(_dropped(code, "rest", "rest before the game", "the schedules disagree about the last game"))
            continue
        days = (date.fromisoformat(game["date"]) - date.fromisoformat(before_s[-1])).days - 1
        say_ = "playing the second night of a back-to-back" if days == 0 else f"{days} day{'s' if days != 1 else ''} of rest"
        out.append(dict(_base(code, "rest", "rest before the game", "Days off since the team's last game.", None),
                        value=days, say=say_, sample="one game", checked_against="Wikipedia game log (dates)", as_of="today"))
    return out


def head_coach(code: str) -> dict:
    """The coach on the team's Wikipedia page, confirmed on its season page."""
    team_page = wiki._page(TEAMS[code][0])
    season_page = wiki._page(f"{label(season())} {TEAMS[code][0]} season", max_age_hours=3)
    pick = lambda pg: (lambda m: wiki._clean(m.group(1)) if m else None)(  # noqa: E731
        re.search(r"\|\s*(?:head[ _]coach|coach)\s*=([^\n]*)", pg["text"]) if pg else None)
    a, b = pick(team_page), pick(season_page)
    if not a or a != b:
        return _dropped(code, "head_coach", "head coach", f"team page says {a}, season page says {b}")
    return dict(_base(code, "head_coach", "head coach", "The team's head coach.", None), value=a, say=a,
                scope="today", as_of="today", source="Wikipedia", credit="Wikipedia (CC BY-SA)",
                checked_against="Wikipedia (team page and season page)")


def _name(pid: str) -> str:
    p = sleeper.players("nba").get(pid, {})
    return p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or pid


def rotation(code: str) -> set[str]:
    """Sleeper IDs of the team's rotation players: 15+ minutes a game this season."""
    stats = sleeper.season_stats("nba", season())
    out = set()
    for pid, p in sleeper.players("nba").items():
        r = stats.get(pid) or {}
        mins = r.get("min") or ((r.get("sp") or 0) / 60)
        if p.get("team") == code and r.get("gp") and mins / r["gp"] >= 15:
            out.add(pid)
    return out


def injuries(code: str) -> dict:
    """Rotation players with an injury designation today (Sleeper, trusted)."""
    hurt = []
    for pid in rotation(code):
        p = sleeper.players("nba")[pid]
        if p.get("injury_status"):
            part = f", {p['injury_body_part'].lower()}" if p.get("injury_body_part") else ""
            hurt.append(f"{_name(pid)} ({p.get('position')}{part}): {p['injury_status']}")
    return dict(_base(code, "injuries", "injured rotation players",
                      "Players averaging 15+ minutes with an injury designation today.", None),
                value=None, say="; ".join(sorted(hurt)) or "none of their rotation players (15+ minutes a game) are on the injury report; bench players aren't covered", scope="today",
                as_of="today", source="Sleeper", credit="Data via Sleeper", status="trusted",
                checked_against="Sleeper (trusted on its own)", sample=f"{len(hurt)} players")


def last_starters(code: str) -> dict:
    """The five who started the team's most recent game (Sleeper, trusted)."""
    games = played(code)
    if not games or not games[-1]["starters"]:
        return _dropped(code, "last_starters", "starting five last game", "no starters listed")
    g = games[-1]
    d = date.fromisoformat(g["date"])
    return dict(_base(code, "last_starters", "starting five in the last game",
                      "The five players who started the team's most recent game.", None),
                value=None, say=f"{', '.join(_name(p) for p in g['starters'])} (vs {TEAMS[g['opp']][1]}, {d:%b}. {d.day})",
                scope="last game", as_of="today", source="Sleeper", credit="Data via Sleeper", status="trusted",
                checked_against="Sleeper (trusted on its own)", sample="one game")


def game_pack(game: dict) -> list[dict]:
    d = date.fromisoformat(game["date"])
    facts = [dict(_base(game["home"], "game", "the game", "Date and home team, confirmed on Sleeper's schedule and "
                        "the home team's Wikipedia game log.", None),
                  subject=f"{TEAMS[game['away']][0]} at {TEAMS[game['home']][0]}",
                  subject_key=f"nbagame:{game['away']}@{game['home']}", value=None, scope=label(season()),
                  say=f"{TEAMS[game['away']][0]} at {TEAMS[game['home']][0]}, {game['weekday']}, {d:%B} {d.day}, {d.year}",
                  as_of="today", checked_against="Wikipedia game log")]
    for code in (game["away"], game["home"]):
        facts += team_facts(code)
        facts += [conference_rank(code), injuries(code), last_starters(code), head_coach(code)]
    facts += rest(game)
    h2h = head_to_head(game["home"], game["away"])
    if h2h:
        facts.append(h2h)
    return facts
