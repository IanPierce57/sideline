# Sideline: notes for Claude Code

The show was called The Receipts until Nov 4, 2026. The project folder keeps that name (`~/Documents/the-receipts`), but the show is Sideline everywhere else.

The person building this has never coded. Explain what you're doing in plain language as you go, and keep code simple: Python for the server, plain HTML and JavaScript for the page, no frameworks.

## Read first, every session

1. `BRIEF.md`, the full spec. It's the authority; if anything else disagrees with it, ask.
2. Every file in `characters/`: `royce_stanhope.md` (Host A), `deacon_pettiford.md` (Host B), `lonnie_fairweather.md` (Host C), `moderator.md` (Hal Brennan), and `callers.md`.
3. `SOURCES.md` before touching any stats source. Never connect a source marked "Manual only" or "Never".

These Markdown files are the master copies. They were converted from the PDFs in `originals/` and aligned on Nov 4, 2026. The user also has older drafts in Claude Docs, which may differ. If something is unclear or two documents contradict each other, ask the user instead of guessing, and keep the documents aligned when you change one.

## The rule that matters most

If a number can't be cross-referenced or otherwise confirmed correct, cross it off and go to something else. It never reaches
the script; `generate.py` runs one more research round for confirmable replacements (step 3b), checked the same way. Numbers
from the sources the user chose to trust on their own (Sleeper for stats, Wikipedia for honors) count as confirmed. Never
loosen this rule without asking.

## Where we are

**Built (Nov 4, 2026):** a typed topic goes through the whole fact pipeline, then plays in the pixel studio.

1. **Topic check** (`pipeline/research.py`, Haiku): NBA/NFL only, appropriate, names resolved by ID. Same-name players are confirmed with the user when two or more current players share the name (or all are retired).
2. **Research agent** (`pipeline/research.py`, Sonnet): picks stats from the catalog through tools. It never types a number.
3. **Checker** (`pipeline/verify.py`, plain code): every fact re-fetched from a second source and compared. NFL basic stats vs Sleeper (Sleeper wins disagreements); NFL advanced stats and team records vs muffed.ai (exact match or dropped); NBA stats from Sleeper, checked against Wikipedia (Sleeper wins); tackles from Sleeper alone; NFL before 2009 and NBA before 2017-18 can't be checked, so they're dropped.
4. **Writer** (`generate.py`, Sonnet): only fact-pack numbers; every line lists the fact IDs it uses (`FACT_RULES`).
5. **Line checker** (`pipeline/linecheck.py`): code checks every number in every line against the facts it cites; an AI reader flags unsupported claims; failed lines are rewritten once, then cut.
6. Each run saves `script.json`, `fact_pack.json`, and `rejection_log.json` in `runs/<date>_<time>/`.

Run `.venv/bin/python tests/accuracy.py` to recheck the sources (free; no API calls). Other tests: `tests/linecheck_test.py`, `tests/news_test.py`, `tests/positions_test.py` (all free), and `tests/pipeline_test.py` (a few cents a topic: times research and checking on six varied topics; targets 12+ confirmed facts and under 60 seconds before writing).

**Speed (Nov 5):** a full segment takes about 35-60 seconds (was 135-200). muffed.ai is asked once per team or player (not once per stat) and answers are saved for 6 hours; Wikipedia requests are one at a time with a short gap; the server loads the data files in the background when it starts; the writer runs at medium effort (`SIDELINE_WRITER_EFFORT=high` to change), which wrote as well as high in a side-by-side test and about 20 seconds faster.

**More NFL facts (Nov 5):** head coaches (nflverse schedules vs Wikipedia team pages); measurables (listed height and weight from Sleeper; combine results from nflverse, matched by draft IDs and checked against the pre-draft table on Wikipedia, so pro-day numbers stay out); draft position (nflverse vs Wikipedia infobox). When muffed.ai and nflverse are a week apart, our numbers are recalculated through muffed's week (Next Gen Stats can't be, so they're crossed off for that day or two); for the season in progress, Sleeper's side adds up its weekly numbers through nflverse's week.

