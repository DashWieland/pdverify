"""Command-line interface: pdverify {analyze,render,doctor}."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import __version__, expect
from .analyze import analyze
from .errors import PdNotFound, PdVerifyError
from .pd_locate import discover
from .render import RenderSpec, render
from .verify import verify
from .wavio import read_wav

_DOCTOR_PATCH = (
    "#N canvas 0 0 300 200 12;\n"
    "#X obj 40 40 osc~ 440;\n"
    "#X obj 40 80 *~ 0.25;\n"
    "#X obj 40 130 dac~;\n"
    "#X connect 0 0 1 0;\n"
    "#X connect 1 0 2 0;\n"
    "#X connect 1 0 2 1;\n"
)


def _spec(args) -> RenderSpec:
    return RenderSpec(duration=args.dur, sr=args.sr, pd_binary=args.pd)


def _add_render_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("--dur", type=float, default=3.0, help="capture duration in seconds (default 3.0)")
    p.add_argument("--sr", type=int, default=44100, help="sample rate (default 44100)")
    p.add_argument("--pd", default=None, help="path to the Pd executable (overrides discovery)")


def cmd_analyze(args) -> int:
    path = Path(args.patch)
    if path.suffix.lower() == ".wav":
        report = analyze(read_wav(path))
    else:
        result = render(str(path), _spec(args))
        report = analyze(result.audio)
        if result.missing_externals:
            print(f"warning: Pd couldn't create: {', '.join(result.missing_externals)}", file=sys.stderr)
    if args.json:
        print(report.to_json())
    else:
        print(report.pretty())
        print(f"\nsounds like: {report.summary()}")
        print(f"tags:        {', '.join(report.descriptors())}")
    return 0


def _expectations_from_args(args) -> list:
    exps = [expect.finite()]
    if not args.allow_silent:
        exps.append(expect.not_silent())
    if not args.allow_clip:
        exps.append(expect.no_clipping())
    if args.note is not None:
        exps.append(expect.note(args.note, tol_cents=args.tol_cents))
    if args.pitch is not None:
        exps.append(expect.pitch(args.pitch, tol_cents=args.tol_cents))
    if args.level is not None:
        exps.append(expect.level(args.level, tol_db=args.tol_db))
    if args.tonal:
        exps.append(expect.tonal())
    if args.noisy:
        exps.append(expect.noisy())
    if args.centroid is not None:
        exps.append(expect.centroid(args.centroid))
    return exps


def cmd_assert(args) -> int:
    card = verify(args.patch, _expectations_from_args(args), spec=_spec(args))
    if args.json:
        print(card.to_json())
    else:
        print(card.feedback())
    if not card.gates_passed:
        return 3
    return 0 if card.passed else 1


def cmd_render(args) -> int:
    dest = Path(args.output)
    # keep the workdir so we can copy the captured wav out, then clean it up
    spec = RenderSpec(duration=args.dur, sr=args.sr, pd_binary=args.pd, keep_workdir=True)
    result = render(args.patch, spec)
    if result.wav_path:
        shutil.copyfile(result.wav_path, dest)
        shutil.rmtree(result.wav_path.parent, ignore_errors=True)
    print(f"wrote {dest}  ({result.audio.duration:.2f}s, {result.audio.channels}ch, {result.wall_ms:.0f}ms)")
    return 0


def cmd_spectrogram(args) -> int:
    from .viz import spectrogram

    path = Path(args.patch)
    if path.suffix.lower() == ".wav":
        audio = read_wav(path)
    else:
        audio = render(str(path), _spec(args)).audio
    out = spectrogram(audio, args.output, fmax=args.fmax, title=path.stem)
    print(f"wrote {out}")
    return 0


def _audio_for(patch_or_wav, args):
    p = Path(patch_or_wav)
    if p.suffix.lower() == ".wav":
        return read_wav(p)
    return render(str(patch_or_wav), _spec(args)).audio


def cmd_compare(args) -> int:
    from .compare import compare

    candidate = analyze(_audio_for(args.patch, args))
    reference = analyze(_audio_for(args.reference, args))
    comp = compare(candidate, reference)
    if args.json:
        import json

        print(json.dumps({"similarity": comp.similarity, "diffs": comp.diffs}, indent=2))
    else:
        print(comp.feedback())
    return 0


def cmd_doctor(args) -> int:
    print(f"pdverify {__version__}")
    try:
        pd = discover(args.pd)
    except PdNotFound as e:
        print(f"FAIL: {e}")
        return 3
    print(f"Pd binary:  {pd.path}")
    print(f"Pd version: {pd.version or '(unknown)'}")
    print("rendering osc~ 440 -> dac~ ...")
    try:
        result = render(_DOCTOR_PATCH, RenderSpec(duration=1.0, pd_binary=args.pd))
    except PdVerifyError as e:
        print(f"FAIL: render error: {e}")
        return 2
    report = analyze(result.audio)
    ok = (not report.is_silent) and report.f0_hz is not None and abs(report.f0_hz - 440.0) < 5.0
    print(f"  -> {report.summary()}")
    print(f"  -> render {result.wall_ms:.0f}ms, soundfiler peak {result.soundfiler_peak}")
    if ok:
        print("PASS: Pd renders and pdverify captures audio correctly.")
        return 0
    print("FAIL: expected a ~440 Hz non-silent tone; got the above. Capture pipeline is broken.")
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pdverify", description="Render Pure Data patches and verify what they sound like.")
    p.add_argument("--version", action="version", version=f"pdverify {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="render a patch (or read a .wav) and print an audio analysis")
    a.add_argument("patch", help="path to a .pd patch or a .wav file")
    a.add_argument("--json", action="store_true", help="emit the report as JSON")
    _add_render_opts(a)
    a.set_defaults(func=cmd_analyze)

    r = sub.add_parser("render", help="render a patch to a .wav file")
    r.add_argument("patch", help="path to a .pd patch")
    r.add_argument("-o", "--output", required=True, help="output .wav path")
    _add_render_opts(r)
    r.set_defaults(func=cmd_render)

    s = sub.add_parser("assert", help="render a patch and check it against expectations")
    s.add_argument("patch", help="path to a .pd patch")
    s.add_argument("--note", default=None, help="expected pitch as a note name, e.g. A4")
    s.add_argument("--pitch", type=float, default=None, help="expected pitch in Hz")
    s.add_argument("--tol-cents", type=float, default=50.0, help="pitch tolerance in cents (default 50)")
    s.add_argument("--level", type=float, default=None, help="expected RMS level in dBFS")
    s.add_argument("--tol-db", type=float, default=3.0, help="level tolerance in dB (default 3)")
    s.add_argument("--tonal", action="store_true", help="expect a tonal (low-flatness) output")
    s.add_argument("--noisy", action="store_true", help="expect a noisy (high-flatness) output")
    s.add_argument("--centroid", type=float, default=None, help="expected spectral centroid in Hz")
    s.add_argument("--allow-silent", action="store_true", help="do not require signal (drop the silence gate)")
    s.add_argument("--allow-clip", action="store_true", help="do not fail on clipping")
    s.add_argument("--json", action="store_true", help="emit the scorecard as JSON")
    _add_render_opts(s)
    s.set_defaults(func=cmd_assert)

    c = sub.add_parser("compare", help="compare a patch against a reference sound (.pd or .wav)")
    c.add_argument("patch", help="path to a .pd patch or a .wav file")
    c.add_argument("--reference", "--ref", required=True, dest="reference", help="reference .pd or .wav to match")
    c.add_argument("--json", action="store_true", help="emit the comparison as JSON")
    _add_render_opts(c)
    c.set_defaults(func=cmd_compare)

    g = sub.add_parser("spectrogram", help="render a patch (or read a .wav) and save a spectrogram PNG")
    g.add_argument("patch", help="path to a .pd patch or a .wav file")
    g.add_argument("-o", "--output", required=True, help="output .png path")
    g.add_argument("--fmax", type=float, default=16000.0, help="max frequency shown (default 16000)")
    _add_render_opts(g)
    g.set_defaults(func=cmd_spectrogram)

    d = sub.add_parser("doctor", help="check the Pd install and capture pipeline")
    d.add_argument("--pd", default=None, help="path to the Pd executable")
    d.set_defaults(func=cmd_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except PdNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    except PdVerifyError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
