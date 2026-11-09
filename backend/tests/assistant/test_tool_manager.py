import pytest

from smartmirror.assistant.tools import ToolManager


def test_tool_manager_register_and_specs():
    manager = ToolManager()
    manager.register("noop", lambda: None)

    assert manager.specs() == []


def test_tool_manager_dispatch_not_implemented():
    manager = ToolManager()
    with pytest.raises(NotImplementedError):
        manager.dispatch(tool_call=None)
