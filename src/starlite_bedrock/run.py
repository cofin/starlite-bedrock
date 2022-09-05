"""Application Web Server Gateway Interface - gunicorn."""
import asyncio
import os
import signal
import sys
import threading
import time
from functools import lru_cache
from typing import TYPE_CHECKING, Any, cast

from gunicorn.app.base import Application
from gunicorn.arbiter import Arbiter
from starlite.utils.module_loading import import_string
from uvicorn.main import Server
from uvicorn.workers import UvicornWorker as _UvicornWorker

if TYPE_CHECKING:
    from starlite import Starlite


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
        options: dict[str, Any] | None = None,
    ):
        self.options = options or {}
        self.asgi_application: "Starlite" = self.options.pop("asgi_application", None)
        self.config_path = self.options.pop("config", None)
        super().__init__()

    def init(self, parser: Any, opts: dict[str, Any], args: Any) -> None:
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

    def load(self) -> "Starlite":
        """Load application."""
        return get_app(self.asgi_application)


@lru_cache()
def get_app(import_path: str) -> "Starlite":
    return cast("Starlite", import_string(import_path))


def run_asgi(
    host: str,
    port: int,
    http_workers: int,
    reload: bool,
    log_level: str,
    app: str,
    lifespan: str = "auto",
    access_log: bool = True,
) -> None:
    """Launches an ASGI application with Uvicorn

    Args:
        host (str): _description_
        port (int): _description_
        http_workers (int): _description_
        reload (bool): _description_
        log_level (str): _description_
        app (str): _description_
        lifespan (str, optional): _description_. Defaults to "auto".
        access_log (bool, optional): _description_. Defaults to True.
    """
    import uvicorn  # pylint: disable=[import-outside-toplevel]

    uvicorn.run(
        app=app,
        host=host,
        port=port,
        log_level=log_level,
        reload=reload,
        lifespan=lifespan,
        access_log=access_log,
        workers=http_workers,
    )


def run_wsgi(
    host: str,
    port: int,
    http_workers: int,
    reload: bool,
    log_level: str,
    app: str,
    gunicorn_conf_path: str,
) -> None:
    """Run gunicorn WSGI with ASGI workers."""
    sys.argv = [
        "--gunicorn",
    ]
    if reload:
        sys.argv.append("-r")
    sys.argv.append(app)

    ApplicationLoader(
        options={
            "host": host,
            "workers": str(http_workers),
            "port": str(port),
            "reload": reload,
            "loglevel": log_level,
            "config": gunicorn_conf_path,
        },
    ).run()
