"""verify(): render a patch, analyze it, and score it against expectations.

This is the one call the live tool and the (future) benchmark share. It ties
together the Pd-dependent render with the Pd-free analyze + score, so the exact
number an agent gets as feedback is the number the benchmark would grade.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .analyze import analyze
from .render import RenderSpec, render
from .score import Scorecard, score


def verify(
    patch: str | Path,
    expectations: Iterable,
    *,
    spec: RenderSpec | None = None,
) -> Scorecard:
    result = render(patch, spec)
    report = analyze(result.audio)
    meta = {
        "pd_version": result.pd_version,
        "render_ms": round(result.wall_ms, 1),
        "missing_externals": list(result.missing_externals),
    }
    return score(report, expectations, meta=meta)
