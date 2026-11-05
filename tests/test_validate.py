"""The validator accepts and rejects hand-built lineups on the reference slate (M0 gate)."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from leverage import validate
from leverage.domain import Lineup, LineupSlot, Slate
from leverage.io.dk_salaries import read_dk_salaries
from leverage.validate import validate_lineup

SALARIES = Path(__file__).parents[1] / "fixtures/2026-w08-main/DKSalaries.csv"
FORBIDDEN_IMPORTS = ("leverage.model", "leverage.solvers", "highspy", "ortools")

GOFF, DOBBS, ALTMYER = "44664393", "44664429", "44664430"  # DET QB
GIBBS, VAKI, SAYLORS = "44664465", "44664607", "44664609"  # DET RB
ST_BROWN, WILLIAMS, TESLAA, MARTIN = "44664721", "44664743", "44664839", "44664927"  # DET WR
LAPORTA, WRIGHT = "44665131", "44665247"  # DET TE
LIONS = "44665390"  # DET DST
YUROSEK = "44665309"  # MIN TE, faces the Lions
NACUA = "44664717"  # LAR WR
KEENAN_ALLEN = "44664789"  # IND WR, $4,500
FLOURNOY = "44664785"  # DAL WR, $4,600
BOWERS = "44665125"  # LV TE, $7,600

# Exactly two games, $48,800, stacked with its own DST.
BASE = {
    "QB": GOFF,
    "RB1": GIBBS,
    "RB2": VAKI,
    "WR1": NACUA,
    "WR2": WILLIAMS,
    "WR3": TESLAA,
    "TE": LAPORTA,
    "FLEX": WRIGHT,
    "DST": LIONS,
}


def build(**changes: str) -> dict[str, str]:
    return BASE | changes


def lineup(slots: dict[str, str]) -> Lineup:
    # The claimed salary is deliberately wrong: the validator must price lineups from the slate.
    # model_construct skips Lineup's own checks, which the validator must not rely on.
    return Lineup.model_construct(
        build_id="test",
        slots=tuple(LineupSlot(slot=slot, player_id=dk_id) for slot, dk_id in slots.items()),
        salary=1,
        proj=0,
        ceiling=0,
        ownership=0,
    )


@pytest.fixture(scope="module")
def slate() -> Slate:
    return read_dk_salaries(SALARIES, slate_id="2026-w08-main", week=8)


def checks(slots: dict[str, str], slate: Slate) -> set[str]:
    return {violation.check for violation in validate_lineup(lineup(slots), slate)}


@pytest.mark.parametrize(
    "slots",
    [
        pytest.param(BASE, id="te-flex-two-games-own-dst-stack"),
        pytest.param(build(FLEX=MARTIN), id="wr-flex"),
        pytest.param(build(QB=DOBBS, FLEX=SAYLORS), id="rb-flex"),
        pytest.param(build(WR3=KEENAN_ALLEN), id="exactly-at-cap"),
    ],
)
def test_feat_006_accepts_valid_lineups(slots: dict[str, str], slate: Slate) -> None:
    assert validate_lineup(lineup(slots), slate) == []


@pytest.mark.parametrize(
    ("slots", "expected"),
    [
        pytest.param(build(RB2=TESLAA, WR3=VAKI), {"slot_eligibility"}, id="positions-swapped"),
        pytest.param(
            {("UTIL" if slot == "FLEX" else slot): dk_id for slot, dk_id in BASE.items()},
            {"slot_eligibility"},
            id="slot-not-in-format",
        ),
        pytest.param(
            {slot: dk_id for slot, dk_id in BASE.items() if slot != "FLEX"},
            {"distinct_players", "slot_eligibility"},
            id="eight-players",
        ),
        pytest.param(build(TE=WRIGHT), {"distinct_players"}, id="duplicate-player"),
        pytest.param(build(WR3=FLOURNOY), {"salary_cap"}, id="100-over-cap"),
        # Filled, eligible slots imply legal counts, so this check never fires alone.
        pytest.param(
            build(QB=DOBBS, FLEX=ALTMYER),
            {"slot_eligibility", "position_counts"},
            id="two-qbs",
        ),
        pytest.param(build(WR1=ST_BROWN), {"min_games"}, id="one-game"),
        pytest.param(build(FLEX=YUROSEK), {"dst_conflict"}, id="offense-facing-dst"),
        pytest.param(build(FLEX="999"), {"unknown_player"}, id="player-not-on-slate"),
    ],
)
def test_feat_006_rejects_invalid_lineups_naming_the_check(
    slots: dict[str, str], expected: set[str], slate: Slate
) -> None:
    assert checks(slots, slate) == expected


def test_feat_006_returns_every_violation_not_only_the_first(slate: Slate) -> None:
    slots = build(RB2=TESLAA, WR3=VAKI, TE=BOWERS, FLEX=YUROSEK)
    assert checks(slots, slate) == {"slot_eligibility", "salary_cap", "dst_conflict"}


def test_feat_006_violation_message_names_the_offending_player(slate: Slate) -> None:
    [violation] = validate_lineup(lineup(build(FLEX=YUROSEK)), slate)
    assert "Ben Yurosek" in violation.message
    assert "Lions" in violation.message


def test_feat_006_validate_module_never_imports_a_solver_directly() -> None:
    imported: set[str] = set()
    for node in ast.walk(ast.parse(Path(validate.__file__).read_text())):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not [name for name in imported if name.startswith(FORBIDDEN_IMPORTS)]


def test_feat_006_importing_validate_loads_no_solver_transitively() -> None:
    code = (
        "import sys, leverage.validate\n"
        f"print([m for m in sys.modules if m.startswith({FORBIDDEN_IMPORTS!r})])"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    )
    assert result.stdout.strip() == "[]"
