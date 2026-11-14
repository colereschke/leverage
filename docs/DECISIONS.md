# Decision Records

Why things are built the way they are. Add an entry only when a future reader would otherwise have
to reconstruct _why_ a non-obvious choice was made: a rejected alternative, a constraint that shaped
the design, a deliberate deferral, or a tradeoff that isn't visible from reading the code. This is
not a changelog; `CLAUDE.md`'s "What's Built" covers the _what_.

## Format

```
### <Title> (<PR/roadmap ref>, <date>)
**Decision:** What was chosen.
**Why:** The reasoning — constraint, incident, or tradeoff that drove it.
**Alternatives considered:** What was rejected and why, if applicable.
**Status:** Active | Superseded by [[link]] | Flagged for revisit | Deferred
```

---

## Platform

### Python for the engine, API and agent layer (spec, 2026-11-01)

**Decision:** Python 3.12 for the core library, CLI, API and the v2 research agent; TypeScript +
React for the web client.

**Why:** The owner has deep Python experience and none in Kotlin. HiGHS has an official Python
binding (`highspy`) but none on the JVM. The Claude Agent SDK and document tooling (PDF extraction,
transcription) are Python-first. Solver time dominates runtime and is identical across languages,
so Kotlin's faster model building doesn't matter.

**Alternatives considered:** Kotlin on the JVM, for compile-time checking of the rule system via
sealed classes. Rejected: no fluency, and only a third-party HiGHS binding.

**Status:** Active

### Hosted from v1 (spec, 2026-11-01)

**Decision:** v1 is deployed, not local-only.

**Why:** Sunday-morning edits and late swap happen on a phone.

**Alternatives considered:** CLI + localhost UI only. Rejected for the phone requirement.

**Status:** Active

### ETR projections stay private; fixtures are synthetic (spec, 2026-11-01)

