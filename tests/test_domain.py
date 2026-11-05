import operator
from collections.abc import MutableMapping
from datetime import UTC, datetime, timedelta, timezone
from typing import cast

import pytest
from pydantic import ValidationError

from leverage.domain import (
    DK_CLASSIC,
    Game,
    Lineup,
    LineupSlot,
    Player,
    Portfolio,
    Projection,
    RosterFormat,
    Slate,
    Slot,
)


def test_dk_classic_slots_and_eligibility() -> None:
    assert [slot.name for slot in DK_CLASSIC.slots] == [
        "QB",
        "RB1",
        "RB2",
        "WR1",
        "WR2",
        "WR3",
        "TE",
        "FLEX",
        "DST",
    ]
    assert DK_CLASSIC.salary_cap == 50_000
    flex = DK_CLASSIC.slots[7]
    assert all(flex.accepts(position) for position in ("RB", "WR", "TE"))
    assert all(not flex.accepts(position) for position in ("QB", "DST"))


def test_roster_format_rejects_empty_slots() -> None:
    with pytest.raises(ValidationError):
        RosterFormat(name="empty", slots=(), salary_cap=50_000)
    with pytest.raises(ValidationError):
        Slot(name="FLEX", eligible_positions=frozenset())


def test_roster_format_rejects_duplicate_slot_names() -> None:
    with pytest.raises(ValidationError):
        RosterFormat(
            name="duplicate",
            slots=(DK_CLASSIC.slots[0], DK_CLASSIC.slots[0]),
            salary_cap=50_000,
        )


def test_game_normalizes_aware_kickoff_to_utc_and_rejects_naive() -> None:
    game = Game(
        id="BUF@MIA",
        away_team="BUF",
        home_team="MIA",
        kickoff=datetime(2026, 9, 13, 13, tzinfo=timezone(timedelta(hours=-4))),
    )
    assert game.kickoff == datetime(2026, 9, 13, 17, tzinfo=UTC)
    assert game.kickoff.tzinfo == UTC
    with pytest.raises(ValidationError):
        Game(id="BUF@MIA", away_team="BUF", home_team="MIA", kickoff=datetime(2026, 9, 13))


def test_slate_requires_a_game_and_positive_week() -> None:
    with pytest.raises(ValidationError):
        Slate(id="main", site="DraftKings", roster_format=DK_CLASSIC, week=0, games=(), players={})


def test_slate_keeps_players_keyed_by_dk_id_without_mutable_source_data() -> None:
    game = Game(
        id="BUF@MIA", away_team="BUF", home_team="MIA", kickoff=datetime(2026, 9, 13, tzinfo=UTC)
    )
    player = Player(
        dk_id="44556892",
        name="Quarterback",
        positions=frozenset({"QB"}),
        team="BUF",
        opponent="MIA",
        game_id=game.id,
        salary=7000,
    )
    source = {player.dk_id: player}
    slate = Slate(
        id="main",
        site="DraftKings",
        roster_format=DK_CLASSIC,
        week=1,
        games=(game,),
        players=source,
    )

    assert slate.players["44556892"] == player
    source.clear()
    assert slate.players["44556892"] == player
    assert slate.model_dump()["players"]["44556892"]["dk_id"] == "44556892"
    with pytest.raises(TypeError):
        operator.setitem(cast(MutableMapping[str, Player], slate.players), "44556892", player)


def test_slate_rejects_player_key_that_disagrees_with_dk_id() -> None:
    game = Game(
        id="BUF@MIA", away_team="BUF", home_team="MIA", kickoff=datetime(2026, 9, 13, tzinfo=UTC)
    )
    player = Player(
        dk_id="44556892",
        name="Quarterback",
        positions=frozenset({"QB"}),
        team="BUF",
        opponent="MIA",
        game_id=game.id,
        salary=7000,
    )
    with pytest.raises(ValidationError):
        Slate(
            id="main",
            site="DraftKings",
            roster_format=DK_CLASSIC,
            week=1,
            games=(game,),
            players={"wrong-id": player},
        )


