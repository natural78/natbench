"""
NatBench cli.py — Rich command-line interface.

Usage:
    python -m natbench [options]
    natbench [options]

Requires: rich (optional but recommended), requests (optional, for DoH).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from typing import Optional

# ---------------------------------------------------------------------------
# Optional rich import
# ---------------------------------------------------------------------------

try:
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box as rich_box
    _HAS_RICH = True
except ImportError:
    _HAS_RICH = False

# ---------------------------------------------------------------------------
# Internal imports (graceful on partial package installs)
# ---------------------------------------------------------------------------

try:
    from .core import ServerStats, run_benchmark
    from .servers import (
        SERVER_DB,
        get_servers_by_tag,
        get_servers_with_doh,
        get_servers_with_dot,
        get_servers_with_ip,
    )
    from .i18n import t, detect_lang, score_label, LANG_NAMES, SUPPORTED_LANGS
    from .system import (
        DnsConfig,
        check_root,
        get_current_dns,
        get_system_dns_servers,
        set_dns,
    )
    from .updater import check_for_updates, self_update
    from .profiles import list_profiles, load_profile, save_profile, validate_profile
except ImportError:
    # Allow running as a standalone script for quick testing
    import importlib, pathlib
    _pkg = pathlib.Path(__file__).parent
    sys.path.insert(0, str(_pkg.parent))
    from natbench.core import ServerStats, run_benchmark
    from natbench.servers import (
        SERVER_DB,
        get_servers_by_tag,
        get_servers_with_doh,
        get_servers_with_dot,
        get_servers_with_ip,
    )
    from natbench.i18n import t, detect_lang, score_label, LANG_NAMES, SUPPORTED_LANGS
    from natbench.system import (
        DnsConfig,
        check_root,
        get_current_dns,
        get_system_dns_servers,
        set_dns,
    )
    from natbench.updater import check_for_updates, self_update
    from natbench.profiles import list_profiles, load_profile, save_profile, validate_profile

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

try:
    from .__version__ import __version__
except Exception:
    try:
        from natbench.__version__ import __version__
    except Exception:
        __version__ = "1.1.0"

# ---------------------------------------------------------------------------
# ASCII logo
# ---------------------------------------------------------------------------

_LOGO = """
╔══════════════════════════════════════════╗
║  ███╗   ██╗ █████╗ ████████╗            ║
║  ████╗  ██║██╔══██╗╚══██╔══╝            ║
║  ██╔██╗ ██║███████║   ██║               ║
║  ██║╚██╗██║██╔══██║   ██║               ║
║  ██║ ╚████║██║  ██║   ██║               ║
║  ╚═╝  ╚═══╝╚═╝  ╚═╝   ╚═╝  BENCH      ║
║  DNS Benchmark & Optimizer  v{ver:<9}  ║
╚══════════════════════════════════════════╝
""".format(ver=__version__)

# ---------------------------------------------------------------------------
# Plain-text fallbacks (when rich is not installed)
# ---------------------------------------------------------------------------


class _PlainConsole:
    """Minimal Console replacement that prints plain text."""

    def print(self, *args, **kwargs) -> None:  # noqa: A003
        # Strip rich markup tags for plain output
        import re
        text = " ".join(str(a) for a in args)
        text = re.sub(r"\[/?[^\]]*\]", "", text)
        print(text)

    def input(self, prompt: str = "") -> str:
        return input(prompt)


# ---------------------------------------------------------------------------
# Latency colour helpers
# ---------------------------------------------------------------------------


def _latency_color(ms: Optional[float]) -> str:
    """Return a rich colour name for a latency value."""
    if ms is None:
        return "red"
    if ms < 50:
        return "bright_green"
    if ms < 150:
        return "green"
    if ms < 300:
        return "yellow"
    return "red"


def _score_color(score: float) -> str:
    if score >= 85:
        return "bright_green"
    if score >= 70:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"


def _bool_symbol(val: bool, color: bool = True) -> str:
    if _HAS_RICH and color:
        return "[green]✓[/green]" if val else "[red]✗[/red]"
    return "✓" if val else "✗"


# ---------------------------------------------------------------------------
# Server selection helpers
# ---------------------------------------------------------------------------


def _select_servers(
    servers_arg: str,
    protocol: str,
    custom_ips: Optional[list[str]] = None,
) -> list[dict]:
    """
    Return a list of server dicts based on the --servers argument.

    Args:
        servers_arg: "all", "fast", "secure", "custom", or comma-separated IPs.
        protocol:    "udp", "tcp", "dot", "doh", or "all".
        custom_ips:  Pre-parsed custom IP list (from --add-server flags).
    """
    extra: list[dict] = []
    if custom_ips:
        for entry in custom_ips:
            parts = entry.split(":", 1)
            ip = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 53
            extra.append({
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
                "description_en": "User-defined custom server.",
            })

    arg = servers_arg.lower().strip()

    if arg == "all":
        pool = list(SERVER_DB)
    elif arg == "fast":
        pool = get_servers_by_tag("fast")
        if not pool:
            pool = list(SERVER_DB)
    elif arg == "secure":
        pool = get_servers_by_tag("malware", "dnssec")
        if not pool:
            pool = list(SERVER_DB)
    elif arg == "custom":
        pool = extra
        extra = []
    else:
        # Treat as comma/space-separated server names or IPs
        pool = []
        seen_names: set[str] = set()
        for entry in arg.replace(" ", ",").split(","):
            entry = entry.strip()
            if not entry:
                continue
            entry_lower = entry.lower()
            # Try name/operator substring match against SERVER_DB first
            matched = [
                s for s in SERVER_DB
                if entry_lower in s.get("name", "").lower()
                or entry_lower in s.get("operator", "").lower()
                or entry == s.get("ip4", "")
                or entry == s.get("dot_host", "")
            ]
            if matched:
                for s in matched:
                    if s["name"] not in seen_names:
                        pool.append(s)
                        seen_names.add(s["name"])
            else:
                # Fall back to raw IP[:port]
                parts = entry.split(":", 1)
                ip = parts[0]
                port = int(parts[1]) if len(parts) > 1 else 53
                name = ip
                if name not in seen_names:
                    pool.append({
                        "name": name,
                        "ip4": ip,
                        "ip6": None,
                        "doh_url": None,
                        "dot_host": None,
                        "dot_port": 853,
                        "port": port,
                        "country": "??",
                        "operator": "Custom",
                        "tags": ["custom"],
                        "description_en": "User-specified server.",
                    })
                    seen_names.add(name)

    # Filter by protocol capability
    if protocol == "dot":
        pool = [s for s in pool if s.get("dot_host")]
    elif protocol == "doh":
        pool = [s for s in pool if s.get("doh_url")]
    elif protocol in ("udp", "tcp"):
        pool = [s for s in pool if s.get("ip4") or s.get("ip6")]
    # "all" protocol: keep everything

    return pool + extra


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _fmt_ms(ms: Optional[float]) -> str:
    if ms is None:
        return "—"
    return f"{ms:.1f}"


def _results_as_json(results: list[ServerStats]) -> str:
    rows = []
    for s in results:
        rows.append({
            "name": s.name,
            "ip": s.ip,
            "protocol": s.protocol,
            "median_ms": s.median_ms,
            "p95_ms": s.p95_ms,
            "min_ms": s.min_ms,
            "max_ms": s.max_ms,
            "avg_ms": s.avg_ms,
            "jitter_ms": s.jitter_ms,
            "success_rate": round(s.success_rate * 100, 1),
            "total_queries": s.total_queries,
            "failed_queries": s.failed_queries,
            "dnssec": s.dnssec_ok,
            "malware_blocked": s.malware_blocked,
            "ads_blocked": s.ads_blocked,
            "score": s.score,
            "country": s.server_info.get("country", ""),
            "operator": s.server_info.get("operator", ""),
            "tags": s.server_info.get("tags", []),
        })
    return json.dumps(rows, indent=2, ensure_ascii=False)


def _results_as_csv(results: list[ServerStats]) -> str:
    import io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "rank", "name", "ip", "protocol", "median_ms", "p95_ms",
        "min_ms", "max_ms", "avg_ms", "jitter_ms",
        "success_rate_pct", "total_queries", "failed_queries",
        "dnssec", "malware_blocked", "ads_blocked", "score",
        "country", "operator",
    ])
    for rank, s in enumerate(results, 1):
        writer.writerow([
            rank, s.name, s.ip, s.protocol,
            _fmt_ms(s.median_ms), _fmt_ms(s.p95_ms),
            _fmt_ms(s.min_ms), _fmt_ms(s.max_ms),
            _fmt_ms(s.avg_ms), _fmt_ms(s.jitter_ms),
            round(s.success_rate * 100, 1),
            s.total_queries, s.failed_queries,
            s.dnssec_ok, s.malware_blocked, s.ads_blocked,
            s.score,
            s.server_info.get("country", ""),
            s.server_info.get("operator", ""),
        ])
    return buf.getvalue()


def _results_as_markdown(results: list[ServerStats]) -> str:
    lines = [
        "| # | Name | Median | P95 | Reliability | Score | DNSSEC | Malware | Ads |",
        "|---|------|--------|-----|-------------|-------|--------|---------|-----|",
    ]
    for rank, s in enumerate(results, 1):
        rel = f"{s.success_rate * 100:.0f}%"
        lines.append(
            f"| {rank} | {s.name} | {_fmt_ms(s.median_ms)} ms | {_fmt_ms(s.p95_ms)} ms"
            f" | {rel} | {s.score:.1f} | {'✓' if s.dnssec_ok else '✗'}"
            f" | {'✓' if s.malware_blocked else '✗'} | {'✓' if s.ads_blocked else '✗'} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rich results table
# ---------------------------------------------------------------------------


def _print_rich_table(
    results: list[ServerStats],
    lang: str,
    top: Optional[int] = None,
) -> None:
    console = Console()
    display = results[:top] if top else results

    table = Table(
        title=t("results_title", lang),
        box=rich_box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        highlight=True,
    )
    table.add_column(t("col_rank", lang), style="bold", justify="right", width=5)
    table.add_column(t("col_server", lang), min_width=22)
    table.add_column(t("col_median", lang) + " (ms)", justify="right", width=12)
    table.add_column(t("col_p95", lang) + " (ms)", justify="right", width=10)
    table.add_column(t("col_reliability", lang), justify="right", width=13)
    table.add_column(t("col_score", lang), justify="right", width=8)
    table.add_column(t("col_dnssec", lang), justify="center", width=8)
    table.add_column(t("col_malware", lang), justify="center", width=9)
    table.add_column(t("col_ads", lang), justify="center", width=6)

    for rank, s in enumerate(display, 1):
        lat_col = _latency_color(s.median_ms)
        sc_col = _score_color(s.score)
        rel_pct = f"{s.success_rate * 100:.0f}%"
        is_system = s.server_info.get("_is_system", False)
        display_name = f"[bold cyan]\U0001f3e0 {s.name}[/bold cyan]" if is_system else s.name

        table.add_row(
            str(rank),
            display_name,
            Text(_fmt_ms(s.median_ms), style=lat_col),
            Text(_fmt_ms(s.p95_ms), style=_latency_color(s.p95_ms)),
            Text(rel_pct, style="green" if s.success_rate >= 0.95 else "yellow"),
            Text(f"{s.score:.1f}", style=sc_col),
            _bool_symbol(s.dnssec_ok),
            _bool_symbol(s.malware_blocked),
            _bool_symbol(s.ads_blocked),
        )

    console.print(table)

    # Score bar graph
    console.print()
    console.print(f"[bold]Score overview (top {len(display)}):[/bold]")
    for s in display:
        bar_len = int(s.score / 2)  # max 50 chars for score 100
        bar = "█" * bar_len + "░" * (50 - bar_len)
        color = _score_color(s.score)
        console.print(
            f"  [{color}]{bar}[/{color}] [{color}]{s.score:5.1f}[/{color}]  {s.name}"
        )


def _print_plain_table(
    results: list[ServerStats],
    lang: str,
    top: Optional[int] = None,
) -> None:
    display = results[:top] if top else results
    col_w = [5, 28, 10, 8, 13, 7, 8, 9, 6]
    headers = [
        t("col_rank", lang), t("col_server", lang),
        t("col_median", lang), t("col_p95", lang),
        t("col_reliability", lang), t("col_score", lang),
        t("col_dnssec", lang), t("col_malware", lang), t("col_ads", lang),
    ]
    sep = "+" + "+".join("-" * (w + 2) for w in col_w) + "+"
    print(sep)
    row = "|" + "|".join(
        f" {h:<{w}} " for h, w in zip(headers, col_w)
    ) + "|"
    print(row)
    print(sep)
    for rank, s in enumerate(display, 1):
        rel = f"{s.success_rate * 100:.0f}%"
        is_system = s.server_info.get("_is_system", False)
        display_name = (f"[{s.name}]" if is_system else s.name)[:col_w[1]]
        cells = [
            str(rank),
            display_name,
            _fmt_ms(s.median_ms),
            _fmt_ms(s.p95_ms),
            rel,
            f"{s.score:.1f}",
            "✓" if s.dnssec_ok else "✗",
            "✓" if s.malware_blocked else "✗",
            "✓" if s.ads_blocked else "✗",
        ]
        row = "|" + "|".join(
            f" {c:<{w}} " for c, w in zip(cells, col_w)
        ) + "|"
        print(row)
    print(sep)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser(lang: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="natbench",
        description=f"NatBench — {t('app_tagline', lang)}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  natbench                          # benchmark all servers, UDP\n"
            "  natbench --protocol dot --top 10  # DoT, show best 10\n"
            "  natbench --servers 8.8.8.8,1.1.1.1 --count 20\n"
            "  natbench --show-dns\n"
            "  natbench --set-dns 1.1.1.1\n"
            "  natbench --output json --file results.json\n"
        ),
    )
    parser.add_argument(
        "--protocol", "-p",
        choices=["udp", "tcp", "dot", "doh", "all"],
        default="udp",
        help="DNS protocol to use (default: udp).",
    )
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=10,
        metavar="INT",
        help="Number of queries per server for latency measurement (default: 10).",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=float,
        default=3.0,
        metavar="FLOAT",
        help="Per-query socket timeout in seconds (default: 3.0).",
    )
    parser.add_argument(
        "--servers", "-s",
        nargs="+",
        default=["all"],
        metavar="FILTER_OR_IPS",
        help=(
            "Which servers to benchmark. "
            "One of: all, fast, secure, custom, "
            "or space/comma-separated server names or IP[:PORT] addresses (default: all)."
        ),
    )
    parser.add_argument(
        "--output", "-o",
        choices=["table", "json", "csv", "markdown"],
        default="table",
        help="Output format (default: table).",
    )
    parser.add_argument(
        "--file", "-f",
        metavar="PATH",
        default=None,
        help="Write output to FILE instead of stdout.",
    )
    parser.add_argument(
        "--set-dns",
        metavar="IP",
        default=None,
        help="Change the system DNS to the specified IP address.",
    )
    parser.add_argument(
        "--show-dns",
        action="store_true",
        help="Show the current system DNS configuration and exit.",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical (Tkinter) interface.",
    )
    parser.add_argument(
        "--lang", "-l",
        default=None,
        metavar="LANG",
        help=(
            "Interface language (ISO 639-1 code). "
            "Auto-detected from environment if omitted. "
            f"Supported: {', '.join(SUPPORTED_LANGS)}"
        ),
    )
    parser.add_argument(
        "--add-server",
        action="append",
        metavar="IP[:PORT]",
        default=[],
        help="Add a custom server to the benchmark pool (can be repeated).",
    )
    parser.add_argument(
        "--top", "-n",
        type=int,
        default=None,
        metavar="N",
        help="Show only the top N results.",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress logo and progress output; print only results.",
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"NatBench {__version__}",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=16,
        metavar="INT",
        help="Number of parallel benchmark threads (default: 16).",
    )
    parser.add_argument(
        "--self-update",
        action="store_true",
        help="Update NatBench to the latest version (git pull or pip upgrade) and exit.",
    )
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="Check GitHub for a newer NatBench release and print the result, then exit.",
    )
    parser.add_argument(
        "--no-system-dns",
        action="store_true",
        help="Do not auto-detect and prepend system/ISP DNS servers to the benchmark.",
    )
    # --- Profile management ---
    parser.add_argument(
        "--profile",
        metavar="NAME",
        default=None,
        help=(
            "Load a named profile (built-in or user-defined) and use its settings "
            "as defaults. Explicit flags override profile values. "
            "See --list-profiles."
        ),
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List all available profiles (built-in and user) and exit.",
    )
    parser.add_argument(
        "--save-profile",
        metavar="NAME",
        default=None,
        help="Save the current benchmark settings as a named profile and exit.",
    )
    # Positional sub-command alias: "natbench update"
    parser.add_argument(
        "command",
        nargs="?",
        default=None,
        metavar="COMMAND",
        help="Optional sub-command: 'update' (alias for --self-update).",
    )
    return parser


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """
    CLI entry point.

    Returns:
        Exit code (0 = success, non-zero = error).
    """
    # --- Detect language early (before parser, so help text is translated) --
    lang = detect_lang()
    # Build parser once to detect --lang arg before translating
    _pre = argparse.ArgumentParser(add_help=False)
    _pre.add_argument("--lang", "-l", default=None)
    _pre.add_argument("--quiet", "-q", action="store_true")
    pre_args, _ = _pre.parse_known_args()
    if pre_args.lang and pre_args.lang.lower() in SUPPORTED_LANGS:
        lang = pre_args.lang.lower()

    console = Console() if _HAS_RICH else _PlainConsole()

    # --- Show logo ---
    quiet = pre_args.quiet
    if not quiet:
        console.print(_LOGO, highlight=False)

    # --- Parse full args ---
    parser = _build_parser(lang)
    args = parser.parse_args()

    # Override lang from full parse
    if args.lang and args.lang.lower() in SUPPORTED_LANGS:
        lang = args.lang.lower()

    # --- --list-profiles ---
    if getattr(args, "list_profiles", False):
        profiles = list_profiles()
        if not profiles:
            console.print(
                "[yellow]No profiles found.[/yellow]" if _HAS_RICH else "No profiles found."
            )
            return 0
        if _HAS_RICH:
            tbl = Table(title="NatBench Profiles", box=rich_box.ROUNDED, header_style="bold cyan")
            tbl.add_column("Name", min_width=18)
            tbl.add_column("Description", min_width=30)
            tbl.add_column("VPN", justify="center", width=5)
            tbl.add_column("Source", width=10)
            for p in profiles:
                tbl.add_row(
                    p["name"],
                    p.get("description", ""),
                    "✓" if p.get("vpn_enabled") else "—",
                    "[dim]built-in[/dim]" if p.get("is_builtin") else "[cyan]user[/cyan]",
                )
            console.print(tbl)
        else:
            print(f"{'Name':<20} {'VPN':<5} {'Source':<10} Description")
            print("-" * 70)
            for p in profiles:
                src = "built-in" if p.get("is_builtin") else "user"
                vpn = "yes" if p.get("vpn_enabled") else "no"
                print(f"{p['name']:<20} {vpn:<5} {src:<10} {p.get('description', '')}")
        return 0

    # --- --save-profile ---
    if getattr(args, "save_profile", None):
        profile = {
            "name": args.save_profile,
            "description": "",
            "protocol": args.protocol,
            "count": args.count,
            "timeout": args.timeout,
            "workers": args.workers,
            "servers": ",".join(args.servers) if isinstance(args.servers, list) else args.servers,
            "top": args.top,
            "include_system_dns": not getattr(args, "no_system_dns", False),
            "scorer": "default",
            "tags": [],
        }
        errors = validate_profile(profile)
        if errors:
            for err in errors:
                console.print(
                    f"[red]Profile error: {err}[/red]" if _HAS_RICH else f"Profile error: {err}"
                )
            return 1
        path = save_profile(profile)
        console.print(
            f"[green]Profile saved: {path}[/green]" if _HAS_RICH else f"Profile saved: {path}"
        )
        return 0

    # --- --profile: load profile and apply as defaults ---
    if getattr(args, "profile", None):
        try:
            prof = load_profile(args.profile)
        except FileNotFoundError:
            console.print(
                f"[red]Profile not found: {args.profile!r}[/red]"
                if _HAS_RICH else f"Profile not found: {args.profile!r}"
            )
            console.print(
                "  Use [bold]natbench --list-profiles[/bold] to see available profiles."
                if _HAS_RICH else "  Use natbench --list-profiles to see available profiles."
            )
            return 1
        if not quiet:
            desc = prof.get("description", "")
            console.print(
                f"[cyan]Using profile: [bold]{args.profile}[/bold]"
                + (f" — {desc}" if desc else "") + "[/cyan]"
                if _HAS_RICH
                else f"Using profile: {args.profile}" + (f" — {desc}" if desc else "")
            )
        # Apply profile values only where the user hasn't explicitly set a flag
        # (argparse doesn't expose which were defaulted, so we compare to defaults)
        _parser_defaults = _build_parser(lang).parse_args([])
        for arg_name, prof_key in [
            ("protocol", "protocol"), ("count", "count"), ("timeout", "timeout"),
            ("workers", "workers"), ("servers", "servers"), ("top", "top"),
        ]:
            if getattr(args, arg_name) == getattr(_parser_defaults, arg_name):
                if prof.get(prof_key) is not None:
                    setattr(args, arg_name, prof[prof_key])

        # Handle VPN if the profile enables it
        vpn_cfg = prof.get("vpn", {})
        if vpn_cfg.get("enabled"):
            try:
                from .vpn import VpnContextManager
                _vpn_ctx = VpnContextManager(vpn_cfg)
            except ImportError:
                try:
                    from natbench.vpn import VpnContextManager
                    _vpn_ctx = VpnContextManager(vpn_cfg)
                except ImportError:
                    _vpn_ctx = None
            if _vpn_ctx and not quiet:
                console.print(
                    f"[yellow]VPN: {vpn_cfg.get('name', vpn_cfg.get('type', 'unknown'))} "
                    f"will be activated before benchmark.[/yellow]"
                    if _HAS_RICH
                    else f"VPN: {vpn_cfg.get('name', 'unknown')} will be activated."
                )
        else:
            _vpn_ctx = None
    else:
        _vpn_ctx = None

    # --- natbench update  /  --self-update ---
    if getattr(args, "self_update", False) or getattr(args, "command", None) == "update":
        return self_update(verbose=True)

    # --- --check-update ---
    if getattr(args, "check_update", False):
        if not quiet:
            console.print(
                "[cyan]Checking for updates…[/cyan]" if _HAS_RICH else "Checking for updates…"
            )
        info = check_for_updates()
        if info["error"]:
            console.print(
                f"[red]Update check failed: {info['error']}[/red]"
                if _HAS_RICH else f"Update check failed: {info['error']}"
            )
            return 1
        if info["newer"]:
            console.print(
                f"[green]New version available: {info['latest']} "
                f"(current: {info['current']})[/green]\n"
                f"[dim]{info['url']}[/dim]"
                if _HAS_RICH
                else f"New version available: {info['latest']} (current: {info['current']})\n{info['url']}"
            )
        else:
            console.print(
                f"[green]NatBench {info['current']} is up-to-date.[/green]"
                if _HAS_RICH else f"NatBench {info['current']} is up-to-date."
            )
        return 0

    # --- --gui ---
    if getattr(args, "gui", False):
        try:
            from .gui import main as _gui_main
        except SystemExit as exc:
            print(str(exc))
            return 1
        _gui_main()
        return 0

    # --- --show-dns ---
    if args.show_dns:
        cfg = get_current_dns()
        if _HAS_RICH:
            from rich.table import Table as RTable
            tbl = RTable(title=t("gui_tab_dns", lang), box=rich_box.SIMPLE)
            tbl.add_column(t("col_server", lang))
            tbl.add_column("Method")
            tbl.add_column("Interface")
            for ip in cfg.servers:
                tbl.add_row(ip, cfg.method, cfg.interface or "(system)")
            console.print(tbl)
        else:
            print(f"{t('gui_lbl_current_dns', lang)}: {', '.join(cfg.servers) or '(none)'}")
            print(f"Method: {cfg.method}")
            if cfg.interface:
                print(f"Interface: {cfg.interface}")
        return 0

    # --- --set-dns ---
    if args.set_dns:
        ip = args.set_dns.strip()
        if _HAS_RICH:
            console.print(t("msg_set_dns_confirm", lang, ip=ip))
            answer = input("  [y/N] ").strip().lower()
        else:
            print(t("msg_set_dns_confirm", lang, ip=ip))
            answer = input("  [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            console.print("[yellow]Aborted.[/yellow]" if _HAS_RICH else "Aborted.")
            return 0
        try:
            ok = set_dns([ip])
            if ok:
                console.print(
                    f"[green]{t('msg_dns_changed', lang, ip=ip)}[/green]"
                    if _HAS_RICH else t("msg_dns_changed", lang, ip=ip)
                )
            else:
                console.print(
                    f"[red]{t('msg_dns_change_failed', lang)}[/red]"
                    if _HAS_RICH else t("msg_dns_change_failed", lang)
                )
                return 1
        except PermissionError:
            console.print(
                f"[red]{t('msg_need_root', lang)}[/red]"
                if _HAS_RICH else t("msg_need_root", lang)
            )
            return 1
        return 0

    # --- Determine protocols to benchmark ---
    protocols: list[str]
    if args.protocol == "all":
        protocols = ["udp", "tcp", "dot", "doh"]
    else:
        protocols = [args.protocol]

    # --- Detect system/ISP DNS and show to user ---
    no_system_dns = getattr(args, "no_system_dns", False)
    system_servers: list[dict] = []
    if not no_system_dns and args.protocol in ("udp", "tcp", "all"):
        system_servers = get_system_dns_servers()
        if system_servers and not quiet:
            if _HAS_RICH:
                console.print("[bold]Detected DNS servers:[/bold]")
                for srv in system_servers:
                    ip = srv.get("_raw_ip", srv.get("ip4") or srv.get("ip6", "?"))
                    label = srv.get("_label", "")
                    tag_str = f" [dim]({label})[/dim]" if label else ""
                    console.print(f"  [cyan]System resolver: {ip}{tag_str}[/cyan]")
                console.print()
            else:
                print("Detected DNS servers:")
                for srv in system_servers:
                    ip = srv.get("_raw_ip", srv.get("ip4") or srv.get("ip6", "?"))
                    label = srv.get("_label", "")
                    tag_str = f" ({label})" if label else ""
                    print(f"  System resolver: {ip}{tag_str}")
                print()

    # --- Select server pool ---
    servers_str = ",".join(args.servers) if isinstance(args.servers, list) else args.servers
    pool = _select_servers(servers_str, args.protocol, args.add_server or [])

    # Prepend system DNS (deduplicated by IP)
    if system_servers:
        existing_ips = {s.get("ip4") or s.get("ip6") for s in pool}
        for srv in reversed(system_servers):
            ip = srv.get("ip4") or srv.get("ip6")
            if ip and ip not in existing_ips:
                pool.insert(0, srv)
                existing_ips.add(ip)

    if not pool:
        console.print(
            "[red]No servers match the selected filter/protocol.[/red]"
            if _HAS_RICH else "No servers match the selected filter/protocol."
        )
        return 1

    if not quiet:
        console.print(
            f"[cyan]Benchmarking {len(pool)} server(s) via {args.protocol.upper()}, "
            f"{args.count} queries each, timeout {args.timeout}s…[/cyan]"
            if _HAS_RICH
            else f"Benchmarking {len(pool)} server(s) via {args.protocol.upper()}…"
        )

    # --- Run benchmark (optionally inside a VPN session) ---
    from contextlib import nullcontext
    _ctx = _vpn_ctx if _vpn_ctx else nullcontext()

    all_results: list[ServerStats] = []
    start_time = time.perf_counter()

    with _ctx:
        for protocol in protocols:
            proto_pool = _filter_pool_for_protocol(pool, protocol)
            if not proto_pool:
                continue
            if _HAS_RICH and not quiet:
                results = _run_with_rich_progress(
                    proto_pool, args.count, args.timeout,
                    protocol, lang, args.workers,
                )
            else:
                results = _run_plain_progress(
                    proto_pool, args.count, args.timeout,
                    protocol, lang, args.workers, quiet,
                )
            all_results.extend(results)

    if not all_results:
        console.print(
            f"[red]{t('msg_no_results', lang)}[/red]"
            if _HAS_RICH else t("msg_no_results", lang)
        )
        return 1

    # Sort combined results by score
    all_results.sort(key=lambda s: s.score, reverse=True)
    elapsed = time.perf_counter() - start_time

    if not quiet:
        console.print(
            f"\n[green]{t('msg_done_n_servers', lang, n=len(all_results))}[/green] "
            f"[dim](in {elapsed:.1f}s)[/dim]"
            if _HAS_RICH
            else f"\n{t('msg_done_n_servers', lang, n=len(all_results))} (in {elapsed:.1f}s)"
        )

    # --- Format output ---
    if args.output == "table":
        if _HAS_RICH:
            _print_rich_table(all_results, lang, args.top)
        else:
            _print_plain_table(all_results, lang, args.top)
        # If --file is given also write JSON alongside
        if args.file:
            _write_file(args.file, _results_as_json(all_results), lang, console)

    elif args.output == "json":
        content = _results_as_json(all_results)
        _output_or_file(content, args.file, lang, console)

    elif args.output == "csv":
        content = _results_as_csv(all_results)
        _output_or_file(content, args.file, lang, console)

    elif args.output == "markdown":
        content = _results_as_markdown(all_results)
        _output_or_file(content, args.file, lang, console)

    return 0


# ---------------------------------------------------------------------------
# Helpers: progress runners
# ---------------------------------------------------------------------------


def _filter_pool_for_protocol(pool: list[dict], protocol: str) -> list[dict]:
    if protocol == "dot":
        return [s for s in pool if s.get("dot_host")]
    if protocol == "doh":
        return [s for s in pool if s.get("doh_url")]
    if protocol in ("udp", "tcp"):
        return [s for s in pool if s.get("ip4") or s.get("ip6")]
    return pool


def _run_with_rich_progress(
    pool: list[dict],
    count: int,
    timeout: float,
    protocol: str,
    lang: str,
    workers: int,
) -> list[ServerStats]:
    """Run benchmark with a rich progress bar."""
    results: list[ServerStats] = []
    console = Console()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(
            f"[cyan]{protocol.upper()}[/cyan]",
            total=len(pool),
        )

        def _cb(name: str, done: int, total: int) -> None:
            progress.update(
                task,
                completed=done,
                description=t("msg_testing_server", lang, name=name),
            )

        results = run_benchmark(
            pool,
            n_queries=count,
            timeout=timeout,
            protocol=protocol,
            progress_cb=_cb,
            max_workers=workers,
        )

    return results


def _run_plain_progress(
    pool: list[dict],
    count: int,
    timeout: float,
    protocol: str,
    lang: str,
    workers: int,
    quiet: bool,
) -> list[ServerStats]:
    """Run benchmark with plain-text progress."""

    done_count = [0]

    def _cb(name: str, done: int, total: int) -> None:
        done_count[0] = done
        if not quiet:
            pct = int(done / total * 100)
            bar = "#" * (pct // 2) + "." * (50 - pct // 2)
            print(
                f"\r[{bar}] {pct:3d}% — {t('msg_testing_server', lang, name=name):<40}",
                end="",
                flush=True,
            )

    results = run_benchmark(
        pool,
        n_queries=count,
        timeout=timeout,
        protocol=protocol,
        progress_cb=_cb,
        max_workers=workers,
    )
    if not quiet:
        print()  # newline after progress
    return results


# ---------------------------------------------------------------------------
# Helpers: file output
# ---------------------------------------------------------------------------


def _write_file(
    path: str,
    content: str,
    lang: str,
    console: object,
) -> None:
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        msg = t("msg_export_done", lang, path=path)
        if _HAS_RICH:
            console.print(f"[green]{msg}[/green]")
        else:
            print(msg)
    except OSError as exc:
        msg = f"Write error: {exc}"
        if _HAS_RICH:
            console.print(f"[red]{msg}[/red]")
        else:
            print(msg)


def _output_or_file(
    content: str,
    path: Optional[str],
    lang: str,
    console: object,
) -> None:
    if path:
        _write_file(path, content, lang, console)
    else:
        print(content)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
