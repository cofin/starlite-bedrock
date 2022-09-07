import asyncio
import random
import string
from collections import abc
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import (
    Any,
    Generic,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)
from uuid import UUID

from pydantic import UUID4
from sqlalchemy import Executable, RowMapping
from sqlalchemy.engine import Result
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, RelationshipProperty
from sqlalchemy.sql import Select, delete
from sqlalchemy.sql import func as sql_func
from sqlalchemy.sql import select
from sqlalchemy.sql.selectable import TypedReturnsRows

from starlite_bedrock.orm import (
    DatabaseModelType,
    DatabaseModelWithCreatedUpdatedAtType,
    DatabaseModelWithExpiresAtType,
    DatabaseModelWithSlugType,
    DatabaseModelWithSoftDeleteType,
)
from starlite_bedrock.utils.text_tools import slugify

__all__ = [
    "RepositoryNotFoundException",
    "RepositoryConflictException",
    "RepositoryException",
    "ParamType",
    "Repository",
    "BaseRepository",
    "SlugRepositoryMixin",
]

T = TypeVar("T")
ParamType = TypeVar("ParamType", bound=float | str | UUID | datetime | int)  # pylint: disable=[invalid-name]
Repository = TypeVar("Repository", bound="BaseRepository")  # pylint: disable=[invalid-name]
TableRow = TypeVar("TableRow", bound=tuple[Any, ...])


class RepositoryException(Exception):
    """
    Base repository exception type.
    """


class RepositoryConflictException(RepositoryException):
    """
    Wraps integrity error from database layer.
    """


class RepositoryNotFoundException(RepositoryException):
    """
    Raised when a method referencing a specific instance by identity is called and no instance with
    that identity exists.
    """


class SQLAlchemyRepositoryBase(Protocol):
    """Basic repository interface for SQL."""

    session: AsyncSession
    """
    Default database session to use for all operations.
    """
    base_error_type: type[Exception] = RepositoryException
    """
    Exception type raised when there is not a more specific error to throw.
    """
    integrity_error_type: type[Exception] = RepositoryConflictException
    """
    Exception type raised when a database layer integrity error is caught.
    """
    not_found_error_type: type[Exception] = RepositoryNotFoundException
    """
    Exception type raised on access to `scalar()`, `update()` and `delete()`
     methods when the select query returns no rows.
    Default `RepositoryNotFoundException`.
    """

    @overload
    async def execute(self, statement: TypedReturnsRows[TableRow], **kwargs: Any) -> Result[TableRow]:
        ...

    @overload
    async def execute(self, statement: Executable, **kwargs: Any) -> Result[Any]:
        ...

    async def execute(self, statement: Executable, **kwargs: Any) -> Result[Any]:
        ...  # pragma: no cover

    async def commit(self) -> None:
        with self.catch_sqlalchemy_exception():
            await self.session.commit()

    @contextmanager
    def catch_sqlalchemy_exception(self) -> Any:
        """
        Context manager that raises a custom exception chained from an original
        [`SQLAlchemyError`][sqlalchemy.exc.SQLAlchemyError].

        If [`IntegrityError`][sqlalchemy.exc.IntegrityError] is raised, we raise
        [`Base.integrity_error_type`][starlite_bedrock.repository.Base.integrity_error_type].

        Any other [`SQLAlchemyError`][sqlalchemy.exc.SQLAlchemyError] is wrapped in
        [`Base.base_error_type`][starlite_bedrock.repository.Base.base_error_type].
        """
        try:
            yield
        except IntegrityError as e:
            raise self.integrity_error_type from e
        except SQLAlchemyError as e:
            raise self.base_error_type(f"An exception occurred: {e}") from e

    @staticmethod
    def _is_asyncio_session(db: AsyncSession) -> bool:
        return isinstance(db, AsyncSession)


class BaseRepositoryProtocol(SQLAlchemyRepositoryBase, Protocol[DatabaseModelType]):
    """_summary_

    Args:
        Protocol (_type_): _description_
    """

    model: Type[DatabaseModelType]
    """
    A model that extends [`DeclarativeBase`][sqlalchemy.orm.DeclarativeBase]. Must be set by concrete subclasses.
    """
    default_options: Optional[Sequence[Any]] = None
    """
    Specify the default join options to use when querying the repository.
    """

    async def paginate(
        self, statement: Select, limit: int = 10, offset: int = 0
    ) -> Tuple[List[DatabaseModelType], int]:
        ...  # pragma: no cover

    def order_by(self, statement: Select, ordering: List[Tuple[List[str], bool]]) -> Select:
        ...  # pragma: no cover

    async def get_by_id(
        self, id: Union[UUID4, int]
    ) -> Optional[DatabaseModelType]:  # pylint: disable=[redefined-builtin]
        ...  # pragma: no cover

    async def get(self, id: Union[UUID4, int]) -> Optional[DatabaseModelType]:  # pylint: disable=[redefined-builtin]
        ...  # pragma: no cover

    async def get_one_or_none(self, statement: Select) -> Optional[DatabaseModelType]:
        ...  # pragma: no cover

    async def list(self, statement: Select) -> List[DatabaseModelType]:
        ...  # pragma: no cover

    async def create(self, db_object: DatabaseModelType) -> DatabaseModelType:
        ...  # pragma: no cover

    async def update(self, db_object: DatabaseModelType) -> None:
        ...  # pragma: no cover

    async def delete(self, db_object: DatabaseModelType) -> None:
        ...  # pragma: no cover

    def sql_join_options(self, options: Optional[Sequence[Any]] = None) -> Sequence[Any]:
        if options:
            return options
        if self.default_options:
            return self.default_options
        return []


