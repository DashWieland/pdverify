"""Temporal features: does the sound hold still, or move over its length?

analyze()'s spectral features look at one window in the middle of the buffer,
which captures timbre but not motion. These look across the whole signal so a
report can say "steady" vs "evolving" instead of a listener having to notice it.
"""

from __future__ import annotations

import numpy as np

_EPS = 1e-12


def frame_rms(x: np.ndarray, sr: int, hop_s: float = 0.046) -> np.ndarray:
    """RMS in ~46 ms hops across the whole signal."""
    hop = max(1, int(sr * hop_s))
    n = len(x) // hop
    if n < 2:
        return np.array([float(np.sqrt(np.mean(x**2) + _EPS))]) if x.size else np.array([0.0])
    frames = x[: n * hop].reshape(n, hop)
    return np.sqrt(np.mean(frames**2, axis=1) + _EPS)


def envelope_variation(x: np.ndarray, sr: int) -> float:
    """Coefficient of variation of the loudness envelope (std/mean). ~0 for a
    steady tone; larger when the level swells, pulses, or gates."""
    env = frame_rms(x, sr)
    m = float(env.mean())
    return float(env.std() / m) if m > 1e-9 else 0.0


def spectral_flux(x: np.ndarray, sr: int, hop_s: float = 0.05, nfft: int = 2048) -> float:
    """Mean frame-to-frame change of the *normalized* magnitude spectrum. ~0 when
    the timbre is unchanging; larger when the spectrum morphs over time. Level is
    normalized out, so this measures timbral motion, not loudness change."""
    hop = max(1, int(sr * hop_s))
    if len(x) < nfft + hop:
        return 0.0
    win = np.hanning(nfft)
    starts = range(0, len(x) - nfft, hop)
    prev = None
    flux = []
    for i in starts:
        mag = np.abs(np.fft.rfft(x[i : i + nfft] * win))
        mag = mag / (mag.sum() + _EPS)
        if prev is not None:
            flux.append(float(np.sqrt(np.sum((mag - prev) ** 2))))
        prev = mag
    return float(np.mean(flux)) if flux else 0.0


def motion(x: np.ndarray, sr: int) -> tuple[str, float]:
    """Combine envelope variation and spectral flux into a label + [0,1] amount.

    Thresholds calibrated so a held sine reads 'steady' and an evolving,
    self-mutating drone reads 'evolving'."""
    ev = envelope_variation(x, sr)
    fl = spectral_flux(x, sr)
    # normalize each to ~[0,1] against calibrated reference scales, then combine
    amount = min(1.0, 0.5 * min(1.0, ev / 0.6) + 0.5 * min(1.0, fl / 0.06))
    if amount < 0.12:
        label = "steady"
    elif amount < 0.35:
        label = "gently moving"
    elif amount < 0.6:
        label = "evolving"
    else:
        label = "very dynamic"
    return label, round(amount, 3)
