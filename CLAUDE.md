# Sideline: notes for Claude Code

The show was called The Receipts until Nov 4, 2026. The project folder keeps that name (`~/Documents/the-receipts`), but the show is Sideline everywhere else.

The person building this has never coded. Explain what you're doing in plain language as you go, and keep code simple: Python for the server, plain HTML and JavaScript for the page, no frameworks.

## Read first, every session

1. `BRIEF.md`, the full spec. It's the authority; if anything else disagrees with it, ask.
2. Every file in `characters/`: `royce_stanhope.md` (Host A), `deacon_pettiford.md` (Host B), `lonnie_fairweather.md` (Host C), `moderator.md` (Hal Brennan), and `callers.md`.
3. `SOURCES.md` before touching any stats source. Never connect a source marked "Manual only" or "Never".

These Markdown files are the master copies. They were converted from the PDFs in `originals/` and aligned on Nov 4, 2026. The user also has older drafts in Claude Docs, which may differ. If something is unclear or two documents contradict each other, ask the user instead of guessing, and keep the documents aligned when you change one.

## Where we are

**Step 1 is built:** a typed topic becomes a Sonnet-written script (caller, Hal, three hosts, Hal's wrap-up). It's saved to `runs/<date>_<time>/script.json` and played as subtitles on a plain page.

Step 1 has its own rules in `generate.py` (`STEP_1_RULES`). They override the bibles until the research step exists: no real-world numbers, no research-step placeholders, no specific real scenes or quotes, and no winner. Hosts may use their fictional bible backstories. Remove or loosen these rules as later steps arrive.

**Next, in the order under "How it's built" in BRIEF.md, one step at a time:**

1. Topic in: the topic check (roster matching plus Haiku) and Haiku picking the format.
2. Research: the research agent pulls stats from nflverse (nflreadpy) and the NBA source once it's chosen, plus web search.
3. Verify: a separate checker agent re-gets each stat on its own and cross-checks it. Only passed stats go into the fact pack, and every drop goes in the rejection log.
4. Write with the fact pack, then check every line's numbers against it.
5. Judge (blind scoring) and close (Hal's verdict, written after scoring).
6. Assemble the timeline, then the pixel studio, sprites, chyron, and meter.

Every character's look is in their bible ("## Look"). The pixel studio follows those; don't change a look without asking.

News ticker (decided Nov 4): the crawl along the bottom of the screen will carry real-time NBA and NFL headlines from a source checked against its terms. Until then it shows a placeholder (`NEWS_PLACEHOLDER` in `static/app.js`); never fill it with made-up headlines.

Cast cards on the page describe background and personality only, not how anyone argues.

Sources (Nov 4): ESPN, nba_api (NBA.com stats), and NBA team websites are ruled out; see the Never table in SOURCES.md and never connect them. Sleeper is approved (Nov 4), including its undocumented stats feed: it's the second source for NFL stats and rosters and the first NBA source. The NBA still needs a second source (balldontlie is the candidate), so NBA stats can't pass verification yet. Rosters need two independent sources that agree.

## Hooks for later steps (already built into the page)

- A line can carry `"stat": {"value", "label", "definition", "source", "asOf"}`; the page shows it on the stat chyron while that line plays.
- A line can carry `"score": {"royce": 66, ...}`; the score bug at the top updates when that line plays.
- A script can carry `"sources": [...]`; the end card lists them.
- The writer may use three big-reaction deliveries: `fired_up` (stands), `slam` (desk slam, with a shake and an optional sound), `exasperated` (turns away).
- **Preview graphics (sample data)** under the TV demos all of this with data stamped SAMPLE. Never show sample numbers anywhere else.
- `Studio.renderOnce()` draws a single frame, for testing when the browser tab is in the background.

## How to run it

```bash
./start.sh
```

That sets up `.venv`, starts `server.py` on http://localhost:8000, and opens the page. Run one script from the command line with:

```bash
.venv/bin/python generate.py "topic"
```

## Rules for working here

- The API key lives in `.env`, saved there by `set_key.sh`. Never print, show, read aloud, or commit it; to check it, print only its length. `.gitignore` already excludes `.env`, `.venv/`, and `runs/`.
- Models: `claude-sonnet-5-5` for writing, research, verifying, checking, judging, and the close; `claude-haiku-5-5` for small jobs like the topic check. Check Anthropic's docs before changing either.
- Commit after each piece works, with a plain-English message.
- Work on a branch, not `main`. Step 1 is on `step-1-scripts`.
