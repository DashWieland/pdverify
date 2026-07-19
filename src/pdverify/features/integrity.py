"""Signal-integrity checks — the hard gates that make a verdict trustworthy."""

from __future__ import annotations

import numpy as np

from .level import peak_linear


def has_nan_inf(x: np.ndarray) -> bool:
    return bool(not np.all(np.isfinite(x)))


def is_silent(x: np.ndarray, floor_dbfs: float = -60.0) -> bool:
    """True if the peak never rises above ``floor_dbfs``."""
    floor_lin = 10.0 ** (floor_dbfs / 20.0)
    return peak_linear(x) < floor_lin


def is_clipped(
    x: np.ndarray, ceiling: float = 0.999, min_run: int = 3, over_unity: float = 1.001
) -> bool:
    """True if the output would clip on playback.

    Two cases: (1) the signal exceeds full scale — ``render()`` recovers the true
    over-unity level, and dac~ would hard-clip anything above ±1; (2) the signal
    already sits at the ±1 rail for at least ``min_run`` consecutive frames (an
    in-patch clip). A single sample grazing full scale is not clipping, and a
    clean full-scale sine (brief peaks) is not either.

    Works on mono (1-D) or multichannel (2-D, frames x channels); a frame counts
    as railed if any channel is at the rail.
    """
    if x.size == 0:
        return False
    if float(np.max(np.abs(x))) > over_unity:
        return True
    at_rail = np.abs(x) >= ceiling
    if at_rail.ndim > 1:
        at_rail = at_rail.any(axis=1)
    if not at_rail.any():
        return False
    return _longest_run(at_rail) >= min_run


def _longest_run(mask: np.ndarray) -> int:
    """Length of the longest run of True in a 1-D boolean array (vectorized)."""
    m = mask.astype(np.int8)
    edges = np.diff(np.concatenate(([0], m, [0])))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    return int((ends - starts).max()) if starts.size else 0
