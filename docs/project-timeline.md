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

- Milestone: M1 Engine + CLI. M0 Foundations closed 2026-11-04. M1 is ticketed in full; M2 and M3
  have outline tickets.
- Reference slate: 2026 Week 8 main. `fixtures/2026-w08-main/DKSalaries.csv` is committed; the ETR
  export lives in `data/2026-w08-main/etr.csv` (gitignored, never committed).
- The owner's Week 8 notes are in hand; the reference `rules.json` is written from them in M1 and
  kept in the gitignored `data/`.
- Open Dependabot PRs: none.

## Master ticket table

Rows are not column-aligned on purpose, so a status change touches one line and parallel
branches don't conflict. Covers lists the spec requirements (R1–R16) a ticket implements; M0
builds the foundation they need, so none of its tickets cover one yet.

| ID | Ticket | Milestone | Status | Depends on | Covers | PRs / commits | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `OPS-001` | Repo scaffold: uv package, `lev` CLI, quality gate, CI, Dependabot | — | Complete | — | — | `e858fcd` | — |
| `FEAT-001` | Solver benchmark spike | M0 | Complete | Reference files | — | [#3](https://github.com/colereschke/leverage/pull/3) | — |
| `FEAT-002` | Domain model for slates, players and lineups | M0 | Complete | — | — | [#4](https://github.com/colereschke/leverage/pull/4) | — |
| `FEAT-003` | DK salary file importer | M0 | Complete | `FEAT-002`, reference files | — | [#5](https://github.com/colereschke/leverage/pull/5) | — |
| `FEAT-004` | Projection importer with the import policy | M0 | Complete | `FEAT-003`, `FEAT-005` | — | [#7](https://github.com/colereschke/leverage/pull/7) | — |
| `FEAT-005` | Synthetic reference fixture | M0 | Complete | `FEAT-003` | — | [#6](https://github.com/colereschke/leverage/pull/6) | — |
| `FEAT-006` | Independent lineup validator | M0 | Complete | `FEAT-002`, `FEAT-005` | — | [#8](https://github.com/colereschke/leverage/pull/8) | — |
| `FEAT-007` | Exact reference check | M1 | In progress | — | — | — | Branch `feat-007-exact-reference-check` |
| `FEAT-008` | Domain model for build configs, builds and groups | M1 | Ready | — | — | — | Branch `feat-008-domain-configs-groups` |
| `FEAT-009` | JSON storage | M1 | Planned | `FEAT-008` | — | — | — |
| `FEAT-010` | Single-lineup model on HiGHS | M1 | Planned | `FEAT-007`, `FEAT-008` | R13, R15 | — | — |
| `FEAT-011` | FLEX slot assignment | M1 | Planned | `FEAT-010` | R11 | — | — |
| `FEAT-012` | Rule document schema | M1 | Planned | `FEAT-008` | — | — | — |
| `FEAT-013` | Per-lineup rules | M1 | Planned | `FEAT-010`, `FEAT-012` | R3–R6, R8, R9 | — | — |
| `FEAT-014` | Sequential builds and build outcomes | M1 | Planned | `FEAT-009`, `FEAT-013` | R1, R2 | — | — |
| `FEAT-015` | Cross-lineup rules | M1 | Planned | `FEAT-014` | R7, R10 | — | — |
| `FEAT-016` | Groups and the exposure view | M1 | Planned | `FEAT-009`, `FEAT-014` | R2 | — | — |
| `FEAT-017` | Projection re-import report | M1 | Planned | `FEAT-009` | R13 | — | — |
| `FEAT-018` | DK upload and text export | M1 | Planned | `FEAT-011`, `FEAT-016` | — | — | — |
| `FEAT-019` | `lev` CLI for the M1 workflow | M1 | Planned | `FEAT-015`, `FEAT-017`, `FEAT-018` | — | — | — |
| `FEAT-020` | M1 acceptance checks | M1 | Planned | `FEAT-019` | — | — | — |
| `FEAT-021` | DK entries import | M2 | Planned | M1 | — | — | — |
| `FEAT-022` | Late swap | M2 | Planned | `FEAT-021` | R12 | — | — |
| `FEAT-023` | Repair and planned swaps | M2 | Planned | `FEAT-022` | R12 | — | — |
| `FEAT-024` | Conflict diagnosis and rule cost | M2 | Planned | M1 | — | — | — |
| `FEAT-025` | API, build jobs and Postgres storage | M3 | Planned | M2 | — | — | — |
| `FEAT-026` | Owner-only access | M3 | Planned | `FEAT-025` | — | — | — |
| `FEAT-027` | Web UI | M3 | Planned | `FEAT-026` | — | — | — |
| `FEAT-028` | Lineup editor and build diff | M3 | Planned | `FEAT-027` | R16 | — | — |
| `OPS-002` | Hosted deploy | M3 | Planned | `FEAT-026` | — | — | — |

## M0 gate

M0 closes when `FEAT-003`, `FEAT-004` and `FEAT-006` pass the spec's M0 test in CI and `FEAT-001`
has recorded its results in `docs/DECISIONS.md`.

Closed 2026-11-04: both conditions met, with CI green on `main` at `9ce5e37`.

## M1 gate

M1 closes when `FEAT-020` passes: synthetic builds match recorded results in CI, `FEAT-007` agrees
with the optimizer (CI and locally), rule types match brute-force enumeration, the Week 8 pool is
validated with every disagreement reviewed, and a 30-lineup real-data build meets N1.

## Outline tickets

M2 and M3 tickets are outlines. Their acceptance criteria and required tests are firmed up when
the milestone before them is close to done, since earlier results can change them.

## Dependency view

```text
FEAT-007 reference check ──┐
FEAT-008 domain ───────────┼── FEAT-010 lineup model ── FEAT-011 FLEX ──────────────┐
   ├── FEAT-012 rule schema┴── FEAT-013 per-lineup rules ──┐                         │
   └── FEAT-009 storage ───────────────────────────────────┴─ FEAT-014 sequential ──┤
          └── FEAT-017 re-import                     FEAT-015 cross-lineup ──┐       │
                                                     FEAT-016 groups ────────┼─ FEAT-018 export
                                                                             └─ FEAT-019 CLI ── FEAT-020
```

`FEAT-007`, `FEAT-008`, `FEAT-012` and `FEAT-017` can run alongside the model work once their own
dependencies land.

## Maintenance rules

- The PR that does the work updates its row here and its outcome in `docs/tickets.md`.
- When a ticket completes, record the PR and a one-line outcome. Move lasting design reasons to
  `docs/DECISIONS.md` rather than writing them into the ticket.
- New work gets a `FEAT-`, `HARD-` or `OPS-` ID and a row here before a branch is created.
- Design changes go in `docs/spec.md`; tickets link to the spec instead of restating it.
