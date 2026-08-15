import warnings

from starlette.config import Config

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore", category=UserWarning, module="starlette.config"
    )
    config = Config(".env")

DEBUG = config("DEBUG", cast=bool, default=False)
RELOAD = config("RELOAD", cast=bool, default=False)
PORT = config("PORT", cast=int, default=8000)
HOST = config("HOST", default="127.0.0.1")
DATA_DIR = config("HOLMES_DATA_DIR", default="")
SKIP_DATA_SYNC = config("HOLMES_SKIP_DATA_SYNC", cast=bool, default=False)
