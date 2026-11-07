"""
server.py: the small local web server.

It does three things:
  - serves the webpage in static/
  - POST /api/generate   starts a segment for a topic and returns a job ID right away
  - GET  /api/job/<id>   the job's progress (for the pre-show control room), then its script
  - GET  /api/runs       lists saved scripts, and GET /api/runs/<name> loads one

It only listens on your own computer (127.0.0.1), so nobody else can reach it.
"""

import json
import re
import threading
import time
import traceback
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

from generate import RUNS, TopicProblem, generate_script

PROJECT = Path(__file__).parent
STATIC = PROJECT / "static"
PORT = 8000
RUN_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")

# Segments being made right now, by job ID. Each one runs in its own thread.
JOBS = {}
JOBS_LOCK = threading.Lock()


# The news ticker. The page never waits on a refresh: it gets whatever is cached,
# and a stale cache is refreshed in the background (at most once an hour).
NEWS_LOCK = threading.Lock()


def _refresh_news() -> None:
    from dotenv import load_dotenv
    from pipeline import news
    load_dotenv(PROJECT / ".env")
    if not NEWS_LOCK.acquire(blocking=False):
        return                      # a refresh is already running
    try:
        news.headlines(force=True)
    except Exception:
        traceback.print_exc()
    finally:
        NEWS_LOCK.release()


_UPCOMING = {"at": 0, "data": None}


def upcoming_for_page() -> dict:
    """Real upcoming games for the try-questions and the right-hand monitor, from the same
    schedules the game finder uses (NFL: the next two weeks; NBA: the next week). Saved for
    30 minutes."""
    if _UPCOMING["data"] and time.time() - _UPCOMING["at"] < 1800:
        return _UPCOMING["data"]
    from datetime import date
    out = {"games": [], "questions": []}
    try:
        from pipeline import games, nba
        today = date.today()
        nfl = games._upcoming(today).sort(["gameday", "gametime"]).head(4)
        for g in nfl.iter_rows(named=True):
            home = games.FROM_NFLVERSE.get(g["home_team"], g["home_team"])
            away = games.FROM_NFLVERSE.get(g["away_team"], g["away_team"])
            d = date.fromisoformat(g["gameday"])
            out["games"].append({"league": "NFL", "text": f"{games.nickname(away)} at {games.nickname(home)}",
                                 "when": f"{d:%a} {d:%b} {d.day}"})
        for g in nba._upcoming(today)[:4]:
            d = date.fromisoformat(g["date"])
            out["games"].append({"league": "NBA", "text": f"{nba.TEAMS[g['away']['team']][1]} at {nba.TEAMS[g['home']['team']][1]}",
                                 "when": f"{d:%a} {d:%b} {d.day}"})
        # Up to four of each league, mixed NFL / NBA, so the try-questions can rotate
        nfl_q, nba_q = games.upcoming_games([], limit=4), nba.upcoming_games([], limit=4)
        out["questions"] = [q for pair in zip(nfl_q + [None] * 4, nba_q + [None] * 4) for q in pair if q]
    except Exception as problem:            # a schedule hiccup shouldn't break the page
        out["note"] = type(problem).__name__
    _UPCOMING.update(at=time.time(), data=out)
    return out


def news_for_page() -> dict:
    from pipeline import news
    cached = json.loads(news.CACHE_FILE.read_text()) if news.CACHE_FILE.exists() else {}
    if time.time() - cached.get("fetched", 0) > news.MAX_AGE_SECONDS:
        threading.Thread(target=_refresh_news, daemon=True).start()
    return {"headlines": cached.get("headlines", []), "fetched": cached.get("fetched")}


