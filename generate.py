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
]

FORMATS = ["debate", "buy_or_sell", "prediction"]

# Rules for step 1 only. They sit on top of the bibles until research exists.
STEP_1_RULES = """\
STEP 1 RULES. These override the bibles wherever they conflict.

The research step does not exist yet, so there is no fact pack. Until it does:

1. No numbers about the real world. Hosts must not cite any stat, count,
   percentage, ranking number, record, score, salary, or year about real
   players, teams, or games. Not in digits, not spelled out ("forty touchdowns",
   "three rings"), not as "about" or "roughly". Make the argument with general
   claims instead: "his efficiency's been elite for years", "he's won it more
   than once", "they've been one of the best defenses in the league".
2. No research-step placeholders. Never write a bracketed placeholder like
   [Research-step stat: ...]. The bibles use them; this script must not.
3. No specific real-world scenes or quotes. Don't describe a particular game,
   play, or score, and don't quote a real player or coach. Talk about patterns
   and well-known reputations instead ("he's been at his best in January").
4. Host backstories are allowed. Hosts may use the fictional careers and
   receipts in their own bibles, years included (Royce's spring 2017 Kansas
   City call, Deacon's 13 seasons, Lonnie's red-team job). Those are checked
   against the bibles, not the real world.
5. Current-season caution. You don't have this season's data. For current
   topics, argue from roster construction, reputations, and how teams are
   built, not from this season's records or results.
6. No winner. The judge and scoring don't exist yet, so Hal does NOT announce
   a winner, say "on the scorecard", or hint at who argued better. After the
   final answers, Hal restates where each host landed in one plain sentence
   (using "Where we are:" or similar), thanks the caller by name, and signs
   off with "That's the board."
"""

