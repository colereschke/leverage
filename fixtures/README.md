# Golden slates

Real slates used as regression fixtures. Each slate gets its own directory, named
`<season>-w<week>-<slate>` (for example `2026-w08-main/`):

```
2026-w08-main/
  DKSalaries.csv     # DraftKings salary file (real)
  projections.csv    # synthetic projections, seeded and reproducible — never ETR data
  rules.json         # the rule document used that week
  expected.json      # results the engine must reproduce on these inputs
```

The reference slate is `2026-w08-main/` (11 games, 562 DK players). Add slates over time.

Regenerate its synthetic projections from the committed DK salary file with:

```bash
uv run python scripts/generate_synthetic_projections.py \
  fixtures/2026-w08-main/DKSalaries.csv \
  fixtures/2026-w08-main/projections.csv --seed 5
```

The generator reads only the DK file. The two ownership columns each sum to about 900%, or one
nine-player lineup's worth of ownership.

**ETR projections never go in this directory.** They are paid data and this repo may be public.
The real ETR files live in the gitignored `data/` directory, e.g.
`data/2026-w08-main/etr.csv`. Tests that run on real ETR data (the exact max-projection check, and
the reference portfolio rebuilt from `rules.json`) skip when that file is absent, so they run
locally but not in CI.
