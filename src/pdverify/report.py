"""Report: the structured result of analyzing captured audio.

M0 carries the measured features plus a human-readable summary. The expectation
/ gate / graded-score layer (``score()``) lands in M1 and will wrap this same
object, so the JSON shape here is the stable foundation the benchmark builds on.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Report:
    # timing / format
    duration: float
    sr: int
    channels: int
    # integrity gates
    is_silent: bool
    is_clipped: bool
    has_nan_inf: bool
    dc_offset: float
    # level
    peak_dbfs: float
    rms_dbfs: float
    crest_factor: float
    # pitch
    f0_hz: float | None
    note: str | None
    cents_error: float | None
    pitch_confidence: float
    # spectral
    centroid_hz: float
    rolloff_hz: float
    flatness: float
    timbre: str
    bands: dict  # band label -> fraction of energy
    top_partials: list  # strongest spectral peaks (Hz), loudest first
    motion: str  # temporal character: steady / gently moving / evolving / very dynamic
    fingerprint: list  # compact L2-normalized log-power timbre vector (for reference matching)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema_version"] = SCHEMA_VERSION
        return d

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def summary(self) -> str:
        """One-line perceptual description of what the patch sounds like."""
        from .describe import describe

        return describe(self)

    def descriptors(self) -> list:
        """Perceptual tags for the sound, most-defining first (e.g. ['evolving',
        'dark', 'sub-heavy', 'hollow mids', 'airy high end', 'chordal',
        'no clear pitch'])."""
        from .describe import descriptors

        return descriptors(self)

    def pretty(self) -> str:
        lines = [
            f"duration    {self.duration:.3f}s  {self.sr} Hz  {self.channels}ch",
            f"level       peak {self.peak_dbfs:+.2f} dBFS   rms {self.rms_dbfs:+.2f} dBFS   crest {self.crest_factor:.2f}",
            f"pitch       {self._fmt_pitch()}",
            f"spectrum    centroid {self.centroid_hz:.0f} Hz   rolloff {self.rolloff_hz:.0f} Hz   flatness {self.flatness:.3f}  -> {self.timbre}",
            f"bands       {self._fmt_bands()}",
            f"partials    {self._fmt_partials()}",
            f"motion      {self.motion}",
            f"integrity   silent={self.is_silent}  clipped={self.is_clipped}  nan/inf={self.has_nan_inf}  dc={self.dc_offset:+.4f}",
        ]
        return "\n".join(lines)

    def _fmt_bands(self) -> str:
        if not self.bands:
            return "(n/a)"
        return "  ".join(f"{name} {pct * 100:.0f}%" for name, pct in self.bands.items())

    def _fmt_partials(self) -> str:
        if not self.top_partials:
            return "(none)"
        return ", ".join(f"{hz:.0f} Hz" for hz in self.top_partials)

    def _fmt_pitch(self) -> str:
        if not self.f0_hz:
            return "(none detected)"
        return f"{self.f0_hz:.2f} Hz -> {self.note} ({self.cents_error:+.0f} cents)  conf {self.pitch_confidence:.2f}"
