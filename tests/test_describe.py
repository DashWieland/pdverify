"""Perceptual-description tests. No Pd required."""

import numpy as np

from pdverify import analyze
from pdverify.audio import AudioBuffer
from pdverify.describe import brightness, describe, descriptors

SR = 44100


def _sine(freq, amp=0.5, dur=1.0):
    t = np.arange(int(SR * dur)) / SR
    return AudioBuffer(amp * np.sin(2 * np.pi * freq * t), SR)


def test_pure_sine_tags():
    tags = descriptors(analyze(_sine(440)))
    assert "pure" in tags
    assert "steady" in tags
    assert any("A4" in t for t in tags)


def test_article_agrees_with_first_word():
    # no "A evolving" / "A airy": the article must match the first word's sound
    for freq in (60, 440, 3000, 9000):
        d = describe(analyze(_sine(freq)))
        first, second = d.split()[0], d.split()[1]
        assert (first == "An") == (second[0].lower() in "aeiou"), d


def test_low_tone_reads_dark_and_bassy():
    r = analyze(_sine(60))
    assert brightness(r) == "dark"
    assert "bass-heavy" in descriptors(r) or "sub-heavy" in descriptors(r)


def test_midrange_sine_not_labelled_bassy():
    # a 440 Hz tone is midrange, not "bass-heavy" (the 250-500 band is not bass)
    tags = descriptors(analyze(_sine(440)))
    assert "bass-heavy" not in tags and "sub-heavy" not in tags


def test_high_tone_reads_bright():
    assert brightness(analyze(_sine(9000))) in ("bright", "brilliant")


def test_noise_reads_noisy_no_pitch():
    rng = np.random.default_rng(0)
    tags = descriptors(analyze(AudioBuffer(0.3 * rng.standard_normal(SR), SR)))
    assert "noisy" in tags


def test_silent_describes_silent():
    assert "Silent" in describe(analyze(AudioBuffer(np.zeros(SR), SR)))
