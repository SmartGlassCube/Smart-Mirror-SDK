import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolated_data_dir(tmp_path_factory):
    """Keep the tests' Qdrant stores and caches out of the real backend/.data."""
    previous = os.environ.get("GLASSCUBE_DATA_DIR")
    os.environ["GLASSCUBE_DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    yield
    if previous is None:
        os.environ.pop("GLASSCUBE_DATA_DIR", None)
    else:
        os.environ["GLASSCUBE_DATA_DIR"] = previous
