# -*- coding: utf-8 -*-
"""Application Web Server Gateway Interface - gunicorn."""
import asyncio
import os
import pkgutil
import signal
import sys
import threading
import time
from typing import Any, Dict, cast

from gunicorn.app.base import Application
from gunicorn.arbiter import Arbiter
from starlite.utils.module_loading import import_string
from uvicorn.main import Server
from uvicorn.workers import UvicornWorker as _UvicornWorker

from starlite_bedrock.config import app_settings, uvicorn_settings
from starlite_bedrock.starlite import Starlite


def get_app(import_path: str) -> "Starlite":
    return cast(Starlite, import_string(import_path))


def run_asgi(
    host: str,
    port: int,
    http_workers: int,
    reload: bool,
) -> None:
    import uvicorn  # pylint: disable=[import-outside-toplevel]

    uvicorn.run(
        uvicorn_settings.ASGI_APP,
        host=host,
        port=port,
        log_level=uvicorn_settings.LOG_LEVEL,
        reload=reload,
        lifespan="auto",
        access_log=True,
        workers=http_workers,
    )


class ReloaderThread(threading.Thread):
    """_summary_

    Args:
        threading (_type_): _description_
    """

    def __init__(self, worker: "UvicornWorker", sleep_interval: float = 1.0):
        super().__init__()
        self.daemon = True
        self._worker = worker
        self._interval = sleep_interval

    def run(self) -> None:
        """
        Sends a KILL signal to the current process if the worker's active flag is set to
        False.
        """
        while True:
            if not self._worker.alive:
                os.kill(os.getpid(), signal.SIGINT)
            time.sleep(self._interval)


class UvicornWorker(_UvicornWorker):  # type: ignore
    """Uvicorn Worker

    Extends built in Gunicorn worker for Uvicorn to integrate better signal handling
    Args:
        _UvicornWorker (_type_): _description_
    """

    CONFIG_KWARGS = {"loop": "uvloop", "http": "httptools", "lifespan": "auto"}

    def __init__(self, *args: list[Any], **kwargs: dict[str, Any]):
        super().__init__(*args, **kwargs)
        self._reloader_thread = ReloaderThread(self)

    def run(self) -> None:
        if self.cfg.reload:
            self._reloader_thread.start()
        super().run()

    def _install_sigquit_handler(self, _: Server) -> None:
        """Workaround to install a SIGQUIT handler on workers.
        Ref.:
        - https://github.com/encode/uvicorn/issues/1116
        - https://github.com/benoitc/gunicorn/issues/2604
        """
        if threading.current_thread() is not threading.main_thread():
            # Signals can only be listened to from the main thread.
            return

        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGQUIT, self.handle_exit, signal.SIGQUIT, None)

    async def _serve(self) -> None:
        self.config.app = self.wsgi
        server = Server(config=self.config)
        self._install_sigquit_handler(server)
        await server.serve(sockets=self.sockets)
        if not server.started:
            sys.exit(Arbiter.WORKER_BOOT_ERROR)


class ApplicationLoader(Application):  # type: ignore
    """Bootstraps the WSGI app"""

    def __init__(
        self,
        options: Dict[str, Any] | None = None,
    ):
        self.options = options or {}
        self.config_path = self.options.pop("config", None)
        super().__init__()

    def init(self, parser: Any, opts: Dict[str, Any], args: Any) -> None:
        """Class ApplicationLoader object constructor."""
        if opts:
            self.options = opts
        self.cfg.set("default_proc_name", args[0])

    def load_config(self) -> None:
        """Load config from passed options"""
        if self.config_path:
            self.load_config_from_file(self.config_path)
        config = {key: value for key, value in self.options.items() if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self) -> Starlite:
        """Load application."""
        return get_app(uvicorn_settings.ASGI_APP)


def run_wsgi(
    host: str,
    port: int,
    http_workers: int,
    reload: bool,
) -> None:
    """Run gunicorn WSGI with ASGI workers."""

    ApplicationLoader(
        options={
            "host": host,
            "workers": str(http_workers),
            "port": str(port),
            "reload": reload,
            "loglevel": app_settings.LOG_LEVEL,
            "config": pkgutil.get_loader("starlite_bedrock.utils.gunicorn").path,  # type: ignore
        },
    ).run()
