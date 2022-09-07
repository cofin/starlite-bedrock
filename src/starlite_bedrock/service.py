from collections import abc
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, ParamSpec, Type, TypeVar, Union

from pydantic import UUID4, parse_obj_as
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from starlite_bedrock import db, orm, repository, schema

P = ParamSpec("P")
T = TypeVar("T")
RepositoryType = TypeVar("RepositoryType", bound=repository.BaseRepository)  # pylint: disable=invalid-name
SchemaType = TypeVar("SchemaType", bound=schema.BaseSchema)  # pylint: disable=invalid-name
DataAccessServiceType = TypeVar("DataAccessServiceType", bound="DataAccessService")  # pylint: disable=invalid-name
CreateSchemaType = TypeVar("CreateSchemaType", bound=schema.BaseSchema)  # pylint: disable=invalid-name
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=schema.BaseSchema)  # pylint: disable=invalid-name


class TableSortOrder(str, Enum):
    ASCENDING = "asc"
    DESCENDING = "desc"


class TablePageSize(str, Enum):
    TEN = 10
    TWENTY_FIVE = 25
    FIFTY = 50


class DataAccessService(Generic[orm.DatabaseModelType, RepositoryType, SchemaType, CreateSchemaType, UpdateSchemaType]):
    """Base class for all Database CRUD operations.

    This class is used to provide a common interface for all CRUD operations.
    """

    model: type[orm.DatabaseModelType]
    repository_type: type[RepositoryType]
    """A [`repository.Base`][starlite_lib.repository.Base] concrete subclass."""
    schema_type: type[SchemaType]
    create_schema_type: Type[CreateSchemaType]
    update_schema_type: Type[UpdateSchemaType]

    """A [`schema.Base`][starlite_lib.schema.Base] concrete subclass."""
    exclude_keys = {"created_at", "updated_at"}

    def __init__(
        self,
        session: AsyncSession,
        *,
        default_options: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> None:
        self.session = session
        self.default_options = default_options or []
        self.repository = self.repository_type(session=session, default_options=default_options, **kwargs)
        self.paginated_schema_type = 

    async def get_by_id(
        self,
        id: Union[int, UUID4],  # pylint: disable=redefined-builtin
        options: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> Optional[SchemaType]:
        """
        Obtain model instance by `identifier`.

        Args:
            id: The identifier of the model instance.
            db: The database session.
        Returns:
            Returns `None` on unsuccessful search`.
        """
        options = options or self.default_options
        db_obj = await self.repository.get_by_id(id, options=options, **kwargs)
        if db_obj:
            return self.schema_type.from_orm(db_obj)
        return None

    async def get(
        self,
        *args: Any,
        options: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> Optional[SchemaType]:
        """
        Obtain a list of model instances

        List starts at offset `skip` and contains a
        maximum of `limit` number of elements.

        Args:
            skip: The offset of the list.
            limit: The maximum number of elements in the list.
            db: The database session.
        Returns:
            Returns a paginated response
        """
        options = options or self.default_options

        statement = (
            select(self.model)
            .filter(*args)
            .filter_by(**kwargs)
            .options(*options)
            .execution_options(populate_existing=True)
        )  # this is important!
        db_obj = await self.repository.get_one_or_none(statement)
        if db_obj:
            return self.schema_type.from_orm(db_obj)
        return None

    async def get_multi(
        self,
        *args: Any,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        sort_order: Optional[TableSortOrder] = TableSortOrder.DESCENDING,
        options: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> schema.PaginatedResults[SchemaType]:
        """
        Obtain a list of model instances

        List starts at offset `skip` and contains a
        maximum of `limit` number of elements.

        Args:
            skip: The offset of the list.
            limit: The maximum number of elements in the list.
            db: The database session.
        Returns:
            Returns a paginated response
        """
        options = options or self.default_options
        sort = sort_order.value if sort_order else TableSortOrder.DESCENDING.value
        order: Any = self.model.id  # default to PK
        if order_by:
            if getattr(self.model, order_by, None):
                order = getattr(self.model, sort, order)
        if sort_order == TableSortOrder.ASCENDING:
            order = order.asc()
        elif sort_order == TableSortOrder.DESCENDING:
            order = order.desc()
        statement = (
            select(self.model)
            .filter(*args)
            .filter_by(**kwargs)
            .offset(skip)
            .limit(limit)
            .order_by(order)
            .options(*options)
            .execution_options(populate_existing=True)
        )  # this is important!
        results, count = await self.repository.paginate(statement, limit, skip)
        
        return schema.PaginatedResults[self.schema_type].parse_obj(
            {"count": count, "limit": limit, "skip": skip, "results": results},
        )

    async def all(
        self,
        *args: Any,
        options: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> List[SchemaType]:
        """
        Obtain a list of model instances

        Returns all elements as a list.  No pagination

        Args:
            skip: The offset of the list.
            limit: The maximum number of elements in the list.
            db: The database session.
        Returns:
            Returns a paginated response
        """
        options = options or self.default_options

        statement = (
            select(self.model)
            .filter(*args)
            .filter_by(**kwargs)
            .options(*options)
            .execution_options(populate_existing=True)
        ) 
        results = await self.repository.list(statement)
        return parse_obj_as(List[self.schema_type], results)

    async def create(
        self,
        obj_in: CreateSchemaType,
    ) -> SchemaType:
        """Create an instance of the model and insert it into the database.

        Args:
            db: The database session.
            obj_in: The object to create.

        Returns:
            The created object.

        """
        obj_in_data = obj_in.dict(exclude_unset=True, by_alias=False)
        db_obj = self.model(**obj_in_data)
        await self.repository.create(db_obj)
        return self.schema_type.from_orm(db_obj)

    async def update(
        self,
        db_obj: orm.DatabaseModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]],
    ) -> SchemaType:
        """
        Update model instance `db_obj` with fields and values specified by `obj_in`.

        Args:
            db: The database session.
            db_obj: The object to update.
            obj_in: The object to update with.
        Returns:
            The updated object.

        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.dict(exclude_unset=True, by_alias=False)
        for field in db_obj.dict():
            if field in update_data:
                setattr(db_obj, field, update_data.get(field))
        await self.repository.update(db_obj)
        return self.schema_type.from_orm(db_obj)

    async def remove(
        self,
        id: Union[int, UUID4],
    ) -> Optional[SchemaType]:
        """Delete model instance by `identifier`.

        Args:
            db: The database session.
            id: The identifier of the model instance.
        Returns:
            The deleted object.
        """
        db_obj = await self.repository.get_by_id(id)
        if db_obj:
            await self.repository.delete(db_obj)
            return self.schema_type.from_orm(db_obj)
        return None
    
    @classmethod
    @asynccontextmanager
    async def with_session(cls: type[DataAccessServiceType], **kwargs: Any) -> abc.AsyncIterator[ServiceType]:
        async with db.async_session_factory() as session:
            async with session.begin():
                yield cls(session, **kwargs)

