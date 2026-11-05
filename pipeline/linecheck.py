"""The line checker: after the script is written, every number in every line must
match a fact that line cites (BRIEF.md, "Checking rules"). Then an AI reader looks
for other factual claims the fact pack doesn't support. Failed lines are rewritten
once with verified numbers, and cut if they still fail. Everything goes in the log.

Rounding rules from the brief: counts must be exact; rates can round to one
decimal; "about" (or nearly, almost, roughly, around) is allowed only when
rounding a real number."""

import json
import re

import anthropic

REWRITE_MODEL = "claude-sonnet-5-5"
CLAIMS_MODEL = "claude-sonnet-5-5"

# Numbers from each character's own bible (fictional careers and receipts). A host
# may say his own; nobody else's, so a made-up "13 touchdowns" can't sneak through.
BIBLE_NUMBERS = {
    "royce": {1963, 1990, 2001, 2009, 2012, 2016, 2017, 2019, 40},   # born, books, TV, receipts, forty years
    "deacon": {1990, 2002, 2011, 2017, 13, 9},                        # drafted, retired, Hall of Fame, the 2017 miss, 13 seasons, ninth round
    "lonnie": {1985, 2008, 2015, 2023, 6, 15, 11},                    # born, video room, NFL move, left, six kids, fifteen years, eleven credits
    "hal": {30},                                                      # thirty years of radio
}

WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
         "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
         "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
         "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
         "ninth": 9, "tenth": 10}
# A spelled-out number only counts as a stat when one of these follows it closely
# ("three rings", "forty touchdowns"); "one series" or "game seven" is just talk.
STAT_NOUNS = r"(yards?|touchdowns?|tds?|interceptions?|picks?|sacks?|rings?|titles?|championships?|super bowls?|mvps?|" \
             r"wins?|losses|points|rebounds|assists|steals|blocks|catches|receptions|carries|games|seasons|percent|" \
             r"pro bowls?|all-pros?|attempts|completions|dropbacks|turnovers|threes|three-pointers|trips)"
HEDGES = ("about", "nearly", "almost", "roughly", "around", "close to", "just under", "just over", "over", "under")


def _numbers_in(text: str):
    """Every number said in a line: (value, the words around it, hedged?)."""
    found = []
    clean = text.replace("’", "'")
    for m in re.finditer(r"(?<![\w.])([+-]?\d[\d,]*(?:\.\d+)?|[+-]?\.\d+)(%|st|nd|rd|th)?", clean):
        raw = m.group(1).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        before = clean[max(0, m.start() - 14):m.start()].lower()
        found.append((value, m.group(0), any(h in before for h in HEDGES)))
    # two-digit years said as '17
    for m in re.finditer(r"'(\d\d)\b", clean):
        found.append((2000 + int(m.group(1)), m.group(0), False))
    words = re.finditer(r"\b(" + "|".join(sorted(WORDS, key=len, reverse=True)) + r")(?:[- ](one|two|three|four|five|six|seven|eight|nine))?\b(?=\W+(?:\w+\W+){0,2}?" + STAT_NOUNS + r"\b)",
                        clean.lower())
    for m in words:
        value = WORDS[m.group(1)] + (WORDS[m.group(2)] if m.group(2) else 0)
        before = clean[max(0, m.start() - 14):m.start()].lower()
        found.append((float(value), m.group(0), any(h in before for h in HEDGES)))
    return found


def _allowed_for(facts: list[dict]) -> list[tuple[float, float, bool]]:
    """(value, tolerance, needs_hedge) for everything the cited facts let a host say."""
    allowed = []
    for f in facts:
        v = f.get("value")
        nums = []
        if isinstance(v, dict):                                   # team record: wins, losses, ties
            nums += [float(x) for x in v.values()]
        elif isinstance(v, (int, float)):
            nums.append(float(v))
        for n in nums:
            allowed.append((n, 1e-6, False))                      # exact
            allowed.append((abs(n), 1e-6, False))                 # said without the sign
            if not float(n).is_integer():
                allowed.append((round(n, 1), 1e-6, False))        # rates may round to one decimal
                allowed.append((abs(round(n, 2)), 1e-6, False))   # EPA said as .17
                allowed.append((round(n), 1e-6, True))            # whole number only with "about"
            elif abs(n) >= 1000:
                allowed.append((round(n, -2), 1e-6, True))        # "about 37,700"
                allowed.append((round(n, -3), 1e-6, True))
        # numbers inside the fact's own description: sample, season, rank, as-of week
        for text in (f.get("sample"), f.get("scope"), f.get("rank"), f.get("as_of"), f.get("say")):
            for m in re.findall(r"\d[\d,]*(?:\.\d+)?", str(text or "")):
                allowed.append((float(m.replace(",", "")), 1e-6, False))
                if len(m) == 4 and m.isdigit():
                    allowed.append((float(m[2:]), 1e-6, False))   # '18 for 2018
    return allowed


def check_numbers(lines: list[dict], facts_by_id: dict) -> list[dict]:
    """Lines with a number that doesn't match a cited fact."""
    problems = []
    for line in lines:
        cited = [facts_by_id[i] for i in line.get("facts", []) if i in facts_by_id]
        allowed = _allowed_for(cited)
        bad = []
        for value, said, hedged in _numbers_in(line["text"]):
            if value in BIBLE_NUMBERS.get(line["speaker"], set()):
                continue
            ok = any(abs(value - a) <= tol and (hedged or not needs_hedge) for a, tol, needs_hedge in allowed)
            if not ok:
                bad.append(said)
        if bad:
            problems.append({"line": line["line"], "problem": f"says {', '.join(bad)}, which doesn't match any fact this line cites"
                             + ("" if cited else " (it cites none)")})
    return problems


