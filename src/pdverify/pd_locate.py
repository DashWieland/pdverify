"""Locate a Pure Data executable across platforms.

Resolution order (first hit wins), recorded so renders are reproducible:
  1. an explicit path passed by the caller
  2. the PDVERIFY_PD environment variable
  3. a Pd unzipped under ./tools/pd-*/ near the cwd (dev convenience)
  4. ``pd`` on PATH
  5. per-OS default install locations
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from glob import glob
from pathlib import Path

from .errors import PdNotFound

_IS_WIN = platform.system() == "Windows"


@dataclass(frozen=True)
class PdBinary:
    path: str
    version: str  # e.g. "0.56.2", or "" if unparsable


def _candidates(explicit: str | None) -> list[str]:
    out: list[str] = []
    if explicit:
        out.append(explicit)
    env = os.environ.get("PDVERIFY_PD")
    if env:
        out.append(env)

    # Dev convenience: a portable Pd unzipped under tools/ near the cwd or its
    # parents (this repo keeps one at ../tools/pd-0.56-2 during development).
    names = ["pd.com", "pd.exe"] if _IS_WIN else ["pd"]
    base = Path.cwd()
    for root in [base, *base.parents[:3]]:
        for name in names:
            out += sorted(glob(str(root / "tools" / "pd-*" / "bin" / name)), reverse=True)

    for name in (["pd.com", "pd.exe"] if _IS_WIN else ["pd", "puredata"]):
        found = shutil.which(name)
        if found:
            out.append(found)

    if _IS_WIN:
        for pf in filter(None, [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]):
            out += sorted(glob(str(Path(pf) / "Pd" / "bin" / "pd.com")), reverse=True)
            out += sorted(glob(str(Path(pf) / "Pd" / "bin" / "pd.exe")), reverse=True)
    elif platform.system() == "Darwin":
        out += sorted(glob("/Applications/Pd-*.app/Contents/Resources/bin/pd"), reverse=True)
        out += ["/opt/homebrew/bin/pd", "/usr/local/bin/pd"]
    else:
        out += ["/usr/bin/pd", "/usr/local/bin/pd"]

    # de-dupe, preserving order
    seen: set[str] = set()
    uniq = []
    for c in out:
        if c and c not in seen and Path(c).exists():
            seen.add(c)
            uniq.append(c)
    return uniq


def _query_version(pd_path: str) -> str:
    try:
        proc = subprocess.run(
            [pd_path, "-version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        banner = (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r"Pd[- ]?(\d+\.\d+[.-]?\d*)", banner)
    return m.group(1).replace("-", ".") if m else ""


def _version_from_path(pd_path: str) -> str:
    """Best-effort version from the install path, e.g. .../Pd-0.56-2.app/... or
    tools/pd-0.56-2/bin/pd. Used when `pd -version` can't be parsed (seen on the
    macOS .app binary)."""
    m = re.search(r"[Pp]d[-_ ]?(\d+\.\d+(?:[.-]\d+)?)", pd_path)
    return m.group(1).replace("-", ".") if m else ""


def discover(explicit: str | None = None) -> PdBinary:
    """Return the first usable Pd binary, or raise PdNotFound."""
    cands = _candidates(explicit)
    if not cands:
        raise PdNotFound(
            "No Pure Data binary found. Install Pd (https://puredata.info/downloads), "
            "put it on PATH, or set PDVERIFY_PD to the pd executable."
        )
    chosen = cands[0]
    version = _query_version(chosen) or _version_from_path(chosen)
    return PdBinary(path=chosen, version=version)
