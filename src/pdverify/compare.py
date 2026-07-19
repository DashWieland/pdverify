"""Compare a rendered patch against a reference sound.

"Make it sound like this" is the one goal that turns a subjective target into an
objective score: instead of arguing about whether something is "warm enough,"
measure how close it is to a reference. The similarity is a timbre-fingerprint
cosine (phase/time-invariant), and the diffs translate the gap back into
concrete, actionable moves — brighter, higher, louder.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import describe
from .report import Report

_BRIGHTNESS_ORDER = ["dark", "warm", "balanced", "bright", "brilliant"]

_BAND_ADVICE = {
    "sub": "low-end / sub weight",
    "bass": "bass",
    "low_mid": "low-mid body",
    "mid": "midrange",
    "high_mid": "upper-mids",
    "presence": "presence (2-6 kHz)",
    "brilliance": "an airy high-frequency top",
}


def fingerprint_similarity(a: list, b: list) -> float:
    """Cosine similarity of two (already L2-normalized) fingerprints, in [0,1]."""
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(n))
    return max(0.0, min(1.0, dot))


@dataclass(frozen=True)
class Comparison:
    similarity: float  # 0..1
    diffs: list  # human-readable moves to close the gap, biggest first

    def feedback(self) -> str:
        head = f"{self.similarity * 100:.0f}% match to the reference"
        if not self.diffs:
            return head + " — very close."
        return head + ". To close the gap: " + "; ".join(self.diffs) + "."


def compare(candidate: Report, target: Report) -> Comparison:
    """Compare a candidate patch's analysis against a target's."""
    sim = fingerprint_similarity(candidate.fingerprint, target.fingerprint)
    diffs: list[str] = []

    cb, tb = describe.brightness(candidate), describe.brightness(target)
    if cb != tb:
        direction = "brighter" if _BRIGHTNESS_ORDER.index(tb) > _BRIGHTNESS_ORDER.index(cb) else "darker"
        diffs.append(f"make it {direction} (target is {tb}, yours is {cb})")

    # biggest band-energy gaps -> concrete "add/reduce X" moves
    if candidate.bands and target.bands:
        deltas = {k: target.bands.get(k, 0.0) - candidate.bands.get(k, 0.0) for k in _BAND_ADVICE}
        for band in sorted(deltas, key=lambda b: -abs(deltas[b]))[:2]:
            if abs(deltas[band]) > 0.1:
                verb = "add" if deltas[band] > 0 else "reduce"
                diffs.append(f"{verb} {_BAND_ADVICE[band]}")

    if (
        candidate.f0_hz and target.f0_hz
        and candidate.pitch_confidence > 0.4 and target.pitch_confidence > 0.4
    ):
        cents = 1200 * math.log2(target.f0_hz / candidate.f0_hz)
        if abs(cents) > 50:
            diffs.append(f"shift pitch {cents:+.0f} cents (target {target.note}, yours {candidate.note})")

    dl = target.rms_dbfs - candidate.rms_dbfs
    if abs(dl) > 4:
        diffs.append(f"{'raise' if dl > 0 else 'lower'} the level by {abs(dl):.0f} dB")

    if candidate.motion != target.motion:
        diffs.append(f"target is '{target.motion}', yours is '{candidate.motion}'")

    return Comparison(similarity=round(sim, 4), diffs=diffs)
