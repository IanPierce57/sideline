"""The checker: every candidate fact is fetched again from a second source and
compared, by code, before it can reach the script. Only facts that pass go into
the fact pack; everything else goes in the rejection log with the reason.

Rules (BRIEF.md "Facts and data", decided Nov 4, 2026):
  NFL basic stats    must match Sleeper. If they disagree, Sleeper's number is used
                     and the disagreement is logged. Seasons before 2009 can't be
                     checked (Sleeper starts in 2009), so those facts are dropped.
  NFL advanced stats must match muffed.ai's published value under the same
                     definition, to one decimal place more than we show. Otherwise dropped.
  NFL team records   must match muffed.ai exactly. Otherwise dropped.
  NBA stats, tackles Sleeper alone (trusted).
  Current team       NFL: nflverse roster and Sleeper; Sleeper wins a disagreement.
  NFL team stats     must match muffed.ai's published value, through the same week, or dropped.
                     The league rank is shown only if ours (all 32 teams) matches muffed's.
  Game results       each final score must match Sleeper's weekly team numbers, or dropped.
  Starting QB        nflverse's starter must be listed as a starter that week by Sleeper, or dropped.
  The game itself    confirmed on both schedules before the segment starts (games.py).
  Injuries           Sleeper (trusted on its own).
"""

import re
from concurrent.futures import ThreadPoolExecutor

import polars as pl

from . import catalog, muffed, nflv, sleeper, wiki


def _check_nfl_count(f: dict) -> dict:
    seasons = f["seasons"]
    if min(seasons) < catalog.SLEEPER_NFL_FIRST_SEASON:
        early = [s for s in seasons if s < catalog.SLEEPER_NFL_FIRST_SEASON]
        f.update(status="dropped", note=f"can't be double-checked: Sleeper's NFL stats start in 2009, and this includes {early[0]}-{early[-1]}")
        return f
    kind = "post" if f["season_type"] == "POST" else "regular"
    sid = f["subject_key"].split(":", 1)[1]
    total = 0.0
    for season in seasons:
        row = catalog.sleeper_season(season, kind).get(sid)
        if row is None:
            f.update(status="dropped", note=f"Sleeper has no {season} {kind}-season record for him to check against")
            return f
        total += row.get(f["sleeper_key"]) or 0
    total = int(total) if float(total).is_integer() else total
    f["checked_against"], f["check_value"] = "Sleeper", total
    if abs(total - f["value"]) < 0.01:
        f["status"] = "verified"
    else:
        f.update(status="verified_sleeper_used",
                 note=f"nflverse said {f['say']}, Sleeper said {catalog.say(total, 0 if isinstance(total, int) else 1)}; using Sleeper's number",
                 value=total, say=catalog.say(total, 0 if isinstance(total, int) else 1))
    return f


def _check_advanced(f: dict) -> dict:
    published = muffed.metric(f["subject"], f["muffed_metric"], f["season"], gsis_id=f.get("gsis_id"))
    f["checked_against"] = "muffed.ai"
    if not published or published.get("value") is None:
        f.update(status="dropped", note="muffed.ai doesn't publish this for him that season (often a too-small sample), so it can't be cross-referenced")
        return f
    pw = published.get("through_week")
    if pw and f["season"] == int(sleeper.state("nfl")["season"]) and f.get("week") and pw != f["week"]:
        # The sources are a week apart: recalculate ours through muffed's week.
        card = {"name": f["subject"], "key": f["subject_key"], "gsis_id": f.get("gsis_id")}
        redo = catalog.nfl_advanced(card, f["stat"], f["season"], through_week=pw)
        if redo["status"] == "dropped":
            f.update(status="dropped", note=redo["note"])
            return f
        f.update({k: redo[k] for k in ("value", "say", "sample", "as_of", "week")})
    theirs = float(published["value"])
    ours = float(f["value"])
    if f["stat"] == "success_rate" and theirs <= 1.0 < ours:
        theirs *= 100                       # they publish a share, we show a percent
    f["check_value"] = theirs
    # Agree at least to the precision we show on air, and to one more decimal
    # when the source publishes that much (muffed shows some stats to 2 places).
    published_decimals = len(repr(theirs).split(".")[1]) if "." in repr(theirs) else 0
    # Same number if ours is within half a unit of their last published decimal.
    # (Re-rounding a value that sits exactly halfway can tip either way in a computer.)
    if abs(ours - theirs) <= 0.5 * 10 ** -published_decimals + 1e-9:
        if published_decimals < f["decimals"]:      # they publish fewer decimals: show only what's confirmed
            f["decimals"] = published_decimals
            shown = catalog.say(ours, published_decimals, pct=f["stat"] == "success_rate")
            f["say"] = ("+" + shown) if f["say"].startswith("+") else shown
        f["status"] = "verified"
        if published.get("rank") and published.get("population"):
            f["rank"] = f"ranked {published['rank']} of {published['population']} qualifying players (muffed.ai)"
        f["credit"] = muffed.CREDIT
    else:
        f.update(status="dropped", note=f"ours {ours:.4f} vs muffed.ai {theirs:.4f}: the numbers don't match, so it's left out")
    return f


