import typer

from starlite_bedrock.cli.commands import run_cli

cli = typer.Typer(
    no_args_is_help=True,
    help="Starlite CLI",
    add_completion=False,
)

cli.add_typer(
    run_cli,
    name="run",
    help="Run Server Processes",
)
