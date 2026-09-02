# -*- mode: python ; coding: utf-8 -*-
# NatBench CLI — PyInstaller spec file
# Build: pyinstaller natbench.spec
#        or: python build.py cli

import os
from pathlib import Path

block_cipher = None

# Collect locale JSON files
datas = []
locales_dir = Path("natbench/locales")
if locales_dir.exists():
    for f in locales_dir.glob("*.json"):
        datas.append((str(f), "natbench/locales"))

# Collect all plugin .py files (preserving subpackage structure)
plugins_root = Path("natbench/plugins")
for root, dirs, files in os.walk(plugins_root):
    for fname in files:
        if fname.endswith(".py"):
            src = os.path.join(root, fname)
            # Destination mirrors the source tree relative to project root
            rel_dir = root  # e.g. natbench/plugins/resolvers
            datas.append((src, rel_dir))

a = Analysis(
    ["natbench/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "natbench",
        "natbench.cli",
        "natbench.core",
        "natbench.servers",
        "natbench.system",
        "natbench.i18n",
        "natbench.plugin_base",
        "natbench.plugin_loader",
        "natbench.plugins",
        "natbench.plugins.resolvers",
        "natbench.plugins.scorers",
        "natbench.plugins.exporters",
        "natbench.plugins.providers",
        # stdlib modules that PyInstaller sometimes misses
        "ssl",
        "socket",
        "http.client",
        "urllib.request",
        "urllib.parse",
        "json",
        "csv",
        "threading",
        "concurrent.futures",
        "struct",
        "base64",
        "hashlib",
        "time",
        "statistics",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "wx",
        "gi",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="natbench",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,          # strip debug symbols
    upx=False,           # set True if UPX is installed for smaller binary
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,        # CLI app — keep console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
