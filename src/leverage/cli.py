"""The `lev` command line interface."""

from typing import Annotated

import typer

from leverage import __version__

app = typer.Typer(help="Build DraftKings lineups and GPP portfolios.", no_args_is_help=True)


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"lev {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_print_version,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Build DraftKings lineups and GPP portfolios."""
