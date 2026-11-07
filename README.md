# Sideline

Type an NBA or NFL question, and a few minutes later a fictional call-in debate show airs it: a caller asks, three AI hosts (Royce, Deacon, Lonnie) argue it with double-checked stats while Hal moderates, a blind panel of AI judges scores every argument, and the whole thing plays in a pixel-art studio with voices, subtitles, theme music, and broadcast graphics. The full spec is in [BRIEF.md](BRIEF.md); the characters are in [characters/](characters/).

## How a segment is made (about 1½ to 2 minutes)

| Step | What happens |
| --- | --- |
| 1. Screen the call | Checks it's an NBA or NFL question about today's players and teams; a bare name gets three suggested questions back. |
| 2. Pull stats | A research agent picks the stats the debate needs from nflverse, Sleeper, muffed.ai, and Wikipedia. It never types a number. |
| 3. Check twice | Code re-fetches every number from a second source. Anything that can't be confirmed is crossed off and replaced. |
| 4. Write it | The writer may use only checked numbers, and every line lists the facts it uses. |
| 5. Line check | Code checks every number in every line; an AI reader checks every claim. Bad lines are rewritten once, then cut. |
| 6. Blind judges | Three AI judges score each argument without knowing who made it; code does the math. |
| 7. The verdict | Hal announces the judges' result. |
| 8. Voices | Each subtitle card is voiced once (Google Cloud Text-to-Speech) and saved, so replays are free. |

Each run's folder in `runs/` has `script.json`, `fact_pack.json` (every checked stat), `rejection_log.json` (every stat and line that was dropped, fixed, or cut, and why), `judge.json`, and the voice clips. Only the 10 newest are kept.

## One-time setup: your keys

Keys are passwords for outside services. They go in a file called `.env` that git never saves. Each one is saved through a pop-up box that hides what you paste; never paste a key into a chat or a file.

```bash
~/Documents/the-receipts/set_key.sh
```

That's the Anthropic (Claude) key: [console.anthropic.com](https://console.anthropic.com) → **API Keys** → **Create Key** → **Copy**. Two more are optional:

- **Voices:** a Google Cloud key restricted to the Cloud Text-to-Speech API (`set_key.sh google`). Free up to 1 million characters a month; Sideline stops itself at 900,000. Without it, segments play with subtitles only.
- **News ticker:** a free [gnews.io](https://gnews.io) key (`set_key.sh gnews`). Without it, the ticker shows a short placeholder.

## Run it

```bash
~/Documents/the-receipts/start.sh
```

The first time, it spends about a minute installing Python packages. Then it opens http://localhost:8000. The page only works while this is running; to stop it, click its Terminal window and press **Control-C**.

Type a question under **Ask the desk**. While it's made, you're "on hold": hold music, the pre-show animation, and a progress bar. Then a countdown, the theme, and the segment.

**Under the TV:** **Pause** (Space), **Replay**, **End segment** (Esc; jumps to the verdict), **Sound** (music and voices), and **Last segment**, which replays the one before for free. If your browser blocks sound (Safari can), the Sound button turns gold and says "Click for sound." **Preview graphics (sample data)** demos every graphic with numbers stamped SAMPLE.

**If Python is missing:** this Mac has Python 3.11. On another computer, install Python 3 from [python.org/downloads](https://www.python.org/downloads/), then run `start.sh` again.

## Write a script without the page

```bash
cd ~/Documents/the-receipts && .venv/bin/python generate.py "Who wins the Super Bowl this season?"
```

## Tests

Free (no AI calls): `tests/accuracy.py` (are the sources still agreeing?), `tests/linecheck_test.py`, `tests/style_test.py`, `tests/positions_test.py`, `tests/news_test.py`, and `tests/voices_test.py` (`--samples` saves one voice per character). A few cents each: `tests/pipeline_test.py` (research and checking on six topics) and `tests/audit.py --latest 4` (a stronger model lists every claim in recent scripts and marks any the facts don't support).

## Files

| File | What it is |
| --- | --- |
| `BRIEF.md`, `SOURCES.md`, `characters/` | The spec, every data source and whether it may be used, and the character bibles. |
| `generate.py` | Runs the whole pipeline for one question and saves the run. |
| `pipeline/` | Each step: the topic check and research, the stat catalog and checker, injuries, the line checker, the judge, voices, and the data sources. |
| `server.py` | The small local web server the page talks to. |
| `static/index.html`, `style.css` | The page and its broadcast look. |
| `static/studio.js` | Draws and animates the pixel studio and cast in code. |
| `static/monitor.js` | The loading animations on the center monitor. |
| `static/sound.js` | The theme music and sound effects, synthesized in code. |
| `static/app.js` | Runs the show: pre-show, countdown, voices and subtitles, graphics, the end card. |
| `start.sh`, `set_key.sh` | Start everything; save a key without showing it. |
| `CLAUDE.md` | Notes for future Claude Code sessions. |

## Cost

A segment costs roughly a dime to a few dimes in Claude API credits (research, writing, checking, judging). Voices are free within Google's monthly allowance. Replays cost nothing.
