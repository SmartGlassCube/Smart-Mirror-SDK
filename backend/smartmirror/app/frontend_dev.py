import asyncio
import logging
import os
import shutil
from pathlib import Path

# <repo>/frontend, next to backend/.
DEFAULT_FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"

logger = logging.getLogger(__name__)


class FrontendLauncher:
    """Dev convenience: runs the frontend's Vite dev server (npm install first if needed).

    The frontend is a separate app; this only saves starting it by hand. It is
    told the backend's WebSocket port through VITE_SMARTMIRROR_WS_PORT.
    """

    def __init__(self, frontend_dir=None, host="localhost", port=5173, ws_port=8080):
        self.frontend_dir = Path(frontend_dir) if frontend_dir else DEFAULT_FRONTEND_DIR
        self.host = host
        self.port = port
        self.ws_port = ws_port
        self.process = None

    async def start(self):
        npm = shutil.which("npm")
        if not self.frontend_dir.exists():
            logger.warning("Skipping frontend launch: directory not found at %s", self.frontend_dir)
            return
        if npm is None:
            logger.warning("Skipping frontend launch: npm is not installed or not in PATH")
            return

        if not (self.frontend_dir / "node_modules").exists():
            logger.info("Installing frontend dependencies (npm install)...")
            install = await asyncio.create_subprocess_exec(npm, "install", cwd=str(self.frontend_dir))
            if await install.wait() != 0:
                logger.error("npm install failed with exit code %s", install.returncode)
                return

        logger.info("Starting frontend on http://%s:%s", self.host, self.port)
        self.process = await asyncio.create_subprocess_exec(
            npm, "run", "dev", "--", "--host", self.host, "--port", str(self.port),
            cwd=str(self.frontend_dir),
            # Read by frontend/src/services/useWebSocket.ts
            env={**os.environ, "VITE_SMARTMIRROR_WS_PORT": str(self.ws_port)},
        )

    async def stop(self):
        if self.process is None:
            return
        if os.name == "nt":
            # terminate() would only end npm's cmd wrapper and leave Vite holding the port.
            killer = await asyncio.create_subprocess_exec(
                "taskkill", "/T", "/F", "/PID", str(self.process.pid),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
        else:
            self.process.terminate()
        await self.process.wait()
        self.process = None
