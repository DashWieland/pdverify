"""Generate the recorder-wrapper patch.

The wrapper is authored entirely by pdverify (never by an LLM), so its object
indices and ``#X connect`` lines are fixed and correct by construction. It:

  1. sums the tapped audio bus with ``[catch~]`` into two recording arrays,
  2. on load, turns DSP on *first*, then arms ``[tabwrite~]`` to record,
  3. after the capture window, writes the arrays to a WAV with ``[soundfiler]``
     (synchronous — never ``[writesf~]``, whose disk thread races the batch
     scheduler and yields an empty file),
  4. quits Pd so the ``-batch`` process terminates.

The ``[loadbang]`` fans out through ``[t b b b]`` which fires right-to-left, so
the ordering (dsp on -> start recording -> start timer) is guaranteed.
"""

from __future__ import annotations

from pathlib import Path

BUS_L = "pdverify_busL"
BUS_R = "pdverify_busR"
ARR_L = "pdverify_outL"
ARR_R = "pdverify_outR"


# small settle so control events never fire before DSP is on
_WARMUP_MS = 15


def _fmt_atom(a) -> str:
    if isinstance(a, float) and a.is_integer():
        return str(int(a))
    return str(a)


def build_wrapper(out_wav: str | Path, n_frames: int, sr: int, tail: float = 0.4, controls=()) -> str:
    """Return the .pd text for a recorder wrapper capturing ``n_frames`` samples
    and writing them to ``out_wav`` (an absolute path).

    ``controls`` is an iterable of Control events; each becomes a
    ``[del t] -> [; receiver atoms(`` chain fired from loadbang, so the patch is
    played during the render."""
    # soundfiler resolves relative paths against the containing canvas's dir, so
    # the caller must pass an absolute path; Pd accepts forward slashes on Windows.
    wav = Path(out_wav).as_posix()
    dur_ms = int(round(n_frames / sr * 1000)) + int(round(tail * 1000))

    lines = [
        "#N canvas 0 0 560 420 12;",
        f"#X obj 30 30 catch~ {BUS_L};",
        f"#X obj 190 30 catch~ {BUS_R};",
        f"#X obj 30 90 tabwrite~ {ARR_L};",
        f"#X obj 190 90 tabwrite~ {ARR_R};",
        "#X obj 330 30 loadbang;",
        "#X obj 330 70 t b b b;",
        "#X msg 470 110 \\; pd dsp 1;",
        f"#X obj 330 130 del {dur_ms};",
        "#X obj 330 180 t b b;",
        f"#X msg 330 220 write -wave {wav} {ARR_L} {ARR_R};",
        "#X obj 330 290 soundfiler;",
        "#X obj 490 220 del 100;",
        "#X msg 490 260 \\; pd quit;",
        f"#X obj 30 150 table {ARR_L} {n_frames};",
        f"#X obj 190 150 table {ARR_R} {n_frames};",
        "#X connect 0 0 2 0;",
        "#X connect 1 0 3 0;",
        "#X connect 4 0 5 0;",
        "#X connect 5 2 6 0;",
        "#X connect 5 1 2 0;",
        "#X connect 5 1 3 0;",
        "#X connect 5 0 7 0;",
        "#X connect 7 0 8 0;",
        "#X connect 8 1 9 0;",
        "#X connect 8 0 11 0;",
        "#X connect 9 0 10 0;",
        "#X connect 11 0 12 0;",
    ]

    # loadbang is object index 4; append a [del t] -> [; receiver atoms( per event
    idx = 15
    y = 340
    for c in controls:
        t_ms = max(0, int(round(c.at * 1000)) + _WARMUP_MS)
        atoms = " ".join(_fmt_atom(a) for a in c.atoms)
        lines.append(f"#X obj 30 {y} del {t_ms};")
        lines.append(f"#X msg 30 {y + 25} \\; {c.receiver} {atoms};")
        lines.append(f"#X connect 4 0 {idx} 0;")
        lines.append(f"#X connect {idx} 0 {idx + 1} 0;")
        idx += 2
        y += 55

    return "\n".join(lines) + "\n"
