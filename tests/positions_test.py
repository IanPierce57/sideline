"""Tests for the position glossary (pipeline/positions.py). Free; no internet.
Run: .venv/bin/python tests/positions_test.py

The rules come from the user (Nov 5, 2026): labels overlap, but not transitively.
An edge rusher can be called a linebacker, and a Mike is a linebacker, but a Mike
is never a defensive end."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import positions as P  # noqa: E402

CASES = [  # (listed as, other label, same player possible?)
    ("DE", "Outside linebacker", True), ("EDGE", "Linebacker", True), ("DL", "Linebacker", True),
    ("LB", "Outside linebacker / Defensive end", True), ("LB", "Defensive end", True),   # Micah Parsons
    ("MLB", "Defensive end", False), ("ILB", "Defensive tackle", False), ("Mike", "Defensive end", False),
    ("Mike", "Linebacker", True), ("Will", "Outside linebacker", True), ("LB", "Middle linebacker", True),
    ("RB", "Halfback", True), ("RB", "Fullback", True), ("HB", "Running back", True), ("RB", "Wide receiver", False),
    ("OT", "Guard", True), ("OT", "Offensive lineman", True), ("OT", "Center", False), ("OG", "Center", True),
    ("DB", "Cornerback", True), ("DB", "[[Safety (gridiron football position)|Safety]]", True),
    ("CB", "Nickelback", True), ("S", "Nickel", True), ("CB", "Safety", False),
    ("QB", "Linebacker", False), ("WR", "Cornerback", False), ("WR", "Wide receiver / Cornerback", True),
    ("TE", "Wide receiver", False), ("K", "Punter", True),
    ("PG", "Shooting guard", True), ("PG", "Center", False), ("SF", "Power forward", True),
]

bad = [(a, b, want) for a, b, want in CASES if P.matches_text(a, b) != want]
for a, b, want in bad:
    print(f"WRONG: {a} vs {b}: expected {'match' if want else 'no match'}")
print(f"{len(CASES) - len(bad)}/{len(CASES)} right")
print("\nAll good." if not bad else "\nPROBLEMS above.")
sys.exit(1 if bad else 0)
