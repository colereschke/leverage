"""FEAT-007: the exact reference agrees with brute force and finds a valid lineup on real slates."""

import random
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

import pytest
from reference import best_lineup, position

from leverage.domain import DK_CLASSIC, Game, Lineup, LineupSlot, Player, Slate
from leverage.io.dk_salaries import read_dk_salaries
from leverage.io.projections import ETR_COLUMNS, import_projections
from leverage.validate import validate_lineup

ROOT = Path(__file__).resolve().parents[1]
SALARIES = ROOT / "fixtures/2026-w08-main/DKSalaries.csv"
SYNTHETIC = ROOT / "fixtures/2026-w08-main/projections.csv"
ETR = ROOT / "data/2026-w08-main/etr.csv"
NOW = datetime(2026, 11, 1, 12, tzinfo=UTC)
GAMES = (("A", "B"), ("C", "D"))
# 20 players: team A can field a full lineup on its own, so one-game lineups are possible.
ROSTERS = {
    "A": ("QB", "RB", "RB", "RB", "WR", "WR", "WR", "TE", "TE", "DST"),
    "B": ("QB", "RB", "WR", "WR", "TE", "DST"),
    "C": ("RB", "WR", "DST"),
    "D": ("QB",),
}


def pool(seed: int, boost: dict[str, float]) -> tuple[Slate, dict[str, float]]:
    """A seeded pool; `boost` adds projection to one team's players ("A") or a DST ("B DST")."""
    rng = random.Random(seed)
    games = tuple(
        Game(id=f"{away}@{home}", away_team=away, home_team=home, kickoff=NOW)
        for away, home in GAMES
    )
    opponent = {away: home for away, home in GAMES} | {home: away for away, home in GAMES}
    players: dict[str, Player] = {}
    proj: dict[str, float] = {}
    for team, positions in ROSTERS.items():
        game = next(g.id for g in games if team in (g.away_team, g.home_team))
        for n, pos in enumerate(positions):
            dk_id = f"{team}{n}"
            players[dk_id] = Player(
                dk_id=dk_id,
                name=f"{team} {pos} {n}",
                positions=frozenset({pos}),  # type: ignore[arg-type]
                team=team,
                opponent=opponent[team],
                game_id=game,
                salary=rng.randrange(3000, 8100, 100),
            )
            proj[dk_id] = round(rng.uniform(2, 25), 2) + boost.get(team, 0)
            proj[dk_id] += boost.get(f"{team} {pos}", 0)
    slate = Slate(
        id=f"pool-{seed}", site="DK", roster_format=DK_CLASSIC, week=1, games=games, players=players
    )
    return slate, proj


def legal(players: tuple[Player, ...], checked: bool) -> bool:
    """Plain DK Classic legality; `checked` adds the 2-games and DST rules."""
    counts = {pos: 0 for pos in ("QB", "RB", "WR", "TE", "DST")}
    for player in players:
        counts[position(player)] += 1
    if not (
        counts["QB"] == 1
        and counts["DST"] == 1
        and counts["RB"] >= 2
        and counts["WR"] >= 3
        and counts["TE"] >= 1
        and sum(p.salary for p in players) <= DK_CLASSIC.salary_cap
    ):
        return False
    dst = next(p for p in players if position(p) == "DST")
    return not checked or (
        len({p.game_id for p in players}) >= 2
        and all(p.team != dst.opponent for p in players if p is not dst)
    )


def brute_force(slate: Slate, proj: dict[str, float], checked: bool = True) -> float:
    return max(
        sum(proj[p.dk_id] for p in lineup)
        for lineup in combinations(slate.players.values(), 9)
        if legal(lineup, checked)
    )


def as_lineup(slate: Slate, ids: tuple[str, ...]) -> Lineup:
    left = [slate.players[dk_id] for dk_id in ids]
    slots = []
    for slot in DK_CLASSIC.slots:  # FLEX comes after RB/WR/TE, so it gets the leftover player
        player = next(p for p in left if p.positions & slot.eligible_positions)
        left.remove(player)
        slots.append(LineupSlot(slot=slot.name, player_id=player.dk_id))
    return Lineup.model_construct(build_id="reference", slots=tuple(slots))


@pytest.mark.parametrize("seed", range(5))
def test_feat_007_matches_brute_force_on_random_pools(seed: int) -> None:
    slate, proj = pool(seed, {})
    score, ids = best_lineup(slate, proj)
    assert score == pytest.approx(brute_force(slate, proj))
    assert validate_lineup(as_lineup(slate, ids), slate) == []


@pytest.mark.parametrize("seed", range(3))
def test_feat_007_falls_back_when_best_lineup_is_one_game(seed: int) -> None:
    slate, proj = pool(seed, {"A": 30})
    unchecked = max(
        (lineup for lineup in combinations(slate.players.values(), 9) if legal(lineup, False)),
        key=lambda lineup: sum(proj[p.dk_id] for p in lineup),
    )
    assert len({p.game_id for p in unchecked}) == 1  # the pool really tests the 2-games rule

    score, ids = best_lineup(slate, proj)
    assert score == pytest.approx(brute_force(slate, proj))
    assert validate_lineup(as_lineup(slate, ids), slate) == []


@pytest.mark.parametrize("seed", range(3))
def test_feat_007_falls_back_when_best_dst_faces_the_offense(seed: int) -> None:
    slate, proj = pool(seed, {"A": 10, "B DST": 40})
    assert brute_force(slate, proj, checked=False) > brute_force(slate, proj)

    score, ids = best_lineup(slate, proj)
    assert score == pytest.approx(brute_force(slate, proj))
    assert validate_lineup(as_lineup(slate, ids), slate) == []


def reference_slate(path: Path) -> None:
    slate = read_dk_salaries(SALARIES, slate_id="2026-w08-main", week=8)
    projections = import_projections(path, slate, ETR_COLUMNS, imported_at=NOW).projections
    proj = {p.player_id: p.proj for p in projections}

    score, ids = best_lineup(slate, proj)

    assert score == pytest.approx(sum(proj[dk_id] for dk_id in ids))
    assert validate_lineup(as_lineup(slate, ids), slate) == []


def test_feat_007_synthetic_fixture_lineup_is_valid() -> None:
    reference_slate(SYNTHETIC)


@pytest.mark.skipif(not ETR.exists(), reason="real ETR data is local only")
def test_feat_007_real_etr_lineup_is_valid() -> None:
    reference_slate(ETR)
