# Sources

The "Facts and data" section of BRIEF.md is the authority on sources. This file repeats the brief's list and adds the reference sites collected later, so everything is in one place.

## Pipeline (the research agent pulls from these)

| Source | Used for |
| --- | --- |
| [nflverse via nflreadpy](https://github.com/nflverse/nflreadpy) | NFL play-by-play, player stats, Next Gen Stats, FTN charting, injuries, schedules, depth charts, rosters, trades. Tested Nov 4, 2026: works, current through Week 8. |
| [Sleeper API](https://docs.sleeper.com/) | Approved Nov 4, 2026, including its undocumented stats feed. Current NFL and NBA players (team, position, injury status, depth chart), the current season and week, weekly and season stats for both leagues, and trending adds and drops. Free for non-commercial use; credit Sleeper wherever its trending data is shown. Ask for the full player list at most once a day, and stay well under 1,000 calls a minute. |
| Web search | News context and pre-1999 NFL numbers, with links saved |

For the NBA, Sleeper is the only source so far, so NBA stats can't pass the two-source check until a second NBA source is added (balldontlie is the candidate).

## Cross-check (the checker agent's second source)

| Source | Used for |
| --- | --- |
| nflverse play-by-play, recomputed | Advanced NFL stats (EPA and the like) worked out again from the raw plays, a different calculation from the one the research agent used |
| [NFL.com](https://www.nfl.com) | Official NFL stats and injury reports. Check by hand. |

| Sleeper stats | The independent second source for basic NFL stats, and the second roster source for the NFL (checked against nflverse rosters) |

The NBA has no second source yet.

## Candidates (tested Nov 4, 2026; waiting on a decision)

| Source | What it offers | Status |
| --- | --- | --- |
| [balldontlie](https://www.balldontlie.io/) | NBA developer API. Free tier has no stats; $9.99/month adds every game's player stats; $39.99/month adds season averages and standings. | Possible NBA source. Terms not checked yet. |
| [MyFantasyLeague API](https://api.myfantasyleague.com/2026/api_info) | Free "in almost any way"; NFL players and injuries. Says it will never provide raw player stats. | Possible extra NFL roster and injury check only. |
| [MySportsFeeds](https://www.mysportsfeeds.com/feed-pricing/) | NFL and NBA feeds; personal plans from about $5/month per league, stats extra. | Paid fallback. Terms not checked. |
| NFL team websites | Official current rosters | Terms not checked. By hand only. |

## News ticker (to choose)

| Source | Used for |
| --- | --- |
| Not chosen yet | Real-time NBA and NFL headlines for the crawl along the bottom of the screen. Check the source's terms on scraping and AI use before connecting it. Sleeper's trending players (credited) could fill the ticker in the meantime. |

## Manual only (check numbers by hand; don't connect these to the app)

From the brief:

| Source | Used for |
| --- | --- |
| [PerThirtySix](https://www.perthirtysix.com) | Checking NFL advanced numbers by hand, method notes |
| RayCarp | Checking numbers by hand, method notes |
| [NFL Next Gen Stats site](https://nextgenstats.nfl.com) | Checking tracking stats by hand (the app gets Next Gen Stats through nflverse) |

Added later. Their terms have not been checked, so they stay manual only until someone checks their rules on scraping and AI use, the way the brief did for the others:

| Source | League | Used for |
| --- | --- | --- |
| [NFL Savant](https://nflsavant.com) | NFL | Play-by-play and advanced team and player stats. Confirm which seasons it covers. |
| [rbsdm.com](https://rbsdm.com/stats/stats/) | NFL | EPA per play and CPOE by quarterback |
| [Over The Cap](https://overthecap.com) | NFL | Cap space, contracts, guarantees, dead money |
| [Spotrac](https://www.spotrac.com) | NFL and NBA | Contracts and cap position |
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
