"""AudioBuffer: the value object passed between render and analyze."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AudioBuffer:
    """PCM audio as float samples in [-1, 1].

    ``samples`` is shape (n_frames, n_channels), float64. Even mono audio is
    stored 2-D so channel handling is uniform.
    """

    samples: np.ndarray
    sr: int

    def __post_init__(self) -> None:
        if self.samples.ndim == 1:
            object.__setattr__(self, "samples", self.samples.reshape(-1, 1))
        if self.samples.ndim != 2:
            raise ValueError(f"samples must be 1-D or 2-D, got {self.samples.ndim}-D")

    @property
    def n_frames(self) -> int:
        return int(self.samples.shape[0])

    @property
    def channels(self) -> int:
        return int(self.samples.shape[1])

    @property
    def duration(self) -> float:
        return self.n_frames / self.sr if self.sr else 0.0

    def mono(self) -> np.ndarray:
        """Channel-summed mono view (mean across channels), 1-D float64."""
        return self.samples.mean(axis=1)

    def channel(self, i: int) -> np.ndarray:
        return self.samples[:, i]
