"""Exact max-projection reference for DK Classic: a dynamic program, no solver, no model code.

Offense is a 0/1 knapsack over salary in $100 steps, run position by position (QB, RB, WR, TE)
with two extra bits of state: whether FLEX is used and whether any player is off the DST's team.
Fixing the DST and dropping its opponent's offense enforces the DST rule; once that holds, a
one-game lineup means all nine players are on the DST's team, so the second bit enforces 2 games.
That exact pass runs per DST, in order of an upper bound from one pass with neither rule, and
stops once no remaining DST can beat the best lineup found.
"""

from collections.abc import Mapping
from math import inf

from leverage.domain import Player, Slate

STEP = 100
# (position, required count, can fill FLEX); DK Classic has one FLEX for RB, WR or TE.
GROUPS = (("QB", 1, False), ("RB", 2, True), ("WR", 3, True), ("TE", 1, True))

Cell = tuple[float, tuple[str, ...]]  # (projection, chosen DK IDs)
Table = dict[tuple[int, bool], list[Cell]]  # (FLEX used, off DST team) -> best by budget
EMPTY: Cell = (-inf, ())


def position(player: Player) -> str:
    assert len(player.positions) == 1, f"{player.name} has several positions"
    return next(iter(player.positions))


def offense(
    players: list[Player],
    proj: Mapping[str, float],
    budget: int,
    own_team: str,
) -> Table:
    """Best 8-player offense for every budget up to `budget` units, keyed by the two state bits."""
    state: Table = {(0, False): [(0.0, ())] * (budget + 1)}
    for pos, need, flexible in GROUPS:
        rows: list[Table] = [state] + [{} for _ in range(need + flexible)]
        for player in (p for p in players if position(p) == pos):
            cost, points, dk_id = player.salary // STEP, proj[player.dk_id], player.dk_id
            # Descending k so each player is added at most once (rows[k - 1] is still pre-player).
            for k in range(len(rows) - 1, 0, -1):
                for (flex, off), before in rows[k - 1].items():
                    row = rows[k].setdefault(
                        (flex, off or player.team != own_team), [EMPTY] * (budget + 1)
                    )
                    row[cost:] = [
                        a if a[0] >= b[0] + points else (b[0] + points, (*b[1], dk_id))
                        for a, b in zip(row[cost:], before, strict=False)
                    ]
        state = {}
        for k in range(need, len(rows)):
            for (flex, off), row in rows[k].items():
                if flex + k - need <= 1:
                    key = (flex + k - need, off)
                    old = state.get(key, [EMPTY] * (budget + 1))
                    state[key] = [
                        max(a, b, key=lambda c: c[0]) for a, b in zip(old, row, strict=True)
                    ]
    return state


def best_lineup(slate: Slate, proj: Mapping[str, float]) -> Cell:
    """The max-projection legal lineup among players with a projection: (score, DK IDs)."""
    assert slate.roster_format.salary_cap % STEP == 0
    pool = [p for p in slate.players.values() if p.dk_id in proj]
    assert all(p.salary % STEP == 0 for p in pool), "salaries must be in $100 steps"
    cap = slate.roster_format.salary_cap // STEP
    dsts = [p for p in pool if position(p) == "DST"]
    skill = [p for p in pool if position(p) != "DST"]

    bound = offense(skill, proj, cap, "").get((1, True), [EMPTY] * (cap + 1))
    best: Cell = EMPTY
    for score, dst in sorted(
        (
            (proj[d.dk_id] + bound[cap - d.salary // STEP][0], d)
            for d in dsts
            if d.salary <= cap * STEP
        ),
        key=lambda pair: -pair[0],
    ):
        if score <= best[0]:
            break
        allowed = [p for p in skill if p.team != dst.opponent]
        budget = cap - dst.salary // STEP
        table = offense(allowed, proj, budget, dst.team)
        points, ids = table.get((1, True), [EMPTY])[-1]
        if points + proj[dst.dk_id] > best[0]:
            best = (points + proj[dst.dk_id], (*ids, dst.dk_id))
    return best
