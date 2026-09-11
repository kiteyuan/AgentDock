"""Audio capture and playback for Pi."""

from __future__ import annotations

import io
import wave
from pathlib import Path

from loguru import logger

SAMPLE_RATE = 16000


def record_wav(seconds: float, sample_rate: int = SAMPLE_RATE) -> bytes:
    import sounddevice as sd

    logger.info("Recording {}s @ {}Hz", seconds, sample_rate)
    frames = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()
    return _frames_to_wav(frames.tobytes(), sample_rate)


def record_until_stop(
    stop_event,
    sample_rate: int = SAMPLE_RATE,
    *,
    max_seconds: float = 60.0,
    blocksize: int = 1024,
) -> bytes:
    """Record until stop_event is set (or max_seconds). Same click-toggle UX as Web."""
    import sounddevice as sd

    chunks: list[bytes] = []
    max_frames = int(max_seconds * sample_rate)
    got = 0
    logger.info("Recording until stop @ {}Hz (max {}s)", sample_rate, max_seconds)

    def _callback(indata, frames, time, status) -> None:  # noqa: ARG001
        nonlocal got
        if stop_event.is_set() or got >= max_frames:
            raise sd.CallbackStop
        raw = indata[:frames].tobytes()
        chunks.append(raw)
        got += frames

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        blocksize=blocksize,
        callback=_callback,
    ):
        while not stop_event.is_set() and got < max_frames:
            stop_event.wait(0.05)

    return _frames_to_wav(b"".join(chunks), sample_rate)


def _frames_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def play_file(path: Path) -> None:
    path = Path(path)
    try:
        import sounddevice as sd
        import soundfile as sf

        data, sr = sf.read(str(path), dtype="float32")
        sd.play(data, sr)
        sd.wait()
        return
    except Exception as exc:  # noqa: BLE001
        logger.warning("sounddevice play failed: {}", exc)

    # mp3 / fallback via system
    import os
    import sys

    if sys.platform.startswith("linux"):
        os.system(f'mpg123 -q "{path}" 2>/dev/null || aplay "{path}" 2>/dev/null || true')
    else:
        logger.info("Saved audio at {} (open manually)", path)


def sniff_ext(data: bytes, declared: str | None = None) -> str:
    if data[:4] == b"RIFF":
        return "wav"
    if data[:3] == b"ID3" or data[:2] == b"\xff\xfb":
        return "mp3"
    if declared == "mp3":
        return "mp3"
    return declared or "wav"