def test_player_uses_dk_id_and_rejects_empty_positions() -> None:
    player = Player(
        dk_id="44556892",
        name="Quarterback",
        positions=frozenset({"QB"}),
        team="BUF",
        opponent="MIA",
        game_id="BUF@MIA",
        salary=7000,
    )
    assert player.dk_id == "44556892"
    with pytest.raises(ValidationError):
        Player(
            dk_id="44556892",
            name="Quarterback",
            positions=frozenset(),
            team="BUF",
            opponent="MIA",
            game_id="BUF@MIA",
            salary=7000,
        )


def test_player_keeps_salary_file_injury_status() -> None:
    player = Player(
        dk_id="44556892",
        name="Quarterback",
        positions=frozenset({"QB"}),
        team="BUF",
        opponent="MIA",
        game_id="BUF@MIA",
        salary=7000,
        injury_status="Q",
    )
    assert player.injury_status == "Q"


def test_projection_rejects_negative_points() -> None:
    with pytest.raises(ValidationError):
        Projection(
            player_id="44556892",
            source="synthetic",
            proj=-1,
            floor=0,
            ceiling=20,
            imported_at=datetime.now(UTC),
        )


def test_projection_rejects_invalid_ownership() -> None:
    with pytest.raises(ValidationError):
        Projection(
            player_id="44556892",
            source="synthetic",
            proj=10,
            floor=5,
            ceiling=20,
            imported_at=datetime.now(UTC),
            ownership_by_field_size=((100, 101.0),),
        )


def test_all_domain_records_construct_with_valid_data() -> None:
    game = Game(
        id="BUF@MIA",
        away_team="BUF",
        home_team="MIA",
        kickoff=datetime(2026, 9, 13, 17, tzinfo=UTC),
    )
    slate = Slate(
        id="main",
        site="DraftKings",
        roster_format=DK_CLASSIC,
        week=1,
        games=(game,),
        players={},
        source_files=("salary.csv",),
    )
    player = Player(
        dk_id="44556892",
        name="Quarterback",
        positions=frozenset({"QB"}),
        team="BUF",
        opponent="MIA",
        game_id=game.id,
        salary=7000,
    )
    projection = Projection(
        player_id=player.dk_id,
        source="synthetic",
        proj=20,
        floor=10,
        ceiling=30,
        imported_at=datetime.now(UTC),
        ownership_by_field_size=((100, 12.5),),
    )
    lineup = Lineup(
        build_id="build-1",
        slots=(LineupSlot(slot="QB", player_id=player.dk_id),),
        salary=7000,
        proj=20,
        ceiling=30,
        ownership=12.5,
    )
    portfolio = Portfolio(name="Cash", contest_type="cash", lineups=(lineup,), target_size=1)

    assert slate.games[0].id == "BUF@MIA"
    assert projection.ownership_by_field_size == ((100, 12.5),)
    assert portfolio.lineups[0].slots[0].player_id == player.dk_id


def test_lineup_rejects_duplicate_players() -> None:
    with pytest.raises(ValidationError):
        Lineup(
            build_id="build-1",
            slots=(
                LineupSlot(slot="QB", player_id="1"),
                LineupSlot(slot="FLEX", player_id="1"),
            ),
            salary=10_000,
            proj=20,
            ceiling=30,
            ownership=10,
        )


def test_lineup_rejects_duplicate_slot_names() -> None:
    with pytest.raises(ValidationError):
        Lineup(
            build_id="build-1",
            slots=(
                LineupSlot(slot="QB", player_id="1"),
                LineupSlot(slot="QB", player_id="2"),
            ),
            salary=10_000,
            proj=20,
            ceiling=30,
            ownership=10,
        )


def test_portfolio_rejects_zero_target_size() -> None:
    with pytest.raises(ValidationError):
        Portfolio(name="GPP", contest_type="gpp", lineups=(), target_size=0)


def test_domain_records_are_frozen() -> None:
    with pytest.raises(ValidationError):
        DK_CLASSIC.__setattr__("salary_cap", 0)
