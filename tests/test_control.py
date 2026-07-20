"""Control-injection tests. Builders/rewrite are Pd-free; the drive tests skip
without Pd."""

from pathlib import Path

import pytest

from pdverify import analyze, control
from pdverify.control import Control, has_notes
from pdverify.errors import PdNotFound
from pdverify.features.pitch import note_to_midi
from pdverify.rewrite import rewrite_notein

FIX = Path(__file__).parent / "fixtures"


def test_note_to_midi():
    assert note_to_midi("C4") == 60
    assert note_to_midi("A4") == 69
    assert note_to_midi("A5") == 81


def test_note_builder_emits_on_then_off():
    evs = control.note("C4", at=0.0, dur=1.0, velocity=100)
    assert len(evs) == 2
    assert evs[0].atoms == (60, 100)  # note-on
    assert evs[1].atoms == (60, 0) and evs[1].at == 1.0  # note-off
    assert has_notes(evs)


def test_send_and_bang_builders():
    assert control.send("cutoff", 2000, at=0.5) == [Control(0.5, "cutoff", (2000,))]
    assert control.bang("trig")[0].atoms == ("bang",)
    assert not has_notes(control.send("cutoff", 2000))


def test_rewrite_notein():
    out, n = rewrite_notein("#X obj 10 10 notein;\n")
    assert n == 1 and "pdverify_notein" in out
    out, n = rewrite_notein("#X obj 10 10 notein 1;\n")  # channel arg dropped
    assert n == 1 and "pdverify_notein" in out and "notein 1" not in out
    out, n = rewrite_notein("#X text 5 5 use notein here;\n")  # comment untouched
    assert n == 0


def _pd_available() -> bool:
    from pdverify.pd_locate import discover

    try:
        discover()
        return True
    except PdNotFound:
        return False


pytestmark = pytest.mark.skipif(not _pd_available(), reason="no Pure Data binary found")


def test_drive_receive_synth():
    from pdverify.render import RenderSpec, render

    r = analyze(render(str(FIX / "recv_synth.pd"), RenderSpec(duration=1.0, controls=tuple(control.send("testfreq", 330)))).audio)
    assert r.f0_hz == pytest.approx(330, abs=2)


def test_play_midi_note_into_notein():
    from pdverify.render import RenderSpec, render

    r = analyze(render(str(FIX / "midi_synth.pd"), RenderSpec(duration=1.0, controls=tuple(control.note("A4", dur=0.9)))).audio)
    assert r.f0_hz == pytest.approx(440, abs=3)
    assert r.note == "A4"


def test_undriven_instrument_makes_no_pitch():
    # a notein synth with no note played should not report a confident pitch
    from pdverify.render import RenderSpec, render

    r = analyze(render(str(FIX / "midi_synth.pd"), RenderSpec(duration=1.0)).audio)
    assert r.pitch_confidence < 0.5 or r.f0_hz is None
