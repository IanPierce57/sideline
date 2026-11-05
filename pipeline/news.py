"""The news ticker: today's NFL and NBA headlines, free, and every one confirmed.

Source: GNews (gnews.io), free plan. Its terms allow "personal, academic, evaluation,
and other non-commercial use" and "reasonable caching", which fits a class project.
Articles arrive about 12 hours late on the free plan; that's fine for "news of the day".

How headlines stay accurate (decided Nov 4, 2026), with no AI rewriting anything:
  - The ticker shows real headlines exactly as the outlets wrote them, with the outlet.
  - Two-outlet rule: headlines about the same story (the same current player, or the
    same team plus the same kind of news) are grouped; a story runs only if two or
    more different outlets report it. Anything else is crossed off.
  - Opinion isn't news: picks, odds, power rankings, mock drafts, and fantasy advice
    are skipped. So are banned outlets (ESPN, NFL.com, NBA.com; see SOURCES.md).
  - Today's news only.
Sleeper's most-added players fill in, credited to Sleeper. Refreshed at most every 6 hours.
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from . import sleeper
from .net import CACHE, get_json

CACHE_FILE = CACHE / "news.json"
MAX_AGE_SECONDS = 6 * 3600            # "for the day" is enough; this keeps us far under 100 requests a day
MAX_ARTICLE_AGE = timedelta(hours=36)  # the free plan runs ~12 hours behind

BLOCKED = ("espn.com", "espn.go.com", "nfl.com", "nba.com", "statmuse.com", "sports-reference.com",
           "pro-football-reference.com", "basketball-reference.com", "sumersports.com", "pff.com",
           "spotrac.com", "overthecap.com")
OPINION = re.compile(r"\b(picks?|odds|predictions?|predict|power rankings?|rankings|mock draft|fantasy|start/sit|"
                     r"start or sit|sleepers?|bets?|betting|parlay|props?|best bets|grades?|takeaways|"
                     r"overreactions?|winners and losers|what we learned|podcast|live updates|how to watch|tv channel|"
                     # rumors and guesses aren't confirmed news either (decided Nov 4, 2026)
                     r"rumou?rs?|rumored|reportedly|could|should|would|might|may|urged|pitch|proposed|potential|"
                     r"plan b|targets?|linked|interest(ed)?|eyeing|buzz|speculation|ideas?|options|"
                     r"markets?|kalshi|polymarket|promo|bonus|sportsbooks?|ranks?|ranked|trending)\b", re.I)
NEWS_WORDS = ("trade", "traded", "acquire", "acquires", "deal", "sign", "signs", "signed", "extension", "release",
              "released", "waive", "waived", "cut", "injury", "injured", "hurt", "out", "return", "returns",
              "questionable", "doubtful", "ruled out", "reserve", "suspend", "suspended", "fire", "fired", "hire",
              "hired", "record", "win", "wins", "beat", "beats", "loss", "rout", "upset", "streak", "retire", "debut")

NFL_TEAMS = ["Cardinals", "Falcons", "Ravens", "Bills", "Panthers", "Bears", "Bengals", "Browns", "Cowboys", "Broncos",
             "Lions", "Packers", "Texans", "Colts", "Jaguars", "Chiefs", "Raiders", "Chargers", "Rams", "Dolphins",
             "Vikings", "Patriots", "Saints", "Giants", "Jets", "Eagles", "Steelers", "49ers", "Seahawks",
             "Buccaneers", "Titans", "Commanders"]
NBA_TEAMS = ["Hawks", "Celtics", "Nets", "Hornets", "Bulls", "Cavaliers", "Mavericks", "Nuggets", "Pistons", "Warriors",
             "Rockets", "Pacers", "Clippers", "Lakers", "Grizzlies", "Heat", "Bucks", "Timberwolves", "Pelicans",
             "Knicks", "Thunder", "Magic", "76ers", "Sixers", "Suns", "Trail Blazers", "Blazers", "Kings", "Spurs",
             "Raptors", "Jazz", "Wizards"]


# ---------- Fetching (GNews) ----------

# Five narrow searches per league (10 articles each on the free plan) give more chances
# for two outlets to cover the same story. 10 searches every 6 hours = about 40 a day of
# the free plan's 100.
QUERIES = {league: [league, f"{league} injury OR injured", f"{league} trade OR traded OR acquires",
                    f"{league} signs OR signed OR released OR waived", f"{league} beat OR beats OR defeat"]
           for league in ("NFL", "NBA")}


def _gnews(query: str, key: str) -> list[dict]:
    """One GNews search. The free plan turns away requests sent too close together,
    so they're spaced out, retried once after a pause, and skipped if they still fail
    (a missing query just means fewer headlines, never made-up ones)."""
    url = "https://gnews.io/api/v4/search?" + urllib.parse.urlencode(
        {"q": query, "lang": "en", "country": "us", "max": 10, "sortby": "publishedAt", "apikey": key})
    name = "gnews/" + re.sub(r"\W+", "_", query)
    for attempt in range(2):
        time.sleep(2 if attempt == 0 else 5)
        try:
            return get_json(url, name, max_age_hours=MAX_AGE_SECONDS / 3600).get("articles", [])
        except urllib.error.HTTPError as e:
            if e.code != 429:
                break                    # don't print the error: its URL contains the key
        except OSError:
            break
    return []


# ---------- Confirming ----------

def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _names(sport: str) -> list[str]:
    """Full names of current players, for spotting who a headline is about."""
    return [p["full_name"] for p in sleeper.players(sport).values()
            if p.get("full_name") and p.get("team") and len(p["full_name"]) > 6]


def _entities(title: str, player_names: list[str], teams: list[str]):
    low = title.lower()
    people = {n for n in player_names if n.lower() in low}
    team_hits = {t for t in teams if re.search(r"\b" + re.escape(t.lower()) + r"\b", low)}
    kinds = {w for w in NEWS_WORDS if re.search(r"\b" + re.escape(w) + r"\b", low)}
    return people, team_hits, kinds


def confirm(articles: list[dict], league: str, player_names: list[str], now: datetime | None = None):
    """Group articles into stories and keep the ones two or more outlets report.
    Returns (kept, crossed_off). Pure logic, so it can be tested without the internet."""
    now = now or datetime.now(timezone.utc)
    teams = NFL_TEAMS if league == "NFL" else NBA_TEAMS
    usable, crossed = [], []
    for a in articles:
        title = (a.get("title") or "").strip()
        source = a.get("source") or {}
        outlet = source.get("name") or _domain(a.get("url", ""))
        domain = _domain(source.get("url") or a.get("url", ""))
        if any(domain.endswith(b) for b in BLOCKED):
            continue                                   # banned outlets never appear
        if OPINION.search(title):
            crossed.append({"headline": title, "reason": "opinion, rumor, or betting, not news"})
            continue
        try:
            published = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if now - published > MAX_ARTICLE_AGE:
            crossed.append({"headline": title, "reason": "older than today's news"})
            continue
        people, team_hits, kinds = _entities(title, player_names, teams)
        if not people and not team_hits:
            crossed.append({"headline": title, "reason": "no current player or team named"})
            continue
        usable.append({"title": title, "outlet": outlet, "domain": domain, "published": published,
                       "people": people, "teams": team_hits, "kinds": kinds})

    # Same story = the same named player, the same two teams (one game), or the same
    # team plus the same kind of news (a trade, an injury, a signing...).
    stories = []
    for a in usable:
        for s in stories:
            shared_teams = a["teams"] & s["teams"]
            if (a["people"] & s["people"]) or len(shared_teams) >= 2 or (shared_teams and (a["kinds"] & s["kinds"])):
                s["articles"].append(a)
                s["people"] |= a["people"]
                s["teams"] |= a["teams"]
                s["kinds"] |= a["kinds"]
                break
        else:
            stories.append({"articles": [a], "people": set(a["people"]), "teams": set(a["teams"]),
                            "kinds": set(a["kinds"])})

    kept = []
    for s in stories:
        outlets = []
        for a in sorted(s["articles"], key=lambda x: x["published"], reverse=True):
            if a["domain"] not in [d for _, d in outlets]:
                outlets.append((a["outlet"], a["domain"]))
        lead = min(s["articles"], key=lambda x: len(x["title"]))     # the plainest headline
        if len(outlets) >= 2:
            kept.append({"league": league, "text": lead["title"][:120], "outlets": [o for o, _ in outlets[:3]],
                         "published": max(a["published"] for a in s["articles"]).isoformat()})
        else:
            crossed.append({"headline": lead["title"], "reason": "only one outlet reported it"})
    kept.sort(key=lambda k: k["published"], reverse=True)
    return kept, crossed


# ---------- Sleeper trending ----------

def _trending() -> list[dict]:
    """Sleeper's most-added players today, credited to Sleeper."""
    items = []
    for sport in ("nfl", "nba"):
        try:
            rows = sleeper.trending(sport, "add", 5)
        except Exception:
            continue
        names = []
        for r in rows:
            p = sleeper.players(sport).get(str(r.get("player_id")))
            if p and p.get("full_name"):
                names.append(f"{p['full_name']} ({p.get('team') or 'FA'})")
        if names:
            items.append({"league": sport.upper(), "text": "Most added in fantasy today: " + ", ".join(names[:4]),
                          "outlets": ["Sleeper"]})
    return items


def headlines(force: bool = False) -> dict:
    """Confirmed headlines plus Sleeper trending, refreshed at most every 6 hours."""
    if CACHE_FILE.exists() and not force:
        cached = json.loads(CACHE_FILE.read_text())
        if time.time() - cached.get("fetched", 0) < MAX_AGE_SECONDS:
            return cached
    key = os.environ.get("GNEWS_API_KEY", "").strip()
    result = {"headlines": [], "crossed_off": [], "fetched": time.time(), "trending": _trending(),
              "note": "" if key else "No GNews key yet: run ./set_key.sh gnews"}
    if key:
        for league, queries in QUERIES.items():
            articles, seen = [], set()
            for q in queries:
                for a in _gnews(q, key):
                    if a.get("url") not in seen:
                        seen.add(a.get("url"))
                        articles.append(a)
            kept, crossed = confirm(articles, league, _names(league.lower()))
            result["headlines"] += kept[:6]
            result["crossed_off"] += crossed
    CACHE_FILE.write_text(json.dumps(result, indent=1, default=str))
    return result
