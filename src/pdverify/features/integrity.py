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


def is_clipped(x: np.ndarray, ceiling: float = 0.999, min_run: int = 3) -> bool:
    """True if the signal sits at (or beyond) the rail for at least ``min_run``
    consecutive samples — a single sample grazing full scale is not clipping."""
    if x.size == 0:
        return False
    at_rail = np.abs(x) >= ceiling
    if not at_rail.any():
        return False
    # longest run of True
    run = best = 0
    for v in at_rail:
        run = run + 1 if v else 0
        best = max(best, run)
    return best >= min_run
