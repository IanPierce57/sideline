"""The line checker: after the script is written, every number in every line must
match a fact that line cites (BRIEF.md, "Checking rules"). Then an AI reader looks
for other factual claims the fact pack doesn't support. Failed lines are rewritten
once with verified numbers, and cut if they still fail. Everything goes in the log.

Rounding rules from the brief: counts must be exact; rates can round to one
decimal; "about" (or nearly, almost, roughly, around) is allowed only when
rounding a real number."""

import json
import os
import re

import anthropic

REWRITE_MODEL = "claude-sonnet-5-5"
CLAIMS_MODEL = os.environ.get("SIDELINE_CLAIMS_MODEL", "claude-sonnet-5-5")
CLAIMS_EFFORT = os.environ.get("SIDELINE_CLAIMS_EFFORT", "high")

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
             r"pro bowls?|all-pros?|attempts|completions|dropbacks|turnovers|threes|three-pointers|trips|" \
             r"hits|takeaways|starts|minutes|reps|inches|seconds|pounds|days)"
# A number said with a noun must come from a fact about that same thing (added Nov 5, 2026,
# after an audit caught "seven games" passing because the line also cited 7 sacks).
# noun -> words, any of which must appear in the fact the number comes from.
NOUN_KEYS = {
    "yard": ("yard",), "touchdown": ("touchdown", "td"), "td": ("touchdown", "td"), "interception": ("interception",),
    "pick": ("interception", "pick"), "sack": ("sack",), "ring": ("champion", "super bowl", "title"),
    "title": ("champion", "title"), "championship": ("champion",), "super bowl": ("super bowl", "champion"),
    "mvp": ("mvp", "most valuable"), "win": ("record", "win", "result", "meeting", "streak"),
    "loss": ("record", "loss", "result", "meeting", "streak"), "point": ("point", "scor"), "rebound": ("rebound",),
    "assist": ("assist",), "steal": ("steal",), "block": ("block",), "catch": ("reception", "catch"),
    "reception": ("reception", "catch"), "carr": ("carr",), "game": ("game",), "season": ("season",),
    "percent": ("percent", "%", "rate", "pct", "shooting"), "pro bowl": ("pro bowl",), "all-pro": ("all-pro",),
    "attempt": ("attempt",), "completion": ("completion",), "dropback": ("dropback",), "turnover": ("turnover",),
    "three": ("three",), "trip": ("trip",), "hit": ("hit",), "takeaway": ("takeaway",), "start": ("start",),
    "minute": ("minute",), "rep": ("rep",), "inch": ("inch", "height", "jump"), "second": ("second", "dash", "drill", "shuttle"),
    "pound": ("pound", "weight"), "day": ("day", "rest", "back-to-back"),
}


def _noun_key(noun: str | None):
    if not noun:
        return None
    n = noun.lower()
    for key in sorted(NOUN_KEYS, key=len, reverse=True):
        if n.startswith(key) or (key == "loss" and n == "losses") or (key == "catch" and n == "catches"):
            return key
    return None
HEDGES = ("about", "nearly", "almost", "roughly", "around", "close to", "just under", "just over", "over", "under")


def _noun_after(clean: str, end: int):
    """The stat noun right after a number (within two words), if any: '7 sacks', '12 QB hits'."""
    m = re.match(r"\W+((?:[a-z'-]+\W+){0,2}?)" + STAT_NOUNS + r"\b", clean[end:].lower())
    if not m or any(w.strip(" ,.-") in WORDS for w in m.group(1).split()):
        return None                        # another number sits in between: the noun is its, not this one's
    return m.group(2)


def _numbers_in(text: str):
    """Every number said in a line: (value, the words around it, hedged?, stat noun after it)."""
    found = []
    clean = text.replace("’", "'")
    for m in re.finditer(r"(?<![\w.])([+-]?\d[\d,]*(?:\.\d+)?|[+-]?\.\d+)(%|st|nd|rd|th)?", clean):
        raw = m.group(1).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        before = clean[max(0, m.start() - 14):m.start()].lower()
        noun = None if m.group(2) == "%" else _noun_after(clean, m.end())
        found.append((value, m.group(0), any(h in before for h in HEDGES), noun))
    # two-digit years said as '17
    for m in re.finditer(r"'(\d\d)\b", clean):
        found.append((2000 + int(m.group(1)), m.group(0), False, None))
    words = re.finditer(r"\b(" + "|".join(sorted(WORDS, key=len, reverse=True)) + r")(?:[- ](one|two|three|four|five|six|seven|eight|nine))?\b(?![- ]team)(?=\W+(?:\w+\W+){0,2}?" + STAT_NOUNS + r"\b)",
                        clean.lower())
    for m in words:
        value = WORDS[m.group(1)] + (WORDS[m.group(2)] if m.group(2) else 0)
        before = clean[max(0, m.start() - 14):m.start()].lower()
        found.append((float(value), m.group(0), any(h in before for h in HEDGES), _noun_after(clean, m.end())))
    return found


