"""pdverify — render Pure Data patches headless and verify what they sound like.

The existing Pd LLM harnesses can *construct* patches but stop at "loaded
without console errors." pdverify closes the loop: it renders a patch to audio
offline and reports what actually came out — pitch, level, timbre, and health.

Public surface (M0):
    render(patch, spec=...)   -> RenderResult   (Pure Data required at runtime)
    analyze(audio, sr=...)    -> Report         (pure numpy, no Pd)
    read_wav(path)            -> AudioBuffer

analyze() has no dependency on Pd or the renderer, so it doubles as the scoring
core the planned benchmark will import verbatim.
"""

from . import control
from . import expect
from .audio import AudioBuffer
from .analyze import analyze
from .report import Report
from .render import render, RenderSpec, RenderResult
from .score import score, Score, Scorecard
from .expect import Expectation
from .verify import verify
from .compare import compare, Comparison
from .errors import PdVerifyError, PdNotFound, NoSinkFound, RenderFailed
from .wavio import read_wav

__version__ = "0.1.0"

__all__ = [
    "analyze",
    "render",
    "score",
    "verify",
    "compare",
    "Comparison",
    "expect",
    "control",
    "read_wav",
    "AudioBuffer",
    "Report",
    "RenderSpec",
    "RenderResult",
    "Score",
    "Scorecard",
    "Expectation",
    "PdVerifyError",
    "PdNotFound",
    "NoSinkFound",
    "RenderFailed",
    "__version__",
]
