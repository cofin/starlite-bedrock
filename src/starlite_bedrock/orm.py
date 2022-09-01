import functools
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional, TypeVar

from sqlalchemy import Column, MetaData
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.event import listens_for
from sqlalchemy.orm import DeclarativeBase, Mapped, Session
from sqlalchemy.orm import registry as orm_registry
from sqlalchemy.orm.decl_api import declarative_mixin, declared_attr
from sqlalchemy.sql import func as sql_func

from starlite_bedrock.db_types import GUID, DateTime

if TYPE_CHECKING:
    from pydantic import UUID4


convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
"""
Templates for automated constraint name generation.
"""

meta = MetaData(naming_convention=convention)
mapper_registry: orm_registry = orm_registry(metadata=meta, type_annotation_map={uuid.UUID: pg.UUID, dict: pg.JSONB})


@listens_for(Session, "before_flush")
def touch_updated_timestamp(session: Session, *_: Any) -> None:
    """
    Called from SQLAlchemy's [`before_flush`][sqlalchemy.orm.SessionEvents.before_flush] event to
    bump the `updated` timestamp on modified instances.

    Parameters
    ----------
    session : Session
        The sync [`Session`][sqlalchemy.orm.Session] instance that underlies the async session.
    """
    for instance in session.dirty:
        if getattr(instance, "updated_at", None):
            setattr(instance, "updated_at", datetime.now())  # noqa: B010


class BaseModel(DeclarativeBase):
    """
    Base for all SQLAlchemy declarative models.
    """

    registry = mapper_registry
    # required in order to access columns with server defaults
    # or SQL expression defaults, subsequent to a flush, without
    # triggering an expired load
    __mapper_args__ = {"eager_defaults": True}

    def from_dict(self, dict: Dict[str, Any]) -> "BaseModel":
        """Return ORM Object from Dictionary"""
        if self.__table__:
            for column in self.__table__.columns:
                if column.name in dict:
                    setattr(self, column.name, dict.get(column.name))
        return self

    def dict(self) -> dict:
        """Returns a dict representation of a model."""
        if self.__table__:
            return {field.name: getattr(self, field.name) for field in self.__table__.columns}
        return {}


@declarative_mixin
class GUIDModelMixin:
    """GUID Column Mixin"""

    id: Mapped["UUID4"] = Column(GUID, primary_key=True, default=uuid.uuid4)
    id._creation_order = 1  # type: ignore[protected-access,attr-defined]


@declarative_mixin
class CreatedUpdatedAtMixin:
    """Created At/Updated At Mixin"""

    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=datetime.now(timezone.utc),
        server_default=sql_func.now(),
        comment="Date the record was inserted",
    )
    created_at._creation_order = 9998  # type: ignore[protected-access,attr-defined]
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        server_default=None,
        comment="Date the record was last modified",
    )
    updated_at._creation_order = 9998  # type: ignore[protected-access,attr-defined]


def _get_default_expires_at(timedelta_seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=timedelta_seconds)


@declarative_mixin
class ExpiresAtMixin:
    """Expires at mixin"""

    __lifetime_seconds__: int = 3600

    @declared_attr
    def expires_at(cls) -> Column[DateTime]:
        return Column(
            DateTime(timezone=True),
            nullable=False,
            index=True,
            default=functools.partial(
                _get_default_expires_at,
                timedelta_seconds=cls.__lifetime_seconds__,
            ),
        )


M = TypeVar("M", bound=BaseModel)
M_UUID = TypeVar("M_UUID", bound=GUIDModelMixin)
M_CREATED_UPDATED_AT = TypeVar("M_CREATED_UPDATED_AT", bound=CreatedUpdatedAtMixin)
M_EXPIRES_AT = TypeVar("M_EXPIRES_AT", bound=ExpiresAtMixin)


def find_by_table_name(table_name: str) -> Optional["BaseModel"]:
    """Return model based on class"""
    for mapper in mapper_registry.mappers:
        model: BaseModel = mapper.class_  # type: ignore
        model_class_name = model.__tablename__
        if model_class_name == table_name:
            return model
    return None
