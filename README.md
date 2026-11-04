# Sideline

Type an NBA or NFL topic, and AI writes a 3-to-5-minute debate between a moderator (Hal) and three hosts (Royce, Deacon, Lonnie), then plays it as subtitles. The full spec is in [BRIEF.md](BRIEF.md); the characters are in [characters/](characters/).

**Current step: 1 of the pipeline, with the pixel studio.** Scripts have no real stats and no scoring yet, and there are no voices.

## One-time setup: add your API key

Your key is a password for the Claude API. It goes in a file called `.env` that git never saves, so it stays on your computer only.

1. At [console.anthropic.com](https://console.anthropic.com), go to **API Keys** → **Create Key**, then click the **Copy** button in the window that appears. (The list of keys only shows a shortened version, which won't work.)
2. Run:

   ```bash
   ~/Documents/the-receipts/set_key.sh
   ```

3. Paste the key into the pop-up box and click **Save**. Terminal should say `Saved` and the key's length (about 106 characters).

Never paste the key into a chat, the page, or any other file. To change keys later, run `set_key.sh` again.

## Run it

```bash
~/Documents/the-receipts/start.sh
```

The first time, it spends about a minute installing Python packages. Then it opens http://localhost:8000 in your browser. The page only works while this is running.

Type a topic under **Ask the desk** and press the button. While the script is written (about a minute), you watch the pre-show: makeup, research, a mic check, the floor producer. Then a 3-2-1 countdown, the ON AIR sign lights, and the segment plays one line at a time in a speech bubble over whoever is talking. Each line stays up about as long as it takes to say it (150 words per minute). **Pause** and **Replay** sit under the screen.

To stop it, click the Terminal window and press **Control-C**.

## Where scripts are saved

Every run gets its own folder named by date and time, like `runs/2026-11-04_14-30-05/script.json`. Each file holds:

- `topic`: what you typed
- `format`: `debate`, `buy_or_sell`, or `prediction` (the AI picks)
- `caller`: the caller type, first name, and city
- `lines`: every line, with `line` (number), `speaker`, `speaker_name`, `text`, `delivery` (calm, heated, laughing, and so on), and `argument` (which argument it belongs to; blank for the caller and Hal)
- `word_count`, `estimated_minutes`, and `warnings` (plain checks for length, stray numbers, and leftover placeholders)
- `meta`: the model, how long it took, and how many tokens it used

The `runs/` folder isn't saved to git, so delete old runs whenever you like.

## Write a script without the page

```bash
cd ~/Documents/the-receipts && .venv/bin/python generate.py "Who wins the Super Bowl this season?"
```

It prints the script in Terminal and saves it to `runs/` the same way.

## Files

| File | What it is |
| --- | --- |
| `BRIEF.md` | The project spec. The rules everything else follows. |
| `SOURCES.md` | Every stats source, and whether the app may use it. |
| `characters/` | One bible per character, plus `callers.md`. |
| `generate.py` | Builds the prompt from the brief and bibles, asks Claude for the script, checks it, and saves it. |
| `server.py` | The small local web server that the page talks to. |
| `static/index.html` | The page: the TV, the Ask the desk console, sources, the cast, and credits. |
| `static/style.css` | The broadcast look: colors, pixel fonts, monitors, name plate, ticker. |
| `static/studio.js` | Draws the pixel studio and the characters in code, and animates them. |
| `static/app.js` | Runs the show: pre-show, countdown, then the segment line by line. |
| `start.sh` | The one command that sets up and starts everything. |
| `set_key.sh` | Saves your API key into `.env` through a pop-up box, without showing it. |
| `requirements.txt` | The Python packages the project needs. |
| `.env.example` | A blank copy of the key file. Your real key goes in `.env`. |
| `originals/` | The PDFs and files these Markdown copies were made from. |
| `CLAUDE.md` | Instructions for future Claude Code sessions. |

## If Python is missing

This Mac already has Python 3.11. On another computer, download Python 3 from [python.org/downloads](https://www.python.org/downloads/), run the installer, then run `start.sh` again.

## Cost

Each script is one Sonnet call. The bibles are about 25,000 tokens and get cached, so repeat runs within a few minutes cost less. Each run's real token counts are saved in its `meta` section.
