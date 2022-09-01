from enum import Enum, EnumMeta
from typing import Any
from uuid import UUID

import starlite
from asyncpg.pgproto import pgproto
from pydantic import SecretStr

__all__ = ["Response"]


class Response(starlite.response.Response):
    """
    Custom [`starlite.Response`][starlite.response.Response] that handles serialization of the
    postgres UUID type used by SQLAlchemy.
    """

    @staticmethod
    def serializer(value: Any) -> Any:
        """
        Serializes `value`.

        Parameters
        ----------
        value : Any
            The thing to be serialized.

        Returns
        -------
        Any
            Serialized representation of `value`.
        """
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, EnumMeta):
            return None
        if isinstance(value, SecretStr):
            return value.get_secret_value()
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, pgproto.UUID):
            return str(value)
        return starlite.Response.serializer(value)
