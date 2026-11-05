# Leverage Tickets

Detail for each ticket in [`docs/project-timeline.md`](project-timeline.md), which holds status and
dependencies. Tickets link to [`docs/spec.md`](spec.md) for the design instead of restating it.

## Required workflow for every ticket

1. Read `CLAUDE.md` and the spec sections the ticket links.
2. Run `git pull origin main` before creating a branch or worktree.
3. Branch from current `main`, one ticket per branch, named after the ticket
   (`feat-002-domain-model`).
4. Write a failing test before changing behavior.
5. Run `make check` before review.
6. In the same PR: update the ticket's row in the tracker and fill in its **Outcome** below.

## Ticket format

```
### <ID> - <title>
- **Milestone:** M0 | M1 | …
- **Spec:** links to the sections it implements
- **Covers:** R-numbers, or —

**Scope:** what's in, and what's explicitly left for later.
**Acceptance criteria:** checkable statements.
**Required tests:** the tests that prove them.
**Outcome:** PR, then one line on what shipped. Empty until complete.
```

A completed ticket keeps its scope and criteria, plus a one-line outcome. Lasting reasons go in
`docs/DECISIONS.md`.

---

## M0 Foundations

### FEAT-001 - Solver benchmark spike

- **Milestone:** M0
- **Spec:** [Optimizer engine](spec.md#optimizer-engine) (solver choice),
  [Portfolio optimization](spec.md#portfolio-optimization)
- **Covers:** —

**Scope:** A throwaway script in `bench/` that builds a rough joint portfolio model on the
reference slate (local `data/` ETR file) and times HiGHS against CP-SAT. It does its own CSV parsing
and doesn't import `leverage`. Not production code: no tests beyond "it runs", and M1/M2 rebuild
the models properly.

**Acceptance criteria:**

- Runs the joint model at 6 and 20 lineups on both solvers at 1, 2 and 8 cores, with the core
  roster, salary, stack and pairwise-overlap constraints.
- Records, per run: solve time, objective, optimality gap, and whether optimality was proven.
- Results and the solver decision (confirm or change the split) are written to
  `docs/DECISIONS.md`, updating the "HiGHS for single lineups, CP-SAT for joint portfolios" entry.
  The recommended build-worker core count is stated.
- No ETR projections or per-player values are committed. Timings, gaps, objective totals and
  the decision are fine (aggregate results, per the data rule in `CLAUDE.md`).

**Required tests:** none; the results are the deliverable.

**Outcome:** Draft PR #3 — benchmarked both solvers at 6/20 lineups and 1/2/8 cores; retained the provisional 8-core CP-SAT joint-worker choice.

### FEAT-002 - Domain model for slates, players and lineups

- **Milestone:** M0
- **Spec:** [Domain model](spec.md#domain-model)
- **Covers:** —

**Scope:** pydantic v2 models in `src/leverage/domain/` for RosterFormat, Slate, Game, Player,
Projection, Lineup and Portfolio. DraftKings Classic is a RosterFormat instance (data, not code).
Workspace, PlayerOverride, Rule, Build and SwapRun wait for M1, when something uses them.

**Acceptance criteria:**

- Models are immutable (`frozen=True`); players are keyed by DK ID.
- DK Classic defines its 9 slots, the eligible positions for each slot, and the $50,000 cap.
- Kickoffs are timezone-aware UTC datetimes.
- mypy strict passes without `Any` leaking from the models.

**Required tests:** construction and validation errors for each model (e.g. a naive kickoff
datetime is rejected); DK Classic FLEX accepts RB/WR/TE and rejects QB and DST.

**Outcome:** [Draft PR #4](https://github.com/colereschke/leverage/pull/4) — shipped immutable
Pydantic domain models, DK Classic roster data, and validation tests.

### FEAT-003 - DK salary file importer

- **Milestone:** M0
- **Spec:** [Data ingestion and export](spec.md#data-ingestion-and-export)
- **Covers:** —

**Scope:** `src/leverage/io/` reads `DKSalaries.csv` into a Slate with Players and Games. Also
commits the reference slate's salary file to `fixtures/2026-w08-main/DKSalaries.csv`.

**Acceptance criteria:**

- Every row imports, with positions, team, opponent, salary, game and injury status (`Status`:
  blank, Q, OUT, IR) correct.
- Game Info is parsed into a Game with a UTC kickoff (ET → UTC, DST-aware).
- DST rows are recognized and normalized.
- A malformed row fails the import with its row number and reason; nothing is dropped silently.

**Required tests:** the reference file imports every row and spot-checks known players, games and
kickoffs (this is half of the M0 gate); a small malformed file fails with a row-specific error.

**Outcome:** [Draft PR #5](https://github.com/colereschke/leverage/pull/5) — `read_dk_salaries` in
`src/leverage/io/dk_salaries.py` imports all 562 reference rows and 11 games, and fails on the first malformed row with its file line number and reason.

### FEAT-004 - Projection importer with the import policy

- **Milestone:** M0
- **Spec:** [Data ingestion and export](spec.md#data-ingestion-and-export) (matching and
  validation, import policy)
- **Covers:** —

**Scope:** A column mapper with an ETR preset and a generic preset, name normalization, matching by
DK ID then by name + team, and an import report. Ambiguous-match resolutions are read from a
mapping file passed to the importer; storing them comes with the Workspace (M1). The re-import
"moved by more than 1 point" report is in M1.

**Acceptance criteria:**

- Each policy case from the spec behaves as written: ambiguous match blocks the import; a DK
  player without a projection is excluded and listed; an unmatched projection row is listed and
  ignored; salary/team/position mismatches keep DK's value and are listed; a team mismatch also
  blocks that player.
- Unprojected DK players are reported as a count, with names listed only for those with no injury
  status and a salary above their position's slate minimum.
- Every row is accounted for in the report (by name or in a count); none disappears silently.

**Required tests:** one test per policy case on small hand-written CSVs; the synthetic reference
projections import with an empty report. Policy-case tests are part of the M0 gate.

**Outcome:**

### FEAT-005 - Synthetic reference fixture

- **Milestone:** M0
- **Spec:** [Testing and validation](spec.md#testing-and-validation) (golden slates),
  [`fixtures/README.md`](../fixtures/README.md)
- **Covers:** —

**Scope:** A seeded generator that creates `fixtures/2026-w08-main/projections.csv` from the DK
salary file alone (salary, position), plus floor, ceiling and two ownership columns, in the ETR
column layout. The generator and its output are committed. `rules.json` and `expected.json` come
in M1.

**Acceptance criteria:**

- The generator reads only the DK salary file. It never reads `data/` or anything ETR.
- The same seed produces a byte-identical file.
- Values are plausible enough to exercise stacks and exposure: higher salaries project higher on
  average, ceiling ≥ projection ≥ floor ≥ 0, and ownership sums to roughly 9 × 100% per column.

**Required tests:** determinism (regenerate and compare); the value invariants above.

**Outcome:** [Draft PR #6](https://github.com/colereschke/leverage/pull/6) — seeded DK-only generator and ETR-shaped CSV for all 562 reference players, with determinism and value-invariant tests.

### FEAT-006 - Independent lineup validator

- **Milestone:** M0
- **Spec:** [Testing and validation](spec.md#testing-and-validation) (validator),
  [Optimizer engine](spec.md#optimizer-engine) (core constraints)
- **Covers:** —

**Scope:** `src/leverage/validate.py` checks a lineup against a Slate and RosterFormat: slot
eligibility, 9 distinct players, salary cap, position counts, players from at least 2 games, and
no offensive player facing the lineup's DST. It returns every violation found, not only the first. No
solver imports and no code shared with `model/`. Max players per team, rule, exposure and overlap
checks are added in M1 and M2 as those settings land.

**Acceptance criteria:**

- Accepts every lineup in a hand-built valid set on the synthetic fixture.
- Rejects every lineup in a hand-built invalid set, one per check, naming the violated check.
- No module in `leverage.validate` imports `leverage.model`, `leverage.solvers`, `highspy` or
  `ortools`.

**Required tests:** the valid and invalid sets (the other half of the M0 gate); an import-boundary
test that enforces the no-solver rule.

**Outcome:**
