"""
NatBench updater.py — self-update and version-check utilities.

Supports:
  - Git-editable installs: ``git pull`` + ``pip install -e .``
  - PyPI installs: ``pip install --upgrade natbench``
  - GitHub API check for latest release (never raises)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Optional[str] = None) -> tuple[int, str, str]:
    """Run *cmd* and return (returncode, stdout, stderr). Never raises."""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            text=True,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def _current_version() -> str:
    """Return the installed NatBench version string."""
    try:
        from natbench.__version__ import __version__
        return __version__
    except Exception:
        pass
    try:
        from importlib.metadata import version
        return version("natbench")
    except Exception:
        return "unknown"


def _detect_git_root() -> Optional[Path]:
    """
    Return the project root if we're running from an editable / git install.

    Looks for a .git directory starting at the package directory and walking
    up two levels (enough to find the repo root whether we're inside the
    package subdirectory or not).
    """
    pkg_dir = Path(__file__).parent
    for candidate in (pkg_dir, pkg_dir.parent):
        if (candidate / ".git").is_dir():
            return candidate
    return None


def _version_tuple(v: str) -> tuple[int, ...]:
    """Convert "1.2.3" to (1, 2, 3); non-numeric parts become 0."""
    parts = []
    for part in v.lstrip("v").split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_for_updates() -> dict:
    """
    Check GitHub API for the latest NatBench release.

    Returns a dict with keys:
        current (str)  — installed version
        latest  (str)  — latest GitHub release tag (without leading "v")
        url     (str)  — HTML URL of the release page
        newer   (bool) — True when latest > current
        error   (str)  — non-empty when the check failed

    This function never raises.
    """
    current = _current_version()
    result: dict = {
        "current": current,
        "latest": current,
        "url": "https://github.com/natural78/natbench/releases",
        "newer": False,
        "error": "",
    }

    api_url = "https://api.github.com/repos/natural78/natbench/releases/latest"

    # Try urllib first (stdlib), fall back to requests
    raw: Optional[str] = None
    try:
        import urllib.request
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": f"natbench/{current}"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        # Try requests as fallback
        try:
            import requests  # type: ignore[import]
            resp2 = requests.get(api_url, timeout=8,
                                 headers={"User-Agent": f"natbench/{current}"})
            raw = resp2.text
        except Exception as exc2:
            result["error"] = f"Network error: {exc2}"
            return result

    if not raw:
        result["error"] = "Empty response from GitHub API"
        return result

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        result["error"] = f"JSON parse error: {exc}"
        return result

    tag = data.get("tag_name", "")
    if not tag:
        result["error"] = "No tag_name in GitHub response"
        return result

    latest = tag.lstrip("v")
    result["latest"] = latest
    result["url"] = data.get("html_url", result["url"])

    try:
        result["newer"] = _version_tuple(latest) > _version_tuple(current)
    except Exception:
        result["newer"] = False

    return result


def self_update(verbose: bool = True) -> int:
    """
    Update NatBench to the latest version.

    - Git install: ``git pull`` then ``pip install -e .``
    - PyPI install: ``pip install --upgrade natbench``

    Args:
        verbose: Print progress messages to stdout.

    Returns:
        0 on success, 1 on error.
    """
    def _print(msg: str) -> None:
        if verbose:
            print(msg)

    current = _current_version()
    _print(f"Current version : {current}")

    git_root = _detect_git_root()

    if git_root:
        _print(f"Git install detected at: {git_root}")
        _print("Running git pull…")
        rc, out, err = _run(["git", "pull"], cwd=str(git_root))
        if rc != 0:
            _print(f"git pull failed:\n{err or out}")
            return 1
        if out:
            _print(out)

        _print("Re-installing editable package…")
        pip_cmd = [sys.executable, "-m", "pip", "install", "-e", "."]
        rc, out, err = _run(pip_cmd, cwd=str(git_root))
        if rc != 0:
            # Retry with --break-system-packages for distro-managed Python envs
            combined = (out + err).lower()
            if "externally-managed" in combined or "break-system-packages" in combined:
                _print("Detected externally-managed environment, retrying with --break-system-packages…")
                rc, out, err = _run(
                    pip_cmd + ["--break-system-packages"],
                    cwd=str(git_root),
                )
        if rc != 0:
            _print(f"pip install -e . failed:\n{err or out}")
            _print("Tip: activate a virtualenv before running --self-update, or install manually.")
            return 1
        if out:
            _print(out)
    else:
        _print("PyPI install detected.")
        _print("Running pip install --upgrade natbench…")
        pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "natbench"]
        rc, out, err = _run(pip_cmd)
        if rc != 0:
            combined = (out + err).lower()
            if "externally-managed" in combined or "break-system-packages" in combined:
                _print("Detected externally-managed environment, retrying with --break-system-packages…")
                rc, out, err = _run(pip_cmd + ["--break-system-packages"])
        if rc != 0:
            _print(f"pip upgrade failed:\n{err or out}")
            _print("Tip: activate a virtualenv before running --self-update, or install manually.")
            return 1
        if out:
            _print(out)

    new_version = _current_version()
    if new_version != current:
        _print(f"Updated: {current} -> {new_version}")
    else:
        _print(f"Already up-to-date ({current}).")

    return 0
