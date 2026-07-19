"""Unit tests for the dac~ -> pdverify_sink~ rewrite. No Pd required."""

from pdverify.rewrite import rewrite_sinks


def test_simple_dac_rewritten():
    out, n = rewrite_sinks("#X obj 50 140 dac~;\n")
    assert n == 1
    assert "pdverify_sink~" in out
    assert "dac~" not in out.replace("pdverify_sink~", "")


def test_creation_args_preserved():
    out, n = rewrite_sinks("#X obj 50 140 dac~ 1 2;\n")
    assert n == 1
    assert out.strip() == "#X obj 50 140 pdverify_sink~ 1 2;"


def test_adc_not_touched():
    out, n = rewrite_sinks("#X obj 10 10 adc~;\n")
    assert n == 0
    assert out == "#X obj 10 10 adc~;\n"


def test_comment_mentioning_dac_not_touched():
    src = "#X text 10 10 remember to add a dac~ here;\n"
    out, n = rewrite_sinks(src)
    assert n == 0
    assert out == src


def test_two_dacs_both_rewritten():
    src = "#X obj 10 10 dac~;\n#X obj 20 20 dac~;\n"
    out, n = rewrite_sinks(src)
    assert n == 2
    assert out.count("pdverify_sink~") == 2


def test_connections_unchanged():
    src = (
        "#N canvas 0 0 300 200 12;\n"
        "#X obj 40 40 osc~ 440;\n"
        "#X obj 40 80 *~ 0.25;\n"
        "#X obj 40 130 dac~;\n"
        "#X connect 0 0 1 0;\n"
        "#X connect 1 0 2 0;\n"
        "#X connect 1 0 2 1;\n"
    )
    out, n = rewrite_sinks(src)
    assert n == 1
    # every #X connect line must survive byte-for-byte
    for line in src.splitlines():
        if line.startswith("#X connect"):
            assert line in out
