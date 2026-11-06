"""Accuracy tests for the data sources. Run before a demo, or any time a number looks off:

    .venv/bin/python tests/accuracy.py

It checks that the two NFL stat sources still agree, that advanced stats still
match muffed.ai, and that rosters agree. Nothing here costs API credits."""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import polars as pl                                       # noqa: E402
from pipeline import catalog, muffed, nflv, players, sleeper, verify   # noqa: E402

FAILS = []


def report(name: str, ok: int, total: int, floor: float) -> None:
    rate = 100 * ok / max(1, total)
    flag = "PASS" if rate >= floor else "FAIL"
    if flag == "FAIL":
        FAILS.append(name)
    print(f"[{flag}] {name}: {ok}/{total} ({rate:.1f}%, needs {floor}%)")


def stats_agree(season: int) -> None:
    """Every stat on the catalog's two-source list, nflverse vs Sleeper, one season."""
    g2s = {p["gsis_id"].strip(): pid for pid, p in sleeper.players("nfl").items() if p.get("gsis_id")}
    df = nflv.player_stats_by_season().filter((pl.col("season") == season) & (pl.col("season_type") == "REG"))
    sl = sleeper.season_stats("nfl", season)
    pairs = [(v[0], v[1]) for k, v in catalog.NFL_COUNTS.items() if v[0] and k != "games"]
    checked = matched = 0
    for r in df.iter_rows(named=True):
        sid = g2s.get(r["player_id"])
        if not sid or sid not in sl:
            continue
        for col, key in pairs:
            a, b = r[col] or 0, sl[sid].get(key) or 0
            if a == 0 and b == 0:
                continue
            checked += 1
            matched += abs(a - b) < 0.01
    report(f"NFL stats agree, {season} (nflverse vs Sleeper)", matched, checked, 97.0)


def advanced_match(season: int) -> None:
    """EPA per dropback for every QB muffed.ai ranks, ours vs theirs."""
    muffed._connect()
    reply = muffed._rpc("tools/call", {"name": "query_stat_leaders", "arguments": {
        "metric": "qb_epa.epa_per_dropback", "season": season, "limit": 25}})
    import json
    rows = []
    for block in reply.get("content", []):
        try:
            rows = json.loads(block["text"]).get("rows", [])
            break
        except (ValueError, KeyError, AttributeError):
            continue
    ok = 0
    for row in rows:
        card = {"name": row["entity_key"], "key": "test", "gsis_id": row["gsis_id"]}
        fact = catalog.nfl_advanced(card, "epa_per_dropback", season)
        ok += fact.get("value") is not None and round(fact["value"], 4) == round(row["value"], 4)
    report(f"EPA per dropback matches muffed.ai, {season}", ok, len(rows), 100.0)


def rosters_agree() -> None:
    season = int(sleeper.state("nfl")["season"])
    ro = nflv.rosters_weekly(season)
    ro = ro.filter((pl.col("week") == ro["week"].max()) & (pl.col("status") == "ACT"))
    sp = sleeper.players("nfl")
    ok = total = 0
    for r in ro.iter_rows(named=True):
        sid = str(r.get("sleeper_id") or "")
        if sid not in sp:
            continue
        total += 1
        ok += catalog.NFLVERSE_TEAM.get(sp[sid].get("team"), sp[sid].get("team")) == r["team"]
    report(f"NFL rosters agree, {season} latest week (nflverse vs Sleeper)", ok, total, 98.0)


def spot_checks() -> None:
    """Known facts that must pass, and known ones that must be rejected."""
    m = players.find("Patrick Mahomes", "nfl")["matches"][0]
    facts, _ = verify.check_all(catalog.get(m, "passing_yards", {"season": 2018}) +
                                catalog.get(players.find("Tom Brady", "nfl")["matches"][0], "passing_yards", {}))
    got = {(f["subject"], f["scope"]): f["say"] for f in facts}
    ok = got.get(("Patrick Mahomes", "2018 regular season")) == "5,097" and not any(s == "Tom Brady" for s, _ in got)
    report("Spot checks (Mahomes 2018 = 5,097 passes; Brady career before 2009 is rejected)", int(ok), 1, 100.0)


def team_stats_match(season: int) -> None:
    """Team stats calculated from nflverse vs muffed.ai's published numbers, six teams
    (kept small: muffed asks for no bulk requests). One red-zone miss is expected."""
    ok = total = 0
    for team in ("NE", "GB", "KC", "DET", "BUF", "PHI"):
        for stat in catalog.NFL_TEAM_STATS:
            f = verify._check_one(catalog.nfl_team_stat(team, stat, season))
            if "can't be compared yet" in (f.get("note") or ""):
                continue                      # the two sources are a week apart; not a disagreement
            total += 1
            ok += f["status"] == "verified"
    report(f"NFL team stats match muffed.ai, {season} (6 teams)", ok, total, 95.0)


if __name__ == "__main__":
    current = int(sleeper.state("nfl")["season"])
    stats_agree(current - 1)
    stats_agree(current)
    advanced_match(current - 1)
    team_stats_match(current)
    rosters_agree()
    spot_checks()
    print("\nAll good." if not FAILS else f"\n{len(FAILS)} check(s) failed: {FAILS}. Look before going on air.")
    sys.exit(1 if FAILS else 0)