def _allowed_for(facts: list[dict]) -> list[tuple]:
    """(value, tolerance, needs_hedge, what it's about) for everything the cited facts let a host say."""
    allowed = []
    for f in facts:
        about = " ".join(str(f.get(k) or "") for k in ("label", "stat", "say")).lower()
        v = f.get("value")
        nums = []
        if isinstance(v, dict):                                   # team record: wins, losses, ties
            nums += [float(x) for x in v.values()]
        elif isinstance(v, (int, float)):
            nums.append(float(v))
        for n in nums:
            allowed.append((n, 1e-6, False, about))                      # exact
            allowed.append((abs(n), 1e-6, False, about))                 # said without the sign
            if not float(n).is_integer():
                allowed.append((round(n, 1), 1e-6, False, about))        # rates may round to one decimal
                allowed.append((abs(round(n, 2)), 1e-6, False, about))   # EPA said as .17
                allowed.append((round(n), 1e-6, True, about))            # whole number only with "about"
            elif abs(n) >= 1000:
                allowed.append((round(n, -2), 1e-6, True, about))        # "about 37,700"
                allowed.append((round(n, -3), 1e-6, True, about))
        # numbers inside the fact's own description: sample, season, rank, as-of week
        for text in (f.get("sample"), f.get("scope"), f.get("rank"), f.get("as_of"), f.get("say"), f.get("definition")):
            text = str(text or "")
            for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", text):
                near = (text + " " + about).lower()      # what the description is about
                allowed.append((float(m.group(0).replace(",", "")), 1e-6, False, near))
                if len(m.group(0)) == 4 and m.group(0).isdigit():
                    allowed.append((float(m.group(0)[2:]), 1e-6, False, near))   # '18 for 2018
    return allowed


# Notes about what a character does, written into the spoken text by mistake.
STAGE_NOTE = re.compile(r"\b(rhetorical question|to the folks at home:|stage direction|asks? (?:the )?(?:audience|viewers)|"
                        r"(?:turns|leans|pauses|gestures|points) (?:to|toward|at)\b[^.!?]*$)|\[[^\]]*\]", re.I)


# A host admitting on air that the show is missing a number ("I don't have their numbers").
MISSING_DATA = re.compile(r"\b(?:i|we) (?:don't|do not|didn't) have (?:the |any |his |her |their |those )?"
                          r"(?:[\w-]+ ){0,3}(?:numbers?|stats?|data|figures?)\b", re.I)


# Stock phrases that make the show sound scripted. Each may appear once per segment; more
# than that sends the line back for a rewrite (style only: it's never cut for this).
STOCK_PHRASES = ["here's my thing", "listen here", "hang on. hang on", "here's the question that matters",
                 "to my eye", "that's the sample", "that's the column", "remember this", "folks at home",
                 "both fair", "okay, okay", "i'll give you that", "can i jump in", "let's be clear",
                 "at the end of the day", "make no mistake", "you're making my case", "sure. fine",
                 "hah", "that's the case", "show me the number", "here's what i'd do"]


STOCK_LIMIT = 2          # stock phrases allowed in a whole segment, all hosts together
# Names of moves from the bibles: notes for the writer, never said on air ("That's the stack").
MOVE_NAMES = re.compile(r"\b(?:that's |this is |call it |here's )?(?:the|my) (?:stack|drop|column|lede|kicker|hinge|steelman)\b"
                        r"|\bsteelman\w*\b", re.I)