def run_job(job_id: str, topic: str, chosen: list) -> None:
    job = JOBS[job_id]

    def progress(event: str, details: dict) -> None:
        with JOBS_LOCK:
            if event == "step":
                job["step"] = details
            elif event == "pulled":
                job["counts"]["found"] += 1
                job["recent"] = f"{details.get('subject')}: {details.get('label') or details.get('stat')}"
            elif event == "checked":
                ok = str(details.get("status", "")).startswith(("verified", "trusted"))
                job["counts"]["verified" if ok else "dropped"] += 1
            elif event == "verified":
                job["counts"].update(found=details["found"], verified=details["passed"], dropped=details["dropped"])
            elif event == "line_check":
                job["counts"]["lines_checked"] = details["checked"]
                job["counts"]["lines_flagged"] = details["flagged"]
            elif event == "line_fix":
                job["counts"].update(lines_rewritten=details["rewritten"], lines_cut=details["cut"])
            elif event == "topic":
                job["players"] = details["players"]

    try:
        run_dir, script = generate_script(topic, progress, chosen)
        script["run"] = run_dir.name
        print(f"  saved {run_dir.relative_to(PROJECT)}/script.json")
        with JOBS_LOCK:
            job.update(state="done", script=script)
    except TopicProblem as problem:
        with JOBS_LOCK:
            job.update(state="topic", topic=problem.details)
    except anthropic.AuthenticationError:
        with JOBS_LOCK:
            job.update(state="error", error="Your API key was rejected. Run set_key.sh again.")
    except anthropic.APIConnectionError:
        with JOBS_LOCK:
            job.update(state="error", error="Couldn't reach the Claude API. Check your internet.")
    except anthropic.APIStatusError as problem:
        # Plain words for the ones that can happen on demo day (Nov 7, 2026)
        text = str(problem).lower()
        if "credit balance" in text:
            message = "The desk is out of Claude API credits. Add credits at console.anthropic.com (Plans & Billing), then ask again."
        elif problem.status_code == 429:
            message = "The Claude API is busy (too many requests). Wait a minute and ask again."
        elif problem.status_code in (500, 502, 503, 529):
            message = "The Claude API is overloaded right now. Wait a minute and ask again."
        else:
            message = f"The Claude API said no ({problem.status_code}). Try asking again."
        print(f"  API error: {problem}")
        with JOBS_LOCK:
            job.update(state="error", error=message)
    except (ValueError, RuntimeError) as problem:
        with JOBS_LOCK:
            job.update(state="error", error=str(problem))
    except Exception as problem:  # show anything unexpected instead of hanging
        traceback.print_exc()
        with JOBS_LOCK:
            job.update(state="error", error=f"Something went wrong: {problem}")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def end_headers(self):
        # Never let the browser reuse an old copy of the page's files: after an update, a
        # saved old studio.js next to a new app.js breaks the page.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_bytes(self, body: bytes, kind: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        from pipeline import voices
        if self.path == "/api/voices":
            return self.send_json(200, {"enabled": voices.enabled()})
        audio = re.match(r"^/api/runs/([^/]+)/audio/(\d{1,3}-\d{1,2})\.mp3$", self.path)
        if audio:
            path = RUNS / audio.group(1) / "audio" / f"{audio.group(2)}.mp3"
            if not RUN_NAME.match(audio.group(1)) or not path.exists():
                return self.send_json(404, {"error": "No audio for that line."})
            return self.send_bytes(path.read_bytes(), "audio/mpeg")
        if self.path == "/api/runs":
            runs = []
            for folder in sorted(RUNS.glob("*/script.json"), reverse=True):
                try:
                    topic = json.loads(folder.read_text())["topic"]
                except (OSError, ValueError, KeyError):
                    continue
                runs.append({"name": folder.parent.name, "topic": topic})
            return self.send_json(200, runs)
        if self.path == "/api/news":
            return self.send_json(200, news_for_page())
        if self.path == "/api/upcoming":
            return self.send_json(200, upcoming_for_page())
        if self.path.startswith("/api/job/"):
            job_id = self.path.removeprefix("/api/job/")
            with JOBS_LOCK:
                job = dict(JOBS.get(job_id) or {})
                job["counts"] = dict(job.get("counts", {}))
            if not job:
                return self.send_json(404, {"error": "No such job."})
            return self.send_json(200, job)
        if self.path.startswith("/api/runs/"):
            name = self.path.removeprefix("/api/runs/")
            path = RUNS / name / "script.json"
            if not RUN_NAME.match(name) or not path.exists():
                return self.send_json(404, {"error": "No saved run with that name."})
            return self.send_json(200, json.loads(path.read_text()))
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/generate":
            return self.send_json(404, {"error": "Not found."})
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        topic = str(body.get("topic", "")).strip()[:300]
        chosen = [str(k) for k in body.get("chosen", [])][:10]
        if not topic:
            return self.send_json(400, {"error": "Type a topic first."})
        job_id = uuid.uuid4().hex[:12]
        with JOBS_LOCK:
            now = time.time()
            for old in [k for k, v in JOBS.items() if v.get("state") != "running" and now - v.get("at", now) > 3600]:
                del JOBS[old]
            JOBS[job_id] = {"at": now, "state": "running", "step": {"step": "start", "text": "Picking up the call"},
                            "counts": {"found": 0, "verified": 0, "dropped": 0}, "recent": "", "players": []}
        threading.Thread(target=run_job, args=(job_id, topic, chosen), daemon=True).start()
        return self.send_json(200, {"job": job_id})

    def log_message(self, format, *args):
        # Keep the terminal quiet except for generation requests.
        if getattr(self, "path", "").startswith("/api/generate") and "POST" in str(args[:1]):
            super().log_message(format, *args)


def _warm_up() -> None:
    """Load (and, once a day, download) the big data files in the background when the
    server starts, so the first segment doesn't wait on a download."""
    try:
        from pipeline import nba, nflv, sleeper
        season = int(sleeper.state("nfl")["season"])
        for load in (lambda: sleeper.players("nfl"), lambda: sleeper.players("nba"), nflv.schedules,
                     nflv.player_stats_by_season, lambda: nflv.player_stats((season,)), lambda: nflv.pbp(season),
                     nflv.sleeper_to_gsis, lambda: nflv.rosters_weekly(season), lambda: sleeper.nfl_schedule(season),
                     lambda: nflv.nextgen("passing"), lambda: nflv.nextgen("rushing"), lambda: nflv.nextgen("receiving"),
                     nflv.combine, nflv.draft_picks, lambda: nba.schedule(),
                     lambda: sleeper.season_stats("nba", nba.season()), lambda: sleeper.season_stats("nba", nba.season() - 1)):
            load()
        print("  data loaded and ready")
    except Exception as problem:            # a slow source shouldn't stop the server
        print(f"  warm-up skipped: {type(problem).__name__}")


def main() -> None:
    threading.Thread(target=_warm_up, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Sideline is running at http://localhost:{PORT}")
    print("Press Control-C here to stop it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
