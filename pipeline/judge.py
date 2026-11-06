"""The judge and Hal's close (BRIEF.md "Scoring"; built Nov 5, 2026).

How a segment is scored, in plain terms:
1. The finished, fact-checked script is made blind: Royce, Deacon, and Lonnie become
   Host 1, 2, and 3 in a random order each time, nicknames included, and bible stage
   directions like "(the pencil stops)" are removed, so the judge can't tell who's who.
2. The judge (Sonnet) rates each numbered argument 1 to 5 on five criteria, using the
   written descriptions in RUBRIC, and says which earlier argument it answers, if any.
   That's all the judge decides.
3. Code does the math, the same way every time:
   - argument score = weighted average of the five ratings, times 20 (so 1 -> 20, 5 -> 100).
     Evidence 30%, reasoning 25%, rebuttal 25%, impact 10%, clarity 10%.
   - An argument that answers no one (an opening point) has no rebuttal rating; its
     rebuttal weight is shared out across the other four, so going first isn't punished.
   - Dropped arguments: a point no opponent answers, though an opponent spoke afterward,
     gets +5 (to start; tuned after testing), up to 100.
   - Host score = the average of his arguments (talking more doesn't win).
   - Winner = highest host score. A tie (same score to one decimal) goes to the higher
     average rebuttal rating; if that's tied too, it's a tie. A margin under 2 points is a
     close call, and Hal says so.
   Three blind judges (PANEL) run at the same time, each with the hosts shuffled
   differently, and their ratings are averaged (tested Nov 5, 2026: same winner in 8 of 10
   re-judged scripts, and the 2 that flipped were within 2 points).
4. Hal's close is written only after scoring, so the verdict always matches it.
"""

import json
import random
import re

import anthropic

JUDGE_MODEL = "claude-sonnet-5-5"
CLOSE_MODEL = "claude-sonnet-5-5"
HOSTS = ("royce", "deacon", "lonnie")
NAMES = {"royce": ("Royce Stanhope", "Royce", "Stanhope"), "deacon": ("Deacon Pettiford", "Deacon", "Pettiford", "Deac"),
         "lonnie": ("Lonnie Fairweather", "Lonnie", "Fairweather", "Lon")}
WEIGHTS = {"evidence": 0.30, "reasoning": 0.25, "rebuttal": 0.25, "impact": 0.10, "clarity": 0.10}
DROPPED_BONUS = 5
CLOSE_CALL = 2.0   # a margin under this many points is a close call: Hal says so ("by a hair")

RUBRIC = """An argument is one turn: a host taking the floor and making a point (tagged
[argument N] on its lines). Rate each argument from 1 to 5 on each criterion. Use these descriptions
exactly, so the same argument always gets the same ratings.

EVIDENCE (are the facts relevant, verified, and from a big enough sample?)
  5: Several verified facts (cited fact IDs) that bear directly on the claim, with fair samples.
  3: One relevant verified fact, or facts that are only partly on point or from a small sample.
  1: No verified facts; only opinion, or numbers that don't bear on the claim.
REASONING (does the evidence actually prove the claim?)
  5: The evidence clearly leads to the claim; the comparison is like for like (same season, same scope).
  3: The evidence supports the claim, but there's a gap or an apples-to-oranges comparison.
  1: The claim doesn't follow from what's offered.
REBUTTAL (does it answer an opponent's strongest point directly?)
  Rate only if the argument answers an earlier argument by another host; otherwise null.
  Arguing that the opponent is measuring the wrong thing ("that's not the question; the
  question is...") counts as a direct answer when it explains WHY the opponent's measure
  falls short; a bare change of subject doesn't.
  5: Takes on the opponent's strongest point head-on and shows why it's wrong or doesn't matter.
  3: Answers the opponent, but a weaker point, or only partly.
  1: Claims to answer but talks past the point.
IMPACT (does it show why this matters to the question asked?)
  5: Ties the point straight to the question (who's better, who wins, buy or sell).
  3: Relevant, but the link to the question is left for the listener.
  1: Off the question.
CLARITY (is the claim specific and easy to follow?)
  5: One specific claim, easy to follow on a first listen.
  3: Understandable, but vague or crowded.
  1: Hard to tell what's being claimed.

Volume, insults, and repetition earn nothing: an argument that only repeats an earlier point
by the same host, gets louder, or insults someone gets 1 on every criterion. Summing up the
other hosts' points before making a new one is NOT repetition: rate the new point. Only a turn
that adds nothing new (no new fact, angle, or answer) earns nothing. Judge the
substance, not the personality: a metaphor or a vivid line is neither a plus nor a minus by
itself. Hosts are anonymous; don't guess who they are."""

