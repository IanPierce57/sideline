"""
generate.py: turns a topic into a debate script.

What it does, in order:
  1. Reads the Debate rules from BRIEF.md and every bible in characters/.
  2. Sends them, plus your topic, to Claude (Sonnet) and asks for the script
     back as structured JSON (every line has a speaker, text, delivery, and
     argument number).
  3. Runs a few plain checks (word count, no numbers, no leftover placeholders).
  4. Saves the script to runs/<date>_<time>/script.json.

Run it on its own:
    .venv/bin/python generate.py "Is Patrick Mahomes the best quarterback of all time?"
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

PROJECT = Path(__file__).parent
RUNS = PROJECT / "runs"
CHARACTERS = PROJECT / "characters"

# The writer model. "Sonnet for writing" (BRIEF.md, How it's built).
MODEL = "claude-sonnet-5-5"

# Years that appear in the hosts' own bibles (Royce's receipts, Deacon's career).
# Hosts may say these in step 1; the number check ignores them.
BIBLE_YEARS = r"\b(?:1990|2002|2011|2016|2017|2019)\b|'(?:16|17|19)\b"

WORDS_PER_MINUTE = 150
TARGET_WORDS = (450, 750)  # 3 to 5 minutes at speaking pace

# Who can speak, and the name shown in the subtitles.
SPEAKERS = {
    "caller": None,  # filled in from the caller the AI picks
    "hal": "Hal",
    "royce": "Royce",
    "deacon": "Deacon",
    "lonnie": "Lonnie",
}

# Delivery tags. Later steps turn these into body animations.
DELIVERIES = [
    "calm", "warm", "curious", "confident", "building", "emphatic",
    "heated", "cold", "quiet", "laughing", "sarcastic", "dismissive",
    "frustrated", "conceding",
    # Big reactions, for rare moments: stands up, slams the desk, turns away.
    "fired_up", "slam", "exasperated",
]

FORMATS = ["debate", "buy_or_sell", "prediction"]
# How hard the writer thinks. Tested Nov 5, 2026 (tests/pipeline_test.py and two full runs).
# Medium wrote as well as high and about 20 seconds faster on the same topic.
WRITER_EFFORT = os.environ.get("SIDELINE_WRITER_EFFORT", "medium")

# Rules about facts. They sit on top of the bibles, which show [Research-step ...]
# placeholders where real numbers go; the fact pack supplies the real numbers.
FACT_RULES = """\
FACT RULES. These override the bibles wherever they conflict.

1. Numbers come only from the fact pack. Every number a host says about the
   real world (a stat, count, percentage, rank, record, season, or sample) must
   come from a fact in the fact pack, and that line must list the fact's ID in
   "facts". Say it the way the fact's "say" field has it. Rates may round to one
   decimal, and "about" is only for rounding a real number. Never estimate,
   remember, or invent a number, and never write a [Research-step ...] placeholder.
2. Say the scope when it matters: "in 2022", "for his career", "in the playoffs",
   "this season, through Week 8". A single season is never a career number.
   Compare like with like (career to career, season to season).
3. The first time an advanced stat comes up, someone explains it in one plain
   sentence, using the fact's definition.
