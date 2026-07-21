# pdverify

Render a Pure Data patch to audio without the GUI, then describe what it produced — in plain language, not just numbers.

Several tools now let a language model build Pd patches — MCP servers that add objects and connect them over FUDI or OSC. They check whether a patch loads, not whether it makes the intended sound, and a patch can load cleanly while being silent, an octave off, or clipping. pdverify checks the audio. Give it a `.pd` file; it renders the patch offline (about 40 times faster than real time), analyzes the output, and tells you what came out. Its only dependency beyond the Python standard library is NumPy.

```console
$ pdverify analyze fmdrone.pd
duration    8.000s  44100 Hz  2ch
level       peak -6.79 dBFS   rms -15.95 dBFS   crest 2.87
pitch       196.54 Hz -> G3 (+5 cents)  conf 0.08
spectrum    centroid 2994 Hz   rolloff 852 Hz   flatness 0.000  -> inharmonic
bands       sub 17%  bass 23%  low_mid 36%  mid 12%  high_mid 0%  presence 0%  brilliance 13%
partials    196 Hz, 327 Hz, 262 Hz, 590 Hz, 393 Hz, 130 Hz
motion      evolving
integrity   silent=False  clipped=False  nan/inf=False  dc=-0.0352

sounds like: An evolving, dark, sub-heavy chord with hollow, scooped mids, an airy
             high-frequency haze, and no single clear pitch.
tags:        evolving, dark, sub-heavy, hollow mids, airy high end, chordal, no clear pitch
```

The `sounds like` line and `tags` are the point: an agent (or a person) gets a usable description of the sound without reading a spectrogram or knowing what a kilohertz is. For a visual, `pdverify spectrogram my_patch.pd -o out.png` (needs `pip install pdverify[plot]`).

## How it fits with the patch-building tools

pdverify reads patches; it does not build or change them. Its input is a `.pd` file, which every existing construction tool can already write, so it runs alongside any of them: build a patch with whatever MCP server you use, save the `.pd`, and run pdverify on the result.

```console
$ pdverify analyze build.pd --json
```

The analysis code (`pdverify.analyze`) imports neither Pd nor the renderer. It works on an audio buffer, so the same code can grade a "make this sound" benchmark later.

## Checking against an expectation

`analyze` reports what a patch sounds like; `assert` checks it against what you asked for and sets an exit code, so it drops into a build-and-check loop.

```console
$ pdverify assert build.pd --note A4 --tonal --no-clip
PASS — score 1.00
  a sine tone at 440.0 Hz (A4, +0 cents); peak -12.0 dBFS, rms -15.1 dBFS over 3.00s.

$ pdverify assert build.pd --note C5        # patch actually produces A4
FAIL — score 0.00
  - note: got 440.0 Hz (A4), expected 523.3 Hz (C5): -300 cents  → scale the oscillator frequency by 1.189 (e.g. [osc~ 523])
```

Checks come in two tiers. Gates — silence, clipping, non-finite output — are pass/fail, and a failed gate forces the score to 0. Graded checks — pitch, level, spectral shape — each yield a value between 0 and 1 through a tolerance curve, combined into the overall score. The same call returns a boolean verdict for a yes/no gate and a continuous score for ranking, which is what lets one function serve both a live check and a benchmark grade.

From Python:

```python
from pdverify import verify, expect

card = verify("build.pd", [
    expect.not_silent(), expect.no_clipping(),
    expect.note("A4", tol_cents=30, weight=2.0),
    expect.tonal(),
])
print(card.passed, card.total)   # True 1.0
print(card.feedback())           # verdict + the worst failing checks, with fixes
```

## Playing instruments

Many patches are instruments — silent until something sends them a note or a
parameter. Drive them during the render so pdverify hears what they actually do:

```console
$ pdverify analyze synth.pd --play-note C4      # plays a MIDI note into [notein]
```

```python
from pdverify import render, analyze, control
from pdverify.render import RenderSpec

controls = control.note("C4", dur=1.0) + control.note("E4", at=1.0) + control.send("cutoff", 2000)
report = analyze(render("synth.pd", RenderSpec(duration=3.0, controls=controls)).audio)
```

`note` drives the patch's `[notein]`; `send`/`bang` reach any `[receive <name>]`.

## Matching a reference — "make it sound like this"

The one goal that turns a subjective target into an objective score. Point it at
a reference (a `.wav` or another `.pd`) and it scores the timbre similarity and
says how to close the gap:

```console
$ pdverify compare my_attempt.pd --ref target.wav
47% match to the reference. To close the gap: reduce bass; add low-mid body;
target is 'evolving', yours is 'steady'.
```

The similarity is a climbable gradient (a closer patch scores higher), and
`expect.matches_reference(ref)` plugs it into the same scored expectations as
everything else — so "sound like this" becomes a checkable, gradeable goal.

## Install

```console
$ pip install pdverify        # Python 3.11+ and NumPy
```

You also need Pure Data at runtime — the free [vanilla Pd](https://puredata.info/downloads), either as `pd` on your PATH or pointed to by the `PDVERIFY_PD` environment variable. To check the install and the capture pipeline:

```console
$ pdverify doctor
```

## Python API

```python
from pdverify import render, analyze

result = render("build.pd")          # RenderResult; raises if it cannot capture audio
report = analyze(result.audio)       # Report; pure NumPy

print(report.f0_hz, report.note)     # 440.0  A4
print(report.summary())
```

## How capture works

Recording an arbitrary patch runs into two problems, and pdverify handles both.

The first is that you cannot capture the built-in `[dac~]` in a headless render, and you cannot replace it by placing a same-named abstraction on the search path — Pd uses the built-in and ignores the file, so the render comes out silent. Instead, pdverify copies the patch and rewrites the class name of each `[dac~]` box to `[pdverify_sink~]`, an abstraction that taps the signal. That changes one word per `[dac~]` and leaves every object index and `#X connect` line untouched, which avoids the index renumbering that breaks machine-edited patches. Multiple `[dac~]` objects mix onto one bus through `[throw~]`/`[catch~]`, the way Pd already mixes them.

The second is that a failed render should not be read as silence. A missing external, a patch with no output object, or a nonzero exit from Pd each raise a specific error — `PdNotFound`, `NoSinkFound`, or `RenderFailed` — rather than returning an empty buffer that a caller might score as a quiet patch.

## Status

Early, but the core is real and working:

- **render** — headless offline capture (~40× realtime)
- **analyze** — pitch, level, integrity gates, spectral bands + partials, motion,
  and a plain-language description
- **assert / verify** — scored expectations (gated + graded) with corrective feedback
- **compare** — reference matching ("make it sound like this")
- **control injection** — play instruments with notes/messages during the render
- **spectrogram** — PNG output (`[plot]` extra)

Validated end-to-end against a real construction MCP in a build → hear → fix loop
(see [`examples/loop_with_construction_mcp.md`](examples/loop_with_construction_mcp.md)).

Planned next:

- **M2** — `pdverify.bench`: a task format and runner, so the same scoring code grades a shared "make this sound" benchmark.
- Deeper repair feedback (past pitch), broader control (MIDI CC, arrays), and hardening the perceptual descriptors against a wider corpus.

Later: attack/decay envelopes, presence-of-harmonics checks, control-input
injection for patches driven by notes or triggers, and reference-audio matching.

## License

MIT.
