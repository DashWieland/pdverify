"""Pitch estimation and note naming."""

from __future__ import annotations

import numpy as np

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_EPS = 1e-12


def estimate_f0(x: np.ndarray, sr: int, fmin: float = 20.0, fmax: float = 12000.0) -> tuple[float, float]:
    """Estimate the fundamental frequency (Hz) of a mono signal.

    Returns (f0_hz, confidence in [0,1]). Uses the magnitude-spectrum peak of a
    Hann-windowed central segment, refined to sub-bin accuracy with parabolic
    interpolation. Confidence is the peak's share of total spectral energy — low
    for noise, high for a clean tone.
    """
    if x.size < 32:
        return 0.0, 0.0
    n = min(len(x), 1 << 14)  # up to 16384 samples
    start = (len(x) - n) // 2
    seg = x[start : start + n] * np.hanning(n)
    spec = np.abs(np.fft.rfft(seg))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)

    lo = np.searchsorted(freqs, fmin)
    hi = np.searchsorted(freqs, fmax)
    if hi <= lo + 1:
        return 0.0, 0.0
    band = spec[lo:hi]
    k = int(np.argmax(band)) + lo

    f0 = float(freqs[k])
    if 0 < k < len(spec) - 1:
        a, b, c = (np.log(spec[k - 1] + _EPS), np.log(spec[k] + _EPS), np.log(spec[k + 1] + _EPS))
        denom = a - 2 * b + c
        if abs(denom) > _EPS:
            delta = 0.5 * (a - c) / denom
            f0 = float((k + delta) * sr / n)

    total = float(np.sum(spec)) + _EPS
    confidence = float(spec[k] / total)
    return f0, min(1.0, confidence * 4.0)  # scale: a pure sine concentrates energy in ~1 bin


def hz_to_note(freq: float) -> tuple[str, float]:
    """Return (note_name_with_octave, cents_error) for a frequency, e.g.
    (``"A4"``, -3.2). Empty name for non-positive input."""
    if freq <= 0:
        return "", 0.0
    midi = 69 + 12 * np.log2(freq / 440.0)
    nearest = int(round(midi))
    cents = float((midi - nearest) * 100.0)
    name = f"{_NOTE_NAMES[nearest % 12]}{nearest // 12 - 1}"
    return name, cents
