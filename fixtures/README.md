# Golden slates

Real slates used as regression fixtures. Each slate gets its own directory, named
`<season>-w<week>-<slate>` (for example `2026-w07-main/`):

```
2026-w07-main/
  DKSalaries.csv     # DraftKings salary file (real)
  projections.csv    # synthetic projections, seeded and reproducible — never ETR data
  rules.json         # the rule document used that week
  expected.json      # results the engine must reproduce on these inputs
```

The reference slate is `2026-w07-main/` (273 players), the first slate with saved files. Add
slates over time.

**ETR projections never go in this directory.** They are paid data and this repo may be public.
The real ETR files live in the gitignored `data/` directory, e.g.
`data/2026-w07-main/etr.csv`. The M1 acceptance tests that reproduce real results on the reference slate
(max-projection lineup = 155.1 at $50,000; first stacked build with λ = 0.1 = 147.9) skip when that
file is absent, so they run locally but not in CI.
