"""render(): drive a headless Pd to capture a patch's audio output.

Pipeline (all in a throwaway, space-free work directory; the original patch is
never touched):

    locate Pd  ->  rewrite [dac~] -> [pdverify_sink~]  ->  emit recorder wrapper
    ->  pd -nogui -batch -noaudio ...  ->  read the WAV back

A render that does not produce audio raises (PdNotFound / NoSinkFound /
RenderFailed) — it never returns a silent buffer that a caller could mistake for
a legitimately quiet patch.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from . import control as _control
from .audio import AudioBuffer
from .errors import NoSinkFound, RenderFailed
from .pd_locate import discover
from .rewrite import NOTEIN_ABSTRACTION, SINK_ABSTRACTION, rewrite_notein, rewrite_sinks
from .wavio import read_wav
from .wrapper import build_wrapper

_PEAK_RE = re.compile(r"biggest amplitude\s*=\s*([0-9.eE+-]+)")
# soundfiler normalizes any array whose peak exceeds 1.0 when writing, and prints
# e.g. "reducing max amplitude 8.000000 to 1". Normalization only *scales* (it
# preserves the waveform), so we can undo it exactly and recover the true signal
# — including its over-unity peak, which is what dac~ would clip on playback.
_NORMALIZE_RE = re.compile(r"reducing max amplitude\s+([0-9.eE+-]+)\s+to 1")


@dataclass(frozen=True)
class RenderSpec:
    duration: float = 3.0
    sr: int = 44100
    pd_binary: str | None = None
    search_paths: tuple[str, ...] = ()
    tail: float = 0.4
    timeout: float = 30.0
    keep_workdir: bool = False
    controls: tuple = ()  # Control events to play into the patch during render


@dataclass(frozen=True)
class RenderResult:
    audio: AudioBuffer
    wav_path: Path | None
    pd_console: str
    missing_externals: tuple[str, ...]
    soundfiler_peak: float | None
    pd_version: str
    returncode: int
    wall_ms: float


def _load_patch(patch: str | Path) -> tuple[str, Path | None]:
    """Return (patch_text, source_dir). Accepts a path to a .pd file or raw
    patch text (anything containing a canvas header)."""
    if isinstance(patch, Path) or (isinstance(patch, str) and "\n" not in patch and "#N canvas" not in patch):
        p = Path(patch)
        if not p.exists():
            raise FileNotFoundError(f"patch file not found: {p}")
        return p.read_text(encoding="utf-8"), p.parent
    if "#N canvas" not in patch:
        raise ValueError("patch text does not look like a Pd patch (no '#N canvas')")
    return patch, None


def _parse_missing_externals(console: str) -> tuple[str, ...]:
    names: list[str] = []
    lines = console.splitlines()
    for i, line in enumerate(lines):
        if "couldn't create" in line:
            # Pd prints the offending object text on the preceding line.
            prev = lines[i - 1].strip() if i > 0 else ""
            token = prev.split()[0] if prev else ""
            m = re.search(r"([\w~/.+-]+)\s*:\s*couldn't create", line)
            name = m.group(1) if m else token
            if name:
                names.append(name)
    # de-dupe, preserve order
    seen: set[str] = set()
    return tuple(n for n in names if not (n in seen or seen.add(n)))


def render(patch: str | Path, spec: RenderSpec | None = None) -> RenderResult:
    spec = spec or RenderSpec()
    pd = discover(spec.pd_binary)

    patch_text, patch_dir = _load_patch(patch)
    instrumented, n_sinks = rewrite_sinks(patch_text)
    if n_sinks == 0:
        raise NoSinkFound(
            "patch has no [dac~] object to capture. (Patches that emit audio only "
            "via send~/throw~ or [outlet~] need a tap strategy not yet in M0.)"
        )

    controls = tuple(spec.controls)
    needs_notein = _control.has_notes(controls)
    if needs_notein:
        instrumented, _ = rewrite_notein(instrumented)

    n_frames = int(round(spec.sr * spec.duration))
    work = Path(tempfile.mkdtemp(prefix="pdverify_"))
    if " " in str(work):
        shutil.rmtree(work, ignore_errors=True)
        raise RenderFailed(
            f"temp dir path contains a space ({work}), which breaks Pd's message "
            "tokenizer. Set TMP/TEMP (or PDVERIFY_TMP) to a space-free path."
        )
    try:
        out_wav = work / "capture.wav"
        (work / "patch.pd").write_text(instrumented, encoding="utf-8")
        (work / "wrapper.pd").write_text(
            build_wrapper(out_wav, n_frames, spec.sr, spec.tail, controls), encoding="utf-8"
        )
        # place the tap abstractions where -path can find them
        assets = [SINK_ABSTRACTION]
        if needs_notein:
            assets.append(NOTEIN_ABSTRACTION)
        for name in assets:
            src = resources.files("pdverify._assets").joinpath(f"{name}.pd")
            (work / f"{name}.pd").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

        cmd = [
            pd.path, "-nogui", "-batch", "-noaudio", "-r", str(spec.sr),
            "-path", str(work),
        ]
        if patch_dir is not None:
            cmd += ["-path", str(patch_dir)]
        for extra in spec.search_paths:
            cmd += ["-path", str(extra)]
        cmd += ["-open", str(work / "wrapper.pd"), "-open", str(work / "patch.pd")]

        t0 = time.perf_counter()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=spec.timeout)
        except subprocess.TimeoutExpired as e:
            raise RenderFailed(
                f"Pd render timed out after {spec.timeout}s. The patch may lack a "
                "reachable sink or contain a runaway message loop.\n"
                f"{(e.stderr or '')[-1000:]}"
            ) from e
        wall_ms = (time.perf_counter() - t0) * 1000.0
        console = (proc.stdout or "") + (proc.stderr or "")

        if not out_wav.exists():
            raise RenderFailed(
                f"Pd produced no output file (exit {proc.returncode}).\n{console[-1500:]}"
            )

        audio = read_wav(out_wav)
        norm_m = _NORMALIZE_RE.search(console)
        true_peak: float | None = None
        if norm_m:
            true_peak = float(norm_m.group(1))
            if true_peak > 1.0:
                # undo soundfiler's normalization to recover the real signal level
                audio = AudioBuffer(audio.samples * true_peak, audio.sr)
        else:
            peak_m = _PEAK_RE.search(console)
            true_peak = float(peak_m.group(1)) if peak_m else None
        result = RenderResult(
            audio=audio,
            wav_path=(out_wav if spec.keep_workdir else None),
            pd_console=console,
            missing_externals=_parse_missing_externals(console),
            soundfiler_peak=true_peak,
            pd_version=pd.version,
            returncode=proc.returncode,
            wall_ms=wall_ms,
        )
        return result
    finally:
        if not spec.keep_workdir:
            shutil.rmtree(work, ignore_errors=True)
