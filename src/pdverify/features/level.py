"""Amplitude / level features."""

from __future__ import annotations

import numpy as np

_EPS = 1e-12


def peak_linear(x: np.ndarray) -> float:
    return float(np.max(np.abs(x))) if x.size else 0.0


def peak_dbfs(x: np.ndarray) -> float:
    return _to_dbfs(peak_linear(x))


def rms_linear(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x**2))) if x.size else 0.0


def rms_dbfs(x: np.ndarray) -> float:
    return _to_dbfs(rms_linear(x))


def crest_factor(x: np.ndarray) -> float:
    """Peak / RMS. ~1.414 for a sine, higher for transient/percussive material."""
    r = rms_linear(x)
    return peak_linear(x) / r if r > _EPS else 0.0


def dc_offset(x: np.ndarray) -> float:
    return float(np.mean(x)) if x.size else 0.0


def _to_dbfs(v: float) -> float:
    return 20.0 * float(np.log10(v + _EPS))
