"""Hardware Abstraction Layer.

This is the one seam between software and physical I/O. The sounddevice
implementation here is for local dev/testing on a laptop; the hardware
owner can swap it for real Raspberry Pi I/O later without touching
STT/TTS/Assistant -- callers only rely on read_audio()/play_audio()
behaving the same:

- read_audio() yields mono int16 blocks at self.samplerate, resampling on
  the fly if the underlying device doesn't natively support that rate.
- play_audio() blocks until playback of the given samples finishes.
- close() makes read_audio() streams end, so a thread blocked waiting for
  speech can return when the app shuts down.

sounddevice is imported lazily inside the methods that need it, so
importing this module (or constructing a HAL that's never used for audio)
doesn't require it to be installed.
"""

import threading

import numpy as np

DEFAULT_SAMPLERATE = 16000
DEFAULT_BLOCKSIZE = 1600  # 100ms at 16kHz
# A network mic that sends nothing for this long counts as gone.
NETWORK_AUDIO_TIMEOUT_SECONDS = 5


def is_stream_url(device) -> bool:
    """True for a camera/microphone given as an http(s):// URL rather than a local device."""
    return isinstance(device, str) and device.startswith(("http://", "https://"))


class HAL:
    def __init__(
        self,
        samplerate: int = DEFAULT_SAMPLERATE,
        channels: int = 1,
        blocksize: int = DEFAULT_BLOCKSIZE,
        input_device=None,
        output_device=None,
    ):
        self.samplerate = samplerate
        self.channels = channels
        self.blocksize = blocksize
        self.input_device = input_device
        self.output_device = output_device
        self._closed = threading.Event()

    def close(self) -> None:
        """End every read_audio() stream after its current block."""
        self._closed.set()

    def read_audio(self):
        """Yield mono int16 audio blocks at self.samplerate from the microphone, until close().

        An http:// `input_device` is a microphone on another machine instead:
        a raw mono int16 stream, as served by scripts/lan_media_server.py.
        """
        if is_stream_url(self.input_device):
            yield from self._read_network_audio()
            return

        import sounddevice as sd

        device_rate = self._resolve_input_samplerate()
        block_in = max(1, int(round(self.blocksize * device_rate / self.samplerate)))

        with sd.InputStream(
            samplerate=device_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=block_in,
            device=self.input_device,
        ) as stream:
            while not self._closed.is_set():
                block, _overflowed = stream.read(block_in)
                block = block[:, 0] if block.ndim > 1 else block
                if device_rate != self.samplerate:
                    block = resample_int16(block, device_rate, self.samplerate)
                yield block

    def _read_network_audio(self):
        """read_audio() for an http:// input_device. Raises once the stream drops, like a mic that's unplugged."""
        from urllib.request import urlopen

        separator = "&" if "?" in self.input_device else "?"
        url = f"{self.input_device}{separator}rate={self.samplerate}"
        block_bytes = self.blocksize * 2  # int16
        with urlopen(url, timeout=NETWORK_AUDIO_TIMEOUT_SECONDS) as response:
            while not self._closed.is_set():
                data = b""
                while len(data) < block_bytes:
                    chunk = response.read(block_bytes - len(data))
                    if not chunk:
                        raise ConnectionError(f"network microphone stream ended: {self.input_device}")
                    data += chunk
                yield np.frombuffer(data, dtype="<i2").copy()

    def play_audio(self, samples: np.ndarray, samplerate: int) -> None:
        """Blocking playback of mono samples at `samplerate` through the speaker."""
        import sounddevice as sd

        sd.play(samples, samplerate=samplerate, device=self.output_device)
        sd.wait()

    def _resolve_input_samplerate(self) -> int:
        """Return self.samplerate if the input device supports it natively,
        otherwise the device's default rate (read_audio resamples down)."""
        import sounddevice as sd

        try:
            sd.check_input_settings(device=self.input_device, samplerate=self.samplerate, channels=self.channels)
            return self.samplerate
        except Exception:
            device_info = sd.query_devices(self.input_device, "input")
            return int(device_info["default_samplerate"])


def resample_int16(block: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """Cheap linear-interpolation resample -- good enough for speech, no extra deps."""
    if from_rate == to_rate or len(block) == 0:
        return block

    duration = len(block) / from_rate
    n_out = max(1, int(round(duration * to_rate)))
    x_old = np.linspace(0, duration, num=len(block), endpoint=False)
    x_new = np.linspace(0, duration, num=n_out, endpoint=False)
    resampled = np.interp(x_new, x_old, block.astype(np.float32))
    return resampled.astype(np.int16)
