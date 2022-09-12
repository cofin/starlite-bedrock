# Standard Library
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)

from pydantic import parse_obj_as
from pydantic.generics import GenericModel
from sqlalchemy import select

from starlite_bedrock import orm, repository, schema

ModelType = TypeVar("ModelType", bound=orm.BaseModel)
RepositoryType = TypeVar("RepositoryType", bound=repository.BaseRepository)
CreateSchemaType = TypeVar("CreateSchemaType", bound=schema.BaseSchema)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=schema.BaseSchema)
SchemaType = TypeVar("SchemaType", bound=schema.BaseSchema)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TableSortOrder(str, Enum):
    ASCENDING = "asc"
    DESCENDING = "desc"


class TablePageSize(str, Enum):
    TEN = 10
    TWENTY_FIVE = 25
    FIFTY = 50


class TotaledResults(GenericModel, Generic[SchemaType]):
    """Provides count and result of result set"""

    count: int
    results: List[SchemaType]


class PaginatedResults(GenericModel, Generic[SchemaType]):
    """Provides count, result, and page information of result set"""

    count: int
    limit: int
    skip: int
    results: List[SchemaType]


class DataAccessService(Generic[ModelType, RepositoryType, SchemaType, CreateSchemaType, UpdateSchemaType]):
    """Base class for all Database CRUD operations.

    This class is used to provide a common interface for all CRUD operations.
    """

    def __init__(
        self,
        model: Type[ModelType],
        repository: Type[RepositoryType],
        response_model: Type[SchemaType],
        default_options: Optional[List[Any]] = None,
    ) -> None:
        """
        CRUD object with default methods to create, read, update, delete (CRUD).

        # Parameters

        * `model`: A SQLAlchemy model class
        * `schema`: A Pydantic model (schema) class
        """
        self.model = model
        self.repository = repository(model=model)
        self.response_model = response_model
        self.paginated_response_model = PaginatedResults[SchemaType]
        self.default_options = default_options if default_options else []

    async def get_by_id(self, db: "AsyncSession", id: int, options: Optional[List[Any]] = None) -> Optional[SchemaType]:
        """
        Obtain model instance by `identifier`.

        Args:
            id: The identifier of the model instance.
            db: The database session.
        Returns:
            Returns `None` on unsuccessful search`.
        """
        options = options if options else self.default_options
        db_obj = await self.repository.get_by_id(db, id, options)
        if db_obj:
            return self.response_model.from_orm(db_obj)
        return None

    async def get(
        self, db: "AsyncSession", *args: Any, options: Optional[List[Any]] = None, **kwargs: Any
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
        options = options if options else self.default_options
        statement = (
            select(self.model)
            .filter(*args)
            .filter_by(**kwargs)
            .options(*options)
            .execution_options(populate_existing=True)
        )  # this is important!
        db_obj = await self.repository.get_one_or_none(db, statement)
        if db_obj:
            return self.response_model.from_orm(db_obj)
        return None

    async def get_multi(
        self,
        db: "AsyncSession",
        *args: Any,
        skip: int = 0,
        limit: int = 100,
        options: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> PaginatedResults[SchemaType]:
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
        options = options if options else self.default_options

        sort = kwargs.pop("sort", None)
        order = kwargs.pop("order", None)
        sort_by = sort if sort else TableSortOrder.DESCENDING
        order_by = self.model.id  # default to PK
        if order and getattr(self.model, order, None):
            order_by = getattr(self.model, order, order_by)
        if sort_by == TableSortOrder.ASCENDING:
            order_by = order_by.asc()  # type: ignore[assignment]
        elif sort_by == TableSortOrder.DESCENDING:
            order_by = order_by.desc()  # type: ignore[assignment]
        statement = (
            select(self.model)
            .filter(*args)
            .filter_by(**kwargs)
            .offset(skip)
            .limit(limit)
            .order_by(order_by)
            .options(*options)
            .execution_options(populate_existing=True)
        )  # this is important!
        results, count = await self.repository.paginate(db, statement, limit, skip)
        return self.paginated_response_model.parse_obj(
            {"count": count, "limit": limit, "skip": skip, "results": results},
        )

    async def list(
        self, db: "AsyncSession", *args: Any, options: Optional[List[Any]] = None, **kwargs: Any
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
        options = options if options else self.default_options

        statement = (
            select(self.model)
            .filter(*args)
            .filter_by(**kwargs)
            .options(*options)
            .execution_options(populate_existing=True)
        )  # this is important!
        results = await self.repository.list(db, statement)
        return parse_obj_as(List[SchemaType], results)

    async def create(self, db: "AsyncSession", obj_in: CreateSchemaType) -> SchemaType:
        """Create an instance of the model and insert it into the database.

        Args:
            db: The database session.
            obj_in: The object to create.

        Returns:
            The created object.

        """
        obj_in_data = obj_in.dict(exclude_unset=True, by_alias=False, exclude_none=True)
        db_obj = self.model(**obj_in_data)
        await self.repository.create(db, db_obj)
        return self.response_model.from_orm(db_obj)

    async def update(
        self, db: "AsyncSession", db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]]
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
        await self.repository.update(db, db_obj)
        return self.response_model.from_orm(db_obj)

    async def remove(self, db: "AsyncSession", id: int) -> Optional[SchemaType]:
        """Delete model instance by `identifier`.

        Args:
            db: The database session.
            id: The identifier of the model instance.
        Returns:
            The deleted object.
        """
        db_obj = await self.repository.get_by_id(db, id)
        if db_obj:
            await self.repository.delete(db, db_obj)
            return self.response_model.from_orm(db_obj)
        return None
