"""Pitch estimation and note naming."""

from __future__ import annotations

import re

import numpy as np

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")
_EPS = 1e-12


def note_to_hz(name: str) -> float:
    """Convert a note name like 'A4', 'C#3', or 'Eb2' to Hz (A4 = 440)."""
    m = _NOTE_RE.match(name.strip())
    if not m:
        raise ValueError(f"unrecognized note name: {name!r} (expected e.g. 'A4', 'C#3', 'Eb2')")
    letter, accidental, octave = m.group(1).upper(), m.group(2), int(m.group(3))
    semitone = _SEMITONE[letter] + (1 if accidental == "#" else -1 if accidental == "b" else 0)
    midi = (octave + 1) * 12 + semitone
    return float(440.0 * 2.0 ** ((midi - 69) / 12.0))


def cents_between(measured_hz: float, target_hz: float) -> float:
    """Signed interval from target to measured, in cents (+ = measured is sharp)."""
    if measured_hz <= 0 or target_hz <= 0:
        return float("nan")
    return float(1200.0 * np.log2(measured_hz / target_hz))


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