def check_stock_phrases(lines: list[dict]) -> list[dict]:
    """Style problems (rewritten, never cut): a move name said on air, stock phrases past the
    segment's limit, and a number said for the third time or more."""
    used, problems = 0, []
    said = {}
    # Final answers may restate the key number (they sum up the case), so they're not counted.
    last_hal = max((l["line"] for l in lines if l["speaker"] == "hal"), default=0)
    for line in lines:
        low = line["text"].lower().replace("’", "'")
        issues = []
        own = {"royce": ("royce",), "deacon": ("deacon", "deac"), "lonnie": ("lonnie",), "hal": ("hal",)}.get(line["speaker"], ())
        if any(re.search(r"(?:,\s*|^)" + n + r"\b[.,?!]", low) for n in own):
            issues.append("the speaker addresses himself by his own name; this line is probably meant for someone "
                          "else, so fix the name (or who's speaking)")
        if MOVE_NAMES.search(low):
            issues.append(f"says the name of a move out loud ({MOVE_NAMES.search(low).group(0)!r}); just do the move")
        found = [p for p in STOCK_PHRASES if p in low]
        if found:
            used += len(found)
            if used > STOCK_LIMIT:
                issues.append(f"uses the stock phrase {', '.join(found)!r} after the segment's limit of {STOCK_LIMIT}; "
                              "say it fresh, in other words, or drop it")
        repeats = []
        # Stat-like numbers only: records ("6-1"), decimals ("0.29"), and numbers of 10 or more
        # ("241"); small counts ("two MVPs", "three rings") are different facts, not repeats.
        clean = line["text"].replace(",", "")
        tokens = re.findall(r"\b\d+-\d+(?:-\d+)?\b|[+-]?\d*\.\d+|\b\d{2,}\b", clean)
        final_answer = line["line"] > last_hal and line["speaker"] in ("royce", "deacon", "lonnie")
        for token in ([] if final_answer else tokens):
            if re.fullmatch(r"(19|20)\d\d", token):
                continue                          # years
            key = (line["speaker"], token.lstrip("+-"))     # the same host saying the same stat again
            said[key] = said.get(key, 0) + 1
            if said[key] == 3:
                repeats.append(token)
        if repeats:
            issues.append(f"this host says {', '.join(repeats)} for the third time. REMOVE that number from this "
                          "line: refer to it in words ('that number', 'his record') and use the turn to add a "
                          "different support for his case")
        if issues:
            problems.append({"line": line["line"], "style": True, "problem": "; ".join(issues)})
    return problems


def check_stage_notes(lines: list[dict]) -> list[dict]:
    """Lines that contain a description of an action instead of spoken words.
    Bible stage directions in parentheses at the start of a line are fine."""
    problems = []
    for line in lines:
        spoken = re.sub(r"^\s*\([^)]*\)\s*", "", line["text"])
        if STAGE_NOTE.search(spoken):
            problems.append({"line": line["line"], "problem": "contains a note about what someone does instead of "
                             "the words they say; rewrite it as spoken words only"})
        elif MISSING_DATA.search(spoken):
            problems.append({"line": line["line"], "problem": "a host says on air that a number is missing; argue "
                             "from what the fact pack has instead, without mentioning what isn't there"})
    return problems


THIS_SEASON = re.compile(r"\bthis (?:season|year)\b|\bso far\b|\bright now\b|\bthrough week \d+|\bthrough (?:nov|dec|jan|feb|mar|apr|oct)", re.I)


def check_scope(lines: list[dict], facts_by_id: dict) -> list[dict]:
    """Lines that say "this season" (or "right now", "so far") while every season-specific
    fact they cite is from an earlier season."""
    from .verify import season_tag
    problems = []
    for line in lines:
        if not THIS_SEASON.search(line["text"]):
            continue
        tags = [season_tag(facts_by_id[i]) for i in line.get("facts", []) if i in facts_by_id]
        tagged = [t for t in tags if t]
        if tagged and all(t != "this season" for t in tagged):
            problems.append({"line": line["line"], "problem": "says this season (or right now) but every season "
                             "number it cites is from an earlier season; say which season, or use this season's facts"})
    return problems


