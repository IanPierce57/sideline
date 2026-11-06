# Sports Debate Show: Project Brief

Nov 3, 2026 · @Ian (aligned with the bibles Nov 4, 2026)

## Status

10 days to the November 14 deadline. The plan is locked and the bibles are drafted, so building in Claude Code starts now.

**Done**

- [x] Concept: type an NBA or NFL topic, get a 3-to-5-minute debate segment
- [x] Format: a webpage that runs on your laptop
- [x] Scope: NBA and NFL only, **current players only** (decided Nov 4, 2026), no draft topics
- [x] Tone: real debate, hosts keep personalities, fewer bits
- [x] Spec: segment flow, debate rules, scoring, fact rules, screen and sound
- [x] Data sources chosen and checked against their terms
- [x] Character bibles drafted for serious debate
- [x] Subtitles first, voices later; Claude Code draws the pixel art
- [x] Name: Sideline (renamed from The Receipts on Nov 4, 2026)
- [x] Project folder holding this brief (saved as BRIEF.md), the bibles, and SOURCES.md

**Not done yet**

- [ ] Claude Code running, plus an API key with about $25 of credits
- [ ] Step 1 working: text scripts from a typed topic

## What it is

Name: **Sideline**, a sports call-in debate show: a caller gets on the line, and the desk argues it out. (Renamed from The Receipts on Nov 4, 2026.)

A webpage that generates a three-to-five-minute NBA or NFL debate on any topic you type about today's players and teams. A moderator and three pixel-art co-hosts argue it out in an 8-bit studio, in subtitles, using real stats that are researched and fact-checked first. A background judge scores every argument, and the most persuasive host wins.

It's a solo final project for an AI class, built entirely with Claude Code by someone who has never coded.

## How a segment works

1. You type an NBA or NFL topic about active players or current teams, and hit go.
2. The topic check screens it, and the pipeline sorts it into a format: debate, buy or sell, or prediction.
3. While it generates, the hosts get ready on set: reading notes, walking to their spots. A small control-room panel shows the pipeline steps.
4. A caller asks your question in their own words, and the moderator takes the call.
5. The moderator restates the question and names the format.
6. The hosts argue in subtitles, each leaning on his kind of evidence. A judge scores every argument in the background.
7. The moderator lets the argument run, then pulls everyone back and asks each host for a one-sentence final answer.
8. The moderator announces the winner by score, summarizes the winning argument, and notes where the others still disagree.
9. You can download the finished segment as a video.

## Debate rules

The goal is a real argument. Hosts keep their personalities, but the substance is evidence and rebuttal, not bits.

