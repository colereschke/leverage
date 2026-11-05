"""The committed projection fixture is reproducible and usable as a full slate."""

import csv
import subprocess
import sys
from pathlib import Path

from leverage.io.dk_salaries import read_dk_salaries

ROOT = Path(__file__).resolve().parents[1]
SALARIES = ROOT / "fixtures/2026-w08-main/DKSalaries.csv"
PROJECTIONS = ROOT / "fixtures/2026-w08-main/projections.csv"
GENERATOR = ROOT / "scripts/generate_synthetic_projections.py"
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


def test_feat_005_same_seed_regenerates_committed_bytes(tmp_path: Path) -> None:
    output = tmp_path / "projections.csv"
    command = [sys.executable, str(GENERATOR), str(SALARIES), str(output), "--seed", "5"]
    subprocess.run(command, check=True)
    assert output.read_bytes() == PROJECTIONS.read_bytes()
    first = output.read_bytes()
    subprocess.run(command, check=True)
    assert output.read_bytes() == first


def test_feat_005_reference_values_cover_dk_players_and_are_plausible() -> None:
    slate = read_dk_salaries(SALARIES, "2026-w08-main", 8)
    with PROJECTIONS.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        assert tuple(reader.fieldnames or ()) == HEADERS
        rows = list(reader)

    assert len(rows) == len(slate.players) == 562
    assert {row["id"] for row in rows} == set(slate.players)
    for row in rows:
        player = slate.players[row["id"]]
        assert row["Player"] == player.name
        assert row["DK Pos"] in player.positions
        assert row["Team"] == player.team
        assert row["Opp"] == player.opponent
        assert int(row["DK Salary"]) == player.salary
        floor = float(row["DK Floor"])
        proj = float(row["DK Proj"])
        ceiling = float(row["DK Ceiling"])
        assert 0 <= floor <= proj <= ceiling
        assert float(row["DK Value"]) >= 0
        for column in ("Small Field", "Large Field"):
            assert 0 <= float(row[column].rstrip("%")) <= 100

    for column in ("Small Field", "Large Field"):
        assert 895 <= sum(float(row[column].rstrip("%")) for row in rows) <= 905

    expensive = [float(row["DK Proj"]) for row in rows if int(row["DK Salary"]) >= 7000]
    cheap = [float(row["DK Proj"]) for row in rows if int(row["DK Salary"]) <= 4000]
    assert expensive and cheap
    assert sum(expensive) / len(expensive) > sum(cheap) / len(cheap)
