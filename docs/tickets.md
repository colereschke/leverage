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
  [Builds and groups](spec.md#builds-and-groups)
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

**Outcome:** PR #3 — benchmarked both solvers at 6/20 lineups and 1/2/8 cores; retained the provisional 8-core CP-SAT joint-worker choice.

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

**Outcome:** [PR #4](https://github.com/colereschke/leverage/pull/4) — shipped immutable
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

**Outcome:** [PR #5](https://github.com/colereschke/leverage/pull/5) — `read_dk_salaries` in
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

**Outcome:** [PR #7](https://github.com/colereschke/leverage/pull/7) — `import_projections` with ETR and generic presets, a test per policy case, and an empty report on the synthetic reference.

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

**Outcome:** [PR #6](https://github.com/colereschke/leverage/pull/6) — seeded DK-only generator and ETR-shaped CSV for all 562 reference players, with determinism and value-invariant tests.

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

**Outcome:** [PR #8](https://github.com/colereschke/leverage/pull/8) — `validate_lineup` returns every core-constraint violation, with hand-built valid and invalid sets on the reference slate and import-boundary tests.

## M1 Engine + CLI

Every M1 rule ticket adds its check to the validator in the same PR. That check is plain code
written against the rule document, never shared with the compiler: the import-boundary test from
`FEAT-006` extends to `leverage.rules`' compiler modules.

### FEAT-007 - Exact reference check

- **Milestone:** M1
- **Spec:** [Testing and validation](spec.md#testing-and-validation) (exact reference check)
- **Covers:** —

**Scope:** A test helper, no solver and no code shared with `model/`, that finds the
max-projection lineup: a dynamic program over players by position count and salary in $100 steps,
with a fallback search when the best lineup breaks the 2-games or own-DST-opponent rule. Test code
only (`tests/`), since nothing in production needs it.

**Acceptance criteria:**

- On pools of about 20 players, it returns the same score as enumerating every legal lineup.
- On the synthetic fixture it finishes within CI's time limit and returns a lineup the validator
  accepts.
- It runs on the real ETR file locally and skips when the file is absent.

**Required tests:** brute-force agreement on several seeded small pools, including pools where
the best lineup breaks the 2-games and DST rules; a validator check on its synthetic result.

**Outcome:** `tests/reference.py` `best_lineup` — per-DST knapsack over salary in $100 steps, with an unconstrained pass as an upper bound so only DSTs that could win get the exact pass. Matches brute force on seeded 20-player pools, including pools where the best lineup is one game or faces its DST; the synthetic and real ETR lineups pass the validator.

### FEAT-008 - Domain model for build configs, builds and groups

- **Milestone:** M1
- **Spec:** [Domain model](spec.md#domain-model), [Requirements](spec.md#requirements) (Terms),
  [Builds and groups](spec.md#builds-and-groups)
- **Covers:** —

**Scope:** Add `BuildConfig` (rule document reference, player overrides, objective weights w, λ and
noise, ownership column), `PlayerOverride` (projection, ownership, injury status, lock, ban,
min/max exposure, only-in-stack, source, approval status), `Build` (input snapshot with file hashes,
config, size, seed, solver settings, status, duration) and `Group` (slate, lineups, entry
assignments). `Lineup.build_id` becomes optional. `Portfolio` is removed. Cash and small/large-field
GPP presets per the spec. Models only: no solving or storage.

**Acceptance criteria:**

- Models are frozen pydantic `DomainModel`s and reject invalid values (negative exposure, min above
  max, unknown ownership column).
- Only `approved` overrides are returned when a config is resolved for a build.
- The three presets construct with the spec's values.

**Required tests:** validation tests per model; preset values; approved-only filtering.

**Outcome:**

### FEAT-009 - JSON storage

- **Milestone:** M1
- **Spec:** [Data ingestion and export](spec.md#data-ingestion-and-export) (Storage),
  [Non-functional requirements](spec.md#non-functional-requirements) (N9–N11)
- **Covers:** —

**Scope:** Save and load workspaces, build configs, builds and groups as JSON files under the
gitignored `data/` directory, keyed by slate. Raw imported files are kept with their hash. Writes go
to a temp file and are renamed into place, keeping the previous version. Every file carries a
schema version, and loading an unknown version fails clearly.

**Acceptance criteria:**

- A save then load returns equal objects for every model.
- A write that fails partway leaves the previous file intact and loadable.
- The previous version of each file is kept after a successful write.
- Loading a file with a newer or unknown schema version raises a clear error.

**Required tests:** round trips; a simulated crash mid-write; version mismatch; storage paths stay
inside `data/`.

**Outcome:**

### FEAT-010 - Single-lineup model on HiGHS

- **Milestone:** M1
- **Spec:** [Optimizer engine](spec.md#optimizer-engine), [Functional requirements](spec.md#functional-requirements)
  (F2, F2a, F5, F24)
- **Covers:** R13, R15

**Scope:** Move `highspy` into the main dependencies. A `Solver` protocol in `solvers/` with a
HiGHS implementation, and a solver-agnostic single-lineup builder in `model/`: one binary per
player, the objective blend (w, λ, seeded ε), and the core constraints (roster counts, salary cap,
2 games, no offense facing your DST, max players per team). Applies a config's approved overrides
(projection, ownership, lock, ban), and players marked OUT are banned unless the config undoes it.
Returns the lineup with projection and ceiling, both without noise. The validator gains the max
players per team check.

**Acceptance criteria:**

- With w = 0, λ = 0 and no noise, the lineup's score equals `FEAT-007`'s on the synthetic fixture.
- Locks are always in, bans and OUT players never are, and projection overrides change the result.
- The same seed gives the same lineup; reported scores exclude noise.
- One lineup solves in under 2 seconds on the reference slate (checked locally, not in CI).

**Required tests:** `FEAT-007` agreement; lock, ban, OUT and override tests;
`test_r15_objective_blends_projection_and_ceiling`; seed determinism; validator acceptance of every
result.

**Outcome:**

### FEAT-011 - FLEX slot assignment

- **Milestone:** M1
- **Spec:** [Optimizer engine](spec.md#optimizer-engine) (slot assignment)
- **Covers:** R11

**Scope:** After solving, assign players to slots so the latest-kicking eligible RB/WR/TE takes
FLEX, while the remaining players still fill a legal core. Assignment never changes which players
are chosen.

**Acceptance criteria:**

- FLEX holds the latest-kicking eligible player whenever a legal assignment allows it.
- Kickoff ties resolve the same way every time.
- Every assigned lineup passes the validator's slot-eligibility check.

**Required tests:** `test_r11_latest_kicking_eligible_player_takes_flex`; a case where the latest
player can't take FLEX (an only TE); a tie case.

**Outcome:**

### FEAT-012 - Rule document schema

- **Milestone:** M1
- **Spec:** [Rule system](spec.md#rule-system)
- **Covers:** —

**Scope:** The versioned JSON rule document as pydantic models, one per rule type in the spec's
table, with `allowViolations`, `source`, `status` and `enabled`. Loading checks that every DK ID
exists on the slate and that `allowViolations` appears only on per-lineup rules. Schema only: no
compiler.

**Acceptance criteria:**

- The spec's example document loads.
- Unknown rule types, unknown DK IDs, a bad version and `allowViolations` on a cross-lineup rule
  are rejected with messages naming the rule.
- Only enabled, approved rules reach a build.

**Required tests:** the spec example; one rejection test per error; approved-only filtering.

**Outcome:**

### FEAT-013 - Per-lineup rules

- **Milestone:** M1
- **Spec:** [Rule system](spec.md#rule-system), [Functional requirements](spec.md#functional-requirements)
  (F4, F5a, F7–F12, F15)
- **Covers:** R3, R4, R5, R6, R8, R9

**Scope:** Compile `stack_default`, `stack_qb`, `group`, `team_group`, `avoid_own_dst` (with
positions), `only_in_stack`, `player_pool`, `salary` and `min_projection` into the single-lineup
model, with a matching validator check for each. Locks ignore `min_projection`; a lock that
contradicts a ban or a `player_pool` is rejected before solving, naming both.

**Acceptance criteria:**

- Each rule type, on a minimal pool where it alone decides the answer, changes the result as
  specified.
- On pools of about 20 players, the optimizer's best lineup matches brute-force enumeration of
  every lineup a plain-code check of the rule accepts.
- A naked QB with bring-backs builds when stack rules allow it.
- Contradicting locks are rejected before solving.

**Required tests:** per rule type, a minimal-pool test and a brute-force test, named by
requirement (e.g. `test_r3_any_of_group_counts_distinct_players`,
`test_r5_if_none_trigger_applies_when_qb_absent`, `test_r8_rb_allowed_with_own_dst_when_scoped`);
validator tests for each check.

**Outcome:**

### FEAT-014 - Sequential builds and build outcomes

- **Milestone:** M1
- **Spec:** [Builds and groups](spec.md#builds-and-groups), [Build outcomes](spec.md#build-outcomes),
  [Functional requirements](spec.md#functional-requirements) (F5a, F6, F16, F20–F22, F25, F36)
- **Covers:** R1, R2

**Scope:** Build N lineups sequentially: per-player min/max and global max exposure with the
spec's rounding, uniqueness, minimum exposure forced when the remaining count equals the shortfall,
and variety defaults (global max plus seeded noise). Locks ignore the global max; a lock that
breaks a per-player max or locks that alone break uniqueness are rejected before solving. Every
build has a time limit, ends in one of the spec's statuses, runs the validator on every lineup,
reports each lineup's rule checks, and is saved with its input snapshot.

**Acceptance criteria:**

- A 30-lineup build on the synthetic fixture honors every exposure and uniqueness limit.
- Each status is produced by a test that forces it, including partial and timed_out.
- A lineup the validator rejects ends the build as `invalid`.
- The same config and seed give the same lineups.
- A locked QB builds 30 lineups under a 50% global max.

**Required tests:** `test_r1_exposure_cap_counts_lineups_built`,
`test_r2_min_exposure_forced_into_remaining_lineups`; exposure rounding; one test per status; the
locked-QB case; lock-conflict rejection; seed determinism.

**Outcome:**

### FEAT-015 - Cross-lineup rules

- **Milestone:** M1
- **Spec:** [Rule system](spec.md#rule-system), [Functional requirements](spec.md#functional-requirements)
  (F13, F14, F17–F19)
- **Covers:** R7, R10

**Scope:** In sequential builds: `pair_limit` (named sets and the positional "any two TEs" form),
`game_presence` (min/max lineups, min offensive players), `dst_pool` (allowed DSTs, min per DST,
salary floor with min lineups), `chalk_coverage` as a soft target that ends a build as
`targets_missed` with the misses listed, and `allowViolations` budgets spent first-come. Validator
checks for each.

**Acceptance criteria:**

- Each rule holds across a build, checked by the validator.
- Unmet chalk coverage lists the players and never fails the build.
- A rule with `allowViolations: 1` is broken in at most one lineup.

**Required tests:** `test_r7_pair_limit_counts_lineups_together`,
`test_r10_allow_violations_breaks_rule_at_most_n_times`; per-rule tests for game presence, DST
salary floor and chalk coverage, including banned and OUT players being excluded from coverage.

**Outcome:**

### FEAT-016 - Groups and the exposure view

- **Milestone:** M1
- **Spec:** [Builds and groups](spec.md#builds-and-groups) (groups, exposure view)
- **Covers:** R2

**Scope:** Save lineups to named groups (one slate, first copy kept), mix builds, and hold
hand-made or imported lineups with no build. Show current numbers beside built-with numbers, and
flag lineups holding OUT or banned players. One exposure function over any set of lineups: player
count, percentage and field ownership in a chosen column; QB, primary stack, bring-back and game
exposure; the most players any two lineups share; top-owned players at 0%, with a confirmable fade.
Returns data only.

**Acceptance criteria:**

- A group mixing two builds can exceed a cap each build met, and the view shows it.
- Saving a lineup twice keeps one copy with its original numbers.
- A player ruled OUT after saving flags every lineup holding him.
- A confirmed fade stops the 0% flag for that slate.

**Required tests:** exposure math on a hand-built set; dedupe; OUT flagging; fade confirmation;
`test_r2_top_owned_player_at_zero_is_flagged`.

**Outcome:**

### FEAT-017 - Projection re-import report

- **Milestone:** M1
- **Spec:** [Data ingestion and export](spec.md#data-ingestion-and-export) (re-import)
- **Covers:** R13

**Scope:** Re-importing a newer projection file keeps configs and overrides, and reports which
players' projections moved by more than 1 point.

**Acceptance criteria:**

- Overrides still apply after a re-import.
- The report lists exactly the players who moved more than 1 point.

**Required tests:** `test_r13_overrides_survive_reimport`; the moved-player report on two seeded
synthetic files.

**Outcome:**

### FEAT-018 - DK upload and text export

- **Milestone:** M1
- **Spec:** [Data ingestion and export](spec.md#data-ingestion-and-export) (DK bulk upload, text
  export, pre-export review)
- **Covers:** —

**Scope:** Export a group as DK's bulk-upload CSV and as text, after the pre-export review summary.
One lineup can fill several entries. Settle the upload cell format (`Name (dk_id)` or bare ID)
against a real DK upload and record it in the spec.

**Acceptance criteria:**

- The review lists import timestamps, unresolved matches, moved projections, flagged lineups, build
  statuses (missed targets need acknowledging) and counts.
- The written file matches the reviewed group and validates against the salary file.
- A lineup holding an OUT or banned player produces a loud warning, not a block.

**Required tests:** export round trip against the salary file; review contents; the warning case;
blocked export of lineups from an invalid build.

**Outcome:**

### FEAT-019 - `lev` CLI for the M1 workflow

- **Milestone:** M1
- **Spec:** [API and interfaces](spec.md#api-and-interfaces) (CLI)
- **Covers:** —

**Scope:** Thin Typer commands over the core: `lev slate import`, `lev config` (create from a
preset, set rules and overrides from files), `lev build`, `lev group` (save, list), `lev exposure`
and `lev export`. No logic beyond argument handling and printing.

**Acceptance criteria:**

- The full M1 workflow runs from the CLI on the synthetic fixture: import, configure, build 30,
  save to a group, view exposure, export.
- Errors from the core (rejected locks, bad rule documents, failed builds) print clearly with a
  non-zero exit code.

**Required tests:** an end-to-end CLI test on the synthetic fixture; error-exit tests.

**Outcome:**

### FEAT-020 - M1 acceptance checks

- **Milestone:** M1
- **Spec:** [Milestones and roadmap](spec.md#milestones-and-roadmap) (M1 exit),
  [Testing and validation](spec.md#testing-and-validation) (golden slates, performance)
- **Covers:** —

**Scope:** Record synthetic-fixture builds (cash and a 30-lineup GPP) as golden results in CI.
Locally: write `rules.json` from the owner's Week 8 notes into `data/2026-w08-main/`, run the
14-lineup Week 8 pool through the validator, and review each disagreement with the owner; run
`FEAT-007` and a 30-lineup build on the real ETR file and record the timing.

**Acceptance criteria:**

- CI fails when a synthetic build's recorded result changes.
- Every Week 8 disagreement is resolved as either "the old lineup broke the rule" or "the rule was
  written wrong", with the rule fixed in the latter case.
- The 30-lineup real-data build meets N1 on the owner's machine.
- Nothing ETR-derived is committed; only aggregate results are recorded.

**Required tests:** the golden-result tests; local tests that skip without the ETR file.

**Outcome:**

## M2 Swap + diagnosis

Outline tickets: acceptance criteria and required tests are firmed up when M1 closes.

### FEAT-021 - DK entries import

- **Milestone:** M2
- **Spec:** [Data ingestion and export](spec.md#data-ingestion-and-export) (late swap edit file)
- **Covers:** —

**Scope:** Import DK's entries export (with Entry IDs) as a group, including lineups edited on DK.
Imported lineups run through the validator and are flagged, not rejected, when they break a rule.

**Acceptance criteria:** every entry maps to a lineup; unknown players or slots fail clearly.

**Required tests:** import of a hand-built entries file on the reference slate.

**Outcome:**

### FEAT-022 - Late swap

- **Milestone:** M2
- **Spec:** [Late swap](spec.md#late-swap)
- **Covers:** R12

**Scope:** Lock games by kickoff or individually; re-solve unlocked slots per lineup with
slot-level variables and a keep-current bonus, under a config chosen at swap time. Per-lineup rules
are enforced and cross-lineup limits reported. Proposals with per-lineup diffs; apply all or one;
export DK's edited entries file.

**Acceptance criteria:** locked players never move; freed salary is used; a late scratch produces a
multi-slot change; locked rule breaks are reported.

**Required tests:** `test_r12_late_scratch_reoptimizes_every_unlocked_slot`; locked-player and
freed-salary tests.

**Outcome:**

### FEAT-023 - Repair and planned swaps

- **Milestone:** M2
- **Spec:** [Late swap](spec.md#late-swap) (planned swaps, repair)
- **Covers:** R12

**Scope:** Repair: late swap with no games locked on lineups flagged for OUT or banned players.
Planned swaps per player, applied to every lineup in the group holding him and checked at swap
time.

**Acceptance criteria:** a repair changes only flagged lineups; a planned swap that became invalid
is reported, not applied.

**Required tests:** repair keeps every unaffected lineup; planned-swap validity.

**Outcome:**

### FEAT-024 - Conflict diagnosis and rule cost

- **Milestone:** M2
- **Spec:** [Rule system](spec.md#rule-system) (diagnostics)
- **Covers:** —

**Scope:** For partial and infeasible builds, a deletion filter names a minimal set of conflicting
rules for the lineup that failed, with earlier lineups fixed. Rule cost runs on demand.

**Acceptance criteria:** the named set is minimal and its rules can't all hold together.

**Required tests:** known-conflict cases, including exposure rounding (min above max).

**Outcome:**

## M3 API + web UI

Outline tickets, firmed up when M2 closes. Expect `HARD-` review tickets here as well.

### FEAT-025 - API, build jobs and Postgres storage

- **Milestone:** M3
- **Spec:** [API and interfaces](spec.md#api-and-interfaces), [Storage](spec.md#data-ingestion-and-export)
- **Covers:** —

**Scope:** FastAPI routes per the spec, builds as async jobs, and Postgres replacing JSON storage,
with a one-time import of saved JSON files.

**Outcome:**

### FEAT-026 - Owner-only access

- **Milestone:** M3
- **Spec:** [API and interfaces](spec.md#api-and-interfaces) (access)
- **Covers:** —

**Scope:** Discord OAuth restricted to the owner's user ID; every route except sign-in rejects
anyone else.

**Outcome:**

### FEAT-027 - Web UI

- **Milestone:** M3
- **Spec:** [API and interfaces](spec.md#api-and-interfaces) (web UI)
- **Covers:** —

**Scope:** React + TypeScript UI with the five tabs, groups and the exposure view with display
thresholds, working at phone width. Playwright tests at desktop and 390 px.

**Outcome:**

### FEAT-028 - Lineup editor and build diff

- **Milestone:** M3
- **Spec:** [Functional requirements](spec.md#functional-requirements) (F32, F41)
- **Covers:** R16

**Scope:** Edit a lineup by hand with live validation and projection and ownership deltas; compare
builds to see what changed.

**Outcome:**

### OPS-002 - Hosted deploy

- **Milestone:** M3
- **Spec:** [Overview](spec.md#overview) (hosted v1)
- **Covers:** —

**Scope:** Docker image, hosting for the API, UI and Postgres, and backups.

**Outcome:**
