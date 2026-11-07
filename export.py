"""export.py: package Sideline for submission (added Nov 7, 2026).

  .venv/bin/python export.py

1. Writes outputs/: one readable transcript per saved segment (the script, the scores, every
   fact used and what it was checked against, and what the checkers caught), plus an index.
2. Builds a zip next to the project folder (~/Documents/Sideline-submission-<date>.zip) with
   the code, docs, character bibles, tests, git history, the saved runs (with voice clips),
   and outputs/. It never includes .env (your keys), .venv (Python packages, rebuilt by
   start.sh), or .cache (downloaded data, re-downloaded on first run), and it refuses to
   finish if anything that looks like an API key is in the files it's packing.
"""

import json
import re
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
RUNS = PROJECT / "runs"
OUT = PROJECT / "outputs"
NAMES = {"hal": "Hal", "royce": "Royce", "deacon": "Deacon", "lonnie": "Lonnie"}
FORMATS = {"debate": "Who's better?", "prediction": "Who wins?", "buy_or_sell": "Buy or sell?",
           "real_or_not": "Real or not?", "rank_em": "Rank 'em", "overrated": "Overrated or underrated?"}
KEY_PATTERN = re.compile(rb"sk-ant-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{35}")
SKIP_DIRS = {".venv", ".cache", "__pycache__", "node_modules"}
SKIP_FILES = {".env", ".DS_Store"}


def transcript(run: Path) -> str:
    s = json.loads((run / "script.json").read_text())
    rej = json.loads((run / "rejection_log.json").read_text()) if (run / "rejection_log.json").exists() else {}
    m = s.get("meta", {})
    caller = s.get("caller", {})
    who = lambda l: f"{caller.get('name', 'Caller')} from {caller.get('city', '')}" if l["speaker"] == "caller" \
        else NAMES.get(l["speaker"], l["speaker"].title())
    out = [f"# {s['topic']}", ""]
    winner = "tie" if s.get("tie") else NAMES.get(s.get("winner"), s.get("winner") or "none")
    scores = ", ".join(f"{NAMES.get(h, h)} {v:.1f}" for h, v in sorted((s.get("scores") or {}).items(),
                                                                        key=lambda x: -(x[1] or 0)) if v is not None)
    timings = m.get("timings", {})
    out += [f"- **Segment type:** {FORMATS.get(s.get('format'), s.get('format'))}",
            f"- **Winner (blind judges):** {winner} ({scores})",
            f"- **Made:** {m.get('created', run.name)} in {sum(timings.values()):.0f} seconds"
            + (f" (voices: {sum(1 for l in s['lines'] for c in l.get('cards', []) if c.get('audio'))} clips)"
               if any(l.get("cards") for l in s["lines"]) else " (subtitles only)"),
            f"- **Facts:** {m.get('stats_found', '?')} pulled, {m.get('stats_verified', '?')} confirmed by a second "
            f"source, {m.get('stats_dropped', '?')} crossed off; {m.get('facts_used', '?')} used on air",
            f"- **Line check:** {m.get('lines_checked', '?')} lines checked, {m.get('lines_rewritten', 0)} rewritten, "
            f"{m.get('lines_cut', 0)} cut"]
    if (m.get("usage") or {}).get("total_usd") is not None:
        out.append(f"- **API cost:** ${m['usage']['total_usd']:.2f}")
    out += ["", "## The segment", ""]
    for l in s["lines"]:
        facts = f"  _(facts {', '.join(l['facts'])})_" if l.get("facts") else ""
        out.append(f"**{who(l)}** [{l.get('delivery', '')}]: {l['text']}{facts}  ")
    out += ["", "## Every fact used on air", "", "| ID | Player or team | Stat | Value | Scope | Checked against |",
            "| --- | --- | --- | --- | --- | --- |"]
    used = {f for l in s["lines"] for f in l.get("facts", [])}
    pack = json.loads((run / "fact_pack.json").read_text()) if (run / "fact_pack.json").exists() else []
    for f in pack:
        if f.get("id") in used:
            cell = lambda x: str(x or "").replace("|", "/").replace("\n", " ")
            out.append(f"| {f['id']} | {cell(f.get('subject'))} | {cell(f.get('label'))} | {cell(f.get('say'))} | "
                       f"{cell(f.get('scope'))} | {cell(f.get('checked_against') or f.get('source'))} |")
    crossed = [r for r in rej.get("stats", []) if not str(r.get("reason", "")).startswith("kept")]
    disagreed = [r for r in rej.get("stats", []) if str(r.get("reason", "")).startswith("kept")]
    out += ["", "## What the checkers caught", ""]
    out.append(f"**Stats crossed off ({len(crossed)}):**" if crossed else "**Stats crossed off:** none")
    out += [f"- {r.get('subject')}: {r.get('stat')} ({r.get('scope')}): {r.get('reason')}" for r in crossed]
    if disagreed:
        out += ["", f"**Kept, but the two sources disagreed ({len(disagreed)}):**"]
        out += [f"- {r.get('subject')}: {r.get('stat')}: {r.get('reason')}" for r in disagreed]
    lines = rej.get("lines", [])
    out += ["", f"**Lines rewritten or cut ({len(lines)}):**" if lines else "**Lines rewritten or cut:** none"]
    for r in lines:
        out.append(f"- Line {r.get('line')} ({NAMES.get(r.get('speaker'), r.get('speaker'))}), {r.get('action')}: "
                   f"said \"{r.get('said')}\". Problem: {r.get('problem')}"
                   + (f" Now: \"{r['now']}\"" if r.get("now") else ""))
    return "\n".join(out) + "\n"