**Decision:** You upload your own ETR projections to your hosted instance, as with any optimizer.
ETR data is never made public: committed fixtures pair real DK salary files with synthetic,
seeded projections. Aggregate results (a lineup's total score, benchmark objectives) may be
committed; per-player ETR values may not. Real ETR files stay in the gitignored `data/` directory, and tests against
them skip when the files are absent.

**Why:** ETR projections are paid data. Uploading them to an optimizer is standard personal use;
publishing them (e.g. in a public repo) would be redistribution.

**Alternatives considered:** Adding noise to the real ETR projections. Rejected: lightly noised
projections are still ETR's numbers, and heavy noise is no better than synthetic.

**Status:** Active

### JSON files until Postgres (M1 planning, 2026-11-06)

**Decision:** The M1 CLI saves workspaces and builds as JSON files in the gitignored `data/`
directory. Postgres arrives in M3 with the API, or sooner if JSON stops being enough. Postgres is
the only database, including for local dev and tests.

**Why:** The storage schema will probably change once the API exists, so a database in M1 would
add a local install and a CI service for a single-user CLI, then need reworking. Going straight
to Postgres keeps one SQL dialect, and tests run on the same database as production.

**Alternatives considered:** Postgres from M1, rejected for that setup cost. JSON's cost is throwaway save and load code, and saved M1 builds need a one-time import to carry over.

**Status:** Active

## Workflow

### Describe, generate, choose (M1 planning, 2026-11-10)

**Decision:** General rules generate builds of any size (30 is normal). The owner saves lineups to
named groups and picks entries by hand. Limits count across one build only; groups never block
anything and show exposure instead. There are no pinned lineups: keep lineups by saving them, then
build again.

**Why:** The tool is meant to speed up building, not play DFS on autopilot. A rule that describes
one lineup just reproduces what the owner already pictured; general rules plus a lock show what
the slate offers, and an absence from a varied build is information. Any player can still be
locked in.

**Alternatives considered:** Per-lineup "stack plans" (asked for in the Week 8 notes), rejected
for the reason above. An automatic pick-best-K step, rejected as autopilot. Limits that block a
group, rejected because a group mixes builds by design. Pinned lineups, rejected because they make
saved lineups count toward a new build's limits.

**Status:** Active

### Joint portfolio optimization deferred past v1 (M1 planning, 2026-11-10)

**Decision:** v1 builds sequentially on HiGHS. Joint mode (R14), the CP-SAT joint model and the
8-core build worker are out of v1.

**Why:** A normal build of 30 lineups is beyond the 20 the M0 benchmark tested, and the spec
already fell back to sequential above 20. With entries picked by hand from a larger build, exact
exposure hits across the final card matter less, and the build worker is the most expensive piece
of hosting.

**Alternatives considered:** Keeping joint mode in M2. Rejected for now: it scored about 4 points
better in the prototype, so revisit if sequential builds disappoint on real slates.

**Status:** Deferred

### Week 8 lineups are a check, not a target (M1 planning, 2026-11-10)

**Decision:** M1's real-data gate validates the 14-lineup Week 8 pool against rules written from
the owner's Week 8 notes and reviews each disagreement, instead of rebuilding that portfolio.

**Why:** Those lineups came from the owner's second attempt at using a Claude session as an
optimizer, and only one is confirmed as entered. Matching them would hold the engine to an
unrefined process.

**Alternatives considered:** Rebuilding the reference portfolio from `rules.json`, the original
M1 gate.

**Status:** Active

## Optimizer

### HiGHS for single lineups, CP-SAT for joint portfolios (FEAT-001, 2026-11-03)

**Decision:** HiGHS for single lineups, sequential builds and late swap; OR-Tools CP-SAT for joint
portfolio builds, run on a separate build worker with 8 dedicated cores that scales to zero.

**Why:** HiGHS is fast on one core. CP-SAT expresses conditional rules and `allowViolations` scopes
natively (no big-M). The M0 spike found that CP-SAT needs 8 workers for this joint model: at 20
lineups it found a stronger feasible portfolio than HiGHS within 180 seconds, while its 1- and
2-worker results were weaker. A small web server cannot supply 8 dedicated cores.

The spike used the private 2026 Week 8 main-slate ETR file joined by DK ID to the committed salary
file. Both solvers used the same top-projection pool (12 QB, 40 RB, 70 WR, 30 TE, 16 DST), integer
projections scaled by 100, 9-player roster and position counts, $50,000 cap, at least 2 games,
at most 4 offensive players per team, QB + pass-catcher and bring-back minimums, no opposing
offense against DST, and at most 7 shared players per lineup pair. These are aggregate totals;
no per-player ETR values are recorded. Runs were sequential on an AMD Ryzen 7 7800X3D (8 physical
cores, 16 threads), HiGHS 1.15.1 and OR-Tools 9.15.6755. Time is solver time only; model
construction was excluded. One run per case, with no optimality proofs.

| Lineups | Cores | HiGHS seconds | HiGHS objective | HiGHS gap | CP-SAT seconds | CP-SAT objective | CP-SAT gap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 6 | 1 | 30.01 | 877.0 | 0.26% | 30.00 | 815.1 | 9.53% |
| 6 | 2 | 30.01 | 876.9 | 0.25% | 30.00 | 851.0 | 4.91% |
| 6 | 8 | 30.01 | 877.0 | 0.32% | 30.01 | 877.0 | 0.27% |
| 20 | 1 | 180.04 | 2885.0 | 1.65% | 180.01 | 2433.6 | 22.29% |
| 20 | 2 | 180.03 | 2877.1 | 1.91% | 180.03 | 2786.1 | 6.82% |
| 20 | 8 | 180.01 | 2882.7 | 1.70% | 180.28 | 2901.9 | 1.39% |

All 12 runs ended with a feasible portfolio and no proof of optimality. The script is
`bench/solver_spike.py`; rerun with `uv run --group bench python bench/solver_spike.py` when the
private ETR file is present. The result supports 8 cores for the joint build worker, but the
unproven gaps and single-run timings do not establish a reliable production latency guarantee.

**Alternatives considered:** HiGHS for joint portfolios too. It was stronger with 1 or 2 workers,
but CP-SAT was stronger at 20 lineups with 8 workers; keep HiGHS for single lineups and sequential
builds. Revisit if production model rules or hosting costs change the comparison.

**Status:** HiGHS choice active. The CP-SAT and build-worker parts are deferred with joint mode;
see "Joint portfolio optimization deferred past v1".

## Data import

### Projection import keeps ETR's values and fails loudly (FEAT-004, 2026-11-04)

**Decision:** `Projection.floor` may be negative. ETR's `LA` is aliased to DK's `LAR`. An ambiguous
match raises `AmbiguousMatchError` carrying the report, rather than returning a flagged result.
Ownership is keyed by the field size names `small` and `large`, not by entry count.
**Why:** The Week 8 ETR file has 8 negative DST floors, which are real values, and 14 Rams rows
that the team-mismatch policy would otherwise block every week. Raising means a caller can't
reach a build by ignoring a report field. ETR publishes two named columns with no contest sizes,
and a portfolio only ever picks one of them.
**Alternatives considered:** Clamping floors to 0 alters source data. A global list of team
aliases was skipped: only `LA` has been seen, and any other difference shows up in the report.
Integer entry counts as ownership keys would be invented numbers that look real. Row numbers as
the main resolution key would silently match the wrong player when a re-issued file shifts its
rows, so resolutions key on name, team, position and salary. Rows identical in all four use that
key plus the row number; a shift then leaves them blocked, though swapping two such rows can't
be detected.
**Status:** Active
