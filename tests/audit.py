"""Hallucination audit: an independent, stricter reviewer reads finished scripts and lists
every real-world claim, marking each supported by the checked fact pack or not.

It uses a different, stronger model (Opus) than the show's own checker (Sonnet), so the
two don't share blind spots. It costs about 10-20 cents a script.

Run: .venv/bin/python tests/audit.py runs/<folder> [runs/<folder> ...]
     .venv/bin/python tests/audit.py --latest 8      (the 8 newest runs)"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import anthropic                       # noqa: E402
from dotenv import load_dotenv         # noqa: E402

AUDIT_MODEL = "claude-opus-5-5"
PROJECT = Path(__file__).resolve().parent.parent

RULES = """You audit a sports debate script for factual errors before it airs. You get the
script and the fact pack: the ONLY facts that were verified. Your job is to find anything a
viewer could take as a statement about the real world that the fact pack does not support.

List EVERY real-world claim in every line (callers and the moderator too), including:
numbers; a player's team, position, or role (starter, rookie, veteran); injuries; awards,
titles, and honors; records and standings; rankings and superlatives ("leads the league",
"best defense", "first in the West"); comparisons ("more than", "nearly double", "same as");
game results, dates, opponents, home or away; who coaches whom; draft position; trades;
streaks; "last season" vs "this season" scope.

For each claim give a verdict:
- SUPPORTED: a fact in the pack states it, or it follows by simple, correct arithmetic or
  comparison from facts in the pack (cite the fact IDs). The scope must match (a 2025 number
  said as "this season" is NOT supported when this season is 2026).
- UNSUPPORTED: no fact backs it, and it could be false.
- CONTRADICTED: the fact pack says something different.
Do NOT list: opinions, predictions, metaphors, how a player "looks" to a host, arguments,
or the hosts' own fictional careers and lives. Common general knowledge that is timeless
and certain (what a stat means, how many teams make the playoffs) is SUPPORTED.
Be strict and literal. When unsure whether a claim is supported, say UNSUPPORTED."""

SCHEMA = {"type": "object", "properties": {"claims": {"type": "array", "items": {"type": "object", "properties": {
    "line": {"type": "integer"}, "speaker": {"type": "string"}, "claim": {"type": "string"},
    "verdict": {"type": "string", "enum": ["SUPPORTED", "UNSUPPORTED", "CONTRADICTED"]},
    "facts": {"type": "array", "items": {"type": "string"}}, "why": {"type": "string"}},
    "required": ["line", "speaker", "claim", "verdict", "facts", "why"], "additionalProperties": False}}},
    "required": ["claims"], "additionalProperties": False}

KEEP = ("id", "league", "subject", "label", "say", "scope", "sample", "rank", "as_of", "definition")


def audit(run: Path, client) -> dict:
    script = json.loads((run / "script.json").read_text())
    facts = json.loads((run / "fact_pack.json").read_text())
    pack = [{k: f[k] for k in KEEP if f.get(k) not in (None, "")} for f in facts]
    text = "\n".join(f"{l['line']}. {l['speaker']}: {l['text']}" for l in script["lines"])
    from pipeline import sleeper
    nfl, nba = int(sleeper.state("nfl")["season"]), int(sleeper.state("nba")["season"])
    when = (f"The script aired on {script['meta']['created'][:10]}. Current seasons: NFL {nfl}, "
            f"NBA {nba}-{str(nba + 1)[-2:]}.")
    with client.messages.stream(
        model=AUDIT_MODEL, max_tokens=16000, thinking={"type": "adaptive"},
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=RULES,
        messages=[{"role": "user", "content": f"Topic: {script['topic']}\n{when}\n\nFact pack:\n"
                   f"{json.dumps(pack, ensure_ascii=False)}\n\nScript:\n{text}"}],
    ) as stream:
        reply = stream.get_final_message()
    claims = json.loads(next(b.text for b in reply.content if b.type == "text"))["claims"]
    return {"run": run.name, "topic": script["topic"], "claims": claims}


def main():
    load_dotenv(PROJECT / ".env")
    client = anthropic.Anthropic()
    args = sys.argv[1:]
    if args[:1] == ["--latest"]:
        runs = sorted(d for d in (PROJECT / "runs").iterdir() if (d / "script.json").exists())[-int(args[1]):]
    else:
        runs = [PROJECT / a if not Path(a).is_absolute() else Path(a) for a in args]
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda r: audit(r, client), runs))
    total = bad = 0
    for r in results:
        problems = [c for c in r["claims"] if c["verdict"] != "SUPPORTED"]
        total += len(r["claims"])
        bad += len(problems)
        print(f"\n{r['topic']}  ({r['run']}): {len(r['claims'])} claims, {len(problems)} not supported")
        for c in problems:
            print(f"  {c['verdict']:12s} line {c['line']} {c['speaker']}: {c['claim']}\n               -> {c['why']}")
    print(f"\nTOTAL: {total} claims, {bad} not supported ({100 * bad / max(total, 1):.1f}%)")
    (PROJECT / "runs" / "last_audit.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
