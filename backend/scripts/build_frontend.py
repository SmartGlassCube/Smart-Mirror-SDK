"""Build ../frontend into glasscube/ui/, the prebuilt UI that ships in the package.

Run before `uv build` (the PyPI workflow does): `uv run python scripts/build_frontend.py`.
Needs Node/npm. The server serves the result on its WebSocket port (glasscube/server/static_ui.py).
"""

import shutil
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
UI_DIR = BACKEND_DIR / "glasscube" / "ui"


def main() -> int:
    npm = shutil.which("npm")
    if npm is None:
        print("npm is not installed or not on PATH", file=sys.stderr)
        return 1
    if not (FRONTEND_DIR / "node_modules").is_dir():
        subprocess.run([npm, "ci"], cwd=FRONTEND_DIR, check=True)
    subprocess.run([npm, "run", "build", "--", "--outDir", str(UI_DIR), "--emptyOutDir"], cwd=FRONTEND_DIR, check=True)
    if not (UI_DIR / "index.html").is_file():
        print(f"The build didn't produce {UI_DIR / 'index.html'}", file=sys.stderr)
        return 1
    print(f"Built the mirror UI into {UI_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
