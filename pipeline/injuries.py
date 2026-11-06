"""Injuries, read the way people who follow the sport read them (added Nov 6, 2026, from the
user's notes):

- Status today. "Questionable" usually means he plays: teams list nearly everything now, so
  it's not a storyline. "Doubtful" means probably out. "Out", injured reserve, and PUP mean out.
- Availability: games played in each of the last five full seasons and this one, so a pattern
  of missed time (injury-prone) shows, and so does one lost season (one big injury). Sleeper's
  games played (trusted), checked against nflverse (NFL) or his Wikipedia career table (NBA).
- Injury history: the injuries his Wikipedia article reports in those seasons, kept ONLY when
  his games played back it up (that season, or the next one for an Achilles, an ACL, or
  anything season-ending, shows a big chunk missed). Otherwise it's crossed off. Tears,
  ruptures, and breaks are marked major.
One big injury doesn't make a player injury-prone; a pattern of missed seasons does.
"""

import re

import polars as pl

from . import nflv, sleeper, wiki

STATUS_MEANING = {                # Sleeper's labels we understand; anything else isn't mentioned
    "Questionable": "questionable (usually plays)",
    "DTD": "day-to-day (a minor injury; often plays)",
    "Doubtful": "doubtful (probably out)",
    "Out": "out",
    "IR": "on injured reserve (out)",
    "PUP": "on the PUP list (out)",
    "Sus": "suspended",
}
LIKELY_OUT = ("Doubtful", "Out", "IR", "PUP", "Sus")
YEARS_BACK = 5                    # full seasons shown, plus the one in progress
HISTORY_BACK = 6                  # injuries looked for this far back (one more, for a long recovery)
MISSED = 0.75                     # played under 75% of his team's games = a big chunk missed


def status_words(status: str | None) -> str:
    """Plain words for a Sleeper status; '' for none or one we don't understand."""
    return STATUS_MEANING.get(status or "", "")


def report_line(statuses: list[tuple[str, str]]) -> str:
    """Team injury report in plain words, most serious first; questionable last and labeled.
    statuses: (status, 'Name (POS, body part)')."""
    groups = {}
    for status, who in statuses:
        groups.setdefault(status, []).append(who)
    order = ["Out", "IR", "PUP", "Sus", "Doubtful", "DTD", "Questionable"]
    label = {"Out": "Out", "IR": "Injured reserve (out)", "PUP": "PUP list (out)", "Sus": "Suspended",
             "Doubtful": "Doubtful (probably out)", "DTD": "Day-to-day (minor; often plays)",
             "Questionable": "Questionable (usually plays; not a real concern on its own)"}
    return "; ".join(f"{label[s]}: {', '.join(sorted(groups[s]))}" for s in order if s in groups)


# ---------- Availability ----------

def _nfl_team_games(season: int, code: str) -> int:
    """Regular-season games the team finished (nflverse codes). 2022's canceled Bills-Bengals
    game means those two played 16 that year."""
    s = nflv.schedules().filter((pl.col("season") == season) & (pl.col("game_type") == "REG") &
                                pl.col("result").is_not_null() &
                                ((pl.col("home_team") == code) | (pl.col("away_team") == code)))
    return s.height


def _label(league: str, season: int) -> str:
    return str(season) if league == "NFL" else f"{season}–{str(season + 1)[-2:]}"


