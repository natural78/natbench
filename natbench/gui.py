"""
NatBench gui.py — Tkinter GUI (900x650).

Uses customtkinter when available, falls back to standard ttk with a dark theme.
All text is routed through i18n.t() and switches language dynamically.
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
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

# ---------------------------------------------------------------------------
# Colour palette (dark theme)
# ---------------------------------------------------------------------------

C = {
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
}

_PROTOCOLS = ["udp", "tcp", "dot", "doh"]

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

        self._build_menu()
        self._build_top_bar()
        self._build_main_area()
        self._build_status_bar()

        self._refresh_all_labels()
        self._update_current_dns_display()

    # ------------------------------------------------------------------
    # i18n shortcut
    # ------------------------------------------------------------------

    def _t(self, key: str, **kwargs: object) -> str:
        return t(key, self._lang, **kwargs)

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
                                     command=self._on_export)
        self._menu_file.add_separator()
        self._menu_file.add_command(label="Exit", command=self._root.destroy)

        # Run
        self._menu_run = tk.Menu(self._menubar, tearoff=False,
                                  bg=C["panel"], fg=C["fg"],
                                  activebackground=C["accent"])
        self._menubar.add_cascade(label=self._t("menu_run"), menu=self._menu_run)
        self._menu_run.add_command(label=self._t("btn_start"),
                                    command=self._on_start)
        self._menu_run.add_command(label=self._t("btn_stop"),
                                    command=self._on_stop)
        self._menu_run.add_separator()
        self._menu_run.add_command(label=self._t("btn_reset"),
                                    command=self._on_clear)

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

        # Help
        self._menu_help = tk.Menu(self._menubar, tearoff=False,
                                   bg=C["panel"], fg=C["fg"],
                                   activebackground=C["accent"])
        self._menubar.add_cascade(label=self._t("menu_help"), menu=self._menu_help)
        self._menu_help.add_command(label=self._t("menu_about"),
                                     command=self._show_about)
        self._menu_help.add_command(
            label="Check for Updates",
            command=self._check_for_updates_gui,
        )

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

        # Language selector
        tk.Label(bar, text="Lang:", bg=C["panel"], fg=C["fg_dim"]).pack(side="right", padx=(0, 4))
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

        # Protocol selector
        tk.Label(bar, text="Protocol:", bg=C["panel"], fg=C["fg_dim"]).pack(side="right", padx=(0, 4))
        self._protocol_var = tk.StringVar(value="udp")
        proto_cb = ttk.Combobox(
            bar, textvariable=self._protocol_var,
            values=_PROTOCOLS, state="readonly", width=6,
        )
        proto_cb.pack(side="right", padx=(0, 12), pady=10)

        # Query count
        tk.Label(bar, text="Queries:", bg=C["panel"], fg=C["fg_dim"]).pack(side="right", padx=(0, 4))
        self._count_var = tk.IntVar(value=10)
        count_spin = ttk.Spinbox(
            bar, textvariable=self._count_var,
            from_=1, to=100, width=5,
        )
        count_spin.pack(side="right", padx=(0, 12), pady=10)

    # ------------------------------------------------------------------
    # Build: main area (left panel + notebook)
    # ------------------------------------------------------------------

    def _build_main_area(self) -> None:
        pane = tk.PanedWindow(
            self._root, orient="horizontal",
            bg=C["bg"], sashwidth=5, sashrelief="flat",
        )
        pane.pack(fill="both", expand=True, padx=6, pady=(4, 2))

        # --- Left panel ---
        left = tk.Frame(pane, bg=C["panel"], width=240)
        left.pack_propagate(False)
        pane.add(left, minsize=180)
        self._build_left_panel(left)

        # --- Right: Notebook ---
        right = tk.Frame(pane, bg=C["bg"])
        pane.add(right, minsize=500)
        self._build_notebook(right)

    def _build_left_panel(self, parent: tk.Frame) -> None:
        tk.Label(
            parent, text=self._t("label_all_servers"),
            bg=C["panel"], fg=C["gold"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 4))

        # Select all / none
        btn_row = tk.Frame(parent, bg=C["panel"])
        btn_row.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(btn_row, text="All", command=self._select_all_servers, width=6).pack(side="left")
        ttk.Button(btn_row, text="None", command=self._select_no_servers, width=6).pack(side="left", padx=(4, 0))

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

        # --- System/ISP DNS group at the top ---
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
            grp_lbl = tk.Label(
                inner, text=f" {group_name}",
                bg=C["accent"], fg=C["gold"],
                font=("Segoe UI", 8, "bold"),
                anchor="w",
            )
            grp_lbl.pack(fill="x", pady=(6, 1))

            for srv in servers:
                name = srv.get("name", "?")
                var = tk.BooleanVar(value=True)
                self._server_vars[name] = var
                cb = tk.Checkbutton(
                    inner, text=name[:30], variable=var,
                    bg=C["panel"], fg=C["fg"],
                    selectcolor=C["accent"], activebackground=C["panel"],
                    font=("Segoe UI", 8), anchor="w",
                )
                cb.pack(fill="x", padx=4)

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
        ttk.Button(custom_row, text="Add", command=self._add_custom_server, width=5).pack(side="left", padx=(4, 0))

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

    # ------------------------------------------------------------------
    # Tab: Benchmark
    # ------------------------------------------------------------------

    def _build_benchmark_tab(self, parent: tk.Frame) -> None:
        # Progress area
        prog_frame = tk.Frame(parent, bg=C["bg"])
        prog_frame.pack(fill="x", padx=10, pady=(8, 4))

        self._progress_var = tk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Progressbar(
            prog_frame, variable=self._progress_var,
            maximum=100, length=400, mode="determinate",
        )
        self._progress_bar.pack(side="left", fill="x", expand=True)

        self._lbl_current = tk.Label(
            prog_frame, text="", bg=C["bg"], fg=C["fg_dim"],
            font=("Segoe UI", 8), width=28, anchor="w",
        )
        self._lbl_current.pack(side="left", padx=(8, 0))

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
            "rank", "name", "median", "p95", "min", "max",
            "reliability", "score", "dnssec", "malware", "ads",
        )
        tree_frame = tk.Frame(parent, bg=C["bg"])
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        self._tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings",
            selectmode="browse",
        )
        col_widths = {
            "rank": 42, "name": 180, "median": 80, "p95": 72,
            "min": 64, "max": 64, "reliability": 90, "score": 60,
            "dnssec": 64, "malware": 68, "ads": 48,
        }
        for col in cols:
            self._tree.heading(col, text=self._t(f"col_{col}"),
                               command=lambda c=col: self._sort_tree(c))
            self._tree.column(col, width=col_widths.get(col, 80),
                              anchor="center" if col in ("rank", "dnssec", "malware", "ads") else "w",
                              stretch=(col == "name"))

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
            parent, text="Version 1.0.0",
            bg=C["bg"], fg=C["fg"],
            font=("Segoe UI", 10),
        ).pack(pady=(12, 2))

        tk.Label(
            parent, text="License: MIT",
            bg=C["bg"], fg=C["fg_dim"],
        ).pack()

        tk.Label(
            parent, text="https://github.com/natbench/natbench",
            bg=C["bg"], fg=C["accent"],
            cursor="hand2",
        ).pack(pady=4)

        tk.Label(
            parent,
            text=(
                f"{len(SERVER_DB)} DNS servers in database\n"
                "Protocols: UDP · TCP · DoT · DoH\n"
                "21 languages supported"
            ),
            bg=C["bg"], fg=C["fg_dim"],
            justify="center",
        ).pack(pady=16)

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
            self._notebook.tab(2, text="Profiles")
            self._notebook.tab(3, text=self._t("btn_export"))
            self._notebook.tab(4, text=self._t("menu_about"))
        # Treeview headings
        if hasattr(self, "_tree"):
            for col in ("rank", "name", "median", "p95", "min", "max",
                        "reliability", "score", "dnssec", "malware", "ads"):
                self._tree.heading(col, text=self._t(f"col_{col}"))
        # Buttons
        if hasattr(self, "_btn_start"):
            self._btn_start.config(text=self._t("btn_start"))
        if hasattr(self, "_btn_stop"):
            self._btn_stop.config(text=self._t("btn_stop"))
        # Custom server label
        if hasattr(self, "_lbl_custom"):
            self._lbl_custom.config(text=self._t("label_custom_server"))
        # Menu
        self._rebuild_menu_labels()

    def _rebuild_menu_labels(self) -> None:
        try:
            self._menubar.entryconfig(0, label=self._t("menu_file"))
            self._menubar.entryconfig(1, label=self._t("menu_run"))
            self._menubar.entryconfig(2, label=self._t("menu_settings"))
            self._menubar.entryconfig(3, label=self._t("menu_help"))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Benchmark lifecycle
    # ------------------------------------------------------------------

    def _on_start(self) -> None:
        if self._bench_thread and self._bench_thread.is_alive():
            return

        # Build selected server pool — system DNS first
        selected: list[dict] = []
        for srv in self._system_dns_servers:
            key = srv.get("_gui_key", "")
            var = self._server_vars.get(key)
            if var and var.get():
                selected.append(srv)

        # Regular servers from SERVER_DB
        selected += [
            srv for name, var in self._server_vars.items()
            if var.get() and not name.startswith("__system_")
            for srv in SERVER_DB
            if srv.get("name") == name
        ]
        # Add custom servers
        selected += self._custom_servers

        if not selected:
            messagebox.showwarning("NatBench", "No servers selected.")
            return

        protocol = self._protocol_var.get()
        # Filter by protocol capability
        if protocol == "dot":
            selected = [s for s in selected if s.get("dot_host")]
        elif protocol == "doh":
            selected = [s for s in selected if s.get("doh_url")]
        else:
            selected = [s for s in selected if s.get("ip4") or s.get("ip6")]

        if not selected:
            messagebox.showwarning("NatBench",
                                   f"No servers support the {protocol.upper()} protocol.")
            return

        self._stop_event.clear()
        self._results = []
        self._clear_tree()
        self._btn_start.state(["disabled"])
        self._btn_stop.state(["!disabled"])
        self._set_status(self._t("status_running"), C["gold"])
        self._progress_var.set(0)

        count = self._count_var.get()

        def _worker() -> None:
            done_ref = [0]
            total = len(selected)

            def _cb(name: str, done: int, _total: int) -> None:
                if self._stop_event.is_set():
                    return
                done_ref[0] = done
                pct = done / total * 100
                self._root.after(0, lambda n=name, p=pct, d=done, tot=total: (
                    self._lbl_current.config(text=self._t("msg_testing_server", name=n)),
                    self._progress_var.set(p),
                    self._lbl_progress_status.config(text=f"{d}/{tot}"),
                ))

            results = run_benchmark(
                selected,
                n_queries=count,
                timeout=3.0,
                protocol=protocol,
                progress_cb=_cb,
                max_workers=16,
            )
            if not self._stop_event.is_set():
                self._root.after(0, lambda r=results: self._on_bench_done(r))
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
        self._clear_tree()
        for rank, s in enumerate(results, 1):
            rel = f"{s.success_rate * 100:.0f}%"
            values = (
                rank,
                s.name,
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
            iid = self._tree.insert("", "end", values=values, tags=(str(rank),))
            # Tag-based row colouring
            tag = "ok" if s.success_rate >= 0.95 else "warn" if s.success_rate >= 0.7 else "bad"
            self._tree.item(iid, tags=(tag,))

        self._tree.tag_configure("ok", foreground=C["fg"])
        self._tree.tag_configure("warn", foreground=C["yellow"])
        self._tree.tag_configure("bad", foreground=C["red"])

    def _sort_tree(self, col: str) -> None:
        """Sort results by a column (alternates asc/desc)."""
        if not self._results:
            return
        key_map = {
            "rank": lambda s: s.score,
            "name": lambda s: s.name.lower(),
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

    def _browse_export_path(self) -> None:
        fmt = self._export_fmt.get()
        ext_map = {"json": ".json", "csv": ".csv", "markdown": ".md", "html": ".html"}
        ext = ext_map.get(fmt, ".txt")
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[("All files", "*.*")],
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
        self._notebook.select(2)
        self._refresh_preview()

    def _show_about(self) -> None:
        self._notebook.select(3)

    def _open_url(self, url: str) -> None:
        import webbrowser
        webbrowser.open(url)

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
