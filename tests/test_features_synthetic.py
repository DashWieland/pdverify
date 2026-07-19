"""Feature tests on synthetic numpy signals. No Pd required — this is the core
the benchmark scorer will lean on, so it must be correct in isolation."""

import numpy as np
import pytest

from pdverify import analyze
from pdverify.audio import AudioBuffer

SR = 44100


def _sine(freq, amp, dur=1.0, sr=SR):
    t = np.arange(int(sr * dur)) / sr
    return amp * np.sin(2 * np.pi * freq * t)


def test_sine_level_and_pitch():
    r = analyze(AudioBuffer(_sine(440, 0.5), SR))
    assert not r.is_silent and not r.is_clipped and not r.has_nan_inf
    assert r.f0_hz == pytest.approx(440, abs=1.0)
    assert r.note == "A4"
    assert abs(r.cents_error) < 10
    assert r.peak_dbfs == pytest.approx(-6.02, abs=0.2)   # 0.5 -> -6 dBFS
    assert r.rms_dbfs == pytest.approx(-9.03, abs=0.2)    # 0.5/sqrt(2)
    assert r.flatness < 0.05
    assert r.timbre == "sine"


def test_note_naming_a4_c4():
    assert analyze(AudioBuffer(_sine(261.63, 0.4), SR)).note == "C4"
    assert analyze(AudioBuffer(_sine(440.0, 0.4), SR)).note == "A4"


def test_white_noise_is_noisy():
    rng = np.random.default_rng(0)
    x = 0.3 * rng.standard_normal(SR)
    r = analyze(AudioBuffer(x, SR))
    assert r.flatness > 0.2
    assert r.timbre == "noise"


def test_silence_detected():
    r = analyze(AudioBuffer(np.zeros(SR), SR))
    assert r.is_silent
    assert r.f0_hz is None


def test_clipping_detected():
    x = np.ones(SR)  # pinned at full scale
    r = analyze(AudioBuffer(x, SR))
    assert r.is_clipped


def test_clipping_detected_stereo():
    # a 2-D (frames x channels) buffer is what render() actually produces;
    # is_clipped must handle it without choking on array truthiness.
    left = _sine(440, 0.5)
    right = np.ones(SR)  # clipped channel
    buf = AudioBuffer(np.stack([left, right], axis=1), SR)
    assert analyze(buf).is_clipped


def test_isolated_full_scale_sample_is_not_clipping():
    x = _sine(440, 0.5)
    x[123] = 1.0  # a single grazing sample, not a run
    assert not analyze(AudioBuffer(x, SR)).is_clipped


def test_over_unity_is_clipping():
    # render() hands analyze a true-scale signal that can exceed +/-1; dac~ would
    # clip it on playback, so it must be flagged.
    r = analyze(AudioBuffer(_sine(440, 2.0), SR))
    assert r.is_clipped
    assert r.peak_dbfs > 0.0


def test_full_scale_sine_not_clipping():
    r = analyze(AudioBuffer(_sine(440, 1.0), SR))
    assert not r.is_clipped
    assert r.peak_dbfs == pytest.approx(0.0, abs=0.1)


def test_nan_detected():
    x = _sine(440, 0.5)
    x[100] = np.nan
    r = analyze(AudioBuffer(x, SR))
    assert r.has_nan_inf


def test_dc_offset_measured():
    x = np.full(SR, 0.5)
    r = analyze(AudioBuffer(x, SR))
    assert r.dc_offset == pytest.approx(0.5, abs=1e-3)


def test_band_energies_locate_tone():
    # a 100 Hz tone lands in 'bass'; a 10 kHz tone lands in 'brilliance'
    low = analyze(AudioBuffer(_sine(100, 0.5), SR)).bands
    high = analyze(AudioBuffer(_sine(10000, 0.5), SR)).bands
    assert max(low, key=low.get) == "bass"
    assert max(high, key=high.get) == "brilliance"
    assert abs(sum(low.values()) - 1.0) < 0.05


def test_bands_cover_full_spectrum():
    # bands must partition all energy (incl. DC/subsonic and near-Nyquist), so
    # the fractions always sum to ~1 with no hidden gap.
    rng = np.random.default_rng(3)
    x = _sine(80, 0.4) + 0.2 * rng.standard_normal(SR)  # low tone + broadband
    total = sum(analyze(AudioBuffer(x, SR)).bands.values())
    assert abs(total - 1.0) < 0.02


def test_top_partials_finds_fundamental():
    parts = analyze(AudioBuffer(_sine(440, 0.5), SR)).top_partials
    assert parts
    assert abs(parts[0] - 440) < 3


def test_centroid_not_fooled_by_noise_floor():
    # a strong low tone plus a faint broadband floor (like 16-bit quantization)
    # must still report a LOW centroid — power weighting, not magnitude.
    rng = np.random.default_rng(2)
    x = _sine(200, 0.5) + 3e-4 * rng.standard_normal(SR)  # floor ~ -70 dB
    c = analyze(AudioBuffer(x, SR)).centroid_hz
    assert c < 1000, f"centroid {c} Hz pulled up by the noise floor"


def test_centroid_high_for_high_tone():
    assert analyze(AudioBuffer(_sine(8000, 0.5), SR)).centroid_hz > 5000


def test_stereo_buffer_pitch():
    left = _sine(330, 0.4)
    right = _sine(330, 0.4)
    buf = AudioBuffer(np.stack([left, right], axis=1), SR)
    r = analyze(buf)
    assert r.channels == 2
    assert r.f0_hz == pytest.approx(330, abs=1.0)
