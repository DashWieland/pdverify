# Changelog

## 0.1.0 (unreleased) — M0 walking skeleton

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