- **Evidence leans.** No host owns a kind of evidence, but each leans on one more than the others, set by his bible: analytics (Deacon), the eye test and the story, told with vivid images and metaphors that fit how the player really plays, backed by basic box-score numbers (Royce), or the front-office view: the cap, contracts, roster fit, and scheme (Lonnie). He still uses whatever wins the point. The leans differ, so arguments clash.
- **Structure.** Every argument is a claim, its evidence, and why it matters.
- **Engagement.** Every reply deals with the previous point directly: rebut it, concede it, or reframe it. No talking past each other.
- **No drift to the middle.** Hosts can concede a specific point but change their overall position only when a fact defeats it. Nobody ends on "both sides make good points." (Lonnie's one switch per segment follows the same rule: he switches only for a new fact or argument, and says what changed his mind.)
- **Plain English.** Hosts can get as technical as the argument needs. The first time an advanced stat comes up, someone explains it in one plain sentence, like: "EPA measures how much a play raises or lowers the points a team should expect on that drive."
- **Length.** 3 to 5 minutes. The segment ends when new arguments run out. Repeated points get cut, never padded.
- **Heat.** Blowups only when the topic earns one. Tangents are fine when they serve an argument.
- **Limits.** Players, coaches, and teams are fair game to criticize. Family and personal life are off-limits. Off-field legal trouble comes up only if it's the topic, stated as fact, with no jokes.
- **Language.** No profanity from anyone on the show. Every bible rules it out, so the subtitles never need censoring.
- **Consistency.** Hosts sound like their bibles every time. There's no memory between segments.
- **Worst-supported take (optional).** The moderator gives it only when the fact pack contradicts a host's argument. First extra to cut.

## Scoring

The most persuasive host wins. A judge agent scores every argument in the background, using criteria adapted from competitive debate judging. The moderator never picks the winner; he announces the judge's result.

| Criterion | What the judge asks | Weight |
| --- | --- | --- |
| Evidence | Are the facts relevant, verified, and from a big enough sample? | 30% |
| Reasoning | Does the evidence actually prove the claim? | 25% |
| Rebuttal | Does it answer the opponent's strongest point directly? | 25% |
| Impact | Does it show why this matters to the question asked? | 10% |
| Clarity | Is the claim specific and easy to follow? | 10% |

Each criterion gets 1 to 5 points per argument, weighted and scaled to a score out of 100.

- **Averages, not totals.** A host's score is the average of his arguments, so talking more doesn't win. Each host needs at least two scored arguments.
- **Dropped arguments count.** As in competitive debate, a point nobody answers counts as conceded. Its maker gets a bonus, 5 points to start, tuned after testing.
- **Volume, insults, and repetition** earn nothing.
- **Blind judging.** The judge sees Host 1, 2, and 3, not names, so it can't favor a character.
- **Ties** go to the higher rebuttal score.
- **Close after scoring.** The moderator's closing lines are written once the score is in, so the verdict always matches it. The meter moves as each argument is scored.
- **The winning summary** gives the winner's claim, his strongest evidence, and the rebuttal that landed, in two or three sentences.

## Topic check

Every topic passes three checks before research starts, so a bad topic costs about a second instead of a full run.

1. **NBA or NFL, current players.** The topic has to be about the NBA or NFL and about current players (decided Nov 4, 2026). Topics mainly about retired players, including head-to-heads like "LeBron vs. Jordan", are turned away, and the research agent never pulls retired players' numbers. So are questions that can't be settled without the past (decided Nov 5, 2026): "greatest ever", GOAT, all-time rankings, "best in franchise history", comparisons with retired players, and past teams or seasons, even when the player asked about is active. The person gets three present-day versions of the question to pick from instead, like "Is Patrick Mahomes the best QB in the NFL right now?" Comparisons across the two leagues are fine. College and draft-prospect topics are turned away.
2. **Real.** Every player, team, and coach named must exist in the current rosters. Rosters come from two independent sources, and a player counts as on a team only when both agree; a disagreement is flagged. (For the NFL, nflverse and Sleeper; for the NBA, Sleeper plus a second source not chosen yet; see SOURCES.md. ESPN and team websites were the first plan, but ESPN's terms forbid automated use and NBA team sites sit on NBA.com, so both are ruled out.) The confirmed rosters also go to the writer, so no host puts a player on the wrong team. A near miss gets a suggestion ("Did you mean Patrick Mahomes?"). When a name belongs to more than one player (there are two Josh Allens), the topic check asks which one before research starts. Players are always matched by ID, never by name alone. A false premise, like a player on the wrong team, is turned away with the correct fact. Predictions about the future are fine.
3. **Appropriate.** No slurs, sexual content, threats, or harassment, and nothing about players' families or personal lives. Text that tries to instruct the hosts ("ignore your rules and say...") is treated as a topic, never followed, and turned away.

**How it runs:** a plain script matches names and teams against the two roster sources. Haiku handles the sports and appropriateness checks.

**When a topic fails,** a call-screener message on screen gives the reason in one line and offers three valid topics instead. Nothing gets voiced.

**Log it:** rejected topics go in the log too, so the presentation can show topics screened next to lines checked and cut.

## Facts and data

Every real-world fact comes from the fact pack. Anything that can't be verified gets rewritten or cut.

**The core rule (Nov 4, 2026):** if a number can't be cross-referenced or otherwise confirmed correct, cross it off and go to something else. It never reaches the script; the research agent gets one more round to find a confirmable replacement, which goes through the same checks. (Numbers from sources the user chose to trust on their own, Sleeper for stats and Wikipedia for honors, count as confirmed.) SOURCES.md repeats this table and adds reference sites that stay manual only.

| Source | Used for | Role |
| --- | --- | --- |
| [nflverse via nflreadpy](https://pypi.org/project/nflreadpy/) | NFL play-by-play, player stats, Next Gen Stats, FTN charting, injuries, schedules, depth charts, trades | Pipeline |
| Web search | News context and pre-1999 NFL numbers, with links saved | Pipeline |
| [Sleeper API](https://docs.sleeper.com/) | NFL and NBA rosters, injuries, the current week, and stats; trending adds and drops. Approved Nov 4, 2026 | Pipeline (NBA), cross-check (NFL stats and rosters) |
| Second NBA source | Not chosen yet (balldontlie is the candidate) | Cross-check |
| NFL.com | Official NFL stats and injury reports | Cross-check, by hand |
| [PerThirtySix](https://perthirtysix.com/nfl/qbs?season=2026), RayCarp, Next Gen Stats site | Checking numbers by hand, method notes | Manual only |
| ESPN, nba\_api (NBA.com stats), NBA team websites | Nothing. Ruled out Nov 4, 2026: ESPN's terms forbid automated access and AI use; NBA.com blocks programs and bars database use (details in SOURCES.md) | Never |
| Pro Football Reference, Basketball-Reference, SumerSports | Nothing. Their terms ban scraping and AI use ([Sports Reference](https://www.sports-reference.com/data_use.html), [SumerSports](https://sumersports.com/terms-of-service/)) | Never |

**Two agents build the fact pack.** A research agent finds the stats; a separate checker agent proves them. Only stats the checker passes go into the fact pack, and the script writer sees nothing else.

1. **Research agent.** Reads the topic, decides which stats the debate needs, and pulls them from the pipeline sources with code. Each stat is saved with its value, exact definition, sample size, source, and an "as of" date.
2. **Checker agent.** Gets each stat again on its own, without seeing the research agent's value, then compares the two with a plain script:
    - Basic stats are matched against a second, independent source (Sleeper for the NFL; the NBA's is not chosen yet). The official source wins, and a mismatch means flag or drop.
    - Advanced stats are recomputed from the raw data (for example, nflverse play-by-play) under the same definition.
    - Pre-1999 NFL numbers need two independent web sources that agree.
    - Sample-size minimums are enforced.
3. **Result.** Passed stats go into the fact pack. Every dropped stat goes in the rejection log with the reason.

**Every stat in the fact pack stores** its value, exact definition, sample size, source, and an "as of" date.

**Checking rules**

- **Basic stats** like yards, touchdowns, and points get cross-checked against a second source. Sleeper is trusted (decided Nov 4, 2026): when nflverse and Sleeper disagree, Sleeper's number is used and the disagreement is logged. For the NBA, Sleeper alone is enough.
- **Coaches, measurables, and the draft** (added Nov 5, 2026). A team's head coach must match on nflverse and Wikipedia. Listed height and weight come from Sleeper (trusted; height must be within an inch of his pre-draft height). Combine results (40-yard dash, jumps, bench, drills, combine weight) must match the pre-draft table on his Wikipedia page. Draft position must match his Wikipedia infobox.
- **Same week on both sides** (added Nov 5, 2026). When two sources cover different weeks, ours is recalculated through the other source's week before comparing, so a one-day gap doesn't cross off good numbers.
- **Opinions about play style** (decided Nov 5, 2026). Opinions don't need to be provably true ("Caleb Williams is exciting" is fine), but they can't be ones no knowledgeable fan would hold ("Jared Goff is a dual-threat quarterback"). Each player gets a style profile from real stats, ranked against his position, given to the writer and the checker in words only. Common labels (dual threat, pocket passer, gunslinger, deep threat, possession receiver, workhorse back, pass rusher, ball hawk, shooter, playmaker, rim protector) are checked against it, and clear contradictions are rewritten.
- **Position names** (decided Nov 5, 2026). Sources label the same player differently (Micah Parsons: LB on Sleeper, outside linebacker and defensive end on Wikipedia), so one glossary lists which labels can stand in for which: running back, halfback, and sometimes fullback; tackle, guard, and offensive line; defensive end, edge, outside linebacker, and linebacker for edge rushers; defensive back, corner, safety, and nickel. The pairs don't chain: an edge rusher can be called a linebacker, but an off-ball (Mike or Will) linebacker is never a defensive end.
- **Single NFL games** (decided Nov 5, 2026). "Who wins Packers at Patriots this Sunday?" works for NFL games in the next two weeks. Code first confirms the game is real: date, home, and away must match on nflverse's and Sleeper's schedules, or the question is turned away with real upcoming games to pick from. Then a game pack is pulled and checked: both records; points scored and allowed per game, offense and defense EPA per play, takeaways, third-down and red-zone rates (each must match muffed.ai through the same week; a league rank is shown only when our ranking of all 32 teams agrees with muffed's); the last three results and any meeting this season (every score checked against Sleeper's weekly team numbers); the last game's starting quarterbacks (checked against Sleeper's games-started); and injured starters (Sleeper, trusted, said as of today). Each host picks a winner; no score predictions, spreads, or betting talk. NBA single games are turned away until an NBA schedule source is approved.
- **Advanced stats** (NFL) are cross-referenced against a second reputable source that publishes the same stat under the same definition, rather than recalculated. They must match exactly, or they're dropped. Tested Nov 4, 2026: muffed.ai (built on nflverse, with an AI-ready connection) matched our 2025 EPA per dropback for all 25 QBs it ranks once the definition matched. Definitions matter: "EPA per dropback" means plain EPA (not QB EPA) averaged over every dropback credited to the quarterback, scrambles and sacks included; and "CPOE" from Next Gen Stats and from nflverse's own model are two different stats (Mahomes 2025: -2.7 vs +0.3), so the fact pack always names which one. They must also match the fact pack exactly, under the same definition. Caleb Williams is 0.16 EPA per play on SumerSports and +0.28 EPA per dropback on PerThirtySix, and both are correct.
- **Sample size.** No league-best or league-worst claims below the minimum, such as 150 dropbacks, unless the host mentions the small sample.
- **Rounding.** Counts must be exact. Rates can round to one decimal. "About" is allowed only when rounding a real number.
- **Host careers** are fiction, checked against the bibles. Their stories never name real games or real teammates.
- **Opinions and predictions** aren't checked.
- **A failed line** gets rewritten with verified numbers, and is cut only if that fails. Then the checker rereads the lines around it so the conversation still flows.
- **The rejection log** records every caught stat and line: what the host said (or the research agent found), what the data said, and whether it was rewritten or cut. It becomes a presentation slide.

**Honors and records:** career titles and awards come from Wikipedia (CC BY-SA), which is trusted on its own (decided Nov 4, 2026), like Sleeper for stats. Where a second source exists it's still checked: Super Bowl rings against nflverse's Super Bowl winners' rosters, MVPs and other major awards against Wikidata; if one disagrees, Wikipedia's number is used and the disagreement is logged. Years are shown only when they add up to the count Wikipedia states. QB playoff records come from nflverse's official scores, with playoff starts checked against Sleeper. **Contracts:** no allowed source yet; Spotrac's and Over The Cap's terms both forbid automated collection (Over The Cap offers licenses at support@overthecap.com). nflverse NFL stats start in 1999. Older NFL numbers come from web search and need two independent sources that agree, or they get cut.

**On screen:** a stat chyron shows the value, a plain-English definition, the source, and how current it is ("Through Week 9"), and a source list appears at the end.

## Cast

A moderator and three hosts, each defined by a bible in the characters folder, plus a pool of callers. The biggest difference between the hosts is the kind of evidence each one leans on.

- **Moderator: Hal Brennan** (characters/moderator.md). Asks the questions, doesn't interrupt, and lets the argument run until it's time to move on, then brings everyone back. His bible covers how much chaos he tolerates, how he cuts in, how he wraps up, how he announces the judge's winner, and one quirk.
- **Three hosts.** Royce Stanhope (Host A, the eye test and the story), Deacon Pettiford (Host B, analytics), and Lonnie Fairweather (Host C, the front-office decision). Each bible covers:
    - Name, age, look, and a signature animation
    - A fictional career: stats, rings, and stories
    - Teams and players he loves and hates
    - The evidence he leans on and how he argues
    - Standing takes he'll defend no matter what
    - What sets him off
    - Voice, pace, catchphrases (once per segment at most), and 5 to 10 sample lines
    - What he thinks of each other host and the moderator
    - Lines he'd never say
- **Callers** (characters/callers.md). A pool of six types: the diehard, the stats nerd, the rival fan, the old-timer, the skeptic, and the settler, so each opening sounds different.

**Banks:** each host bible already has a takes bank, a career or life bank, a line bank, and one example exchange; the moderator bible has his lines, and the callers file has sample openings. Every character now has a look. Still to add once the bibles pass the blind test: two to four more example exchanges per host.

**Blind test:** hide the speaker names in a script and check whether you can tell who's talking from the lines alone.

## Screen and sound

An 8-bit studio, the same set every time, with the page around it themed to match. The set says NBA and NFL at a glance: a night stadium behind the desk where a football field runs into a basketball court along one painted sideline, a football and a basketball on the desk, and a hardwood floor. No league, team, or network logos.

- **Subtitles first.** Lines appear as pixel-font subtitles paced at speaking speed, with the speaker's name, while his character animates. Voices are a stretch goal.
- **Pixel art.** Claude Code draws all the characters and the set in code.
- **Emotion** comes through body animation driven by each line's delivery tag: leaning in, pointing, standing up, slamming the desk, throwing hands up, turning away. Each character's tell from his bible (Royce's pencil, Deacon's toothpick, Lonnie's sleeves, Hal's headphones) is part of his animation set.
- **On screen:** subtitles (a speech bubble over whoever is talking), a topic banner, a stat chyron on the right-hand monitor whenever a stat comes up, a score bug across the top showing each host's score as arguments are judged, and an end card with each host's final answer and the source list.
- **Sound:** no theme music. A desk-slam effect is optional.
- **News ticker:** the crawl along the bottom carries the day's NFL and NBA headlines (decided Nov 4, 2026: free, and a delay is fine). Source: GNews's free plan, whose terms allow academic and non-commercial use (articles arrive about 12 hours late). Headlines are shown exactly as the outlets wrote them, with the outlet named, and a story runs only if two or more different outlets report it; opinion, rumors, and betting (picks, odds, rankings, fantasy, "could", "reportedly", trade pitches) and banned outlets are skipped. No fantasy trends (decided Nov 4, 2026). Refreshed at most every 6 hours. With no confirmed headlines (or no GNews key), the ticker shows a short Sideline placeholder, never invented headlines.
- **Cast cards:** the page introduces Hal and the hosts by background and personality only. How each one argues (their kind of evidence, catchphrases) should come through on air, not in the descriptions.
- **Branding:** Sideline, with a logo.
- **Credits and disclaimer** on the page: everyone on the show is fictional and everything they say is AI-generated opinion; callers are never real people (no parodies of real athletes, broadcasters, or public figures); the show isn't affiliated with the NBA, NFL, ESPN, or any team; every stat source and voice dataset is credited wherever its license asks.
- **Voices (last, stretch goal).** Use a free, local text-to-speech tool such as Piper, with ready-made voices trained on open datasets like LibriTTS-R and VCTK (CC BY 4.0). Pick one distinct voice each for Hal, Royce, Deacon, and Lonnie, plus a few for callers. Check each voice's license before using it, and add the dataset credits to the page.

## How it's built

Everything runs on your laptop: a small local server starts each generation, and the webpage plays the result. API keys live in a private .env file, never in the page code, this brief, or a chat.

**Pipeline**

1. **Topic in.** Run the topic check, then sort the topic into a format: debate, buy or sell, or prediction.
2. **Research.** The research agent pulls stats from nflverse (NFL) and the NBA source once it's chosen, plus news and pre-1999 NFL numbers from web search.
3. **Verify.** The checker agent re-gets each stat on its own and cross-checks it (see Facts and data). Only passed stats enter the fact pack; dropped ones go in the rejection log.
4. **Write.** Produce the debate as structured lines: speaker, text, delivery, the fact IDs each line uses, and which argument it belongs to.
5. **Check.** A plain script matches every number in the script against the fact pack, and an AI checker handles other claims. Failed lines get rewritten or cut, and everything is logged.
6. **Judge.** Score every argument blind, using the Scoring criteria, and pick the winner.
7. **Close.** Write the moderator's verdict and the summary of the winning argument, now that the score is known.
8. **Assemble.** Save a timeline file: who speaks when, subtitle timing, animations, chyrons, and meter updates.
9. **Play.** The page plays the timeline.

**Models:** Sonnet for writing, research, verifying, checking, judging, and the close. Haiku for small jobs like the topic check and sorting the format.

**Speed target:** topic to playback in about 2 minutes or less. Skipping voices for now makes this easier. Measure it on November 8.

## Schedule

Get an ugly version working end to end, with a plain page showing a scored, subtitled segment, by November 9. Then improve it. The dates are a guide for making sure everything gets addressed, not a fixed order.

- [ ] **Nov 4-5:** Set up Claude Code and the API key. Put the brief and bibles in the project folder. Generate text scripts from a typed topic, read five, and fix the bibles.
- [ ] **Nov 6-7:** Data pull from nflverse and the NBA source, the topic check, the research and checker agents, the fact pack, the number checker, and the rejection log.
- [ ] **Nov 8:** The judge, scoring, and the close. Time a full run from topic to finished script.
- [ ] **Nov 9-11:** The webpage: input box, studio, sprites, subtitles, player, loading screen, chyron, and meter.
- [ ] **Nov 12:** Test 20 topics and fix what breaks.
- [ ] **Nov 13:** Freeze the code, record a backup segment, and build the presentation.
- [ ] **Nov 14:** Due.

**If you fall behind, cut in this order:**

1. Video download (screen-record a segment instead)
2. The trailer
3. The animated meter (keep the scoring)
4. The hosts-getting-ready animation (use a static "stand by" screen)
5. The caller opener
6. Worst-supported take

**Never cut:** a typed topic becoming a subtitled, scored segment on a pixel page, backed by the research step and the fact-check log.

**Stretch goal, only if everything above works:** voices.

## Presentation

Three minutes, built around one live run with a classmate's topic.

| Time | What happens |
| --- | --- |
| 0:00 to 0:10 | A classmate calls out a topic. You type it and hit go. Keep three typed backups in case the room is quiet. |
| 0:10 to 0:50 | The trailer plays while it generates. Cut it only from real generated segments. |
| 0:50 to 1:40 | The pipeline live on screen: research finding stats, the checker confirming them, the script appearing, the line checker catching lines. |
| 1:40 to 2:50 | The first minute or so of the segment. |
| 2:50 to 3:00 | The kicker: you'd never coded, and Claude Code built all of it. |

**Numbers to show:** generation time, stats found, stats verified and dropped, lines checked, lines cut, and cost per segment.

**Backup:** a finished segment and a screen recording, in case the live run stalls or the wifi drops.

## First prompt for Claude Code

Kept as a record of how the build started. The live instructions for each session are in CLAUDE.md.

```
I've never coded before, so explain what you're doing in plain language
as you go. I'm building "The Receipts": a webpage where you type an NBA
or NFL topic and AI generates a 3-to-5-minute debate between a moderator
and three hosts.

Before anything else, read BRIEF.md (the full project spec) and every
file in the characters folder (the character bibles). Follow them. If
something is unclear or contradicts itself, ask me instead of guessing.

TODAY'S GOAL: STEP 1, AN UGLY VERSION I CAN SEE WORKING
(the full step 1 request: a Python script writer, runs saved as JSON,
a plain subtitle page, one start command, a README, git, CLAUDE.md,
and three test topics)
```

After step 1 works, read the three test scripts, fix the bibles wherever a host sounds generic, then ask for one pipeline step at a time, in the order under How it's built.
