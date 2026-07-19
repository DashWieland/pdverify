"""Exception types for pdverify.

The central discipline: a *failed* render must never look like a legitimately
silent patch. Missing Pd, no reachable audio sink, or a nonzero Pd exit each
raise a distinct error so a caller (and, later, the benchmark scorer) can tell
"this patch is silent" apart from "this patch never ran."
"""


class PdVerifyError(Exception):
    """Base class for all pdverify errors."""


class PdNotFound(PdVerifyError):
    """No Pure Data binary could be located."""


class NoSinkFound(PdVerifyError):
    """The patch contains no object we know how to tap for audio output.

    In M0 that means no ``[dac~]`` object box. Raised instead of returning a
    silent buffer, because silence-from-no-sink and silence-from-DSP are very
    different facts.
    """


class RenderFailed(PdVerifyError):
    """Pd ran but did not produce a usable capture (nonzero exit, timeout, or
    missing output file)."""