def write_outputs() -> list[tuple[str, str]]:
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.md"):
        old.unlink()
    made = []
    for run in sorted(d for d in RUNS.iterdir() if (d / "script.json").exists()):
        topic = json.loads((run / "script.json").read_text())["topic"]
        name = f"{run.name}_{re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')[:50]}.md"
        (OUT / name).write_text(transcript(run))
        made.append((name, topic))
    index = ["# Sideline: saved segments", "",
             "Each file is one segment as it aired: the script, the blind judges' scores, every fact used and what it "
             "was checked against, and what the fact checkers caught. The raw files (with the voice clips) are in "
             "`runs/`, one folder per segment.", ""]
    index += [f"- [{topic}]({name})" for name, topic in made]
    (OUT / "README.md").write_text("\n".join(index) + "\n")
    return made


def files_to_pack() -> list[Path]:
    files = []
    for path in PROJECT.rglob("*"):
        rel = path.relative_to(PROJECT)
        if path.is_dir() or rel.parts[0] in SKIP_DIRS or any(p in SKIP_DIRS for p in rel.parts) \
                or path.name in SKIP_FILES or path.suffix == ".pyc":
            continue
        files.append(path)
    return sorted(files)


def build_zip() -> Path:
    zip_path = PROJECT.parent / f"Sideline-submission-{date.today():%Y-%m-%d}.zip"
    files = files_to_pack()
    leaks = [f for f in files if f.stat().st_size < 50_000_000 and KEY_PATTERN.search(f.read_bytes())]
    if leaks:
        sys.exit("Stopped: these files look like they contain an API key, so nothing was zipped:\n  "
                 + "\n  ".join(str(f.relative_to(PROJECT)) for f in leaks))
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, Path("Sideline") / f.relative_to(PROJECT))
    return zip_path


if __name__ == "__main__":
    status = subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT, capture_output=True, text=True).stdout
    if status.strip():
        print("Note: some changes aren't committed yet; they're still included in the zip.")
    made = write_outputs()
    print(f"Wrote {len(made)} readable transcripts to outputs/")
    path = build_zip()
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    print(f"Built {path} ({path.stat().st_size / 1e6:.1f} MB, {len(names)} files). No .env, .venv, or .cache inside; "
          "no API keys found.")
