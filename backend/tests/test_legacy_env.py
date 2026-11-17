from glasscube.config.env import adopt_legacy_env


def test_old_smartmirror_variables_still_apply(monkeypatch):
    monkeypatch.setenv("SMARTMIRROR_WS_PORT", "9001")
    monkeypatch.setenv("SMARTMIRROR_CAMERA", "2")
    monkeypatch.setenv("GLASSCUBE_CAMERA", "1")
    monkeypatch.delenv("GLASSCUBE_WS_PORT", raising=False)
    adopt_legacy_env()
    import os

    assert os.environ["GLASSCUBE_WS_PORT"] == "9001"
    assert os.environ["GLASSCUBE_CAMERA"] == "1"  # the new name wins
