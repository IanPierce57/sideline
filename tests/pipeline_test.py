"""Speed and coverage test for the fact pipeline: topic check, research, checking,
and the replacement round, on a varied set of topics. No script is written, so it
costs only a few cents per topic (Haiku topic check + Sonnet research).

Run: .venv/bin/python tests/pipeline_test.py            (all topics)
     .venv/bin/python tests/pipeline_test.py "topic"    (one topic)

For each topic it prints how long each step took, how many facts were confirmed,
and what the slowest kinds of check were. Targets: at least 12 confirmed facts,
and the whole pipeline (before writing) under 60 seconds."""

import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import anthropic                              # noqa: E402
from dotenv import load_dotenv                # noqa: E402

from pipeline import catalog, research, verify  # noqa: E402

TOPICS = [
    "Is Patrick Mahomes still the best QB in the NFL?",              # NFL QB debate
    "Who will win between the Patriots and Packers this Sunday?",    # NFL game
    "Is Micah Parsons the best pass rusher in football?",            # defense
    "Should the Bears trade for Jonathan Taylor?",                   # buy or sell
    "Is Shai Gilgeous-Alexander a better player than Nikola Jokic?",  # NBA
    "Are the Lions a real Super Bowl contender this season?",        # NFL team
]
MIN_FACTS, MAX_SECONDS = 12, 60

KIND = lambda f: ("honor" if f.get("honor") else "team stat" if f["stat"] in catalog.NFL_TEAM_STATS else  # noqa: E731
                  "advanced" if f["stat"] in catalog.NFL_ADVANCED else f["stat"] if f["stat"] in
                  ("current_team", "team_record", "qb_playoff_record", "recent_results", "qb_last_start") else
                  "nba" if f.get("league") == "NBA" else "nfl count")


def run(topic: str, client) -> dict:
    timing = {}
    t = time.time()
    check = research.check_topic(topic, client)
    timing["topic"] = time.time() - t
    if not check["ok"]:
        return {"topic": topic, "error": check.get("reason") or check.get("confirm")}
    t = time.time()
    candidates = catalog.game_pack(check["game"]) if check.get("game") else []
    candidates += research.research(topic, check["format"], check["players"], client)
    timing["research"] = time.time() - t

    slow = defaultdict(float)                 # seconds spent per kind of check
    original = verify._check_one

    def timed(f):
        s = time.time()
        out = original(f)
        slow[KIND(f)] += time.time() - s
        return out
    verify._check_one = timed
    t = time.time()
    facts, log = verify.check_all(candidates)
    timing["verify"] = time.time() - t
    crossed = [r for r in log if not r["reason"].startswith("kept")]
    if crossed:
        t = time.time()
        listing = "\n".join(f"- {r['subject']}: {r['stat']} ({r.get('scope')}): {r['reason']}" for r in crossed)
        more = research.research(topic, check["format"], check["players"], client, rounds=2, follow_up=(
            "These stats couldn't be confirmed, so they were crossed off:\n" + listing +
            "\n\nFind checkable replacements. If nothing fits, reply \"done\"."))
        more_facts, _ = verify.check_all(more) if more else ([], [])
        facts = verify.merge(facts, more_facts)
        timing["replace"] = time.time() - t
    verify._check_one = original
    return {"topic": topic, "timing": timing, "found": len(candidates), "facts": len(facts),
            "crossed": crossed, "slow": dict(slow)}


def main():
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    client = anthropic.Anthropic()
    topics = sys.argv[1:] or TOPICS
    problems = []
    for topic in topics:
        r = run(topic, client)
        if "error" in r:
            print(f"\n{topic}\n  TURNED AWAY: {r['error']}")
            problems.append(topic)
            continue
        total = sum(r["timing"].values())
        steps = ", ".join(f"{k} {v:.0f}s" for k, v in r["timing"].items())
        slow = ", ".join(f"{k} {v:.0f}s" for k, v in sorted(r["slow"].items(), key=lambda x: -x[1])[:3])
        print(f"\n{topic}\n  {total:.0f}s total ({steps})\n  {r['facts']} confirmed of {r['found']} pulled; "
              f"{len(r['crossed'])} crossed off\n  slowest checks: {slow}")
        for c in r["crossed"][:6]:
            print(f"    x {c['subject']}: {c['stat']} ({c.get('scope')}): {str(c['reason'])[:90]}")
        if r["facts"] < MIN_FACTS or total > MAX_SECONDS:
            problems.append(topic)
    print("\nAll good." if not problems else f"\nNeeds work ({len(problems)}): {problems}")


if __name__ == "__main__":
    main()
