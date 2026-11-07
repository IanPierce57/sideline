"""Voices (added Nov 6, 2026): Google Cloud Text-to-Speech, Chirp 3 HD voices.

Each line is voiced once, when the segment is made, and saved with it as an MP3, so the
rolling replay costs nothing. Google's free allowance is 1 million characters a month; a
segment is about 4,000, so a month of normal use is free. A local counter stops voicing at
900,000 characters in a calendar month, so it can never run into paid use.

The key lives in .env as GOOGLE_TTS_KEY (./set_key.sh google). Without it, nothing here
runs and the show plays with subtitles only, the way it always has.
"""

import base64
import hashlib
import json
import os
import re
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from .net import SSL            # certifi's certificates (Python on macOS doesn't trust HTTPS by default)

URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
VOICES_URL = "https://texttospeech.googleapis.com/v1/voices?languageCode=en-US"
CACHE = Path(__file__).resolve().parent.parent / ".cache" / "voices"
MONTHLY_CAP = 900_000          # stay under Google's 1,000,000 free characters a month

# Who sounds like whom (Chirp 3 HD voice names). Chosen to fit each bible: Hal smooth and
# unhurried, Royce clear and polished, Deacon gravelly, Lonnie friendly. Only the segment is
# voiced (user, Nov 6, 2026); the crew voices are only for the samples.
CAST = {
    "hal": "en-US-Chirp3-HD-Algieba",
    "royce": "en-US-Chirp3-HD-Iapetus",
    "deacon": "en-US-Chirp3-HD-Algenib",
    "lonnie": "en-US-Chirp3-HD-Achird",
    "producer": "en-US-Chirp3-HD-Orus",
    "artist": "en-US-Chirp3-HD-Sulafat",
}
# Callers get one of these, picked from the caller's name so the same caller always sounds the same.
CALLERS = ["en-US-Chirp3-HD-Puck", "en-US-Chirp3-HD-Zubenelgenubi", "en-US-Chirp3-HD-Sadachbia",
           "en-US-Chirp3-HD-Aoede", "en-US-Chirp3-HD-Kore", "en-US-Chirp3-HD-Laomedeia",
           "en-US-Chirp3-HD-Umbriel", "en-US-Chirp3-HD-Callirrhoe"]
# Each person's natural pace, nudged by how the line is delivered.
PACE = {"hal": 0.97, "royce": 1.0, "deacon": 1.03, "lonnie": 1.0, "caller": 1.02, "producer": 1.05, "artist": 1.0}
DELIVERY = {"heated": 1.07, "fired_up": 1.09, "slam": 1.07, "emphatic": 1.04, "exasperated": 1.03, "laughing": 1.04,
            "building": 1.02, "quiet": 0.94, "cold": 0.95, "calm": 0.98, "warm": 0.98, "conceding": 0.97}
SPOKEN = ("hal", "caller", "royce", "deacon", "lonnie")

_lock = threading.Lock()
_rate_ok = True                # set False if this voice type turns out not to take a speaking rate


def key() -> str:
    """Read fresh from .env each time, so a new key saved with set_key.sh works without a restart."""
    from dotenv import dotenv_values
    saved = dotenv_values(Path(__file__).resolve().parent.parent / ".env").get("GOOGLE_TTS_KEY") or ""
    return (saved or os.environ.get("GOOGLE_TTS_KEY", "")).strip()


def enabled() -> bool:
    return bool(key())


def voice_for(speaker: str, caller_name: str = "") -> str:
    if speaker == "caller":
        n = hashlib.md5((caller_name or "caller").encode()).digest()[0]
        return CALLERS[n % len(CALLERS)]
    return CAST.get(speaker, CAST["hal"])


# ---------- Subtitle cards (the same split the page used before voices) ----------

MAX_CARD = 170          # longer lines become two or more subtitle cards (static/app.js MAX_BUBBLE_CHARS)
ABBREV = re.compile(r"(?:^|\s)(?:jr|sr|st|vs|mr|mrs|dr|no|mt|ft|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
                    r"|a\.m|p\.m|u\.s)\.$", re.I)


def spoken(text: str) -> str:
    """The line without stage directions in parentheses (they drive the animation)."""
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", text)).strip()


def sentences(text: str) -> list[str]:
    """Split at real sentence ends. '0.37' and 'Jr.' don't end a sentence."""
    out, start = [], 0
    for m in re.finditer(r"[.!?]+[\"'’”)\]]*\s+", text):
        piece = text[start: m.start() + len(m.group(0).rstrip())]
        nxt = text[m.end()] if m.end() < len(text) else ""
        if ABBREV.search(piece) or not re.match(r"[A-Z0-9\"'“(]", nxt):
            continue
        out.append(piece.strip())
        start = m.end()
    if start < len(text):
        out.append(text[start:].strip())
    return [s for s in out if s]


def cards_for(text: str) -> list[str]:
    """The subtitle cards for one line: whole sentences, up to MAX_CARD characters each."""
    said = spoken(text)
    chunks, current = [], ""
    for s in sentences(said) or [said]:
        if current and len(current + " " + s) > MAX_CARD:
            chunks.append(current)
            current = s
        else:
            current = f"{current} {s}" if current else s
    if current or not chunks:
        chunks.append(current)
    return [c for c in chunks if c]


# ---------- What the voice reads (the subtitles keep the original text) ----------

