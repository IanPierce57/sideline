"""Tests for the news ticker's confirmation rules, on made-up sample headlines.
Run: .venv/bin/python tests/news_test.py   (free; no internet needed)"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import news   # noqa: E402

NOW = datetime(2026, 11, 5, 18, 0, tzinfo=timezone.utc)
H = lambda hours: (NOW - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")   # noqa: E731
A = lambda title, outlet, domain, hours=3: {"title": title, "publishedAt": H(hours), "url": f"https://{domain}/x",  # noqa: E731
                                            "source": {"name": outlet, "url": f"https://{domain}"}}
PLAYERS = ["Jacoby Brissett", "Jack Campbell", "Patrick Mahomes", "Myles Garrett", "Jonathan Taylor"]

ARTICLES = [
    A("Cardinals trade QB Jacoby Brissett to Ravens", "CBS Sports", "cbssports.com"),
    A("Ravens acquire Jacoby Brissett from Arizona after QB injuries", "Sports Illustrated", "si.com"),     # same story
    A("Lions LB Jack Campbell dealing with neck injury", "Yahoo Sports", "sports.yahoo.com"),
    A("Jack Campbell neck injury update: Lions linebacker questionable", "CBS Sports", "cbssports.com"),   # same story
    A("Patrick Mahomes throws three touchdowns in win", "Fox Sports", "foxsports.com"),                      # one outlet only
    A("NFL Week 10 picks: Chiefs over Bills", "USA Today", "usatoday.com"),                                 # opinion
    A("Myles Garrett placed on injured reserve", "ESPN", "espn.com"),                                       # banned outlet
    A("Myles Garrett placed on injured reserve", "AP", "apnews.com", hours=60),                             # too old
    A("League announces new broadcast deal", "Reuters", "reuters.com"),                                     # no player or team
    A("Bears and Packers combine for wild finish", "AP", "apnews.com"),
    A("Bears win wild finish over Packers on late field goal", "NBC Sports", "nbcsports.com"),              # same story (teams + win)
    A("New Jonathan Taylor trade rumors on Colts' asking price", "Bleacher Report", "bleacherreport.com"),  # rumor
    A("Vikings have potential Jonathan Taylor 'Plan B' at trade deadline", "Heavy", "heavy.com"),           # rumor: two rumors aren't a confirmation
]

kept, crossed = news.confirm(ARTICLES, "NFL", PLAYERS, now=NOW)
print("KEPT:")
for k in kept:
    print(f"  {k['text']}  ({', '.join(k['outlets'])})")
print("CROSSED OFF:")
for c in crossed:
    print(f"  {c['headline']}  -> {c['reason']}")

expected_kept = {"Brissett", "Campbell", "Bears"}
got = {w for w in expected_kept if any(w in k["text"] for k in kept)}
problems = []
if got != expected_kept:
    problems.append(f"expected stories about {sorted(expected_kept)}, got {sorted(got)}")
if any("Mahomes" in k["text"] or "picks" in k["text"] or "broadcast" in k["text"] or "Garrett" in k["text"] or "Taylor" in k["text"] for k in kept):
    problems.append("something that should have been crossed off got through")
if any(o == "ESPN" for k in kept for o in k["outlets"]):
    problems.append("a banned outlet appeared")
print("\nAll good." if not problems else "\nPROBLEMS: " + "; ".join(problems))
sys.exit(1 if problems else 0)
