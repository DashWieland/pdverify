"""Visualization tests. Skipped unless the [plot] extra (matplotlib) is present."""

import numpy as np
import pytest

matplotlib = pytest.importorskip("matplotlib")

from pdverify.audio import AudioBuffer
from pdverify import viz

SR = 44100


def _sine(freq, amp=0.5, dur=0.5):
    t = np.arange(int(SR * dur)) / SR
    return AudioBuffer(amp * np.sin(2 * np.pi * freq * t), SR)


def test_spectrogram_writes_png(tmp_path):
    out = viz.spectrogram(_sine(440), tmp_path / "s.png", title="test")
    assert out.exists() and out.stat().st_size > 0


def test_spectrum_writes_png(tmp_path):
    out = viz.spectrum(_sine(440), tmp_path / "spec.png")
    assert out.exists() and out.stat().st_size > 0