CLAIMS_RULES = """You fact-check a sports debate script before it airs. You get the script and the
fact pack (the only verified facts). List every line that states something about the
real world that is not supported by the fact pack and could be false: a player's
current team, a trade, an injury, an award or title count, a record, a ranking,
"led the league", a specific game result, or a quote.

Do NOT flag: opinions, predictions, arguments, how someone "looks" or "feels" to a host,
the hosts' own fictional careers, general well-known framing ("he's won it more than once"
is fine only if the fact pack doesn't contradict it), or anything the fact pack supports.
Be strict about anything the fact pack contradicts. Return an empty list if nothing is wrong."""

CLAIMS_SCHEMA = {"type": "object", "properties": {"flags": {"type": "array", "items": {"type": "object", "properties": {
    "line": {"type": "integer"}, "claim": {"type": "string"}, "problem": {"type": "string"}},
    "required": ["line", "claim", "problem"], "additionalProperties": False}}},
    "required": ["flags"], "additionalProperties": False}


def check_claims(lines: list[dict], pack: list[dict], context: str, client: anthropic.Anthropic) -> list[dict]:
    script = "\n".join(f"{l['line']}. {l['speaker']}: {l['text']}" for l in lines)
    reply = client.messages.create(
        model=CLAIMS_MODEL, max_tokens=4000, system=CLAIMS_RULES, output_config={"effort": "low",
            "format": {"type": "json_schema", "schema": CLAIMS_SCHEMA}},
        messages=[{"role": "user", "content": f"{context}\n\nFact pack:\n{json.dumps(pack, ensure_ascii=False)}\n\nScript:\n{script}"}],
    )
    flags = json.loads(next(b.text for b in reply.content if b.type == "text"))["flags"]
    return [{"line": f["line"], "problem": f"{f['claim']}: {f['problem']}"} for f in flags]


REWRITE_SCHEMA = {"type": "object", "properties": {"fixes": {"type": "array", "items": {"type": "object", "properties": {
    "line": {"type": "integer"}, "text": {"type": "string"}, "facts": {"type": "array", "items": {"type": "string"}}},
    "required": ["line", "text", "facts"], "additionalProperties": False}}},
    "required": ["fixes"], "additionalProperties": False}


def rewrite(lines: list[dict], problems: list[dict], pack: list[dict], client: anthropic.Anthropic) -> dict:
    """One rewrite pass for the failed lines. Returns {line number: {'text', 'facts'}}."""
    script = "\n".join(f"{l['line']}. {l['speaker']}: {l['text']}  [facts: {', '.join(l.get('facts', [])) or 'none'}]" for l in lines)
    issues = "\n".join(f"line {p['line']}: {p['problem']}" for p in problems)
    reply = client.messages.create(
        model=REWRITE_MODEL, max_tokens=6000, output_config={"effort": "low",
            "format": {"type": "json_schema", "schema": REWRITE_SCHEMA}},
        system="You fix lines in a sports debate script so every fact is right. Keep each line in the same "
               "speaker's voice, the same length, and the same point. Use only numbers from the fact pack, "
               "cite the fact IDs you use, and say each number exactly as the fact pack's 'say' field has it "
               "(rates may round to one decimal; use 'about' only when rounding). If a claim can't be "
               "supported, make it a general claim or an opinion instead. Fix only the listed lines.",
        messages=[{"role": "user", "content": f"Fact pack:\n{json.dumps(pack, ensure_ascii=False)}\n\nScript:\n{script}\n\nFix these lines:\n{issues}"}],
    )
    fixes = json.loads(next(b.text for b in reply.content if b.type == "text"))["fixes"]
    return {f["line"]: {"text": f["text"], "facts": f["facts"]} for f in fixes}


def run(lines: list[dict], facts: list[dict], pack: list[dict], context: str, client: anthropic.Anthropic,
        progress=lambda *a: None) -> tuple[list[dict], list[dict]]:
    """Check, rewrite once, re-check, cut what still fails. Returns (lines, log)."""
    by_id = {f["id"]: f for f in facts}
    log = []
    number_problems = check_numbers(lines, by_id)
    claim_problems = check_claims(lines, pack, context, client)
    progress("line_check", {"checked": len(lines), "flagged": len({p['line'] for p in number_problems + claim_problems})})
    problems = number_problems + claim_problems
    if not problems:
        return lines, log

    merged = {}
    for p in problems:
        merged.setdefault(p["line"], []).append(p["problem"])
    fixes = rewrite(lines, [{"line": n, "problem": "; ".join(ps)} for n, ps in merged.items()], pack, client)
    out = []
    for line in lines:
        if line["line"] not in merged:
            out.append(line)
            continue
        original = line["text"]
        fix = fixes.get(line["line"])
        if fix:
            candidate = dict(line, text=fix["text"], facts=[i for i in fix["facts"] if i in by_id])
            still = check_numbers([candidate], by_id)
            if not still:
                out.append(candidate)
                log.append({"line": line["line"], "speaker": line["speaker"], "said": original,
                            "problem": "; ".join(merged[line["line"]]), "action": "rewritten", "now": fix["text"]})
                continue
        log.append({"line": line["line"], "speaker": line["speaker"], "said": original,
                    "problem": "; ".join(merged[line["line"]]), "action": "cut"})
    progress("line_fix", {"rewritten": sum(1 for e in log if e["action"] == "rewritten"),
                          "cut": sum(1 for e in log if e["action"] == "cut")})
    for i, line in enumerate(out, start=1):
        line["line"] = i
    return out, log
