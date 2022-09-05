import functools
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional, TypeAlias, TypeVar

from sqlalchemy import BigInteger, Boolean, Column, Identity, MetaData, String
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.event import listens_for
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, Session
from sqlalchemy.orm import registry as orm_registry
from sqlalchemy.orm.decl_api import declarative_mixin, declared_attr
from sqlalchemy.sql import func as sql_func
from sqlalchemy.sql.expression import FunctionElement

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


class coalesce(FunctionElement):  # pylint: disable=[invalid-name]
    name = "coalesce"
    inherit_cache = True


@compiles(coalesce)  # type: ignore
def compile_coalesce(element, compiler, **kw: Any) -> str:  # type: ignore[no-untyped-def] # pylint: disable=[unused-argument]
    return f"coalesce({compiler.process(element.clauses)})"


@compiles(coalesce, "oracle")  # type: ignore
def compile_nvl(element, compiler, **kw) -> str:  # type: ignore[no-untyped-def] # pylint: disable=[unused-argument]
    if len(element.clauses) > 2:
        raise TypeError("coalesce (nvl) only supports two arguments on Oracle")
    return f"nvl({compiler.process(element.clauses)})"


class BaseModel(DeclarativeBase):
    """
    Base for all SQLAlchemy declarative models.
    """

    registry = mapper_registry
    # required in order to access columns with server defaults
    # or SQL expression defaults, subsequent to a flush, without
    # triggering an expired load
    __mapper_args__ = {"eager_defaults": True}
    id: Mapped["UUID4"] = Column(  # type: ignore
        GUID,
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    id._creation_order = 1  # type: ignore[attr-defined] # pylint: disable=[protected-access]

    def from_dict(self, **kwargs: Any) -> "BaseModel":
        """Return ORM Object from Dictionary"""
        if self.__table__:
            for column in self.__table__.columns:
                if column.name in kwargs:
                    setattr(self, column.name, kwargs.get(column.name))
        return self

    def dict(self) -> dict[str, Any]:
        """Returns a dict representation of a model."""
        if self.__table__:
            return {field.name: getattr(self, field.name) for field in self.__table__.columns}
        return {}


@declarative_mixin
class IntegerPrimaryKeyMixin:
    """GUID Column Mixin"""

    id: Mapped["int"] = Column(BigInteger, Identity(always=True), primary_key=True, unique=True, nullable=False)
    id._creation_order = 1  # type: ignore[attr-defined] # pylint: disable=[protected-access]


@declarative_mixin
class SlugModelMixin:
    slug: Mapped["str"] = Column(String(length=100), index=True, nullable=False, unique=True)
    slug._creation_order = 2  # type: ignore[attr-defined] # pylint: disable=[protected-access]


@declarative_mixin
class SoftDeleteMixin:
    is_deleted: Mapped[bool] = Column(Boolean, index=True, nullable=False, default=False)
    is_deleted._creation_order = 999  # type: ignore[attr-defined] # pylint: disable=[protected-access]


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
    created_at._creation_order = 9998  # type: ignore[attr-defined] # pylint: disable=[protected-access]
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        server_default=None,
        comment="Date the record was last modified",
    )
    updated_at._creation_order = 9998  # type: ignore[attr-defined] # pylint: disable=[protected-access]


def _get_default_expires_at(timedelta_seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=timedelta_seconds)


@declarative_mixin
class ExpiresAtMixin:
    """Expires at mixin"""

    __lifetime_seconds__: int = 3600

    @declared_attr
    def expires_at(cls) -> Column[DateTime]:  # pylint: disable=[no-self-argument]
        return Column(
            DateTime(timezone=True),
            nullable=False,
            index=True,
            default=functools.partial(
                _get_default_expires_at,
                timedelta_seconds=cls.__lifetime_seconds__,
            ),
        )


def find_by_table_name(table_name: str) -> Optional["DatabaseModel"]:
    """Return model based on class"""
    for mapper in mapper_registry.mappers:
        model: DatabaseModel = mapper.class_  # type: ignore
        model_class_name = model.__tablename__
        if model_class_name == table_name:
            return model
    return None


DatabaseSession: TypeAlias = AsyncSession
DatabaseModel = TypeVar("DatabaseModel", bound=BaseModel)
DatabaseModelWithSlug = TypeVar("DatabaseModelWithSlug", bound=SlugModelMixin)
DatabaseModelWithIntegerPrimaryKey = TypeVar("DatabaseModelWithIntegerPrimaryKey", bound=IntegerPrimaryKeyMixin)
DatabaseModelWithCreatedUpdatedAt = TypeVar("DatabaseModelWithCreatedUpdatedAt", bound=CreatedUpdatedAtMixin)
DatabaseModelWithExpiresAt = TypeVar("DatabaseModelWithExpiresAt", bound=ExpiresAtMixin)
DatabaseModelWithSoftDelete = TypeVar("DatabaseModelWithSoftDelete", bound=SoftDeleteMixin)