def _check_team_record(f: dict) -> dict:
    v = f["value"]
    got = {k: muffed.metric(f["team_code"], f"team_records.{k}", f["season"], kind="team") for k in ("wins", "losses", "ties")}
    f["checked_against"] = "muffed.ai"
    if not got["wins"] or got["wins"].get("value") is None:
        f.update(status="dropped", note="muffed.ai has no record for this team and season")
        return f
    pw = got["wins"].get("through_week")
    if pw and f["season"] == int(sleeper.state("nfl")["season"]) and f.get("week") and pw != f["week"]:
        redo = catalog.nfl_team_record(f["subject_key"].split(":", 1)[1], f["season"], through_week=pw)
        f.update({k: redo[k] for k in ("value", "say", "sample", "as_of", "week")})
        v = f["value"]
    theirs = {k: int((got[k] or {}).get("value") or 0) for k in got}
    f["check_value"] = theirs
    if theirs == v:
        f["status"] = "verified"
    else:
        f.update(status="dropped", note=f"ours {v} vs muffed.ai {theirs}")
    return f


def _check_current_team(f: dict) -> dict:
    if f["league"] != "NFL" or not f.get("gsis_id"):
        f.update(status="trusted", checked_against="Sleeper (trusted on its own)")
        return f
    season = int(sleeper.state("nfl")["season"])
    ro = nflv.rosters_weekly(season)
    ro = ro.filter((pl.col("gsis_id") == f["gsis_id"]) & (pl.col("week") == ro["week"].max()))
    theirs = ro["team"][0] if ro.height else None
    theirs = {"LA": "LAR"}.get(theirs, theirs)
    f["checked_against"], f["check_value"] = "nflverse roster", theirs
    if theirs == f["value"]:
        f["status"] = "verified"
    else:
        f.update(status="verified_sleeper_used",
                 note=f"nflverse's latest roster says {theirs or 'not on a team'}; Sleeper (more current) says {f['value'] or 'no team'}")
    return f


def _check_honor(f: dict) -> dict:
    """Wikipedia is trusted for career honors (decided Nov 4, 2026). Where a second
    source exists it's still checked: Super Bowl rings against nflverse's Super Bowl
    winners' rosters, major awards against Wikidata. If one disagrees, Wikipedia's
    number is used and the disagreement is logged, like Sleeper for stats."""
    other, theirs = None, None
    if f["honor"] == "sb_champion" and f.get("gsis_id"):
        sched = nflv.schedules().filter((pl.col("game_type") == "SB") & pl.col("result").is_not_null())
        winners = {(r["season"], r["home_team"] if r["result"] > 0 else r["away_team"]) for r in sched.iter_rows(named=True)}
        ro = nflv.rosters_all().filter(pl.col("gsis_id") == f["gsis_id"])
        other = "nflverse (Super Bowl winners' rosters)"
        theirs = len({r["season"] for r in ro.iter_rows(named=True) if (r["season"], r["team"]) in winners})
    elif f.get("wikidata") and f.get("qid"):
        other, theirs = "Wikidata", wiki.wikidata_award_count(f["qid"], f["wikidata"])
    if theirs is None:
        f.update(status="trusted", checked_against="Wikipedia (trusted on its own)")
    elif theirs == f["value"]:
        f.update(status="verified", checked_against=other, check_value=theirs)
    else:
        f.update(status="verified_wikipedia_used", checked_against=other, check_value=theirs,
                 note=f"Wikipedia says {f['value']}, {other} says {theirs}; using Wikipedia's")
    return f


