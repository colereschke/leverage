import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from leverage.domain import DK_CLASSIC, Game, Player, Slate
from leverage.io.dk_salaries import read_dk_salaries
from leverage.io.projections import (
    ETR_COLUMNS,
    GENERIC_COLUMNS,
    AmbiguousMatchError,
    ColumnMap,
    ImportResult,
    ProjectionFileError,
    import_projections,
    normalize_name,
)

ROOT = Path(__file__).parents[1]
SALARIES = ROOT / "fixtures/2026-w08-main/DKSalaries.csv"
SYNTHETIC = ROOT / "fixtures/2026-w08-main/projections.csv"
ETR = ROOT / "data/2026-w08-main/etr.csv"
NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)
ETR_HEADER = (
    "Player,DK Pos,Team,Opp,DK Salary,DK Proj,DK Value,"
    "Small Field,Large Field,DK Floor,DK Ceiling,id"
)
GENERIC_HEADER = "name,position,team,salary,projection"


def player(
    dk_id: str,
    name: str,
    team: str = "AAA",
    position: str = "WR",
    salary: int = 5000,
    status: str = "",
) -> Player:
    return Player.model_validate(
        {
            "dk_id": dk_id,
            "name": name,
            "positions": {position},
            "team": team,
            "opponent": "BBB" if team == "AAA" else "AAA",
            "game_id": "AAA@BBB",
            "salary": salary,
            "injury_status": status,
        }
    )


def slate(*players: Player) -> Slate:
    game = Game(id="AAA@BBB", away_team="AAA", home_team="BBB", kickoff=NOW)
    return Slate(
        id="test",
        site="DraftKings",
        roster_format=DK_CLASSIC,
        week=8,
        games=(game,),
        players={entry.dk_id: entry for entry in players},
    )


def etr_row(
    name: str,
    dk_id: str = "",
    team: str = "AAA",
    position: str = "WR",
    salary: str = "$5,000",
    floor: str = "4.0",
) -> str:
    return f'{name},{position},{team},BBB,"{salary}",10.5,2.1,5.5%,6.5%,{floor},20.5,{dk_id}'


def run(
    tmp_path: Path,
    target: Slate,
    rows: Iterable[str],
    header: str = ETR_HEADER,
    columns: ColumnMap = ETR_COLUMNS,
    resolutions: dict[str, str | None] | None = None,
) -> ImportResult:
    path = tmp_path / "projections.csv"
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    mapping = None
    if resolutions is not None:
        mapping = tmp_path / "resolutions.json"
        mapping.write_text(json.dumps(resolutions), encoding="utf-8")
    return import_projections(path, target, columns, resolutions=mapping, imported_at=NOW)


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("Michael Penix Jr.", "michael penix"),
        ("Kenneth Walker III", "kenneth walker"),
        ("A.J. Brown", "aj brown"),
        ("Amon-Ra St. Brown", "amonra st brown"),
        ("Ja'Marr Chase", "jamarr chase"),
        ("Bears D/ST", "bears"),
        ("  Bears  ", "bears"),
        ("José Núñez", "jose nunez"),
    ],
)
def test_normalize_name(raw: str, normalized: str) -> None:
    assert normalize_name(raw) == normalized


def test_etr_row_imports_every_value(tmp_path: Path) -> None:
    result = run(tmp_path, slate(player("1", "Ann Lee")), [etr_row("Ann Lee", "1")])

    (projection,) = result.projections
    assert projection.player_id == "1"
    assert projection.source == "ETR"
    assert (projection.proj, projection.floor, projection.ceiling) == (10.5, 4.0, 20.5)
    assert projection.ownership_by_field_size == (("small", 5.5), ("large", 6.5))
    assert projection.imported_at == NOW


def test_negative_floor_is_kept(tmp_path: Path) -> None:
    target = slate(player("1", "Bears", position="DST"))
    rows = [etr_row("Bears", "1", position="DST", floor="-1.5")]

    assert run(tmp_path, target, rows).projections[0].floor == -1.5


def test_etr_la_team_code_is_dk_lar(tmp_path: Path) -> None:
    result = run(
        tmp_path, slate(player("1", "Ann Lee", team="LAR")), [etr_row("Ann Lee", "1", team="LA")]
    )

    assert len(result.projections) == 1
    assert result.report.mismatches == ()
    assert result.report.blocked == ()


def test_dst_position_spelling_is_not_a_mismatch(tmp_path: Path) -> None:
    target = slate(player("1", "Bears", position="DST"))

    result = run(tmp_path, target, [etr_row("Bears", "1", position="D/ST")])

    assert result.report.mismatches == ()


