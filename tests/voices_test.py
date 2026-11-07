"""Voices: does everyone sound different, and will the lines read right?

Free checks (no key needed):
  - every character has his own voice, and no caller can sound like a host or the crew
  - numbers are read the way a broadcaster says them
  - long lines split into the same subtitle cards the page shows
With the Google key saved (./set_key.sh google), it also asks Google for its voice list and
checks that every voice we use exists. Add --samples to save one short sample per character
to tests/voice_samples/ so you can listen (a few hundred characters of the free allowance).

Run: .venv/bin/python tests/voices_test.py [--samples]"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import voices  # noqa: E402

failures = []


def check(ok, what):
    print(f"[{'OK ' if ok else 'BAD'}] {what}")
    if not ok:
        failures.append(what)


# 1. Everyone sounds different
cast = list(voices.CAST.values())
check(len(set(cast)) == len(cast), f"each cast and crew member has his own voice ({len(cast)} voices)")
check(not set(voices.CALLERS) & set(cast), "no caller shares a voice with the cast or crew")
check(len(set(voices.CALLERS)) == len(voices.CALLERS), "the caller voices are all different")
check(voices.voice_for("caller", "Dana") == voices.voice_for("caller", "Dana"), "the same caller always gets the same voice")

# 2. Read like a broadcaster
for said, heard in [("Philly's 8-1 this year.", "Philly's 8 and 1 this year."),
                    ("They beat Dallas 31-28.", "They beat Dallas 31 to 28."),
                    ("In the 2024–25 season.", "In the 24 25 season."),
                    ("He's at +0.37 EPA.", "He's at plus .37 EPA."),
                    ("He was -0.54 per carry.", "He was minus .54 per carry."),
                    ("A 2-time All-Pro, 3-for-10 tonight.", "A 2-time All-Pro, 3-for-10 tonight."),
                    ("Seven of seven (pencil down).", "Seven of seven."),
                    ("Who wins Bengals vs. Falcons on Sunday, Nov. 8?", "Who wins Bengals versus Falcons on Sunday, November 8?"),
                    ("He's No. 1 in EPA, #2 in yards, offense & defense.", "He's number 1 in EPA, number 2 in yards, offense and defense.")]:
    got = voices.speech_text(said)
    check(got == heard, f"reads {said!r} as {heard!r}" + ("" if got == heard else f" (got {got!r})"))

# 3. Subtitle cards
long_line = ("Listen here. Right now he's at 53.8 true shooting, that's scoring efficiency counting threes and "
             "free throws, and Luka's at 68.5. Shai's at 55.8. He's shooting 41.4 from the field. That's a lot of "
             "shots for that kind of return.")
cards = voices.cards_for(long_line)
check(all(len(c) <= voices.MAX_CARD for c in cards) and " ".join(cards) == long_line,
      f"a long line splits into {len(cards)} whole-sentence cards with nothing lost")
check(voices.cards_for("Jr. Smith said 0.37. Nah.") == ["Jr. Smith said 0.37. Nah."], "'Jr.' and '0.37' don't end a card")

# 4. With the key: every voice exists at Google
if voices.enabled():
    try:
        available = {v["name"]: v for v in voices.list_voices()}
        for who, name in list(voices.CAST.items()) + [("caller", n) for n in voices.CALLERS]:
            v = available.get(name)
            check(v is not None, f"{who}: {name} exists" + (f" ({v.get('ssmlGender', '?').lower()})" if v else ""))
    except Exception as problem:
        check(False, f"couldn't reach Google's voice list ({type(problem).__name__}: {problem})")
    if "--samples" in sys.argv:
        out = Path(__file__).resolve().parent / "voice_samples"
        out.mkdir(exist_ok=True)
        lines = {"hal": "You're on the Sideline. Go ahead, caller.",
                 "royce": "Fourteen and three as a starter. That's the record, and the record doesn't lie.",
                 "deacon": "Listen here. That's a team result, and I won't hang it on one player.",
                 "lonnie": "Okay, but what's the actual decision here? Who plays the snaps next week?",
                 "producer": "Quiet on set! In three...", "artist": "Chin up for me."}
        for who, text in lines.items():
            (out / f"{who}.mp3").write_bytes(voices.synthesize(text, voices.CAST[who], voices.PACE.get(who, 1.0)))
        (out / "caller.mp3").write_bytes(voices.synthesize("My brother and I have argued about this all week.",
                                                           voices.CALLERS[0], voices.PACE["caller"]))
        print(f"Samples saved in {out} (one per character).")
else:
    print("(No Google key saved yet, so the voice list and samples were skipped.)")

print("\nAll good." if not failures else f"\n{len(failures)} problem(s).")
sys.exit(1 if failures else 0)
