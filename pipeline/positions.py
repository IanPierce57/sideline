"""One glossary of position names, so every check treats position labels the same way
(decided Nov 5, 2026, from the user's football knowledge).

Sources label the same player differently: Micah Parsons is "LB" on Sleeper and
"Outside linebacker / Defensive end" on Wikipedia; Kyle Hamilton is "DB" on Sleeper
and "Safety" on Wikipedia. So we keep a list of which labels can stand in for which.

The list is NOT transitive. An edge rusher like Myles Garrett can be called a
linebacker, and a Mike linebacker is a linebacker, but that doesn't make a Mike
linebacker a defensive end. Each pair below is checked on its own; we never chain
pairs together.

Used to make sure a same-name record or page is the right player (a quarterback's
Wikipedia page can't be mistaken for a linebacker's)."""

import re

# Written forms -> one short label. Longest phrases are matched first.
WORDS = {
    "quarterback": "QB",
    "running back": "RB", "halfback": "HB", "tailback": "TB", "fullback": "FB", "h-back": "HBACK",
    "wide receiver": "WR", "slot receiver": "SLOT", "flanker": "WR", "split end": "WR", "receiver": "WR",
    "tight end": "TE",
    "offensive tackle": "OT", "left tackle": "OT", "right tackle": "OT", "offensive guard": "OG", "guard": "OG",
    "center": "C", "centre": "C", "offensive lineman": "OL", "offensive line": "OL",
    "edge rusher": "EDGE", "edge": "EDGE", "pass rusher": "EDGE",
    "defensive end": "DE", "defensive tackle": "DT", "nose tackle": "NT", "defensive lineman": "DL", "defensive line": "DL",
    "outside linebacker": "OLB", "inside linebacker": "ILB", "middle linebacker": "MLB", "off-ball linebacker": "ILB",
    "mike linebacker": "MIKE", "will linebacker": "WILL", "sam linebacker": "SAM", "mike": "MIKE", "will": "WILL",
    "sam": "SAM", "linebacker": "LB",
    "cornerback": "CB", "corner": "CB", "slot corner": "NICKEL", "nickelback": "NICKEL", "nickel back": "NICKEL",
    "nickel": "NICKEL", "star": "NICKEL", "free safety": "FS", "strong safety": "SS", "safety": "S",
    "defensive back": "DB", "dime back": "DB",
    "placekicker": "K", "place kicker": "K", "kicker": "K", "punter": "P", "long snapper": "LS",
    "point guard": "PG", "shooting guard": "SG", "combo guard": "G", "small forward": "SF", "power forward": "PF",
    "forward": "F", "wing": "SF",
}
CODES = {"T": "OT", "G": "OG", "PK": "K", "SAF": "S", "NB": "NICKEL", "DI": "DL", "IOL": "OL", "LT": "OT", "RT": "OT",
         "LG": "OG", "RG": "OG", "GF": "G-F", "FC": "F-C", "F-G": "G-F", "C-F": "F-C"}

# Who can also be called what. Each line is one direction's list; the pairs are made
# two-way below (if an OT can be called an OG, an OG can be called an OT), but never chained.
CAN_BE = {
    # offense
    "RB": {"HB", "TB", "FB"},          # a running back is a halfback, sometimes a fullback
    "HB": {"TB", "FB"},
    "FB": {"HBACK"},
    "TE": {"HBACK"},
    "WR": {"SLOT"},
    "OL": {"OT", "OG", "C"},           # any offensive lineman
    "OT": {"OG"},                      # tackles sometimes play guard
    "OG": {"C"},                       # guards sometimes play center
    # defensive front: edge rushers sit between the line and the linebackers
    "EDGE": {"DE", "OLB", "DL", "LB", "SAM"},
    "DE": {"DL", "OLB", "LB", "DT"},   # Garrett, Parsons: DE, OLB, or LB; 3-4 ends play inside too
    "DT": {"DL", "NT"},
    "NT": {"DL"},
    "DL": {"OLB", "LB"},               # a team's "DL" label can cover edge rushers listed as linebackers
    # linebackers: off-ball linebackers are NOT defensive linemen
    "LB": {"OLB", "ILB", "MLB", "MIKE", "WILL", "SAM"},
    "OLB": {"SAM", "WILL"},
    "ILB": {"MLB", "MIKE", "WILL"},
    "MLB": {"MIKE"},
    # secondary
    "DB": {"CB", "S", "FS", "SS", "NICKEL"},
    "CB": {"NICKEL"},
    "S": {"FS", "SS", "NICKEL"},
    # special teams
    "K": {"P"},                        # some kickers punt
    # basketball: neighbors overlap, the ends don't (a point guard isn't a center)
    "G": {"PG", "SG", "G-F"},
    "PG": {"SG"},
    "SG": {"SF", "G-F"},
    "SF": {"F", "PF", "G-F"},
    "F": {"PF", "G-F", "F-C"},
    "PF": {"C", "F-C"},
    "C": {"F-C"},
}
_PAIRS = {(a, b) for a, bs in CAN_BE.items() for b in bs} | {(b, a) for a, bs in CAN_BE.items() for b in bs}

# The plainest word for each label, used for Wikipedia titles like "Josh Allen (quarterback)".
TITLE_WORD = {"QB": "quarterback", "RB": "running back", "HB": "running back", "FB": "fullback", "WR": "wide receiver",
              "TE": "tight end", "K": "kicker", "P": "punter", "LB": "linebacker", "OLB": "linebacker",
              "ILB": "linebacker", "MLB": "linebacker", "DE": "defensive end", "EDGE": "defensive end",
              "DT": "defensive tackle", "NT": "defensive tackle", "DL": "defensive end", "CB": "cornerback",
              "S": "safety", "FS": "safety", "SS": "safety", "DB": "cornerback", "OT": "offensive tackle",
              "OG": "guard", "C": "center", "OL": "offensive tackle"}


def label(text: str | None):
    """A code or written position -> one short label ('Outside linebacker' -> 'OLB'). None if unknown."""
    if not text:
        return None
    t = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", text)          # [[Safety (...)|Safety]] -> Safety
    t = re.sub(r"\(.*?\)", "", t).strip()
    code = t.upper()
    if code in CODES:
        return CODES[code]
    if code in {a for a, _ in _PAIRS} | set(CAN_BE) | {"QB", "WR", "TE", "LS"}:
        return code
    low = t.lower()
    for phrase in sorted(WORDS, key=len, reverse=True):
        if re.search(r"\b" + re.escape(phrase) + r"\b", low):
            return WORDS[phrase]
    return None


def can_be(a: str | None, b: str | None) -> bool:
    """True if a player listed as a can also be listed as b (one pair, no chaining).
    An unknown label doesn't block a match."""
    la, lb = label(a), label(b)
    return la is None or lb is None or la == lb or (la, lb) in _PAIRS


def matches_text(code: str | None, text: str) -> bool:
    """True if any position in a written list ("Wide receiver / Cornerback") can be
    this player's listed position. Empty text doesn't block."""
    if not code or not text.strip():
        return True
    parts = [p for p in re.split(r"\s*(?:/|,|;|\bor\b|\band\b|<br\s*/?>)\s*", text, flags=re.I) if p.strip()]
    known = [p for p in parts if label(p)]
    return not known or any(can_be(code, p) for p in known)
