"""analyze(): turn captured audio into a Report. Pure numpy, no Pd."""

from __future__ import annotations

import numpy as np

from .audio import AudioBuffer
from .features import integrity, level, pitch, spectral, temporal
from .report import Report


def _timbre(flatness: float, confidence: float) -> str:
    if flatness >= 0.5:
        return "noise"
    if confidence >= 0.6 and flatness < 0.05:
        return "sine"
    if confidence >= 0.4:
        return "harmonic"
    return "inharmonic"


def analyze(audio: AudioBuffer | np.ndarray, sr: int = 44100) -> Report:
    """Analyze an AudioBuffer (or a raw ndarray + sr) and return a Report.

    Pitch/level/spectral features are computed on the channel-summed mono view;
    integrity checks run on the full buffer so a NaN or clip in any channel is
    caught.
    """
    if isinstance(audio, AudioBuffer):
        buf = audio
        sr = audio.sr
    else:
        buf = AudioBuffer(np.asarray(audio, dtype=np.float64), sr)

    full = buf.samples
    mono = buf.mono()

    nan_inf = integrity.has_nan_inf(full)
    safe = np.nan_to_num(mono) if nan_inf else mono

    motion_label, _motion_amt = temporal.motion(safe, sr)
    f0, conf = pitch.estimate_f0(safe, sr)
    note, cents = pitch.hz_to_note(f0)
    flat = spectral.spectral_flatness(safe, sr)
    timbre = _timbre(flat, conf)
    silent = integrity.is_silent(full)

    return Report(
        duration=buf.duration,
        sr=sr,
        channels=buf.channels,
        is_silent=silent,
        is_clipped=integrity.is_clipped(full),
        has_nan_inf=nan_inf,
        dc_offset=level.dc_offset(mono),
        peak_dbfs=level.peak_dbfs(full),
        rms_dbfs=level.rms_dbfs(mono),
        crest_factor=level.crest_factor(mono),
        f0_hz=(f0 if (f0 > 0 and not silent) else None),
        note=(note if (f0 > 0 and not silent) else None),
        cents_error=(cents if (f0 > 0 and not silent) else None),
        pitch_confidence=conf,
        centroid_hz=spectral.spectral_centroid(safe, sr),
        rolloff_hz=spectral.spectral_rolloff(safe, sr),
        flatness=flat,
        timbre=timbre,
        bands=spectral.band_energies(safe, sr),
        top_partials=spectral.top_partials(safe, sr),
        motion=motion_label,
        fingerprint=spectral.log_power_fingerprint(safe, sr),
    )
