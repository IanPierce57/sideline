# Sources

The "Facts and data" section of BRIEF.md is the authority on sources. This file repeats the brief's list and adds the reference sites collected later, so everything is in one place.

## Pipeline (the research agent pulls from these)

| Source | Used for |
| --- | --- |
| [nflverse via nflreadpy](https://github.com/nflverse/nflreadpy) | NFL play-by-play, player stats, Next Gen Stats, FTN charting, injuries, schedules, depth charts, trades |
| [nba_api](https://github.com/swar/nba_api) | NBA.com stats |
| Web search | News context and pre-1999 NFL numbers, with links saved |

## Cross-check (the checker agent uses these as the second source for basic stats)

| Source | Used for |
| --- | --- |
| [ESPN](https://www.espn.com) | Second source for basic stats |
| [NFL.com](https://www.nfl.com) | Official NFL stats and injury reports. Check by hand. |

## Rosters (topic check)

| Source | Used for |
| --- | --- |
| [ESPN](https://www.espn.com) | Current team rosters |
| Each team's official website | Official current rosters, to cross-check ESPN. Their terms on scraping and AI use must be checked before the app connects to them; until then, check by hand. |

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
