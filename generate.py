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

# Segment types (more added Nov 6, 2026, so topics don't get squeezed into three shapes).
FORMATS = ["debate", "prediction", "buy_or_sell", "real_or_not", "rank_em", "overrated"]
# How hard the writer thinks. Tested Nov 5, 2026 (tests/pipeline_test.py and two full runs).
# Medium wrote as well as high and about 20 seconds faster on the same topic.
WRITER_EFFORT = os.environ.get("SIDELINE_WRITER_EFFORT", "medium")

# Rules about facts. They sit on top of the bibles, which show [Research-step ...]
# placeholders where real numbers go; the fact pack supplies the real numbers.
def season_progress() -> str:
    """How far into each season we are, so sample-size talk fits the league (Nov 6, 2026:
    eight NFL games is half a season; eight NBA games is a week and a half)."""
    from pipeline import sleeper
    out = []
    try:
        season = int(sleeper.state("nfl")["season"])
        done = sum(1 for g in sleeper.nfl_schedule(season) if g.get("status") == "complete")
        per = round(2 * done / 32)
        size = ("a small sample" if per <= 4 else "a real sample, not a small one" if per >= 7
                else "a fair sample, getting bigger every week")
        out.append(f"NFL: teams have played about {per} of 17 games, {size}.")
    except Exception:
        pass
    try:
        from pipeline import nba
        done = sum(1 for g in nba.schedule() if g["status"] == "complete")
        per = round(2 * done / 30)
        size = "a small sample" if per < 20 else "a fair sample" if per < 41 else "a real sample"
        out.append(f"NBA: teams have played about {per} of 82 games, {size}.")
    except Exception:
        pass
    return ("How far into the season: " + " ".join(out)) if out else ""


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
3. The first time an advanced stat comes up, someone explains it in a few casual
   words, the way you'd explain it to a friend ("EPA, basically how many points each
   play is worth"), not a textbook definition; the stat card on screen shows the full
   definition. Keep it true to the fact's definition.
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
   for this player; never reuse a bible's example image word for word. An image
   never stands alone: the same turn lands on a fact from the pack (Royce's rule 4).
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
6b. Sample size depends on the league's calendar (see "How far into the season").
   NFL: the first three or four games are a small sample; by midseason (seven or eight
   games, half the schedule) a season's numbers are a real sample, so nobody calls them
   small. A slow start that turned around is fair to point out (a quarterback who
   struggled his first three games and has been strong since). NBA: under about 20
   games is small (eight games is a week and a half). Small counts are small in any
   league: a few playoff starts, under about 150 dropbacks, a handful of games back from
   an injury. Bring a sample up only when it's really small AND it changes the point,
   and at most once or twice in a whole segment; most segments shouldn't need it.
7. Injuries, read like someone who follows the sport.
   - Today's report: "questionable" usually means he plays (teams list nearly
     everything now), so it's never a storyline or an argument on its own. Day-to-day
     is minor. "Doubtful" means probably out. Out, injured reserve, and PUP mean out.
   - History comes only from the availability and injury_history facts. Never name an
     injury, a body part, a date, or a reason for missed games that they don't give.
     Games played are for the whole season, so never say an injury "cost him" a number
     of games; say what the fact says ("he played 16 of 82 the next season"). Games
     since a major injury come from the injury_history fact's "in the seasons since"
     numbers, never from this season's games alone.
   - Injury-prone is a pattern, not one injury. "Injury-prone", "can't stay healthy",
     "always hurt", or "durability concerns" need an availability fact showing a quarter
     or more missed in at least two of its full seasons. One major injury (a torn
     Achilles or ACL) doesn't make a player injury-prone, and nobody who follows the
     sport would call him that; it is fair to question how he comes back from it, as the
     host's opinion ("Achilles injuries take something; I want to see the burst first").
     How serious an injury type is stays the host's view too ("to me, that's the one you
     fear"), never a ranking said as fact ("the worst injury in the sport").
     A player who plays nearly every game can be called durable.
   - Never say a team won or lost "without" him; the fact pack doesn't say.
8. Superlatives and roles need proof. "Best scorer on the floor", "leads the
   league", "the second option", "the go-to guy" need a fact with a rank or that
   covers everyone being compared. Otherwise make it the host's read ("to my eye,
   he's their go-to guy").
9. Titles, awards, and trends. Don't say which team a player won a title or award
   with unless the fact says so. Don't say a player improved, declined, or "dipped"
   unless the fact pack has the numbers for both seasons being compared.
