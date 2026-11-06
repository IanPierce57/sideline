"""Style profiles: how a player actually plays, so the hosts' opinions stay believable
(decided Nov 5, 2026).

An opinion doesn't have to be provably true ("Caleb Williams is exciting" is fine),
but it can't be one no knowledgeable fan would hold ("Jared Goff is a dual-threat
quarterback"). Each player in a segment gets a style profile: a few stats that show
how he plays, ranked against players at his position. The profile is shown to the
writer and the claims checker as plain words ("rushing: very low for a QB"), never as
numbers, so it can't be quoted on air. Every number a host says still comes from the
checked fact pack.

STYLE_LABELS lists common labels ("dual threat", "deep threat", "workhorse back") and
the profile trait each one needs. If a host gives a player a label his profile clearly
contradicts, the line checker flags it and the line is rewritten."""

import re
from functools import lru_cache

import polars as pl

from . import nflv, positions, sleeper

# ---------- What a profile measures ----------
# group -> [(trait, plain words, how to read it: higher = more of this)]
TRAITS = {
    "QB": [("rush_ypg", "running the ball (rushing yards per game)"),
           ("adot", "how far downfield he throws (average depth of target)"),
           ("aggressiveness", "throws into tight coverage (Next Gen Stats aggressiveness)"),
           ("cpoe", "accuracy (completion percentage over expected)"),
           ("int_rate", "interceptions per pass"),
           ("time_to_throw", "how long he holds the ball"),
           ("big_plays", "completions of 20+ yards per pass")],
    "RB": [("carries_pg", "carries per game"), ("targets_pg", "targets per game (catching passes)"),
           ("big_runs", "runs of 20+ yards per carry"), ("ryoe", "rush yards over expected per carry"),
           ("ypc", "yards per carry")],
    "WR": [("adot", "how far downfield he's targeted (average depth of target)"), ("separation", "separation from defenders"),
           ("yac_oe", "yards after the catch over expected"), ("catch_pct", "catch rate"),
           ("targets_pg", "targets per game"), ("big_plays", "catches of 20+ yards per catch")],
    "TE": [("adot", "how far downfield he's targeted"), ("separation", "separation from defenders"),
           ("yac_oe", "yards after the catch over expected"), ("targets_pg", "targets per game")],
    "FRONT": [("pressure_pg", "sacks plus QB hits per game"), ("sacks_pg", "sacks per game"),
              ("tfl_pg", "tackles for loss per game"), ("tackles_pg", "tackles per game")],
    "DB": [("ballhawk_pg", "interceptions plus passes defended per game"), ("int_pg", "interceptions per game"),
           ("tackles_pg", "tackles per game")],
    "NBA": [("pts_pg", "scoring (points per game)"), ("tpm_pg", "three-pointers made per game"),
            ("ast_pg", "playmaking (assists per game)"), ("reb_pg", "rebounds per game"),
            ("blk_pg", "blocks per game"), ("stl_pg", "steals per game")],
}
# The least a player needs to be ranked (too small a sample says nothing about style).
QUALIFY = {"QB": ("attempts", 100), "RB": ("carries", 40), "WR": ("targets", 25), "TE": ("targets", 20),
           "FRONT": ("games", 4), "DB": ("games", 4), "NBA": ("gp", 5)}


def group_for(position: str | None, league: str) -> str | None:
    if league == "NBA":
        return "NBA"
    lab = positions.label(position) or ""
    if lab in ("QB",):
        return "QB"
    if lab in ("RB", "HB", "FB", "TB"):
        return "RB"
    if lab in ("WR", "SLOT"):
        return "WR"
    if lab == "TE":
        return "TE"
    if lab in ("DE", "DT", "NT", "DL", "EDGE", "OLB", "ILB", "MLB", "LB", "MIKE", "WILL", "SAM"):
        return "FRONT"
    if lab in ("DB", "CB", "S", "FS", "SS", "NICKEL"):
        return "DB"
    return None


# ---------- Building the tables (every qualified player at a position) ----------

