#!/bin/bash
# start.sh: the one command that starts Sideline.
# It sets up Python packages the first time (and again only when they change), starts the
# server, and opens the page as soon as the server answers. If Sideline is already running,
# it just opens the page.
set -e
cd "$(dirname "$0")"
URL="http://localhost:8000"

if curl -s -o /dev/null -m 2 "$URL/api/voices"; then
  echo "Sideline is already running. Opening $URL"
  open "$URL"
  exit 0
fi

if ! command -v python3 >/dev/null; then
  echo "Python 3 isn't installed. See README.md, section 'If Python is missing'."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "First run: setting up Python packages (takes about a minute)..."
  python3 -m venv .venv
fi
# Install packages only when requirements.txt has changed since the last install.
STAMP=".venv/.requirements-installed"
if [ ! -f "$STAMP" ] || ! cmp -s requirements.txt "$STAMP"; then
  .venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt
  cp requirements.txt "$STAMP"
fi

if [ ! -f .env ]; then
  cp .env.example .env
fi
if ! grep -qE '^ANTHROPIC_API_KEY=.+' .env; then
  echo "Heads up: your API key isn't in .env yet, so Ask the desk will show an error. See README.md."
fi

# Open the page once the server answers (up to about 15 seconds).
(for i in $(seq 1 60); do
   if curl -s -o /dev/null -m 1 "$URL/api/voices"; then open "$URL"; exit 0; fi
   sleep 0.25
 done) &
.venv/bin/python server.py
