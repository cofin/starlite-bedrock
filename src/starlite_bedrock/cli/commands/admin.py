import binascii
import os

import typer
from alembic import command as migration_command
from alembic.config import Config as AlembicConfig

from starlite_bedrock.cli.console import console
from starlite_bedrock.config import db_settings, uvicorn_settings
from starlite_bedrock.run import get_app
from starlite_bedrock.schema import serialize_object

cli = typer.Typer(no_args_is_help=True)


@cli.command(name="generate-random-key")
def generate_random_key(length: int = 26) -> None:
    """Helper for admins to generate random 26 character string.

    Used as the secret key for sessions.
    Must be consistent (and secret) per environment.
    Output: b'random2323db3....1xyz'
    Copy the value in between the quotation marks to the settings file
    """
    console.print(binascii.hexlify(os.urandom(length)))


@cli.command(
    name="export-openapi-schema",
)
def export_api_schema(
    export_location: str = "domain/web/spec/openapi.json",
) -> None:
    """Push secrets to Secrets Provider"""

    console.print("Exporting API Schema")
    application = get_app(uvicorn_settings.ASGI_APP)
    schema = application.openapi_schema
    if schema:
        with open(export_location, "w", encoding="utf-8") as fd:
            fd.write(serialize_object(application.openapi_schema))
        console.print_json(schema.json())


@cli.command(
    name="create-database",
    help="Creates an empty postgres database and executes migrations",
)
def create_database() -> None:
    """Create database DDL migrations."""
    alembic_cfg = AlembicConfig(db_settings.MIGRATION_CONFIG)
    alembic_cfg.set_main_option("script_location", db_settings.MIGRATION_PATH)
    migration_command.upgrade(alembic_cfg, "head")


@cli.command(
    name="upgrade-database",
    help="Executes migrations to apply any outstanding database structures.",
)
def upgrade_database() -> None:
    """Upgrade the database to the latest revision."""
    alembic_cfg = AlembicConfig(db_settings.MIGRATION_CONFIG)
    alembic_cfg.set_main_option("script_location", db_settings.MIGRATION_PATH)
    migration_command.upgrade(alembic_cfg, "head")


@cli.command(
    name="reset-database",
    help="Executes migrations to apply any outstanding database structures.",
)
def reset_database() -> None:
    """Resets the database to an initial empty state."""
    _ = typer.confirm(
        "[bold red] Are you sure you want to drop and recreate all tables?",
    )
    alembic_cfg = AlembicConfig(db_settings.MIGRATION_CONFIG)
    alembic_cfg.set_main_option("script_location", db_settings.MIGRATION_PATH)
    console.log("Dropping the db")
    # models.BaseModel.metadata.drop_all(bind=engine)
    # console.log("Truncating the version table")
    # with session() as db:
    #     db.execute(sa.text("truncate table ddl_version"))
    #     db.commit()

    console.log("Recreating the db")
    migration_command.upgrade(alembic_cfg, "head")


@cli.command(
    name="purge-database",
    help="Drops all tables.",
)
def purge_database() -> None:
    """Drop all objects in the database."""
    _ = typer.confirm(
        "[bold red] Are you sure you want to drop everything?",
    )
    alembic_cfg = AlembicConfig(db_settings.MIGRATION_CONFIG)
    alembic_cfg.set_main_option("script_location", db_settings.MIGRATION_PATH)
    console.log("Dropping the db")
    # models.BaseModel.metadata.drop_all(bind=engine)
    # console.log("Truncating the version table")
    # with session() as db:
    #     db.execute(sa.text("truncate table ddl_version"))
    #     db.commit()


@cli.command(
    name="show-current-database-revision",
    help="Shows the current revision for the database.",
)
def show_database_revision() -> None:
    """Starts the Gluent Console API."""
    alembic_cfg = AlembicConfig(db_settings.MIGRATION_CONFIG)
    alembic_cfg.set_main_option("script_location", db_settings.MIGRATION_PATH)
    migration_command.current(alembic_cfg, verbose=False)
