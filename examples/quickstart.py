"""Minimal pdverify example: render a patch and print what it sounds like.

    python examples/quickstart.py path/to/patch.pd

With no argument it renders a built-in osc~ 440 -> dac~ patch.
"""

import sys

from pdverify import analyze, render

DEMO = (
    "#N canvas 0 0 300 200 12;\n"
    "#X obj 40 40 osc~ 440;\n#X obj 40 80 *~ 0.25;\n#X obj 40 130 dac~;\n"
    "#X connect 0 0 1 0;\n#X connect 1 0 2 0;\n#X connect 1 0 2 1;\n"
)


def main() -> None:
    patch = sys.argv[1] if len(sys.argv) > 1 else DEMO
    result = render(patch)
    report = analyze(result.audio)
    print(report.pretty())
    print()
    print(report.summary())
    print(f"\n(rendered in {result.wall_ms:.0f} ms with Pd {result.pd_version})")


if __name__ == "__main__":
    main()
