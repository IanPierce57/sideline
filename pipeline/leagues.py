"""One place for what differs between the NFL and the NBA (added Nov 5, 2026), so the
topic check, the script generator, and the tests don't each carry their own copy.

Both schedule modules (games.py for the NFL, nba.py for the NBA) offer the same
functions: team_code, find_game, next_game, upcoming_games, and TEAMS."""

from . import games, nba


def schedule(league: str):
    """The schedule module for a league."""
    return nba if league == "NBA" else games


def game_pack(game: dict) -> list[dict]:
    """Every fact the show needs for one game, unchecked (verify.py checks each one)."""
    if game.get("league") == "NBA":
        return nba.game_pack(game)
    from . import catalog
    return catalog.game_pack(game)


def game_note(game: dict) -> str:
    """One paragraph telling research and the writer which game this is and what's pulled."""
    teams = schedule(game.get("league", "NFL")).TEAMS
    matchup = f"{teams[game['away']][0]} at {teams[game['home']][0]}"
    if game.get("league") == "NBA":
        when = f"{game['weekday']} {game['date']}"
        pulled = ("Records, home and road, scoring, last five, streaks, standings, rest, injuries, "
                  "last starting fives, and head coaches are already pulled.")
    else:
        when = f"{game['weekday']} {game['date']} (Week {game['week']})"
        pulled = "Team stats, records, recent results, last game's starting QBs, and injured starters are already pulled."
    return f"This segment previews one game: {matchup}, {when}. {pulled}"
