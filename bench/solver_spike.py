"""FEAT-001: rough joint-portfolio solver benchmark on private Week 8 data.

Run: uv run --group bench python bench/solver_spike.py
Each case runs in a fresh process because highspy and OR-Tools clash when imported together.
"""

import argparse
import csv
import json
import math
import subprocess
import sys
import time
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SALARIES = ROOT / "fixtures/2026-w08-main/DKSalaries.csv"
PROJECTIONS = ROOT / "data/2026-w08-main/etr.csv"
LIMITS = {6: 30, 20: 180}
POOL = {"QB": 12, "RB": 40, "WR": 70, "TE": 30, "DST": 16}


def players() -> list[dict[str, str | int]]:
    with SALARIES.open(encoding="utf-8-sig", newline="") as source:
        salaries = {row["ID"]: row for row in csv.DictReader(source)}
    with PROJECTIONS.open(encoding="utf-8-sig", newline="") as source:
        projections = {row["id"]: row for row in csv.DictReader(source)}
    if len(salaries) < 500 or len(projections) < 250:
        raise ValueError("Expected the full Week 8 reference files")
    pool: list[dict[str, str | int]] = []
    for position, size in POOL.items():
        matches = []
        for player_id, salary in salaries.items():
            projection = projections.get(player_id)
            if salary["Position"] != position or projection is None:
                continue
            points = round(float(projection["DK Proj"]) * 100)
            if points <= 0:
                continue
            matches.append(
                {
                    "id": player_id,
                    "position": position,
                    "team": salary["TeamAbbrev"],
                    "opponent": projection["Opp"],
                    "game": salary["Game Info"].split(" ")[0],
                    "salary": int(salary["Salary"]),
                    "points": points,
                }
            )
        pool.extend(sorted(matches, key=lambda p: int(p["points"]), reverse=True)[:size])
    if any(sum(p["position"] == position for p in pool) < size for position, size in POOL.items()):
        raise ValueError("Reference projection file does not fill the benchmark pool")
    return pool


def rows(
    pool: list[dict[str, str | int]], lineups: int
) -> list[tuple[int, int, list[int], list[int]]]:
    count = len(pool)
    result: list[tuple[int, int, list[int], list[int]]] = []

    def add(lineup: int, selected: list[int], low: int, high: int) -> None:
        result.append((low, high, [lineup * count + p for p in selected], [1] * len(selected)))

    positions = {pos: [i for i, p in enumerate(pool) if p["position"] == pos] for pos in POOL}
    games = {str(p["game"]) for p in pool}
    teams = {str(p["team"]) for p in pool}
    for lineup in range(lineups):
        add(lineup, list(range(count)), 9, 9)
        result.append(
            (0, 50000, [lineup * count + p for p in range(count)], [int(p["salary"]) for p in pool])
        )
        for position, low, high in (
            ("QB", 1, 1),
            ("RB", 2, 3),
            ("WR", 3, 4),
            ("TE", 1, 2),
            ("DST", 1, 1),
        ):
            add(lineup, positions[position], low, high)
        for game in games:
            add(lineup, [i for i, p in enumerate(pool) if p["game"] == game], 0, 8)
        for team in teams:
            add(
                lineup,
                [i for i, p in enumerate(pool) if p["team"] == team and p["position"] != "DST"],
                0,
                4,
            )
        for qb in positions["QB"]:
            team = str(pool[qb]["team"])
            opponent = str(pool[qb]["opponent"])
            pass_catchers = [
                i for i, p in enumerate(pool) if p["team"] == team and p["position"] in ("WR", "TE")
            ]
            bring_backs = [
                i
                for i, p in enumerate(pool)
                if p["team"] == opponent and p["position"] in ("RB", "WR", "TE")
            ]
            for group in (pass_catchers, bring_backs):
                result.append(
                    (
                        0,
                        count,
                        [lineup * count + i for i in group] + [lineup * count + qb],
                        [1] * len(group) + [-1],
                    )
                )
        for dst in positions["DST"]:
            for i, p in enumerate(pool):
                if p["team"] == pool[dst]["opponent"] and p["position"] != "DST":
                    result.append((0, 1, [lineup * count + dst, lineup * count + i], [1, 1]))
    return result


def verify(
    pool: list[dict[str, str | int]], lineups: int, picks: list[int], objective: float
) -> None:
    for low, high, indexes, values in rows(pool, lineups):
        total = sum(picks[i] * v for i, v in zip(indexes, values, strict=True))
        assert low <= total <= high, (low, high, total)
    count = len(pool)
    for a, b in combinations(range(lineups), 2):
        assert sum(picks[a * count + p] & picks[b * count + p] for p in range(count)) <= 7
    score = sum(
        picks[lineup * count + p] * int(player["points"])
        for lineup in range(lineups)
        for p, player in enumerate(pool)
    )
    assert abs(score / 100 - objective) < 0.01


