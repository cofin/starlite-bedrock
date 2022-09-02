import asyncio
import sys
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


async def c(engine: "AsyncEngine") -> None:
    """
    Checks for database connectivity.
    """
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:  # pylint: disable=broad-except
        print(f"Waiting for Postgres: {e}")  # noqa: T201
        sys.exit(-1)
    else:
        print("Postgres OK!")  # noqa: T201


def main(engine: "AsyncEngine") -> None:
    """Entrypoint"""
    asyncio.run(c(engine))
