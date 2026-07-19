"""Scoring and expectation tests. Mostly Pd-free (synthetic signals)."""

import numpy as np
import pytest

from pdverify import analyze, expect, score
from pdverify.audio import AudioBuffer
from pdverify.features.pitch import note_to_hz
from pdverify.score import linear_ramp

SR = 44100


def _sine(freq, amp=0.5, dur=1.0, sr=SR):
    t = np.arange(int(sr * dur)) / sr
    return AudioBuffer(amp * np.sin(2 * np.pi * freq * t), sr)


def test_note_to_hz():
    assert note_to_hz("A4") == pytest.approx(440.0)
    assert note_to_hz("C4") == pytest.approx(261.63, abs=0.01)
    assert note_to_hz("A#4") == pytest.approx(466.16, abs=0.01)
    assert note_to_hz("Bb4") == pytest.approx(466.16, abs=0.01)
    assert note_to_hz("A5") == pytest.approx(880.0)


def test_linear_ramp_curve():
    assert linear_ramp(0, 10) == 1.0
    assert linear_ramp(10, 10) == pytest.approx(0.5)
    assert linear_ramp(20, 10) == 0.0
    assert linear_ramp(100, 10) == 0.0


def test_correct_note_passes():
    r = analyze(_sine(440))
    card = score(r, [expect.not_silent(), expect.no_clipping(), expect.note("A4")])
    assert card.passed
    assert card.gates_passed
    assert card.total == pytest.approx(1.0, abs=0.05)


def test_wrong_note_fails_with_hint():
    r = analyze(_sine(440))
    card = score(r, [expect.note("E5", tol_cents=30)])  # 659.26 Hz, way off
    assert not card.passed
    note_score = next(s for s in card.scores if s.field == "note")
    assert not note_score.passed
    assert note_score.pd_hint is not None
    assert "scale the oscillator frequency" in note_score.pd_hint


def test_octave_error_named_in_feedback():
    r = analyze(_sine(440))
    card = score(r, [expect.pitch(880, tol_cents=20)])  # measured is an octave below target
    s = card.scores[0]
    assert "octave down" in s.detail


def test_silence_gate_zeroes_total():
    r = analyze(AudioBuffer(np.zeros(SR), SR))
    card = score(r, [expect.not_silent(), expect.note("A4")])
    assert not card.gates_passed
    assert card.total == 0.0
    # even though we couldn't even test pitch, the verdict is unambiguous
    assert card.verdict() == "GATE FAIL"


def test_clipping_gate():
    r = analyze(AudioBuffer(np.ones(SR), SR))
    card = score(r, [expect.no_clipping()])
    assert not card.gates_passed


def test_tonal_vs_noisy():
    tone = analyze(_sine(440))
    rng = np.random.default_rng(1)
    noise = analyze(AudioBuffer(0.3 * rng.standard_normal(SR), SR))
    assert score(tone, [expect.tonal()]).passed
    assert not score(noise, [expect.tonal()]).passed
    assert score(noise, [expect.noisy()]).passed


def test_weighted_mean_aggregation():
    r = analyze(_sine(440))
    # one perfect (note) + one failing (level way off) with equal weight
    card = score(r, [expect.note("A4", weight=1.0), expect.level(-40, tol_db=1.0, weight=1.0)])
    # note ~1.0, level ~0.0 -> total around 0.5, and overall not passed
    assert 0.3 < card.total < 0.7
    assert not card.passed


def test_scorecard_json_roundtrips():
    r = analyze(_sine(440))
    card = score(r, [expect.note("A4")])
    import json

    d = json.loads(card.to_json())
    assert d["passed"] is True
    assert "analysis" in d and "scores" in d


# --- end-to-end (needs Pd) --------------------------------------------------

def _pd_available() -> bool:
    from pdverify.errors import PdNotFound
    from pdverify.pd_locate import discover

    try:
        discover()
        return True
    except PdNotFound:
        return False


@pytest.mark.skipif(not _pd_available(), reason="no Pure Data binary found")
def test_verify_end_to_end():
    from pathlib import Path

    from pdverify import verify
    from pdverify.render import RenderSpec

    fix = Path(__file__).parent / "fixtures" / "sine440.pd"
    card = verify(str(fix), [expect.not_silent(), expect.no_clipping(), expect.note("A4")], spec=RenderSpec(duration=1.0))
    assert card.passed
    assert card.meta["pd_version"]
