"""Small command-line surface; no pretend implementations."""

import typer

from agentbenchkit import __version__

app = typer.Typer(no_args_is_help=True, help="Local coding-agent evaluation and evidence.")


@app.callback()
def main() -> None:
    """Local coding-agent evaluation and evidence."""


@app.command()
def version() -> None:
    """Print the AgentBenchKit version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