def season_games(card: dict, season: int, current: int, first: int | None) -> dict | None:
    """One season: Sleeper's games played (trusted), compared with nflverse or Wikipedia,
    out of his team's games. None before he was in the league."""
    from . import catalog, games, verify
    league = card["league"]
    if first is not None and season < first:
        return None
    if league == "NFL":
        gp = int((catalog.sleeper_season(season, "regular").get(card["sleeper_id"]) or {}).get("gp") or 0)
        other = nflv.player_stats_by_season().filter((pl.col("player_id") == card.get("gsis_id")) &
                                                     (pl.col("season") == season) & (pl.col("season_type") == "REG"))
        theirs = int(other["games"][0]) if other.height else None
        code = other["recent_team"][0] if other.height else games.TO_NFLVERSE.get(card.get("team") or "", card.get("team"))
        of = _nfl_team_games(season, code)
        if season == current and card.get("team"):
            # this season: Sleeper's schedule too, since its games played can include a game
            # nflverse hasn't posted yet (a Thursday night game, say)
            done = [g for g in sleeper.nfl_schedule(season) if g.get("status") == "complete"
                    and card["team"] in (g.get("home"), g.get("away"))]
            of = max(of, len(done))
        if season < current and of < 16:
            of = 17 if season >= 2021 else 16          # traded or missing: the full schedule
        if gp > of and theirs is not None and theirs <= of:
            gp = theirs                                  # can't play more games than his team did
    else:
        if first is None and season < current and not sleeper.season_stats("nba", season).get(card["sleeper_id"]):
            return None
        gp = int((sleeper.season_stats("nba", season).get(card["sleeper_id"]) or {}).get("gp") or 0)
        rows = verify._nba_table(card["name"], card.get("position"), False).get(season) if season < current else None
        theirs = int(sum(r.get("gp") or 0 for r in rows)) if rows else (0 if gp == 0 and season < current else None)
        if season < current:
            of = 72 if season == 2020 else 82            # 2020-21 was a 72-game season
        else:
            from . import nba
            of = len(nba.played(card.get("team") or ""))
    if not of:
        return None
    label = _label(league, season)
    out = {"season": season, "label": label, "gp": gp, "of": max(of, gp), "current": season == current,
           "compared": theirs is not None}
    if theirs is not None and theirs != gp:
        out.update(differs=True, note=f"{label}: Sleeper {gp}, {'nflverse' if league == 'NFL' else 'Wikipedia'} {theirs}")
    return out


def availability(card: dict) -> dict:
    """Games played, last five full seasons and this one."""
    league = card["league"]
    current = int(sleeper.state(league.lower())["season"])
    first = current - int(card["years_exp"]) if card.get("years_exp") is not None else None
    base = dict(league=league, subject=card["name"], subject_key=card["key"], stat="availability",
                label="games played by season", scope=f"last {YEARS_BACK} full seasons and this one", as_of="today",
                definition="Games he played each regular season, out of his team's games. Missing games can be injury, "
                           "rest, suspension, or not being on a roster yet; this doesn't say which.",
                source="Sleeper", credit="Data via Sleeper", position=card.get("position"))
    rows, notes, seasons, compared = [], [], [], 0
    for season in range(current - HISTORY_BACK, current + 1):
        one = season_games(card, season, current, first)
        if not one:
            continue
        compared += one.pop("compared")
        if one.pop("differs", None):
            notes.append(one.pop("note"))
        seasons.append(one)
        if season >= current - YEARS_BACK:
            rows.append(f"{one['label']}: {one['gp']} of {one['of']}{' so far' if one['current'] else ''}")
    shown = [s for s in seasons if s["season"] >= current - YEARS_BACK]
    if not shown:
        return {**base, "status": "dropped", "note": "no games found", "say": None}
    full = [s for s in shown if not s["current"]]
    big = [s for s in full if s["gp"] < MISSED * s["of"]]
    tally = (f"; he missed a quarter or more of his team's games in {len(big)} of his last {len(full)} full seasons"
             if full else "")
    status = "verified_sleeper_used" if notes else ("verified" if compared else "trusted")
    return {**base, "value": len(big), "say": "; ".join(rows) + tally, "season_rows": seasons, "big_misses": len(big),
            "full_seasons": len(full), "status": status,
            "checked_against": ("nflverse games" if league == "NFL" else "Wikipedia (career statistics table)")
                               if compared else "Sleeper (trusted on its own)",
            "note": ("games played differ: " + "; ".join(notes) + "; using Sleeper's") if notes else "",
            "sample": f"{len(seasons)} seasons"}


# ---------- Injury history ----------

