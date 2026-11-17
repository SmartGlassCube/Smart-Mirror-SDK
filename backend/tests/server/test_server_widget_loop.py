import asyncio

from glasscube.server import SmartMirrorServer


def test_widgets_keep_refreshing_while_the_camera_loop_is_stuck(monkeypatch):
    server = SmartMirrorServer(graph={"nodes": [{"id": "home", "widgets": []}], "edges": []},
                               ws_port=0, widget_update_tick=0.05)
    refreshes = []

    async def stuck_camera_loop():
        # Like a LAN camera stream that hangs mid-read: never yields a frame.
        while server.running:
            await asyncio.sleep(0.01)

    async def refresh_widget_data():
        refreshes.append(1)
        if len(refreshes) == 5:
            server.stop()

    monkeypatch.setattr(server, "_main_loop", stuck_camera_loop)
    monkeypatch.setattr(server, "_refresh_widget_data", refresh_widget_data)
    asyncio.run(asyncio.wait_for(server.run(), timeout=5))

    assert len(refreshes) == 5


def test_a_crashing_camera_loop_is_logged_and_widgets_carry_on(monkeypatch, caplog):
    server = SmartMirrorServer(graph={"nodes": [{"id": "home", "widgets": []}], "edges": []},
                               ws_port=0, widget_update_tick=0.05)
    refreshes = []

    async def crashing_camera_loop():
        raise RuntimeError("hand tracking failed to start")

    async def refresh_widget_data():
        refreshes.append(1)
        if len(refreshes) == 3:
            server.stop()

    monkeypatch.setattr(server, "_main_loop", crashing_camera_loop)
    monkeypatch.setattr(server, "_refresh_widget_data", refresh_widget_data)
    with caplog.at_level("ERROR", logger="glasscube.server.app"):
        asyncio.run(asyncio.wait_for(server.run(), timeout=5))

    assert len(refreshes) == 3
    crash = next(record for record in caplog.records if record.getMessage() == "Camera loop crashed")
    assert str(crash.exc_info[1]) == "hand tracking failed to start"
