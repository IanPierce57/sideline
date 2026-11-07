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

URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
VOICES_URL = "https://texttospeech.googleapis.com/v1/voices?languageCode=en-US"
CACHE = Path(__file__).resolve().parent.parent / ".cache" / "voices"
MONTHLY_CAP = 900_000          # stay under Google's 1,000,000 free characters a month

# Who sounds like whom (Chirp 3 HD voice names). Chosen to fit each bible: Hal smooth and
# unhurried, Royce clear and polished, Deacon gravelly, Lonnie friendly.
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
    if not os.environ.get("GOOGLE_TTS_KEY"):
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    return os.environ.get("GOOGLE_TTS_KEY", "").strip()


def enabled() -> bool:
    return bool(key())


def voice_for(speaker: str, caller_name: str = "") -> str:
    if speaker == "caller":
        n = hashlib.md5((caller_name or "caller").encode()).digest()[0]
        return CALLERS[n % len(CALLERS)]
    return CAST.get(speaker, CAST["hal"])


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
    t = re.sub(r"\s+([.,!?;:])", r"\1", t)
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
            with urllib.request.urlopen(req, timeout=40) as r:
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
    with urllib.request.urlopen(req, timeout=20) as r:
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
        text = speech_text(line["text"])
        if not text:
            continue
        rate = PACE.get(line["speaker"], 1.0) * DELIVERY.get(line.get("delivery", ""), 1.0)
        jobs.append((line, text, voice_for(line["speaker"], caller), rate))

    def one(job):
        line, text, voice, rate = job
        try:
            (folder / f"{line['line']}.mp3").write_bytes(synthesize(text, voice, rate))
            return line, len(text), None
        except Exception as problem:            # noqa: BLE001 - any failure means "subtitles only"
            return line, 0, f"{type(problem).__name__}: {problem}"

    voiced = chars = 0
    failed = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for line, n, problem in pool.map(one, jobs):
            if problem:
                failed.append({"line": line["line"], "problem": problem})
            else:
                line["audio"] = f"{line['line']}.mp3"
                voiced += 1
                chars += n
    progress("voiced", {"voiced": voiced, "failed": len(failed)})
    return {"voiced": voiced, "lines": len(jobs), "characters": chars, "failed": failed[:5],
            "used_this_month": used_this_month()}


# ---------- Short fixed lines on the page (the countdown, the pre-show crew) ----------

def say(who: str, text: str) -> bytes | None:
    """A short line for the page, voiced once and cached on disk. Only the cast and crew, and
    only short lines (the page asks for the countdown and pre-show lines)."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if not enabled() or who not in CAST or not text or len(text) > 120:
        return None
    voice = CAST[who]
    name = hashlib.sha1(f"{voice}|{text}".encode()).hexdigest()[:20] + ".mp3"
    path = CACHE / name
    if path.exists():
        return path.read_bytes()
    audio = synthesize(speech_text(text), voice, PACE.get(who, 1.0))
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(audio)
    return audio