BODY = (r"achilles(?: tendon)?|anterior cruciate ligament|posterior cruciate ligament|medial collateral ligament|"
        r"acl|mcl|pcl|lcl|meniscus|labrum|patellar tendon|quad(?:riceps)? tendon|kneecap|patella|collarbone|clavicle|"
        r"pectoral(?: muscle)?|biceps|hamstring|groin|adductor|calf|turf toe|toe|foot|ankle|knee|hip|shoulder|elbow|"
        r"fibula|tibia|leg|wrist|hand|thumb|ribs?|back|neck|vertebrae?|spine")
SIDE = r"(?:(?:his|the|a|an|left|right|lateral|medial|high|partial(?:ly)?|small|throwing|non-throwing)\s+){0,3}"
VERB = r"tore|torn|tearing|ruptur\w*|fractur\w*|broke|broken|dislocat\w*"
INJURY = re.compile(
    rf"\b(?P<verb>{VERB})\s+(?:(?:his|the|a|an|several|multiple)\s+)?(?P<mid>(?:\w+\s+){{0,5}}?)(?P<b1>{BODY})\b"
    rf"|\b(?P<noun>tear|rupture|fracture|sprain|strain|injury|injuries)\s+(?:of|in|to)\s+{SIDE}(?P<b2>{BODY})\b"
    rf"|\b(?P<b3>{BODY})\s+(?P<noun2>tear|rupture|fracture|sprain|strain|injury|injuries)\b"
    rf"|\b(?P<b4>turf toe|concussion)s?\b", re.I)
CANON = {"achilles tendon": "Achilles", "achilles": "Achilles", "anterior cruciate ligament": "ACL",
         "posterior cruciate ligament": "PCL", "medial collateral ligament": "MCL", "acl": "ACL", "mcl": "MCL",
         "pcl": "PCL", "lcl": "LCL", "rib": "ribs", "vertebra": "vertebrae", "quadriceps tendon": "quad tendon",
         "kneecap": "patella"}
REGION = {"ACL": "knee", "MCL": "knee", "PCL": "knee", "LCL": "knee", "meniscus": "knee", "patella": "knee",
          "patellar tendon": "knee", "quad tendon": "knee", "turf toe": "toe", "Achilles": "lower leg",
          "calf": "lower leg", "fibula": "lower leg", "tibia": "lower leg", "leg": "lower leg", "labrum": "shoulder"}
LONG = {"Achilles", "ACL", "patellar tendon", "quad tendon"}          # recovery that can run into the next season
SEASON_OVER = re.compile(r"season-ending|rest of the (?:regular )?season|remainder of the (?:regular )?season|"
                         r"end(?:ed|ing) his (?:\w+ )?season|out for the season|missed the entire", re.I)
PLAYOFFS = re.compile(r"playoff|postseason|\bfinals\b|conference (?:semi)?finals|super bowl|\bgame [1-7]\b", re.I)
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
DATED = re.compile(r"\b(" + "|".join(MONTHS) + r")\s+\d{1,2},\s+((?:19|20)\d\d)\b", re.I)
OTHER_SUBJECT = re.compile(r"\b([A-Z][a-z]+(?:'s|, who)|[A-Z][a-z]+\s+(?:suffered|sustained|tore|injured|exited|"
                           r"left|was|had|broke|ruptured|fractured))\b")
NOT_NAMES = {"He", "His", "On", "In", "During", "After", "Before", "Following", "Later", "The", "That", "This",
             "Despite", "While", "Although", "However", "Two", "Three", "Four", "Five", "It", "Head", "Week"}


def _heading_season(title: str, league: str):
    """A heading's season, only when it names exactly one ("2023", "2024–25 season"). Ranges
    ("2020–2022", "Los Angeles Lakers (2019–2025)") and draft or college sections give None."""
    if re.search(r"draft|college|high school|amateur|early life", title, re.I):
        return None
    if league == "NFL":
        years = re.findall(r"\b((?:19|20)\d\d)\b", title)
        return int(years[0]) if len(years) == 1 and not re.search(r"\d[–-](?:\d|present)", title) else None
    m = re.search(r"\b((?:19|20)\d\d)[–-](\d\d|\d{4})\b", title)
    if m and int(m.group(2)[-2:]) == (int(m.group(1)) + 1) % 100:
        return int(m.group(1))
    return None