def _ngs(kind: str, season: int) -> dict:
    df = nflv.nextgen(kind).filter((pl.col("season") == season) & (pl.col("season_type") == "REG") & (pl.col("week") == 0))
    return {r["player_gsis_id"]: r for r in df.iter_rows(named=True)}


@lru_cache(maxsize=16)
def _nfl_table(group: str, season: int) -> dict:
    """{gsis_id: {trait: value}} for every qualified player in the group."""
    ps = nflv.player_stats_by_season().filter((pl.col("season") == season) & (pl.col("season_type") == "REG"))
    want = {"QB": ["QB"], "RB": ["RB", "FB"], "WR": ["WR"], "TE": ["TE"]}.get(group)
    if want:
        ps = ps.filter(pl.col("position").is_in(want))
    else:
        ps = ps.filter(pl.col("position_group") == ("DB" if group == "DB" else None) if group == "DB"
                       else pl.col("position_group").is_in(["DL", "LB"]))
    passing, receiving, rushing = (_ngs(k, season) for k in ("passing", "receiving", "rushing"))
    col, floor = QUALIFY[group]
    out = {}
    for r in ps.iter_rows(named=True):
        if (r.get(col) or 0) < floor:
            continue
        g = max(r["games"] or 1, 1)
        pid = r["player_id"]
        if group == "QB":
            n = passing.get(pid, {})
            att = max(r["attempts"] or 1, 1)
            t = {"rush_ypg": (r["rushing_yards"] or 0) / g, "adot": n.get("avg_intended_air_yards"),
                 "aggressiveness": n.get("aggressiveness"), "cpoe": n.get("completion_percentage_above_expectation"),
                 "int_rate": (r["passing_interceptions"] or 0) / att, "time_to_throw": n.get("avg_time_to_throw"),
                 "big_plays": (r["passing_20"] or 0) / att}
        elif group == "RB":
            n = rushing.get(pid, {})
            c = max(r["carries"] or 1, 1)
            t = {"carries_pg": (r["carries"] or 0) / g, "targets_pg": (r["targets"] or 0) / g,
                 "big_runs": (r["rushing_20"] or 0) / c, "ryoe": n.get("rush_yards_over_expected_per_att"),
                 "ypc": (r["rushing_yards"] or 0) / c}
        elif group in ("WR", "TE"):
            n = receiving.get(pid, {})
            t = {"adot": n.get("avg_intended_air_yards"), "separation": n.get("avg_separation"),
                 "yac_oe": n.get("avg_yac_above_expectation"), "catch_pct": n.get("catch_percentage"),
                 "targets_pg": (r["targets"] or 0) / g,
                 "big_plays": (r["receiving_20"] or 0) / max(r["receptions"] or 1, 1)}
        elif group == "FRONT":
            t = {"pressure_pg": ((r["def_sacks"] or 0) + (r["def_qb_hits"] or 0)) / g, "sacks_pg": (r["def_sacks"] or 0) / g,
                 "tfl_pg": (r["def_tackles_for_loss"] or 0) / g,
                 "tackles_pg": ((r["def_tackles_solo"] or 0) + (r["def_tackle_assists"] or 0)) / g}
        else:
            t = {"ballhawk_pg": ((r["def_interceptions"] or 0) + (r["def_pass_defended"] or 0)) / g,
                 "int_pg": (r["def_interceptions"] or 0) / g,
                 "tackles_pg": ((r["def_tackles_solo"] or 0) + (r["def_tackle_assists"] or 0)) / g}
        out[pid] = {k: v for k, v in t.items() if v is not None}
    return out


@lru_cache(maxsize=4)
def _nba_table(season: int) -> dict:
    out = {}
    for pid, r in sleeper.season_stats("nba", season).items():
        gp = r.get("gp") or 0
        if gp < QUALIFY["NBA"][1] or (r.get("min") or 0) / gp < 15:
            continue
        out[pid] = {"pts_pg": (r.get("pts") or 0) / gp, "tpm_pg": (r.get("tpm") or 0) / gp, "ast_pg": (r.get("ast") or 0) / gp,
                    "reb_pg": (r.get("reb") or 0) / gp, "blk_pg": (r.get("blk") or 0) / gp, "stl_pg": (r.get("stl") or 0) / gp}
    return out


