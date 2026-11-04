#!/bin/bash
# start.sh: the one command that starts Sideline.
# It sets up Python packages the first time, then starts the server and opens the page.
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
  echo "Python 3 isn't installed. See README.md, section 'If Python is missing'."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "First run: setting up Python packages (takes about a minute)..."
  python3 -m venv .venv
fi
.venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
fi
if ! grep -qE '^ANTHROPIC_API_KEY=.+' .env; then
  echo "Heads up: your API key isn't in .env yet, so Go will show an error. See README.md."
fi

# Open the page a moment after the server starts.
(sleep 1.5 && open "http://localhost:8000") &
.venv/bin/python server.py
