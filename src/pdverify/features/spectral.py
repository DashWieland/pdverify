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
    """Power-weighted mean frequency (Hz) — a 'brightness' measure.

    Weighted by power (mag**2), not magnitude: a magnitude-weighted centroid is
    dragged upward by the thousands of tiny high-frequency bins in a noise/
    quantization floor, reporting a bright spectrum where there is no real energy.
    Power weighting keeps it consistent with the band energies and flatness.
    """
    if x.size < 32:
        return 0.0
    mag, freqs = _spectrum(x, sr)
    power = mag**2
    denom = float(np.sum(power)) + _EPS
    return float(np.sum(freqs * power) / denom)


def spectral_rolloff(x: np.ndarray, sr: int, fraction: float = 0.85) -> float:
    """Frequency below which ``fraction`` of the spectral *power* lies."""
    if x.size < 32:
        return 0.0
    mag, freqs = _spectrum(x, sr)
    csum = np.cumsum(mag**2)
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


# musically meaningful frequency bands, (label, low_hz, high_hz). The edges span
# 0 .. beyond any Nyquist we'll see, so every bin lands in exactly one band and
# the fractions sum to ~1 — a coverage gap otherwise hides DC/subsonic content
# and near-Nyquist aliasing (common with Pd's non-band-limited oscillators).
BANDS: tuple[tuple[str, float, float], ...] = (
    ("sub", 0, 60),
    ("bass", 60, 250),
    ("low_mid", 250, 500),
    ("mid", 500, 2000),
    ("high_mid", 2000, 4000),
    ("presence", 4000, 6000),
    ("brilliance", 6000, 1_000_000),
)


def band_energies(x: np.ndarray, sr: int) -> dict[str, float]:
    """Fraction of total spectral energy in each named band (sums to ~1)."""
    if x.size < 32:
        return {name: 0.0 for name, _, _ in BANDS}
    mag, freqs = _spectrum(x, sr)
    power = mag**2
    total = float(power.sum()) + _EPS
    return {
        name: float(power[(freqs >= lo) & (freqs < hi)].sum() / total)
        for name, lo, hi in BANDS
    }


def log_power_fingerprint(x: np.ndarray, sr: int, n_bands: int = 32, fmin: float = 50.0) -> list[float]:
    """A compact, level-independent timbre fingerprint: log power in ``n_bands``
    geometrically-spaced bands, L2-normalized. Cosine similarity between two
    fingerprints is a robust "do these sound alike" measure — phase- and
    time-invariant, so it works for drones and textures, not just aligned tones."""
    if x.size < 64:
        return [0.0] * n_bands
    mag, freqs = _spectrum(x, sr)
    power = mag**2
    edges = np.geomspace(fmin, sr / 2, n_bands + 1)
    vec = np.array([power[(freqs >= edges[i]) & (freqs < edges[i + 1])].sum() for i in range(n_bands)])
    vec = np.log1p(vec)
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec = vec / norm
    return [round(float(v), 5) for v in vec]


def top_partials(x: np.ndarray, sr: int, n: int = 6, thresh: float = 0.03) -> list[float]:
    """The strongest spectral peaks (Hz), loudest first — useful for telling a
    clean tone from a rich harmonic stack from an inharmonic/metallic spectrum."""
    if x.size < 32:
        return []
    mag, freqs = _spectrum(x, sr)
    interior = mag[1:-1]
    is_peak = (interior > mag[:-2]) & (interior >= mag[2:]) & (interior > thresh * mag.max())
    idx = np.flatnonzero(is_peak) + 1
    order = idx[np.argsort(mag[idx])[::-1]]
    return [round(float(freqs[i]), 1) for i in order[:n]]
