# Changelog

## 0.1.0 (unreleased)

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