def _percentile(value: float, values: list[float]) -> int:
    below = sum(v < value for v in values)
    same = sum(v == value for v in values)
    return round(100 * (below + 0.5 * same) / len(values))


BANDS = [(15, "very low"), (35, "low"), (65, "about average"), (85, "high"), (101, "very high")]


def band(pct: int) -> str:
    return next(word for top, word in BANDS if pct < top)


GROUP_NAME = {"QB": "QBs", "RB": "running backs", "WR": "wide receivers", "TE": "tight ends",
              "FRONT": "defensive linemen and linebackers", "DB": "defensive backs", "NBA": "NBA rotation players"}


def profile(card: dict) -> dict | None:
    """{'name', 'group', 'season', 'traits': {trait: percentile}} or None if he hasn't
    played enough (this season first, else last season)."""
    group = group_for(card.get("position"), card["league"])
    if not group:
        return None
    sport = card["league"].lower()
    current = int(sleeper.state(sport)["season"])
    for season in (current, current - 1):
        if group == "NBA":
            table, me = _nba_table(season), card.get("sleeper_id")
        else:
            table, me = _nfl_table(group, season), card.get("gsis_id")
        if me in table and len(table) >= 10:
            traits = {}
            for trait, _ in TRAITS[group]:
                if trait in table[me]:
                    pool = [row[trait] for row in table.values() if trait in row]
                    traits[trait] = _percentile(table[me][trait], pool)
            label = f"{season}-{str(season + 1)[-2:]}" if group == "NBA" else str(season)
            return {"name": card["name"], "group": group, "season": label, "traits": traits}
    return None


def describe(p: dict) -> str:
    """A profile in words only (no numbers to quote): 'running the ball: very low for QBs'."""
    parts = [f"{words}: {band(p['traits'][t])}" for t, words in TRAITS[p["group"]] if t in p["traits"]]
    return f"{p['name']} ({p['season']}, compared with {GROUP_NAME[p['group']]}): " + "; ".join(parts)


