"""Composable expectations. Build them with the `expect` namespace and pass a
list to `score()` or `verify()`:

    from pdverify import expect, verify
    card = verify("build.pd", [
        expect.not_silent(), expect.no_clipping(),
        expect.note("A4", tol_cents=30, weight=2.0),
        expect.tonal(),
    ])

Each builder returns an `Expectation` that knows how to evaluate itself against
an analysis `Report` and produce a `Score`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .features.pitch import cents_between, hz_to_note, note_to_hz
from .report import Report
from .score import Score, linear_ramp

_EvalFn = Callable[[Report], Score]


@dataclass(frozen=True)
class Expectation:
    field: str
    kind: str  # "gate" | "graded"
    weight: float
    evaluate: _EvalFn


# --- gates ------------------------------------------------------------------

def not_silent(floor_dbfs: float = -60.0) -> Expectation:
    def ev(r: Report) -> Score:
        passed = not r.is_silent
        return Score(
            field="not_silent", kind="gate", value=1.0 if passed else 0.0, passed=passed,
            measured=round(r.peak_dbfs, 2), target=f">{floor_dbfs} dBFS peak",
            detail="output is silent" if not passed else "signal present",
            pd_hint=None if passed else "nothing reaches [dac~]; check the output connections and that DSP is producing signal",
        )
    return Expectation("not_silent", "gate", 1.0, ev)


def finite() -> Expectation:
    def ev(r: Report) -> Score:
        passed = not r.has_nan_inf
        return Score(
            field="finite", kind="gate", value=1.0 if passed else 0.0, passed=passed,
            measured=r.has_nan_inf, target=False,
            detail="output contains NaN/Inf" if not passed else "all samples finite",
            pd_hint=None if passed else "a feedback path is diverging; add damping or a [clip~], or break the loop",
        )
    return Expectation("finite", "gate", 1.0, ev)


def no_clipping(ceiling: float = 0.999) -> Expectation:
    def ev(r: Report) -> Score:
        passed = not r.is_clipped
        detail = "no clipping"
        if not passed:
            over = " (exceeds full scale)" if r.peak_dbfs > 0.1 else " (pinned at the rail)"
            detail = f"output clips on playback: peak {r.peak_dbfs:+.1f} dBFS{over}"
        return Score(
            field="no_clipping", kind="gate", value=1.0 if passed else 0.0, passed=passed,
            measured=round(r.peak_dbfs, 2), target="<= 0 dBFS", detail=detail,
            pd_hint=None if passed else "lower the gain before [dac~] (e.g. an extra [*~ 0.5])",
        )
    return Expectation("no_clipping", "gate", 1.0, ev)


def duration(seconds: float, tol: float = 0.05) -> Expectation:
    def ev(r: Report) -> Score:
        err = abs(r.duration - seconds)
        passed = err <= tol
        return Score(
            field="duration", kind="gate", value=1.0 if passed else 0.0, passed=passed,
            measured=round(r.duration, 3), target=seconds, tolerance=tol,
            detail=f"{r.duration:.3f}s vs expected {seconds:.3f}s",
        )
    return Expectation("duration", "gate", 1.0, ev)


# --- graded -----------------------------------------------------------------

_INTERVALS = {  # ratio -> name, for pitch-error hints
    2.0: "an octave up", 0.5: "an octave down",
    1.5: "a fifth up", 0.6667: "a fifth down",
    1.3333: "a fourth up", 0.75: "a fourth down",
    1.26: "a major third up", 1.2: "a minor third up",
}


def _interval_name(ratio: float) -> str:
    for r, name in _INTERVALS.items():
        if abs(ratio - r) / r < 0.02:
            return f" (~{name})"
    return ""


def _pitch_score(field: str, r: Report, target_hz: float, tol_cents: float, weight: float) -> Score:
    if r.f0_hz is None:
        return Score(
            field=field, kind="graded", value=0.0, passed=False, measured=None,
            target=round(target_hz, 2), weight=weight, tolerance=tol_cents,
            detail="no pitch detected (silent or noise-like output)",
            pd_hint="expected a clear tone; the output has no stable fundamental",
        )
    cents = cents_between(r.f0_hz, target_hz)
    err = abs(cents)
    value = linear_ramp(err, tol_cents)
    passed = err <= tol_cents
    # error framing: how the measured pitch sits relative to the target (matches
    # the sign of `cents`). The fix ratio (target/measured) goes in the hint.
    err_ratio = r.f0_hz / target_hz
    fix_ratio = target_hz / r.f0_hz
    meas_note, _ = hz_to_note(r.f0_hz)
    tgt_note, _ = hz_to_note(target_hz)
    detail = f"got {r.f0_hz:.1f} Hz ({meas_note}), expected {target_hz:.1f} Hz ({tgt_note}): {cents:+.0f} cents{_interval_name(err_ratio)}"
    pd_hint = None if passed else f"scale the oscillator frequency by {fix_ratio:.3f} (e.g. [osc~ {target_hz:.0f}])"
    return Score(
        field=field, kind="graded", value=value, passed=passed, measured=round(r.f0_hz, 2),
        target=round(target_hz, 2), weight=weight, tolerance=tol_cents, detail=detail, pd_hint=pd_hint,
    )


def pitch(hz: float, tol_cents: float = 20.0, weight: float = 1.0) -> Expectation:
    return Expectation("pitch", "graded", weight, lambda r: _pitch_score("pitch", r, hz, tol_cents, weight))


def note(name: str, tol_cents: float = 50.0, weight: float = 1.0) -> Expectation:
    target_hz = note_to_hz(name)
    return Expectation("note", "graded", weight, lambda r: _pitch_score("note", r, target_hz, tol_cents, weight))


def level(dbfs: float, tol_db: float = 3.0, weight: float = 1.0) -> Expectation:
    def ev(r: Report) -> Score:
        err = abs(r.rms_dbfs - dbfs)
        passed = err <= tol_db
        return Score(
            field="level", kind="graded", value=linear_ramp(err, tol_db), passed=passed,
            measured=round(r.rms_dbfs, 2), target=dbfs, weight=weight, tolerance=tol_db,
            detail=f"rms {r.rms_dbfs:.1f} dBFS vs expected {dbfs:.1f} dBFS ({r.rms_dbfs - dbfs:+.1f} dB)",
            pd_hint=None if passed else f"adjust the output gain by {dbfs - r.rms_dbfs:+.1f} dB",
        )
    return Expectation("level", "graded", weight, ev)


def tonal(max_flatness: float = 0.1, weight: float = 1.0) -> Expectation:
    def ev(r: Report) -> Score:
        passed = r.flatness <= max_flatness
        return Score(
            field="tonal", kind="graded", value=linear_ramp(r.flatness, max_flatness), passed=passed,
            measured=round(r.flatness, 3), target=f"flatness <= {max_flatness}", weight=weight,
            tolerance=max_flatness, detail=f"spectral flatness {r.flatness:.3f} (0=pure tone, 1=noise); timbre '{r.timbre}'",
            pd_hint=None if passed else "output is noisier than expected; check for aliasing or an unintended noise source",
        )
    return Expectation("tonal", "graded", weight, ev)


def noisy(min_flatness: float = 0.5, weight: float = 1.0) -> Expectation:
    def ev(r: Report) -> Score:
        passed = r.flatness >= min_flatness
        err = max(0.0, min_flatness - r.flatness)
        return Score(
            field="noisy", kind="graded", value=linear_ramp(err, min_flatness), passed=passed,
            measured=round(r.flatness, 3), target=f"flatness >= {min_flatness}", weight=weight,
            tolerance=min_flatness, detail=f"spectral flatness {r.flatness:.3f}; timbre '{r.timbre}'",
            pd_hint=None if passed else "output is more tonal than expected; a noise source may be missing",
        )
    return Expectation("noisy", "graded", weight, ev)


def _reference_report(reference) -> Report:
    """Resolve a reference into an analysis Report. Accepts a Report, an
    AudioBuffer, a .wav path, a .pd patch path, or raw patch text. Any rendering
    happens here (at construction time), so score() stays Pd-free."""
    from pathlib import Path

    from .analyze import analyze
    from .audio import AudioBuffer

    if isinstance(reference, Report):
        return reference
    if isinstance(reference, AudioBuffer):
        return analyze(reference)
    if isinstance(reference, str) and "#N canvas" in reference:
        from .render import render

        return analyze(render(reference).audio)
    p = Path(str(reference))
    if p.suffix.lower() == ".wav":
        from .wavio import read_wav

        return analyze(read_wav(p))
    from .render import render

    return analyze(render(str(p)).audio)


def matches_reference(reference, tol: float = 0.2, weight: float = 1.0) -> Expectation:
    """Graded: how close the patch sounds to ``reference`` (a Report, AudioBuffer,
    .wav, or .pd). Scored by timbre-fingerprint similarity; the hint says how to
    close the gap."""
    ref = _reference_report(reference)

    def ev(r: Report) -> Score:
        from .compare import compare

        comp = compare(r, ref)
        dist = 1.0 - comp.similarity
        passed = dist <= tol
        detail = f"{comp.similarity * 100:.0f}% timbre match to reference"
        if comp.diffs:
            detail += " — " + "; ".join(comp.diffs)
        return Score(
            field="matches_reference", kind="graded", value=linear_ramp(dist, tol), passed=passed,
            measured=round(comp.similarity, 3), target=f">= {1 - tol:.2f} similarity",
            weight=weight, tolerance=tol, detail=detail,
            pd_hint=(comp.diffs[0] if comp.diffs else None),
        )

    return Expectation("matches_reference", "graded", weight, ev)


def centroid(hz: float, tol: float = 0.2, rel: bool = True, weight: float = 1.0) -> Expectation:
    def ev(r: Report) -> Score:
        tol_abs = hz * tol if rel else tol
        err = abs(r.centroid_hz - hz)
        passed = err <= tol_abs
        return Score(
            field="centroid", kind="graded", value=linear_ramp(err, tol_abs), passed=passed,
            measured=round(r.centroid_hz, 1), target=hz, weight=weight, tolerance=tol_abs,
            detail=f"spectral centroid {r.centroid_hz:.0f} Hz vs expected {hz:.0f} Hz",
            pd_hint=None if passed else ("brighten the tone" if r.centroid_hz < hz else "darken the tone / add a lowpass"),
        )
    return Expectation("centroid", "graded", weight, ev)
