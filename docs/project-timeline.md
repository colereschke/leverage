# Leverage Project Timeline & Tracker

This is the current planning view: what's done, what's next, and what each ticket depends on.
Ticket details (acceptance criteria, required tests, outcomes) live in
[`docs/tickets.md`](tickets.md). What each milestone delivers and the test that closes it live in
the spec's [Milestones and roadmap](spec.md#milestones-and-roadmap); this file tracks status only.

## ID conventions

- `FEAT-###`: product and engine work, including spikes that decide how it's built.
- `HARD-###`: correctness, security and maintainability work found by reviews and audits.
- `OPS-###`: repo tooling, CI, deployment, hosting and monitoring.

Numbers are never reused. A ticket keeps its ID if it moves to another milestone.

## Status definitions

- **Planned:** scoped, but blocked by a dependency.
- **Ready:** dependencies met; nobody is working on it.
- **In progress:** a branch exists. Name it in the Next action column.
- **Complete:** merged to `main` and verified.
- **Deferred:** intentionally not being done now; the reason is in its ticket.

## Current snapshot

- Milestone: M0 Foundations. Nothing in M0 has started.
- Reference slate: 2026 Week 8 main. `fixtures/2026-w08-main/DKSalaries.csv` is committed; the ETR
  export lives in `data/2026-w08-main/etr.csv` (gitignored, never committed).
- Still needed from the owner before M1: the rules behind the Week 8 GPP portfolio, for the
  reference `rules.json`.
- Open Dependabot PRs: #1 (setup-uv 9 → 10), #2 (uv-build < 0.14).

## Master ticket table

Rows are not column-aligned on purpose, so a status change touches one line and parallel
branches don't conflict. Covers lists the spec requirements (R1–R16) a ticket implements; M0
builds the foundation they need, so none of its tickets cover one yet.

| ID | Ticket | Milestone | Status | Depends on | Covers | PRs / commits | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `OPS-001` | Repo scaffold: uv package, `lev` CLI, quality gate, CI, Dependabot | — | Complete | — | — | `e858fcd` | — |
| `FEAT-001` | Solver benchmark spike | M0 | Complete | Reference files | — | [#3](https://github.com/colereschke/leverage/pull/3) | — |
| `FEAT-002` | Domain model for slates, players and lineups | M0 | In progress | — | — | [#4](https://github.com/colereschke/leverage/pull/4) | Review draft PR |
| `FEAT-003` | DK salary file importer | M0 | In progress | `FEAT-002`, reference files | — | [#5](https://github.com/colereschke/leverage/pull/5) | Review draft PR |
| `FEAT-004` | Projection importer with the import policy | M0 | Planned | `FEAT-003`, `FEAT-005` | — | — | — |
| `FEAT-005` | Synthetic reference fixture | M0 | In progress | `FEAT-003` | — | — | Review generator and fixture |
| `FEAT-006` | Independent lineup validator | M0 | Planned | `FEAT-002`, `FEAT-005` | — | — | — |

## M0 gate

M0 closes when `FEAT-003`, `FEAT-004` and `FEAT-006` pass the spec's M0 test in CI and `FEAT-001`
has recorded its results in `docs/DECISIONS.md`.

## Not yet ticketed

Each milestone's tickets are written when the milestone before it is close to done, since earlier
results (especially the M0 benchmark) can change them.

- **M1 Engine + CLI:** lineup model on HiGHS with the projection/ceiling blend (R15); projection
  overrides (R13); FLEX slot assignment (R11); rule document schema and compiler for stack and
  group rules (R3–R6, R8, R9); sequential portfolios with exposure (R1, R2); build outcomes;
  projection re-import report; DK upload export with the pre-export review; exact reference check
  (max-projection DP) and brute-force rule tests; local acceptance test rebuilding the reference
  portfolio on real ETR data.
- **M2 Portfolio + swap:** joint model on CP-SAT (R14); pair limits (R7) and allowViolations
  scopes (R10); correlated exposure; late swap + DK entries (R12); infeasibility report.
- **M3 API + web UI:** saved, diffable build history (R16); the rest per the spec. Expect the first
  `OPS-` deploy and `HARD-` review tickets here.

## Dependency view

```text
Reference files (owner) ──┬───────────────────────── FEAT-001 benchmark spike
                          │
FEAT-002 domain model ────┴── FEAT-003 DK importer ── FEAT-005 synthetic fixture
                                                          ├── FEAT-004 projection importer
                                                          └── FEAT-006 validator (+ FEAT-002)
```

`FEAT-001` is a throwaway script with its own rough parsing, so it doesn't wait for the importers.

## Maintenance rules

- The PR that does the work updates its row here and its outcome in `docs/tickets.md`.
- When a ticket completes, record the PR and a one-line outcome. Move lasting design reasons to
  `docs/DECISIONS.md` rather than writing them into the ticket.
- New work gets a `FEAT-`, `HARD-` or `OPS-` ID and a row here before a branch is created.
- Design changes go in `docs/spec.md`; tickets link to the spec instead of restating it.
