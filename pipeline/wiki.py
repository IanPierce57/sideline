"""Wikipedia and Wikidata, for career honors (titles and awards).

Wikipedia's content is licensed CC BY-SA 4.0 and its API is meant for programs;
credit: "Honors: Wikipedia". Wikidata (CC0) is used as a cross-check where it
records the same award. Requests identify the app with a User-Agent, per
Wikimedia's policy, and are cached for a day."""

import json
import re
import threading
import time
import urllib.parse
import urllib.request
from functools import lru_cache

from .net import CACHE, SSL

UA = "SidelineClassProject/0.1 (non-commercial student project; data cached daily)"

# How Wikipedia's infobox names an honor -> (our key, label, Wikidata award label or None)
HONORS = [
    # (pattern on the infobox line, our key, label, Wikidata award, Wikipedia page that lists every winner)
    (r"super bowl champion", "sb_champion", "Super Bowl champion", None, None),
    (r"super bowl (most valuable player|mvp)", "sb_mvp", "Super Bowl MVP",
     "Super Bowl Most Valuable Player Award", "Super Bowl Most Valuable Player Award"),
    (r"^(ap )?nfl most valuable player|national football league most valuable player", "nfl_mvp", "NFL MVP",
     "National Football League Most Valuable Player Award", "Associated Press NFL Most Valuable Player Award"),
    (r"^(ap )?nfl offensive player of the year", "opoy", "NFL Offensive Player of the Year",
     "AP NFL Offensive Player of the Year Award", "Associated Press NFL Offensive Player of the Year Award"),
    (r"^(ap )?nfl defensive player of the year", "dpoy_nfl", "NFL Defensive Player of the Year",
     "AP NFL Defensive Player of the Year Award", "Associated Press NFL Defensive Player of the Year Award"),
    (r"^nba champion", "nba_champion", "NBA champion", None, None),
    (r"^nba finals (most valuable player|mvp)", "finals_mvp", "NBA Finals MVP",
     "Bill Russell NBA Finals Most Valuable Player Award", "Bill Russell NBA Finals Most Valuable Player Award"),
    (r"^nba most valuable player", "nba_mvp", "NBA MVP", "NBA Most Valuable Player Award", "NBA Most Valuable Player Award"),
    (r"^nba defensive player of the year", "dpoy_nba", "NBA Defensive Player of the Year",
     "NBA Defensive Player of the Year Award", "NBA Defensive Player of the Year Award"),
    (r"^pro bowl", "pro_bowl", "Pro Bowl selection", None, None),
    (r"^nba all-star( |$|\()", "all_star", "NBA All-Star selection", None, None),
    (r"^first-team all-pro", "all_pro_1", "First-team All-Pro", None, None),
]


_LOCK = threading.Lock()   # one request at a time, politely spaced (Wikimedia asks for this)


def _get(url: str, cache_name: str):
    path = CACHE / "wiki" / f"{cache_name}.json"
    if path.exists() and time.time() - path.stat().st_mtime < 24 * 3600:
        return json.loads(path.read_text())
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with _LOCK:
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=30, context=SSL) as response:
                    data = json.loads(response.read())
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 3:
                    raise
                time.sleep(3 * (attempt + 1))     # asked to slow down: wait and retry
        time.sleep(1.0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def _page(title: str):
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "prop": "revisions|pageprops", "rvprop": "content", "rvslots": "main",
        "titles": title, "format": "json", "formatversion": 2, "redirects": 1})
    page = _get(url, "page_" + re.sub(r"\W+", "_", title))["query"]["pages"][0]
    if page.get("missing"):
        return None
    text = page["revisions"][0]["slots"]["main"]["content"]
    return {"title": page["title"], "text": text, "qid": page.get("pageprops", {}).get("wikibase_item")}


POSITIONS = {"QB": "quarterback", "RB": "running back", "WR": "wide receiver", "TE": "tight end", "K": "kicker",
             "P": "punter", "LB": "linebacker", "DE": "defensive end", "DT": "defensive tackle", "DL": "defensive",
             "CB": "cornerback", "S": "safety", "DB": "back", "OL": "", "OT": "tackle", "G": "guard", "C": "center",
             "PG": "guard", "SG": "guard", "SF": "forward", "PF": "forward", "F": "forward"}