def _sections(text: str, league: str):
    """(season, sentence) for every sentence. The season comes from a full date in the
    sentence ("On November 16, 2023"), otherwise from a heading that names a single season.
    Anything else is left without a season and skipped: a guessed year could pin an injury
    on the wrong season."""
    season = None
    for block in re.split(r"\n(?==)", text):
        head = re.match(r"(={2,})\s*([^=\n]+?)\s*\1", block)
        if head:
            found = _heading_season(head.group(2), league)
            if found is not None or len(head.group(1)) <= 3 or re.search(r"\b(?:19|20)\d\d\b", head.group(2)):
                season = found                          # a heading with a range of years resets it too
        body = re.sub(r"<ref[^>]*?/>|<ref.*?</ref>", "", block, flags=re.S)
        body = wiki._clean(re.sub(r"\{\{[^{}]*\}\}", "", body))
        for sentence in re.split(r"(?<=[.!?])\s+", body):
            if "||" in sentence:
                continue                                    # stats tables
            when = season
            d = DATED.search(sentence)
            if d:
                month, year = MONTHS[d.group(1).lower()], int(d.group(2))
                when = year if month >= (3 if league == "NFL" else 7) else year - 1
            yield when, sentence


def _about_him(sentence: str, start: int, names: set[str]) -> bool:
    """Is the injury at `start` his, not a teammate's or an opponent's?"""
    before = sentence[:start]
    mine = [m.end() for m in re.finditer(r"\b(he|his|him|" + "|".join(map(re.escape, names)) + r")\b", before, re.I)]
    if not mine and not re.search(r"\b(he|his)\b|" + "|".join(map(re.escape, names)), sentence, re.I):
        return False
    others = [m.end() for m in OTHER_SUBJECT.finditer(before)
              if re.match(r"[A-Z][a-z]+", m.group(1)).group(0) not in names | NOT_NAMES]
    return not others or bool(mine and max(mine) > max(others))


def _describe(m: re.Match, sentence: str) -> tuple[str, str, bool]:
    """(body part, plain description, major?) for one match."""
    raw = (m.group("b1") or m.group("b2") or m.group("b3") or m.group("b4")).lower()
    body = CANON.get(raw, raw)
    if m.group("b4"):
        return body, body, False
    verb = (m.group("verb") or "").lower()
    noun = (m.group("noun") or m.group("noun2") or "").lower()
    word = verb or noun
    kind = ("torn" if word.startswith(("tor", "tear")) else "ruptured" if word.startswith("rupt")
            else "fractured" if word.startswith("fract") else "broken" if word.startswith("brok")
            else "dislocated" if word.startswith("dislocat") else None)
    partial = "partial" in sentence[max(0, m.start() - 20): m.end()].lower()
    if kind:
        mid = (m.group("mid") or "").lower()
        ligament = " ligament" if "ligament" in mid and body not in ("ACL", "MCL", "PCL", "LCL") else ""
        return body, f"{'partially ' if partial else ''}{kind} {body}{ligament}", True
    if noun in ("sprain", "strain"):
        return body, f"{body} {noun}", False
    return body, f"{body} injury", False