**Opinions (Nov 5):** opinions about how a player plays don't need proof, but they must be believable (no "dual-threat" Jared Goff). `pipeline/style.py` builds a style profile per player (rushing, depth of throws, separation, carries...), ranked against his position and shown to the writer and claims checker in words only, never numbers. `STYLE_LABELS` maps common labels to the trait they need; the line checker flags clear contradictions. Test: `tests/style_test.py`. Royce (the eye test) may use images and metaphors ("runs routes like a locksmith"); they must fit the profile, be fresh (never the bible's examples), and never describe looks or a specific real play. Profile rankings are never stated as facts on air. No fan-opinion source (Bluesky dropped Nov 5). After a line is cut, the lines on either side are smoothed (`linecheck.smooth`) so hand-offs still match, then checked again.

**Positions (Nov 5):** `pipeline/positions.py` lists which position labels can stand in for which (RB/HB/FB, OT/OG/OL, DE/EDGE/OLB/LB, DB/CB/S/nickel...). The pairs are not transitive: an edge rusher can be called a linebacker, but a Mike linebacker is never a defensive end. Used to match the right player's Wikipedia page.

**Hallucination audit (Nov 5):** `tests/audit.py --latest 8` has a separate, stronger model (Opus) list every real-world claim in finished scripts and mark it supported by the fact pack or not (about 10-20 cents a script). Rounds on eight varied topics went from 10 of 200 claims unsupported (5%) to 2 of 178 (1.1%, both minor, none contradicted). What fixed it: past seasons labeled "last season, not this one" in the pack, a code check for "this season" with only old facts, numbers said with a noun must match a fact about that noun ("seven games" can't borrow 7 sacks), current-team facts include position, starter, and health, playoff records include their seasons, new writer rules (injuries as of today only, superlatives and roles need a rank, no trends without both seasons, no title-team claims, callers state no facts), and the in-show claims check lists every claim with a verdict (Sonnet, high effort, kept by the user's choice on Nov 5 after seeing the Opus comparison; `SIDELINE_CLAIMS_MODEL=claude-opus-5-5` caught 9 of 10 vs Sonnet's 5 of 10 in a side-by-side, about 5-10 seconds slower). Run the audit after any change to the writer, checker, or sources.

**NBA (Nov 5):** `pipeline/nba.py` (schedule, scores, standings, game finder, team facts, game pack) uses Sleeper first and Wikipedia second (team-season game logs, standings templates); NBA player stats are checked against Wikipedia career tables, current team/height/draft against Wikipedia. `pipeline/leagues.py` holds what differs between leagues. Facts are checked in the background as research pulls them (`verify.warm`); the real check is unchanged. NBA coaches: name only.

**Single NFL games** (Nov 5): `pipeline/games.py` confirms the game on two schedules (nflverse and Sleeper); `catalog.game_pack` pulls records, team stats (checked against muffed.ai), recent scores (checked against Sleeper), last starting QBs, and injured starters. NBA single games are turned away for now.

**Scope:** active players and current teams only (Nov 4); questions that need the past ("greatest ever", GOAT, all-time rankings, comparisons with retired players, past teams) are turned away with present-day suggestions (Nov 5). Honors come from Wikipedia, trusted on its own (Nov 4), still cross-checked where possible (Super Bowl rings vs nflverse rosters; major awards vs Wikidata; Wikipedia wins a disagreement, which is logged); QB playoff records from nflverse scores with starts checked against Sleeper.

**Known gaps:** no contract or cap data (Spotrac and Over The Cap forbid automated use; Lonnie argues money in general terms); Wikipedia rate-limits bursts of requests (they're spaced and cached daily); spelled-out decimals ("twenty point nine") aren't checked; claims without numbers are judged by an AI checker, so a small error rate remains (about 1% of claims in the last audit); Royce (the eye test) rarely wins under the debate rubric: 0 wins in the last 16 judged segments, mostly for not engaging the opponent and small-sample evidence (Nov 5). Whether that's right for the show is the user's call.

**Next, in the order under "How it's built" in BRIEF.md:** finish testing the judge (fairness and consistency), then voices last. (The fact pipeline, the news ticker, the judge, and Hal's close are built as of Nov 5, 2026.)

**Judge (Nov 5):** `pipeline/judge.py` (see BRIEF.md "How it works in practice" under Scoring). The writer ends the script at the final answers; generate.py runs the judge, puts running scores on lines for the meter, then writes and checks Hal's close. Each run also saves `judge.json`. No host is favored on home topics (user, Nov 5). `tests/judge_test.py [n] [--blind-only]` re-judges recent scripts to check consistency, name bias, and Hal-vs-judge agreement. Games played in NFL facts come from Sleeper (it counts differently from nflverse).

**Voice and fire (Nov 6):** the writer plans positions and escalating beats first, then writes with fire (cross-examination, traps, catching contradictions, rapid-fire stretches, no free concessions, a decisive moment the facts decide) and a "how real people talk" guide. `linecheck.check_stock_phrases` flags move names said on air, stock phrases past two per segment, and stat-like numbers said a third time; those lines are rewritten, never cut. Six segment types (who's better, who wins, buy or sell, real or not, rank 'em, overrated). Each player's time with his team (`catalog.tenure`) keeps trade talk realistic. Hal's close: winner, one or two plain sentences on what carried it, where the others land, sign-off (guaranteed in code); no rebuttal recap. Pre-show is mostly silent animation with a few short lines.

**Hosts (Nov 5):** one standard of skill for all three (BRIEF.md Debate rules): answer first, big samples, turn their numbers, every turn adds something, concede small, land on the question, a counter for every attack and a Plan B, never a one-trick pony. Each bible keeps his distinct lean and go-to moves, plus "How he wins a debate" and "Counterpunches". Bible evidence lists match what the fact pack actually has; example lines that needed missing data were rewritten. Royce also has `qb_starter_record` (regular-season record as a starter). Not yet re-tested with the judge (user: test after other work).

Every character's look is in their bible ("## Look"). The pixel studio follows those; don't change a look without asking.

News ticker (decided Nov 4): `pipeline/news.py` pulls the day's headlines from GNews's free plan (free and delayed is fine; accuracy matters most). Headlines are shown verbatim with the outlet, and a story runs only if two or more outlets report it. No Sleeper most-added players (decided Nov 4). With no confirmed headlines it shows the placeholder (`NEWS_PLACEHOLDER` in `static/app.js`). Never fill it with made-up headlines. Test: `.venv/bin/python tests/news_test.py`.

Cast cards on the page describe background and personality only, not how anyone argues.

Sources (Nov 4): ESPN, nba_api (NBA.com stats), and NBA team websites are ruled out; see the Never table in SOURCES.md and never connect them. Sleeper is approved (Nov 4), including its undocumented stats feed: it's the second source for NFL stats and rosters and the first NBA source. Decisions (Nov 4): Sleeper is trusted. When nflverse and Sleeper disagree, use Sleeper's number and log the disagreement; for the NBA, Sleeper alone is enough. Same-name players are confirmed with the user in the topic check. NFL advanced stats are included, cross-referenced against a second reputable source (not recalculated). Rosters need two independent sources that agree.

## Hooks for later steps (already built into the page)

- A line can carry `"stat": {"value", "label", "definition", "source", "asOf"}`; the page shows it on the stat chyron while that line plays.
- A line can carry `"score": {"royce": 66, ...}`; the score bug at the top updates when that line plays (the judge sets these).
- A script carries `"scores"`, `"winner"`, and `"tie"`; the end card shows each host's final score and marks the winner.
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
