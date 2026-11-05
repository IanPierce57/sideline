"""Fetching JSON from the internet, with a small cache on disk so we don't ask
the same source the same question over and over."""

import json
import ssl
import time
import urllib.request
from pathlib import Path

import certifi

CACHE = Path(__file__).resolve().parent.parent / ".cache"
CACHE.mkdir(exist_ok=True)

# Python on macOS doesn't trust secure connections out of the box; use certifi's list.
SSL = ssl.create_default_context(cafile=certifi.where())
USER_AGENT = "Sideline/0.1 (non-commercial class project)"


def get_json(url: str, cache_name: str, max_age_hours: float):
    """Return the JSON at url, reusing a saved copy younger than max_age_hours."""
    path = CACHE / f"{cache_name}.json"
    if path.exists() and time.time() - path.stat().st_mtime < max_age_hours * 3600:
        return json.loads(path.read_text())
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60, context=SSL) as response:
        data = json.loads(response.read())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data
