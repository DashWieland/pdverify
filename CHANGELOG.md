# Changelog

## 0.1.0 (unreleased)

### Reference matching — "make it sound like this"

- `compare(candidate, target)` scores how close two sounds are (timbre-fingerprint
  cosine, phase/time-invariant) and returns concrete moves to close the gap —
  brighter/darker, pitch shift, level, add/reduce a frequency band, more/less
  motion. Turns a subjective target into an objective, climbable score.
- `expect.matches_reference(ref, tol)` — a graded expectation against a reference
  that may be a Report, an AudioBuffer, a `.wav`, or a `.pd` (rendered on the fly).
  Any rendering happens when the expectation is built, so `score()` stays Pd-free.
- `pdverify compare patch.pd --ref target.wav` CLI.
- A compact L2-normalized log-power `fingerprint` is added to every Report.

### Plain-language description

- `report.summary()` now returns a perceptual, human-meaningful sentence instead
  of a number dump — e.g. "An evolving, dark, sub-heavy chord with hollow,
  scooped mids, an airy high-frequency haze, and no single clear pitch." A
  `report.descriptors()` accessor gives the same as structured tags. The point:
  an agent (or person) shouldn't have to read a spectrogram or know what a
  kilohertz is to know what a patch sounds like.
- New temporal `motion` feature (steady / gently moving / evolving / very
  dynamic) from loudness-envelope variation and spectral flux across the whole
  signal — so "evolving" is measured, not eyeballed.

### Spectral analysis and visualization

- `analyze()` now reports a full-spectrum band-energy breakdown (sub / bass /
  low-mid / mid / high-mid / presence / brilliance, summing to ~1) and the
  strongest partials — enough to actually describe a timbre, not just one
  centroid number. Found by dogfooding: a single centroid hid a real patch's
  character.
- `pdverify spectrogram` (and `viz.spectrogram` / `viz.spectrum`) save PNGs;
  needs the `[plot]` extra (matplotlib), lazy-imported so the core stays
  numpy-only.
- Fix: spectral centroid and rolloff are now **power**-weighted, not
  magnitude-weighted. Magnitude weighting let a 16-bit quantization noise floor
  drag the centroid to ~9.7 kHz on a bass-heavy drone; power weighting reports
  the true ~300 Hz body.
- Fix: frequency bands now span 0..Nyquist with no gaps, so DC/subsonic and
  near-Nyquist aliasing (common with Pd's non-band-limited oscillators) are
  counted instead of silently dropped.

### M1 — expectations and scoring

- `expect.*` builders for composable expectations: gates (`not_silent`,
  `finite`, `no_clipping`, `duration`) and graded checks (`pitch`, `note`,
  `level`, `tonal`, `noisy`, `centroid`).
- `score()` — gates short-circuit the total to 0; graded checks combine via a
  named tolerance curve (`linear_ramp`, `half_gaussian`) into a weighted mean.
  Returns a `Scorecard` with a boolean verdict, a continuous score, JSON, and
  `feedback()` carrying worst-first fixes with repair hints.
- `verify()` — one-shot render + analyze + score, shared by the live tool and
  (later) the benchmark.
- `pdverify assert` CLI with exit codes (0 pass / 1 fail / 3 gate-fail).
- Over-unity capture fix: soundfiler normalizes any array whose peak exceeds 1.0
  when writing. `render()` now detects this from the console and rescales to
  recover the true level, so a hot patch is caught as clipping instead of being
  silently normalized to a clean full-scale signal.

### M0 — walking skeleton

First working version. Renders a Pure Data patch headless and reports what it
sounds like.

- `render()` — headless offline capture via `pd -nogui -batch -noaudio`. Rewrites
  `[dac~]` object boxes to a `[pdverify_sink~]` tap, sums them onto a
  `[throw~]`/`[catch~]` bus, records with a tool-authored `[soundfiler]` wrapper,
  and reads the WAV back. Distinguishes render failure from genuine silence
  (`PdNotFound` / `NoSinkFound` / `RenderFailed`).
- `analyze()` — pure-NumPy features: integrity gates (silence, clipping,
  NaN/Inf, DC), level (peak/RMS/crest in dBFS), pitch (parabolic-interpolated
  FFT peak + note name + cents), and spectral shape (centroid, rolloff, flatness,
  timbre label). No dependency on Pd or the renderer.
- `pdverify` CLI — `analyze`, `render`, `doctor`.
- Cross-platform Pd discovery; WAV I/O for 16-bit PCM (stdlib `wave`) with a
  NumPy-only RIFF fallback for float/EXTENSIBLE files.
