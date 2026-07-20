"""Rewrite a patch's audio-output objects so we can tap them.

You cannot capture a running ``[dac~]`` in a headless ``-noaudio`` render, and
you cannot shadow the built-in ``dac~`` with a same-named abstraction on the
search path (Pd resolves the registered built-in and never looks at the path —
verified on vanilla 0.56-2; the render comes out silent). So instead we rewrite
the *class token* of every ``[dac~]`` object box to ``[pdverify_sink~]``, a real
abstraction that loads from ``-path`` and taps its signal inlets onto a global
``throw~`` bus.

This is a single-token string swap on the class field only. It touches no object
indices and no ``#X connect`` lines, so it sidesteps the connection-index
bookkeeping that is the #1 failure mode for machine-edited patches.
"""

from __future__ import annotations

import re

# The class token ends in '~' (a non-word char), so a trailing \b never anchors
# — a real bug found in prototyping. Use an explicit lookahead for whitespace or
# end-of-record instead. The leading (?<![\w~-]) guard keeps us from matching the
# 'dac~' inside a hypothetical 'mydac~'.
_SINK_RE = re.compile(
    r"^(#X obj\s+-?\d+\s+-?\d+\s+)(?<![\w~-])dac~(?=\s|$)(.*)$",
    re.DOTALL,
)

SINK_ABSTRACTION = "pdverify_sink~"
NOTEIN_ABSTRACTION = "pdverify_notein"

# [notein] can't be shadowed either; rewrite it to a message-driven shim so
# scheduled note events can play the patch. Any channel arg is dropped.
_NOTEIN_RE = re.compile(r"^(#X obj\s+-?\d+\s+-?\d+\s+)notein(?=\s|$).*$", re.DOTALL)


def rewrite_sinks(patch_text: str, replacement: str = SINK_ABSTRACTION) -> tuple[str, int]:
    """Return (rewritten_text, count) where count is the number of ``[dac~]``
    object boxes rewritten. A count of 0 means the patch has no dac~ sink.

    Only object boxes are considered; ``#X text`` comments that happen to mention
    ``dac~`` are left alone, and ``adc~`` is never matched.
    """
    # Pd records are ';'-terminated and may span physical lines. Split on the
    # terminators, keeping them, and only rewrite records that are object boxes.
    parts = re.split(r"(;)", patch_text)
    count = 0
    out = []
    for part in parts:
        if part.lstrip().startswith("#X obj"):
            new, n = _SINK_RE.subn(rf"\g<1>{replacement}\g<2>", part.lstrip("\n"), count=1)
            if n:
                # preserve any leading newline that lstrip removed
                lead = part[: len(part) - len(part.lstrip("\n"))]
                out.append(lead + new)
                count += 1
                continue
        out.append(part)
    return "".join(out), count


def rewrite_notein(patch_text: str, replacement: str = NOTEIN_ABSTRACTION) -> tuple[str, int]:
    """Rewrite every ``[notein]`` object box to the message-driven shim. Returns
    (rewritten_text, count)."""
    parts = re.split(r"(;)", patch_text)
    count = 0
    out = []
    for part in parts:
        if part.lstrip().startswith("#X obj"):
            stripped = part.lstrip("\n")
            new, n = _NOTEIN_RE.subn(rf"\g<1>{replacement}", stripped, count=1)
            if n:
                lead = part[: len(part) - len(stripped)]
                out.append(lead + new)
                count += 1
                continue
        out.append(part)
    return "".join(out), count
