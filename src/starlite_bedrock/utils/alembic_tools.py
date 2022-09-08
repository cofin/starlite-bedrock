import logging
from typing import TYPE_CHECKING

from alembic import command as migration_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Table
from sqlalchemy.schema import DropTable

from starlite_bedrock.orm import BaseModel, meta
from starlite_bedrock.utils import async_tools

if TYPE_CHECKING:
    from sqlalchemy import Engine
logger = logging.getLogger()


def create_database(migration_config: str, migration_path: str) -> None:
    """Create the database."""
    alembic_cfg = AlembicConfig(migration_config)
    alembic_cfg.set_main_option("script_location", migration_path)
    migration_command.upgrade(alembic_cfg, "head")


def upgrade_database(migration_config: str, migration_path: str) -> None:
    """Upgrade the database."""
    alembic_cfg = AlembicConfig(migration_config)
    alembic_cfg.set_main_option("script_location", migration_path)
    migration_command.upgrade(alembic_cfg, "head")


def drop_database(migration_config: str, migration_path: str, engine: "Engine") -> None:
    """Drop all objects in the database."""
    alembic_cfg = AlembicConfig(migration_config)
    alembic_cfg.set_main_option("script_location", migration_path)

    async_tools.run(drop_tables)(engine)


def reset_database(migration_config: str, migration_path: str, engine: "Engine") -> None:
    """Reset the database."""


def show_database_revision(migration_config: str, migration_path: str) -> str:
    """Show the current database revision."""
    alembic_cfg = AlembicConfig(migration_config)
    alembic_cfg.set_main_option("script_location", migration_path)
    migration_command.current(alembic_cfg, verbose=False)


async def drop_tables(engine: "Engine", alembic_config: "AlembicConfig") -> None:
    async with engine.begin() as db:
        BaseModel.metadata.drop_all()
        await db.execute(
            DropTable(
                element=Table("ddl_version", meta),
                if_exists=True,
            )
        )
        await db.commit()