SCORE_WORDS = re.compile(r"\b(beat|beats|won|win|wins|lost|loses|final|score|scored)\b", re.I)


def speech_text(text: str) -> str:
    """Say it the way a broadcaster would: '5-3' is 'five and three' for a record ('to' for a
    score), '2024-25' is 'twenty-four twenty-five', '+0.37' is 'plus point three seven'.
    Stage directions in parentheses aren't spoken."""
    t = re.sub(r"\([^)]*\)", " ", text)
    t = re.sub(r"\b20(\d\d)[–-](\d\d)\b", r"\1 \2", t)
    joiner = "to" if SCORE_WORDS.search(t) else "and"
    t = re.sub(r"(?<![\d.])(\d{1,3})[-–](\d{1,3})(?![\d-])", rf"\1 {joiner} \2", t)
    t = t.replace("ANY/A", "any-slash-A")
    t = re.sub(r"(?<![\w.])\+(?=\.?\d)", "plus ", t)
    t = re.sub(r"(?<![\w.])[-–](?=0?\.\d)", "minus ", t)
    t = re.sub(r"(?<![\d.])0\.(\d)", r".\1", t)
    t = re.sub(r"\s+([.,!?;:])(?!\d)", r"\1", t)          # no space before a period, but keep "plus .37"
    return re.sub(r"\s+", " ", t).strip()


# ---------- Talking to Google ----------

def _usage_file() -> Path:
    return CACHE / "usage.json"


def _use(chars: int) -> bool:
    """Count characters against this month's cap. False if this would go over."""
    month = date.today().strftime("%Y-%m")
    with _lock:
        CACHE.mkdir(parents=True, exist_ok=True)
        try:
            usage = json.loads(_usage_file().read_text())
        except (OSError, ValueError):
            usage = {}
        used = usage.get(month, 0)
        if used + chars > MONTHLY_CAP:
            return False
        usage[month] = used + chars
        _usage_file().write_text(json.dumps(usage))
        return True


def used_this_month() -> int:
    try:
        return json.loads(_usage_file().read_text()).get(date.today().strftime("%Y-%m"), 0)
    except (OSError, ValueError):
        return 0


def synthesize(text: str, voice: str, rate: float = 1.0) -> bytes:
    """One line of speech as MP3 bytes. The key goes in a header, never in the URL."""
    global _rate_ok
    if not _use(len(text)):
        raise RuntimeError("this month's free voice allowance is used up")
    config = {"audioEncoding": "MP3"}
    if _rate_ok and abs(rate - 1.0) > 0.005:
        config["speakingRate"] = round(rate, 2)
    body = {"input": {"text": text}, "voice": {"languageCode": "en-US", "name": voice}, "audioConfig": config}
    for attempt in range(3):
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-Goog-Api-Key": key()})
        try:
            with urllib.request.urlopen(req, timeout=40, context=SSL) as r:
                return base64.b64decode(json.loads(r.read())["audioContent"])
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code == 400 and "speakingRate" in config and "rate" in detail.lower():
                _rate_ok = False                      # this voice type doesn't take a rate: drop it
                config.pop("speakingRate")
                continue
            if e.code in (429, 500, 503) and attempt < 2:
                import time
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(f"Google said {e.code}: {detail}") from None
    raise RuntimeError("Google didn't answer")


def list_voices() -> list[dict]:
    req = urllib.request.Request(VOICES_URL, headers={"X-Goog-Api-Key": key()})
    with urllib.request.urlopen(req, timeout=20, context=SSL) as r:
        return json.loads(r.read()).get("voices", [])


# ---------- A whole segment ----------

def voice_script(script: dict, run_dir: Path, progress=lambda *a: None) -> dict:
    """Voice every spoken line into run_dir/audio/<line>.mp3 and mark the line with its file.
    A line that fails just plays as subtitles. Returns a short summary for the run's meta."""
    folder = run_dir / "audio"
    folder.mkdir(exist_ok=True)
    caller = (script.get("caller") or {}).get("name", "")
    jobs = []
    for line in script["lines"]:
        if line["speaker"] not in SPOKEN:
            continue
        rate = PACE.get(line["speaker"], 1.0) * DELIVERY.get(line.get("delivery", ""), 1.0)
        line["cards"] = [{"text": c, "audio": None} for c in cards_for(line["text"])]
        for i, card in enumerate(line["cards"]):
            text = speech_text(card["text"])
            if text:
                jobs.append((line, i, text, voice_for(line["speaker"], caller), rate))

    def one(job):
        line, i, text, voice, rate = job
        name = f"{line['line']}-{i}.mp3"
        try:
            (folder / name).write_bytes(synthesize(text, voice, rate))
            return line, i, name, len(text), None
        except Exception as problem:            # noqa: BLE001 - any failure means "subtitles only"
            return line, i, None, 0, f"{type(problem).__name__}: {problem}"

    voiced = chars = 0
    failed = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for line, i, name, n, problem in pool.map(one, jobs):
            if problem:
                failed.append({"line": line["line"], "card": i, "problem": problem})
            else:
                line["cards"][i]["audio"] = name
                voiced += 1
                chars += n
    progress("voiced", {"voiced": voiced, "failed": len(failed)})
    return {"voiced_cards": voiced, "cards": len(jobs), "characters": chars, "failed": failed[:5],
            "used_this_month": used_this_month()}