def _check_qb_playoff_record(f: dict) -> dict:
    """The wins come from official scores; the starts are checked against Sleeper."""
    if min(f["seasons"]) < catalog.SLEEPER_NFL_FIRST_SEASON:
        f.update(status="dropped", note="includes playoff starts before 2009, which can't be double-checked")
        return f
    sid = f["subject_key"].split(":", 1)[1]
    starts = 0
    for season in f["seasons"]:
        starts += (sleeper.season_stats("nfl", season, "post").get(sid) or {}).get("gs") or 0
    f["checked_against"], f["check_value"] = "Sleeper (playoff starts)", starts
    if int(starts) == f["starts"]:
        f["status"] = "verified"
    else:
        f.update(status="dropped", note=f"nflverse shows {f['starts']} playoff starts, Sleeper {int(starts)}")
    return f


def _check_team_stat(f: dict) -> dict:
    published = muffed.metric(f["team_code"], f["muffed_metric"], f["season"], kind="team")
    f["checked_against"] = "muffed.ai"
    if not published or published.get("value") is None:
        f.update(status="dropped", note="muffed.ai doesn't publish this for that team and season")
        return f
    pw = published.get("through_week")
    if pw and f["season"] == int(sleeper.state("nfl")["season"]) and pw != f["week"]:
        # The sources are a week apart: recalculate ours through muffed's week.
        team = f["subject_key"].split(":", 1)[1]
        redo = catalog.nfl_team_stat(team, f["stat"], f["season"], through_week=pw)
        if redo["status"] == "dropped":
            f.update(status="dropped", note=redo["note"])
            return f
        f.update({k: redo[k] for k in ("value", "say", "sample", "as_of", "week", "our_rank", "teams")})
    raw = repr(float(published["value"]))
    theirs = float(published["value"]) * (100 if f["pct"] else 1)
    published_decimals = max(0, len(raw.split(".")[1].rstrip("0") or "") - (2 if f["pct"] else 0))
    f["check_value"] = theirs
    tolerance = 0.5 * 10 ** -max(published_decimals, f["decimals"]) + 1e-9
    if abs(float(f["value"]) - theirs) > tolerance:
        f.update(status="dropped", note=f"ours {f['value']:.4f} vs muffed.ai {theirs:.4f}: the numbers don't match, so it's left out")
        return f
    f.update(status="verified", credit=muffed.CREDIT)
    if published.get("rank") == f.get("our_rank"):
        f["rank"] = f"{catalog._ordinal(f['our_rank'])} of {f['teams']} teams (1st is best)"
    return f


def _check_results(f: dict) -> dict:
    """Every final score must match Sleeper: each team's points allowed is the other's score."""
    f["checked_against"] = "Sleeper (weekly team scoring)"
    for g in f["games"]:
        week = sleeper.week_stats("nfl", f["season"], g["week"])
        allowed_by_opp = (week.get(g["opp"]) or {}).get("pts_allow")
        allowed_by_us = (week.get(g["team"]) or {}).get("pts_allow")
        if allowed_by_opp != g["ours"] or allowed_by_us != g["theirs"]:
            f.update(status="dropped", note=f"Week {g['week']} score: nflverse {g['ours']}-{g['theirs']}, Sleeper "
                                            f"{allowed_by_opp}-{allowed_by_us}; they don't match")
            return f
    f["status"] = "verified"
    return f


def _check_qb_start(f: dict) -> dict:
    gsis_to_sleeper = {g: s for s, g in nflv.sleeper_to_gsis().items()}
    for pid, p in sleeper.players("nfl").items():
        if p.get("gsis_id"):
            gsis_to_sleeper[p["gsis_id"].strip()] = pid
    sid = gsis_to_sleeper.get(f.get("qb_gsis"))
    started = (sleeper.week_stats("nfl", f["season"], f["week"]).get(sid) or {}).get("gs") if sid else None
    f.update(checked_against="Sleeper (games started)", check_value=started)
    if started == 1:
        f["status"] = "verified"
    else:
        f.update(status="dropped", note=f"Sleeper doesn't list {f.get('qb_name')} as the Week {f.get('week')} starter")
    return f


