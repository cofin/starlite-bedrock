from datetime import datetime, timezone
from enum import Enum, EnumMeta
from typing import Any, Generic, List, TypeVar, Union
from uuid import UUID

import orjson
from pydantic import BaseModel as _BaseSchema
from pydantic import BaseSettings as _BaseSettings
from pydantic import Field, SecretBytes, SecretStr
from pydantic.generics import GenericModel


def serialize_object(obj: Any) -> str:
    """
    Encodes json with the optimized ORJSON package

    orjson.dumps returns bytearray, so you can't pass it directly as json_serializer
    """

    def _serializer(obj: Any) -> Any:
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, EnumMeta):
            return None
        if isinstance(obj, SecretStr):
            return obj.get_secret_value()
        if isinstance(obj, UUID):
            return str(obj)
        raise TypeError

    return orjson.dumps(
        obj,
        default=_serializer,
        option=orjson.OPT_NAIVE_UTC | orjson.OPT_SERIALIZE_NUMPY,
    ).decode()


def deserialize_object(obj: Union[bytes, bytearray, memoryview, str, dict[str, Any]]) -> Any:
    """
    Decodes to an object with the optimized ORJSON package

    orjson.dumps returns bytearray, so you can't pass it directly as json_serializer

    """
    if isinstance(obj, dict):
        return obj
    return orjson.loads(obj)


def convert_datetime_to_gmt(dt: datetime) -> str:
    """Handles datetime serialization for nested timestamps in models/dataclasses"""
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def convert_field_to_camel_case(string: str) -> str:
    """Converts a string to camel case

    Args:
        string (str): The string to convert

    Returns:
        str: The string converted to camel case
    """
    return "".join(word if index == 0 else word.capitalize() for index, word in enumerate(string.split("_")))


class BaseSchema(_BaseSchema):
    """
    Base schema model for input deserialization and validation, and output serialization.

    Attributes
    ----------
    created : datetime
        Date/time of instance creation. Read-only attribute.
    updated: datetime
        Date/time of last instance update. Read-only attribute.
    """

    class Config:

        arbitrary_types_allowed = True
        orm_mode = True
        use_enum_values = True
        json_loads = deserialize_object
        json_dumps = serialize_object
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: convert_datetime_to_gmt,
            SecretStr: lambda secret: secret.get_secret_value() if secret else None,
            SecretBytes: lambda secret: secret.get_secret_value() if secret else None,
            Enum: lambda enum: enum.value if enum else None,
            EnumMeta: None,
        }


class CamelizedBaseSchema(BaseSchema):
    """Camelized Base pydantic schema"""

    class Config:
        allow_population_by_field_name = True
        alias_generator = convert_field_to_camel_case


class BaseModelSchema(BaseSchema):
    """
    Base schema model for input deserialization and validation, and output serialization.

    Attributes
    ----------
    created_at : datetime
        Date/time of instance creation. Read-only attribute.
    updated_at: datetime
        Date/time of last instance update. Read-only attribute.
    """

    class Config(BaseSchema.Config):
        extra = "ignore"

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BaseSettings(_BaseSettings):
    """Base Settings"""

    class Config:
        """Base Settings Config"""

        json_loads = deserialize_object
        json_dumps = serialize_object
        case_sensitive = True
        json_encoders = {
            datetime: convert_datetime_to_gmt,
            SecretStr: lambda secret: secret.get_secret_value() if secret else None,
            SecretBytes: lambda secret: secret.get_secret_value() if secret else None,
            Enum: lambda enum: enum.value if enum else None,
            EnumMeta: None,
        }
        validate_assignment = True
        orm_mode = True
        use_enum_values = True
        env_file = ".env"
        env_file_encoding = "utf-8"


BaseSchemaType = TypeVar("BaseSchemaType", bound=BaseSchema)  # pylint: disable=[invalid-name]


class TotaledResults(GenericModel, Generic[BaseSchemaType]):
    """Provides count and result of result set"""

    count: int
    results: List[BaseSchemaType]


class PaginatedResults(GenericModel, Generic[BaseSchemaType]):
    """Provides count, result, and page information of results"""

    count: int
    limit: int
    skip: int
    results: List[BaseSchemaType]