def check_numbers(lines: list[dict], facts_by_id: dict, topic: str = "") -> list[dict]:
    """Lines with a number that doesn't match a cited fact. Numbers in the caller's
    own question (the topic) are allowed anywhere: "top-10" isn't a stat claim."""
    problems = []
    topic_numbers = [(v, 1e-6, False, "") for v, _, _, _ in _numbers_in(topic)]
    for line in lines:
        cited = [facts_by_id[i] for i in line.get("facts", []) if i in facts_by_id]
        allowed = _allowed_for(cited) + topic_numbers
        bad = []
        for value, said, hedged, noun in _numbers_in(line["text"]):
            if value in BIBLE_NUMBERS.get(line["speaker"], set()):
                continue
            key = _noun_key(noun)
            fits = [a for a in allowed if abs(value - a[0]) <= a[1] and (hedged or not a[2])]
            if key and fits and not any(any(w in a[3] for w in NOUN_KEYS[key]) for a in fits if a[3]) \
                    and not any(a[3] == "" for a in fits):
                bad.append(f"{said} {noun} (no cited fact has {int(value) if value.is_integer() else value} {noun})")
            elif not fits:
                bad.append(said)
        if bad:
            problems.append({"line": line["line"], "problem": f"says {', '.join(bad)}, which doesn't match any fact this line cites"
                             + ("" if cited else " (it cites none)")})
    return problems


# The claims check lists EVERY real-world claim with a verdict, rather than "list what's
# wrong" (changed Nov 5, 2026: on eight audited scripts, listing every claim caught 5x more
# unsupported claims than the old way). The model can be set with SIDELINE_CLAIMS_MODEL.
CLAIMS_RULES = """You fact-check a sports debate script before it airs. You get the script, the
fact pack (the ONLY verified facts), and style profiles (NOT verified; for judging whether
opinions are believable only).

List EVERY real-world claim in every line (callers and the moderator too): numbers; a
player's team, position, or role (starter, second option); injuries and health; awards,
titles, and which team they came with; records and standings; rankings and superlatives
("leads the league", "best scorer on the floor"); comparisons ("more than", "nearly
double"); trends ("he's improved", "a dip"); game results, dates, opponents; who coaches
whom; draft position; trades; streaks; and scope ("this season" vs "last season").

For each claim give a verdict:
- SUPPORTED: a fact states it, or it follows by simple, correct arithmetic or comparison
  from facts (cite them). Scope must match: a fact marked "last season, not this one"
  said as this season's, or in the present tense, is NOT supported.
- UNSUPPORTED: no fact backs it, and it could be false. This includes how a player plays
  stated as fact from the style profiles ("he throws deep more than most"), injury
  history ("they won without him"), and roles or superlatives no fact ranks.
- CONTRADICTED: the fact pack says something different.
Do NOT list: opinions and the host's read ("to my eye..."), predictions, metaphors,
arguments, believable opinions about how a player plays, or the hosts' own fictional
careers. Timeless general knowledge (what a stat means) is SUPPORTED.
Opinions must still be believable: list as UNSUPPORTED an opinion no knowledgeable fan
would hold given the style profiles (a quarterback who barely runs called a dual threat).
Be strict and literal. When unsure, say UNSUPPORTED."""

CLAIMS_SCHEMA = {"type": "object", "properties": {"claims": {"type": "array", "items": {"type": "object", "properties": {
    "line": {"type": "integer"}, "claim": {"type": "string"},
    "verdict": {"type": "string", "enum": ["SUPPORTED", "UNSUPPORTED", "CONTRADICTED"]},
    "facts": {"type": "array", "items": {"type": "string"}}, "why": {"type": "string"}},
    "required": ["line", "claim", "verdict", "facts", "why"], "additionalProperties": False}}},
    "required": ["claims"], "additionalProperties": False}


def check_claims(lines: list[dict], pack: list[dict], context: str, client: anthropic.Anthropic,
                 effort: str | None = None) -> list[dict]:
    """Every real-world claim, judged against the fact pack; returns the ones not supported."""
    script = "\n".join(f"{l['line']}. {l['speaker']}: {l['text']}" for l in lines)
    with client.messages.stream(
        model=CLAIMS_MODEL, max_tokens=16000, system=CLAIMS_RULES, thinking={"type": "adaptive"},
        output_config={"effort": effort or CLAIMS_EFFORT, "format": {"type": "json_schema", "schema": CLAIMS_SCHEMA}},
        messages=[{"role": "user", "content": f"{context}\n\nFact pack:\n{json.dumps(pack, ensure_ascii=False)}\n\nScript:\n{script}"}],
    ) as stream:
        reply = stream.get_final_message()
    claims = json.loads(next(b.text for b in reply.content if b.type == "text"))["claims"]
    return [{"line": c["line"], "problem": f"{c['claim']}: {c['why']} ({c['verdict'].lower()})"}
            for c in claims if c["verdict"] != "SUPPORTED"]


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


