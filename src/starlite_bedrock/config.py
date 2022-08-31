"""
All configuration is via environment variables.

Take not of the environment variable prefixes required for each settings class, except
[`AppSettings`][starlite.contrib.bedrock.config.AppSettings].
"""
import os
import pkgutil
from functools import lru_cache
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Literal

from pydantic import AnyUrl, PostgresDsn

from starlite_bedrock.schema import BaseSettings

APP_PREFIX: str = os.environ.get("APP_PREFIX", "")
"""Application prefix is blank by default"""


@lru_cache()
def dotted_path(dotted_path: str = "starlite_bedrock") -> Path:
    """
    Returns the path to the base directory of the project.

    Ensures that pkgutil returns a valid source file loader.
    """
    src = pkgutil.get_loader(dotted_path)
    if not isinstance(src, SourceFileLoader):
        raise ValueError(f"Couldn't find the path for {dotted_path}")
    return Path(str(src.path).removesuffix("/__init__.py"))


class AppSettings(BaseSettings):
    """
    Generic application settings.

    These settings are returned as json by the healthcheck endpoint,
    so do not include any sensitive values here,
    or if you do ensure to exclude them from
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

    BUILD_NUMBER: str
    DEBUG: bool
    ENVIRONMENT: str
    LOG_LEVEL: str = "INFO"
    NAME: str

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
    """

    class Config:
        env_prefix = f"{APP_PREFIX}API_"

    TCP_PORT: int = 8080
    BIND_HOST: str = "0.0.0.0"
    HTTP_WORKERS: int = 1
    BACKGROUND_WORKERS: int = 1
    CACHE_EXPIRATION: int
    DEFAULT_PAGINATION_LIMIT: int
    HEALTH_PATH: str


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
        env_prefix = f"{APP_PREFIX}OPENAPI_"

    TITLE: str | None
    VERSION: str
    CONTACT_NAME: str
    CONTACT_EMAIL: str
    TERMS_OF_SERVICE: str | None


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
        env_prefix = f"{APP_PREFIX}DB_"

    ENGINE: Literal["postgres", "sqlite", "oracle"] = "postgres"
    CONNECT_ARGS: dict = {}
    MIN_POOL_SIZE: int = 4
    MAX_POOL_SIZE: int = 15
    ECHO: bool = False
    ECHO_POOL: bool | Literal["debug"] = False
    URL: PostgresDsn
    MIGRATION_CONFIG: str = str(Path(dotted_path("starlite_bedrock") / "alembic.ini"))
    MIGRATION_PATH: str = str(Path(dotted_path("starlite_bedrock") / "migrations"))


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
        env_prefix = f"{APP_PREFIX}CACHE_"
        case_sensitive = True

    URL: AnyUrl


class SentrySettings(BaseSettings):
    """
    Configures sentry for the application.

    Attributes
    ----------
    DSN : str
        The sentry DSN. Set as empty string to disable sentry reporting.
    TRACES_SAMPLE_RATE : float
        % of requests traced by sentry, `0.0` means none, `1.0` means all.
    """

    class Config:
        env_prefix = f"{APP_PREFIX}SENTRY_"
        case_sensitive = True

    DSN: str
    TRACES_SAMPLE_RATE: float = 0.0001


class UvicornSettings(BaseSettings):
    """Uvicorn Specific Configuration"""

    class Config:
        env_prefix = f"{APP_PREFIX}UVICORN_"

    ASGI_APP: str = "examples.basic_example:app"
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    WORKERS: int = 1
    RELOAD: bool = False
    LOG_LEVEL: str = "error"


class GunicornSettings(BaseSettings):
    """Gunicorn settings"""

    class Config:
        env_prefix = f"{APP_PREFIX}GUNICORN_"

    ACCESS_LOG: str = "-"
    ERROR_LOG: str = "-"
    HOST: str = "0.0.0.0"
    KEEPALIVE: int = 120
    LOG_LEVEL: str = "ERROR"
    PORT: int = 8080
    RELOAD: bool = False
    THREADS: int
    TIMEOUT: int = 0
    WORKERS: int = 1
    WORKER_CLASS: str = "starlite_bedrock.run.UvicornWorker"
    PRELOAD: bool = True


api_settings = APISettings()
app_settings = AppSettings()
cache_settings = CacheSettings()
db_settings = DatabaseSettings()
openapi_settings = OpenAPISettings()
gunicorn_settings = GunicornSettings()
uvicorn_settings = UvicornSettings()
