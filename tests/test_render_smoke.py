"""End-to-end render tests. Skipped automatically if no Pd binary is found."""

from pathlib import Path

import pytest

from pdverify import analyze, render
from pdverify.errors import NoSinkFound, PdNotFound
from pdverify.render import RenderSpec

FIX = Path(__file__).parent / "fixtures"


def _pd_available() -> bool:
    from pdverify.pd_locate import discover

    try:
        discover()
        return True
    except PdNotFound:
        return False


pytestmark = pytest.mark.skipif(not _pd_available(), reason="no Pure Data binary found")

SPEC = RenderSpec(duration=1.0)


def test_render_sine440():
    result = render(str(FIX / "sine440.pd"), SPEC)
    r = analyze(result.audio)
    assert not r.is_silent
    assert r.f0_hz == pytest.approx(440, abs=2.0)
    assert r.note == "A4"
    assert result.soundfiler_peak == pytest.approx(0.25, abs=0.01)


def test_render_noise_is_noisy():
    r = analyze(render(str(FIX / "noise.pd"), SPEC).audio)
    assert not r.is_silent
    assert r.timbre == "noise"
    assert r.flatness > 0.2


def test_silence_patch_is_silent_not_error():
    # dac~ present but nothing wired to it: a real, capturable silence — must NOT
    # raise NoSinkFound, and must be reported as silent.
    r = analyze(render(str(FIX / "silence.pd"), SPEC).audio)
    assert r.is_silent


def test_nosink_raises():
    with pytest.raises(NoSinkFound):
        render(str(FIX / "nosink.pd"), SPEC)


def test_over_unity_patch_detected_as_clipping():
    # osc~ * 8 exceeds full scale; soundfiler normalizes on write, but render()
    # recovers the true level so the clip is caught rather than hidden.
    text = (
        "#N canvas 0 0 300 200 12;\n"
        "#X obj 40 40 osc~ 440;\n#X obj 40 80 *~ 8;\n#X obj 40 130 dac~;\n"
        "#X connect 0 0 1 0;\n#X connect 1 0 2 0;\n#X connect 1 0 2 1;\n"
    )
    result = render(text, SPEC)
    assert result.soundfiler_peak == pytest.approx(8.0, abs=0.1)
    assert analyze(result.audio).is_clipped


def test_raw_patch_text_accepted():
    text = (
        "#N canvas 0 0 300 200 12;\n"
        "#X obj 40 40 osc~ 220;\n#X obj 40 80 *~ 0.2;\n#X obj 40 130 dac~;\n"
        "#X connect 0 0 1 0;\n#X connect 1 0 2 0;\n"
    )
    r = analyze(render(text, SPEC).audio)
    assert r.f0_hz == pytest.approx(220, abs=2.0)
