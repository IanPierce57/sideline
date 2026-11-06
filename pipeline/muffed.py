"""muffed.ai's read-only MCP server, used to cross-reference NFL advanced stats.

Terms: free for individuals; email hello@muffed.ai before building it into a
product; no bulk scraping; show the credit line wherever its numbers appear.
It is built on nflverse, so it confirms our definitions and calculations match a
published source (it is not an independent source of the raw play data)."""

import json
import re
import threading
import time
import urllib.error
import urllib.request

from .net import CACHE, SSL, USER_AGENT

URL = "https://muffed.ai/api/mcp"
CREDIT = "Data via nflverse · NFL Next Gen Stats via nflverse · FTN Data via nflverse"

_lock = threading.Lock()
_session = {"id": None, "next": 1}
_memo = {}


def _post(payload: dict):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
               "User-Agent": USER_AGENT}
    if _session["id"]:
        headers["Mcp-Session-Id"] = _session["id"]
    request = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(request, timeout=45, context=SSL) as response:
        _session["id"] = response.headers.get("Mcp-Session-Id") or _session["id"]
        raw = response.read().decode()
    if "data:" in raw[:40]:
        raw = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")][-1]
    return json.loads(raw) if raw.strip() else {}


def _rpc(method: str, params: dict) -> dict:
    _session["next"] += 1
    reply = _post({"jsonrpc": "2.0", "id": _session["next"], "method": method, "params": params})
    if "error" in reply:
        raise RuntimeError(f"muffed.ai: {reply['error'].get('message')}")
    return reply.get("result", {})


def _connect():
    if _session["id"]:
        return
    _rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "sideline", "version": "0.1"}})
    try:
        _post({"jsonrpc": "2.0", "method": "notifications/initialized"})
    except Exception:
        pass


def _all_metrics(entity: str, kind: str, season: int) -> list:
    """Every metric muffed publishes for one team or player in one season: one request
    (not one per stat), saved for 6 hours. muffed asks for no bulk scraping, so requests
    go one at a time and wait and retry if it says to slow down."""
    key = (entity, kind, season)
    with _lock:
        if key in _memo:
            return _memo[key]
        path = CACHE / "muffed" / (re.sub(r"\W+", "_", f"{kind}_{entity}_{season}") + ".json")
        if path.exists() and time.time() - path.stat().st_mtime < 6 * 3600:
            rows = json.loads(path.read_text())
        else:
            _connect()
            for attempt in range(4):
                try:
                    result = _rpc("tools/call", {"name": "get_entity_metrics", "arguments": {
                        "entity": entity, "entity_kind": kind, "season": season, "scope": "all"}})
                    break
                except urllib.error.HTTPError as e:
                    if e.code != 429 or attempt == 3:
                        raise
                    time.sleep(5 * (attempt + 1))
            rows = (result.get("structuredContent") or {}).get("rows")
            if rows is None:                       # older replies carry the table as text
                rows = []
                for block in result.get("content", []):
                    try:
                        data = json.loads(block.get("text", ""))
                    except (ValueError, TypeError):
                        continue
                    if isinstance(data, dict):
                        rows += data.get("rows", [])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(rows))
            time.sleep(0.3)
        _memo[key] = rows
        return rows


def metric(entity: str, metric_key: str, season: int, kind: str = "player", gsis_id: str | None = None):
    """muffed's published value for one metric, or None if it doesn't publish one.
    Returns {'value', 'rank', 'population', 'as_of', 'through_week'}."""
    for row in _all_metrics(entity, kind, season):
        if row.get("metric_key") != metric_key or row.get("season") != season:
            continue
        if gsis_id and row.get("gsis_id") and row["gsis_id"] != gsis_id:
            continue   # same name, different player
        return {k: row.get(k) for k in ("value", "rank", "population", "as_of", "through_week")}
    return None
