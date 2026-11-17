"""Environment variables: GLASSCUBE_*, with the pre-rename SMARTMIRROR_* names still accepted."""

import os

PREFIX = "GLASSCUBE_"
LEGACY_PREFIX = "SMARTMIRROR_"


def adopt_legacy_env() -> None:
    """Copy each SMARTMIRROR_X into GLASSCUBE_X when GLASSCUBE_X isn't set.

    The package was called `smartmirror` before 0.1.0; mirrors set up then keep working.
    """
    for name, value in list(os.environ.items()):
        if name.startswith(LEGACY_PREFIX):
            os.environ.setdefault(PREFIX + name[len(LEGACY_PREFIX):], value)
