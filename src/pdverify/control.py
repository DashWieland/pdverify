"""Control events to drive a patch during a render.

Many patches are instruments: silent until something sends them a note, a gate,
or a parameter. These builders describe timed control input that the renderer
schedules into the patch, so pdverify can hear what an instrument actually does
when played — not just the silence it makes on its own.

    from pdverify import control, render
    from pdverify.render import RenderSpec

    controls = (
        control.note("C4", at=0.0, dur=1.0)
        + control.note("E4", at=1.0, dur=1.0)
        + control.send("cutoff", 2000)
    )
    render("synth.pd", RenderSpec(duration=3.0, controls=controls))

`send`/`bang` target any `[receive <name>]` in the patch. `note` drives a
`[notein]` (which the renderer rewrites to a message-driven shim), emitting a
note-on then a note-off.
"""

from __future__ import annotations

from dataclasses import dataclass

# receiver the pdverify_notein shim listens on
NOTE_RECEIVER = "pdverify_note"


@dataclass(frozen=True)
class Control:
    """A single message to a named receiver at time ``at`` (seconds)."""

    at: float
    receiver: str
    atoms: tuple


def send(receiver: str, *atoms, at: float = 0.0) -> list[Control]:
    """Send ``atoms`` (floats/symbols) to ``[receive receiver]`` at time ``at``."""
    return [Control(float(at), receiver, tuple(atoms))]


def bang(receiver: str, at: float = 0.0) -> list[Control]:
    """Send a bang to ``[receive receiver]`` at time ``at``."""
    return [Control(float(at), receiver, ("bang",))]


def note(pitch, at: float = 0.0, dur: float = 0.5, velocity: int = 100) -> list[Control]:
    """Play a MIDI note into the patch's ``[notein]``: note-on at ``at``, note-off
    ``dur`` seconds later. ``pitch`` is a note name ('C4') or a MIDI number."""
    from .features.pitch import note_to_midi

    midi = int(pitch) if isinstance(pitch, (int, float)) else note_to_midi(pitch)
    return [
        Control(float(at), NOTE_RECEIVER, (midi, int(velocity))),
        Control(float(at + dur), NOTE_RECEIVER, (midi, 0)),
    ]


def has_notes(controls) -> bool:
    return any(c.receiver == NOTE_RECEIVER for c in controls)