def injury_history(card: dict, avail: dict | None = None) -> dict:
    """Injuries his Wikipedia article reports in recent seasons, each confirmed by games missed."""
    base = dict(league=card["league"], subject=card["name"], subject_key=card["key"], stat="injury_history",
                label="injury history", scope=f"the last {HISTORY_BACK} seasons", as_of="today",
                source="Wikipedia, confirmed by games played", credit="Wikipedia (CC BY-SA); games via Sleeper",
                position=card.get("position"),
                definition="Injuries his Wikipedia article reports, kept only when his games played show real time "
                           "missed. Games played are for the whole regular season, not a count of games that "
                           "injury cost him.")
    page = wiki.find_page(card["name"], card["league"], card.get("position"))
    if not page:
        return {**base, "status": "dropped", "note": "no Wikipedia page found", "say": None}
    avail = avail or availability(card)
    by_season = {s["season"]: s for s in avail.get("season_rows") or []}
    if not by_season:
        return {**base, "status": "dropped", "note": "no games played to confirm against", "say": None}
    names = {card["name"].split()[-1], card["name"].split()[0]}
    found = {}                                             # (season, body) -> entry
    for season, sentence in _sections(page["text"], card["league"]):
        if season is None or season < min(by_season) - 1 or re.search(r"\brecords?\b", sentence, re.I):
            continue
        for m in INJURY.finditer(sentence):
            if not _about_him(sentence, m.start(), names):
                continue
            body, what, major = _describe(m, sentence)
            if (season - 1, body) in found:
                continue                                    # "ten months after rupturing his Achilles..."
            entry = {"season": season, "body": body, "what": what, "major": major,
                     "over": bool(SEASON_OVER.search(sentence)), "playoffs": bool(PLAYOFFS.search(sentence))}
            old = found.get((season, body))
            if old:
                entry["over"] = entry["over"] or old["over"]
                entry["playoffs"] = entry["playoffs"] and old["playoffs"]
                if old["major"] or not major:
                    entry.update(what=old["what"], major=old["major"])
            found[(season, body)] = entry
    # Within a season: a major injury explains the missed time better than a minor one, and a
    # specific part (meniscus, turf toe) beats the general one (knee, toe).
    by = {}
    for f in found.values():
        by.setdefault(f["season"], []).append(f)
    kept = []
    for season in sorted(by, reverse=True):
        items = by[season]
        if any(f["major"] for f in items):
            items = [f for f in items if f["major"]]
        specific = {REGION[f["body"]] for f in items if f["body"] in REGION}
        items = [f for f in items if f["body"] not in specific]
        confirmed = []
        for f in items:
            if f["playoffs"] and not ((f["body"] in LONG and f["major"]) or f["over"]):
                continue                                    # a playoff knock can't be checked by regular-season games
            check = ([] if f["playoffs"] else [season]) + \
                    ([season + 1] if (f["body"] in LONG and f["major"]) or f["over"] or f["playoffs"] else [])
            seen = [by_season[s] for s in check if s in by_season]
            if any(s["gp"] < MISSED * s["of"] for s in seen):
                confirmed.append(f)
        if confirmed:
            kept.append((season, confirmed[:2]))
    if not kept:
        return {**base, "status": "dropped", "say": None,
                "note": "no injury in his article (recent seasons) that his games played confirm"}
    lg, parts, out = card["league"], [], []
    for season, items in kept[:3]:
        what = " and ".join(f"{f['what']}{' (major)' if f['major'] else ''}" for f in items)
        when = f"in the {_label(lg, season)} {'playoffs' if all(f['playoffs'] for f in items) else 'season'}"
        games = []
        if season in by_season and not all(f["playoffs"] for f in items):
            s = by_season[season]
            games.append(f"he played {s['gp']} of {s['of']} games that season")
        after = [by_season[y] for y in sorted(by_season) if y > season]
        if after and any((f["body"] in LONG and f["major"]) or f["over"] or f["playoffs"] for f in items):
            # spelled out so "seven games back from the Achilles" can't be said when it's 23
            listed = [f"{s['gp']} of {s['of']} {'so far this season' if s['current'] else 'in ' + s['label']}" for s in after]
            total = sum(s["gp"] for s in after)
            if len(after) <= 3:
                games.append("in the seasons since: " + ", ".join(listed) +
                             (f" ({total} games in all)" if len(after) > 1 else ""))
            else:                                       # long ago: the total, not every season again
                games.append(f"in the {len(after)} seasons since, counting this one: {total} games in all")
        parts.append(f"{what} {when}" + (f" ({'; '.join(games)})" if games else ""))
        out += items
    return {**base, "value": len(out), "say": "; ".join(parts), "injuries": out, "status": "verified",
            "checked_against": "games played those seasons (Sleeper)", "sample": f"{len(kept[:3])} seasons"}
