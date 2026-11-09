import os
from pathlib import Path

# backend/.data when running from a checkout.
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / ".data"


def data_dir(*parts) -> Path:
    """Where the mirror keeps the files it creates at runtime, joined with `parts`.

    Holds the downloaded hand-tracking model (models/), the embedded Qdrant
    store (qdrant/) and the content-sync cache (content-cache/). Override the
    root with SMARTMIRROR_DATA_DIR; read on every call, so it can change at runtime.
    """
    return Path(os.getenv("SMARTMIRROR_DATA_DIR") or DEFAULT_DATA_DIR).joinpath(*parts)
