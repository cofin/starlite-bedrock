import typer

from starlite_bedrock.cli.console import console
from starlite_bedrock.config import api_settings

cli = typer.Typer(
    no_args_is_help=True,
    rich_markup_mode="markdown",
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_short=True,
    add_completion=False,
)


@cli.command()
def api(
    host: str = typer.Option(
        api_settings.BIND_HOST,
        "--host",
        "-h",
        help="Host interface to listen on.  Use 0.0.0.0 for all available interfaces.",
    ),
    port: int = typer.Option(api_settings.TCP_PORT, "--port", "-p", help="Port to listen on."),
    http_workers: int = typer.Option(
        api_settings.HTTP_WORKERS,
        "--http-workers",
        "-wh",
        help="Number of HTTP workers to run.  This should equal the number of CPUs available.",
    ),
    background_workers: int = typer.Option(
        api_settings.BACKGROUND_WORKERS,
        "--background-workers",
        "-wb",
        help="Number of Background workers to run.  Defaults to 2.",
    ),
    use_gunicorn: bool = typer.Option(
        False,
        "--use-gunicorn",
        help=(
            "Use Gunicorn instead of only uvicorn.  "
            "This should best in places where process management isn't managed (i.e. outside of Docker/K8s)"
        ),
    ),
) -> None:
    """Run the API server."""

    console.print(f"✨ Starlite API with {http_workers} HTTP and {background_workers} background workers")
    if use_gunicorn:
        from starlite_bedrock.config import (  # pylint: disable=[import-outside-toplevel]
            gunicorn_settings,
        )
        from starlite_bedrock.run import (  # pylint: disable=[import-outside-toplevel]
            run_wsgi,
        )

        gunicorn_settings.HOST = host
        gunicorn_settings.PORT = port
        gunicorn_settings.WORKERS = http_workers
        run_wsgi(
            host=gunicorn_settings.HOST,
            port=gunicorn_settings.PORT,
            http_workers=gunicorn_settings.WORKERS,
            reload=gunicorn_settings.RELOAD,
        )
    else:
        from starlite_bedrock.config import (  # pylint: disable=[import-outside-toplevel]
            uvicorn_settings,
        )
        from starlite_bedrock.run import (  # pylint: disable=[import-outside-toplevel]
            run_asgi,
        )

        uvicorn_settings.HOST = host
        uvicorn_settings.PORT = port
        uvicorn_settings.WORKERS = http_workers
        run_asgi(
            host=uvicorn_settings.HOST,
            port=uvicorn_settings.PORT,
            http_workers=uvicorn_settings.WORKERS,
            reload=uvicorn_settings.RELOAD,
        )
