from unittest.mock import MagicMock

import pytest

from smartmirror.smartmirror import SmartMirrorServer
from smartmirror.config.state_manager import StateManager


def _make_server(**overrides):
    graph = {"nodes": [{"id": "home", "widgets": []}], "edges": []}
    state_manager = StateManager(graph=graph, initial_node_id="home")
    kwargs = dict(
        graph=graph,
        state_manager=state_manager,
        gesture_detector=MagicMock(),  # skip real mediapipe construction
        with_camera=False,
        with_microphone=False,
        with_ui=False,
        ws_port=0,  # let the OS pick a free port
    )
    kwargs.update(overrides)
    return SmartMirrorServer(**kwargs)


@pytest.mark.asyncio
async def test_run_survives_one_loop_raising_and_logs_it(monkeypatch, caplog):
    """A bad camera_loop/assistant_loop must not crash the whole server silently."""
    server = _make_server()

    async def failing_camera_loop():
        raise RuntimeError("camera exploded")

    async def ok_assistant_loop():
        return None

    monkeypatch.setattr(server, "camera_loop", failing_camera_loop)
    monkeypatch.setattr(server, "assistant_loop", ok_assistant_loop)

    with caplog.at_level("ERROR", logger="smartmirror.smartmirror"):
        await server.run()  # must not raise -- that's the point of return_exceptions=True

    assert any("unhandled exception" in message for message in caplog.messages)


@pytest.mark.asyncio
async def test_run_completes_normally_when_both_loops_succeed(monkeypatch, caplog):
    server = _make_server()

    async def ok_loop():
        return None

    monkeypatch.setattr(server, "camera_loop", ok_loop)
    monkeypatch.setattr(server, "assistant_loop", ok_loop)

    with caplog.at_level("ERROR", logger="smartmirror.smartmirror"):
        await server.run()

    assert not any("unhandled exception" in message for message in caplog.messages)


@pytest.mark.asyncio
async def test_run_logs_both_loops_failing_independently(monkeypatch, caplog):
    server = _make_server()

    async def failing(label):
        raise RuntimeError(label)

    monkeypatch.setattr(server, "camera_loop", lambda: failing("camera"))
    monkeypatch.setattr(server, "assistant_loop", lambda: failing("assistant"))

    with caplog.at_level("ERROR", logger="smartmirror.smartmirror"):
        await server.run()  # neither exception propagates out of run()

    error_logs = [r for r in caplog.records if "unhandled exception" in r.message]
    assert len(error_logs) == 2
