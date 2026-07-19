"""Spectral shape features: centroid, rolloff, flatness."""

from __future__ import annotations

import numpy as np

_EPS = 1e-12


def _spectrum(x: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    n = min(len(x), 1 << 15)
    start = (len(x) - n) // 2
    seg = x[start : start + n] * np.hanning(n)
    mag = np.abs(np.fft.rfft(seg))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    return mag, freqs


def spectral_centroid(x: np.ndarray, sr: int) -> float:
    """Energy-weighted mean frequency (Hz) — a rough 'brightness' measure."""
    if x.size < 32:
        return 0.0
    mag, freqs = _spectrum(x, sr)
    denom = float(np.sum(mag)) + _EPS
    return float(np.sum(freqs * mag) / denom)


def spectral_rolloff(x: np.ndarray, sr: int, fraction: float = 0.85) -> float:
    """Frequency below which ``fraction`` of the spectral energy lies."""
    if x.size < 32:
        return 0.0
    mag, freqs = _spectrum(x, sr)
    csum = np.cumsum(mag)
    if csum[-1] <= _EPS:
        return 0.0
    idx = int(np.searchsorted(csum, fraction * csum[-1]))
    idx = min(idx, len(freqs) - 1)
    return float(freqs[idx])


def spectral_flatness(x: np.ndarray, sr: int) -> float:
    """Ratio of geometric to arithmetic mean of the power spectrum, in [0,1].

    ~0 for a pure tone, ~1 for white noise. The tonal-vs-noisy discriminator.
    """
    if x.size < 32:
        return 0.0
    mag, _ = _spectrum(x, sr)
    power = mag**2
    power = power[power > _EPS]
    if power.size == 0:
        return 0.0
    gmean = np.exp(np.mean(np.log(power)))
    amean = np.mean(power)
    return float(gmean / (amean + _EPS))
