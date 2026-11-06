"""Is the judge fair and consistent, and is a blind judge needed at all?

On recent finished scripts, compares:
  A. the blind judge, three times (host labels shuffled each time): is the winner stable?
  B. the same judge with real names showing: do names change the result?
  C. Hal deciding in character (names showing, no rubric), twice: is he stable, and does
     he agree with the judge?
and counts how often each host wins, to spot a scoring system that favors one style.

Run: .venv/bin/python tests/judge_test.py [number of recent runs, default 10]
Costs about 30-50 cents per script (six judging calls)."""

import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import anthropic                       # noqa: E402
from dotenv import load_dotenv         # noqa: E402

from pipeline import judge, verify     # noqa: E402

PROJECT = Path(__file__).resolve().parent.parent
HAL_ONLY = """You are Hal Brennan, the moderator of Sideline (your bible is below). The debate is
over. Decide, fairly and objectively, which host made the most persuasive case. Return only
the winner: royce, deacon, or lonnie."""
HAL_SCHEMA = {"type": "object", "properties": {"winner": {"type": "string", "enum": list(judge.HOSTS)},
              "why": {"type": "string"}}, "required": ["winner", "why"], "additionalProperties": False}


def host_lines(script: dict) -> list[dict]:
    """The debate up to the final answers (drops any old wrap-up by Hal)."""
    lines = script["lines"]
    last_host = max(i for i, l in enumerate(lines) if l["speaker"] in judge.HOSTS)
    return lines[: last_host + 1]


def named(lines, seed=None):
    """No blinding: real names, real speakers."""
    label = {h: h.capitalize() for h in judge.HOSTS}
    return [{"line": l["line"], "who": label.get(l["speaker"], "Moderator" if l["speaker"] == "hal" else "Caller"),
             "text": l["text"], "facts": l.get("facts", []), "argument": l.get("argument")} for l in lines], label


def hal_decides(lines, pack, topic, client):
    script = "\n".join(f"{l['line']}. {l['speaker_name']}: {l['text']}" for l in lines)
    hal = (PROJECT / "characters" / "moderator.md").read_text()
    reply = client.messages.create(
        model=judge.JUDGE_MODEL, max_tokens=4000, system=HAL_ONLY + "\n\n" + hal,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": HAL_SCHEMA}},
        messages=[{"role": "user", "content": f"Question: {topic}\n\nFact pack:\n{json.dumps(pack)}\n\nDebate:\n{script}"}])
    return json.loads(next(b.text for b in reply.content if b.type == "text"))["winner"]


def one(run: Path, client) -> dict:
    script = json.loads((run / "script.json").read_text())
    pack = verify.pack_for_writer(json.loads((run / "fact_pack.json").read_text()))
    lines = host_lines(script)
    blind = [judge.judge(lines, pack, script["topic"], client, seed=s) for s in (1, 2, 3)]
    original = judge.blind
    judge.blind = named
    try:
        with_names = judge.judge(lines, pack, script["topic"], client)
    finally:
        judge.blind = original
    hal = [hal_decides(lines, pack, script["topic"], client) for _ in range(2)]
    return {"topic": script["topic"], "blind": [r["winner"] for r in blind],
            "blind_scores": [{h: v["score"] for h, v in r["hosts"].items()} for r in blind],
            "named": with_names["winner"], "named_scores": {h: v["score"] for h, v in with_names["hosts"].items()},
            "hal": hal}


def main():
    load_dotenv(PROJECT / ".env")
    client = anthropic.Anthropic()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    runs = sorted(d for d in (PROJECT / "runs").iterdir() if (d / "script.json").exists())[-n:]
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda r: one(r, client), runs))
    stable = named_same = hal_stable = hal_agree = 0
    wins = Counter()
    spread = []
    for r in results:
        b = r["blind"]
        majority = Counter(b).most_common(1)[0][0]
        wins[majority] += 1
        stable += len(set(b)) == 1
        named_same += r["named"] == majority
        hal_stable += r["hal"][0] == r["hal"][1]
        hal_agree += r["hal"][0] == majority
        for h in judge.HOSTS:
            vals = [s[h] for s in r["blind_scores"] if s.get(h) is not None]
            if len(vals) > 1:
                spread.append(max(vals) - min(vals))
        print(f"{r['topic'][:60]:60s} blind {b}  named {r['named']}  Hal {r['hal']}")
    k = len(results)
    print(f"\nBlind judge picked the same winner all 3 times: {stable}/{k}")
    print(f"Average spread in a host's score across the 3 blind runs: {sum(spread) / max(len(spread), 1):.1f} points")
    print(f"Judge with names showing agreed with the blind majority: {named_same}/{k}")
    print(f"Hal (no rubric) picked the same winner twice: {hal_stable}/{k}; agreed with the blind judge: {hal_agree}/{k}")
    print(f"Wins (blind majority): {dict(wins)}")
    (PROJECT / "runs" / "last_judge_test.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
