"""Tests for the line checker: made-up numbers must be caught, honest ones allowed.
Run: .venv/bin/python tests/linecheck_test.py   (free; no API calls)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import linecheck   # noqa: E402

ANYA = {"id": "F1", "stat": "any_a", "value": 5.383, "say": "5.38", "scope": "2026 regular season",
        "sample": "222 dropbacks", "definition": "Passing yards per dropback, with touchdowns worth 20 extra yards, "
        "interceptions costing 45, and sack yardage taken off."}
RECORD = {"id": "F2", "stat": "team_record", "value": {"wins": 6, "losses": 2, "ties": 0}, "say": "6-2",
          "scope": "2026 regular season", "sample": "8 games"}
FACTS = {f["id"]: f for f in (ANYA, RECORD)}
TOPIC = "Is Aaron Rodgers still a top-10 quarterback?"

CASES = [  # (speaker, text, cited facts, should it pass?)
    ("hal", "Is he still a top-10 quarterback?", [], True),
    ("deacon", "ANY/A gives 20 yards for a touchdown and takes 45 for a pick. He's at 5.38.", ["F1"], True),
    ("deacon", "He's at about 5.4 ANY/A this year.", ["F1"], True),
    ("royce", "Pittsburgh is 6-2.", ["F2"], True),
    ("deacon", "Thirteen seasons in the league taught me that.", [], True),
    ("royce", "He threw 41 touchdowns last year.", [], False),
    ("deacon", "He's at 6.1 ANY/A.", ["F1"], False),
    ("royce", "Pittsburgh is 7-1.", ["F2"], False),
    ("royce", "Thirteen touchdowns says enough.", [], False),
    ("lonnie", "He's at 5.38 ANY/A.", [], False),   # right number, but no fact cited
]

failures = 0
for n, (speaker, text, cited, should_pass) in enumerate(CASES, start=1):
    problems = linecheck.check_numbers([{"line": n, "speaker": speaker, "text": text, "facts": cited}], FACTS, TOPIC)
    passed = not problems
    ok = passed == should_pass
    failures += not ok
    print(f"[{'OK ' if ok else 'BAD'}] {'passes' if passed else 'flagged'}: {text}")
print("\nAll good." if not failures else f"\n{failures} case(s) wrong.")
sys.exit(1 if failures else 0)