class ExpiresAtRepositoryProtocol(BaseRepositoryProtocol, Protocol[DatabaseModelWithExpiresAtType]):
    model: Type[DatabaseModelWithExpiresAtType]

    async def delete_expired(self, db: AsyncSession) -> None:
        ...  # pragma: no cover


class CreatedUpdatedAtRepositoryProtocol(BaseRepositoryProtocol, Protocol[DatabaseModelWithCreatedUpdatedAtType]):
    model: Type[DatabaseModelWithCreatedUpdatedAtType]


class SlugRepositoryProtocol(BaseRepositoryProtocol, Protocol[DatabaseModelWithSlugType]):
    model: Type[DatabaseModelWithSlugType]

    async def get_by_slug(
        self,
        slug: str,
    ) -> Optional[DatabaseModelWithSlugType]:
        ...  # pragma: no cover


class SoftDeleteRepositoryProtocol(BaseRepositoryProtocol, Protocol[DatabaseModelWithSoftDeleteType]):
    model: Type[DatabaseModelWithSoftDeleteType]


class BaseRepository(BaseRepositoryProtocol, Generic[DatabaseModelType]):
    """Base SQL Alchemy repository."""

    def __init__(
        self,
        session: AsyncSession,
        model: Type[DatabaseModelType],
        default_options: Optional[list] = None,
    ) -> None:
        """
        CRUD object with default methods to create, read, update, delete (CRUD).

        # Parameters
        * `session`: A default session object to use
        * `model`: A SQLAlchemy model class
        * `default_options`: Default options for SQL joins
        """
        self.session = session
        self.model = model
        self.default_options = default_options if default_options else []

    async def count(self, statement: Select) -> int:
        count_statement = statement.with_only_columns(  # type: ignore[call-overload]
            [sql_func.count()],
            maintain_column_froms=True,
        ).order_by(None)
        results = await self.execute(count_statement)
        return results.scalar_one()  # type: ignore

    async def paginate(
        self, statement: Select, limit: int = 10, offset: int = 0
    ) -> Tuple[List[DatabaseModelType], int]:
        paginated_statement = statement.offset(offset).limit(limit)

        [count, results] = await asyncio.gather(self.count(statement), self.execute(paginated_statement))

        return [result[0] for result in results.unique().all()], count

    def order_by(
        self,
        statement: Select,
        ordering: List[Tuple[List[str], bool]],
    ) -> Select:
        for (accessors, is_desc) in ordering:
            field: InstrumentedAttribute
            # Local field
            if len(accessors) == 1:
                try:
                    field = getattr(self.model, accessors[0])
                    statement = statement.order_by(field.desc() if is_desc else field.asc())
                except AttributeError:
                    pass
            # Relationship field
            else:
                valid_field = True
                model = self.model
                for accessor in accessors:
                    try:
                        field = getattr(model, accessor)
                        if isinstance(field.prop, RelationshipProperty):
                            if field.prop.lazy != "joined":
                                statement = statement.join(field)
                            model = field.prop.entity.class_
                    except AttributeError:
                        valid_field = False
                        break
                if valid_field:
                    statement = statement.order_by(field.desc() if is_desc else field.asc())
        return statement

    async def get_one_or_none(
        self, statement: Select, options: Optional[List[Any]] = None
    ) -> Optional[DatabaseModelType]:
        statement.options(*self.sql_join_options(options)).execution_options(populate_existing=True)
        results = await self.execute(statement)
        db_object = results.first()
        if db_object is None:
            return None
        return cast("DatabaseModelType", db_object[0])

    async def get_by_id(
        self,
        id: Union[int, UUID4],  # pylint: disable=[redefined-builtin]
        options: Optional[list] = None,
    ) -> Optional[DatabaseModelType]:
        """_summary_

        Args:
            id (Union[int, UUID4]): _description_
            db (AsyncSession, optional): _description_. Defaults to AsyncSession().
            options (Optional[list], optional): _description_. Defaults to None.

        Returns:
            Optional[DatabaseModel]: _description_
        """
        statement = (
            select(self.model)
            .where(self.model.id == id)
            .options(*self.sql_join_options(options))
            .execution_options(populate_existing=True)
        )

        return await self.get_one_or_none(statement)

    async def list(self, statement: Optional[Select] = None, options: Optional[list] = None) -> List[DatabaseModelType]:
        if statement is None:
            statement = (
                select(self.model).options(*self.sql_join_options(options)).execution_options(populate_existing=True)
            )
        results = await self.execute(statement)
        return [result[0] for result in results.unique().all()]

    async def create(
        self,
        db_object: DatabaseModelType,
        commit: bool = True,
    ) -> DatabaseModelType:
        self.session.add(instance=db_object)
        if commit:
            await self.commit()
            await self.refresh(db_object)
        return db_object

    async def create_many(
        self,
        db_objects: List[DatabaseModelType],
        commit: bool = True,
    ) -> List[DatabaseModelType]:
        """Create Many"""
        for db_object in db_objects:
            self.session.add(instance=db_object)
        if commit:
            await self.commit()
        return db_objects

    @staticmethod
    def update_model(model: T, data: abc.Mapping[str, Any]) -> T:
        """
        Simple helper for setting key/values from `data` as attributes on `model`.

        Parameters
        ----------
        model : T
            Model instance to be updated.
        data : Mapping[str, Any]
            Mapping of data to set as key/value pairs on `model`.

        Returns
        -------
        T
            Key/value pairs from `data` have been set on the model.
        """
        for k, v in data.items():
            setattr(model, k, v)
        return model

    async def update(self, db_object: DatabaseModelType, commit: bool = True) -> None:
        self.session.add(instance=db_object)
        if commit:
            await self.commit()
            await self.refresh(db_object)

    async def delete(self, db_object: DatabaseModelType, commit: bool = True) -> None:
        with self.catch_sqlalchemy_exception():
            await self.session.delete(db_object)
            if commit:
                await self.commit()

    async def refresh(self, db_object: DatabaseModelType) -> None:
        with self.catch_sqlalchemy_exception():
            await self.session.refresh(db_object)

    async def execute(self, statement: Executable, **kwargs: Any) -> Result[Any]:
        """
        Execute `statement` with [`self.session`][starlite_lib.repository.Base.session].

        Parameters
        ----------
        statement : Executable
            Any SQLAlchemy executable type.
        **kwargs : Any
            Passed as kwargs to [`self.session.execute()`][sqlalchemy.ext.asyncio.AsyncSession.execute]

        Returns
        -------
        Result
            A set of database results.
        """
        with self.catch_sqlalchemy_exception():
            return await self.session.execute(statement, **kwargs)


