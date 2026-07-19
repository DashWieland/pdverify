"""Translate a numeric Report into perceptual language.

The analysis measures things in Hz and dB; a person hears "a dark, hollow,
chordal drone with an airy haze." This module maps the (now trustworthy) numbers
onto words, so an agent gets a usable description without reading a spectrogram
or knowing what a kilohertz is. Rule-based and deterministic on purpose.
"""

from __future__ import annotations


def _slices(report) -> dict:
    b = report.bands or {}
    g = lambda k: float(b.get(k, 0.0))  # noqa: E731
    sub, bass, low_mid = g("sub"), g("bass"), g("low_mid")
    return {
        "sub": sub,
        "bass": bass,
        "low": sub + bass + low_mid,  # 0-500 Hz
        "upper_mid": g("high_mid") + g("presence"),  # 2-6 kHz (the "presence" gap)
        "brilliance": g("brilliance"),  # 6 kHz+ (air / sizzle)
        "high": g("presence") + g("brilliance"),  # 4 kHz+
    }


def brightness(report) -> str:
    """One dark..brilliant word. When the sound is bimodal — a low body plus a
    high haze — it's called by its body ('dark') and the haze is named
    separately; otherwise brightness follows the (power-weighted) centroid."""
    s = _slices(report)
    if s["low"] > 0.4 and s["high"] > 0.08:  # dark body + bright top
        return "dark"
    c = report.centroid_hz
    if c < 250:
        return "dark"
    if c < 800:
        return "warm"
    if c < 2500:
        return "balanced"
    if c < 6000:
        return "bright"
    return "brilliant"


def _weight(report) -> str | None:
    s = _slices(report)
    if s["sub"] > 0.15:
        return "sub-heavy"
    if s["sub"] + s["bass"] > 0.4:
        return "bass-heavy"
    return None


def _tonality(report) -> str:
    if report.flatness > 0.45:
        return "noisy"
    if report.flatness < 0.12:
        if report.pitch_confidence >= 0.6:
            return "pure"
        if len(report.top_partials) >= 3 and report.pitch_confidence < 0.4:
            return "chordal"
        return "tonal"
    return "metallic"


_TYPE = {"noisy": "texture", "pure": "pure tone", "tonal": "tone", "chordal": "chord", "metallic": "metallic tone"}


def _high_phrase(report) -> str | None:
    b = _slices(report)["brilliance"]
    if b > 0.3:
        return "a sizzly high end"
    if b > 0.08:
        return "an airy high-frequency haze"
    return None


def _is_hollow(report) -> bool:
    s = _slices(report)
    return s["upper_mid"] < 0.05 and s["low"] > 0.3 and s["high"] > 0.05


def descriptors(report) -> list[str]:
    """Perceptual tags, most-defining first. Safe on any Report."""
    if report.has_nan_inf:
        return ["unstable (NaN/Inf)"]
    if report.is_silent:
        return ["silent"]

    tags: list[str] = [report.motion, brightness(report)]
    weight = _weight(report)
    if weight:
        tags.append(weight)
    if _is_hollow(report):
        tags.append("hollow mids")
    high = _high_phrase(report)
    if high:
        tags.append("sizzly high end" if "sizzly" in high else "airy high end")
    tags.append(_tonality(report))
    if report.pitch_confidence >= 0.6 and report.note:
        tags.append(f"pitched near {report.note}")
    elif report.pitch_confidence < 0.3:
        tags.append("no clear pitch")
    if report.is_clipped:
        tags.append("distorted / clipping")
    return tags


def describe(report) -> str:
    """A single natural-language sentence composed from the tags."""
    if report.has_nan_inf:
        return "Unstable output — the DSP graph produced NaN/Inf."
    if report.is_silent:
        return "Silent — no signal above -60 dBFS."

    ton = _tonality(report)
    kind = _TYPE[ton]

    adjectives = [brightness(report)]
    weight = _weight(report)
    if weight:
        adjectives.append(weight)
    if report.motion != "steady":
        adjectives.insert(0, report.motion)

    article = "An" if adjectives[0][0].lower() in "aeiou" else "A"
    sentence = f"{article} {', '.join(adjectives)} {kind}"

    phrases: list[str] = []
    if _is_hollow(report):
        phrases.append("hollow, scooped mids")
    high = _high_phrase(report)
    if high:
        phrases.append(high)
    if report.pitch_confidence < 0.3 and ton not in ("noisy",):
        phrases.append("no single clear pitch")

    if len(phrases) == 1:
        sentence += " with " + phrases[0]
    elif phrases:
        sentence += " with " + ", ".join(phrases[:-1]) + ", and " + phrases[-1]

    if report.pitch_confidence >= 0.6 and report.note:
        sentence += f", pitched near {report.note}"
    if report.is_clipped:
        sentence += " — and it clips"
    return sentence + "."
