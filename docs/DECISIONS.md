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

**Status:** Active, provisional until the M2 production model benchmark.
