"""Reference-matching tests. No Pd required (synthetic audio)."""

import numpy as np
import pytest

from pdverify import analyze, compare, expect, score
from pdverify.audio import AudioBuffer

SR = 44100


def _sine(freq, amp=0.5, dur=1.0):
    t = np.arange(int(SR * dur)) / SR
    return AudioBuffer(amp * np.sin(2 * np.pi * freq * t), SR)


def _noise(amp=0.3, seed=0):
    return AudioBuffer(amp * np.random.default_rng(seed).standard_normal(SR), SR)


def test_identical_audio_is_full_match():
    a = analyze(_sine(440))
    comp = compare(a, a)
    assert comp.similarity > 0.99
    assert comp.diffs == []


def test_sine_vs_noise_is_low_match():
    comp = compare(analyze(_sine(440)), analyze(_noise()))
    assert comp.similarity < 0.6


def test_pitch_gap_reported_with_direction():
    comp = compare(analyze(_sine(440)), analyze(_sine(880)))  # target an octave up
    assert comp.similarity < 0.99
    joined = " ".join(comp.diffs)
    assert "pitch" in joined or "brighter" in joined


def test_missing_high_end_suggested():
    low = analyze(_sine(150))  # candidate: low body only
    bright = analyze(_sine(9000))  # target: high content
    comp = compare(low, bright)
    joined = " ".join(comp.diffs)
    assert "high-frequency" in joined or "brighter" in joined


def test_level_gap_reported():
    quiet = analyze(_sine(440, amp=0.1))
    loud = analyze(_sine(440, amp=0.8))
    comp = compare(quiet, loud)  # target is louder
    assert any("raise" in d for d in comp.diffs)


def test_matches_reference_expectation_passes_on_self():
    ref = _sine(440)
    card = score(analyze(ref), [expect.matches_reference(ref, tol=0.15)])
    assert card.passed


def test_matches_reference_fails_on_mismatch():
    card = score(analyze(_noise()), [expect.matches_reference(_sine(440), tol=0.15)])
    assert not card.passed
    s = card.scores[0]
    assert s.field == "matches_reference"
    assert 0.0 <= s.value <= 1.0


def test_reference_accepts_wav_path(tmp_path):
    import wave

    ref = _sine(330)
    path = tmp_path / "ref.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((ref.mono() * 32767).astype("<i2").tobytes())
    exp = expect.matches_reference(str(path), tol=0.2)
    card = score(analyze(_sine(330)), [exp])
    assert card.passed
