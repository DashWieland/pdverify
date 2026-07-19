"""Optional visualization. Needs matplotlib (``pip install pdverify[plot]``);
kept out of the core import path so the analysis engine stays numpy-only."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .audio import AudioBuffer
from .errors import PdVerifyError


def _pyplot():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise PdVerifyError(
            "visualization needs matplotlib; install it with:  pip install pdverify[plot]"
        ) from e


def _as_buffer(audio) -> AudioBuffer:
    return audio if isinstance(audio, AudioBuffer) else AudioBuffer(np.asarray(audio, dtype=np.float64), 44100)


def spectrogram(audio, path: str | Path, *, fmax: float = 16000.0, title: str | None = None) -> Path:
    """Save a spectrogram PNG of the (channel-summed) audio to ``path``."""
    plt = _pyplot()
    buf = _as_buffer(audio)
    x, sr = buf.mono(), buf.sr
    fig, ax = plt.subplots(figsize=(9, 4))
    _, _, _, im = ax.specgram(x, NFFT=2048, Fs=sr, noverlap=1024, cmap="magma")
    ax.set_ylim(0, min(fmax, sr / 2))
    ax.set_xlabel("time (s)")
    ax.set_ylabel("frequency (Hz)")
    if title:
        ax.set_title(title)
    fig.colorbar(im, ax=ax, label="dB")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return Path(path)


def spectrum(audio, path: str | Path, *, fmax: float = 20000.0, title: str | None = None) -> Path:
    """Save an averaged magnitude-spectrum PNG (log-frequency) to ``path``."""
    plt = _pyplot()
    buf = _as_buffer(audio)
    x, sr = buf.mono(), buf.sr
    n = min(len(x), 1 << 15)
    seg = x[(len(x) - n) // 2 :][:n] * np.hanning(n)
    mag = np.abs(np.fft.rfft(seg))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    db = 20 * np.log10(mag / (mag.max() + 1e-12) + 1e-12)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.semilogx(freqs[1:], db[1:], color="#c1440e")
    ax.set_xlim(20, min(fmax, sr / 2))
    ax.set_ylim(-90, 3)
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel("dB (rel. peak)")
    if title:
        ax.set_title(title)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return Path(path)