JUDGE_SCHEMA = {"type": "object", "properties": {"arguments": {"type": "array", "items": {"type": "object", "properties": {
    "argument": {"type": "integer"},
    "answers": {"type": "array", "items": {"type": "integer"},
                "description": "Numbers of earlier arguments by OTHER hosts that this argument directly answers."},
    "evidence": {"type": "integer"}, "reasoning": {"type": "integer"},
    "rebuttal": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
    "impact": {"type": "integer"}, "clarity": {"type": "integer"},
    "note": {"type": "string", "description": "One plain sentence on why."}},
    "required": ["argument", "answers", "evidence", "reasoning", "rebuttal", "impact", "clarity", "note"],
    "additionalProperties": False}}}, "required": ["arguments"], "additionalProperties": False}


# ---------- 1. Blind ----------

def blind(lines: list[dict], seed=None) -> tuple[list[dict], dict]:
    """The script with hosts as Host 1-3 (random order), names and nicknames replaced,
    and opening stage directions removed. Returns (blind lines, {host: label})."""
    order = list(HOSTS)
    random.Random(seed).shuffle(order)
    label = {h: f"Host {i}" for i, h in enumerate(order, start=1)}
    swaps = sorted(((n, label[h]) for h in HOSTS for n in NAMES[h]), key=lambda x: -len(x[0]))
    out = []
    for line in lines:
        text = re.sub(r"^\s*\([^)]*\)\s*", "", line["text"])
        for name, lab in swaps:
            text = re.sub(r"\b" + re.escape(name) + r"\b", lab, text)
        who = label.get(line["speaker"]) or ("Moderator" if line["speaker"] == "hal" else "Caller")
        out.append({"line": line["line"], "who": who, "text": text, "facts": line.get("facts", []),
                    "argument": line.get("argument")})
    return out, label


# ---------- 2. Judge ----------

def _arguments(lines: list[dict]) -> dict:
    """One argument = one turn: each time a host takes the floor (one or more lines in a row)
    and makes a point. A turn of nothing but short reactions ("Hah.") or a final answer,
    which the writer leaves untagged, isn't an argument. Numbered 1, 2, 3... in order.
    Returns {argument number: {"host", "lines": [...]}}."""
    turns, current = [], None
    for line in lines:
        if line["speaker"] not in HOSTS:
            current = None
            continue
        if current and current["host"] == line["speaker"]:
            current["lines"].append(line)
        else:
            current = {"host": line["speaker"], "lines": [line]}
            turns.append(current)
    args = {}
    for t in turns:
        if any(l.get("argument") is not None for l in t["lines"]):
            args[len(args) + 1] = {"host": t["host"], "lines": [l["line"] for l in t["lines"]]}
    return args


def rate(lines: list[dict], pack: list[dict], topic: str, client: anthropic.Anthropic, seed=None) -> tuple[dict, dict]:
    """Ask the judge for ratings. Returns ({argument number: ratings}, {host: label})."""
    blind_lines, label = blind(lines, seed)
    args = _arguments(lines)
    tag = {ln: n for n, a in args.items() for ln in a["lines"]}
    script = "\n".join(f"{l['line']}. {l['who']}" + (f" [argument {tag[l['line']]}]" if l["line"] in tag else "")
                       + f": {l['text']}" + (f"  (cites {', '.join(l['facts'])})" if l["facts"] else "") for l in blind_lines)
    numbers = sorted(args)
    with client.messages.stream(
        model=JUDGE_MODEL, max_tokens=12000, thinking={"type": "adaptive"}, system=RUBRIC,
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": JUDGE_SCHEMA}},
        messages=[{"role": "user", "content": f"Question being debated: {topic}\n\nVerified fact pack:\n"
                   f"{json.dumps(pack, ensure_ascii=False)}\n\nScript (each host line is tagged with its argument "
                   f"number):\n{script}\n\nRate every argument: {', '.join(map(str, numbers))}."}],
    ) as stream:
        reply = stream.get_final_message()
    rows = json.loads(next(b.text for b in reply.content if b.type == "text"))["arguments"]
    out = {}
    for r in rows:
        n = r["argument"]
        if n not in args:
            continue
        # Only real answers count: an earlier argument by a different host.
        r["answers"] = [a for a in r.get("answers", []) if a in args and args[a]["host"] != args[n]["host"]
                        and min(args[a]["lines"]) < max(args[n]["lines"])]
        out[n] = r
    return out, label


def _clamp(x):
    return min(5.0, max(1.0, float(x)))


