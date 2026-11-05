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
"""

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
        row = sleeper.season_stats("nfl", season, kind).get(sid)
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
    theirs = float(published["value"])
    ours = float(f["value"])
    if f["stat"] == "success_rate" and theirs <= 1.0 < ours:
        theirs *= 100                       # they publish a share, we show a percent
    f["check_value"] = theirs
    # Agree at least to the precision we show on air, and to one more decimal
    # when the source publishes that much (muffed shows some stats to 2 places).
    published_decimals = len(repr(theirs).split(".")[1]) if "." in repr(theirs) else 0
    places = max(f["decimals"], min(f["decimals"] + 1, published_decimals))
    if round(ours, places) == round(theirs, places):
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


def _check_one(f: dict) -> dict:
    """Check one fact. If the check itself fails (a source is down), drop the fact."""
    try:
        return _check(f)
    except Exception as problem:
        f.update(status="dropped", note=f"the check couldn't run ({type(problem).__name__}: {problem}), so it's left out")
        return f


def _check(f: dict) -> dict:
    if f["status"] in ("dropped", "trusted"):
        return f
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
