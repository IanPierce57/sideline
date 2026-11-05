"""Finding players by name, by ID, never by name alone.

Every player gets a key like "nfl:4046" (Sleeper's ID). NFL players also carry
their nflverse ID (gsis_id), which is how the two sources are matched exactly.
When a name belongs to more than one player, lookups return all of them so the
topic check can ask which one."""

import difflib
import re
import unicodedata

from . import sleeper

SKILL = {"nfl": {"QB", "RB", "WR", "TE", "K", "DEF", "LB", "DL", "DB", "DE", "DT", "CB", "S", "OL", "OT", "G", "C"},
         "nba": {"PG", "SG", "SF", "PF", "C", "G", "F"}}


def _norm(name: str) -> str:
    """Compare names without accents, punctuation, or suffixes: Jokić = Jokic, T.J. = TJ."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    plain = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", plain.lower())
    return re.sub(r"[^a-z]", "", plain)


def _gsis(sport: str, pid: str, p: dict):
    """The player's nflverse ID: from Sleeper, or else from nflverse's own crosswalk."""
    if sport != "nfl":
        return None
    from . import nflv
    return (p.get("gsis_id") or "").strip() or nflv.sleeper_to_gsis().get(pid)


def _card(sport: str, pid: str, p: dict) -> dict:
    return {
        "key": f"{sport}:{pid}",
        "league": sport.upper(),
        "name": p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
        "team": p.get("team"),
        "position": p.get("position"),
        "active": bool(p.get("active")) if "active" in p else p.get("status") in ("Active", "ACT"),
        "status": p.get("status"),
        "injury_status": p.get("injury_status"),
        "years_exp": p.get("years_exp"),
        "gsis_id": _gsis(sport, pid, p),
        "sleeper_id": pid,
    }


def find(name: str, league: str | None = None) -> dict:
    """Look up a player. Returns {'matches': [...], 'suggestions': [...]}.
    More than one match means the name is shared and someone has to choose."""
    target = _norm(name)
    leagues = [league.lower()] if league else ["nfl", "nba"]
    matches, pool = [], {}
    for sport in leagues:
        for pid, p in sleeper.players(sport).items():
            full = p.get("full_name") or ""
            if not full or (p.get("position") not in SKILL[sport]):
                continue
            n = _norm(full)
            pool.setdefault(n, (sport, pid, p))
            if n == target:
                matches.append(_card(sport, pid, p))
    # Prefer players who actually played: active, or with experience, over empty records.
    matches.sort(key=lambda c: (not c["active"], -(c["years_exp"] or 0)))
    suggestions = []
    if not matches:
        for close in difflib.get_close_matches(target, list(pool), n=3, cutoff=0.82):
            sport, pid, p = pool[close]
            suggestions.append(_card(sport, pid, p))
    return {"matches": matches, "suggestions": suggestions}


def by_key(key: str) -> dict:
    sport, pid = key.split(":", 1)
    return _card(sport, pid, sleeper.players(sport)[pid])


def describe(card: dict) -> str:
    """'Josh Allen (QB, BUF)' style label for confirmations."""
    team = card["team"] or "free agent / retired"
    return f"{card['name']} ({card['position']}, {team})"