def _predraft(f: dict) -> dict:
    """The pre-draft measurables table on his Wikipedia page, as {field: text}."""
    page = wiki.find_page(f["subject"], "NFL", f.get("position"))
    m = re.search(r"\{\{\s*nfl predraft(.*?)\n\}\}|\{\{\s*nfl predraft(.*?)\}\}", page["text"], re.S | re.I) if page else None
    body = (m.group(1) or m.group(2)) if m else ""
    return {k.strip().lower(): re.sub(r"<ref.*", "", v).strip() for k, v in re.findall(r"\|\s*([a-z ]+?)\s*=\s*([^|\n]*)", body)}


def _number(text: str):
    """'10 1/8' -> 10.125; '4.75' -> 4.75; '' -> None."""
    parts = text.split()
    try:
        total = float(parts[0]) if parts else None
        if len(parts) > 1 and "/" in parts[1]:
            a, b = parts[1].split("/")
            total += float(a) / float(b)
        return total
    except (ValueError, ZeroDivisionError):
        return None


def _check_coach(f: dict) -> dict:
    page = wiki._page(f["team_name"])
    m = re.search(r"\|\s*(?:head[ _]coach|coach)\s*=([^\n]*)", page["text"]) if page else None
    theirs = wiki._clean(m.group(1)) if m else None
    f.update(checked_against="Wikipedia (team page)", check_value=theirs)
    if theirs and theirs.lower() == (f["value"] or "").lower():
        f["status"] = "verified"
    else:
        f.update(status="dropped", note=f"nflverse says {f['value']}, Wikipedia says {theirs or 'nothing'}")
    return f


def _check_height(f: dict) -> dict:
    """Sleeper's listed height (trusted), as long as the pre-draft height is within an inch:
    a bigger gap means a mix-up between two players."""
    pre = _predraft(f)
    ft, inch = _number(pre.get("height ft", "")), _number(pre.get("height in", ""))
    if ft is None:
        f.update(status="trusted", checked_against="Sleeper (trusted on its own)")
        return f
    theirs = ft * 12 + (inch or 0)
    f.update(checked_against="Wikipedia (pre-draft height)", check_value=theirs)
    if abs(theirs - f["value"]) <= 1.0:
        f["status"] = "verified"
    else:
        f.update(status="dropped", note=f"Sleeper lists {f['say']}, his pre-draft height was {theirs:g} inches")
    return f


def _check_combine(f: dict) -> dict:
    _, field, _, _ = catalog.COMBINE[f["combine_key"]]
    pre = _predraft(f)
    if field == "broad":
        ft, inch = _number(pre.get("broad ft", "")), _number(pre.get("broad in", ""))
        theirs = ft * 12 + (inch or 0) if ft is not None else None
    else:
        theirs = _number(pre.get(field, ""))
    f.update(checked_against="Wikipedia (pre-draft measurables)", check_value=theirs)
    if theirs is None:
        f.update(status="dropped", note="his Wikipedia page doesn't list it, so it can't be cross-checked")
    elif abs(theirs - f["value"]) < 0.011:
        f["status"] = "verified"
    else:
        f.update(status="dropped", note=f"nflverse {f['value']:g} vs Wikipedia {theirs:g} (maybe a pro-day number)")
    return f


def _check_draft(f: dict) -> dict:
    page = wiki.find_page(f["subject"], "NFL", f.get("position"))
    info = {k.replace("_", ""): wiki._clean(v) for k, v in
            re.findall(r"\|\s*(draft_?year|draft_?round|draft_?pick|undrafted_?year)\s*=([^\n]*)", page["text"])} if page else {}
    f["checked_against"] = "Wikipedia (infobox)"
    if f.get("undrafted"):
        ok = bool(info.get("undraftedyear")) and not info.get("draftyear")
    else:
        got = tuple(int(re.sub(r"\D", "", info.get(k, "")) or 0) for k in ("draftyear", "draftround", "draftpick"))
        f["check_value"] = got
        ok = got == (f["draft_year"], f["draft_round"], f["draft_pick"])
    if ok:
        f["status"] = "verified"
    else:
        f.update(status="dropped", note=f"his Wikipedia page says {info or 'nothing about the draft'}")
    return f


def _check_one(f: dict) -> dict:
    """Check one fact. If the check itself fails (a source is down), drop the fact."""
    try:
        return _check(f)
    except Exception as problem:
        f.update(status="dropped", note=f"the check couldn't run ({type(problem).__name__}: {problem}), so it's left out")
        return f


