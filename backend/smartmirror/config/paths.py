import os
import sys
from pathlib import Path

# backend/, when the package runs from a checkout of the repo (not from a pip install).
_BACKEND_DIR = Path(__file__).resolve().parents[2]
CHECKOUT_BACKEND_DIR = _BACKEND_DIR if (_BACKEND_DIR / "pyproject.toml").is_file() else None


def _user_data_dir() -> Path:
    """The per-user data folder for an installed package, following each OS's convention."""
    if sys.platform == "win32":
        base = os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "smartmirror"


# backend/.data in a checkout; the user's data folder (e.g. ~/.local/share/smartmirror) once installed.
DEFAULT_DATA_DIR = CHECKOUT_BACKEND_DIR / ".data" if CHECKOUT_BACKEND_DIR else _user_data_dir()


def data_dir(*parts) -> Path:
    """Where the mirror keeps the files it creates at runtime, joined with `parts`.

    Holds the downloaded hand-tracking model (models/), the embedded Qdrant
    store (qdrant/) and the content-sync cache (content-cache/). Override the
    root with SMARTMIRROR_DATA_DIR; read on every call, so it can change at runtime.
    """
    return Path(os.getenv("SMARTMIRROR_DATA_DIR") or DEFAULT_DATA_DIR).joinpath(*parts)
