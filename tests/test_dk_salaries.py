from datetime import UTC, datetime
from pathlib import Path

import pytest

from leverage.domain import DK_CLASSIC, Slate
from leverage.io.dk_salaries import SalaryFileError, read_dk_salaries

REFERENCE = Path(__file__).parents[1] / "fixtures/2026-w08-main/DKSalaries.csv"
HEADER = (
    "Position,Name + ID,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev,AvgPointsPerGame,Status"
)
GOOD_ROW = "QB,A (1),A,1,QB,5000,AAA@BBB 11/01/2026 01:00PM ET,AAA,10,"


def write_salaries(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "DKSalaries.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def import_file(path: Path) -> Slate:
    return read_dk_salaries(path, slate_id="test", week=8)


@pytest.fixture(scope="module")
def reference() -> Slate:
    return read_dk_salaries(REFERENCE, slate_id="2026-w08-main", week=8)


def test_reference_file_imports_every_row(reference: Slate) -> None:
    assert len(reference.players) == 562
    assert len(reference.games) == 11
    assert sum(player.positions == {"DST"} for player in reference.players.values()) == 22
    assert reference.roster_format == DK_CLASSIC
    assert reference.source_files == ("DKSalaries.csv",)


@pytest.mark.parametrize(
    ("dk_id", "name", "position", "team", "opponent", "game_id", "salary", "status"),
    [
        ("44664465", "Jahmyr Gibbs", "RB", "DET", "MIN", "MIN@DET", 9500, ""),
        ("44664755", "Jaylen Waddle", "WR", "DEN", "KC", "KC@DEN", 5400, "Q"),
        ("44664493", "Breece Hall", "RB", "NYJ", "LV", "LV@NYJ", 6000, "OUT"),
        ("44664511", "RJ Harvey", "RB", "DEN", "KC", "KC@DEN", 5200, "IR"),
        ("44665379", "Bengals", "DST", "CIN", "TEN", "TEN@CIN", 3800, ""),
    ],
)
def test_reference_players(
    reference: Slate,
    dk_id: str,
    name: str,
    position: str,
    team: str,
    opponent: str,
    game_id: str,
    salary: int,
    status: str,
) -> None:
    player = reference.players[dk_id]
    assert player.name == name
    assert player.positions == {position}
    assert (player.team, player.opponent, player.game_id) == (team, opponent, game_id)
    assert player.salary == salary
    assert player.injury_status == status


@pytest.mark.parametrize(
    ("game_id", "hour", "minute"),
    [("MIN@DET", 18, 0), ("LAC@LAR", 21, 5), ("KC@DEN", 21, 25)],
)
def test_reference_kickoffs_are_utc_after_dst_ends(
    reference: Slate, game_id: str, hour: int, minute: int
) -> None:
    games = {game.id: game for game in reference.games}
    assert games[game_id].kickoff == datetime(2026, 11, 1, hour, minute, tzinfo=UTC)


def test_kickoff_during_daylight_time_is_four_hours_behind_utc(tmp_path: Path) -> None:
    row = GOOD_ROW.replace("11/01/2026", "10/25/2026")
    slate = import_file(write_salaries(tmp_path, HEADER, row))
    assert slate.games[0].kickoff == datetime(2026, 10, 25, 17, 0, tzinfo=UTC)


def test_dst_spelling_and_padding_are_normalized(tmp_path: Path) -> None:
    row = "D/ST,Bears  (9),Bears ,9,D/ST,2500,AAA@BBB 11/01/2026 01:00PM ET,BBB,5,"
    player = import_file(write_salaries(tmp_path, HEADER, row)).players["9"]
    assert player.positions == {"DST"}
    assert player.name == "Bears"


@pytest.mark.parametrize(
    ("bad_row", "reason"),
    [
        ("QB,B (2),B,2,QB,lots,AAA@BBB 11/01/2026 01:00PM ET,BBB,10,", "Salary"),
        ("QB,B (2),B,2,QB,0,AAA@BBB 11/01/2026 01:00PM ET,BBB,10,", "Salary"),
        ("K,B (2),B,2,K,5000,AAA@BBB 11/01/2026 01:00PM ET,BBB,10,", "Position"),
        ("QB,B (2),B,2,CPT,5000,AAA@BBB 11/01/2026 01:00PM ET,BBB,10,", "Position"),
        ("QB,B (2),B,2,QB,5000,Postponed,BBB,10,", "Game Info"),
        ("QB,B (2),B,2,QB,5000,AAA@BBB 13/45/2026 01:00PM ET,BBB,10,", "Game Info"),
        ("QB,B (2),B,2,QB,5000,AAA@BBB 11/01/2026 01:00PM ET,CCC,10,", "TeamAbbrev"),
        ("QB,B (2),B,2,QB,5000,AAA@BBB 11/01/2026 04:25PM ET,BBB,10,", "kickoff"),
        ("QB,A (1),A,1,QB,5000,AAA@BBB 11/01/2026 01:00PM ET,AAA,10,", "duplicate"),
        ("QB,B (2),,2,QB,5000,AAA@BBB 11/01/2026 01:00PM ET,BBB,10,", "name"),
        ("QB,B (2),B,2,QB", "columns"),
        ("QB,B (2),B,2,QB,5000,AAA@BBB 11/01/2026 01:00PM ET,BBB,10,,extra", "columns"),
    ],
)
def test_malformed_row_fails_with_row_number_and_reason(
    tmp_path: Path, bad_row: str, reason: str
) -> None:
    with pytest.raises(SalaryFileError, match=reason) as caught:
        import_file(write_salaries(tmp_path, HEADER, GOOD_ROW, bad_row))
    assert caught.value.row == 3
    assert str(caught.value).startswith("row 3: ")


def test_missing_column_fails_on_the_header_row(tmp_path: Path) -> None:
    header = HEADER.replace("TeamAbbrev", "Team")
    with pytest.raises(SalaryFileError, match="TeamAbbrev") as caught:
        import_file(write_salaries(tmp_path, header, GOOD_ROW))
    assert caught.value.row == 1


def test_duplicate_column_fails_on_the_header_row(tmp_path: Path) -> None:
    path = write_salaries(tmp_path, f"{HEADER},Salary", f"{GOOD_ROW},9000")
    with pytest.raises(SalaryFileError, match="duplicate columns: Salary") as caught:
        import_file(path)
    assert caught.value.row == 1


def test_header_only_file_fails_on_the_header_row(tmp_path: Path) -> None:
    with pytest.raises(SalaryFileError, match="empty file") as caught:
        import_file(write_salaries(tmp_path, HEADER))
    assert caught.value.row == 1
