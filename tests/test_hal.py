import sys

import numpy as np

from smartmirror.hal import HAL


class FakeResponse:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.current = b""
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def read1(self, size):
        while not self.current:
            self.current = next(self.chunks, b"")
            if not self.current:
                return b""
        chunk, self.current = self.current[:size], self.current[size:]
        return chunk


def test_read_audio_uses_http_pcm_stream(monkeypatch):
    samples = np.array([100, -200, 300, -400], dtype="<i2")
    response = FakeResponse([samples.tobytes()[:3], samples.tobytes()[3:]])
    requested = []

    def fake_urlopen(url, timeout):
        requested.append((url, timeout))
        return response

    monkeypatch.setattr("smartmirror.hal.hal.urllib.request.urlopen", fake_urlopen)
    hal = HAL(
        samplerate=4, blocksize=4, input_stream_url="http://example.test/audio_feed"
    )

    blocks = list(hal.read_audio())

    assert requested == [("http://example.test/audio_feed", 1)]
    assert len(blocks) == 1
    np.testing.assert_array_equal(blocks[0], samples)
    assert blocks[0].dtype == np.int16
    assert response.closed


def test_read_audio_resamples_http_pcm_to_hal_rate(monkeypatch):
    samples = np.array([0, 1000, 2000, 3000], dtype="<i2")
    response = FakeResponse([samples.tobytes()])
    monkeypatch.setattr(
        "smartmirror.hal.hal.urllib.request.urlopen",
        lambda _url, timeout: response,
    )
    hal = HAL(
        samplerate=2,
        blocksize=2,
        input_stream_url="http://example.test/audio_feed",
        input_stream_samplerate=4,
    )

    blocks = list(hal.read_audio())

    assert len(blocks) == 1
    assert len(blocks[0]) == 2
    assert blocks[0].dtype == np.int16


def test_read_audio_keeps_local_input_when_no_stream_url(monkeypatch):
    class FakeInputStream:
        def __init__(self, **kwargs):
            self.blocksize = kwargs["blocksize"]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _blocksize):
            hal.close()
            return np.array([[123]], dtype=np.int16), False

    class FakeSounddevice:
        InputStream = FakeInputStream

    hal = HAL(samplerate=1, blocksize=1)
    monkeypatch.setitem(sys.modules, "sounddevice", FakeSounddevice)
    monkeypatch.setattr(HAL, "_resolve_input_samplerate", lambda _self: 1)

    blocks = list(hal.read_audio())

    assert len(blocks) == 1
    np.testing.assert_array_equal(blocks[0], np.array([123], dtype=np.int16))