def test_generic_preset_matches_by_name_and_team(tmp_path: Path) -> None:
    target = slate(player("1", "Michael Penix Jr.", position="QB"))

    result = run(
        tmp_path,
        target,
        ["Michael Penix,QB,AAA,5000,18.5"],
        header=GENERIC_HEADER,
        columns=GENERIC_COLUMNS,
    )

    (projection,) = result.projections
    assert projection.player_id == "1"
    assert (projection.proj, projection.floor, projection.ceiling) == (18.5, 18.5, 18.5)
    assert projection.ownership_by_field_size == ()


def test_id_match_wins_over_name_and_team(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"), player("2", "Bo Ray"))

    result = run(tmp_path, target, [etr_row("Bo Ray", "1")])

    assert result.projections[0].player_id == "1"


def test_unknown_id_falls_back_to_name_and_team(tmp_path: Path) -> None:
    result = run(tmp_path, slate(player("1", "Ann Lee")), [etr_row("Ann Lee", "999")])

    assert result.projections[0].player_id == "1"


def test_row_fitting_several_dk_players_blocks_the_import(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"), player("2", "Ann Lee", position="RB"))

    with pytest.raises(AmbiguousMatchError) as error:
        run(tmp_path, target, [etr_row("Ann Lee")])

    assert [(row.row, row.name) for row in error.value.report.ambiguous] == [(2, "Ann Lee")]


def test_several_rows_fitting_one_dk_player_blocks_the_import(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee Jr."))

    with pytest.raises(AmbiguousMatchError) as error:
        run(tmp_path, target, [etr_row("Ann Lee"), etr_row("Ann Lee Jr.")])

    assert [row.row for row in error.value.report.ambiguous] == [2, 3]


def test_resolution_file_settles_a_row_fitting_several_players(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"), player("2", "Ann Lee", position="RB"))

    result = run(tmp_path, target, [etr_row("Ann Lee")], resolutions={"Ann Lee|AAA|WR|5000": "2"})

    assert [projection.player_id for projection in result.projections] == ["2"]


@pytest.mark.parametrize(
    ("first", "second", "resolutions"),
    [
        (
            etr_row("Ann Lee", position="WR"),
            etr_row("Ann Lee", position="RB"),
            {"Ann Lee|AAA|WR|5000": "1", "Ann Lee|AAA|RB|5000": "2"},
        ),
        (
            etr_row("Ann Lee", salary="$5,000"),
            etr_row("Ann Lee", salary="$6,000"),
            {"Ann Lee|AAA|WR|5000": "1", "Ann Lee|AAA|WR|6000": "2"},
        ),
    ],
)
def test_same_name_and_team_rows_resolve_to_different_players(
    tmp_path: Path, first: str, second: str, resolutions: dict[str, str | None]
) -> None:
    target = slate(player("1", "Ann Lee"), player("2", "Ann Lee", salary=6000))

    result = run(tmp_path, target, [first, second], resolutions=resolutions)

    assert {projection.player_id for projection in result.projections} == {"1", "2"}


def test_resolution_survives_a_reordered_file(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"), player("2", "Ann Lee", position="RB"))
    resolutions: dict[str, str | None] = {"Ann Lee|AAA|WR|5000": "1", "Ann Lee|AAA|RB|5000": "2"}
    rows = [etr_row("Ann Lee", position="RB", floor="1.0"), etr_row("Ann Lee", floor="2.0")]

    result = run(tmp_path, target, rows, resolutions=resolutions)

    floors = {projection.player_id: projection.floor for projection in result.projections}
    assert floors == {"1": 2.0, "2": 1.0}


def test_identical_rows_stay_blocked_despite_a_resolution(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"), player("2", "Ann Lee"))

    with pytest.raises(AmbiguousMatchError):
        run(
            tmp_path,
            target,
            [etr_row("Ann Lee"), etr_row("Ann Lee")],
            resolutions={"Ann Lee|AAA|WR|5000": "1"},
        )


def test_row_key_resolves_identical_rows_to_different_players(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"), player("2", "Ann Lee"))
    rows = [etr_row("Ann Lee", floor="1.0"), etr_row("Ann Lee", floor="2.0")]
    resolutions: dict[str, str | None] = {
        "Ann Lee|AAA|WR|5000|row 2": "1",
        "Ann Lee|AAA|WR|5000|row 3": "2",
    }

    result = run(tmp_path, target, rows, resolutions=resolutions)

    floors = {projection.player_id: projection.floor for projection in result.projections}
    assert floors == {"1": 1.0, "2": 2.0}


def test_row_key_ignores_one_of_two_identical_rows(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"))
    rows = [etr_row("Ann Lee", floor="1.0"), etr_row("Ann Lee", floor="2.0")]
    resolutions: dict[str, str | None] = {
        "Ann Lee|AAA|WR|5000|row 2": None,
        "Ann Lee|AAA|WR|5000|row 3": "1",
    }

    result = run(tmp_path, target, rows, resolutions=resolutions)

    assert [projection.floor for projection in result.projections] == [2.0]
    assert [row.row for row in result.report.ignored] == [2]


def test_row_key_takes_priority_over_the_stable_key(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"), player("2", "Ann Lee"))
    resolutions: dict[str, str | None] = {
        "Ann Lee|AAA|WR|5000": "1",
        "Ann Lee|AAA|WR|5000|row 3": "2",
    }

    result = run(
        tmp_path, target, [etr_row("Ann Lee"), etr_row("Ann Lee")], resolutions=resolutions
    )

    assert {projection.player_id for projection in result.projections} == {"1", "2"}


def test_shifted_rows_miss_their_row_keys_and_stay_blocked(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"), player("2", "Ann Lee"), player("3", "Bo Ray"))
    rows = [etr_row("Bo Ray", "3"), etr_row("Ann Lee"), etr_row("Ann Lee")]
    resolutions: dict[str, str | None] = {
        "Ann Lee|AAA|WR|5000|row 2": "1",
        "Ann Lee|AAA|WR|5000|row 3": "2",
    }

    with pytest.raises(AmbiguousMatchError) as error:
        run(tmp_path, target, rows, resolutions=resolutions)

    assert [row.row for row in error.value.report.ambiguous] == [4]


def test_row_key_marks_a_team_mismatch_reviewed(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"))

    result = run(
        tmp_path,
        target,
        [etr_row("Ann Lee", "1", team="BBB")],
        resolutions={"Ann Lee|BBB|WR|5000|row 2": "1"},
    )

    assert result.report.blocked == ()


def test_resolution_to_null_ignores_a_row_and_lists_it(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee Jr."))

    result = run(
        tmp_path,
        target,
        [etr_row("Ann Lee"), etr_row("Ann Lee Jr.")],
        resolutions={"Ann Lee|AAA|WR|5000": None},
    )

    assert [projection.player_id for projection in result.projections] == ["1"]
    assert [row.name for row in result.report.ignored] == ["Ann Lee"]


def test_resolution_naming_a_player_off_the_slate_fails(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"))

    with pytest.raises(ProjectionFileError, match="999"):
        run(tmp_path, target, [etr_row("Ann Lee")], resolutions={"Ann Lee|AAA|WR|5000": "999"})


def test_dk_player_without_projection_is_excluded_and_counted(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"), player("2", "Bo Ray", salary=6000))

    result = run(tmp_path, target, [etr_row("Ann Lee", "1")])

    assert [projection.player_id for projection in result.projections] == ["1"]
    assert result.report.unprojected_count == 1


def test_unprojected_names_only_healthy_players_above_position_minimum(tmp_path: Path) -> None:
    target = slate(
        player("1", "Projected", salary=9000),
        player("2", "Min Salary WR", salary=3000),
        player("3", "Above Min WR", salary=3100),
        player("4", "Injured WR", salary=7000, status="Q"),
        player("5", "Min Salary QB", position="QB", salary=4000),
        player("6", "Above Min QB", position="QB", salary=4100),
    )

    report = run(tmp_path, target, [etr_row("Projected", "1")]).report

    assert report.unprojected_count == 5
    assert report.unprojected_names == ("Above Min WR", "Above Min QB")


def test_row_matching_no_dk_player_is_listed_and_ignored(tmp_path: Path) -> None:
    result = run(
        tmp_path, slate(player("1", "Ann Lee")), [etr_row("Ann Lee", "1"), etr_row("Nobody")]
    )

    assert len(result.projections) == 1
    assert [(row.row, row.name) for row in result.report.unmatched] == [(3, "Nobody")]


def test_salary_mismatch_keeps_dk_and_is_listed(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee", salary=5000))

    result = run(tmp_path, target, [etr_row("Ann Lee", "1", salary="$5,500")])

    assert len(result.projections) == 1
    assert [(m.dk_id, m.attribute, m.dk_value, m.file_value) for m in result.report.mismatches] == [
        ("1", "salary", "5000", "5500")
    ]
    assert result.report.blocked == ()


def test_position_mismatch_keeps_dk_and_is_listed(tmp_path: Path) -> None:
    result = run(tmp_path, slate(player("1", "Ann Lee")), [etr_row("Ann Lee", "1", position="RB")])

    assert len(result.projections) == 1
    assert [(m.attribute, m.dk_value, m.file_value) for m in result.report.mismatches] == [
        ("position", "WR", "RB")
    ]


def test_team_mismatch_is_listed_and_blocks_the_player(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"), player("2", "Bo Ray"))
    rows = [etr_row("Ann Lee", "1", team="BBB"), etr_row("Bo Ray", "2")]

    result = run(tmp_path, target, rows)

    assert [projection.player_id for projection in result.projections] == ["2"]
    assert [(m.attribute, m.dk_value, m.file_value) for m in result.report.mismatches] == [
        ("team", "AAA", "BBB")
    ]
    assert result.report.blocked == ("1",)


def test_resolution_marks_a_team_mismatch_reviewed(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"))

    result = run(
        tmp_path,
        target,
        [etr_row("Ann Lee", "1", team="BBB")],
        resolutions={"Ann Lee|BBB|WR|5000": "1"},
    )

    assert [projection.player_id for projection in result.projections] == ["1"]
    assert result.report.blocked == ()
    assert [m.attribute for m in result.report.mismatches] == ["team"]


def test_every_row_is_accounted_for(tmp_path: Path) -> None:
    target = slate(player("1", "Ann Lee"), player("2", "Bo Ray"), player("3", "Cy Poe"))
    rows = [
        etr_row("Ann Lee", "1"),
        etr_row("Bo Ray", "2", team="BBB"),
        etr_row("Nobody"),
        etr_row("Skipped"),
    ]

    report = run(tmp_path, target, rows, resolutions={"Skipped|AAA|WR|5000": None}).report

    assert report.rows == 4
    assert (report.imported, len(report.blocked), len(report.unmatched), len(report.ignored)) == (
        1,
        1,
        1,
        1,
    )
    assert report.unprojected_count == 1


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (etr_row("Ann Lee", "1", salary="free"), "salary"),
        ('Ann Lee,WR,AAA,BBB,"$5,000",abc,2.1,5.5%,6.5%,4.0,20.5,1', "could not convert"),
        ('Ann Lee,WR,AAA,BBB,"$5,000",-1,2.1,5.5%,6.5%,4.0,20.5,1', "proj"),
        ('Ann Lee,WR,AAA,BBB,"$5,000",10,2.1,105%,6.5%,4.0,20.5,1', "ownership"),
        (',WR,AAA,BBB,"$5,000",10,2.1,5.5%,6.5%,4.0,20.5,1', "name"),
        ("Ann Lee,WR,AAA", "expected 12 columns"),
    ],
)
def test_bad_row_fails_with_its_row_number(tmp_path: Path, row: str, reason: str) -> None:
    with pytest.raises(ProjectionFileError, match=reason) as error:
        run(tmp_path, slate(player("1", "Ann Lee")), [row])

    assert error.value.row == 2


def test_missing_column_fails(tmp_path: Path) -> None:
    with pytest.raises(ProjectionFileError, match="DK Proj"):
        run(tmp_path, slate(player("1", "A")), [], header="Player,DK Pos,Team,DK Salary")


def test_duplicate_column_fails(tmp_path: Path) -> None:
    with pytest.raises(ProjectionFileError, match="duplicate columns"):
        run(tmp_path, slate(player("1", "A")), [], header=f"{ETR_HEADER},id")


def test_empty_file_fails(tmp_path: Path) -> None:
    with pytest.raises(ProjectionFileError, match="no projection rows"):
        run(tmp_path, slate(player("1", "A")), [])


@pytest.mark.skipif(not SYNTHETIC.exists(), reason="needs the FEAT-005 synthetic fixture")
def test_synthetic_reference_imports_with_an_empty_report() -> None:
    reference = read_dk_salaries(SALARIES, slate_id="2026-w08-main", week=8)

    result = import_projections(SYNTHETIC, reference, ETR_COLUMNS, imported_at=NOW)

    assert len(result.projections) == len(reference.players)
    assert result.report.is_clean


@pytest.mark.skipif(not ETR.exists(), reason="real ETR data is local only")
def test_real_etr_file_matches_every_row() -> None:
    reference = read_dk_salaries(SALARIES, slate_id="2026-w08-main", week=8)

    report = import_projections(ETR, reference, ETR_COLUMNS, imported_at=NOW).report

    assert report.imported == 306
    assert report.mismatches == ()
    assert report.blocked == ()
    assert report.unmatched == ()
    assert report.unprojected_count == 256
