"""
server.py: the small local web server.

It does three things:
  - serves the webpage in static/
  - POST /api/generate   writes a new script for a topic (calls generate.py)
  - GET  /api/runs       lists saved scripts, and GET /api/runs/<name> loads one

It only listens on your own computer (127.0.0.1), so nobody else can reach it.
"""

import json
import re
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

from generate import RUNS, generate_script

PROJECT = Path(__file__).parent
STATIC = PROJECT / "static"
PORT = 8000
RUN_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def send_json(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/runs":
            runs = []
            for folder in sorted(RUNS.glob("*/script.json"), reverse=True):
                try:
                    topic = json.loads(folder.read_text())["topic"]
                except (OSError, ValueError, KeyError):
                    continue
                runs.append({"name": folder.parent.name, "topic": topic})
            return self.send_json(200, runs)
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
        try:
            length = int(self.headers.get("Content-Length", 0))
            topic = json.loads(self.rfile.read(length) or b"{}").get("topic", "")
            run_dir, script = generate_script(topic)
            script["run"] = run_dir.name
            print(f"  saved {run_dir.relative_to(PROJECT)}/script.json")
            return self.send_json(200, script)
        except (ValueError, RuntimeError) as problem:
            return self.send_json(400, {"error": str(problem)})
        except anthropic.AuthenticationError:
            return self.send_json(500, {"error": "Your API key was rejected. Check the .env file."})
        except anthropic.APIConnectionError:
            return self.send_json(502, {"error": "Couldn't reach the Claude API. Check your internet."})
        except Exception as problem:  # show anything unexpected instead of hanging
            traceback.print_exc()
            return self.send_json(500, {"error": f"Something went wrong: {problem}"})

    def log_message(self, format, *args):
        # Keep the terminal quiet except for generation requests.
        if getattr(self, "path", "").startswith("/api/generate"):
            super().log_message(format, *args)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"The Receipts is running at http://localhost:{PORT}")
    print("Press Control-C here to stop it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