def smooth(out: list[dict], cut_numbers: list[int], original: list[dict], by_id: dict, pack: list[dict],
           client: anthropic.Anthropic, topic: str = "", profiles: list[dict] | None = None, log: list | None = None) -> list[dict]:
    """After lines are cut, fix the lines on either side so the conversation still flows
    (a hand-off to someone whose line is gone, a reply to a point nobody made). Each fixed
    line is checked again; if it fails, the old line stays."""
    from . import style
    if not cut_numbers:
        return out
    gone = {l["line"]: l for l in original if l["line"] in cut_numbers}
    order = [l["line"] for l in out]
    around = set()
    for n in cut_numbers:
        before = [x for x in order if x < n]
        after = [x for x in order if x > n]
        if before:
            around.add(before[-1])
        if after:
            around.add(after[0])
    if not around:
        return out
    notes = "; ".join(f"after line {max([x for x in order if x < n] or [0])} the line \"{gone[n]['speaker']}: "
                      f"{gone[n]['text'][:120]}\" was removed" for n in cut_numbers)
    problems = [{"line": n, "problem": "a nearby line was removed (" + notes + "). Adjust this line only as much as "
                 "needed so the conversation flows: fix hand-offs (who Hal calls on must be who speaks next) and "
                 "don't answer or refer to the removed line. Keep its numbers and facts."} for n in sorted(around)]
    try:
        fixes = rewrite(out, problems, pack, client)
    except Exception:
        return out
    smoothed = []
    for line in out:
        fix = fixes.get(line["line"])
        if fix:
            candidate = dict(line, text=fix["text"], facts=[i for i in fix["facts"] if i in by_id])
            if not (check_numbers([candidate], by_id, topic) + check_stage_notes([candidate])
                    + style.check_labels([candidate], profiles or []) + check_scope([candidate], by_id)):
                if log is not None and candidate["text"] != line["text"]:
                    log.append({"line": line["line"], "speaker": line["speaker"], "said": line["text"],
                                "problem": "smoothed after a nearby cut", "action": "smoothed", "now": candidate["text"]})
                smoothed.append(candidate)
                continue
        smoothed.append(line)
    return smoothed


def run(lines: list[dict], facts: list[dict], pack: list[dict], context: str, client: anthropic.Anthropic,
        progress=lambda *a: None, topic: str = "", profiles: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """Check, rewrite once, re-check, cut what still fails. Returns (lines, log).
    profiles: style profiles (pipeline/style.py) for checking that opinions are believable."""
    from . import style
    profiles = profiles or []
    by_id = {f["id"]: f for f in facts}
    log = []
    number_problems = (check_numbers(lines, by_id, topic) + check_stage_notes(lines) + style.check_labels(lines, profiles)
                       + check_scope(lines, by_id))
    claim_problems = check_claims(lines, pack, context, client)
    progress("line_check", {"checked": len(lines), "flagged": len({p['line'] for p in number_problems + claim_problems})})
    style_problems = check_stock_phrases(lines)
    problems = number_problems + claim_problems + style_problems
    style_only = {p["line"] for p in style_problems} - {p["line"] for p in number_problems + claim_problems}
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
            still = (check_numbers([candidate], by_id, topic) + check_stage_notes([candidate])
                     + style.check_labels([candidate], profiles) + check_scope([candidate], by_id))
            if not still:
                out.append(candidate)
                log.append({"line": line["line"], "speaker": line["speaker"], "said": original,
                            "problem": "; ".join(merged[line["line"]]), "action": "rewritten", "now": fix["text"]})
                continue
        if line["line"] in style_only:                 # a style problem never costs a line
            out.append(line)
            continue
        log.append({"line": line["line"], "speaker": line["speaker"], "said": original,
                    "problem": "; ".join(merged[line["line"]]), "action": "cut"})
    out = smooth(out, [e["line"] for e in log if e["action"] == "cut"], lines, by_id, pack, client, topic, profiles, log)
    progress("line_fix", {"rewritten": sum(1 for e in log if e["action"] == "rewritten"),
                          "cut": sum(1 for e in log if e["action"] == "cut")})
    for i, line in enumerate(out, start=1):
        line["line"] = i
    return out, log
