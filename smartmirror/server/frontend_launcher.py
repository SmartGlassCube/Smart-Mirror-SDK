import asyncio
import os
import shutil
from pathlib import Path

DEFAULT_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


class FrontendLauncher:
    """Installs dependencies for and runs the Vite dev server of the React frontend (`frontend/`)."""

    def __init__(self, frontend_dir=None, host="localhost", port=5173, ws_port=8080):
        self.frontend_dir = Path(frontend_dir) if frontend_dir else DEFAULT_FRONTEND_DIR
        self.host = host
        self.port = port
        self.ws_port = ws_port
        self.process = None

    async def start(self):
        npm = shutil.which("npm")
        if not self.frontend_dir.exists():
            print(f"[Frontend] Skipping launch: frontend directory not found at {self.frontend_dir}")
            return
        if npm is None:
            print("[Frontend] Skipping launch: npm is not installed or not in PATH")
            return

        if not (self.frontend_dir / "node_modules").exists():
            print("[Frontend] Installing frontend dependencies (npm install)...")
            install = await asyncio.create_subprocess_exec(npm, "install", cwd=str(self.frontend_dir))
            if await install.wait() != 0:
                print(f"[Frontend] npm install failed with exit code {install.returncode}")
                return

        print(f"[Frontend] Starting frontend on http://{self.host}:{self.port}")
        self.process = await asyncio.create_subprocess_exec(
            npm, "run", "dev", "--", "--host", self.host, "--port", str(self.port),
            cwd=str(self.frontend_dir),
            # Read by frontend/src/services/useWebSocket.ts
            env={**os.environ, "VITE_SMARTMIRROR_WS_PORT": str(self.ws_port)},
        )

    async def stop(self):
        if self.process is None:
            return
        self.process.terminate()
        await self.process.wait()
        self.process = None