def _check(f: dict) -> dict:
    if f["status"] in ("dropped", "trusted", "verified"):
        return f
    if f["stat"] == "head_coach":
        return _check_coach(f)
    if f["stat"] == "height":
        return _check_height(f)
    if f.get("combine_key"):
        return _check_combine(f)
    if f["stat"] == "draft":
        return _check_draft(f)
    if f["stat"] in catalog.NFL_TEAM_STATS:
        return _check_team_stat(f)
    if f["stat"] in ("recent_results", "head_to_head"):
        return _check_results(f)
    if f["stat"] == "qb_last_start":
        return _check_qb_start(f)
    if f.get("honor"):
        return _check_honor(f)
    if f["stat"] == "qb_playoff_record":
        return _check_qb_playoff_record(f)
    if f["stat"] == "current_team":
        return _check_current_team(f)
    if f["stat"] == "team_record":
        return _check_team_record(f)
    if f["stat"] in catalog.NFL_ADVANCED:
        return _check_advanced(f)
    if f.get("depends_on"):
        return f                       # rates are settled after their parts
    return _check_nfl_count(f)


def _settle_rate(f: dict) -> dict:
    parts = f.pop("depends_on")
    bad = [p for p in parts if not p["status"].startswith(("verified", "trusted"))]
    if bad:
        f.update(status="dropped", note=f"built from a number that failed its check ({bad[0].get('label')}: {bad[0].get('note')})")
        return f
    mult, dec = f.pop("rate")
    top, bottom = parts[0]["value"], parts[1]["value"]
    if not bottom:
        f.update(status="dropped", note="nothing to divide by")
        return f
    value = round(mult * top / bottom, dec)
    f.update(value=value, say=catalog.say(value, dec, pct=f.pop("pct")), status="verified",
             checked_against="Sleeper (both parts)",
             definition=f"{f['definition']} ({parts[0]['say']} {parts[0]['label']} / {parts[1]['say']} {parts[1]['label']})")
    return f


def check_all(candidates: list[dict], progress=lambda *a: None) -> tuple[list[dict], list[dict]]:
    """Check every candidate. Returns (fact_pack, rejection_log)."""
    simple = [f for f in candidates if not f.get("depends_on")]
    parts = [p for f in candidates if f.get("depends_on") for p in f["depends_on"]]
    with ThreadPoolExecutor(max_workers=6) as pool:
        for f in pool.map(_check_one, simple + parts):
            progress("checked", f)
    for f in candidates:
        if f.get("depends_on"):
            _settle_rate(f)
            progress("checked", f)

    passed, rejected, seen = [], [], set()
    for f in candidates:
        if f["status"].startswith(("verified", "trusted")):
            key = (f.get("subject_key"), f["stat"], f.get("scope"))
            if key in seen:
                continue                 # the same fact asked for twice
            seen.add(key)
            passed.append(f)
        else:
            rejected.append({"subject": f.get("subject"), "stat": f.get("label") or f.get("stat"),
                             "scope": f.get("scope"), "what_we_found": f.get("say"), "reason": f.get("note")})
        if f["status"] in ("verified_sleeper_used", "verified_wikipedia_used"):
            rejected.append({"subject": f["subject"], "stat": f.get("label"), "scope": f.get("scope"),
                             "what_we_found": f.get("say"), "reason": f"kept, but the sources disagreed: {f['note']}"})
    for i, f in enumerate(passed, start=1):
        f["id"] = f"F{i}"
    return passed, rejected


def pack_for_writer(facts: list[dict]) -> list[dict]:
    """The fields the script writer needs, nothing else."""
    keep = ("id", "league", "subject", "label", "say", "scope", "sample", "definition", "rank", "as_of", "source")
    return [{k: f[k] for k in keep if f.get(k) not in (None, "")} for f in facts]


def merge(facts: list[dict], more: list[dict]) -> list[dict]:
    """Add newly verified facts to the pack, skipping repeats, and renumber F1, F2, ..."""
    seen = {(f.get("subject_key"), f["stat"], f.get("scope")) for f in facts}
    combined = list(facts)
    for f in more:
        key = (f.get("subject_key"), f["stat"], f.get("scope"))
        if key not in seen:
            seen.add(key)
            combined.append(f)
    for i, f in enumerate(combined, start=1):
        f["id"] = f"F{i}"
    return combined