def argument_score(r: dict) -> float:
    """Weighted 1-5 ratings, scaled to 100. No rebuttal rating: its weight is shared out."""
    parts = {k: _clamp(r[k]) for k in ("evidence", "reasoning", "impact", "clarity")}
    if r.get("rebuttal") is not None and r.get("answers"):
        parts["rebuttal"] = _clamp(r["rebuttal"])
    total_weight = sum(WEIGHTS[k] for k in parts)
    return 20 * sum(WEIGHTS[k] * v for k, v in parts.items()) / total_weight


def tally(lines: list[dict], ratings: dict) -> dict:
    """All the math, in code: argument scores, dropped bonuses, host averages, winner."""
    args = _arguments(lines)
    order = sorted(args, key=lambda n: max(args[n]["lines"]))           # in the order they finish
    answered = {a for r in ratings.values() for a in r.get("answers", [])}
    per_arg = {}
    for n in order:
        r = ratings.get(n)
        if not r:
            continue
        host = args[n]["host"]
        base = argument_score(r)
        later_opponent = any(args[m]["host"] != host and min(args[m]["lines"]) > max(args[n]["lines"]) for m in args)
        dropped = n not in answered and later_opponent
        per_arg[n] = {"host": host, "score": round(min(100, base + (DROPPED_BONUS if dropped else 0)), 1),
                      "base": round(base, 1), "dropped": dropped, "lines": args[n]["lines"],
                      "rebuttal": _clamp(r["rebuttal"]) if r.get("rebuttal") is not None and r.get("answers") else None,
                      "answers": r.get("answers", []), "note": r.get("note", ""),
                      "ratings": {k: (round(_clamp(r[k]), 2) if r.get(k) is not None else None) for k in WEIGHTS}}
    hosts = {}
    for h in HOSTS:
        mine = [a for a in per_arg.values() if a["host"] == h]
        rebuttals = [a["rebuttal"] for a in mine if a["rebuttal"] is not None]
        hosts[h] = {"score": round(sum(a["score"] for a in mine) / len(mine), 1) if mine else None,
                    "arguments": len(mine), "rebuttal": round(sum(rebuttals) / len(rebuttals), 2) if rebuttals else 0}
    ranked = sorted((h for h in HOSTS if hosts[h]["score"] is not None),
                    key=lambda h: (hosts[h]["score"], hosts[h]["rebuttal"]), reverse=True)
    winner, tie, tiebreak = (ranked[0] if ranked else None), False, False
    if len(ranked) > 1 and hosts[ranked[0]]["score"] == hosts[ranked[1]]["score"]:
        if hosts[ranked[0]]["rebuttal"] == hosts[ranked[1]]["rebuttal"]:
            tie, winner = True, None
        else:
            tiebreak = True
    close_call = (not tie and len(ranked) > 1
                  and hosts[ranked[0]]["score"] - hosts[ranked[1]]["score"] < CLOSE_CALL)
    return {"arguments": per_arg, "hosts": hosts, "ranked": ranked, "winner": winner, "tie": tie,
            "tiebreak": tiebreak, "close_call": close_call, "order": [n for n in order if n in per_arg]}


def meter(lines: list[dict], result: dict) -> None:
    """Put running scores on the lines so the meter moves as each argument is scored:
    after an argument's last line, that host's running average (before dropped bonuses,
    which can only be known at the end)."""
    seen = {h: [] for h in HOSTS}
    last_line = {n: max(a["lines"]) for n, a in result["arguments"].items()}
    for line in lines:
        for n, a in result["arguments"].items():
            if last_line[n] == line["line"]:
                seen[a["host"]].append(a["base"])
                line["score"] = {a["host"]: round(sum(seen[a["host"]]) / len(seen[a["host"]]))}


PANEL = 3          # blind judges per segment, run side by side; their ratings are averaged


def _average(panels: list[dict]) -> dict:
    """Average several judges' ratings for each argument. An argument counts as answering an
    earlier one if any judge said so; its rebuttal rating is the average of the judges who
    rated it."""
    out = {}
    for n in set().union(*panels):
        rows = [p[n] for p in panels if n in p]
        merged = {"argument": n, "answers": sorted({a for r in rows for a in r.get("answers", [])}),
                  "note": " / ".join(r.get("note", "") for r in rows)}
        for k in ("evidence", "reasoning", "impact", "clarity"):
            merged[k] = sum(_clamp(r[k]) for r in rows) / len(rows)
        rebuttals = [_clamp(r["rebuttal"]) for r in rows if r.get("rebuttal") is not None and r.get("answers")]
        merged["rebuttal"] = sum(rebuttals) / len(rebuttals) if rebuttals else None
        out[n] = merged
    return out


