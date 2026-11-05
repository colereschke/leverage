"""Generate the public Week 8 projection fixture from DK salaries alone."""

import argparse
import csv
from pathlib import Path
from random import Random

from leverage.domain import Position
from leverage.io.dk_salaries import read_dk_salaries

HEADERS = (
    "Player",
    "DK Pos",
    "Team",
    "Opp",
    "DK Salary",
    "DK Proj",
    "DK Value",
    "Small Field",
    "Large Field",
    "DK Floor",
    "DK Ceiling",
    "id",
)
POINTS_PER_THOUSAND: dict[Position, float] = {
    "QB": 3.2,
    "RB": 2.8,
    "WR": 2.7,
    "TE": 2.6,
    "DST": 2.0,
}
# One full roster's worth of ownership, with the FLEX split across RB and WR.
OWNERSHIP_SLOTS: dict[Position, float] = {
    "QB": 1.0,
    "RB": 2.5,
    "WR": 3.5,
    "TE": 1.0,
    "DST": 1.0,
}


def generate(salaries: Path, output: Path, seed: int) -> None:
    slate = read_dk_salaries(salaries, "2026-w08-main", 8)
    players = list(slate.players.values())
    random = Random(seed)
    weights = {
        player.dk_id: (
            player.salary**2 * random.uniform(0.7, 1.3),
            player.salary**3 * random.uniform(0.7, 1.3),
        )
        for player in players
    }
    totals = {
        position: tuple(
            sum(weights[player.dk_id][column] for player in players if position in player.positions)
            for column in range(2)
        )
        for position in OWNERSHIP_SLOTS
    }

    with output.open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target, lineterminator="\n")
        writer.writerow(HEADERS)
        for player in players:
            position = next(iter(player.positions))
            proj = round(
                player.salary / 1000 * POINTS_PER_THOUSAND[position] * random.uniform(0.85, 1.15),
                2,
            )
            floor = round(proj * random.uniform(0.55, 0.75), 2)
            ceiling = round(proj * random.uniform(1.25, 1.65), 2)
            ownership = tuple(
                f"{100 * OWNERSHIP_SLOTS[position] * weight / totals[position][column]:.2f}%"
                for column, weight in enumerate(weights[player.dk_id])
            )
            writer.writerow(
                (
                    player.name,
                    position,
                    player.team,
                    player.opponent,
                    player.salary,
                    f"{proj:.2f}",
                    f"{proj / player.salary * 1000:.2f}",
                    *ownership,
                    f"{floor:.2f}",
                    f"{ceiling:.2f}",
                    player.dk_id,
                )
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("salaries", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=5)
    args = parser.parse_args()
    generate(args.salaries, args.output, args.seed)
