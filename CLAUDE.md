# Leverage — Claude Context

`AGENTS.md` is a symlink to this file, so Codex and other agents read the same instructions. Edit
`CLAUDE.md` only; `make check` fails if the symlink is replaced by a copy.

DraftKings NFL Classic lineup optimizer for one serious player: 1 cash lineup and a 6–20 entry GPP
portfolio each week. It turns rules usually applied by hand into a tested engine: QB stacks, conditional group rules, portfolio exposure targets, late swap, and DK export.
The owner (Cole) has deep Python experience and no Kotlin.

**Source of truth for design:** [`docs/spec.md`](docs/spec.md). Read it before planning engine,
rule or portfolio work, and update it in the same PR when a design changes. Its requirements
R1–R16 each trace to a real hand-building mistake; keep that traceability in tests. (It began as the
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
docs/project-timeline.md # ticket tracker: status, dependencies
docs/tickets.md   # ticket detail: scope, acceptance criteria, required tests
docs/DECISIONS.md # why non-obvious choices were made
```

The subpackages are empty stubs until their milestone starts.

## Engine Rules (from the spec)

- **The validator is independent.** It re-checks every lineup before display or export and must not
  share constraint code with the model builders. Most mistakes behind R1–R16 were a rule silently not applied.
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

- **Never commit ETR projections** or per-player values derived from them — paid data, and this
  repo is public. Aggregate results (a lineup's total score, solve times) are fine. Fixtures use real DK salary files with synthetic, seeded projections. Real ETR files go
  in the gitignored `data/`; tests that need them must skip when they're absent.

## Code Quality Rules

- Type everything; mypy strict must pass. Use `Protocol` for solver interfaces.
- No unused imports or variables (ruff errors). Do not skip the pre-commit hook with `--no-verify`.
- Tests that encode a requirement name it, e.g. `test_r3_any_of_group_counts_distinct_players`.

## What's Built

- Repo scaffold: uv package, `lev --version`, quality gate, pre-commit hook, CI, Dependabot.
- DK salary importer: `leverage.io.dk_salaries.read_dk_salaries` builds a Slate from `DKSalaries.csv`.
- Independent validator: `leverage.validate.validate_lineup` returns every core-constraint violation for a lineup on a Slate.

## What's Next

Work is ticketed. [`docs/project-timeline.md`](docs/project-timeline.md) has status and
dependencies; [`docs/tickets.md`](docs/tickets.md) has scope, acceptance criteria and required
tests, plus the per-ticket workflow. Pick a Ready ticket, and in its PR update its row and outcome.
IDs: `FEAT-` (product and engine), `HARD-` (review and audit fixes), `OPS-` (tooling, CI, deploy).

Current milestone: M0 Foundations (`FEAT-001`–`FEAT-006`). The real-data checks are M1 local
acceptance tests.

## Repo Rules

**Extract decisions, then clean up superpowers docs.** Specs and plans in `docs/superpowers/` are
working documents. When a feature merges: for non-trivial work, add an entry to `docs/DECISIONS.md`
(decision, why, alternatives), then delete the spec/plan files. For self-evident work, just delete
them.