# ---------- Labels and what they need ----------
# (pattern, groups it applies to, trait, "min" or "max", percentile)
# "min": the label needs at least this percentile. "max": at most. Thresholds are lenient on
# purpose: only labels a knowledgeable fan would call plainly wrong get flagged.
STYLE_LABELS = [
    (r"dual[- ]threat|mobile (?:qb|quarterback)|running quarterback|scrambl\w*|threat with his legs|runs? (?:it|the ball) a lot",
     {"QB"}, "rush_ypg", "min", 50, "a running threat"),
    (r"pocket passer|statue|doesn't run|won't run", {"QB"}, "rush_ypg", "max", 70, "a pocket passer"),
    (r"gunslinger|pushes the ball downfield|airs it out|vertical passer|throws deep|deep[- ]ball passer",
     {"QB"}, "adot", "min", 35, "a downfield thrower"),
    (r"game manager|dink(?:s)? and dunk|check[- ]?down (?:artist|merchant|machine)", {"QB"}, "adot", "max", 65, "a short-passing game manager"),
    (r"\binaccurate\b|scattershot|spray(?:s)? the ball", {"QB"}, "cpoe", "max", 70, "inaccurate"),
    (r"turnover[- ]prone|interception[- ]prone|careless with the ball|throws a lot of picks", {"QB"}, "int_rate", "min", 35, "turnover-prone"),
    (r"takes care of the (?:ball|football)|protects the (?:ball|football)|never turns it over", {"QB"}, "int_rate", "max", 65, "careful with the ball"),
    (r"holds the ball|holds onto the ball", {"QB"}, "time_to_throw", "min", 35, "slow to throw"),
    (r"quick release|gets (?:it|the ball) out (?:fast|quick)", {"QB"}, "time_to_throw", "max", 65, "quick to throw"),
    (r"workhorse|bell[- ]?cow|every[- ]down back|feature back", {"RB"}, "carries_pg", "min", 50, "a workhorse back"),
    (r"pass[- ]catching back|receiving back|catches (?:passes )?out of the backfield|third[- ]down back",
     {"RB"}, "targets_pg", "min", 45, "a pass-catching back"),
    (r"home[- ]run (?:hitter|threat)|big[- ]play back|breakaway", {"RB"}, "big_runs", "min", 40, "a big-play runner"),
    (r"\belusive\b|makes (?:people|defenders|guys) miss|shifty", {"RB"}, "ryoe", "min", 25, "elusive"),
    (r"deep threat|field[- ]stretcher|stretches the field|burner|vertical threat|takes the top off",
     {"WR", "TE"}, "adot", "min", 50, "a deep threat"),
    (r"possession receiver|chain[- ]mover|underneath (?:guy|receiver)", {"WR", "TE"}, "adot", "max", 70, "a possession receiver"),
    (r"route[- ]runn\w*|gets open|separat\w+", {"WR", "TE"}, "separation", "min", 20, "a receiver who gets open"),
    (r"after the catch|\byac\b", {"WR", "TE"}, "yac_oe", "min", 35, "dangerous after the catch"),
    (r"pass[- ]rusher|edge rusher|sack (?:artist|machine)|gets after the quarterback|quarterback hunter",
     {"FRONT"}, "pressure_pg", "min", 50, "a pass rusher"),
    (r"run[- ]stopper|tackling machine|tackle machine", {"FRONT", "DB"}, "tackles_pg", "min", 45, "a heavy tackler"),
    (r"ball[- ]?hawk|takeaway machine|playmaker in coverage", {"DB"}, "ballhawk_pg", "min", 45, "a ball hawk"),
    (r"sharpshooter|knockdown shooter|marksman|three-point (?:shooter|threat)|\bshooter\b", {"NBA"}, "tpm_pg", "min", 50, "a shooter"),
    (r"playmaker|facilitator|floor general|pass-first", {"NBA"}, "ast_pg", "min", 55, "a playmaker"),
    (r"rim protector|shot[- ]blocker", {"NBA"}, "blk_pg", "min", 60, "a rim protector"),
    (r"\brebounder\b|cleans the glass|owns the glass", {"NBA"}, "reb_pg", "min", 55, "a rebounder"),
    (r"\bscorer\b|bucket[- ]getter|walking bucket", {"NBA"}, "pts_pg", "min", 50, "a scorer"),
]


def _names(p: dict) -> list[str]:
    full = p["name"]
    last = re.sub(r"\b(jr|sr|ii|iii|iv)\.?$", "", full, flags=re.I).split()[-1]
    return [full, last]


def check_labels(lines: list[dict], profiles: list[dict]) -> list[dict]:
    """Lines that pin a style label on a player whose profile clearly contradicts it.
    A label counts only when exactly one profiled player is named in the same sentence."""
    problems = []
    for line in lines:
        for sentence in re.split(r"(?<=[.!?])\s+", line["text"]):
            low = sentence.lower()
            named = [p for p in profiles if any(re.search(r"\b" + re.escape(n.lower()) + r"\b", low) for n in _names(p))]
            if len(named) != 1:
                continue
            p = named[0]
            for pattern, groups, trait, kind, limit, what in STYLE_LABELS:
                if p["group"] not in groups or trait not in p["traits"] or not re.search(pattern, low):
                    continue
                pct = p["traits"][trait]
                if (kind == "min" and pct < limit) or (kind == "max" and pct > limit):
                    words = dict(TRAITS[p["group"]])[trait]
                    problems.append({"line": line["line"], "problem": (
                        f"calls {p['name']} {what}, but his {words} is {band(pct)} for {GROUP_NAME[p['group']]} "
                        f"({p['season']}); no fan would call him that. Pick a description that fits how he plays")})
    return problems
