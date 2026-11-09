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
6. Each run saves `script.json`, `fact_pack.json`, and `rejection_log.json` in `runs/<date>_<time>/`. Only the 10 newest are kept (`generate.prune_runs`, user, Nov 6): no archive of every segment. The page's **Last segment** button (under the TV) replays the most recent saved segment that isn't on screen, so it rolls forward with each new one (user, Nov 6; replaced a video download).

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

**Status (Nov 7, 2026):** everything in BRIEF.md is built, including voices; the user considers it the final version (due Nov 14). Polish pass Nov 7: the debate's voices are recorded in the background while the judge and Hal's close run (`generate._BACKGROUND`), so only Hal's close is voiced at the end; more broadcaster reading rules (months, "vs.", "No. 1"); hold music has a second phrase; Space/Esc shortcuts; the browser tab title shows the show's state; README rewritten; music and effects at 60% (`MUSIC_LEVEL`; measured, the theme had run 2-3x louder than speech); start.sh skips the package install unless requirements.txt changed, opens the page when the server answers, and just opens it if Sideline is already running; plain-English errors for running out of API credits or an overloaded API; finished jobs are cleared after an hour; keyboard focus outlines and a screen-reader line announcer. End-to-end check Nov 7: voices step 1.9 s (was ~6), sync within 0.01 s, audit 0 of 73 claims unsupported. The first segment of a day is slower (research ~50 s instead of ~10) because each player's Wikipedia page is fetched fresh once a day; run one segment before a demo to warm it.

**Judge (Nov 5):** `pipeline/judge.py` (see BRIEF.md "How it works in practice" under Scoring). The writer ends the script at the final answers; generate.py runs the judge, puts running scores on lines for the meter, then writes and checks Hal's close. Each run also saves `judge.json`. No host is favored on home topics (user, Nov 5). `tests/judge_test.py [n] [--blind-only]` re-judges recent scripts to check consistency, name bias, and Hal-vs-judge agreement. Games played in NFL facts come from Sleeper (it counts differently from nflverse).

**Voice and fire (Nov 6):** the writer plans positions and escalating beats first, then writes with fire (cross-examination, traps, catching contradictions, rapid-fire stretches, no free concessions, a decisive moment the facts decide) and a "how real people talk" guide. `linecheck.check_stock_phrases` flags move names said on air, stock phrases past two per segment, and stat-like numbers said a third time; those lines are rewritten, never cut. Six segment types (who's better, who wins, buy or sell, real or not, rank 'em, overrated). Each player's time with his team (`catalog.tenure`) keeps trade talk realistic. Hal's close: winner, one or two plain sentences on what carried it, where the others land, sign-off (guaranteed in code); no rebuttal recap. Pre-show is mostly silent animation with a few short lines.

**Hosts (Nov 5):** one standard of skill for all three (BRIEF.md Debate rules): answer first, big samples, turn their numbers, every turn adds something, concede small, land on the question, a counter for every attack and a Plan B, never a one-trick pony. Each bible keeps his distinct lean and go-to moves, plus "How he wins a debate" and "Counterpunches". Bible evidence lists match what the fact pack actually has; example lines that needed missing data were rewritten. Royce also has `qb_starter_record` (regular-season record as a starter). Not yet re-tested with the judge (user: test after other work).

**Injuries (Nov 6):** `pipeline/injuries.py`. Today's status in plain words (questionable = usually plays, day-to-day = minor, doubtful = probably out; out, IR, PUP = out); team reports group by that, questionable last. `current_team` now also returns `availability` (games played, last five full seasons plus this one; Sleeper vs nflverse or Wikipedia; seasons with a quarter or more missed) and `injury_history` (Wikipedia, kept only when games played confirm missed time; season only from a full date or a one-season heading). Writer rule 7 and `linecheck.check_injury_labels`: "injury-prone" needs a pattern (2+ full seasons with a quarter missed); one major injury is a fair question about the return, not a label. Next-season games confirm only a long recovery (torn Achilles or ACL); this season's NFL row runs through nflverse's week, like the team record. Audit after the injury work (Nov 6): no injury errors in the final runs; the misses left were older kinds (a superlative, a style read said as fact). Same day: traps must be built on true statements (leaving something out is fine, saying something false isn't); the number checker no longer pairs a number with a noun across a comma ("all seventeen, MVP"); "the pack" and similar internal words said on air are flagged.

