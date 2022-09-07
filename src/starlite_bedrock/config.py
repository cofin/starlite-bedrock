"""
All configuration is via environment variables.

Take not of the environment variable prefixes required for each settings class, except
[`AppSettings`][starlite_lib.config.AppSettings].
"""
from typing import Literal

from pydantic import AnyUrl, PostgresDsn

from starlite_bedrock.schema import BaseSchema, BaseSettings


# noinspection PyUnresolvedReferences
class AppSettings(BaseSettings):
    """
    Generic application settings. These settings are returned as json by the healthcheck endpoint,
    so do not include any sensitive values here, or if you do ensure to exclude them from
    serialization in the `Config` object.

    Attributes
    ----------
    BUILD_NUMBER : str
        Identity of the CI build of current app instance.
    DEBUG : bool
        If `True` runs `Starlite` in debug mode.
    ENVIRONMENT : str
        "dev", "prod", etc.
    LOG_LEVEL : str
        Stdlib log level names, "DEBUG", "INFO", etc.
    NAME : str
        App name.
    """

    class Config:
        case_sensitive = True

    BUILD_NUMBER: str = "0.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    LOG_LEVEL: str = "INFO"
    NAME: str = "Application"

    @property
    def slug(self) -> str:
        """
        A slugified name.

        Returns
        -------
        str
            `self.NAME`, all lowercase and hyphens instead of spaces.
        """
        return "-".join(s.lower() for s in self.NAME.split())


# noinspection PyUnresolvedReferences
class APISettings(BaseSettings):
    """
    API specific configuration.

    Prefix all environment variables with `API_`, e.g., `API_CACHE_EXPIRATION`.

    Attributes
    ----------
    CACHE_EXPIRATION : int
        Default cache key expiration in seconds.
    DEFAULT_PAGINATION_LIMIT : int
        Max records received for collection routes.
    HEALTH_PATH : str
        Path to healthcheck endpoint.
    """

    class Config:
        env_prefix = "API_"
        case_sensitive = True

    CACHE_EXPIRATION: int = 60
    DEFAULT_PAGINATION_LIMIT: int = 25
    HEALTH_PATH: str = "/health"


# noinspection PyUnresolvedReferences
class OpenAPISettings(BaseSettings):
    """
    Configures OpenAPI for the application.

    Prefix all environment variables with `OPENAPI_`, e.g., `OPENAPI_TITLE`.

    Attributes
    ----------
    TITLE : str
        OpenAPI document title.
    VERSION : str
        OpenAPI document version.
    CONTACT_NAME : str
        OpenAPI document contact name.
    CONTACT_EMAIL : str
        OpenAPI document contact email.
    """

    class Config:
        env_prefix = "OPENAPI_"
        case_sensitive = True

    TITLE: str | None
    VERSION: str = "v1"
    CONTACT_NAME: str = "Admin"
    CONTACT_EMAIL: str = "admin@localhost"


# noinspection PyUnresolvedReferences
class DatabaseSettings(BaseSettings):
    """
    Configures the database for the application.

    Prefix all environment variables with `DB_`, e.g., `DB_URL`.

    Attributes
    ----------
    ECHO : bool
        Enables SQLAlchemy engine logs.
    URL : PostgresDsn
        URL for database connection.
    """

    class Config:
        env_prefix = "DB_"
        case_sensitive = True

    ECHO: bool = False
    ECHO_POOL: bool | Literal["debug"] = False
    POOL_DISABLE: bool = False
    POOL_MAX_OVERFLOW: int = 20
    POOL_SIZE: int = 10
    POOL_TIMEOUT: int = 30
    URL: PostgresDsn


# noinspection PyUnresolvedReferences
class CacheSettings(BaseSettings):
    """
    Cache settings for the application.

    Prefix all environment variables with `CACHE_`, e.g., `CACHE_URL`.

    Attributes
    ----------
    URL : AnyUrl
        A redis connection URL.
    """

    class Config:
        env_prefix = "CACHE_"
        case_sensitive = True

    URL: AnyUrl


class Settings(BaseSchema):
    """
    Cache settings for the application.

    Prefix all environment variables with `CACHE_`, e.g., `CACHE_URL`.

    Attributes
    ----------
    URL : AnyUrl
        A redis connection URL.
    """

    api: APISettings
    app: AppSettings
    cache: CacheSettings
    db: DatabaseSettings
    openapi: OpenAPISettings


api_settings = APISettings()
app_settings = AppSettings()
cache_settings = CacheSettings()
db_settings = DatabaseSettings()
openapi_settings = OpenAPISettings()
