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
HITS = {"id": "F3", "label": "QB hits", "stat": "qb_hits", "value": 12, "say": "12", "scope": "2026 regular season",
        "sample": "8 games"}
SACKS_2025 = {"id": "F4", "label": "sacks", "stat": "sacks", "value": 7, "say": "7", "scope": "2025 regular season",
              "sample": "17 games"}
ASSISTS = {"id": "F5", "label": "assists per game", "stat": "assists_per_game", "value": 7.9, "say": "7.9",
           "scope": "2025-26 regular season", "sample": "70 games"}
FACTS = {f["id"]: f for f in (ANYA, RECORD, HITS, SACKS_2025, ASSISTS)}
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
    # Numbers said with a noun must match a fact about that noun (audit, Nov 5, 2026)
    ("deacon", "Twelve hits in eight games this year.", ["F3", "F4"], True),
    ("deacon", "Twelve hits in seven games this year.", ["F3", "F4"], False),   # 7 is sacks, not games
    ("royce", "Seven sacks last season.", ["F4"], True),
    ("lonnie", "He's averaging 7.9 assists a game.", ["F5"], True),
    ("lonnie", "He's averaging seven assists a game.", ["F5"], False),          # 7.9 isn't seven
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
