from functools import partial
from typing import Any
from uuid import UUID

from orjson import dumps
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from starlite_bedrock.config import db_settings

__all__ = [
    "engine",
    "async_session_factory",
]


def _default(val: Any) -> str:
    if isinstance(val, UUID):
        return str(val)
    raise TypeError()


engine = create_async_engine(
    db_settings.URL,
    echo=db_settings.ECHO,
    echo_pool=db_settings.ECHO_POOL,
    json_serializer=partial(dumps, default=_default),
    max_overflow=db_settings.POOL_MAX_OVERFLOW,
    pool_size=db_settings.POOL_SIZE,
    pool_timeout=db_settings.POOL_TIMEOUT,
    poolclass=NullPool if db_settings.POOL_DISABLE else None,
)
"""Configure via [DatabaseSettings][starlite_lib.config.DatabaseSettings]. Overrides default JSON 
serializer to use `orjson`. See [`create_async_engine()`][sqlalchemy.ext.asyncio.create_async_engine]
for detailed instructions.
"""
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
"""
Database session factory. See [`async_sessionmaker()`][sqlalchemy.ext.asyncio.async_sessionmaker].
"""
