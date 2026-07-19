"""Scoring: turn an Analysis Report + a list of Expectations into a verdict.

Two tiers, so one call serves both a yes/no check and a graded benchmark:

  * GATES (silence, clipping, non-finite, duration) are pass/fail. If any gate
    fails, the total score is 0 — a clipping or silent render cannot earn
    partial credit for being roughly the right pitch.
  * GRADED expectations each yield a continuous value in [0, 1] via a named
    tolerance curve, combined as a weighted mean.

This module imports neither Pd nor the renderer, so the benchmark can grade
pre-rendered audio with it directly.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable

from .report import Report

# --- tolerance curves -------------------------------------------------------
# Each maps (error, tolerance) -> [0,1]; 1.0 at zero error. `passed` is decided
# separately (error <= tolerance), so the curve only shapes partial credit.

def linear_ramp(error: float, tol: float) -> float:
    if tol <= 0:
        return 1.0 if error <= 0 else 0.0
    return max(0.0, min(1.0, 1.0 - error / (2.0 * tol)))


def half_gaussian(error: float, tol: float) -> float:
    if tol <= 0:
        return 1.0 if error <= 0 else 0.0
    return math.exp(-0.5 * (error / tol) ** 2)


CURVES: dict[str, Callable[[float, float], float]] = {
    "linear_ramp": linear_ramp,
    "half_gaussian": half_gaussian,
}


@dataclass(frozen=True)
class Score:
    """The result of evaluating one Expectation against a Report."""

    field: str
    kind: str  # "gate" | "graded"
    value: float  # [0,1]
    passed: bool
    measured: Any
    target: Any
    weight: float = 1.0
    tolerance: float = 0.0
    curve: str = "linear_ramp"
    detail: str = ""
    hint: str = ""
    pd_hint: str | None = None


@dataclass(frozen=True)
class Scorecard:
    total: float
    passed: bool
    gates_passed: bool
    scores: list[Score]  # ranked worst-first
    report: Report
    meta: dict = field(default_factory=dict)

    # --- serialization ---
    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "gates_passed": self.gates_passed,
            "scores": [asdict(s) for s in self.scores],
            "analysis": self.report.to_dict(),
            "meta": self.meta,
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, default=str)

    # --- human / LLM facing ---
    def verdict(self) -> str:
        if not self.gates_passed:
            return "GATE FAIL"
        return "PASS" if self.passed else "FAIL"

    def summary(self) -> str:
        return f"{self.verdict()} (score {self.total:.2f}) — {self.report.summary()}"

    def feedback(self, limit: int = 3) -> str:
        """Verdict plus the worst failing checks, with repair hints — the string
        an agent reads to decide what to change next."""
        lines = [f"{self.verdict()} — score {self.total:.2f}"]
        failures = [s for s in self.scores if not s.passed]
        if not failures:
            lines.append(f"  {self.report.summary()}")
            return "\n".join(lines)
        for s in failures[:limit]:
            line = f"  - {s.field}: {s.detail}" if s.detail else f"  - {s.field}: failed"
            if s.pd_hint:
                line += f"  → {s.pd_hint}"
            lines.append(line)
        if len(failures) > limit:
            lines.append(f"  (+{len(failures) - limit} more)")
        return "\n".join(lines)


def score(report: Report, expectations: Iterable, *, meta: dict | None = None) -> Scorecard:
    """Evaluate `expectations` (from the `expect` namespace) against `report`."""
    scores = [e.evaluate(report) for e in expectations]

    gates = [s for s in scores if s.kind == "gate"]
    graded = [s for s in scores if s.kind == "graded"]
    gates_passed = all(s.passed for s in gates)

    if not gates_passed:
        total = 0.0
    elif graded:
        wsum = sum(s.weight for s in graded) or 1.0
        total = sum(s.value * s.weight for s in graded) / wsum
    else:
        total = 1.0

    passed = gates_passed and all(s.passed for s in scores)
    # worst first: failures before passes, then lowest value
    ranked = sorted(scores, key=lambda s: (s.passed, s.value))
    return Scorecard(
        total=total,
        passed=passed,
        gates_passed=gates_passed,
        scores=ranked,
        report=report,
        meta=meta or {},
    )
