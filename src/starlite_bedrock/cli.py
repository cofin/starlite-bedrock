import typer
from rich.console import Console

console = Console(markup=True)

app = typer.Typer(no_args_is_help=True)
