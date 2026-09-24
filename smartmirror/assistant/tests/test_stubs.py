import pytest

from smartmirror.assistant.stt import WhisperSTT
from smartmirror.assistant.tts import PiperTTS
from smartmirror.assistant.tools import ToolManager


def test_whisper_stt_transcribe_and_listen_not_implemented():
    stt = WhisperSTT()
    with pytest.raises(NotImplementedError):
        stt.transcribe()
    with pytest.raises(NotImplementedError):
        stt.listen()


def test_piper_tts_speak_no_op_when_disabled():
    tts = PiperTTS(enabled=False)
    tts.speak("hello")  # must not raise


def test_piper_tts_speak_not_implemented_when_enabled():
    tts = PiperTTS(enabled=True)
    with pytest.raises(NotImplementedError):
        tts.speak("hello")


def test_tool_manager_register_and_specs():
    manager = ToolManager()
    manager.register("noop", lambda: None)

    assert manager.specs() == []


def test_tool_manager_dispatch_not_implemented():
    manager = ToolManager()
    with pytest.raises(NotImplementedError):
        manager.dispatch(tool_call=None)
