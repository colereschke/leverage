# Leverage

A DraftKings NFL Classic lineup optimizer for one player building a cash lineup and a small GPP
portfolio (6–20 entries) each week: QB stacks, conditional group rules, portfolio exposure targets,
late swap, and DraftKings upload export.

The design lives in [`docs/spec.md`](docs/spec.md); the reasoning behind key choices is in
[`docs/DECISIONS.md`](docs/DECISIONS.md).

## Getting started

**Prerequisites:** [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 if needed).

```bash
make setup        # install dependencies and enable the pre-commit hook
uv run lev --help # the CLI
make check        # mypy, ruff, pytest
```

Run `make` to list every target.