4. Real-world claims without numbers (a player's current team, an injury, a
   title, a record) must agree with the fact pack. Use the current_team facts:
   never put a player on a team the fact pack contradicts. If the fact pack
   doesn't cover something, keep it general or make it clearly an opinion.
   Opinions about how a player plays must fit his style profile: never call a
   quarterback who barely runs a dual threat, or a short-area receiver a deep threat.
   The same goes for images and metaphors (Royce's eye test): "he plays quarterback
   like a point guard" is fine for a quarterback who runs and improvises, not for
   one who barely leaves the pocket. Metaphors describe how a player plays in
   general, never a specific real play, and never his looks. Invent fresh images
   for this player; never reuse a bible's example image word for word.
   Style profiles are not checked facts: use them only to keep opinions believable.
   Never state a profile ranking as fact ("he has a very high catch rate"); cite a
   fact-pack stat, or make it the host's read ("to my eye, the ball always finds him").
   Never say on air that a number is missing ("I don't have their numbers"):
   argue from what the fact pack has.
5. No specific real-world scenes or quotes. Don't describe a particular play or
   game, and don't quote a real player or coach.
6. This season vs. last season. A fact whose scope says "last season, not this one"
   is last season's: say "last season" (or the year) every time, and never use it
   with "this season", "this year", "right now", or the present tense ("he's scoring
   28.8 a night"). Present-tense numbers must be this season's facts.
7. Injuries are as of today only. Never say when a player got hurt, how many games
   he's missed, or that a team won or lost "without" him; the fact pack doesn't say.
8. Superlatives and roles need proof. "Best scorer on the floor", "leads the
   league", "the second option", "the go-to guy" need a fact with a rank or that
   covers everyone being compared. Otherwise make it the host's read ("to my eye,
   he's their go-to guy").
9. Titles, awards, and trends. Don't say which team a player won a title or award
   with unless the fact says so. Don't say a player improved, declined, or "dipped"
   unless the fact pack has the numbers for both seasons being compared.
10. Not every line needs a number. Use facts where they win the point: Royce lands
   one memorable number, Deacon stacks two or three. Lonnie has no contract or
   cap figures in the fact pack, so he keeps money talk general.
11. Host backstories are allowed. Hosts may use the fictional careers and receipts
   in their own bibles, years included. Those come from the bibles, not the world.
12. Every host gets his best honest case. Don't decide who should win or tilt the
   debate toward anyone; strengths show up naturally in what each host knows.
13. No winner in your script. A judge scores the debate after you write it, and
   Hal's close (the winner, the summary, the sign-off) is written then. Hal never
   hints at who argued better before that; end the script with the final answers.
"""

SCRIPT_INSTRUCTIONS = """\
YOUR JOB

Write one segment of Sideline for the topic the user gives you. Follow the
Debate rules, the moderator bible (Hal), the three host bibles (Royce, Deacon,
Lonnie), the callers file, and the fact rules above.

Segment flow:
1. Hal takes the call: "You're on the Sideline. Go ahead, <name> from <city>."
2. The caller asks the user's question in their own words, without stating or
   implying facts of their own (no "go deep again", no records or injuries) (one to three
   sentences), in the voice of the caller type that fits the topic best.
3. Hal restates the question in one plain sentence and names the format.
4. Hal throws to the host whose kind of evidence fits the question best.
5. The hosts argue. Every reply deals with the previous point. Hal stays out
   while new arguments keep coming, and cuts in (headphones off one ear) only
   for the reasons in his bible.
6. When new arguments run out, Hal asks for one-sentence final answers.
7. The script ENDS with the three final answers. Don't write Hal's wrap-up: the judge
   scores the debate first, and Hal's close is written afterward (fact rule 12).

Format: pick exactly one.
- "debate": a question with sides (who's better right now, is Y overrated).
- "buy_or_sell": a team or front-office decision (trade, sign, extend, buy or sell).
- "prediction": a future outcome (who wins, will X happen this season).

Length: aim for 600 to 720 spoken words in total (about 4 to 5 minutes at 150 words
per minute; it must land between 450 and 750 after the fact check, which cuts any
line it can't confirm). End when the new arguments run out. Never pad, never repeat a point.

Each line:
- speaker: one of caller, hal, royce, deacon, lonnie.
- text: exactly what is said out loud. Never write a note about what a character
  does instead of the words themselves ("Ask a rhetorical question to the folks at
  home:" or "He turns to Hal"): ask the question, say the words. Stage directions from the bibles, like
  "(the pencil stops)", may open a line in parentheses; keep them rare.
- delivery: one tag for how it's said, from the allowed list. Three tags are
  big physical reactions the studio animates: "fired_up" (he stands up),
  "slam" (he slams the desk), and "exasperated" (he turns away, arms crossed).
  Use them only when the topic earns a blowup, at most two in a segment, and
  only in character: Deacon is the one who gets loud, Royce goes cold instead,
  Lonnie almost never does, and Hal never does.
- facts: the IDs of every fact-pack fact this line uses (e.g. ["F3", "F7"]),
  or [] if it uses none. Every real-world number in the line needs one.
- argument: which argument this line belongs to, or null.
  * Number arguments 1, 2, 3... in the order they first appear.
  * A new number starts each time a host makes a new claim or a rebuttal
    (a rebuttal to someone else's argument is its own new argument).
  * A host's follow-up line that continues the same argument keeps its number.
  * Caller and Hal lines are always null. A short reaction that argues
    nothing ("Hah.", "Come on.") is null.
  * Each argument number belongs to exactly one host. Never give a line the
    number of another host's argument; answering it starts a new number.
  * Every host should have at least two numbered arguments.

Write it so a reader could tell who's talking with the names hidden: each
host's voice, evidence lean, signature move, and temperature come from his
bible. Catchphrases at most once per segment each.

Keep it fresh. The line banks, sample lines, and example exchanges show how
each character sounds; they are not lines to reuse. Write new lines in that
voice for this topic. Don't open with a line-bank line, and use at most one
line-bank line per character, reworded. Hal's cut-ins should fit the moment,
not repeat his sample lines. Lonnie's switch is rare: only when a co-host
brings a new fact or argument that changes the decision, never just because
someone landed a good line. Most segments, nobody switches.
"""


def section(markdown: str, heading: str) -> str:
    """Return one '## heading' section of a Markdown file, heading included."""
    match = re.search(rf"^## {re.escape(heading)}\n.*?(?=^## |\Z)", markdown, re.S | re.M)
    if not match:
        raise ValueError(f"BRIEF.md has no '## {heading}' section")
    return match.group(0).strip()


def build_system_prompt() -> str:
    """Debate rules + Cast from the brief, then every character file."""
    brief = (PROJECT / "BRIEF.md").read_text()
    parts = [
        "You are the writer for Sideline, an NBA and NFL call-in debate show.",
        "# From BRIEF.md\n\n" + section(brief, "Debate rules") + "\n\n" + section(brief, "Cast"),
    ]
    # Sorted so the prompt is byte-identical every run (keeps the cache warm).
    for path in sorted(CHARACTERS.glob("*.md")):
        parts.append(f"# characters/{path.name}\n\n{path.read_text().strip()}")
    parts.append(FACT_RULES)
    parts.append(SCRIPT_INSTRUCTIONS)
    return "\n\n---\n\n".join(parts)


# The exact JSON shape Claude must return. The API enforces it.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "format": {"type": "string", "enum": FORMATS},
        "caller": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["diehard", "stats_nerd", "rival_fan", "old_timer", "skeptic", "settler"],
                },
                "name": {"type": "string", "description": "First name only"},
                "city": {"type": "string", "description": "A real U.S. city"},
            },
            "required": ["type", "name", "city"],
            "additionalProperties": False,
        },
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string", "enum": list(SPEAKERS)},
                    "text": {"type": "string"},
                    "delivery": {"type": "string", "enum": DELIVERIES},
                    "facts": {"type": "array", "items": {"type": "string"}},
                    "argument": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                },
                "required": ["speaker", "text", "delivery", "facts", "argument"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["format", "caller", "lines"],
    "additionalProperties": False,
}


def count_words(text: str) -> int:
    # Stage directions in parentheses aren't spoken, so they don't count.
    spoken = re.sub(r"\([^)]*\)", " ", text)
    return len(spoken.split())


def check_script(lines: list[dict]) -> list[str]:
    """Plain checks. They don't change the script; they report problems."""
    warnings = []
    words = sum(count_words(line["text"]) for line in lines)
    if not TARGET_WORDS[0] <= words <= TARGET_WORDS[1]:
        warnings.append(f"{words} spoken words, outside the {TARGET_WORDS[0]}-{TARGET_WORDS[1]} target")
    for line in lines:
        if "[" in line["text"]:
            warnings.append(f"line {line['line']} has a bracket, maybe a leftover placeholder")
    hosts_args = {}
    owners = {}
    for line in lines:
        if line["argument"] is not None:
            hosts_args.setdefault(line["speaker"], set()).add(line["argument"])
            owner = owners.setdefault(line["argument"], line["speaker"])
            if owner != line["speaker"]:
                warnings.append(f"line {line['line']}: argument {line['argument']} belongs to "
                                f"{SPEAKERS[owner]} but {line['speaker_name']} used it")
    from pipeline.judge import _arguments
    turns = _arguments(lines)
    for host in ("royce", "deacon", "lonnie"):
        if sum(1 for a in turns.values() if a["host"] == host) < 2:
            warnings.append(f"{SPEAKERS[host]} has fewer than two scored arguments")
    return warnings


class TopicProblem(Exception):
    """The topic check turned the topic away, or needs the user to pick a player."""
    def __init__(self, details: dict):
        super().__init__(details.get("reason") or "Which player did you mean?")
        self.details = details


def _source_line(fact: dict) -> str:
    """One plain line for the end card's source list."""
    checked = str(fact.get("checked_against") or "")
    if fact["stat"] == "current_team":
        return "Current rosters: Sleeper" + (", checked against nflverse" if "nflverse" in checked else "")
    if "muffed" in checked:
        return "Advanced stats: nflverse, checked against muffed.ai (" + fact.get("credit", "Data via nflverse") + ")"
    if fact["source"] == "Sleeper":
        return f"{fact['league']} stats: Sleeper"
    return f"{fact['league']} stats: nflverse, checked against Sleeper"


def _chyron(fact: dict) -> dict:
    """What the stat chyron shows for one fact."""
    checked = fact.get("checked_against") or ""
    return {"value": fact["say"], "label": f"{fact['subject']} · {fact['label']}",
            "definition": fact.get("definition", ""),
            "source": _source_line(fact).split(": ", 1)[1],
            "asOf": f"{fact.get('scope', '')} · {fact.get('as_of', '')}".strip(" ·")}


def generate_script(topic: str, progress=None, chosen: list[str] | None = None) -> tuple[Path, dict]:
    """Research, verify, write, and check a segment for one topic. Saves the run
    and returns (run folder, script). progress(event, details) reports each step.
    chosen: player keys the user picked when a name matched more than one player."""
    from pipeline import linecheck, research, verify

    progress = progress or (lambda *a: None)
    topic = topic.strip()
    if not topic:
        raise ValueError("Type a topic first.")

    load_dotenv(PROJECT / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        raise RuntimeError("No API key yet. Run set_key.sh (see README.md).")
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from .env
    started = time.time()
    timings = {}

    # 1. Topic check
    progress("step", {"step": "topic", "text": "Screening the call"})
    t = time.time()
    check = research.check_topic(topic, client, chosen=set(chosen or []))
    timings["topic_check"] = round(time.time() - t, 1)
    if not check["ok"]:
        raise TopicProblem(check)
    named = check["players"]
    progress("topic", {"format": check["format"], "players": [p["name"] for p in named]})

    # 2. Research
    progress("step", {"step": "research", "text": "Pulling stats"})
    t = time.time()
    game = check.get("game")
    candidates, game_note = [], ""
    # Facts are checked in the background as soon as they're pulled (verify.warm), so the
    # second sources are already fetched when research finishes. The real check below is
    # unchanged; it just finds what it needs already saved.
    def pulled(event, fact=None):
        if event == "pulled" and isinstance(fact, dict):
            verify.warm(fact)
        progress(event, fact)
    if game:
        from pipeline import leagues
        candidates = leagues.game_pack(game)
        for fact in candidates:
            pulled("pulled", fact)
        game_note = leagues.game_note(game)
    candidates += research.research(topic, check["format"], named, client, pulled, follow_up=game_note)
    timings["research"] = round(time.time() - t, 1)

    # 3. Verify
    progress("step", {"step": "verify", "text": "Checking every number against a second source"})
    t = time.time()
    facts, stat_log = verify.check_all(candidates, progress)

    # 3b. Anything that couldn't be confirmed is crossed off. Go find something else:
    # one more research round for checkable replacements, checked the same way.
    crossed_off = [r for r in stat_log if not r["reason"].startswith("kept")]
    if crossed_off:
        progress("step", {"step": "research", "text": f"Replacing {len(crossed_off)} crossed-off stats"})
        listing = "\n".join(f"- {r['subject']}: {r['stat']} ({r.get('scope') or 'n/a'}): {r['reason']}" for r in crossed_off)
        kept = "\n".join(f"- {f['subject']}: {f['label']} ({f.get('scope')})" for f in facts)
        more = research.research(topic, check["format"], named, client, pulled, rounds=2, follow_up=(game_note + "\n\n" +
            "These stats couldn't be confirmed, so they were crossed off:\n" + listing +
            "\n\nAlready confirmed (don't ask for these again):\n" + kept +
            "\n\nFind replacements that can be confirmed and still serve the argument: other seasons or stats "
            "for the same players, or comparable numbers for other current players. Don't re-request anything "
            "crossed off. If nothing fits, reply \"done\"."))
        if more:
            candidates += more
            more_facts, more_log = verify.check_all(more, progress)
            facts = verify.merge(facts, more_facts)
            stat_log += more_log
    timings["verify"] = round(time.time() - t, 1)
    pack = verify.pack_for_writer(facts)
    progress("verified", {"found": len(candidates), "passed": len(facts),
                          "dropped": sum(1 for r in stat_log if not r["reason"].startswith("kept"))})

    # 3c. Style profiles: how each player actually plays, in words only, so opinions stay
    # believable (no "dual-threat" Jared Goff). Never quoted; numbers still come from the pack.
    from pipeline import players as player_lookup, style
    profiles, seen_keys = [], set()
    for f in facts:
        key = f.get("subject_key") or ""
        if key.split(":")[0] in ("nfl", "nba") and key not in seen_keys:
            seen_keys.add(key)
            try:
                p = style.profile(player_lookup.by_key(key))
            except Exception:
                p = None
            if p:
                profiles.append(p)
    style_text = "\n".join(style.describe(p) for p in profiles)

    # 4. Write, with the fact pack
    progress("step", {"step": "write", "text": "Writing the segment"})
    context = (f"Format (from the topic check): {check['format']}. Today is {datetime.now():%B %-d, %Y}. "
               "Current teams and anything else about the real world: see the fact pack.")
    if game:
        context += ("\n\nGame preview: " + game_note + " Every host picks a winner and argues it from the fact pack "
                    "(matchups, form, injuries, home field). Hal makes sure each pick is stated plainly. No one predicts a "
                    "final score or a point spread, and no betting talk: a score is a number, and every number must come "
                    "from the fact pack. Injury designations can change before kickoff; say they're as of today.")
    t = time.time()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=32000,
        thinking={"type": "adaptive"},
        output_config={"effort": WRITER_EFFORT, "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        # If a safety check declines the request, the API retries it on another model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=[{"type": "text", "text": build_system_prompt(),
                 # The bibles are the same every run, so cache them (cheaper and faster).
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Topic: {topic}\n\n{context}\n\n"
                   f"Fact pack (every number you may use):\n{json.dumps(pack, indent=1, ensure_ascii=False)}"
                   + (f"\n\nStyle profiles (how each player actually plays, ranked against his position; for choosing "
                      f"believable descriptions only, never to quote):\n{style_text}" if style_text else "")}],
    ) as stream:
        response = stream.get_final_message()
    timings["write"] = round(time.time() - t, 1)

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to write this one. Try rewording the topic.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("The script got cut off before it finished. Try again.")
    data = json.loads(next(block.text for block in response.content if block.type == "text"))

    caller = data["caller"]
    names = dict(SPEAKERS, caller=f"{caller['name']} from {caller['city']}")
    lines = [{"line": n, "speaker": l["speaker"], "speaker_name": names[l["speaker"]], "text": l["text"].strip(),
              "delivery": l["delivery"], "facts": l["facts"], "argument": l["argument"]}
             for n, l in enumerate(data["lines"], start=1)]

    # 5. Check every line
    progress("step", {"step": "check", "text": "Checking every line of the script"})
    t = time.time()
    lines, line_log = linecheck.run(lines, facts, pack, context + ("\n\nStyle profiles:\n" + style_text if style_text else ""),
                                    client, progress, topic, profiles=profiles)
    timings["line_check"] = round(time.time() - t, 1)

    # 6. Judge: score every argument blind (pipeline/judge.py). The math is done in code.
    from pipeline import judge as judging
    progress("step", {"step": "judge", "text": "The judge is scoring every argument"})
    t = time.time()
    result = judging.judge(lines, pack, topic, client)
    judging.meter(lines, result)
    timings["judge"] = round(time.time() - t, 1)

    # 7. Close: Hal announces the result, written only now that the score is known.
    # It goes through the same checks as every other line; if it can't pass, a close
    # with no facts in it is used instead.
    progress("step", {"step": "close", "text": "Hal is getting the verdict"})
    t = time.time()
    hal_bible = (CHARACTERS / "moderator.md").read_text()
    by_id_all = {f["id"]: f for f in facts}
    close_log = []
    try:
        drafted = judging.write_close(lines, result, pack, caller, hal_bible, client)
        close = [{"line": len(lines) + i, "speaker": "hal", "speaker_name": names["hal"], "text": c["text"].strip(),
                  "delivery": "calm" if i < len(drafted) else "warm", "facts": [x for x in c["facts"] if x in by_id_all],
                  "argument": None} for i, c in enumerate(drafted, start=1)]
        def close_problems(c):
            return (linecheck.check_numbers(c, by_id_all, topic) + linecheck.check_scope(c, by_id_all)
                    + linecheck.check_stage_notes(c) + linecheck.check_claims(c, pack, context, client))
        problems = close_problems(close)
        if problems:                                   # one rewrite, the same as any other line
            close_log = problems
            fixes = linecheck.rewrite(close, problems, pack, client)
            close = [dict(c, text=fixes[c["line"]]["text"], facts=[x for x in fixes[c["line"]]["facts"] if x in by_id_all])
                     if c["line"] in fixes else c for c in close]
            if close_problems(close):
                close = None
    except Exception as problem:                       # the close must never sink the segment
        close_log = [{"line": 0, "problem": f"{type(problem).__name__}: {problem}"}]
        close = None
    if not close:
        close = [{"line": len(lines) + i, "speaker": "hal", "speaker_name": names["hal"], "text": c["text"],
                  "delivery": "calm", "facts": [], "argument": None}
                 for i, c in enumerate(judging.safe_close(result, caller), start=1)]
    close[0]["score"] = {h: round(v["score"]) for h, v in result["hosts"].items() if v["score"] is not None}
    lines += close
    timings["close"] = round(time.time() - t, 1)

    # The stat chyron shows each fact the first time it's cited.
    by_id = {f["id"]: f for f in facts}
    shown = set()
    for line in lines:
        for fid in line.get("facts", []):
            fact = by_id.get(fid)
            if fact and fact["stat"] != "current_team" and fid not in shown:
                line["stat"] = _chyron(fact)
                shown.add(fid)
                break

    used = {fid for line in lines for fid in line.get("facts", [])}
    sources = sorted({_source_line(by_id[i]) for i in used if i in by_id})
    words = sum(count_words(line["text"]) for line in lines)
    script = {
        "topic": topic,
        "format": check["format"],
        "caller": caller,
        "players": [p["name"] for p in named],
        "word_count": words,
        "estimated_minutes": round(words / WORDS_PER_MINUTE, 1),
        "warnings": check_script(lines),
        "sources": sources,
        "scores": {h: v["score"] for h, v in result["hosts"].items()},
        "winner": result["winner"],
        "tie": result["tie"],
        "lines": lines,
        "meta": {
            "step": 2,
            "model": response.model,
            "created": datetime.now().isoformat(timespec="seconds"),
            "generation_seconds": round(time.time() - started, 1),
            "timings": timings,
            "stats_found": len(candidates),
            "stats_verified": len(facts),
            "stats_dropped": sum(1 for r in stat_log if not r["reason"].startswith("kept")),
            "facts_used": len(used),
            "lines_checked": len(lines) + sum(1 for e in line_log if e["action"] == "cut"),
            "lines_rewritten": sum(1 for e in line_log if e["action"] == "rewritten"),
            "lines_cut": sum(1 for e in line_log if e["action"] == "cut"),
            "writer_input_tokens": response.usage.input_tokens,
            "writer_cache_read_tokens": response.usage.cache_read_input_tokens,
            "writer_output_tokens": response.usage.output_tokens,
        },
    }

    # One folder per run, named by date and time. If two runs finish in the
    # same second, wait a second so they never share a folder.
    RUNS.mkdir(exist_ok=True)
    while True:
        run_dir = RUNS / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        try:
            run_dir.mkdir()
            break
        except FileExistsError:
            time.sleep(1)
    (run_dir / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False))
    (run_dir / "fact_pack.json").write_text(json.dumps(facts, indent=2, ensure_ascii=False, default=str))
    (run_dir / "rejection_log.json").write_text(json.dumps({"stats": stat_log, "lines": line_log, "close": close_log},
                                                           indent=2, ensure_ascii=False))
    (run_dir / "judge.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    progress("done", {"run": run_dir.name})
    return run_dir, script


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: .venv/bin/python generate.py "your NBA or NFL topic"')
        sys.exit(1)
    topic = " ".join(sys.argv[1:])
    print(f"Writing a segment on: {topic}")
    try:
        run_dir, script = generate_script(topic)
    except anthropic.AuthenticationError:
        print("Your API key was rejected. Check the line in .env (see README.md).")
        sys.exit(1)
    except anthropic.APIConnectionError:
        print("Couldn't reach the Claude API. Check your internet connection.")
        sys.exit(1)
    except TopicProblem as problem:
        d = problem.details
        if d.get("confirm"):
            for c in d["confirm"]:
                print(f"'{c['asked']}' could be: " + "; ".join(f"{x['label']} [{x['key']}]" for x in c["choices"]))
        else:
            print("Topic turned away:", d.get("reason"), "| Try:", "; ".join(d.get("suggestions", [])))
        sys.exit(1)
    except RuntimeError as problem:
        print(problem)
        sys.exit(1)
    print()
    for line in script["lines"]:
        cites = f"  {line['facts']}" if line.get("facts") else ""
        print(f"{line['speaker_name'].upper()} [{line['delivery']}]: {line['text']}{cites}")
    print()
    m = script["meta"]
    print(f"Format: {script['format']}   Words: {script['word_count']} "
          f"(~{script['estimated_minutes']} min)   Took: {m['generation_seconds']}s {m['timings']}")
    print(f"Stats: {m['stats_found']} found, {m['stats_verified']} verified, {m['stats_dropped']} dropped, "
          f"{m['facts_used']} used | Lines: {m['lines_checked']} checked, {m['lines_rewritten']} rewritten, {m['lines_cut']} cut")
    board = ", ".join(f"{SPEAKERS[h]} {s:.1f}" for h, s in sorted(script["scores"].items(), key=lambda x: -(x[1] or 0)) if s is not None)
    print(f"Scores: {board}   Winner: {'tie' if script['tie'] else SPEAKERS.get(script['winner'], script['winner'])}")
    for warning in script["warnings"]:
        print(f"WARNING: {warning}")
    print(f"Saved to {run_dir.relative_to(PROJECT)}/script.json")


if __name__ == "__main__":
    main()
