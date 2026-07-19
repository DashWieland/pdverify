# pdverify

**Render a Pure Data patch headless and verify what it actually sounds like.**

There is a small, growing family of tools that let an LLM *construct* Pure Data
patches — MCP servers that add objects and wire them together over FUDI or OSC.
They almost all stop at the same place: "the patch loaded without console
errors." None of them *listen*. So an agent building a patch is flying blind —
it can produce a graph that loads fine and is silent, detuned, or clipping, and
never know.

`pdverify` closes that loop. Give it a `.pd` file; it renders the patch to audio
offline (about 40× faster than real time), analyzes the result, and tells you
what came out — pitch, level, timbre, and signal health — with zero native
dependencies beyond NumPy.

```console
$ pdverify analyze my_patch.pd
duration    3.000s  44100 Hz  2ch
level       peak -12.04 dBFS   rms -15.05 dBFS   crest 1.41
pitch       440.00 Hz -> A4 (+0 cents)  conf 0.98
spectrum    centroid 441 Hz   rolloff 441 Hz   flatness 0.000  -> sine
integrity   silent=False  clipped=False  nan/inf=False  dc=+0.0000

a sine tone at 440.0 Hz (A4, +0 cents); peak -12.0 dBFS, rms -15.1 dBFS over 3.00s.
```

## Why it composes

`pdverify` **verifies**; it never constructs. Its only input is a `.pd` file on
disk — which every existing construction harness can already produce. So it sits
downstream of all of them without their cooperation: an agent builds a patch
with whatever MCP server it likes, exports the `.pd`, and shells

```console
$ pdverify analyze build.pd --json
```

to get a structured report back. The analysis core (`pdverify.analyze`) has no
dependency on Pd or the renderer, so it is also the scoring engine a
"make-this-sound" benchmark can import directly.

## Install

```console
$ pip install pdverify        # needs Python 3.11+ and NumPy
```

You also need Pure Data itself at runtime (the free, open-source
[vanilla Pd](https://puredata.info/downloads); `pd` on your PATH, or point
`PDVERIFY_PD` at the binary). Check your setup:

```console
$ pdverify doctor
```

## Use it from Python

```python
from pdverify import render, analyze

result = render("build.pd")          # -> RenderResult (raises if it can't capture audio)
report = analyze(result.audio)       # -> Report (pure NumPy)

print(report.f0_hz, report.note)     # 440.0  A4
print(report.summary())
```

## How the capture works

Two facts make headless verification of an *arbitrary* patch tricky, and both
are handled for you:

- **You can't shadow the built-in `[dac~]`.** Dropping a same-named abstraction
  on the search path does *not* intercept it — Pd resolves the registered
  built-in and the render comes out silent. Instead, pdverify rewrites the
  *class token* of every `[dac~]` object box to `[pdverify_sink~]` on a throwaway
  copy of the patch. That is a single-token swap on the class field; it touches
  no object indices and no `#X connect` lines, so it sidesteps the
  connection-index bookkeeping that trips up machine-edited patches. Multiple
  `[dac~]` objects sum onto one bus via `[throw~]`/`[catch~]`, exactly as real
  Pd sums them.
- **A broken render must not look like silence.** A missing external, a patch
  with no reachable sink, or a nonzero Pd exit each raise a distinct error
  (`PdNotFound` / `NoSinkFound` / `RenderFailed`) rather than returning an empty
  buffer that a caller could score as a legitimately quiet patch.

## Status

Early (M0). Today it renders, analyzes, and reports. On the roadmap:

- **M1** — an expectation/assertion API (`--note A4 --tonal --no-clip`) with
  gated + graded scores, and corrective feedback aimed at an LLM fixing a patch.
- **M2** — `pdverify.bench`: a task manifest format and runner, so the same
  scoring core grades a public "make this sound" benchmark.
- **M3** — an optional MCP adapter so an agent can call `pd_check` in a
  build → listen → fix loop alongside a construction server.

## License

MIT.