**Toolboxes (Nov 6):** each bible has a Toolbox: signature tools (where he's best, reached for first when they fit) and the rest of his kit; he picks what fits the question and never changes the question to suit a tool (user: flexibility, not reframing). Every case answers the question as asked, about its subject: on a player question, Lonnie argues the player (role, fit, usage), and front-office angles lead only on decision questions. The judge rates a swapped question or team stats used to judge one player as off the question. Sample talk: a season is just "this season"; small only when it is (early season, playoffs); `linecheck.SAMPLE_TALK` flags "a real sample" and "building a statue". A bare name or team as a topic gets three suggested questions.

**Conversation flow (Nov 6):** Hal takes the call (code adds the line if the writer skips it) but doesn't hand off or pick who starts. `generate.turn_order` deals a random order of host turns each segment (roughly even, nobody twice in a row, no two hosts trading more than three turns before the third comes in); the writer follows it and stops where the arguments run out. It's one three-way conversation: anyone answers anyone (user). If the writer leaves arguments untagged, the judge counts every host turn before the final answers (a run crashed with no winner).

**Voices (Nov 6):** `pipeline/voices.py`, Google Cloud Text-to-Speech, Chirp 3 HD (user's choice; free tier, capped at 900,000 characters a month in `.cache/voices/usage.json`). Key `GOOGLE_TTS_KEY` via `./set_key.sh google`; without it the show is subtitles only. generate.py voices every line after saving (step "voices") into `runs/<run>/audio/<line>.mp3`; every subtitle card is voiced as its own clip (`voices.cards_for` splits lines the way the page did), so a card shows when its clip starts and moves on when it ends (`source.onended`), with the text typing out at speaking pace; they can't drift. Sync tested Nov 6 with clips of known length: card changes landed within a few hundredths of a second, also across a pause. Every character has a different voice (`tests/voices_test.py`, free; `--samples` saves one per character once the key is in). Only the segment is voiced (user): not the countdown, the pre-show, or the idle page. `voices.speech_text` makes numbers read like a broadcaster ("5-3" is "five and three"). Cast: Hal Algieba, Royce Iapetus, Deacon Algenib, Lonnie Achird; callers from a pool by name. Overall talking speed `voices.SPEED` = 1.08 (user, Nov 7: a bit faster); each person's pace and each line's delivery scale from it.

**Cost (Nov 7):** `pipeline/meter.py` adds up every Claude call's tokens by step and prices them (rates from Anthropic's pricing page, checked Nov 7: Sonnet 5.5 $2 in / $10 out per million, cache reads $0.10, 5-minute writes $2.50, 1-hour writes $4); each run's meta has `usage`, and the CLI and the server terminal print the cost. The writer's 50,000-token system prompt uses a 1-hour cache (segments start 6-10 minutes apart, so the 5-minute cache hit only 2 of 10 runs). Research caches its rules plus the growing conversation (rounds 2+ read from cache; ~4 cents instead of ~5.5). Not changed, by choice: judge and claims-check effort (quality tradeoffs needing the user's OK and a test).

**Music and sound (Nov 6):** `static/sound.js`, all synthesized in code with Web Audio (original, no files): quiet hold music in the pre-show ("you're on hold"), countdown beeps, the theme under the wipe going on air (lands its big chord as the wipe clears, then a breath before the first line), the closing theme with crowd and applause before the end card, a chime for stat cards, a blip for score changes, and the desk slam. Music only plays between the talking. The Sound button mutes music and voices together. Real-voice sync check (Nov 6): every card stayed up exactly as long as its clip, within 0.01 s.

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
- Visual upgrade (Nov 6): `static/monitor.js` rotates seven loading animations on the center monitor during the pre-show (none show numbers); a broadcast wipe (`stinger()` in app.js) plays going live and before the end card; `Studio.celebrate(winner)` throws confetti and has the desk applaud; listeners react to each line and speakers sometimes count on fingers, tap the desk, or think; hosts fidget between calls; the pipeline strip under the question box lights up step by step; the page glow follows `data-mode` on `<html>`. Character looks are unchanged (bibles).

## Screenshots and source labels (Nov 8)

`?shot=home|preshow|live|end` freezes the page in that state with the newest saved run (animations shown finished, no sound prompt); `docs/screenshots/` was captured with headless Chrome at 2x (`--virtual-time-budget`). Capturing them caught two real bugs, both fixed: long stat-card values (honors) ran off the monitor (now sized by length, parentheses moved to the label), and `generate._source_line` labeled every fact that wasn't Sleeper or muffed as "nflverse, checked against Sleeper" (Wikipedia honors included); it now states each fact's real source and check, and the 10 saved runs were corrected.

## Submitting (Nov 7)

`.venv/bin/python export.py` writes `outputs/` (readable transcripts of the saved runs) and `~/Documents/Sideline-submission-<date>.zip` (code, docs, git history, runs with audio, transcripts; never `.env`, `.venv`, `.cache`; refuses if a key pattern is found). The professor asked for the full project: code and outputs.

## Hosting and submission files (Nov 8)

The live version runs on Google Cloud Run (the user's Google Cloud project, the one with the voices), built from the root `Dockerfile` by `hosting/deploy-cloud-run.sh`, which the user runs in Cloud Shell from a clone of GitHub `main` (push first). Steps are in `hosting/README.md`. Hugging Face was the first plan; dropped Nov 8 because Docker Spaces now need a paid plan. Live since Nov 8: https://sideline-380036639629.us-east1.run.app (project `sideline-514000`, region `us-east1`; the user linked billing and granted the build service account `roles/run.builder` themselves). The keys and access code are saved only in the user's Cloud Shell (`~/.sideline-keys`); the code goes in the submission, never in this public repo. Redeploy: push, then in Cloud Shell `cd ~/sideline && git pull && hosting/deploy-cloud-run.sh`. Take down after grading: `gcloud run services delete sideline --region us-east1`. Driving Cloud Shell from the app's browser: the `type` action doesn't reach the terminal, but `key` with space-separated characters does (100 keys per call), and the connection drops often (click Reconnect, then retype). Cloud Run settings: 2 GiB (the server peaks near 480 MB loading data, and Cloud Run's disk is memory), 1 CPU, CPU not throttled (segments run in a background thread while the page polls), max 1 instance (jobs live in memory), scales to zero. Settings that are off on the user's Mac: `HOST`/`PORT`, `SIDELINE_ACCESS_CODE` (new segments need it; replays don't; the page shows a code box when `/api/config` says so), `SIDELINE_DAILY_LIMIT` (15 in the Dockerfile; turned-away questions don't count), `SIDELINE_MAX_AT_ONCE` (1). Keys are Space secrets, never in the repo. The slides are `docs/slides/Sideline-slides.pdf` (the deck itself is a Claude artifact); the 53-second clip is `docs/video/sideline-best-qb.mp4`. The README is the front page for the professor; class-facing text stays in the user's plain voice.

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
- GitHub (Nov 7): the project is public at https://github.com/IanPierce57/sideline (user's account IanPierce57; chose public, outputs included). `main` holds the final version. The GitHub tool is at `~/.local/bin/gh` (not on PATH). After committing on `step-1-scripts`, bring `main` up with `git fetch . step-1-scripts:main` and push both only when the user asks. Commits link to the account through its no-reply email (set in this repo's git config). `runs/` and `outputs/` are committed now (outputs); never commit `.env`.
