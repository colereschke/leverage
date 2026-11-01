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

### HiGHS for single lineups, CP-SAT for joint portfolios (spec, 2026-11-01)

**Decision:** HiGHS for single lineups, sequential builds and late swap; OR-Tools CP-SAT for joint
portfolio builds, run on a separate build worker with 8+ dedicated cores that scales to zero.

**Why:** HiGHS is fast on one core and deterministic single-threaded. CP-SAT expresses conditional
rules and `allowViolations` scopes natively (no big-M) and suits the all-boolean joint model, but
its speed comes from ~8 parallel workers that small hosting tiers don't provide.

**Alternatives considered:** One solver for everything. Deferred to the M0 benchmark (joint model on
the reference slate at 6 and 20 lineups, both solvers, 1/2/8 cores).

**Status:** Flagged for revisit after the M0 benchmark.