def find_page(name: str, league: str, position: str | None = None):
    """The player's Wikipedia page. It must have the right sport's infobox and, when we
    know his position, list that position, so a same-name page can't slip in."""
    boxes = ("infobox gridiron football biography", "infobox nfl biography") if league == "NFL" else ("infobox basketball biography",)
    word = POSITIONS.get(position or "", "")
    suffixes = ["", f" ({word})" if word else None, " (American football)" if league == "NFL" else " (basketball)"]
    for suffix in [x for x in suffixes if x is not None]:
        page = _page(name + suffix)
        if not page or not any(box in page["text"].lower() for box in boxes):
            continue
        infobox_position = re.search(r"\|\s*position\s*=([^\n]*)", page["text"])
        if word and infobox_position and word not in infobox_position.group(1).lower():
            continue                      # same name, different position: a different player
        return page
    return None


def _clean(line: str) -> str:
    line = re.sub(r"\{\{efn[^}]*\}\}", "", line)
    line = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^/]*/>", "", line)
    # {{nbay|2014|end}} means the 2014-15 season, shown as 2015; {{nbay|2014}} means "2014-15"
    line = re.sub(r"\{\{nbay\|(\d{4})\|end\}\}", lambda m: str(int(m.group(1)) + 1), line)
    line = re.sub(r"\{\{nbay\|(\d{4})(?:\|[^}]*)?\}\}", lambda m: f"{m.group(1)}–{(int(m.group(1)) + 1) % 100:02d}", line)
    line = re.sub(r"\{\{nasg\|(\d{4})(?:\|[^}]*)?\}\}", r"\1", line)
    line = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", line)
    line = re.sub(r"\{\{[^}]*\}\}", "", line)
    return re.sub(r"\s+", " ", line).strip()


def honors(name: str, league: str, position: str | None = None) -> dict:
    """{'page', 'qid', 'items': {key: {'label', 'count', 'years', 'wikidata'}}} from the infobox."""
    page = find_page(name, league, position)
    if not page:
        return {"page": None, "qid": None, "items": {}}
    m = re.search(r"\|\s*highlights\s*=(.*?)\n\s*\|\s*[a-z_]+\s*=", page["text"], re.S)
    lines = [_clean(x) for x in re.findall(r"^\s*\*+\s*(.+)$", m.group(1), re.M)] if m else []
    items = {}
    for line in lines:
        low = line.lower()
        count_match = re.match(r"(\d+)\s*×\s*", line)
        count = int(count_match.group(1)) if count_match else 1
        body = re.sub(r"^\d+\s*×\s*", "", low)
        for pattern, key, label, wikidata, list_page in HONORS:
            if re.search(pattern, body) and key not in items:
                years = re.findall(r"\b(?:19|20)\d\d(?:–\d\d)?\b", line)
                items[key] = {"label": label, "count": count, "years": years, "wikidata": wikidata,
                              "list_page": list_page, "line": line}
                break
    return {"page": page["title"], "qid": page["qid"], "items": items}


def wikidata_award_count(qid: str, award_label: str):
    """How many times Wikidata says this person received the award (None if it lists none)."""
    n = _award_counts(qid).get(award_label, 0)
    return n or None


@lru_cache(maxsize=64)
def _award_counts(qid: str) -> dict:
    """Every award Wikidata lists for this person, with how many times."""
    ent = _get(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json", f"wd_{qid}")["entities"][qid]
    ids = [c["mainsnak"]["datavalue"]["value"]["id"] for c in ent.get("claims", {}).get("P166", [])
           if c["mainsnak"].get("datavalue")]
    if not ids:
        return {}
    unique = list(dict.fromkeys(ids))
    labels = {}
    for i in range(0, len(unique), 45):
        chunk = unique[i:i + 45]
        url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "wbgetentities", "ids": "|".join(chunk), "props": "labels", "languages": "en", "format": "json"})
        got = _get(url, "wdl_" + "_".join(chunk)[:120])["entities"]
        labels.update({k: v.get("labels", {}).get("en", {}).get("value") for k, v in got.items()})
    counts = {}
    for i in ids:
        if labels.get(i):
            counts[labels[i]] = counts.get(labels[i], 0) + 1
    return counts

