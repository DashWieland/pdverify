"""WAV I/O with zero native dependencies.

Pd's ``soundfiler`` writes plain 16-bit PCM by default, which the stdlib
``wave`` module reads directly. 32-bit float output (which ``wave`` refuses,
because Pd tags it WAVE_FORMAT_EXTENSIBLE) is handled by a small hand-rolled
RIFF parser so the fidelity opt-in never drags in scipy/soundfile.
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path

import numpy as np

from .audio import AudioBuffer


def read_wav(path: str | Path) -> AudioBuffer:
    path = Path(path)
    try:
        return _read_pcm_wave(path)
    except wave.Error:
        # wave chokes on float / EXTENSIBLE formats; fall back to a RIFF walk.
        return _read_riff(path)


def _read_pcm_wave(path: Path) -> AudioBuffer:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif sw == 3:
        data = _unpack_int24(raw) / 8388608.0
    elif sw == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    elif sw == 1:
        data = (np.frombuffer(raw, dtype="<u1").astype(np.float64) - 128.0) / 128.0
    else:
        raise wave.Error(f"unsupported sample width {sw}")
    return AudioBuffer(data.reshape(-1, ch), sr)


def _unpack_int24(raw: bytes) -> np.ndarray:
    a = np.frombuffer(raw, dtype="<u1").reshape(-1, 3).astype(np.int32)
    val = a[:, 0] | (a[:, 1] << 8) | (a[:, 2] << 16)
    val = np.where(val & 0x800000, val - 0x1000000, val)
    return val.astype(np.float64)


def _read_riff(path: Path) -> AudioBuffer:
    """Minimal RIFF/WAVE reader for PCM and IEEE-float, including EXTENSIBLE."""
    buf = path.read_bytes()
    if buf[0:4] != b"RIFF" or buf[8:12] != b"WAVE":
        raise ValueError(f"{path} is not a RIFF/WAVE file")
    pos = 12
    fmt = None
    sr = ch = bits = 0
    while pos + 8 <= len(buf):
        cid = buf[pos : pos + 4]
        (size,) = struct.unpack_from("<I", buf, pos + 4)
        body = pos + 8
        if cid == b"fmt ":
            fmt_tag, ch, sr, _byte_rate, _align, bits = struct.unpack_from(
                "<HHIIHH", buf, body
            )
            fmt = fmt_tag
            if fmt == 0xFFFE and size >= 24:  # EXTENSIBLE: real tag in subformat GUID
                (fmt,) = struct.unpack_from("<H", buf, body + 24)
        elif cid == b"data":
            raw = buf[body : body + size]
            if fmt == 3:  # IEEE float
                dt = "<f4" if bits == 32 else "<f8"
                data = np.frombuffer(raw, dtype=dt).astype(np.float64)
            elif fmt == 1:
                if bits == 16:
                    data = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
                elif bits == 24:
                    data = _unpack_int24(raw) / 8388608.0
                elif bits == 32:
                    data = np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
                else:
                    raise ValueError(f"unsupported PCM bit depth {bits}")
            else:
                raise ValueError(f"unsupported WAVE format tag {fmt}")
            return AudioBuffer(data.reshape(-1, ch if ch else 1), sr)
        pos = body + size + (size & 1)  # chunks are word-aligned
    raise ValueError(f"no data chunk found in {path}")