10. Realism. Trade, signing, and roster ideas must be ones a real front office could
   make: never propose trading away a player his team just acquired ("new to the team
   this season" in his time-with-team fact), and treat a team's established stars and
   recent big additions as off the table unless the topic is about them. When a host
   floats a move, he says why that team would do it (its record, its injuries, its
   needs). No contract figures exist in the pack, so money stays general.
10b. Not every line needs a number. Use facts where they win the point: Royce lands
   one memorable number, Deacon stacks two or three. Lonnie has no contract or
   cap figures in the fact pack, so he keeps money talk general.
11. Host backstories are allowed. Hosts may use the fictional careers and receipts
   in their own bibles, years included. Those come from the bibles, not the world.
12. Every turn adds something new: a fact, an answer, or an angle. A host deals with
   the point on the table before he pivots, and a host who reframes the question
   ("that's not the question") says why the other measure falls short and backs his
   own with a fact. A sign-off line that only repeats his case belongs in the final
   answer, not in a turn of its own.
13. Every host gets his best honest case. Don't decide who should win or tilt the
   debate toward anyone; strengths show up naturally in what each host knows.
14. No winner in your script. A judge scores the debate after you write it, and
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
3. Hal does NOT repeat the caller's question; everyone just heard it, and the segment
   type is on screen. He connects: one short, natural line that names ONE host, and
   that host speaks next ("Deacon, you've been itching for this one." / "Royce, you take
   it."). Nobody answers a host who hasn't spoken yet.
4. Hal throws to the host whose kind of evidence fits the question best.
5. The hosts argue. Every reply deals with the previous point. Hal stays out
   while new arguments keep coming, and cuts in (headphones off one ear) only
   for the reasons in his bible.
6. When new arguments run out, Hal asks for final answers in a few words, without
   recapping the debate. Each final answer is ONE fresh sentence: the pick and the one
   reason that decided it for him, said a new way. No reciting stats already said, no
   summary of the whole case. Hal's cut-ins move the debate forward with a question;
   they don't recap what's been said.
7. The script ENDS with the three final answers. Don't write Hal's wrap-up: the judge
   scores the debate first, and Hal's close is written afterward (fact rule 14).

Format: use the one the topic check picked. Each has its own shape:
- "debate" (WHO'S BETTER?): a head-to-head or "is he the best right now". Each host
  takes a side and they clash on the comparison.
- "prediction" (WHO WINS?): a game or a season outcome. Each host picks a winner and
  argues why it happens; no score predictions.
- "buy_or_sell" (BUY OR SELL?): a team or front-office move only (trade for, sign,
  extend, buy or sell at the deadline). The question is whether the move is smart and
  realistic for that team now; not for player comparisons.
- "real_or_not" (REAL OR NOT?): is a hot or cold start, a breakout, or a slump real?
  Each host says real or not, and what would prove him wrong.
- "rank_em" (RANK 'EM): rank three or more players or teams. Each host gives his
  ranking early; the debate is over where they differ. Final answers are rankings.
- "overrated" (OVERRATED OR UNDERRATED?): a player's or team's reputation against the
  numbers. Each host says overrated, underrated, or about right, and why.

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

Plan first (the "plan" field, before any line). For each host, a complete case: his
claim, 2 or 3 DIFFERENT supports (each a different kind of evidence, with its fact IDs:
say a rate stat, a record, and a matchup or context fact, not the same number three
ways), and how he answers the strongest objection. Then 3 or 4 beats: the opening positions, the main
clash, the trap or the exposed weakness, and the decisive exchange where one case gets
cornered. Then write the lines to follow the beats. Which case gets cornered follows
from the facts: the host whose position the fact pack supports less is the one who has
to scramble. Never decide it any other way.

The argument has to BUILD, not circle (added Nov 6, 2026):
- Each beat moves somewhere new. Once a point has been made and answered, nobody makes
  it again; the next exchange goes deeper or somewhere else.
- Each host builds his COMPLETE case across his turns (added Nov 6, 2026): his first
  turn states the claim with one support; later turns bring his other supports and his
  answer to the strongest objection. By his final answer, the audience has heard the
  whole case: claim, two or three different reasons, and why the other side's best point
  doesn't change it. He doesn't hop between unrelated ideas without finishing one.
- Coming back to a point is fine when it presses an opponent ("You still haven't answered
  the 6-1") or ties the case together, but it's never a whole turn by itself: a turn
  that returns to an old point also adds something. The segment is short, so balance it:
  every support gets said clearly once, and only the strongest one gets hammered.
- Hal moves it forward when it stalls: he names what's settled and points at the open
  question ("We've done the sack numbers. What does Chicago give up?").

Fire: this is a real fight between the best debaters on television (added Nov 6, 2026).
- Cross-examination. Hosts ask each other pointed questions that demand an answer, and
  the next line answers it directly or gets called out for dodging ("You didn't answer
  the question, Royce. Who's better this year?").
- Traps. A host gets an opponent to commit to a standard ("So the bigger sample wins?"
  "Of course.") and then shows that standard cuts against him.
- Catch them. Point out when an opponent contradicts himself, leans on a stat he
  dismissed a minute ago, or answers a question nobody asked. A host may leave out what
  hurts him, and get caught for it, but what he does say is always true: "his last two
  full seasons, 16 and 17" is fair and catchable; "in between he played 16 and 17" when
  four seasons came in between is false, even if someone corrects it.
- Turn their evidence. Take the other host's own fact and show it helps your side.
- Rapid fire. At least two stretches where three or four turns in a row are one short
  sentence each, people cutting in on each other.
- No free concessions. A host concedes only when a fact corners him, and a concession
  costs him: the others press on it right away. Nobody says "you're right" just to be
  agreeable.
- Every host takes at least one direct shot at another host's argument, and every shot
  gets an answer.

Sound like three people arguing live, not like AI (added Nov 6, 2026):
- Signature phrases ("Here's my thing", "Listen here", "Hang on. Hang on.", "Here's the
  question that matters", "To my eye", "That's the sample", "That's the column",
  "Remember this", "Folks at home", "Hah", "Can I jump in", "Sure. Fine.") at most TWO
  in the whole segment, all hosts together; most turns use none. Never: "Both fair",
  "Okay, okay", "Let's be clear", "At the end of the day", "make no mistake".
- Never say the names of moves from the bibles out loud: no "the stack", "the drop",
  "the Column", "the lede", "the kicker", "steelman", "my hinge", "the hinge". Those are
  notes for you, not words anyone says on air.
- Numbers: a number gets said at most twice in the whole segment (once to make the
  point, once if someone turns it). After that, refer to it in words ("that EPA number",
  "his record"). Final answers are one fresh sentence of conclusion, usually with no number.
- No formula openings. Don't start a turn by summing up both other hosts ("Royce is right
  about X, and Deacon's right about Y"). Answer the last thing said, in its own words.
- Vary the length: some turns are one short sentence ("That's a team stat, Royce."), some
  are a few sentences; nobody gives a speech every turn.
- No two turns open the same way. Contractions, plain words, the odd interruption.

How real people talk (added Nov 6, 2026). Colloquial but professional: three pros who
argue for a living, talking, not reading.
- Mix the shapes. Questions. Fragments. A one-word reaction ("Please."). Now and then a
  longer sentence that winds a little, with an aside in the middle, before it lands.
  Never the same structure two turns in a row.
- Let people be human: they react (laugh, get annoyed, sound surprised), correct
  themselves mid-thought ("He's second. Well, second on half the dropbacks, which is my
  point."), cut each other off (end a line with an em dash and let the next speaker jump
  in), call back to something said earlier, and needle each other a little.
- Natural fillers, sparingly: "look," "I mean," "come on," "honestly." Plain words,
  contractions, no slang overload, no profanity.
- Avoid the AI tells: tidy lists of three; "It's not X, it's Y" more than once a
  segment; every turn ending on a neat summary or a punchline; perfectly balanced
  "on one hand... on the other"; formal transitions ("Moreover," "Additionally,"
  "Ultimately," "That said"); restating the question back; announcing what you're about
  to do ("Let me tell you why...").

Think out loud (added Nov 6, 2026). These are people working an idea out live, not a
machine arranging finished sentences. They reach for the point and sharpen it as they go,
lean on a word to hit it ("Per snap. Per snap."), ask themselves a question and answer
it, grab a comparison from everyday life, start one way and correct course ("He's the
best passer in the... okay, not the best. The scariest."), and sometimes trail off into
a question. Same point, two ways:
  Machine: "That is a small sample, so it can't support a conclusion."
  Person:  "That's five games, Royce. Five. I've had colds last longer than that."
  Machine: "While the playoff record is impressive, it reflects team performance."
  Person:  "Sure, he's won in January. You know who else was out there for those? Fifty
            other guys."
  Machine: "Let me explain why this trade doesn't make sense for the franchise."
  Person:  "I keep coming back to one thing and I can't get past it. Who plays left
            tackle if they make that deal?"
  Machine: "In conclusion, he is the best quarterback in the league right now."
  Person:  "So yeah. Right now? It's him. And I'm not sure it's close."
  Machine: "His efficiency metrics are superior, which demonstrates greater value."
  Person:  "Look at what he does per snap this year. Then tell me who you'd rather have.
            Go ahead. I'll wait."
These show the kind of sound, not lines to reuse.

Charisma and persuasion (added Nov 6, 2026). They're the best on TV because people want
to keep listening:
- Conviction you can hear. They believe it, and they make the audience feel the
  stakes: what it means for a fan, a city, a season. Not just a number, why it matters.
- Lead with the strongest point, make the comparison vivid, and end on something that
  sticks, but not every turn; some turns end on a question, some just stop.
- Humor and warmth: a light jab, a self-deprecating line, a laugh at a good comeback.
  Never mean.
- Each in his own way: Royce is warm, story-led, and quotable; he paints it and lets it
  sit. Deacon is blunt and funny, with farm-country comparisons, and he'll laugh at
  himself. Lonnie disarms: a curious question that makes the other two stop and think,
  delivered calm, like he already knows the answer.

Write it so a reader could tell who's talking with the names hidden: each
host's voice, evidence lean, signature move, and temperature come from his
bible.

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
        "plan": {
            "type": "object",
            "description": "Written BEFORE the lines: how this argument builds.",
            "properties": {
                "cases": {"type": "object", "properties": {h: {"type": "object", "properties": {
                              "claim": {"type": "string", "description": "His position in one sentence."},
                              "supports": {"type": "array", "items": {"type": "string"},
                                           "description": "2 or 3 DIFFERENT supports, each a different kind of evidence "
                                                          "with its fact IDs (not the same stat restated)."},
                              "answer": {"type": "string", "description": "How he answers the strongest objection to his case."}},
                              "required": ["claim", "supports", "answer"], "additionalProperties": False}
                              for h in ("royce", "deacon", "lonnie")},
                          "required": ["royce", "deacon", "lonnie"], "additionalProperties": False,
                          "description": "Each host's complete case."},
                "beats": {"type": "array", "items": {"type": "string"},
                          "description": "3 or 4 beats, in order. Each one moves the argument somewhere new."},
            },
            "required": ["cases", "beats"],
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
    "required": ["format", "caller", "plan", "lines"],
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
               "Current teams and anything else about the real world: see the fact pack.\n" + season_progress())
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
        finals = "\n".join(f"{l['speaker_name']}: {l['text']}" for l in lines if l["speaker"] in judging.HOSTS)
        verdict = ("a tie" if result["tie"] else f"{judging.NAMES[result['winner']][1]} won"
                   + (" (a close call)" if result.get("close_call") else ""))
        close_context = (context + f"\n\nThese are Hal's closing lines. The judge's result is: {verdict}. Announcing "
                         "that result is SUPPORTED. When Hal reports what a host argued or still thinks ('Royce still "
                         "thinks...'), that's the host's opinion being reported, and it's SUPPORTED if the host said it "
                         f"in the script below. Only Hal's own statements of fact need the fact pack.\n\nWhat the hosts "
                         f"said:\n{finals}")

        def close_problems(c):
            return (linecheck.check_numbers(c, by_id_all, topic) + linecheck.check_scope(c, by_id_all)
                    + linecheck.check_stage_notes(c) + linecheck.check_claims(c, pack, close_context, client, effort="medium"))
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
    # Hal always signs off the same way, whatever the close writer did.
    signoff = f"That's the board. Thanks for the call, {caller['name']}."
    if len(close) > 1:
        close[-1]["text"], close[-1]["facts"] = signoff, []
    elif "that's the board" not in close[-1]["text"].lower().replace("’", "'"):
        close[-1]["text"] = close[-1]["text"].rstrip() + " " + signoff
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
    # The end card ("That's the board") shows only the winner: his argument (his own final
    # answer, which passed every check) and the key stats he leaned on, from the fact pack.
    winning_case = None
    if result["winner"]:
        w = result["winner"]
        mine = [l for l in lines if l["speaker"] == w]
        counts, first = {}, {}
        for i, l in enumerate(mine):
            for fid in l.get("facts", []):
                f = by_id.get(fid)
                if f and f["stat"] not in ("current_team", "tenure", "injuries", "game", "availability", "injury_history") and f.get("say"):
                    counts[fid] = counts.get(fid, 0) + 1
                    first.setdefault(fid, i)
        top = sorted(counts, key=lambda x: (-counts[x], first[x]))[:4]
        winning_case = {"host": w, "score": result["hosts"][w]["score"], "argument": mine[-1]["text"] if mine else "",
                        "stats": [{"subject": by_id[f]["subject"], "label": by_id[f]["label"], "say": by_id[f]["say"],
                                   "scope": by_id[f].get("scope", "")} for f in top]}

    # The receipts: every fact the segment used, and what it was checked against.
    receipts = []
    for fid in sorted(used, key=lambda x: int(x[1:]) if x[1:].isdigit() else 0):
        f = by_id.get(fid)
        if not f:
            continue
        receipts.append({"subject": f.get("subject"), "label": f.get("label"), "say": f.get("say"),
                         "scope": f.get("scope"), "source": f.get("source"),
                         "checked": f.get("checked_against") or "", "status": f.get("status")})
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
        "receipts": receipts,
        "winning_case": winning_case,
        "plan": data.get("plan"),
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
