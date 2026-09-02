"""
NatBench gui.py — Tkinter GUI (900x650).

Uses customtkinter when available, falls back to standard ttk with a dark theme.
All text is routed through i18n.t() and switches language dynamically.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import messagebox, ttk, filedialog
except ImportError as _tk_err:
    raise SystemExit(
        "tkinter is not available. Install it first:\n"
        "  Arch/CachyOS:    sudo pacman -S tk\n"
        "  Debian/Ubuntu:   sudo apt install python3-tk\n"
        "  Fedora:          sudo dnf install python3-tkinter\n"
        f"Original error: {_tk_err}"
    ) from None
from typing import Optional

# ---------------------------------------------------------------------------
# Optional customtkinter
# ---------------------------------------------------------------------------

try:
    import customtkinter as ctk
    _HAS_CTK = True
except ImportError:
    ctk = None  # type: ignore[assignment]
    _HAS_CTK = False

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------

try:
    from .core import ServerStats, run_benchmark
    from .servers import SERVER_DB, get_servers_by_tag
    from .i18n import t, detect_lang, score_label, LANG_NAMES, SUPPORTED_LANGS
    from .system import (
        DnsConfig,
        check_root,
        get_current_dns,
        get_interfaces,
        get_system_dns_servers,
        set_dns,
    )
    from .updater import check_for_updates
    from .profiles import list_profiles, load_profile, save_profile, delete_profile, validate_profile
    from .__version__ import __version__ as _APP_VERSION, __author__ as _APP_AUTHOR, __url__ as _APP_URL
except ImportError:
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    from natbench.core import ServerStats, run_benchmark
    from natbench.servers import SERVER_DB, get_servers_by_tag
    from natbench.i18n import t, detect_lang, score_label, LANG_NAMES, SUPPORTED_LANGS
    from natbench.system import (
        DnsConfig,
        check_root,
        get_current_dns,
        get_interfaces,
        get_system_dns_servers,
        set_dns,
    )
    from natbench.updater import check_for_updates
    from natbench.profiles import list_profiles, load_profile, save_profile, delete_profile, validate_profile
    from natbench.__version__ import __version__ as _APP_VERSION, __author__ as _APP_AUTHOR, __url__ as _APP_URL

# ---------------------------------------------------------------------------
# Colour palette (dark theme)
# ---------------------------------------------------------------------------

_THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg":        "#1a1a2e",
        "panel":     "#16213e",
        "accent":    "#0f3460",
        "highlight": "#e94560",
        "gold":      "#ffaa00",
        "fg":        "#e0e0e0",
        "fg_dim":    "#888899",
        "green":     "#4caf50",
        "yellow":    "#ffcc00",
        "red":       "#e94560",
        "treesel":   "#0f3460",
        "entry_bg":  "#0d1b34",
    },
    "light": {
        "bg":        "#f4f6f8",
        "panel":     "#dde3ea",
        "accent":    "#3a7bd5",
        "highlight": "#c0392b",
        "gold":      "#b8860b",
        "fg":        "#1a1a2e",
        "fg_dim":    "#555566",
        "green":     "#27ae60",
        "yellow":    "#f39c12",
        "red":       "#c0392b",
        "treesel":   "#aac4e8",
        "entry_bg":  "#ffffff",
    },
    "colorblind": {           # Okabe-Ito safe palette on neutral dark gray
        "bg":        "#1c1c1c",
        "panel":     "#2a2a2a",
        "accent":    "#0072b2",  # blue
        "highlight": "#e69f00",  # orange
        "gold":      "#f0e442",  # yellow
        "fg":        "#ffffff",
        "fg_dim":    "#aaaaaa",
        "green":     "#009e73",  # bluish-green
        "yellow":    "#f0e442",
        "red":       "#d55e00",  # vermillion
        "treesel":   "#005b8e",
        "entry_bg":  "#242424",
    },
    "high_contrast": {
        "bg":        "#000000",
        "panel":     "#111111",
        "accent":    "#0055ff",
        "highlight": "#ffff00",
        "gold":      "#ffff00",
        "fg":        "#ffffff",
        "fg_dim":    "#cccccc",
        "green":     "#00ff00",
        "yellow":    "#ffff00",
        "red":       "#ff0000",
        "treesel":   "#0055ff",
        "entry_bg":  "#000011",
    },
}

C = dict(_THEMES["dark"])  # active theme, mutable copy
_CURRENT_THEME = "dark"

_PROTOCOLS = ["udp", "tcp", "dot", "doh", "udp+tcp", "all"]

# ---------------------------------------------------------------------------
# App icon (base64-encoded 64×64 PNG generated from assets/icon.svg)
# ---------------------------------------------------------------------------

_ICON_B64 = (
    "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"
    "8EZqsKkPAAAAAElFTkSuQmCC"
)


def _set_app_icon(root: tk.Tk) -> None:
    """Set the application window icon from embedded base64 PNG data."""
    try:
        img = tk.PhotoImage(data=_ICON_B64)
        root.iconphoto(True, img)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# TTK dark-theme style (used when customtkinter is absent)
# ---------------------------------------------------------------------------


def _apply_dark_ttk_style() -> None:
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    bg, panel, accent, fg, hl = C["bg"], C["panel"], C["accent"], C["fg"], C["highlight"]
    entry_bg = C["entry_bg"]

    style.configure(".", background=bg, foreground=fg, fieldbackground=entry_bg,
                    font=("Segoe UI", 10))
    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("TLabelframe", background=panel, foreground=fg, bordercolor=accent)
    style.configure("TLabelframe.Label", background=panel, foreground=C["gold"])
    style.configure("TButton",
                    background=accent, foreground=fg,
                    borderwidth=0, focuscolor=hl, padding=(6, 4))
    style.map("TButton",
              background=[("active", hl), ("pressed", hl)],
              foreground=[("active", "#ffffff")])
    style.configure("Accent.TButton",
                    background=hl, foreground="#ffffff",
                    font=("Segoe UI", 10, "bold"))
    style.map("Accent.TButton", background=[("active", "#c73250")])
    style.configure("TNotebook", background=bg, borderwidth=0)
    style.configure("TNotebook.Tab", background=panel, foreground=fg,
                    padding=(12, 5), borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", accent)],
              foreground=[("selected", "#ffffff")])
    style.configure("TCombobox", fieldbackground=entry_bg, background=panel,
                    foreground=fg, selectbackground=accent, arrowcolor=fg)
    style.map("TCombobox", fieldbackground=[("readonly", entry_bg)])
    style.configure("TEntry", fieldbackground=entry_bg, foreground=fg,
                    insertcolor=fg, borderwidth=1, relief="flat")
    style.configure("TSpinbox", fieldbackground=entry_bg, foreground=fg,
                    buttonbackground=panel, arrowcolor=fg)
    style.configure("Treeview",
                    background=panel, foreground=fg,
                    fieldbackground=panel, rowheight=22,
                    font=("Segoe UI", 9))
    style.configure("Treeview.Heading",
                    background=accent, foreground=fg,
                    relief="flat", font=("Segoe UI", 9, "bold"))
    style.map("Treeview",
              background=[("selected", C["treesel"])],
              foreground=[("selected", "#ffffff")])
    style.configure("TProgressbar",
                    troughcolor=panel, background=C["gold"],
                    thickness=10)
    style.configure("TCheckbutton",
                    background=bg, foreground=fg,
                    indicatorcolor=accent)
    style.map("TCheckbutton", indicatorcolor=[("selected", hl)])
    style.configure("TScrollbar",
                    background=panel, troughcolor=bg,
                    arrowcolor=fg, borderwidth=0)
    style.configure("Vertical.TScrollbar", width=14, arrowsize=14)
    style.configure("Horizontal.TScrollbar", width=14, arrowsize=14)
    style.map("TCombobox",
              fieldbackground=[("readonly", entry_bg)],
              foreground=[("readonly", fg)],
              selectbackground=[("readonly", accent)],
              selectforeground=[("readonly", fg)])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ms_color(ms: Optional[float]) -> str:
    if ms is None:
        return C["red"]
    if ms < 50:
        return "#00e676"
    if ms < 150:
        return C["green"]
    if ms < 300:
        return C["yellow"]
    return C["red"]


def _score_color(score: float) -> str:
    if score >= 85:
        return "#00e676"
    if score >= 70:
        return C["green"]
    if score >= 50:
        return C["yellow"]
    return C["red"]


def _fmt(ms: Optional[float]) -> str:
    return "—" if ms is None else f"{ms:.1f}"


def _bool_sym(v: bool) -> str:
    return "✓" if v else "✗"


# ---------------------------------------------------------------------------
# Server group definitions
# ---------------------------------------------------------------------------

_SERVER_GROUPS: dict[str, list[dict]] = {
    "Recommended": [
        s for s in SERVER_DB
        if "fast" in s.get("tags", []) or "anycast" in s.get("tags", [])
    ][:12],
    "Security": get_servers_by_tag("malware"),
    "Privacy": get_servers_by_tag("no-log"),
    "Regional": [
        s for s in SERVER_DB
        if any(t in s.get("tags", []) for t in ("china", "russia", "canada", "asia"))
    ],
    "Community": get_servers_by_tag("community"),
    "ISP": get_servers_by_tag("isp"),
}


# ===========================================================================
# Main Application Window
# ===========================================================================


class NatBenchApp:
    """
    Main application window.

    Args:
        lang: Initial language code (auto-detected if None).
    """

    def __init__(self, lang: Optional[str] = None) -> None:
        self._lang = lang or detect_lang()
        self._results: list[ServerStats] = []
        self._saved_dns: Optional[DnsConfig] = None
        self._dns_history: list[str] = []
        self._bench_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._custom_servers: list[dict] = []
        self._server_vars: dict[str, tk.BooleanVar] = {}
        self._prev_scores: dict[str, float] = self._load_history()
        # Auto-detected system/ISP DNS servers
        try:
            self._system_dns_servers: list[dict] = get_system_dns_servers()
        except Exception:
            self._system_dns_servers = []

        # --- Root window ---
        self._root = tk.Tk()
        self._root.title("NatBench")
        self._root.geometry("900x650")
        self._root.minsize(820, 580)
        self._root.configure(bg=C["bg"])

        if not _HAS_CTK:
            _apply_dark_ttk_style()
        else:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")

        _set_app_icon(self._root)
        self._build_menu()
        self._build_top_bar()
        self._build_main_area()
        self._build_status_bar()

        # Apply persisted settings
        _s = self._load_settings()
        if _s.get("geometry"):
            try:
                self._root.geometry(_s["geometry"])
            except Exception:
                pass
        if _s.get("lang"):
            self._lang = _s["lang"]
            self._lang_var.set(f"{LANG_NAMES.get(_s['lang'], _s['lang'])} ({_s['lang']})")
        if _s.get("theme") and _s["theme"] in _THEMES:
            self._apply_theme(_s["theme"])
        if _s.get("font_size"):
            try:
                self._font_size_var.set(_s["font_size"])
                self._set_font_size()
            except Exception:
                pass
        if _s.get("col_widths") and hasattr(self, "_tree"):
            for col, w in _s["col_widths"].items():
                try:
                    self._tree.column(col, width=int(w))
                except Exception:
                    pass
        if _s.get("sash_x") and hasattr(self, "_pane"):
            try:
                self._pane.update()
                self._pane.sash_place(0, int(_s["sash_x"]), 0)
            except Exception:
                pass

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_font_size()  # sync rowheight with initial font setting
        self._refresh_all_labels()
        self._update_current_dns_display()

    # ------------------------------------------------------------------
    # i18n shortcut
    # ------------------------------------------------------------------

    def _t(self, key: str, **kwargs: object) -> str:
        return t(key, self._lang, **kwargs)

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    _SETTINGS_PATH = Path.home() / ".config" / "natbench" / "settings.json"

    def _load_settings(self) -> dict:
        try:
            if self._SETTINGS_PATH.exists():
                with open(self._SETTINGS_PATH) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_settings(self) -> None:
        try:
            self._SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            settings: dict = {
                "geometry": self._root.winfo_geometry(),
                "theme": _CURRENT_THEME,
                "lang": self._lang,
                "font_size": self._font_size_var.get() if hasattr(self, "_font_size_var") else 9,
            }
            if hasattr(self, "_tree"):
                settings["col_widths"] = {
                    col: self._tree.column(col, "width")
                    for col in self._tree["columns"]
                }
            if hasattr(self, "_pane"):
                try:
                    settings["sash_x"] = self._pane.sash_coord(0)[0]
                except Exception:
                    pass
            with open(self._SETTINGS_PATH, "w") as f:
                json.dump(settings, f, indent=2)
        except Exception:
            pass

    _HISTORY_PATH = Path.home() / ".config" / "natbench" / "history.json"

    @staticmethod
    def _load_history() -> dict:
        try:
            p = NatBenchApp._HISTORY_PATH
            if p.exists():
                with open(p) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_history(self, results: list) -> None:
        try:
            self._HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {s.name: s.median_ms for s in results if s.median_ms is not None}
            with open(self._HISTORY_PATH, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _on_close(self) -> None:
        self._save_settings()
        self._root.destroy()

    # ------------------------------------------------------------------
    # Build: menu bar
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        self._menubar = tk.Menu(
            self._root,
            bg=C["panel"], fg=C["fg"],
            activebackground=C["accent"], activeforeground="#ffffff",
            relief="flat",
        )
        self._root.config(menu=self._menubar)

        # File
        self._menu_file = tk.Menu(self._menubar, tearoff=False,
                                   bg=C["panel"], fg=C["fg"],
                                   activebackground=C["accent"])
        self._menubar.add_cascade(label=self._t("menu_file"), menu=self._menu_file)
        self._menu_file.add_command(label=self._t("btn_export"),
                                     command=self._on_export,
                                     accelerator="Ctrl+E")
        self._menu_file.add_separator()
        self._menu_file.add_command(label="Exit", command=self._root.destroy,
                                     accelerator="Alt+F4")

        # Run
        self._menu_run = tk.Menu(self._menubar, tearoff=False,
                                  bg=C["panel"], fg=C["fg"],
                                  activebackground=C["accent"])
        self._menubar.add_cascade(label=self._t("menu_run"), menu=self._menu_run)
        self._menu_run.add_command(label=self._t("btn_start"),
                                    command=self._on_start,
                                    accelerator="Ctrl+R")
        self._menu_run.add_command(label=self._t("btn_stop"),
                                    command=self._on_stop,
                                    accelerator="Ctrl+T")
        self._menu_run.add_separator()
        self._menu_run.add_command(label=self._t("btn_reset"),
                                    command=self._on_clear,
                                    accelerator="Ctrl+Shift+R")

        # Settings
        self._menu_settings = tk.Menu(self._menubar, tearoff=False,
                                       bg=C["panel"], fg=C["fg"],
                                       activebackground=C["accent"])
        self._menubar.add_cascade(label=self._t("menu_settings"),
                                   menu=self._menu_settings)
        lang_menu = tk.Menu(self._menu_settings, tearoff=False,
                             bg=C["panel"], fg=C["fg"],
                             activebackground=C["accent"])
        self._menu_settings.add_cascade(label="Language", menu=lang_menu)
        for code in SUPPORTED_LANGS:
            name = LANG_NAMES.get(code, code)
            lang_menu.add_command(
                label=f"{name} ({code})",
                command=lambda c=code: self._change_lang(c),
            )
        theme_menu = tk.Menu(self._menu_settings, tearoff=False,
                             bg=C["panel"], fg=C["fg"],
                             activebackground=C["accent"])
        self._menu_settings.add_cascade(label="Theme", menu=theme_menu)
        for theme_name in _THEMES:
            theme_menu.add_command(
                label=theme_name.replace("_", " ").title(),
                command=lambda tn=theme_name: self._apply_theme(tn),
            )

        # Help
        self._menu_help = tk.Menu(self._menubar, tearoff=False,
                                   bg=C["panel"], fg=C["fg"],
                                   activebackground=C["accent"])
        self._menubar.add_cascade(label=self._t("menu_help"), menu=self._menu_help)
        self._menu_help.add_command(label=self._t("menu_about"),
                                     command=self._show_about,
                                     accelerator="F1")
        self._menu_help.add_command(
            label="Check for Updates",
            command=self._check_for_updates_gui,
        )

        # Keyboard bindings
        self._root.bind("<Control-e>", lambda e: self._on_export())
        self._root.bind("<Control-r>", lambda e: self._on_start())
        self._root.bind("<Control-t>", lambda e: self._on_stop())
        self._root.bind("<Control-R>", lambda e: self._on_clear())
        self._root.bind("<F1>", lambda e: self._show_about())

    # ------------------------------------------------------------------
    # Build: top bar
    # ------------------------------------------------------------------

    def _build_top_bar(self) -> None:
        bar = tk.Frame(self._root, bg=C["panel"], height=52)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        # App name
        tk.Label(
            bar, text=" NatBench",
            bg=C["panel"], fg=C["highlight"],
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left", padx=(12, 4), pady=8)

        tk.Label(
            bar, text="DNS Benchmark",
            bg=C["panel"], fg=C["fg_dim"],
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 20), pady=8, anchor="s")

        # Language selector (widget packed first so label appears to the left)
        self._lang_var = tk.StringVar(value=self._lang)
        lang_opts = [f"{LANG_NAMES.get(c, c)} ({c})" for c in SUPPORTED_LANGS]
        self._lang_cb = ttk.Combobox(
            bar, textvariable=self._lang_var,
            values=lang_opts, state="readonly", width=18,
        )
        # Set displayed value to match current lang
        self._lang_cb.set(f"{LANG_NAMES.get(self._lang, self._lang)} ({self._lang})")
        self._lang_cb.pack(side="right", padx=(0, 12), pady=10)
        self._lang_cb.bind("<<ComboboxSelected>>", self._on_lang_change)
        tk.Label(bar, text="Lang:", bg=C["panel"], fg=C["fg_dim"]).pack(side="right", padx=(0, 4))

        # AF (address-family) selector
        tk.Label(bar, text="AF:", bg=C["panel"], fg=C["fg_dim"]).pack(side="right", padx=(0, 4))
        self._af_var = tk.StringVar(value="auto")
        af_cb = ttk.Combobox(bar, textvariable=self._af_var,
                             values=["auto", "ipv4", "ipv6"],
                             state="readonly", width=6)
        af_cb.pack(side="right", padx=(0, 8), pady=10)

        # Protocol selector
        self._protocol_var = tk.StringVar(value="udp")
        proto_cb = ttk.Combobox(
            bar, textvariable=self._protocol_var,
            values=_PROTOCOLS, state="readonly", width=6,
        )
        proto_cb.pack(side="right", padx=(0, 12), pady=10)
        tk.Label(bar, text="Protocol:", bg=C["panel"], fg=C["fg_dim"]).pack(side="right", padx=(0, 4))

        # Font size spinbox
        self._font_size_var = tk.IntVar(value=9)
        font_spin = ttk.Spinbox(
            bar, textvariable=self._font_size_var,
            from_=7, to=14, width=3,
            command=self._set_font_size,
        )
        font_spin.pack(side="right", padx=(0, 12), pady=10)
        tk.Label(bar, text="Font:", bg=C["panel"], fg=C["fg_dim"]).pack(side="right", padx=(0, 4))

        # Query count
        self._count_var = tk.IntVar(value=10)
        count_spin = ttk.Spinbox(
            bar, textvariable=self._count_var,
            from_=1, to=100, width=5,
        )
        count_spin.pack(side="right", padx=(0, 12), pady=10)
        tk.Label(bar, text="Queries:", bg=C["panel"], fg=C["fg_dim"]).pack(side="right", padx=(0, 4))

    # ------------------------------------------------------------------
    # Build: main area (left panel + notebook)
    # ------------------------------------------------------------------

    def _build_main_area(self) -> None:
        self._pane = tk.PanedWindow(
            self._root, orient="horizontal",
            bg=C["bg"], sashwidth=5, sashrelief="flat",
        )
        self._pane.pack(fill="both", expand=True, padx=6, pady=(4, 2))

        # --- Left panel ---
        left = tk.Frame(self._pane, bg=C["panel"], width=260)
        left.pack_propagate(False)
        self._pane.add(left, minsize=200)
        self._build_left_panel(left)

        # --- Right: Notebook ---
        right = tk.Frame(self._pane, bg=C["bg"])
        self._pane.add(right, minsize=500)
        self._build_notebook(right)

        # Set default sash position after layout
        self._pane.update()
        self._pane.sash_place(0, 260, 0)

    def _make_collapsible_group(self, parent: tk.Frame, title: str,
                                initially_expanded: bool = True,
                                group_vars: Optional[list] = None):
        """Create a collapsible group. Returns (header_frame, content_frame)."""
        state = {"expanded": initially_expanded}
        content = tk.Frame(parent, bg=C["panel"])

        def toggle() -> None:
            state["expanded"] = not state["expanded"]
            if state["expanded"]:
                content.pack(fill="x", after=header_frame)
                arrow_btn.config(text="▼")
            else:
                content.pack_forget()
                arrow_btn.config(text="▶")

        def _on_group_check() -> None:
            val = group_var.get()
            for v in (group_vars or []):
                v.set(val)

        header_frame = tk.Frame(parent, bg=C["panel"])
        header_frame.pack(fill="x", pady=(4, 0))

        group_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            header_frame, variable=group_var,
            bg=C["panel"], selectcolor=C["accent"],
            activebackground=C["panel"],
            command=_on_group_check,
        ).pack(side="left", padx=(2, 0))

        pfx = "▼" if initially_expanded else "▶"
        arrow_btn = tk.Button(
            header_frame, text=pfx,
            bg=C["panel"], fg=C["gold"],
            font=("Segoe UI", 8), width=2,
            relief="flat", cursor="hand2",
            command=toggle, activebackground=C["accent"],
            activeforeground=C["fg"],
        )
        arrow_btn.pack(side="left")

        tk.Label(
            header_frame, text=title,
            bg=C["panel"], fg=C["gold"],
            font=("Segoe UI", 8, "bold"), anchor="w",
        ).pack(side="left", fill="x", expand=True)

        self._group_headers.append(header_frame)
        if initially_expanded:
            content.pack(fill="x")
        return header_frame, content

    def _build_left_panel(self, parent: tk.Frame) -> None:
        self._group_headers: list[tk.Button] = []

        self._lbl_all_servers = tk.Label(
            parent, text=self._t("label_all_servers"),
            bg=C["panel"], fg=C["gold"],
            font=("Segoe UI", 10, "bold"),
        )
        self._lbl_all_servers.pack(anchor="w", padx=10, pady=(10, 4))

        # Select all / none
        btn_row = tk.Frame(parent, bg=C["panel"])
        btn_row.pack(fill="x", padx=8, pady=(0, 4))
        self._btn_all = ttk.Button(btn_row, text="All", command=self._select_all_servers, width=6)
        self._btn_all.pack(side="left")
        self._btn_none = ttk.Button(btn_row, text="None", command=self._select_no_servers, width=6)
        self._btn_none.pack(side="left", padx=(4, 0))

        # Scrollable server list
        list_frame = tk.Frame(parent, bg=C["panel"])
        list_frame.pack(fill="both", expand=True, padx=4, pady=2)

        canvas = tk.Canvas(list_frame, bg=C["panel"], highlightthickness=0)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=C["panel"])
        canvas_win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_frame_configure(event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_win, width=canvas.winfo_width())

        inner.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win, width=e.width))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        # --- Quick-select row ---
        best_row = tk.Frame(inner, bg=C["panel"])
        best_row.pack(fill="x", pady=(4, 2))
        ttk.Button(best_row, text="⭐ Best", command=self._select_best_servers, width=7).pack(side="left")
        ttk.Button(best_row, text="🔒 Secure", command=self._select_secure_servers, width=7).pack(side="left", padx=(2, 0))
        ttk.Button(best_row, text="⚡ Fast", command=self._select_fast_servers, width=7).pack(side="left", padx=(2, 0))
        ttk.Button(best_row, text="🌍 Region", command=self._select_region_servers, width=7).pack(side="left", padx=(2, 0))

        # --- System/ISP DNS group at the top (always visible, no collapse) ---
        if self._system_dns_servers:
            grp_lbl = tk.Label(
                inner, text=" \U0001f3e0 Your System DNS",
                bg=C["highlight"], fg="#ffffff",
                font=("Segoe UI", 8, "bold"),
                anchor="w",
            )
            grp_lbl.pack(fill="x", pady=(2, 1))

            for srv in self._system_dns_servers:
                raw_ip = srv.get("_raw_ip", srv.get("ip4") or srv.get("ip6", "?"))
                label = srv.get("_label", "")
                display = f"\U0001f3e0 {raw_ip}"
                if label:
                    display += f" ({label})"
                var = tk.BooleanVar(value=True)
                # Use a unique key for system DNS vars
                key = f"__system_{raw_ip}"
                self._server_vars[key] = var
                srv["_gui_key"] = key
                cb = tk.Checkbutton(
                    inner, text=display[:32], variable=var,
                    bg=C["panel"], fg=C["gold"],
                    selectcolor=C["accent"], activebackground=C["panel"],
                    font=("Segoe UI", 8, "bold"), anchor="w",
                )
                cb.pack(fill="x", padx=4)

        for group_name, servers in _SERVER_GROUPS.items():
            if not servers:
                continue
            # Build/reuse vars for this group first (fix duplicate-key bug)
            grp_var_list: list[tk.BooleanVar] = []
            for srv in servers:
                name = srv.get("name", "?")
                if name not in self._server_vars:
                    self._server_vars[name] = tk.BooleanVar(value=True)
                grp_var_list.append(self._server_vars[name])

            initially_expanded = group_name != "ISP"
            _header, content_frame = self._make_collapsible_group(
                inner, group_name, initially_expanded=initially_expanded,
                group_vars=grp_var_list,
            )

            for srv in servers:
                name = srv.get("name", "?")
                var = self._server_vars[name]
                ip_disp = srv.get("ip4") or srv.get("ip6") or ""
                display = f"{name}  {ip_disp}" if ip_disp else name
                tk.Checkbutton(
                    content_frame, text=display[:42], variable=var,
                    bg=C["panel"], fg=C["fg"],
                    selectcolor=C["accent"], activebackground=C["panel"],
                    font=("Segoe UI", 8), anchor="w",
                ).pack(fill="x", padx=4)

        # Custom server entry
        sep = ttk.Separator(parent, orient="horizontal")
        sep.pack(fill="x", padx=8, pady=6)

        self._lbl_custom = tk.Label(
            parent, text=self._t("label_custom_server"),
            bg=C["panel"], fg=C["gold"], font=("Segoe UI", 9, "bold"),
        )
        self._lbl_custom.pack(anchor="w", padx=10)

        custom_row = tk.Frame(parent, bg=C["panel"])
        custom_row.pack(fill="x", padx=8, pady=(4, 8))
        self._custom_entry = ttk.Entry(custom_row, width=16)
        self._custom_entry.pack(side="left", fill="x", expand=True)
        self._btn_add = ttk.Button(custom_row, text="Add", command=self._add_custom_server, width=5)
        self._btn_add.pack(side="left", padx=(4, 0))

    def _build_notebook(self, parent: tk.Frame) -> None:
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True)
        self._notebook = nb

        # --- Tab 1: Benchmark ---
        tab_bench = tk.Frame(nb, bg=C["bg"])
        nb.add(tab_bench, text=self._t("btn_start"))
        self._tab_bench = tab_bench
        self._build_benchmark_tab(tab_bench)

        # --- Tab 2: System DNS ---
        tab_dns = tk.Frame(nb, bg=C["bg"])
        nb.add(tab_dns, text=self._t("label_system_dns"))
        self._tab_dns = tab_dns
        self._build_system_dns_tab(tab_dns)

        # --- Tab 3: Profiles ---
        tab_profiles = tk.Frame(nb, bg=C["bg"])
        nb.add(tab_profiles, text="Profiles")
        self._tab_profiles = tab_profiles
        self._build_profiles_tab(tab_profiles)

        # --- Tab 4: Export ---
        tab_export = tk.Frame(nb, bg=C["bg"])
        nb.add(tab_export, text=self._t("btn_export"))
        self._tab_export = tab_export
        self._build_export_tab(tab_export)

        # --- Tab 5: About ---
        tab_about = tk.Frame(nb, bg=C["bg"])
        nb.add(tab_about, text=self._t("menu_about"))
        self._tab_about = tab_about
        self._build_about_tab(tab_about)

        # --- Tab 6: Traceroute ---
        tab_trace = tk.Frame(nb, bg=C["bg"])
        nb.add(tab_trace, text="Traceroute")
        self._tab_trace = tab_trace
        self._build_traceroute_tab(tab_trace)

    # ------------------------------------------------------------------
    # Tab: Benchmark
    # ------------------------------------------------------------------

    def _build_benchmark_tab(self, parent: tk.Frame) -> None:
        # Progress bar row
        prog_frame = tk.Frame(parent, bg=C["bg"])
        prog_frame.pack(fill="x", padx=10, pady=(8, 0))

        self._progress_var = tk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Progressbar(
            prog_frame, variable=self._progress_var,
            maximum=100, mode="determinate",
        )
        self._progress_bar.pack(side="left", fill="x", expand=True)

        self._lbl_progress_status = tk.Label(
            prog_frame, text="", bg=C["bg"], fg=C["fg_dim"],
            font=("Segoe UI", 8), width=8, anchor="e",
        )
        self._lbl_progress_status.pack(side="right", padx=(4, 0))

        # Currently-testing label on its own row (full width, no truncation)
        self._lbl_current = tk.Label(
            parent, text="", bg=C["bg"], fg=C["fg_dim"],
            font=("Segoe UI", 8), anchor="w",
        )
        self._lbl_current.pack(fill="x", padx=10, pady=(1, 4))

        # Start/Stop buttons
        btn_row = tk.Frame(parent, bg=C["bg"])
        btn_row.pack(fill="x", padx=10, pady=(0, 6))
        self._btn_start = ttk.Button(
            btn_row, text=self._t("btn_start"),
            style="Accent.TButton", command=self._on_start,
        )
        self._btn_start.pack(side="left")
        self._btn_stop = ttk.Button(
            btn_row, text=self._t("btn_stop"),
            command=self._on_stop,
        )
        self._btn_stop.pack(side="left", padx=(6, 0))
        self._btn_stop.state(["disabled"])
        ttk.Button(
            btn_row, text=self._t("btn_reset"),
            command=self._on_clear,
        ).pack(side="left", padx=(6, 0))

        # Results treeview
        cols = (
            "rank", "name", "ip", "median", "p95", "min", "max",
            "reliability", "score", "dnssec", "malware", "ads",
        )
        tree_frame = tk.Frame(parent, bg=C["bg"])
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        self._tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings",
            selectmode="browse",
        )
        col_widths = {
            "rank": 42, "name": 180, "ip": 120, "median": 80, "p95": 72,
            "min": 64, "max": 64, "reliability": 90, "score": 60,
            "dnssec": 64, "malware": 68, "ads": 48,
        }
        for col in cols:
            self._tree.heading(col, text=self._t(f"col_{col}"),
                               command=lambda c=col: self._sort_tree(c))
            self._tree.column(col, width=col_widths.get(col, 80),
                              anchor="center" if col in ("rank", "dnssec", "malware", "ads") else "w",
                              minwidth=30,
                              stretch=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(side="left", fill="both", expand=True)

        # Bind double-click and right-click
        self._tree.bind("<Double-1>", self._on_tree_double_click)
        self._tree.bind("<Button-3>", self._on_tree_right_click)

        # Context menu
        self._ctx_menu = tk.Menu(
            self._root, tearoff=False,
            bg=C["panel"], fg=C["fg"],
            activebackground=C["accent"],
        )
        self._ctx_menu.add_command(label="Set as DNS", command=self._ctx_set_dns)
        self._ctx_menu.add_command(label="Copy IP", command=self._ctx_copy_ip)
        self._ctx_menu.add_command(label="Copy connect string", command=self._ctx_copy_connect)
        self._ctx_menu.add_command(label="Traceroute", command=self._ctx_traceroute)

    # ------------------------------------------------------------------
    # Tab: System DNS
    # ------------------------------------------------------------------

    def _build_system_dns_tab(self, parent: tk.Frame) -> None:
        # Current DNS display
        frm = ttk.LabelFrame(parent, text=self._t("label_current_dns"), padding=10)
        frm.pack(fill="x", padx=10, pady=10)

        self._lbl_dns_current = tk.Label(
            frm, text="…",
            bg=C["panel"], fg=C["gold"],
            font=("Segoe UI", 12, "bold"),
        )
        self._lbl_dns_current.pack(anchor="w")

        self._lbl_dns_method = tk.Label(
            frm, text="", bg=C["panel"], fg=C["fg_dim"], font=("Segoe UI", 8),
        )
        self._lbl_dns_method.pack(anchor="w")

        # Interface selector
        iface_frm = tk.Frame(parent, bg=C["bg"])
        iface_frm.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(iface_frm, text="Interface:", bg=C["bg"], fg=C["fg"]).pack(side="left")
        self._iface_var = tk.StringVar()
        ifaces = get_interfaces()
        self._iface_cb = ttk.Combobox(
            iface_frm, textvariable=self._iface_var,
            values=ifaces, state="readonly", width=20,
        )
        if ifaces:
            self._iface_var.set(ifaces[0])
        self._iface_cb.pack(side="left", padx=(6, 0))

        # Buttons
        btn_row = tk.Frame(parent, bg=C["bg"])
        btn_row.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(
            btn_row, text="Set to Best", style="Accent.TButton",
            command=self._dns_set_best,
        ).pack(side="left")
        ttk.Button(
            btn_row, text="Set Custom…", command=self._dns_set_custom,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            btn_row, text=self._t("btn_refresh"), command=self._update_current_dns_display,
        ).pack(side="left", padx=(8, 0))

        # History
        hist_frm = ttk.LabelFrame(parent, text="DNS History", padding=6)
        hist_frm.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._hist_listbox = tk.Listbox(
            hist_frm,
            bg=C["entry_bg"], fg=C["fg"],
            selectbackground=C["treesel"],
            font=("Segoe UI", 9), height=8,
        )
        self._hist_listbox.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Tab: Export
    # ------------------------------------------------------------------

    def _build_export_tab(self, parent: tk.Frame) -> None:
        frm = tk.Frame(parent, bg=C["bg"])
        frm.pack(fill="x", padx=10, pady=12)

        tk.Label(frm, text="Format:", bg=C["bg"], fg=C["fg"]).grid(row=0, column=0, sticky="w", pady=4)
        self._export_fmt = tk.StringVar(value="json")
        self._export_fmt.trace_add("write", self._on_export_fmt_change)
        for i, fmt in enumerate(["json", "csv", "markdown", "html"]):
            tk.Radiobutton(
                frm, text=fmt.upper(), variable=self._export_fmt, value=fmt,
                bg=C["bg"], fg=C["fg"], selectcolor=C["accent"],
                activebackground=C["bg"],
            ).grid(row=0, column=i + 1, padx=6, pady=4)

        tk.Label(frm, text="File:", bg=C["bg"], fg=C["fg"]).grid(row=1, column=0, sticky="w", pady=4)
        self._export_path = tk.StringVar(value="natbench_results.json")
        ttk.Entry(frm, textvariable=self._export_path, width=38).grid(row=1, column=1, columnspan=3, sticky="ew", pady=4)
        ttk.Button(frm, text="Browse…", command=self._browse_export_path).grid(row=1, column=4, padx=6)

        ttk.Button(
            frm, text=self._t("btn_export"), style="Accent.TButton",
            command=self._do_export,
        ).grid(row=2, column=0, columnspan=2, pady=8, sticky="w")

        # Preview
        tk.Label(parent, text="Preview:", bg=C["bg"], fg=C["fg_dim"],
                 font=("Segoe UI", 8)).pack(anchor="w", padx=12)
        preview_frame = tk.Frame(parent, bg=C["bg"])
        preview_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._preview_text = tk.Text(
            preview_frame,
            bg=C["entry_bg"], fg=C["fg"],
            font=("Consolas", 8), wrap="none", state="disabled",
        )
        pvsb = ttk.Scrollbar(preview_frame, orient="vertical",
                              command=self._preview_text.yview)
        self._preview_text.configure(yscrollcommand=pvsb.set)
        pvsb.pack(side="right", fill="y")
        self._preview_text.pack(side="left", fill="both", expand=True)

        ttk.Button(parent, text="Refresh Preview",
                   command=self._refresh_preview).pack(anchor="w", padx=10, pady=(0, 8))

    # ------------------------------------------------------------------
    # Tab: Profiles
    # ------------------------------------------------------------------

    def _build_profiles_tab(self, parent: tk.Frame) -> None:
        """Profile manager: list, load, save, delete profiles."""
        top = tk.Frame(parent, bg=C["bg"])
        top.pack(fill="both", expand=True, padx=10, pady=8)

        # --- Profile list ---
        lbl = tk.Label(top, text="Profiles", bg=C["bg"], fg=C["highlight"],
                       font=("Segoe UI", 12, "bold"))
        lbl.pack(anchor="w", pady=(0, 4))

        list_frame = tk.Frame(top, bg=C["panel"])
        list_frame.pack(fill="both", expand=True)

        cols = ("name", "description", "vpn", "source")
        self._profile_tree = ttk.Treeview(
            list_frame, columns=cols, show="headings", height=10,
        )
        self._profile_tree.heading("name", text="Name")
        self._profile_tree.heading("description", text="Description")
        self._profile_tree.heading("vpn", text="VPN")
        self._profile_tree.heading("source", text="Source")
        self._profile_tree.column("name", width=130, minwidth=80)
        self._profile_tree.column("description", width=250, minwidth=100)
        self._profile_tree.column("vpn", width=50, anchor="center")
        self._profile_tree.column("source", width=80, anchor="center")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self._profile_tree.yview)
        self._profile_tree.configure(yscrollcommand=vsb.set)
        self._profile_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # --- Buttons ---
        btn_frame = tk.Frame(top, bg=C["bg"])
        btn_frame.pack(fill="x", pady=(8, 0))

        ttk.Button(btn_frame, text="Reload", command=self._refresh_profiles, width=10).pack(side="left", padx=(0, 4))
        ttk.Button(btn_frame, text="Load Profile", command=self._load_selected_profile, width=14).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Delete", command=self._delete_selected_profile, width=10).pack(side="left", padx=4)

        # --- Save current settings as profile ---
        save_frame = tk.Frame(top, bg=C["bg"])
        save_frame.pack(fill="x", pady=(12, 0))

        tk.Label(save_frame, text="Save current settings as profile:",
                 bg=C["bg"], fg=C["fg_dim"], font=("Segoe UI", 9)).pack(anchor="w")

        name_row = tk.Frame(save_frame, bg=C["bg"])
        name_row.pack(fill="x", pady=(4, 0))

        tk.Label(name_row, text="Name:", bg=C["bg"], fg=C["fg"], width=8, anchor="w").pack(side="left")
        self._profile_name_var = tk.StringVar()
        ttk.Entry(name_row, textvariable=self._profile_name_var, width=20).pack(side="left", padx=(0, 6))
        ttk.Button(name_row, text="Save Profile", command=self._save_current_as_profile, width=14).pack(side="left")

        # --- Info label ---
        self._profile_info_lbl = tk.Label(
            top, text="", bg=C["bg"], fg=C["accent"],
            font=("Segoe UI", 9), anchor="w", wraplength=450,
        )
        self._profile_info_lbl.pack(anchor="w", pady=(6, 0))

        self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        """Reload and display all profiles in the tree."""
        if not hasattr(self, "_profile_tree"):
            return
        self._profile_tree.delete(*self._profile_tree.get_children())
        for p in list_profiles():
            vpn = "✓" if p.get("vpn_enabled") else "—"
            src = "built-in" if p.get("is_builtin") else "user"
            self._profile_tree.insert("", "end", iid=p["name"], values=(
                p["name"], p.get("description", ""), vpn, src,
            ))

    def _load_selected_profile(self) -> None:
        """Apply the selected profile's settings to the Benchmark panel."""
        sel = self._profile_tree.selection()
        if not sel:
            messagebox.showinfo("NatBench", "Select a profile first.")
            return
        name = sel[0]
        try:
            prof = load_profile(name)
        except (FileNotFoundError, ValueError) as exc:
            messagebox.showerror("NatBench", f"Cannot load profile: {exc}")
            return

        # Apply protocol
        if hasattr(self, "_proto_var") and prof.get("protocol"):
            self._proto_var.set(prof["protocol"].upper())

        # Apply count
        if hasattr(self, "_count_var") and prof.get("count"):
            self._count_var.set(str(prof["count"]))

        # Apply timeout
        if hasattr(self, "_timeout_var") and prof.get("timeout") is not None:
            self._timeout_var.set(str(prof["timeout"]))

        # Apply workers
        if hasattr(self, "_workers_var") and prof.get("workers"):
            self._workers_var.set(str(prof["workers"]))

        # Switch to Benchmark tab
        if hasattr(self, "_notebook"):
            self._notebook.select(0)

        desc = prof.get("description", "")
        self._profile_info_lbl.config(
            text=f"Loaded: {name}" + (f" — {desc}" if desc else "")
        )

    def _delete_selected_profile(self) -> None:
        sel = self._profile_tree.selection()
        if not sel:
            messagebox.showinfo("NatBench", "Select a profile first.")
            return
        name = sel[0]
        # Find if built-in
        items = {p["name"]: p for p in list_profiles()}
        if items.get(name, {}).get("is_builtin"):
            messagebox.showwarning("NatBench", f"Cannot delete built-in profile '{name}'.")
            return
        if not messagebox.askyesno("NatBench", f"Delete profile '{name}'?"):
            return
        try:
            delete_profile(name)
        except Exception as exc:
            messagebox.showerror("NatBench", f"Delete failed: {exc}")
            return
        self._refresh_profiles()
        self._profile_info_lbl.config(text=f"Deleted: {name}")

    def _save_current_as_profile(self) -> None:
        name = self._profile_name_var.get().strip()
        if not name:
            messagebox.showwarning("NatBench", "Enter a profile name first.")
            return
        profile = {
            "name": name,
            "description": "",
            "protocol": getattr(self, "_proto_var", tk.StringVar()).get().lower() or "udp",
            "count": int(getattr(self, "_count_var", tk.StringVar(value="10")).get() or 10),
            "timeout": float(getattr(self, "_timeout_var", tk.StringVar(value="3.0")).get() or 3.0),
            "workers": int(getattr(self, "_workers_var", tk.StringVar(value="16")).get() or 16),
            "servers": "all",
            "include_system_dns": True,
            "scorer": "default",
            "tags": ["user"],
        }
        errors = validate_profile(profile)
        if errors:
            messagebox.showerror("NatBench", "\n".join(errors))
            return
        try:
            path = save_profile(profile)
        except ValueError as exc:
            messagebox.showerror("NatBench", str(exc))
            return
        self._profile_info_lbl.config(text=f"Saved: {path}")
        self._refresh_profiles()

    # ------------------------------------------------------------------
    # Tab: About
    # ------------------------------------------------------------------

    def _build_about_tab(self, parent: tk.Frame) -> None:
        _ver, _author, _url = _APP_VERSION, _APP_AUTHOR, _APP_URL

        tk.Label(
            parent, text="NatBench",
            bg=C["bg"], fg=C["highlight"],
            font=("Segoe UI", 26, "bold"),
        ).pack(pady=(30, 4))

        tk.Label(
            parent, text=self._t("app_tagline"),
            bg=C["bg"], fg=C["fg_dim"],
            font=("Segoe UI", 11),
        ).pack()

        tk.Label(
            parent, text=f"Version {_ver}",
            bg=C["bg"], fg=C["fg"],
            font=("Segoe UI", 10),
        ).pack(pady=(12, 2))

        tk.Label(
            parent, text=f"License: MIT  |  Author: {_author}",
            bg=C["bg"], fg=C["fg_dim"],
        ).pack()

        _link_font = ("Segoe UI", 10, "underline")
        url_lbl = tk.Label(
            parent, text="GitHub: github.com/natural78/natbench",
            bg=C["bg"], fg=C["accent"],
            cursor="hand2", font=_link_font,
        )
        url_lbl.pack(pady=(4, 1))
        url_lbl.bind("<Button-1>", lambda e: self._open_url("https://github.com/natural78/natbench"))

        codeberg_lbl = tk.Label(
            parent, text="Codeberg: codeberg.org/natural78/natbench",
            bg=C["bg"], fg=C["accent"],
            cursor="hand2", font=_link_font,
        )
        codeberg_lbl.pack(pady=1)
        codeberg_lbl.bind("<Button-1>", lambda e: self._open_url("https://codeberg.org/natural78/natbench"))

        blog_lbl = tk.Label(
            parent, text="Blog & Projekt: natural.yt",
            bg=C["bg"], fg=C["accent"],
            cursor="hand2", font=_link_font,
        )
        blog_lbl.pack(pady=(1, 4))
        blog_lbl.bind("<Button-1>", lambda e: self._open_url("https://natural.yt"))

        tk.Label(
            parent,
            text=(
                f"{len(SERVER_DB)} DNS servers in database\n"
                "Protocols: UDP · TCP · DoT · DoH\n"
                f"{len(SUPPORTED_LANGS)} languages supported"
            ),
            bg=C["bg"], fg=C["fg_dim"],
            justify="center",
        ).pack(pady=16)

    # ------------------------------------------------------------------
    # Tab: Traceroute
    # ------------------------------------------------------------------

    def _build_traceroute_tab(self, parent: tk.Frame) -> None:
        # Top controls row
        ctrl = tk.Frame(parent, bg=C["bg"])
        ctrl.pack(fill="x", padx=10, pady=(10, 4))

        tk.Label(ctrl, text="Host / IP:", bg=C["bg"], fg=C["fg"]).pack(side="left")
        self._trace_host_var = tk.StringVar(value="")
        self._trace_entry = ttk.Entry(ctrl, textvariable=self._trace_host_var, width=30)
        self._trace_entry.pack(side="left", padx=(6, 8))

        self._trace_af_var = tk.StringVar(value="auto")
        af_trace = ttk.Combobox(ctrl, textvariable=self._trace_af_var,
                                values=["auto", "ipv4", "ipv6"],
                                state="readonly", width=6)
        af_trace.pack(side="left", padx=(0, 6))

        self._trace_btn = ttk.Button(ctrl, text="Run Traceroute", command=self._run_traceroute)
        self._trace_btn.pack(side="left")

        self._trace_stop_btn = ttk.Button(ctrl, text="Stop", command=self._stop_traceroute,
                                           state="disabled")
        self._trace_stop_btn.pack(side="left", padx=(6, 0))

        tk.Label(ctrl, text="  From results:", bg=C["bg"], fg=C["fg_dim"],
                 font=("Segoe UI", 8)).pack(side="left", padx=(16, 4))
        self._trace_pick_btn = ttk.Button(ctrl, text="Use selected server",
                                           command=self._trace_use_selected)
        self._trace_pick_btn.pack(side="left")

        # Output area
        out_frame = tk.Frame(parent, bg=C["bg"])
        out_frame.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        self._trace_text = tk.Text(
            out_frame, bg=C["panel"], fg=C["fg"],
            font=("Consolas", 9), wrap="none",
            state="disabled", relief="flat", borderwidth=1,
            insertbackground=C["fg"],
        )
        trace_vsb = ttk.Scrollbar(out_frame, orient="vertical", command=self._trace_text.yview)
        trace_hsb = ttk.Scrollbar(out_frame, orient="horizontal", command=self._trace_text.xview)
        self._trace_text.configure(yscrollcommand=trace_vsb.set, xscrollcommand=trace_hsb.set)
        trace_vsb.pack(side="right", fill="y")
        trace_hsb.pack(side="bottom", fill="x")
        self._trace_text.pack(fill="both", expand=True)

        # Tag colors
        self._trace_text.tag_configure("header", foreground=C["gold"], font=("Consolas", 9, "bold"))
        self._trace_text.tag_configure("hop", foreground=C["fg"])
        self._trace_text.tag_configure("timeout", foreground=C["fg_dim"])
        self._trace_text.tag_configure("error", foreground=C["red"])
        self._trace_text.tag_configure("done", foreground=C["green"])

        self._trace_proc: Optional[object] = None
        self._trace_running = False

    # ------------------------------------------------------------------
    # Build: status bar
    # ------------------------------------------------------------------

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self._root, bg=C["panel"], height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self._lbl_status = tk.Label(
            bar, text=self._t("status_idle"),
            bg=C["panel"], fg=C["fg_dim"],
            font=("Segoe UI", 8), anchor="w",
        )
        self._lbl_status.pack(side="left", padx=10)

        self._lbl_server_count = tk.Label(
            bar, text=f"{len(SERVER_DB)} servers",
            bg=C["panel"], fg=C["fg_dim"],
            font=("Segoe UI", 8),
        )
        self._lbl_server_count.pack(side="right", padx=10)

        self._lbl_progress_status = tk.Label(
            bar, text="",
            bg=C["panel"], fg=C["gold"],
            font=("Segoe UI", 8),
        )
        self._lbl_progress_status.pack(side="right", padx=10)

    # ------------------------------------------------------------------
    # Theme switching
    # ------------------------------------------------------------------

    def _apply_theme(self, theme_name: str) -> None:
        global C, _CURRENT_THEME
        _CURRENT_THEME = theme_name
        old = dict(C)  # snapshot before update
        new = _THEMES.get(theme_name, _THEMES["dark"])
        C.update(new)

        # Build colour-remap: old_hex → new_hex for every role
        remap_bg: dict[str, str] = {}
        remap_fg: dict[str, str] = {}
        for role in ("bg", "panel", "accent", "highlight", "gold", "entry_bg", "treesel"):
            if old.get(role) != C[role]:
                remap_bg[old[role].lower()] = C[role]
        for role in ("fg", "fg_dim", "green", "yellow", "red"):
            if old.get(role) != C[role]:
                remap_fg[old[role].lower()] = C[role]
        # Also remap accent used as fg on links
        remap_fg[old.get("accent", "").lower()] = C["accent"]

        # ttk styles
        style = ttk.Style()
        style.configure(".", background=C["bg"], foreground=C["fg"],
                        fieldbackground=C["entry_bg"])
        style.configure("Treeview", background=C["panel"], foreground=C["fg"],
                        fieldbackground=C["panel"], rowheight=22)
        style.configure("Treeview.Heading", background=C["accent"], foreground=C["fg"])
        style.map("Treeview", background=[("selected", C["treesel"])])
        style.configure("TNotebook", background=C["bg"])
        style.configure("TNotebook.Tab", background=C["panel"], foreground=C["fg"])
        style.map("TNotebook.Tab",
                  background=[("selected", C["accent"])],
                  foreground=[("selected", C["highlight"])])
        style.configure("TProgressbar", troughcolor=C["panel"], background=C["highlight"])
        style.configure("TCombobox", fieldbackground=C["entry_bg"], foreground=C["fg"])
        style.configure("TSpinbox", fieldbackground=C["entry_bg"], foreground=C["fg"])
        style.configure("TLabelframe", background=C["bg"])
        style.configure("TLabelframe.Label", background=C["bg"], foreground=C["fg"])
        style.configure("TButton", background=C["panel"], foreground=C["fg"])
        style.configure("TCheckbutton", background=C["panel"], foreground=C["fg"])
        style.configure("Vertical.TScrollbar", background=C["panel"],
                        troughcolor=C["bg"], width=14, arrowsize=14)
        style.configure("Horizontal.TScrollbar", background=C["panel"],
                        troughcolor=C["bg"], width=14, arrowsize=14)
        # For light themes: ensure combobox/entry text is readable
        style.map("TCombobox",
                  fieldbackground=[("readonly", C["entry_bg"])],
                  foreground=[("readonly", C["fg"])],
                  selectbackground=[("readonly", C["treesel"])],
                  selectforeground=[("readonly", C["fg"])])
        style.map("TEntry",
                  fieldbackground=[("focus", C["entry_bg"]), ("!focus", C["entry_bg"])],
                  foreground=[("focus", C["fg"]), ("!focus", C["fg"])])

        # Walk all Tk widgets and remap bg/fg by old colour value
        def _recolor(widget):
            try:
                cls = widget.winfo_class()
                if cls in ("Frame", "Canvas", "Text", "Listbox"):
                    try:
                        cur = widget.cget("bg").lower()
                        if cur in remap_bg:
                            widget.configure(bg=remap_bg[cur])
                    except Exception:
                        pass
                elif cls == "Label":
                    try:
                        cur_bg = widget.cget("bg").lower()
                        if cur_bg in remap_bg:
                            widget.configure(bg=remap_bg[cur_bg])
                    except Exception:
                        pass
                    try:
                        cur_fg = widget.cget("fg").lower()
                        if cur_fg in remap_fg:
                            widget.configure(fg=remap_fg[cur_fg])
                    except Exception:
                        pass
            except Exception:
                pass
            for child in widget.winfo_children():
                _recolor(child)

        _recolor(self._root)

        # Menubar colours
        try:
            self._menubar.configure(bg=C["panel"], fg=C["fg"])
            for m in (self._menu_file, self._menu_run, self._menu_settings, self._menu_help):
                m.configure(bg=C["panel"], fg=C["fg"],
                            activebackground=C["accent"], activeforeground=C["fg"])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Language change
    # ------------------------------------------------------------------

    def _on_lang_change(self, event: Optional[tk.Event] = None) -> None:
        raw = self._lang_var.get()
        # Extract code from "English (en)"
        if "(" in raw and ")" in raw:
            code = raw.split("(")[-1].rstrip(")")
        else:
            code = raw.lower()
        if code in SUPPORTED_LANGS:
            self._change_lang(code)

    def _change_lang(self, code: str) -> None:
        self._lang = code
        self._lang_var.set(f"{LANG_NAMES.get(code, code)} ({code})")
        self._refresh_all_labels()

    def _refresh_all_labels(self) -> None:
        """Re-apply all translated strings to widgets."""
        self._root.title(f"NatBench — {self._t('app_tagline')}")
        # Notebook tabs
        if hasattr(self, "_notebook"):
            self._notebook.tab(0, text=self._t("label_results"))
            self._notebook.tab(1, text=self._t("label_system_dns"))
            self._notebook.tab(2, text=self._t("tab_profiles"))
            self._notebook.tab(3, text=self._t("btn_export"))
            self._notebook.tab(4, text=self._t("menu_about"))
            self._notebook.tab(5, text=self._t("tab_traceroute"))
        # Treeview headings
        if hasattr(self, "_tree"):
            for col in ("rank", "name", "ip", "median", "p95", "min", "max",
                        "reliability", "score", "dnssec", "malware", "ads"):
                self._tree.heading(col, text=self._t(f"col_{col}"))
        # Buttons
        if hasattr(self, "_btn_start"):
            self._btn_start.config(text=self._t("btn_start"))
        if hasattr(self, "_btn_stop"):
            self._btn_stop.config(text=self._t("btn_stop"))
        if hasattr(self, "_btn_all"):
            self._btn_all.config(text=self._t("btn_all"))
        if hasattr(self, "_btn_none"):
            self._btn_none.config(text=self._t("btn_none"))
        if hasattr(self, "_btn_add"):
            self._btn_add.config(text=self._t("btn_add"))
        # Custom server label
        if hasattr(self, "_lbl_custom"):
            self._lbl_custom.config(text=self._t("label_custom_server"))
        if hasattr(self, "_lbl_all_servers"):
            self._lbl_all_servers.config(text=self._t("label_all_servers"))
        # Menu cascade labels
        self._rebuild_menu_labels()
        # Update individual menu items (each wrapped independently)
        for _fn in [
            lambda: self._menu_file.entryconfig(0, label=self._t("btn_export")),
            lambda: self._menu_run.entryconfig(0, label=self._t("btn_start")),
            lambda: self._menu_run.entryconfig(1, label=self._t("btn_stop")),
            lambda: self._menu_run.entryconfig(3, label=self._t("btn_reset")),
            lambda: self._menu_help.entryconfig(0, label=self._t("menu_about")),
            lambda: self._menu_settings.entryconfig(0, label=self._t("menu_language") if self._t("menu_language") != "menu_language" else "Language"),
            lambda: self._menu_settings.entryconfig(1, label=self._t("menu_theme") if self._t("menu_theme") != "menu_theme" else "Theme"),
        ]:
            try:
                _fn()
            except Exception:
                pass

    def _rebuild_menu_labels(self) -> None:
        try:
            self._menubar.entryconfig(0, label=self._t("menu_file"))
            self._menubar.entryconfig(1, label=self._t("menu_run"))
            self._menubar.entryconfig(2, label=self._t("menu_settings"))
            self._menubar.entryconfig(3, label=self._t("menu_help"))
        except Exception:
            pass

    def _set_font_size(self) -> None:
        """Update Treeview and global font size when the spinbox changes."""
        try:
            size = int(self._font_size_var.get())
        except (ValueError, tk.TclError):
            return
        size = max(7, min(14, size))
        style = ttk.Style()
        rowheight = max(18, int(size * 2.2))
        style.configure("Treeview", font=("Segoe UI", size), rowheight=rowheight)
        style.configure("Treeview.Heading", font=("Segoe UI", size, "bold"))
        style.configure(".", font=("Segoe UI", size))
        # Force immediate redraw on all Treeviews
        for tv in (getattr(self, "_tree", None), getattr(self, "_profile_tree", None)):
            if tv:
                try:
                    tv.update_idletasks()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Benchmark lifecycle
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        if self._bench_thread and self._bench_thread.is_alive():
            return

        # Determine address-family preference
        af = self._af_var.get() if hasattr(self, "_af_var") else "auto"

        def _pick_ip(srv: dict):
            ip4 = srv.get("ip4") or srv.get("ip")
            ip6 = srv.get("ip6")
            if af == "ipv4":
                return ip4
            elif af == "ipv6":
                return ip6
            else:  # auto: prefer ip4, fall back to ip6
                return ip4 or ip6

        # Build selected server pool — system DNS first
        selected: list[dict] = []
        for srv in self._system_dns_servers:
            key = srv.get("_gui_key", "")
            var = self._server_vars.get(key)
            if var and var.get():
                ip = _pick_ip(srv)
                if ip or srv.get("doh_url") or srv.get("dot_host"):
                    srv_copy = dict(srv)
                    if ip:
                        srv_copy["ip"] = ip
                    selected.append(srv_copy)

        # Regular servers from SERVER_DB
        for name, var in self._server_vars.items():
            if not var.get() or name.startswith("__system_"):
                continue
            for srv in SERVER_DB:
                if srv.get("name") == name:
                    ip = _pick_ip(srv)
                    if ip or srv.get("doh_url") or srv.get("dot_host"):
                        srv_copy = dict(srv)
                        if ip:
                            srv_copy["ip"] = ip
                        selected.append(srv_copy)
                    break

        # Add custom servers
        for srv in self._custom_servers:
            ip = _pick_ip(srv)
            if ip or srv.get("doh_url") or srv.get("dot_host"):
                srv_copy = dict(srv)
                if ip:
                    srv_copy["ip"] = ip
                selected.append(srv_copy)

        if not selected:
            messagebox.showwarning("NatBench", "No servers selected.")
            return

        protocol = self._protocol_var.get()
        # Expand multi-protocol tokens
        if protocol == "all":
            protocols_to_run = ["udp", "tcp", "dot", "doh"]
        elif "+" in protocol:
            protocols_to_run = protocol.split("+")
        else:
            protocols_to_run = [protocol]

        self._stop_event.clear()
        self._results = []
        self._clear_tree()
        self._btn_start.state(["disabled"])
        self._btn_stop.state(["!disabled"])
        self._set_status(self._t("status_running"), C["gold"])
        self._progress_var.set(0)

        count = self._count_var.get()
        servers_snapshot = list(selected)

        def _worker() -> None:
            all_results: list[ServerStats] = []
            for proto in protocols_to_run:
                if self._stop_event.is_set():
                    break
                # Filter by protocol capability
                if proto == "dot":
                    proto_servers = [s for s in servers_snapshot if s.get("dot_host")]
                elif proto == "doh":
                    proto_servers = [s for s in servers_snapshot if s.get("doh_url")]
                else:
                    proto_servers = [s for s in servers_snapshot if s.get("ip") or s.get("ip4") or s.get("ip6")]
                if not proto_servers:
                    continue

                total = len(proto_servers)
                offset = len(all_results)

                def _cb(name: str, done: int, _total: int,
                        _proto=proto, _offset=offset, _total_all=len(servers_snapshot) * len(protocols_to_run)) -> None:
                    if self._stop_event.is_set():
                        return
                    global_done = _offset + done
                    grand_total = sum(
                        len([s for s in servers_snapshot if (
                            s.get("dot_host") if p == "dot" else
                            s.get("doh_url") if p == "doh" else
                            (s.get("ip") or s.get("ip4") or s.get("ip6"))
                        )]) for p in protocols_to_run
                    )
                    pct = global_done / max(grand_total, 1) * 100
                    ip = next((s.get("ip", s.get("ip4", s.get("ip6", ""))) for s in servers_snapshot if s.get("name") == name), "")
                    label = f"[{_proto.upper()}] {name}  {ip}" if ip else f"[{_proto.upper()}] {name}"
                    self._root.after(0, lambda lbl=label, p=pct, gd=global_done, gt=grand_total: (
                        self._lbl_current.config(text=lbl),
                        self._progress_var.set(p),
                        self._lbl_progress_status.config(text=f"{gd}/{gt}"),
                    ))

                results = run_benchmark(
                    proto_servers,
                    n_queries=count,
                    timeout=3.0,
                    protocol=proto,
                    progress_cb=_cb,
                    max_workers=16,
                )
                all_results.extend(results)

            if not self._stop_event.is_set():
                self._root.after(0, lambda r=all_results: self._on_bench_done(r))
            else:
                self._root.after(0, self._on_bench_stopped)

        self._bench_thread = threading.Thread(target=_worker, daemon=True)
        self._bench_thread.start()

    def _on_stop(self) -> None:
        self._stop_event.set()

    def _on_bench_done(self, results: list[ServerStats]) -> None:
        self._results = results
        self._populate_tree(results)
        self._btn_start.state(["!disabled"])
        self._btn_stop.state(["disabled"])
        self._set_status(self._t("status_done"), C["green"])
        msg = self._t("msg_done_n_servers", n=len(results))
        self._lbl_current.config(text=msg)
        self._progress_var.set(100)
        # Save this run as history for next comparison
        self._save_history(results)
        self._prev_scores = {s.name: s.median_ms for s in results if s.median_ms is not None}

    def _on_bench_stopped(self) -> None:
        self._btn_start.state(["!disabled"])
        self._btn_stop.state(["disabled"])
        self._set_status(self._t("status_idle"), C["fg_dim"])
        self._lbl_current.config(text="Stopped.")
        self._progress_var.set(0)

    def _on_clear(self) -> None:
        self._results = []
        self._clear_tree()
        self._progress_var.set(0)
        self._lbl_current.config(text="")
        self._set_status(self._t("status_idle"), C["fg_dim"])

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _clear_tree(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)

    def _populate_tree(self, results: list[ServerStats]) -> None:
        import ipaddress
        self._clear_tree()
        # Alternating row backgrounds
        row_bg = [C["panel"], C["bg"]]
        self._tree.tag_configure("even", background=row_bg[0])
        self._tree.tag_configure("odd",  background=row_bg[1])
        self._tree.tag_configure("ok",   foreground=C["fg"])
        self._tree.tag_configure("warn", foreground=C["yellow"])
        self._tree.tag_configure("bad",  foreground=C["red"])

        for rank, s in enumerate(results, 1):
            rel = f"{s.success_rate * 100:.0f}%"
            try:
                addr = ipaddress.ip_address(s.ip)
                ip_tag = f"IPv6  {s.ip}" if addr.version == 6 else f"IPv4  {s.ip}"
            except (ValueError, TypeError):
                ip_tag = s.ip or ""
            values = (
                rank,
                s.name,
                ip_tag,
                _fmt(s.median_ms),
                _fmt(s.p95_ms),
                _fmt(s.min_ms),
                _fmt(s.max_ms),
                rel,
                f"{s.score:.1f}",
                _bool_sym(s.dnssec_ok),
                _bool_sym(s.malware_blocked),
                _bool_sym(s.ads_blocked),
            )
            stripe = "even" if rank % 2 == 0 else "odd"
            rel_tag = "ok" if s.success_rate >= 0.95 else "warn" if s.success_rate >= 0.7 else "bad"
            # Delta vs. previous run
            prev_ms = self._prev_scores.get(s.name)
            if prev_ms is not None and s.median_ms is not None:
                d = s.median_ms - prev_ms
                arrow = " ↑" if d < -0.5 else (" ↓" if d > 0.5 else "")
            else:
                arrow = ""
            values = values[:-4] + (f"{s.score:.1f}{arrow}",) + values[-3:]
            self._tree.insert("", "end", values=values, tags=(stripe, rel_tag))

    def _sort_tree(self, col: str) -> None:
        """Sort results by a column (alternates asc/desc)."""
        if not self._results:
            return
        key_map = {
            "rank": lambda s: s.score,
            "name": lambda s: s.name.lower(),
            "ip": lambda s: s.ip or "",
            "median": lambda s: s.median_ms or 9999,
            "p95": lambda s: s.p95_ms or 9999,
            "min": lambda s: s.min_ms or 9999,
            "max": lambda s: s.max_ms or 9999,
            "reliability": lambda s: s.success_rate,
            "score": lambda s: s.score,
            "dnssec": lambda s: s.dnssec_ok,
            "malware": lambda s: s.malware_blocked,
            "ads": lambda s: s.ads_blocked,
        }
        key_fn = key_map.get(col, lambda s: s.score)
        # Toggle sort direction
        attr = f"_sort_rev_{col}"
        rev = getattr(self, attr, True)
        setattr(self, attr, not rev)
        self._results.sort(key=key_fn, reverse=rev)
        self._populate_tree(self._results)

    # ------------------------------------------------------------------
    # Tree events
    # ------------------------------------------------------------------

    def _on_tree_double_click(self, event: tk.Event) -> None:
        item = self._tree.focus()
        if not item:
            return
        vals = self._tree.item(item, "values")
        if not vals:
            return
        rank = int(vals[0]) - 1
        if 0 <= rank < len(self._results):
            self._show_detail_popup(self._results[rank])

    def _on_tree_right_click(self, event: tk.Event) -> None:
        iid = self._tree.identify_row(event.y)
        if iid:
            self._tree.selection_set(iid)
            self._tree.focus(iid)
            self._ctx_menu.post(event.x_root, event.y_root)

    def _get_selected_stat(self) -> Optional[ServerStats]:
        item = self._tree.focus()
        if not item:
            return None
        vals = self._tree.item(item, "values")
        if not vals:
            return None
        rank = int(vals[0]) - 1
        if 0 <= rank < len(self._results):
            return self._results[rank]
        return None

    def _ctx_set_dns(self) -> None:
        s = self._get_selected_stat()
        if s and s.ip:
            self._do_set_dns(s.ip)

    def _ctx_copy_ip(self) -> None:
        s = self._get_selected_stat()
        if s and s.ip:
            self._root.clipboard_clear()
            self._root.clipboard_append(s.ip)

    def _ctx_copy_connect(self) -> None:
        s = self._get_selected_stat()
        if not s:
            return
        if s.protocol == "doh":
            url = s.server_info.get("doh_url", s.ip)
        elif s.protocol == "dot":
            host = s.server_info.get("dot_host", s.ip)
            url = f"tls://{host}"
        else:
            url = s.ip
        self._root.clipboard_clear()
        self._root.clipboard_append(url)

    # ------------------------------------------------------------------
    # Detail popup
    # ------------------------------------------------------------------

    def _show_detail_popup(self, s: ServerStats) -> None:
        win = tk.Toplevel(self._root)
        win.title(s.name)
        win.geometry("420x340")
        win.configure(bg=C["bg"])
        win.grab_set()

        tk.Label(win, text=s.name, bg=C["bg"], fg=C["highlight"],
                 font=("Segoe UI", 14, "bold")).pack(pady=(16, 4))
        tk.Label(win, text=f"IP: {s.ip or '—'}  |  Protocol: {s.protocol.upper()}",
                 bg=C["bg"], fg=C["fg_dim"]).pack()

        rows = [
            ("Median latency", _fmt(s.median_ms) + " ms"),
            ("P95 latency", _fmt(s.p95_ms) + " ms"),
            ("Min / Max", f"{_fmt(s.min_ms)} / {_fmt(s.max_ms)} ms"),
            ("Jitter (stdev)", _fmt(s.jitter_ms) + " ms"),
            ("Reliability", f"{s.success_rate * 100:.0f}%"),
            ("Total queries", str(s.total_queries)),
            ("Failed queries", str(s.failed_queries)),
            ("Score", f"{s.score:.1f} — {score_label(s.score, self._lang)}"),
            ("DNSSEC", _bool_sym(s.dnssec_ok)),
            ("Malware block", _bool_sym(s.malware_blocked)),
            ("Ads block", _bool_sym(s.ads_blocked)),
            ("Country", s.server_info.get("country", "?")),
            ("Operator", s.server_info.get("operator", "?")),
        ]
        for lbl, val in rows:
            row_fr = tk.Frame(win, bg=C["bg"])
            row_fr.pack(fill="x", padx=20, pady=1)
            tk.Label(row_fr, text=lbl + ":", width=18, anchor="w",
                     bg=C["bg"], fg=C["fg_dim"], font=("Segoe UI", 9)).pack(side="left")
            tk.Label(row_fr, text=val, anchor="w",
                     bg=C["bg"], fg=C["fg"], font=("Segoe UI", 9, "bold")).pack(side="left")

        ttk.Button(win, text=self._t("btn_close"), command=win.destroy).pack(pady=10)

    # ------------------------------------------------------------------
    # DNS management
    # ------------------------------------------------------------------

    def _update_current_dns_display(self) -> None:
        try:
            cfg = get_current_dns()
            self._saved_dns = cfg
            ips = ", ".join(cfg.servers) if cfg.servers else "(none detected)"
            self._lbl_dns_current.config(text=ips)
            self._lbl_dns_method.config(text=f"via {cfg.method}" + (f" [{cfg.interface}]" if cfg.interface else ""))
        except Exception as exc:
            self._lbl_dns_current.config(text=f"Error: {exc}")

    def _do_set_dns(self, ip: str) -> None:
        if not messagebox.askyesno("NatBench", self._t("msg_set_dns_confirm", ip=ip)):
            return
        if not check_root():
            messagebox.showerror("NatBench", self._t("msg_need_root"))
            return
        iface = self._iface_var.get() or None
        try:
            ok = set_dns([ip], interface=iface)
            if ok:
                self._dns_history.append(ip)
                self._hist_listbox.insert("end", ip)
                self._update_current_dns_display()
                messagebox.showinfo("NatBench", self._t("msg_dns_changed", ip=ip))
            else:
                messagebox.showerror("NatBench", self._t("msg_dns_change_failed"))
        except PermissionError:
            messagebox.showerror("NatBench", self._t("msg_need_root"))
        except Exception as exc:
            messagebox.showerror("NatBench", str(exc))

    def _dns_set_best(self) -> None:
        if not self._results:
            messagebox.showwarning("NatBench", self._t("msg_no_results"))
            return
        best = self._results[0]
        if not best.ip:
            messagebox.showerror("NatBench", "Best server has no plain IP.")
            return
        self._do_set_dns(best.ip)

    def _dns_set_custom(self) -> None:
        ip = tk.simpledialog.askstring("Set DNS", "Enter DNS server IP:", parent=self._root)
        if ip:
            ip = ip.strip()
            self._do_set_dns(ip)

    # ------------------------------------------------------------------
    # Server list helpers
    # ------------------------------------------------------------------

    def _select_all_servers(self) -> None:
        for var in self._server_vars.values():
            var.set(True)

    def _select_no_servers(self) -> None:
        for var in self._server_vars.values():
            var.set(False)

    def _select_best_servers(self) -> None:
        """Select servers tagged 'fast' or with DNSSEC."""
        self._select_no_servers()
        for name, var in self._server_vars.items():
            srv = next((s for s in SERVER_DB if s.get("name") == name), None)
            if srv and ("fast" in srv.get("tags", []) or "dnssec" in srv.get("tags", [])):
                var.set(True)

    def _select_secure_servers(self) -> None:
        """Select only servers with malware+dnssec tags."""
        self._select_no_servers()
        for name, var in self._server_vars.items():
            srv = next((s for s in SERVER_DB if s.get("name") == name), None)
            if srv and "malware" in srv.get("tags", []) and "dnssec" in srv.get("tags", []):
                var.set(True)

    def _select_fast_servers(self) -> None:
        """Select only servers tagged 'fast'."""
        self._select_no_servers()
        for name, var in self._server_vars.items():
            srv = next((s for s in SERVER_DB if s.get("name") == name), None)
            if srv and "fast" in srv.get("tags", []):
                var.set(True)

    def _select_region_servers(self) -> None:
        """Select servers from the user's locale country + system DNS."""
        import locale
        loc = locale.getdefaultlocale()[0] or ""
        country = loc.split("_")[-1].upper() if "_" in loc else ""
        self._select_no_servers()
        # Always include system DNS
        for key, var in self._server_vars.items():
            if key.startswith("__system_"):
                var.set(True)
        matched = 0
        if country:
            for name, var in self._server_vars.items():
                srv = next((s for s in SERVER_DB if s.get("name") == name), None)
                if srv and srv.get("country", "").upper() == country:
                    var.set(True)
                    matched += 1
        # Fallback: select Recommended if no country match
        if matched == 0:
            for name, var in self._server_vars.items():
                srv = next((s for s in SERVER_DB if s.get("name") == name), None)
                if srv and ("fast" in srv.get("tags", []) or "anycast" in srv.get("tags", [])):
                    var.set(True)

    def _add_custom_server(self) -> None:
        raw = self._custom_entry.get().strip()
        if not raw:
            return
        parts = raw.split(":", 1)
        ip = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 53
        srv = {
            "name": f"Custom ({ip})",
            "ip4": ip,
            "ip6": None,
            "doh_url": None,
            "dot_host": None,
            "dot_port": 853,
            "port": port,
            "country": "??",
            "operator": "Custom",
            "tags": ["custom"],
            "description_en": "User-added custom server.",
        }
        self._custom_servers.append(srv)
        self._custom_entry.delete(0, "end")
        messagebox.showinfo("NatBench", f"Added {ip}:{port} to custom servers.")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _on_export_fmt_change(self, *args) -> None:
        ext_map = {"json": ".json", "csv": ".csv", "markdown": ".md", "html": ".html"}
        new_ext = ext_map.get(self._export_fmt.get(), ".txt")
        cur = self._export_path.get()
        if cur:
            import os
            base = os.path.splitext(cur)[0]
            self._export_path.set(base + new_ext)

    def _browse_export_path(self) -> None:
        fmt = self._export_fmt.get()
        ext_map = {"json": ".json", "csv": ".csv", "markdown": ".md", "html": ".html"}
        type_map = {
            "json": [("JSON files", "*.json"), ("All files", "*.*")],
            "csv":  [("CSV files", "*.csv"), ("All files", "*.*")],
            "markdown": [("Markdown files", "*.md"), ("All files", "*.*")],
            "html": [("HTML files", "*.html"), ("All files", "*.*")],
        }
        ext = ext_map.get(fmt, ".txt")
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=type_map.get(fmt, [("All files", "*.*")]),
            initialfile=f"natbench_results{ext}",
        )
        if path:
            self._export_path.set(path)

    def _do_export(self) -> None:
        if not self._results:
            messagebox.showwarning("NatBench", self._t("msg_no_results"))
            return
        fmt = self._export_fmt.get()
        path = self._export_path.get().strip()
        if not path:
            messagebox.showwarning("NatBench", "Please enter a file path.")
            return

        content = self._render_export(fmt)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            messagebox.showinfo("NatBench", self._t("msg_export_done", path=path))
        except OSError as exc:
            messagebox.showerror("NatBench", str(exc))

    def _render_export(self, fmt: str) -> str:
        if fmt == "json":
            import json
            rows = []
            for s in self._results:
                rows.append({
                    "name": s.name, "ip": s.ip, "protocol": s.protocol,
                    "median_ms": s.median_ms, "p95_ms": s.p95_ms,
                    "score": s.score, "success_rate": s.success_rate,
                    "dnssec": s.dnssec_ok, "malware": s.malware_blocked, "ads": s.ads_blocked,
                })
            return json.dumps(rows, indent=2, ensure_ascii=False)
        elif fmt == "csv":
            import io, csv
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["rank", "name", "ip", "median_ms", "p95_ms", "score",
                        "reliability_pct", "dnssec", "malware", "ads"])
            for rank, s in enumerate(self._results, 1):
                w.writerow([rank, s.name, s.ip, _fmt(s.median_ms), _fmt(s.p95_ms),
                             f"{s.score:.1f}", f"{s.success_rate * 100:.0f}",
                             s.dnssec_ok, s.malware_blocked, s.ads_blocked])
            return buf.getvalue()
        elif fmt == "markdown":
            lines = [
                "| # | Name | Median | P95 | Reliability | Score | DNSSEC | Malware | Ads |",
                "|---|------|--------|-----|-------------|-------|--------|---------|-----|",
            ]
            for rank, s in enumerate(self._results, 1):
                lines.append(
                    f"| {rank} | {s.name} | {_fmt(s.median_ms)} ms | {_fmt(s.p95_ms)} ms"
                    f" | {s.success_rate * 100:.0f}% | {s.score:.1f}"
                    f" | {_bool_sym(s.dnssec_ok)} | {_bool_sym(s.malware_blocked)}"
                    f" | {_bool_sym(s.ads_blocked)} |"
                )
            return "\n".join(lines)
        elif fmt == "html":
            rows_html = ""
            for rank, s in enumerate(self._results, 1):
                rows_html += (
                    f"<tr><td>{rank}</td><td>{s.name}</td>"
                    f"<td>{_fmt(s.median_ms)}</td><td>{_fmt(s.p95_ms)}</td>"
                    f"<td>{s.success_rate * 100:.0f}%</td><td>{s.score:.1f}</td>"
                    f"<td>{_bool_sym(s.dnssec_ok)}</td>"
                    f"<td>{_bool_sym(s.malware_blocked)}</td>"
                    f"<td>{_bool_sym(s.ads_blocked)}</td></tr>\n"
                )
            return (
                "<!DOCTYPE html><html><head><title>NatBench Results</title>"
                "<style>body{font-family:sans-serif;background:#1a1a2e;color:#e0e0e0}"
                "table{border-collapse:collapse;width:100%}"
                "th{background:#0f3460;padding:8px}td{padding:6px;border-bottom:1px solid #333}"
                "tr:nth-child(even){background:#16213e}</style></head><body>"
                "<h1>NatBench Results</h1>"
                "<table><thead><tr>"
                "<th>#</th><th>Name</th><th>Median</th><th>P95</th>"
                "<th>Reliability</th><th>Score</th><th>DNSSEC</th><th>Malware</th><th>Ads</th>"
                "</tr></thead><tbody>"
                + rows_html
                + "</tbody></table></body></html>"
            )
        return ""

    def _refresh_preview(self) -> None:
        if not self._results:
            content = self._t("msg_no_results")
        else:
            fmt = self._export_fmt.get()
            content = self._render_export(fmt)[:4000] + ("\n[…truncated]" if len(self._render_export(fmt)) > 4000 else "")
        self._preview_text.config(state="normal")
        self._preview_text.delete("1.0", "end")
        self._preview_text.insert("1.0", content)
        self._preview_text.config(state="disabled")

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    def _set_status(self, text: str, color: str = C["fg_dim"]) -> None:
        self._lbl_status.config(text=text, fg=color)

    def _on_export(self) -> None:
        self._notebook.select(3)
        self._refresh_preview()

    def _show_about(self) -> None:
        self._notebook.select(4)

    def _open_url(self, url: str) -> None:
        import sys, subprocess
        try:
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", url], stderr=subprocess.DEVNULL)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", url])
            else:
                import webbrowser
                webbrowser.open(url)
        except Exception:
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception:
                pass

    def _check_for_updates_gui(self) -> None:
        """Check GitHub for a newer release and show a messagebox."""
        self._set_status("Checking for updates…", C["gold"])

        def _worker() -> None:
            info = check_for_updates()
            self._root.after(0, lambda: _show_result(info))

        def _show_result(info: dict) -> None:
            self._set_status(self._t("status_idle"), C["fg_dim"])
            if info["error"]:
                messagebox.showwarning("NatBench", f"Update check failed:\n{info['error']}")
            elif info["newer"]:
                if messagebox.askyesno(
                    "NatBench",
                    f"New version available: {info['latest']}\n"
                    f"Current version: {info['current']}\n\n"
                    f"Open release page?",
                ):
                    self._open_url(info["url"])
            else:
                messagebox.showinfo(
                    "NatBench",
                    f"NatBench {info['current']} is up-to-date.",
                )

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # Traceroute helpers
    # ------------------------------------------------------------------

    def _trace_use_selected(self) -> None:
        """Copy the IP of the currently selected result row into the traceroute host field."""
        stat = self._get_selected_stat()
        if stat:
            self._trace_host_var.set(stat.ip or stat.name)
            self._notebook.select(5)

    def _stop_traceroute(self) -> None:
        self._trace_running = False
        if self._trace_proc:
            try:
                self._trace_proc.kill()
            except Exception:
                pass
        self._trace_btn.config(state="normal")
        self._trace_stop_btn.config(state="disabled")

    def _run_traceroute(self) -> None:
        import sys, shutil, subprocess, threading as _th

        host = self._trace_host_var.get().strip()
        if not host:
            messagebox.showwarning("NatBench", "Enter a host or IP address.")
            return

        self._trace_text.config(state="normal")
        self._trace_text.delete("1.0", "end")
        self._trace_text.config(state="disabled")

        self._trace_btn.config(state="disabled")
        self._trace_stop_btn.config(state="normal")
        self._trace_running = True

        # --- choose backend ---
        af = self._trace_af_var.get() if hasattr(self, "_trace_af_var") else "auto"
        if sys.platform.startswith("linux") or sys.platform == "darwin":
            af_flag = ["-4"] if af == "ipv4" else (["-6"] if af == "ipv6" else [])
        else:
            af_flag = []

        if sys.platform.startswith("win"):
            cmd = ["tracert", "-d", host]
            use_subprocess = True
        elif shutil.which("traceroute"):
            cmd = ["traceroute"] + af_flag + ["-m", "30", host]
            use_subprocess = True
        elif shutil.which("tracepath"):
            cmd = ["tracepath"] + af_flag + [host]
            use_subprocess = True
        elif shutil.which("mtr"):
            cmd = ["mtr"] + af_flag + ["--report", "--report-cycles", "3", host]
            use_subprocess = True
        else:
            cmd = None
            use_subprocess = False  # fall back to Python raw-socket impl

        header = f"Traceroute → {host}\n{'─' * 62}\n"
        self._trace_append(header, "header")

        def _subprocess_worker():
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1,
                )
                self._trace_proc = proc
                for line in proc.stdout:
                    if not self._trace_running:
                        proc.kill()
                        break
                    line = line.rstrip()
                    tag = "timeout" if ("* * *" in line or line.strip() == "*") else "hop"
                    self._root.after(0, lambda l=line, t=tag: self._trace_append(l + "\n", t))
                proc.wait()
                if self._trace_running:
                    self._root.after(0, lambda: self._trace_append("\n─── Done ───\n", "done"))
            except Exception as exc:
                self._root.after(0, lambda: self._trace_append(f"Error: {exc}\n", "error"))
            finally:
                self._trace_running = False
                self._root.after(0, lambda: (
                    self._trace_btn.config(state="normal"),
                    self._trace_stop_btn.config(state="disabled"),
                ))

        def _python_worker():
            import socket, time
            try:
                # Determine socket address family from AF preference
                if af == "ipv6":
                    sock_af = socket.AF_INET6
                    icmp_proto_name = "ipv6-icmp"
                else:
                    sock_af = socket.AF_INET
                    icmp_proto_name = "icmp"

                try:
                    if sock_af == socket.AF_INET6:
                        infos = socket.getaddrinfo(host, None, socket.AF_INET6)
                        dest_ip = infos[0][4][0] if infos else None
                        if not dest_ip:
                            raise socket.gaierror("No IPv6 address found")
                    else:
                        dest_ip = socket.gethostbyname(host)
                except socket.gaierror as e:
                    self._root.after(0, lambda: self._trace_append(
                        f"Cannot resolve '{host}': {e}\n", "error"))
                    return

                self._root.after(0, lambda: self._trace_append(
                    f"Target: {dest_ip}  (Python raw-socket mode)\n\n", "header"))

                try:
                    icmp_proto = socket.getprotobyname(icmp_proto_name)
                except OSError:
                    icmp_proto = socket.getprotobyname("icmp")
                try:
                    recv_sock = socket.socket(
                        sock_af, socket.SOCK_RAW, icmp_proto)
                    recv_sock.settimeout(3.0)
                except PermissionError:
                    self._root.after(0, lambda: self._trace_append(
                        "No raw-socket permission. Options:\n"
                        "  • Run NatBench with sudo\n"
                        "  • Install traceroute:  sudo pacman -S traceroute\n"
                        "  •                      sudo apt install traceroute\n"
                        "  •                      sudo dnf install traceroute\n",
                        "error"))
                    return

                for ttl in range(1, 31):
                    if not self._trace_running:
                        break
                    send_sock = socket.socket(
                        socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                    send_sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
                    t0 = time.perf_counter()
                    hop_ip = None
                    rtt_ms = None
                    try:
                        send_sock.sendto(b"\x00" * 40, (dest_ip, 33434 + ttl))
                        data, addr = recv_sock.recvfrom(512)
                        hop_ip = addr[0]
                        rtt_ms = (time.perf_counter() - t0) * 1000
                    except socket.timeout:
                        pass
                    except Exception:
                        pass
                    finally:
                        send_sock.close()

                    if hop_ip:
                        try:
                            name = socket.gethostbyaddr(hop_ip)[0]
                            hop_str = f"{ttl:3d}  {name} ({hop_ip})"
                        except Exception:
                            hop_str = f"{ttl:3d}  {hop_ip}"
                        line = f"{hop_str}   {rtt_ms:.1f} ms"
                        reached = (hop_ip == dest_ip)
                        tag = "done" if reached else "hop"
                        self._root.after(0, lambda l=line, t=tag: self._trace_append(l + "\n", t))
                        if reached:
                            self._root.after(0, lambda: self._trace_append(
                                "\n─── Destination reached ───\n", "done"))
                            break
                    else:
                        line = f"{ttl:3d}  * * *  (timeout)"
                        self._root.after(0, lambda l=line: self._trace_append(l + "\n", "timeout"))

                recv_sock.close()
                if self._trace_running:
                    self._root.after(0, lambda: self._trace_append("\n─── Done ───\n", "done"))

            except Exception as exc:
                self._root.after(0, lambda: self._trace_append(f"Error: {exc}\n", "error"))
            finally:
                self._trace_running = False
                self._root.after(0, lambda: (
                    self._trace_btn.config(state="normal"),
                    self._trace_stop_btn.config(state="disabled"),
                ))

        worker = _subprocess_worker if use_subprocess else _python_worker
        _th.Thread(target=worker, daemon=True).start()

    def _trace_append(self, text: str, tag: str = "hop") -> None:
        self._trace_text.config(state="normal")
        self._trace_text.insert("end", text, tag)
        self._trace_text.see("end")
        self._trace_text.config(state="disabled")

    def _ctx_traceroute(self) -> None:
        stat = self._get_selected_stat()
        if stat:
            self._trace_host_var.set(stat.ip or stat.name)
            self._notebook.select(5)
            self._run_traceroute()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the Tkinter main loop."""
        self._root.mainloop()


# ---------------------------------------------------------------------------
# Module entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Launch the NatBench GUI."""
    # Need simpledialog for _dns_set_custom
    from tkinter import simpledialog  # noqa: F401 — imported to ensure availability
    tk.simpledialog = simpledialog  # attach to module for use in _dns_set_custom

    app = NatBenchApp()
    app.run()


if __name__ == "__main__":
    main()
