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

from .audio import AudioBuffer
from .errors import NoSinkFound, RenderFailed
from .pd_locate import discover
from .rewrite import SINK_ABSTRACTION, rewrite_sinks
from .wavio import read_wav
from .wrapper import build_wrapper

_PEAK_RE = re.compile(r"biggest amplitude\s*=\s*([0-9.eE+-]+)")


@dataclass(frozen=True)
class RenderSpec:
    duration: float = 3.0
    sr: int = 44100
    pd_binary: str | None = None
    search_paths: tuple[str, ...] = ()
    tail: float = 0.4
    timeout: float = 30.0
    keep_workdir: bool = False


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
            build_wrapper(out_wav, n_frames, spec.sr, spec.tail), encoding="utf-8"
        )
        # place the sink abstraction where -path can find it
        sink_src = resources.files("pdverify._assets").joinpath(f"{SINK_ABSTRACTION}.pd")
        (work / f"{SINK_ABSTRACTION}.pd").write_text(sink_src.read_text(encoding="utf-8"), encoding="utf-8")

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
        peak_m = _PEAK_RE.search(console)
        result = RenderResult(
            audio=audio,
            wav_path=(out_wav if spec.keep_workdir else None),
            pd_console=console,
            missing_externals=_parse_missing_externals(console),
            soundfiler_peak=(float(peak_m.group(1)) if peak_m else None),
            pd_version=pd.version,
            returncode=proc.returncode,
            wall_ms=wall_ms,
        )
        return result
    finally:
        if not spec.keep_workdir:
            shutil.rmtree(work, ignore_errors=True)
