import asyncio
from typing import Dict, List, Optional, Union

import starlite
from pydantic_openapi_schema.v3_1_0 import SecurityRequirement
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR
from starlite.utils import AsyncCallable

from starlite_bedrock.client import HttpClient
from starlite_bedrock.db import engine
from starlite_bedrock.redis import redis
from starlite_bedrock.starlite import (
    cache,
    compression,
    health,
    hooks,
    logging,
    openapi,
    response,
)
from starlite_bedrock.starlite.dependencies import filters
from starlite_bedrock.starlite.exceptions import logging_exception_handler
from starlite_bedrock.worker import Worker, WorkerFunction, queue


class Starlite(starlite.Starlite):
    """
    Wrapper around [`starlite.Starlite`][starlite.app.Starlite] that abstracts boilerplate, with
    the following differences:

    - `compression_config` and `openapi_config` are omitted as parameters and set internally
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
        route_handlers: List[starlite.types.ControllerRouterHandler],
        *,
        after_exception: Optional[starlite.types.SingleOrList[starlite.types.AfterExceptionHookHandler]] = None,
        after_request: Optional[starlite.types.AfterRequestHookHandler] = None,
        after_response: Optional[starlite.types.AfterResponseHookHandler] = None,
        after_shutdown: Optional[starlite.types.SingleOrList[starlite.types.LifeSpanHookHandler]] = None,
        after_startup: Optional[starlite.types.SingleOrList[starlite.types.LifeSpanHookHandler]] = None,
        allowed_hosts: Optional[List[str]] = None,
        before_request: Optional[starlite.types.BeforeRequestHookHandler] = None,
        before_send: Optional[starlite.types.SingleOrList[starlite.types.BeforeMessageSendHookHandler]] = None,
        before_shutdown: Optional[starlite.types.SingleOrList[starlite.types.LifeSpanHookHandler]] = None,
        before_startup: Optional[starlite.types.SingleOrList[starlite.types.LifeSpanHookHandler]] = None,
        cache_config: Optional[starlite.config.CacheConfig] = None,
        cors_config: Optional[starlite.config.CORSConfig] = None,
        csrf_config: Optional[starlite.config.CSRFConfig] = None,
        debug: bool = False,
        dependencies: Optional[Dict[str, starlite.Provide]] = None,
        exception_handlers: Optional[starlite.types.ExceptionHandlersMap] = None,
        guards: Optional[List[starlite.types.Guard]] = None,
        middleware: Optional[List[starlite.types.Middleware]] = None,
        on_shutdown: Optional[List[starlite.types.LifeSpanHandler]] = None,
        on_startup: Optional[List[starlite.types.LifeSpanHandler]] = None,
        parameters: Optional[starlite.types.ParametersMap] = None,
        plugins: Optional[List[starlite.plugins.PluginProtocol]] = None,
        response_cookies: Optional[starlite.types.ResponseCookies] = None,
        response_headers: Optional[starlite.types.ResponseHeadersMap] = None,
        security: Optional[List[SecurityRequirement]] = None,
        static_files_config: Optional[
            Union[starlite.config.StaticFilesConfig, List[starlite.config.StaticFilesConfig]]
        ] = None,
        tags: Optional[List[str]] = None,
        template_config: Optional[starlite.config.TemplateConfig] = None,
        worker_functions: list[WorkerFunction | tuple[str, WorkerFunction]] | None = None,
    ) -> None:
        if after_request is not None:
            async_after_request = AsyncCallable(after_request)  # type:ignore[arg-type]

            async def _after_request(response: starlite.Response) -> starlite.Response:
                try:
                    response = await hooks.session_after_request(response)
                finally:
                    response = await async_after_request(response)  # type:ignore[assignment]
                return response

        else:
            _after_request = hooks.session_after_request  # pylint: disable=[invalid-name]

        dependencies = dependencies or {}
        dependencies.setdefault("filters", starlite.Provide(filters))
        cache_config = cache_config or cache.config
        exception_handlers = exception_handlers or {}
        exception_handlers.setdefault(HTTP_500_INTERNAL_SERVER_ERROR, logging_exception_handler)
        after_exception = after_exception or []

        middleware = middleware or []

        on_shutdown = on_shutdown or []
        on_shutdown.extend([HttpClient.close, engine.dispose, redis.close])

        on_startup = on_startup or []
        on_startup.extend([logging.log_config.configure])

        worker_functions = worker_functions or []
        # only instantiate the worker if necessary
        if worker_functions:
            worker = Worker(queue, worker_functions or [])

            async def worker_on_app_startup() -> None:
                loop = asyncio.get_running_loop()
                loop.create_task(worker.start())

            on_shutdown.append(worker.stop)
            on_startup.append(worker_on_app_startup)

        route_handlers.append(health.health_check)

        super().__init__(
            after_request=_after_request,
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
            openapi_config=openapi.config,
            parameters=parameters,
            plugins=plugins,
            response_class=response.Response,
            response_cookies=response_cookies,
            response_headers=response_headers,
            route_handlers=route_handlers,
            static_files_config=static_files_config,
            security=security,
            template_config=template_config,
            tags=tags,
        )
