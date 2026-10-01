from unittest.mock import MagicMock, patch

import numpy as np

from smartmirror.hal.hal import HAL, resample_int16


def test_resample_int16_is_a_no_op_at_the_same_rate():
    block = np.array([1, 2, 3], dtype=np.int16)
    assert np.array_equal(resample_int16(block, 16000, 16000), block)


def test_resample_int16_changes_length_proportionally():
    block = np.full(480, 1000, dtype=np.int16)  # 10ms @ 48000Hz

    resampled = resample_int16(block, from_rate=48000, to_rate=16000)

    assert len(resampled) == 160  # 10ms @ 16000Hz
    assert resampled.dtype == np.int16


def test_resample_int16_handles_empty_block():
    block = np.array([], dtype=np.int16)
    assert len(resample_int16(block, 48000, 16000)) == 0


class _FakeInputStream:
    """Mimics sounddevice.InputStream just enough for HAL.read_audio()."""

    instances = []

    def __init__(self, samplerate, channels, dtype, blocksize, device):
        self.samplerate = samplerate
        self.blocksize = blocksize
        self._reads = 0
        _FakeInputStream.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self, n):
        self._reads += 1
        if self._reads > 2:
            raise _StopReading  # stop the infinite generator in tests
        return np.full((n, 1), 1000, dtype=np.int16), False


class _StopReading(Exception):
    """PEP 479: a StopIteration raised inside read_audio's generator body
    would be reinterpreted as a RuntimeError, so use a distinct exception
    to end the infinite loop from within these tests."""


def test_read_audio_yields_blocks_at_native_rate_without_resampling():
    _FakeInputStream.instances = []
    fake_sd = MagicMock()
    fake_sd.InputStream = _FakeInputStream
    fake_sd.check_input_settings.return_value = None  # requested rate accepted as-is

    with patch.dict("sys.modules", {"sounddevice": fake_sd}):
        hal = HAL(samplerate=16000, blocksize=1600)
        blocks = []
        try:
            for block in hal.read_audio():
                blocks.append(block)
        except _StopReading:
            pass

    assert len(blocks) == 2
    assert all(len(block) == 1600 for block in blocks)


def test_read_audio_resamples_when_device_rejects_requested_rate():
    _FakeInputStream.instances = []
    fake_sd = MagicMock()
    fake_sd.InputStream = _FakeInputStream
    fake_sd.check_input_settings.side_effect = Exception("unsupported rate")
    fake_sd.query_devices.return_value = {"default_samplerate": 48000.0}

    with patch.dict("sys.modules", {"sounddevice": fake_sd}):
        hal = HAL(samplerate=16000, blocksize=1600)
        blocks = []
        try:
            for block in hal.read_audio():
                blocks.append(block)
        except _StopReading:
            pass

    assert _FakeInputStream.instances[0].samplerate == 48000
    assert len(blocks) == 2
    assert all(len(block) == 1600 for block in blocks)  # resampled back down to 16kHz-sized blocks


def test_play_audio_calls_sounddevice_play_and_wait():
    fake_sd = MagicMock()
    samples = np.array([1, 2, 3], dtype=np.int16)

    with patch.dict("sys.modules", {"sounddevice": fake_sd}):
        hal = HAL(output_device="speakers")
        hal.play_audio(samples, samplerate=22050)

    fake_sd.play.assert_called_once_with(samples, samplerate=22050, device="speakers")
    fake_sd.wait.assert_called_once()
