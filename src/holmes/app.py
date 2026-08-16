import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from starlette.applications import Starlette

from . import config
from .api import api
from .data import archive
from .utils.print import done_print, warn_print

#############
# constants #
#############

# uvicorn binds well inside this, and the sync it follows has already run
browser_delay = 1.0

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

    # started after the sync, so a first-run download is over before the
    # browser asks for a page; daemon so it never holds up a Ctrl-C
    if not config.DEBUG:
        threading.Thread(
            target=_open_browser, args=(url,), daemon=True
        ).start()

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


###########
# private #
###########


def _open_browser(url: str) -> None:
    """Point the default browser at the dashboard once it is up.

    A machine with no browser — a lab server, a container — must still
    serve the app, so a failure here only says so and leaves the url.
    """
    time.sleep(browser_delay)
    try:
        webbrowser.open(url)
    except Exception as exc:
        warn_print(f"Could not open a browser ({exc}); open {url} yourself.")