def solve_highs(
    pool: list[dict[str, str | int]], lineups: int, cores: int, limit: int
) -> dict[str, object]:
    import highspy

    model = highspy.Highs()  # type: ignore[no-untyped-call]
    model.setOptionValue("output_flag", False)
    model.setOptionValue("threads", cores)
    model.setMaximize()  # type: ignore[no-untyped-call]
    count = len(pool)
    for _lineup in range(lineups):
        for player in pool:
            model.addVar(0.0, 1.0)
            index = model.getNumCol() - 1
            model.changeColIntegrality(index, highspy.HighsVarType.kInteger)
            model.changeColCost(index, float(player["points"]))
    for low, high, indexes, values in rows(pool, lineups):
        model.addRow(float(low), float(high), len(indexes), indexes, [float(v) for v in values])
    for a, b in combinations(range(lineups), 2):
        overlap = []
        for p in range(count):
            model.addVar(0.0, 1.0)
            y = model.getNumCol() - 1
            model.changeColIntegrality(y, highspy.HighsVarType.kInteger)
            model.addRow(-1.0, math.inf, 3, [y, a * count + p, b * count + p], [1.0, -1.0, -1.0])
            overlap.append(y)
        model.addRow(0.0, 7.0, len(overlap), overlap, [1.0] * len(overlap))
    model.setOptionValue("time_limit", float(limit))
    start = time.monotonic()
    model.run()
    duration = time.monotonic() - start
    info = model.getInfo()
    status = model.getModelStatus()
    feasible = model.getSolution().value_valid
    objective = info.objective_function_value / 100 if feasible else None
    gap = info.mip_gap if feasible and math.isfinite(info.mip_gap) else None
    if objective is not None:
        verify(
            pool,
            lineups,
            [round(v) for v in model.getSolution().col_value[: count * lineups]],
            objective,
        )
    return {
        "solver": "highs",
        "lineups": lineups,
        "cores": cores,
        "seconds": round(duration, 2),
        "objective": objective,
        "gap": gap,
        "proven": status == highspy.HighsModelStatus.kOptimal,
        "status": str(status),
    }


def solve_cpsat(
    pool: list[dict[str, str | int]], lineups: int, cores: int, limit: int
) -> dict[str, object]:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    count = len(pool)
    x = [model.new_bool_var(f"x_{i}") for i in range(count * lineups)]
    for low, high, indexes, values in rows(pool, lineups):
        expression = sum(x[i] * v for i, v in zip(indexes, values, strict=True))
        model.add_linear_constraint(expression, low, high)
    for a, b in combinations(range(lineups), 2):
        overlap = []
        for p in range(count):
            y = model.new_bool_var(f"y_{a}_{b}_{p}")
            model.add(y >= x[a * count + p] + x[b * count + p] - 1)
            overlap.append(y)
        model.add(sum(overlap) <= 7)
    model.maximize(
        sum(
            x[lineup * count + p] * int(player["points"])
            for lineup in range(lineups)
            for p, player in enumerate(pool)
        )
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(limit)
    solver.parameters.num_search_workers = cores
    start = time.monotonic()
    status = solver.solve(model)
    duration = time.monotonic() - start
    feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    objective = solver.objective_value / 100 if feasible else None
    if objective is not None:
        verify(pool, lineups, [solver.value(v) for v in x], objective)
    gap = (
        (
            max(0.0, solver.best_objective_bound - solver.objective_value)
            / max(1.0, abs(solver.objective_value))
        )
        if feasible
        else None
    )
    return {
        "solver": "cpsat",
        "lineups": lineups,
        "cores": cores,
        "seconds": round(duration, 2),
        "objective": objective,
        "gap": gap,
        "proven": status == cp_model.OPTIMAL,
        "status": solver.status_name(status),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("highs", "cpsat"))
    parser.add_argument("--lineups", type=int, choices=(6, 20))
    parser.add_argument("--cores", type=int, choices=(1, 2, 8))
    args = parser.parse_args()
    if args.case:
        if args.lineups is None or args.cores is None:
            parser.error("--case requires --lineups and --cores")
        pool = players()
        result = (solve_highs if args.case == "highs" else solve_cpsat)(
            pool, args.lineups, args.cores, LIMITS[args.lineups]
        )
        print(json.dumps(result), flush=True)
        return
    for lineups in LIMITS:
        for cores in (1, 2, 8):
            for solver in ("highs", "cpsat"):
                command = [
                    sys.executable,
                    __file__,
                    "--case",
                    solver,
                    "--lineups",
                    str(lineups),
                    "--cores",
                    str(cores),
                ]
                completed = subprocess.run(command, check=True, capture_output=True, text=True)
                print(completed.stdout.strip(), flush=True)


if __name__ == "__main__":
    main()