SCRIPT_INSTRUCTIONS = """\
YOUR JOB

Write one segment of The Receipts for the topic the user gives you. Follow the
Debate rules, the moderator bible (Hal), the three host bibles (Royce, Deacon,
Lonnie), the callers file, and the step 1 rules above.

Segment flow:
1. Hal takes the call: "You're on The Receipts. Go ahead, <name> from <city>."
2. The caller asks the user's question in their own words (one to three
   sentences), in the voice of the caller type that fits the topic best.
3. Hal restates the question in one plain sentence and names the format.
4. Hal throws to the host whose kind of evidence fits the question best.
5. The hosts argue. Every reply deals with the previous point. Hal stays out
   while new arguments keep coming, and cuts in (headphones off one ear) only
   for the reasons in his bible.
6. When new arguments run out, Hal asks for one-sentence final answers.
7. Hal wraps up with no winner (step 1 rule 6).

Format: pick exactly one.
- "debate": a question with sides (who's better, is X the greatest, is Y overrated).
- "buy_or_sell": a team or front-office decision (trade, sign, extend, buy or sell).
- "prediction": a future outcome (who wins, will X happen this season).

Length: aim for 450 to 750 spoken words in total (3 to 5 minutes at 150 words
per minute). End when the new arguments run out. Never pad, never repeat a point.

Each line:
- speaker: one of caller, hal, royce, deacon, lonnie.
- text: exactly what is said out loud. Stage directions from the bibles, like
  "(the pencil stops)", may open a line in parentheses; keep them rare.
- delivery: one tag for how it's said, from the allowed list.
- argument: which argument this line belongs to, or null.
  * Number arguments 1, 2, 3... in the order they first appear.
  * A new number starts each time a host makes a new claim or a rebuttal
    (a rebuttal to someone else's argument is its own new argument).
  * A host's follow-up line that continues the same argument keeps its number.
  * Caller and Hal lines are always null. A short reaction that argues
    nothing ("Hah.", "Come on.") is null.
  * Every host should have at least two numbered arguments.

Write it so a reader could tell who's talking with the names hidden: each
host's voice, evidence lean, signature move, and temperature come from his
bible. Catchphrases at most once per segment each.
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
        "You are the writer for The Receipts, an NBA and NFL debate show.",
        "# From BRIEF.md\n\n" + section(brief, "Debate rules") + "\n\n" + section(brief, "Cast"),
    ]
    # Sorted so the prompt is byte-identical every run (keeps the cache warm).
    for path in sorted(CHARACTERS.glob("*.md")):
        parts.append(f"# characters/{path.name}\n\n{path.read_text().strip()}")
    parts.append(STEP_1_RULES)
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
                    "argument": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                },
                "required": ["speaker", "text", "delivery", "argument"],
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
        if line["speaker"] in ("royce", "deacon", "lonnie") and re.search(r"\d", line["text"]):
            warnings.append(f"line {line['line']} ({line['speaker_name']}) contains a digit: {line['text']!r}")
        if "[" in line["text"]:
            warnings.append(f"line {line['line']} has a bracket, maybe a leftover placeholder")
    hosts_args = {}
    for line in lines:
        if line["argument"] is not None:
            hosts_args.setdefault(line["speaker"], set()).add(line["argument"])
    for host in ("royce", "deacon", "lonnie"):
        if len(hosts_args.get(host, ())) < 2:
            warnings.append(f"{SPEAKERS[host]} has fewer than two numbered arguments")
    return warnings


def generate_script(topic: str) -> tuple[Path, dict]:
    """Write a script for one topic, save it, and return (run folder, script)."""
    topic = topic.strip()
    if not topic:
        raise ValueError("Type a topic first.")

    load_dotenv(PROJECT / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        raise RuntimeError("No API key yet. Paste it into the .env file (see README.md).")
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from .env

    started = time.time()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=32000,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
        },
        # If a safety check declines the request, the API retries it on another model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=[{
            "type": "text",
            "text": build_system_prompt(),
            # The bibles are the same every run, so cache them (cheaper and faster).
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": f"Topic: {topic}"}],
    ) as stream:
        response = stream.get_final_message()
    seconds = round(time.time() - started, 1)

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to write this one. Try rewording the topic.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("The script got cut off before it finished. Try again.")

    text = next(block.text for block in response.content if block.type == "text")
    data = json.loads(text)

    caller = data["caller"]
    names = dict(SPEAKERS, caller=f"{caller['name']} from {caller['city']}")
    lines = []
    for number, line in enumerate(data["lines"], start=1):
        lines.append({
            "line": number,
            "speaker": line["speaker"],
            "speaker_name": names[line["speaker"]],
            "text": line["text"].strip(),
            "delivery": line["delivery"],
            "argument": line["argument"],
        })

    words = sum(count_words(line["text"]) for line in lines)
    script = {
        "topic": topic,
        "format": data["format"],
        "caller": caller,
        "word_count": words,
        "estimated_minutes": round(words / WORDS_PER_MINUTE, 1),
        "warnings": check_script(lines),
        "lines": lines,
        "meta": {
            "step": 1,
            "model": response.model,
            "created": datetime.now().isoformat(timespec="seconds"),
            "generation_seconds": seconds,
            "input_tokens": response.usage.input_tokens,
            "cache_read_tokens": response.usage.cache_read_input_tokens,
            "cache_write_tokens": response.usage.cache_creation_input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }

    run_dir = RUNS / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False))
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
    except RuntimeError as problem:
        print(problem)
        sys.exit(1)
    print()
    for line in script["lines"]:
        print(f"{line['speaker_name'].upper()} [{line['delivery']}]: {line['text']}")
    print()
    print(f"Format: {script['format']}   Words: {script['word_count']} "
          f"(~{script['estimated_minutes']} min)   Took: {script['meta']['generation_seconds']}s")
    for warning in script["warnings"]:
        print(f"WARNING: {warning}")
    print(f"Saved to {run_dir.relative_to(PROJECT)}/script.json")


if __name__ == "__main__":
    main()
