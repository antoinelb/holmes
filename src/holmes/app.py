import os
import threading
import webbrowser
from pathlib import Path

import uvicorn
from starlette.applications import Starlette

from . import api, config
from .logging import init_logging, logger

##########
# public #
##########


def create_app() -> Starlette:
    init_logging()

    app = Starlette(
        debug=config.DEBUG,
        routes=api.get_routes(),
    )

    logger.info("App started.")
    if config.DEBUG:
        logger.warning("Running in debug mode.")

    return app


def run_server() -> None:
    init_logging()

    url = f"http://{config.HOST}:{config.PORT}"
    logger.info(
        f"Starting app in {'debug' if config.DEBUG else 'production'} mode "
        f"on port {config.PORT} : {url}"
    )

    def open_browser() -> None:
        threading.Event().wait(1.0)
        webbrowser.open(url)

    if not config.DEBUG and "PYTEST_CURRENT_TEST" not in os.environ:
        threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(
        "holmes.app:create_app",
        factory=True,
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        reload_dirs=str(Path(__file__).parent.parent.absolute()),
        log_level="debug" if config.DEBUG else "info",
        access_log=True,
    )
