import asyncio
from typing import TYPE_CHECKING, Optional, Union

import sqlalchemy as sa
import starlite
from redis.asyncio import Redis
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR
from starlite.plugins.sql_alchemy import SQLAlchemyPlugin
from starlite.types import ResponseType

from starlite_bedrock.client import HttpClient
from starlite_bedrock.starlite import cache, compression, logging, openapi, response
from starlite_bedrock.starlite.exceptions import logging_exception_handler
from starlite_bedrock.worker import Worker, WorkerFunction, queue

if TYPE_CHECKING:
    from pydantic_openapi_schema.v3_1_0 import SecurityRequirement


class Starlite(starlite.Starlite):
    """
    Wrapper around [`starlite.Starlite`][starlite.app.Starlite] that abstracts boilerplate, with
    the following differences:

    - `compression_config`, `cache_config, and `openapi_config` are omitted as parameters and set internally
    - Adds an after-request handler that commits or rolls back the db session based on HTTP status
    code of response.
    - Provides the standard collection route filter dependencies.
    - Adds `handler_functions` param and registers them on an SAQ `Worker` instance.
    - Registers shutdown handlers for the worker, http client, database and redis.
    - Registers startup handlers for logging, sentry and the worker.
    - Adds a health check route handler that serves on `/health` by default and returns json
    representation of app settings.
    """

    def __init__(
        self,
        route_handlers: list[starlite.types.ControllerRouterHandler],
        *,
        after_exception: Optional[starlite.types.SingleOrList[starlite.types.AfterExceptionHookHandler]] = None,
        after_request: Optional[starlite.types.AfterRequestHookHandler] = None,
        after_response: Optional[starlite.types.AfterResponseHookHandler] = None,
        after_shutdown: Optional[starlite.types.SingleOrList[starlite.types.LifeSpanHookHandler]] = None,
        after_startup: Optional[starlite.types.SingleOrList[starlite.types.LifeSpanHookHandler]] = None,
        allowed_hosts: Optional[list[str]] = None,
        before_request: Optional[starlite.types.BeforeRequestHookHandler] = None,
        before_send: Optional[starlite.types.SingleOrList[starlite.types.BeforeMessageSendHookHandler]] = None,
        before_shutdown: Optional[starlite.types.SingleOrList[starlite.types.LifeSpanHookHandler]] = None,
        before_startup: Optional[starlite.types.SingleOrList[starlite.types.LifeSpanHookHandler]] = None,
        cache_config: Optional[starlite.config.CacheConfig] = None,
        cors_config: Optional[starlite.config.CORSConfig] = None,
        csrf_config: Optional[starlite.config.CSRFConfig] = None,
        debug: bool = False,
        dependencies: Optional[dict[str, starlite.Provide]] = None,
        exception_handlers: Optional[starlite.types.ExceptionHandlersMap] = None,
        guards: Optional[list[starlite.types.Guard]] = None,
        openapi_config: Optional[starlite.OpenAPIConfig] = None,
        middleware: Optional[list[starlite.types.Middleware]] = None,
        on_shutdown: Optional[list[starlite.types.LifeSpanHandler]] = None,
        on_startup: Optional[list[starlite.types.LifeSpanHandler]] = None,
        parameters: Optional[starlite.types.ParametersMap] = None,
        plugins: Optional[list[starlite.plugins.PluginProtocol]] = None,
        response_class: Optional[ResponseType] = None,
        response_cookies: Optional[starlite.types.ResponseCookies] = None,
        response_headers: Optional[starlite.types.ResponseHeadersMap] = None,
        security: Optional[list["SecurityRequirement"]] = None,
        static_files_config: Optional[
            Union[
                starlite.config.StaticFilesConfig,
                list[starlite.config.StaticFilesConfig],
            ]
        ] = None,
        tags: Optional[list[str]] = None,
        template_config: Optional[starlite.config.TemplateConfig] = None,
        log_config: Optional[starlite.logging.LoggingConfig] = None,
        db: Optional[sa.Engine] = None,
        worker_functions: list[WorkerFunction | tuple[str, WorkerFunction]] | None = None,
    ) -> None:
        log_config = log_config or logging.log_config
        dependencies = dependencies or {}
        exception_handlers = exception_handlers or {}
        exception_handlers.setdefault(HTTP_500_INTERNAL_SERVER_ERROR, logging_exception_handler)
        after_exception = after_exception or []
        openapi_config = openapi_config or openapi.config
        middleware = middleware or []
        plugins = plugins or []
        response_class = response_class or response.Response

        on_shutdown = on_shutdown or []
        on_shutdown.extend([HttpClient.close])
        if db:
            on_shutdown.extend([db.dispose])
            plugins.extend([SQLAlchemyPlugin()])
        if cache_config and isinstance(cache_config.backend, Redis):
            on_shutdown.extend([cache_config.backend.close])

        on_startup = on_startup or []
        on_startup.extend([log_config.configure])

        # custom attributes

        worker_functions = worker_functions or []
        # only instantiate the worker if necessary
        if worker_functions:
            if cache_config and not isinstance(cache_config.backend, Redis):
                raise ValueError("background functions require the use of a redis cache backend")
            worker = Worker(queue, worker_functions or [])

            async def worker_on_app_startup() -> None:
                loop = asyncio.get_running_loop()
                loop.create_task(worker.start())

            on_shutdown.append(worker.stop)
            on_startup.append(worker_on_app_startup)

        super().__init__(
            after_request=after_request,
            after_response=after_response,
            allowed_hosts=allowed_hosts,
            before_request=before_request,
            compression_config=compression.config,
            cache_config=cache.config,
            cors_config=cors_config,
            csrf_config=csrf_config,
            before_send=before_send,
            dependencies=dependencies,
            exception_handlers=exception_handlers,
            after_exception=after_exception,
            debug=debug,
            guards=guards,
            middleware=middleware,
            before_shutdown=before_shutdown,
            on_shutdown=on_shutdown,
            after_shutdown=after_shutdown,
            before_startup=before_startup,
            on_startup=on_startup,
            after_startup=after_startup,
            openapi_config=openapi_config,
            parameters=parameters,
            plugins=plugins,
            response_class=response_class,
            response_cookies=response_cookies,
            response_headers=response_headers,
            route_handlers=route_handlers,
            static_files_config=static_files_config,
            security=security,
            template_config=template_config,
            tags=tags,
        )
