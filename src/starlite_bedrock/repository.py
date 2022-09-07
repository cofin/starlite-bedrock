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
    DatabaseModel,
    DatabaseModelWithCreatedUpdatedAt,
    DatabaseModelWithExpiresAt,
    DatabaseModelWithSlug,
    DatabaseModelWithSoftDelete,
)
from starlite_bedrock.utils.async_tools import run_async
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


class SQLRepositoryBase(Protocol):
    """Basic repository interface for SQL."""

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


class BaseRepositoryProtocol(SQLRepositoryBase, Protocol[DatabaseModel]):
    """_summary_

    Args:
        Protocol (_type_): _description_
    """

    session: AsyncSession
    """
    Default database session to use for all operations.
    """
    model: Type[DatabaseModel]
    """
    A model that extends [`DeclarativeBase`][sqlalchemy.orm.DeclarativeBase]. Must be set by concrete subclasses.
    """
    default_options: Optional[Sequence[Any]] = None
    """
    Specify the default join options to use when querying the repository.
    """

    async def paginate(
        self,
        db: AsyncSession,
        statement: Select,
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[List[DatabaseModel], int]:
        ...  # pragma: no cover

    def order_by(self, db: AsyncSession, statement: Select, ordering: List[Tuple[List[str], bool]]) -> Select:
        ...  # pragma: no cover

    async def get_by_id(
        self, db: AsyncSession, id: Union[UUID4, int]  # pylint: disable=[redefined-builtin]
    ) -> Optional[DatabaseModel]:
        ...  # pragma: no cover

    async def get(
        self, db: AsyncSession, id: Union[UUID4, int]  # pylint: disable=[redefined-builtin]
    ) -> Optional[DatabaseModel]:
        ...  # pragma: no cover

    async def get_one_or_none(self, db: AsyncSession, statement: Select) -> Optional[DatabaseModel]:
        ...  # pragma: no cover

    async def list(self, db: AsyncSession, statement: Select) -> List[DatabaseModel]:
        ...  # pragma: no cover

    async def create(self, db: AsyncSession, db_object: DatabaseModel) -> DatabaseModel:
        ...  # pragma: no cover

    async def update(self, db: AsyncSession, db_object: DatabaseModel) -> None:
        ...  # pragma: no cover

    async def delete(self, db: AsyncSession, db_object: DatabaseModel) -> None:
        ...  # pragma: no cover

    def sql_join_options(self, options: Optional[Sequence[Any]] = None) -> Sequence[Any]:
        if options:
            return options
        if self.default_options:
            return self.default_options
        return []


class ExpiresAtRepositoryProtocol(BaseRepositoryProtocol, Protocol[DatabaseModelWithExpiresAt]):
    model: Type[DatabaseModelWithExpiresAt]

    async def delete_expired(self, db: AsyncSession) -> None:
        ...  # pragma: no cover


class CreatedUpdatedAtRepositoryProtocol(BaseRepositoryProtocol, Protocol[DatabaseModelWithCreatedUpdatedAt]):
    model: Type[DatabaseModelWithCreatedUpdatedAt]


class SlugRepositoryProtocol(BaseRepositoryProtocol, Protocol[DatabaseModelWithSlug]):
    model: Type[DatabaseModelWithSlug]

    async def get_by_slug(
        self,
        db: AsyncSession,
        slug: str,
    ) -> Optional[DatabaseModelWithSlug]:
        ...  # pragma: no cover


class SoftDeleteRepositoryProtocol(BaseRepositoryProtocol, Protocol[DatabaseModelWithSoftDelete]):
    model: Type[DatabaseModelWithSoftDelete]


class BaseRepository(BaseRepositoryProtocol, Generic[DatabaseModel]):
    """Base SQL Alchemy repository."""

    def __init__(
        self,
        session: AsyncSession,
        model: Type[DatabaseModel],
        default_options: Optional[list] = None,
    ) -> None:
        """
        CRUD object with default methods to create, read, update, delete (CRUD).

        # Parameters

        * `model`: A SQLAlchemy model class
        * `default_options`: Default options for SQL joins
        """
        self.session = session
        self.model = model
        self.default_options = default_options if default_options else []

    async def count(self, db: AsyncSession, statement: Select) -> int:
        count_statement = statement.with_only_columns(  # type: ignore[call-overload]
            [sql_func.count()],
            maintain_column_froms=True,
        ).order_by(None)
        results = await self.execute(db, count_statement)
        return results.scalar_one()  # type: ignore

    async def paginate(
        self, db: AsyncSession, statement: Select, limit: int = 10, offset: int = 0
    ) -> Tuple[List[DatabaseModel], int]:
        paginated_statement = statement.offset(offset).limit(limit)

        [count, results] = await asyncio.gather(
            self.count(db, statement),
            self.execute(
                db,
                paginated_statement,
            ),
        )

        return [result[0] for result in results.unique().all()], count

    def order_by(
        self,
        db: AsyncSession,
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
        self, db: AsyncSession, statement: Select, options: Optional[List[Any]] = None
    ) -> Optional[DatabaseModel]:
        statement.options(*self.sql_join_options(options)).execution_options(populate_existing=True)
        results = await self.execute(db, statement)
        db_object = results.first()
        if db_object is None:
            return None
        return cast("DatabaseModel", db_object[0])

    async def get_by_id(
        self,
        db: AsyncSession,
        id: Union[int, UUID4],  # pylint: disable=[redefined-builtin]
        options: Optional[list] = None,
    ) -> Optional[DatabaseModel]:
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

        return await self.get_one_or_none(db, statement)

    async def list(
        self,
        db: AsyncSession,
        statement: Optional[Select] = None,
        options: Optional[list] = None,
    ) -> List[DatabaseModel]:
        if statement is None:
            statement = (
                select(self.model).options(*self.sql_join_options(options)).execution_options(populate_existing=True)
            )
        results = await self.execute(db, statement)
        return [result[0] for result in results.unique().all()]

    async def create(
        self,
        db: AsyncSession,
        db_object: DatabaseModel,
        commit: bool = True,
    ) -> DatabaseModel:
        db.add(instance=db_object)
        if commit:
            await self.commit(db)
            await self.refresh(db, db_object)
        return db_object

    async def create_many(
        self,
        db: AsyncSession,
        db_objects: List[DatabaseModel],
        commit: bool = True,
    ) -> List[DatabaseModel]:
        """Create Many"""
        for db_object in db_objects:
            db.add(instance=db_object)
        if commit:
            await self.commit(db)
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

    async def update(self, data: abc.Mapping[str, Any]) -> DatabaseModel:
        """
        Update the model returned from `self.select` with key/val pairs from `data`.

        Parameters
        ----------
        data : Mapping[str, Any]
            Key/value pairs used to set attribute vals on result of `self.select`.

        Returns
        -------
        DatabaseModel
            The type returned by `self.select`

        Raises
        ------
        Base.not_found_error_type
            If `self.select` returns no rows.
        Base.base_error_type
            If `self.select` returns more than a single row.
        """
        model = await self.scalar()
        return await self.add(self.update_model(model, data))

    async def update(self, db: AsyncSession, db_object: DatabaseModel, commit: bool = True) -> None:
        db.add(instance=db_object)
        if commit:
            await self.commit(db)
            await self.refresh(db, db_object)

    async def delete(self, db: AsyncSession, db_object: DatabaseModel, commit: bool = False) -> None:
        await self.delete(db, db_object)
        if commit:
            await self.commit(db)

    async def refresh(self, db: AsyncSession, db_object: DatabaseModel) -> None:
        await db.refresh(db_object)

    async def commit(self, db: AsyncSession) -> None:
        await db.commit()

    @overload
    async def execute(self, db: AsyncSession, statement: TypedReturnsRows[TableRow], **kwargs: Any) -> Result[TableRow]:
        ...

    @overload
    async def execute(self, db: AsyncSession, statement: Executable, **kwargs: Any) -> Result[Any]:
        ...

    async def execute(self, db: AsyncSession, statement: Executable, **kwargs: Any) -> Result[Any]:
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
            return await db.execute(statement, **kwargs)


class SlugRepositoryMixin(SlugRepositoryProtocol, Generic[DatabaseModelWithSlug]):
    """Slug Repository Mixin."""

    async def get_by_slug(
        self,
        db: AsyncSession,
        slug: str,
        options: Optional[Sequence[Any]] = None,
    ) -> Optional[DatabaseModelWithSlug]:
        statement = (
            select(self.model)
            .where(self.model.slug == slug)
            .options(*self.sql_join_options(options=options))
            .execution_options(populate_existing=True)
        )

        return await self.get_one_or_none(db, statement)

    async def get_available_slug(
        self,
        value_to_slugify: str,
        db: AsyncSession,
    ) -> str:
        slug = slugify(value_to_slugify)
        if await self._is_slug_unique(slug, db):
            return slug
        random_string = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"{slug}-{random_string}"

    async def _is_slug_unique(
        self,
        slug: str,
        db: AsyncSession,
    ) -> bool:
        statement = select(self.model.slug).where(self.model.slug == slug)
        return await self.get_one_or_none(db, statement) is None


class ExpiresAtMixin(ExpiresAtRepositoryProtocol, Generic[DatabaseModelWithExpiresAt]):
    async def delete_expired(self, db: AsyncSession) -> None:
        statement = delete(self.model).where(self.model.expires_at < datetime.now(timezone.utc))
        await self._execute_statement(db, statement)


class SQLManager(SQLRepositoryBase):
    """Simple manager to handle one off sql statements."""

    async def query(
        self,
        db: AsyncSession,
        statement: Select,
    ) -> Sequence[RowMapping] | None:
        result = await self._execute_statement(db, statement)
        return result.mappings().all()

    async def query_one(
        self,
        db: AsyncSession,
        statement: Select,
    ) -> RowMapping | None:
        result = await self._execute_statement(db, statement)
        result_set = result.mappings().all()
        if result_set:
            return result_set[0]
        return None

    async def count(
        self,
        db: AsyncSession,
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
        results = await self._execute_statement(db, count_statement)
        return cast("int", results.scalar_one())

    async def _execute_statement(self, db: AsyncSession, statement: Select) -> Result:
        with self.catch_sqlalchemy_exception():
            if self._is_asyncio_session(db):
                return await db.execute(statement)  # type: ignore
            return await run_async(db.execute)(statement)  # type: ignore

    async def _execute_script(self, db: AsyncSession, statement: Executable) -> None:
        with self.catch_sqlalchemy_exception():
            if self._is_asyncio_session(db):
                return await db.execute(statement)  # type: ignore
            return await run_async(db.execute)(statement)  # type: ignore