class SlugRepositoryMixin(SlugRepositoryProtocol, Generic[DatabaseModelWithSlugType]):
    """Slug Repository Mixin."""

    async def get_by_slug(
        self,
        slug: str,
        options: Optional[Sequence[Any]] = None,
    ) -> Optional[DatabaseModelWithSlugType]:
        statement = (
            select(self.model)
            .where(self.model.slug == slug)
            .options(*self.sql_join_options(options=options))
            .execution_options(populate_existing=True)
        )

        return await self.get_one_or_none(statement)

    async def get_available_slug(
        self,
        value_to_slugify: str,
    ) -> str:
        slug = slugify(value_to_slugify)
        if await self._is_slug_unique(slug):
            return slug
        random_string = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"{slug}-{random_string}"

    async def _is_slug_unique(
        self,
        slug: str,
    ) -> bool:
        statement = select(self.model.slug).where(self.model.slug == slug)
        return await self.get_one_or_none(statement) is None


class ExpiresAtMixin(ExpiresAtRepositoryProtocol, Generic[DatabaseModelWithExpiresAtType]):
    async def delete_expired(self, db: AsyncSession) -> None:
        statement = delete(self.model).where(self.model.expires_at < datetime.now(timezone.utc))
        await self.execute(statement)


class SQLManager(SQLAlchemyRepositoryBase):
    """Simple manager to handle one off sql statements."""

    async def query(
        self,
        statement: Select,
    ) -> Sequence[RowMapping] | None:
        result = await self.execute(statement)
        return result.mappings().all()

    async def query_one(
        self,
        statement: Select,
    ) -> RowMapping | None:
        result = await self.execute(statement)
        result_set = result.mappings().all()
        if result_set:
            return result_set[0]
        return None

    async def count(
        self,
        statement: Select,
    ) -> int:
        """Counts the records in a query.

        Args:
            statement (Select): _description_
            db (AsyncSession): _description_

        Returns:
            int: _description_
        """
        count_statement = statement.with_only_columns(  # type: ignore[call-overload]
            [sql_func.count()],
            maintain_column_froms=True,
        ).order_by(None)
        results = await self.execute(count_statement)
        return cast("int", results.scalar_one())

    async def execute(self, statement: Executable, **kwargs: Any) -> Result[Any]:
        with self.catch_sqlalchemy_exception():
            return await self.session.execute(statement)
