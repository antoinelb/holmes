from pathlib import Path

import uvicorn
from starlette.applications import Starlette

from . import config
from .api import api
from .data import archive
from .utils.print import done_print

##########
# public #
##########


def create_app() -> Starlette:
    app = Starlette(
        debug=config.DEBUG,
        routes=api.get_routes(),
    )

    done_print("App started.")
    if config.DEBUG:
        done_print("Running in debug mode.")

    return app


def run_server() -> None:
    # the sync runs here rather than in `create_app`: uvicorn installs its
    # own SIGINT handler before calling the factory, and that handler only
    # sets a flag, so a Ctrl-C during the download would be ignored
    if not config.SKIP_DATA_SYNC:
        archive.sync_data()

    url = f"http://{config.HOST}:{config.PORT}"
    done_print(
        f"Starting app in {'debug' if config.DEBUG else 'production'} mode "
        f"on port {config.PORT} : {url}"
    )

    uvicorn.run(
        "holmes.app:create_app",
        factory=True,
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        reload_dirs=str(Path(__file__).parent.parent.absolute()),
        log_level="error",
        access_log=False,
    )
