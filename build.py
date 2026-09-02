#!/usr/bin/env python3
"""Build NatBench executables for the current platform.

Usage
-----
    python build.py            # build both CLI and GUI
    python build.py cli        # build CLI only
    python build.py gui        # build GUI only
    python build.py all        # build both (same as no arg)

Requirements
------------
    pip install pyinstaller

Output
------
    dist/natbench          (Linux/macOS)
    dist/natbench.exe      (Windows)
    dist/natbench-gui      (Linux/macOS)
    dist/natbench-gui.exe  (Windows)
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Platform helpers
# ---------------------------------------------------------------------------

def _exe_name(stem: str) -> str:
    """Return platform-correct binary name."""
    if sys.platform == "win32":
        return stem + ".exe"
    return stem


def _platform_label() -> str:
    """Human-readable platform string for display."""
    if sys.platform == "win32":
        return "Windows"
    if sys.platform == "darwin":
        return "macOS"
    return "Linux"


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------

def _run_pyinstaller(spec: str) -> int:
    """Run PyInstaller with *spec* and return the exit code."""
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", spec]
    print(f"\n[build] Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    return result.returncode


def _print_binary_info(path: Path) -> None:
    """Print size and SHA-256 checksum of the built binary."""
    if not path.exists():
        print(f"[build] WARNING: expected binary not found at {path}")
        return

    size_bytes = path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)

    sha256 = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha256.update(chunk)

    print(f"\n[build] Binary : {path}")
    print(f"[build] Size   : {size_mb:.2f} MB ({size_bytes:,} bytes)")
    print(f"[build] SHA-256: {sha256.hexdigest()}")


# ---------------------------------------------------------------------------
# Build targets
# ---------------------------------------------------------------------------

def build_cli() -> bool:
    """Build the CLI binary from natbench.spec. Returns True on success."""
    print(f"\n{'=' * 60}")
    print(f"  Building natbench CLI  [{_platform_label()}]")
    print(f"{'=' * 60}")

    spec = "natbench.spec"
    if not Path(spec).exists():
        print(f"[build] ERROR: {spec} not found — run from the project root.")
        return False

    rc = _run_pyinstaller(spec)
    if rc != 0:
        print(f"[build] ERROR: PyInstaller exited with code {rc}")
        return False

    _print_binary_info(Path("dist") / _exe_name("natbench"))
    return True


def build_gui() -> bool:
    """Build the GUI binary from natbench-gui.spec. Returns True on success."""
    print(f"\n{'=' * 60}")
    print(f"  Building natbench-gui  [{_platform_label()}]")
    print(f"{'=' * 60}")

    spec = "natbench-gui.spec"
    if not Path(spec).exists():
        print(f"[build] ERROR: {spec} not found — run from the project root.")
        return False

    rc = _run_pyinstaller(spec)
    if rc != 0:
        print(f"[build] ERROR: PyInstaller exited with code {rc}")
        return False

    _print_binary_info(Path("dist") / _exe_name("natbench-gui"))
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    # Ensure we run from the project root (where build.py lives)
    project_root = Path(__file__).parent.resolve()
    os.chdir(project_root)
    print(f"[build] Project root : {project_root}")
    print(f"[build] Platform     : {_platform_label()} ({sys.platform})")
    print(f"[build] Python       : {sys.version.split()[0]}")

    # Check PyInstaller is available
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("\n[build] ERROR: PyInstaller is not installed.")
        print("[build]        Run: pip install pyinstaller")
        return 1

    if target in ("cli",):
        ok = build_cli()
    elif target in ("gui",):
        ok = build_gui()
    elif target in ("all", "both"):
        ok_cli = build_cli()
        ok_gui = build_gui()
        ok = ok_cli and ok_gui
    else:
        print(f"[build] Unknown target '{target}'. Use: cli | gui | all")
        return 1

    if ok:
        print("\n[build] Done. Binaries are in the dist/ directory.")
        return 0
    else:
        print("\n[build] Build FAILED — see errors above.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
