"""Tests for style labels (pipeline/style.py): opinions don't need proof, but they must be
believable. Uses real data from nflverse and Sleeper; free, no AI calls.
Run: .venv/bin/python tests/style_test.py

Note: profiles use this season's numbers (or last season's if a player hasn't played
enough), so a borderline label could change as the season goes on."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import players, style  # noqa: E402

PLAYERS = [("Jared Goff", "nfl", "QB"), ("Lamar Jackson", "nfl", "QB"), ("Josh Allen", "nfl", "QB"),
           ("Caleb Williams", "nfl", "QB"), ("Bijan Robinson", "nfl", None), ("Myles Garrett", "nfl", None),
           ("Kyle Hamilton", "nfl", None), ("Stephen Curry", "nba", None), ("Nikola Jokic", "nba", None)]
CASES = [  # (line, should it be flagged?)
    ("Jared Goff is a dual-threat quarterback, plain and simple.", True),
    ("Lamar Jackson is a pocket passer.", True),
    ("Lamar Jackson is the ultimate dual threat.", False),
    ("Josh Allen is a gunslinger with a big arm.", False),
    ("Bijan Robinson is a workhorse and a pass-catching back.", False),
    ("Myles Garrett is the best pass rusher alive.", False),
    ("Kyle Hamilton is a ball hawk.", False),
    ("Stephen Curry is the greatest shooter on the planet.", False),
    ("Caleb Williams is exciting, he's fun to watch.", False),     # pure opinion: no rule applies
    ("Jared Goff takes care of the football.", False),
]

profiles = []
for name, sport, pos in PLAYERS:
    found = [m for m in players.find(name, sport)["matches"] if m["active"] and (not pos or m["position"] == pos)]
    p = style.profile(found[0]) if found else None
    if p:
        profiles.append(p)
    else:
        print(f"(no profile for {name})")
bad = []
for i, (text, want) in enumerate(CASES, start=1):
    got = bool(style.check_labels([{"line": i, "text": text}], profiles))
    print(("ok    " if got == want else "WRONG ") + ("flagged  " if got else "allowed  ") + text)
    if got != want:
        bad.append(text)
print("\nAll good." if not bad else f"\n{len(bad)} wrong.")
sys.exit(1 if bad else 0)
