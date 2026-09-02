# -*- mode: python ; coding: utf-8 -*-
# NatBench GUI — PyInstaller spec file
# Build: pyinstaller natbench-gui.spec
#        or: python build.py gui

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
            rel_dir = root
            datas.append((src, rel_dir))

a = Analysis(
    ["natbench/_gui_entry.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "natbench",
        "natbench.cli",
        "natbench.core",
        "natbench.gui",
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
        # tkinter and its sub-modules (needed for GUI)
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "tkinter.filedialog",
        "tkinter.simpledialog",
        "tkinter.font",
        "tkinter.scrolledtext",
        "_tkinter",
        # stdlib
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
        "queue",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
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
    name="natbench-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # windowed — no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
