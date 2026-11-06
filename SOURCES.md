# Sources

The "Facts and data" section of BRIEF.md is the authority on sources. This file repeats the brief's list and adds the reference sites collected later, so everything is in one place.

## Pipeline (the research agent pulls from these)

| Source | Used for |
| --- | --- |
| [nflverse via nflreadpy](https://github.com/nflverse/nflreadpy) | NFL play-by-play, player stats, Next Gen Stats, FTN charting, injuries, schedules, depth charts, rosters, trades, head coaches (in schedules), combine results, and draft picks. Tested Nov 4, 2026: works, current through Week 8. |
| [Sleeper API](https://docs.sleeper.com/) | Approved Nov 4, 2026, including its undocumented stats feed. Current NFL and NBA players (team, position, injury status, depth chart), the current season and week, weekly and season stats for both leagues (including each NFL team defense's points allowed per week, used to confirm final scores), the NFL schedule (`api.sleeper.app/schedule/nfl/...`, used to confirm games), and trending adds and drops. Free for non-commercial use; credit Sleeper wherever its trending data is shown. Ask for the full player list at most once a day, and stay well under 1,000 calls a minute. |
| Web search | News context and pre-1999 NFL numbers, with links saved |

For the NBA, Sleeper is the only source so far, so NBA stats can't pass the two-source check until a second NBA source is added (balldontlie is the candidate).

| [Wikipedia](https://en.wikipedia.org/w/api.php) | Career titles and awards from player infoboxes, trusted on its own for honors (decided Nov 4, 2026). CC BY-SA 4.0; official API; credit "Honors: Wikipedia". |

## Cross-check (the checker agent's second source)

| Source | Used for |
| --- | --- |
| nflverse play-by-play, recomputed | Advanced NFL stats (EPA and the like) worked out again from the raw plays, a different calculation from the one the research agent used |
| [NFL.com](https://www.nfl.com) | Official NFL stats and injury reports. Check by hand. |
| [Wikidata](https://www.wikidata.org) | Cross-check for major awards (MVP, Finals MVP, Player of the Year). CC0. Many recent awards aren't recorded yet; those pass on Wikipedia alone. |
| nflverse Super Bowl results and season rosters | Cross-check for Super Bowl rings |

| Sleeper stats | The independent second source for basic NFL stats, and the second roster source for the NFL (checked against nflverse rosters) |

The NBA has no second source yet.

## Candidates (tested Nov 4, 2026; waiting on a decision)

| Source | What it offers | Status |
| --- | --- | --- |
| [muffed.ai](https://muffed.ai/mcp) | NFL advanced stats (EPA per dropback, success rate, Next Gen Stats CPOE, and more) through a free, read-only MCP server built for AI assistants (`https://muffed.ai/api/mcp`, no key). Built on nflverse, so it confirms our calculations and definitions match a published source; it doesn't independently confirm the raw data. Tested Nov 4, 2026: 2025 EPA per dropback matched for all 25 QBs it ranks, to four decimals. Terms: free for individuals; "email first" before building it into a product (hello@muffed.ai); no bulk scraping; carry the credit line "Data via nflverse · NFL Next Gen Stats via nflverse · FTN Data via nflverse" everywhere its numbers appear. | Approved by the user Nov 4, 2026 to cross-reference NFL advanced stats and team records; also team scoring, EPA, takeaways, third-down and red-zone rates (Nov 5, 2026: 41 of 42 matched for six teams). Answers are saved for 6 hours and requests are spaced out. Per its terms, the user emailed hello@muffed.ai (Nov 5, 2026); muffed.ai replied that use for a school project is fine. |
| [balldontlie](https://www.balldontlie.io/) | NBA developer API. Free tier has no stats; $9.99/month adds every game's player stats; $39.99/month adds season averages and standings. | Possible NBA source. Terms not checked yet. |
| [MyFantasyLeague API](https://api.myfantasyleague.com/2026/api_info) | Free "in almost any way"; NFL players and injuries. Says it will never provide raw player stats. | Possible extra NFL roster and injury check only. |
| [MySportsFeeds](https://www.mysportsfeeds.com/feed-pricing/) | NFL and NBA feeds; personal plans from about $5/month per league, stats extra. | Paid fallback. Terms not checked. |
| NFL team websites | Official current rosters | Terms not checked. By hand only. |

## News ticker

| Source | Used for |
| --- | --- |
| [GNews](https://gnews.io) (free plan) | The day's NFL and NBA headlines. Terms (checked Nov 4, 2026): free use is "personal, academic, evaluation, and other non-commercial use"; "reasonable caching" allowed; articles about 12 hours late. Key goes in .env via `./set_key.sh gnews`. A story runs only if two or more outlets report it. |

## Manual only (check numbers by hand; don't connect these to the app)

From the brief:

| Source | Used for |
| --- | --- |
| [PerThirtySix](https://www.perthirtysix.com) | Checking NFL advanced numbers by hand, method notes |
| Yahoo Fantasy Sports API | Considered Nov 5, 2026, not a fit right now: access is by application and Yahoo account sign-in; its developer terms ask that user data be removed within 24 hours and require the Yahoo Fantasy logo and a privacy policy; it doesn't name its stats provider, and Sleeper, nflverse, and muffed.ai already cover the same numbers. |
| Bluesky public posts | Considered Nov 5, 2026 for fan opinion, then dropped by the user: Royce's eye-test images and metaphors cover it instead. (Search now requires signing in, and most posts about players are fantasy, betting, or promos.) |
| [Roll Coverage](https://rollcoverage.com) | Reading by hand: coaching staffs, scheme and matchup pages, and its source list (checked Nov 5, 2026). Its terms ban automated access: "Do not scrape, crawl or download either site in bulk by automated means." Most of its data is nflverse, which Sideline already uses directly. |
| RayCarp | Checking numbers by hand, method notes |
| [NFL Next Gen Stats site](https://nextgenstats.nfl.com) | Checking tracking stats by hand (the app gets Next Gen Stats through nflverse) |

Added later. Their terms have not been checked, so they stay manual only until someone checks their rules on scraping and AI use, the way the brief did for the others:

| Source | League | Used for |
| --- | --- | --- |
| [NFL Savant](https://nflsavant.com) | NFL | Play-by-play and advanced team and player stats. Confirm which seasons it covers. |
| [rbsdm.com](https://rbsdm.com/stats/stats/) | NFL | EPA per play and CPOE by quarterback |
| [NBA RAPM](https://nbarapm.com) | NBA | RAPM, multi-year impact, DARKO, LEBRON, RAPTOR (RAPTOR is history only) |
| [databallr](https://databallr.com) | NBA | Impact metrics, with/without lineup splits, shot quality, contracts |
| [RealGM advanced stats](https://basketball.realgm.com/nba/stats/2026/Advanced_Stats/Qualified/points/All/desc/1/Regular_Season) | NBA | True shooting, usage, assist and turnover rates, ratings |
| [Dunks & Threes](https://dunksandthrees.com/epm) | NBA | EPM impact ratings |
| [BBall Index](https://www.bball-index.com/) | NBA | LEBRON impact metric (likely mostly paid) |
| DARKO | NBA | Daily impact projections |
| [Crafted NBA](https://craftednba.com/) | NBA | Several impact metrics on one page (has a paid tier) |
| HoopsHype | NBA | Salaries |
| [Hoop Explorer](https://hoop-explorer.com/LineupAnalyzer?filter=&maxTableSize=50&minPoss=5&) | Probably college only | Lineup analysis. Confirm it covers the NBA before using it. |

## Never

| Source | Why |
| --- | --- |
| Pro Football Reference, Basketball-Reference | Sports Reference's terms ban scraping and AI use (linked in BRIEF.md) |
| SumerSports | Terms ban scraping and AI use |
| PFF, Cleaning the Glass | Paid; the app can't reach them |
| ESPN (site, rosters, stats, news, and its public JSON feeds) | Ruled out Nov 4, 2026. ESPN is covered by Disney's terms, which forbid accessing content "using a robot, spider, script, or other automated means" and any use with AI tools. |
| nba_api / NBA.com stats | Ruled out Nov 4, 2026. NBA.com blocks programs unless they pretend to be a web browser, and its terms bar using the stats in anything that "features a database." |
| NBA team websites | Ruled out Nov 4, 2026. They live on NBA.com, under the same blocking and terms. |
| NFL.com and NFL Next Gen Stats site | Ruled out for the app Nov 4, 2026. NFL terms forbid "systematic retrieval of data" without written consent. (Next Gen Stats numbers still come in through nflverse.) |
| StatMuse | Ruled out Nov 4, 2026. Terms ban bots, scrapers, and machine learning or AI use. |
| Google News RSS | Ruled out Nov 4, 2026. The feed says it's "made available solely for the purpose of rendering Google News results within a personal feed reader"; "any other use of the feed is expressly prohibited." |
| Spotrac | Ruled out for the app Nov 4, 2026. Terms forbid "systematically extract, collect or harvest" data, data mining or robots, and putting its material in any database. Fine to read by hand. |
| Over The Cap (and nflverse's contracts dataset, which comes from it) | Ruled out for the app Nov 4, 2026, unless licensed. Terms forbid "any systematic retrieval, by manual, automated or other means" to compile a database, and any robot or spider. Licenses: support@overthecap.com. |
