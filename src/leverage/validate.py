"""Independent lineup validator: plain-code checks, no solver."""

from typing import Literal, get_args

from leverage.domain import DomainModel, Lineup, NonEmptyStr, Position, Slate

MIN_GAMES = 2  # a DraftKings rule, so it isn't in the RosterFormat

Check = Literal[
    "unknown_player",
    "slot_eligibility",
    "distinct_players",
    "salary_cap",
    "position_counts",
    "min_games",
    "dst_conflict",
]


class Violation(DomainModel):
    check: Check
    message: NonEmptyStr


def validate_lineup(lineup: Lineup, slate: Slate) -> list[Violation]:
    """Return every violation, trusting only the slate: not Lineup's totals or its own checks."""
    violations: list[Violation] = []

    def fail(check: Check, message: str) -> None:
        violations.append(Violation(check=check, message=message))

    slots = {slot.name: slot for slot in slate.roster_format.slots}
    ids = [entry.player_id for entry in lineup.slots]
    players = [slate.players[dk_id] for dk_id in ids if dk_id in slate.players]

    for dk_id in ids:
        if dk_id not in slate.players:
            fail("unknown_player", f"player {dk_id} is not on slate {slate.id}")

    for entry in lineup.slots:
        slot = slots.get(entry.slot)
        player = slate.players.get(entry.player_id)
        if slot is None:
            fail("slot_eligibility", f"slot {entry.slot} is not in {slate.roster_format.name}")
        elif player is not None and player.positions.isdisjoint(slot.eligible_positions):
            fail("slot_eligibility", f"{player.name} can't fill {entry.slot}")
    for name in sorted(slots.keys() - {entry.slot for entry in lineup.slots}):
        fail("slot_eligibility", f"slot {name} is empty")

    if len(ids) != len(slots) or len(set(ids)) != len(slots):
        fail(
            "distinct_players",
            f"expected {len(slots)} distinct players, got {len(set(ids))} in {len(ids)} slots",
        )

    salary = sum(player.salary for player in players)
    if salary > slate.roster_format.salary_cap:
        fail("salary_cap", f"salary {salary} is over {slate.roster_format.salary_cap}")

    # shortcut: a multi-position player counts at each position, upgrade if a format has any.
    for position in get_args(Position):
        accepting = [s for s in slots.values() if position in s.eligible_positions]
        low = sum(s.eligible_positions == {position} for s in accepting)
        count = sum(position in player.positions for player in players)
        if not low <= count <= len(accepting):
            fail("position_counts", f"{count} {position}, allowed {low} to {len(accepting)}")

    games = {player.game_id for player in players}
    if len(games) < MIN_GAMES:
        fail("min_games", f"players from {len(games)} game(s), need {MIN_GAMES}")

    for dst in (player for player in players if "DST" in player.positions):
        for player in players:
            if "DST" not in player.positions and player.team == dst.opponent:
                fail("dst_conflict", f"{player.name} faces {dst.name}")

    return violations
