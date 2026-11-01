# Leverage — Claude Context

DraftKings NFL Classic lineup optimizer for one serious player: 1 cash lineup and a 6–20 entry GPP
portfolio each week. It turns the rules applied by hand on the 2026 Week 7 main slate into a tested
engine: QB stacks, conditional group rules, portfolio exposure targets, late swap, and DK export.
The owner (Cole) has deep Python experience and no Kotlin.

**Source of truth for design:** [`docs/spec.md`](docs/spec.md). Read it before planning engine,
rule or portfolio work, and update it in the same PR when a design changes. Its requirements
R1–R16 each trace to a real Week 7 mistake; keep that traceability in tests. (It began as the
"Stack Lab Project Spec" Claude Doc; that copy is no longer maintained.)

## Quick Commands

```bash
make setup        # First-time: uv sync + enable .githooks/pre-commit
make check        # Full quality gate: mypy + ruff lint + ruff format check + pytest
make test         # pytest only
make format       # ruff format
uv run lev --help # the CLI
```

## Tech Stack

- **Python 3.12**, managed with **uv** (`uv add`, `uv run`; never pip directly). `uv.lock` is committed.
- **Typer** for the `lev` CLI (`src/leverage/cli.py`)
- **pytest** for tests; **mypy** strict; **ruff** for lint and format (100-char lines)
- Pre-commit hook in `.githooks/pre-commit` (enabled by `make hooks`): ruff format check, ruff lint, mypy
- CI: GitHub Actions runs `make check` on every PR and push to main

Planned, per the spec — add each when the milestone that needs it starts, not before:
pydantic v2 (domain), highspy and OR-Tools CP-SAT (solvers), pandas (CSV mapping), Hypothesis
(property tests), FastAPI + Postgres (API, M3), React + TypeScript in `web/` (M3).

## Project Structure

```
src/leverage/
├── cli.py        # Typer app, entry point `lev`
├── domain/       # Slate, Player, Game, Projection, Lineup, Portfolio
├── rules/        # rule document schema + compiler, one module per rule type
├── model/        # single-lineup and joint-portfolio model builders (solver-agnostic)
├── solvers/      # HiGHS and CP-SAT behind one Solver protocol
├── swap/         # late swap
├── io/           # DK salary + entries files, projection mapper, DK upload export
└── validate.py   # independent validator: plain code, never calls a solver
tests/            # pytest
fixtures/         # golden slates, one directory per slate (see fixtures/README.md)
docs/spec.md      # the design spec: requirements, domain model, engine, roadmap
docs/DECISIONS.md # why non-obvious choices were made
```

The subpackages are empty stubs until their milestone starts.

## Engine Rules (from the spec)

- **The validator is independent.** It re-checks every lineup before display or export and must not
  share constraint code with the model builders. Every Week 7 mistake was a rule silently not applied.
- **Rules are data.** A typed, versioned JSON document per workspace, compiled into constraints.
  Players are referenced by DraftKings ID, never by name.
- **`allowViolations: N`** means a rule may be broken in at most N lineups. 0 (default) = every lineup.
- **Source data is immutable.** Slates are never edited; overrides, rules and builds hang off a
  Workspace. Overrides and rules carry `source` and `status`; only `approved` items reach a build
  (the hook for the v2 research agent).
- **Every build ends in one status** (optimal, feasible, targets_missed, infeasible, timed_out,
  invalid), defined in the spec's Build outcomes. Never present a missed target or timeout as a
  valid portfolio.
- **Solver split:** HiGHS for single lineups, sequential mode and late swap; CP-SAT for joint
  portfolio builds. Provisional until the M0 benchmark; see `docs/DECISIONS.md`.

## Data Rules

- **Never commit ETR projections** (or anything derived from them) — paid data, and this repo may be
  public. Fixtures use real DK salary files with synthetic, seeded projections. Real ETR files go
  in the gitignored `data/`; tests that need them must skip when they're absent.

## Code Quality Rules

- Type everything; mypy strict must pass. Use `Protocol` for solver interfaces.
- No unused imports or variables (ruff errors). Do not skip the pre-commit hook with `--no-verify`.
- Tests that encode a Week 7 requirement name it, e.g. `test_r3_any_of_group_counts_distinct_players`.

## What's Built

- Repo scaffold: uv package, `lev --version`, quality gate, pre-commit hook, CI, Dependabot.

## What's Next

M0 Foundations, in order: the solver benchmark spike (a throwaway script in `bench/`: Week 7 joint
model at 6 and 20 lineups, HiGHS vs CP-SAT, 1/2/8 cores; record results in `docs/DECISIONS.md`),
domain model, DK + ETR importers with the spec's import policy, independent validator, synthetic
Week 7 fixture. M0 closes in CI when the Week 7 DK salary file imports every row with correct
positions, games and kickoffs, and the validator accepts and rejects a hand-built set of
lineups. The real 155.1 check is an M1 local acceptance test.

## Repo Rules

**Extract decisions, then clean up superpowers docs.** Specs and plans in `docs/superpowers/` are
working documents. When a feature merges: for non-trivial work, add an entry to `docs/DECISIONS.md`
(decision, why, alternatives), then delete the spec/plan files. For self-evident work, just delete
them.