def judge(lines: list[dict], pack: list[dict], topic: str, client: anthropic.Anthropic, seed=None) -> dict:
    """Score a finished script. PANEL blind judges run at the same time, each with the hosts
    shuffled differently, and their ratings are averaged; then code does the math."""
    from concurrent.futures import ThreadPoolExecutor
    rng = random.Random(seed)
    seeds = [rng.random() for _ in range(PANEL)]
    with ThreadPoolExecutor(PANEL) as pool:
        panels = list(pool.map(lambda s: rate(lines, pack, topic, client, s), seeds))
    result = tally(lines, _average([p[0] for p in panels]))
    result["blind_labels"] = [p[1] for p in panels]
    return result


# ---------- 3. Hal's close ----------

CLOSE_RULES = """You write Hal Brennan's closing lines on Sideline, after the judge has scored the
debate. Follow Hal's bible (below). The winner is decided; you only announce it.

Write TWO short lines for Hal, in order (changed Nov 6, 2026: no recap of the others;
the audience just heard their final answers):
1. The winner, by score: "On the scorecard, tonight goes to <name>." (On a tie, say the
   judge has it even and name both. If the verdict says it was close, say so in plain words,
   like "by a hair".) Don't say the numeric scores; the meter shows them.
   Put the winner announcement and what carried it in this first line: one or two plain
   sentences on why his case won, in fresh words, not a repeat of his final answer. At
   most one number. Use only what the winner actually said; don't add new facts.
2. The sign-off: "That's the board. Thanks for the call, <caller first name>." Nothing
   else: don't restate the other hosts' positions.
Every number, and every claim about the real world (who runs more, who's injured, who has
an MVP), must come from the fact pack, with its fact ID in "facts". When Hal repeats a point
from the script, cite the same fact IDs that line cites, and say numbers the same way. Plain words, short sentences, first names. No jokes at anyone's expense."""

CLOSE_SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {
    "text": {"type": "string"}, "facts": {"type": "array", "items": {"type": "string"}}},
    "required": ["text", "facts"], "additionalProperties": False}}}, "required": ["lines"], "additionalProperties": False}


def write_close(lines: list[dict], result: dict, pack: list[dict], caller: dict, hal_bible: str,
                client: anthropic.Anthropic) -> list[dict]:
    names = {"royce": "Royce", "deacon": "Deacon", "lonnie": "Lonnie"}
    script = "\n".join(f"{l['line']}. {l['speaker_name']}: {l['text']}" + (f"  [facts: {', '.join(l['facts'])}]" if l.get("facts") else "")
                       for l in lines)
    # (each line shows the fact IDs it used: when Hal repeats a point, he cites the same IDs)
    w = result["winner"]
    if result["tie"]:
        verdict = f"A tie between {names[result['ranked'][0]]} and {names[result['ranked'][1]]}."
    else:
        verdict = f"The winner is {names[w]}" + (" (on the rebuttal tiebreaker)" if result["tiebreak"] else "") + "."
        if result.get("close_call"):
            verdict += f" It was close: {names[result['ranked'][1]]} was right behind."
    best = sorted((a for a in result["arguments"].values() if a["host"] == w), key=lambda a: -a["score"]) if w else []
    hint = f"\nThe winner's strongest argument is lines {best[0]['lines']}." if best else ""
    reply = client.messages.create(
        model=CLOSE_MODEL, max_tokens=3000, system=CLOSE_RULES + "\n\n" + hal_bible,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": CLOSE_SCHEMA}},
        messages=[{"role": "user", "content": f"{verdict}{hint}\nCaller: {caller['name']} from {caller['city']}.\n\n"
                   f"Fact pack:\n{json.dumps(pack, ensure_ascii=False)}\n\nScript:\n{script}"}],
    )
    data = json.loads(next(b.text for b in reply.content if b.type == "text"))
    return data["lines"][:2]


def safe_close(result: dict, caller: dict) -> list[dict]:
    """A close with no facts in it, used only if the written close fails its checks."""
    names = {"royce": "Royce", "deacon": "Deacon", "lonnie": "Lonnie"}
    if result["tie"]:
        first = f"On the scorecard, the judge has it even between {names[result['ranked'][0]]} and {names[result['ranked'][1]]}."
    else:
        first = f"On the scorecard, tonight goes to {names[result['winner']]}."
    return [{"text": first, "facts": []},
            {"text": f"That's the board. Thanks for the call, {caller['name']}.", "facts": []}]
