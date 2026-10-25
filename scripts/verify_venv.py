#!/usr/bin/env python
"""Check every installed package's files against the sha256 hashes in its RECORD.

Finds packages that are damaged on disk -- e.g. by a Raspberry Pi losing
power mid-install with a too-weak supply -- which then fail in odd ways
(segfaults, missing attributes) instead of with a clear error:

    .venv/bin/python scripts/verify_venv.py

Lists each damaged package and prints the commands that reinstall them
from a fresh download; exits 1 if any are found.
"""
import base64
import hashlib
import sys
import warnings
from importlib.metadata import distributions
from pathlib import Path


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return base64.urlsafe_b64encode(digest.digest()).rstrip(b"=").decode()


def package_name(dist):
    """The package's name -- from its folder when METADATA itself is damaged or missing."""
    name = dist.metadata["Name"] if dist.metadata is not None else None
    if name:
        return name
    folder = Path(str(getattr(dist, "_path", "unknown-package")))
    return folder.name.split("-")[0]


def hashed_entries(dist):
    for entry in dist.files or []:
        if entry.hash is not None and entry.hash.mode == "sha256":  # skips RECORD itself, .pyc files
            yield entry


def main():
    print(f"Checking the packages in {sys.prefix} (can take a few minutes on an SD card)...")
    warnings.simplefilter("ignore", DeprecationWarning)  # importlib's noise about a missing Name
    dists = sorted(distributions(), key=lambda d: package_name(d).lower())

    damaged = {}
    for dist in dists:
        if not (dist.metadata is not None and dist.metadata["Name"]):
            damaged.setdefault(package_name(dist), []).append(f"{getattr(dist, '_path', '?')}/METADATA (missing or empty)")

    # Some packages ship the same files (opencv-python and opencv-contrib-python
    # both install cv2/): whichever was installed last wins, so a file is fine
    # if it matches what any package recorded for that path.
    expected = {}
    for dist in dists:
        for entry in hashed_entries(dist):
            expected.setdefault(entry.locate(), set()).add(entry.hash.value)

    actual = {}
    for dist in dists:
        for entry in hashed_entries(dist):
            path = entry.locate()
            if path not in actual:
                try:
                    actual[path] = file_hash(path)
                except FileNotFoundError:
                    actual[path] = None
            if actual[path] not in expected[path]:
                damaged.setdefault(package_name(dist), []).append(str(entry) + (" (missing)" if actual[path] is None else ""))

    if not damaged:
        print("All installed packages match their recorded hashes.")
        return 0

    for name, files in damaged.items():
        print(f"DAMAGED {name}: {len(files)} file(s), e.g. {', '.join(files[:3])}")
    names = " ".join(damaged)
    reinstall = " ".join(f"--reinstall-package {name}" for name in damaged)
    print("\nReinstall them from a fresh download:")
    print(f"  uv cache clean {names}")
    print(f"  uv sync --extra data --extra assistant {reinstall}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
