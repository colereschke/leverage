"""Read a DraftKings NFL Classic salary file into a Slate."""

import csv
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from leverage.domain import DK_CLASSIC, Game, Player, Position, Slate

COLUMNS = (
    "Position",
    "Name",
    "ID",
    "Roster Position",
    "Salary",
    "Game Info",
    "TeamAbbrev",
    "Status",
)
# Anything else, such as Showdown's CPT, is not a Classic file and must not import.
ROSTER_POSITIONS: dict[str, Position] = {
    "QB": "QB",
    "RB/FLEX": "RB",
    "WR/FLEX": "WR",
    "TE/FLEX": "TE",
    "DST": "DST",
}
GAME_INFO = re.compile(r"(\w+)@(\w+) (\d{2}/\d{2}/\d{4} \d{2}:\d{2}[AP]M) ET")
EASTERN = ZoneInfo("America/New_York")


class SalaryFileError(ValueError):
    def __init__(self, row: int, reason: str) -> None:
        super().__init__(f"row {row}: {reason}")
        self.row = row
        self.reason = reason


def parse_game(game_info: str) -> Game:
    match = GAME_INFO.fullmatch(game_info)
    if match is None:
        raise ValueError(f"invalid Game Info {game_info!r}")
    away, home, kickoff = match.groups()
    try:
        local_kickoff = datetime.strptime(kickoff, "%m/%d/%Y %I:%M%p")
    except ValueError as exc:
        raise ValueError(f"invalid Game Info {game_info!r}") from exc
    return Game(
        id=f"{away}@{home}",
        away_team=away,
        home_team=home,
        kickoff=local_kickoff.replace(tzinfo=EASTERN),
    )


def parse_player(row: dict[str, str], game: Game) -> Player:
    position = row["Position"].strip().replace("D/ST", "DST")
    roster_position = row["Roster Position"].strip().replace("D/ST", "DST")
    normalized = ROSTER_POSITIONS.get(roster_position)
    if normalized != position or normalized is None:
        raise ValueError(f"invalid Position {position!r} / Roster Position {roster_position!r}")

    salary = row["Salary"].strip()
    if not salary.isdecimal() or int(salary) == 0:
        raise ValueError(f"invalid Salary {salary!r}")

    team = row["TeamAbbrev"].strip()
    if team not in (game.away_team, game.home_team):
        raise ValueError(f"TeamAbbrev {team!r} is not in game {game.id}")

    return Player(
        dk_id=row["ID"].strip(),
        name=row["Name"].strip(),
        positions=frozenset({normalized}),
        team=team,
        opponent=game.home_team if team == game.away_team else game.away_team,
        game_id=game.id,
        salary=int(salary),
        injury_status=row["Status"].strip(),
    )


def read_dk_salaries(path: Path, slate_id: str, week: int) -> Slate:
    """Import every row or raise SalaryFileError; row numbers are file lines, header = 1."""
    games: dict[str, Game] = {}
    players: dict[str, Player] = {}
    # utf-8-sig because DK files start with a BOM, which would corrupt the first column name.
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = [column for column in COLUMNS if column not in (reader.fieldnames or ())]
        if missing:
            raise SalaryFileError(1, f"missing columns: {', '.join(missing)}")

        for row in reader:
            try:
                if None in row or None in row.values():
                    raise ValueError(f"expected {len(reader.fieldnames or ())} columns")
                game = parse_game(row["Game Info"].strip())
                if games.setdefault(game.id, game) != game:
                    raise ValueError(f"conflicting kickoff for {game.id}")
                player = parse_player(row, game)
                if player.dk_id in players:
                    raise ValueError(f"duplicate ID {player.dk_id}")
                players[player.dk_id] = player
            except ValueError as exc:
                raise SalaryFileError(reader.line_num, str(exc)) from exc

    return Slate(
        id=slate_id,
        site="DraftKings",
        roster_format=DK_CLASSIC,
        week=week,
        games=tuple(games.values()),
        players=players,
        source_files=(path.name,),
    )
