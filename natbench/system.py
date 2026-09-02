"""
NatBench system.py — OS-level DNS management.

Reads and writes the system DNS configuration on Linux, macOS and Windows.
All write operations require root / administrator privileges.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# DnsConfig dataclass
# ---------------------------------------------------------------------------


@dataclass
class DnsConfig:
    """
    Snapshot of the system's DNS configuration.

    Attributes:
        servers:   Ordered list of resolver IP addresses (IPv4 or IPv6).
        interface: Network interface / service name the config applies to.
                   Empty string means "system-wide / unknown".
        method:    How the config was read / should be written back.
                   One of: "resolv", "systemd-resolved", "networksetup",
                   "netsh", "unknown".
    """

    servers: list[str]
    interface: str = ""
    method: str = "unknown"

    def __str__(self) -> str:
        iface = f" [{self.interface}]" if self.interface else ""
        return f"DnsConfig(servers={self.servers}, method={self.method}{iface})"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], timeout: int = 10) -> str:
    """
    Run *cmd* and return stdout as a string.  Returns "" on any error.
    Never raises.
    """
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
        )
        return result.stdout
    except Exception:
        return ""


def _run_checked(cmd: list[str], timeout: int = 10) -> tuple[bool, str, str]:
    """
    Run *cmd* and return (success, stdout, stderr).
    *success* is True when returncode == 0.
    """
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as exc:
        return False, "", str(exc)


def _ip_valid(s: str) -> bool:
    """Lightweight check: does *s* look like an IPv4 or IPv6 address?"""
    import socket
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(family, s)
            return True
        except OSError:
            pass
    return False


def _parse_resolv_conf(text: str) -> list[str]:
    """Return nameserver IPs from resolv.conf text."""
    servers: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or line.startswith(";"):
            continue
        m = re.match(r"^nameserver\s+(\S+)", line, re.IGNORECASE)
        if m:
            ip = m.group(1)
            if _ip_valid(ip) and ip not in servers:
                servers.append(ip)
    return servers


def _is_systemd_resolved_active() -> bool:
    """Return True if systemd-resolved is the active stub resolver."""
    # Check if /etc/resolv.conf is a symlink pointing to systemd-resolved's stub
    resolv = "/etc/resolv.conf"
    try:
        target = os.readlink(resolv)
        if "systemd" in target or "run/resolve" in target:
            return True
    except OSError:
        pass
    # Check if the service is running
    ok, out, _ = _run_checked(["systemctl", "is-active", "systemd-resolved"])
    if ok and "active" in out:
        return True
    # Check for resolvectl
    if shutil.which("resolvectl"):
        ok2, out2, _ = _run_checked(["resolvectl", "status", "--no-pager"])
        if ok2 and out2:
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_root() -> bool:
    """
    Return True if the current process has root / administrator privileges.

    On Unix this checks ``os.geteuid() == 0``.
    On Windows this calls ``ctypes.windll.shell32.IsUserAnAdmin()``.
    """
    if platform.system() == "Windows":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0


def get_interfaces() -> list[str]:
    """
    Return a list of network interface / service names relevant for DNS.

    - Linux:   network interface names from ``/proc/net/dev`` (e.g. "eth0", "wlan0")
    - macOS:   network service names from ``networksetup -listallnetworkservices``
    - Windows: adapter names from ``netsh interface ip show config``
    - Fallback: ["default"]
    """
    system = platform.system()

    if system == "Linux" or system == "FreeBSD":
        ifaces: list[str] = []
        try:
            with open("/proc/net/dev", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if ":" in line:
                        name = line.split(":")[0].strip()
                        if name and name != "lo":
                            ifaces.append(name)
        except OSError:
            pass
        # Also try ip link
        if not ifaces:
            out = _run(["ip", "-o", "link", "show"])
            for line in out.splitlines():
                m = re.match(r"^\d+:\s+(\S+):", line)
                if m:
                    name = m.group(1).rstrip("@").split("@")[0]
                    if name != "lo":
                        ifaces.append(name)
        return ifaces or ["default"]

    elif system == "Darwin":
        out = _run(["networksetup", "-listallnetworkservices"])
        services: list[str] = []
        for line in out.splitlines():
            line = line.strip()
            if line and not line.startswith("*") and not line.lower().startswith("an asterisk"):
                services.append(line)
        return services or ["Wi-Fi", "Ethernet"]

    elif system == "Windows":
        out = _run(["netsh", "interface", "show", "interface"])
        adapters: list[str] = []
        for line in out.splitlines():
            # "Enabled  Connected  Dedicated  Wi-Fi"  (last field is the name)
            parts = line.split()
            if len(parts) >= 4 and parts[0] in ("Enabled", "Disabled"):
                adapters.append(" ".join(parts[3:]))
        return adapters or ["Local Area Connection"]

    return ["default"]


def get_current_dns() -> DnsConfig:
    """
    Read the current system DNS configuration.

    - Linux/FreeBSD:
        * Checks if systemd-resolved is active; if so reads
          ``/run/systemd/resolve/resolv.conf`` (the full upstream list)
          and uses ``resolvectl`` to find the interface.
        * Otherwise parses ``/etc/resolv.conf`` directly.
    - macOS:
        * Runs ``networksetup -getdnsservers <service>`` for all network
          services; also cross-checks with ``scutil --dns``.
    - Windows:
        * Parses output of ``netsh interface ip show dns``.

    Returns:
        :class:`DnsConfig` with the discovered servers.
    """
    system = platform.system()

    if system in ("Linux", "FreeBSD"):
        return _get_dns_linux()
    elif system == "Darwin":
        return _get_dns_macos()
    elif system == "Windows":
        return _get_dns_windows()
    else:
        return _get_dns_linux()


# -- Linux -------------------------------------------------------------------


def _get_dns_linux() -> DnsConfig:
    """Read DNS on Linux/FreeBSD."""
    if _is_systemd_resolved_active():
        return _get_dns_systemd_resolved()
    return _get_dns_resolv_conf()


def _get_dns_resolv_conf(path: str = "/etc/resolv.conf") -> DnsConfig:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        text = ""
    servers = _parse_resolv_conf(text)
    return DnsConfig(servers=servers, interface="", method="resolv")


def _get_dns_systemd_resolved() -> DnsConfig:
    """Read DNS via systemd-resolved."""
    # Prefer the upstream resolv.conf that resolved writes
    stub_path = "/run/systemd/resolve/resolv.conf"
    if os.path.isfile(stub_path):
        try:
            with open(stub_path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            servers = _parse_resolv_conf(text)
            if servers:
                return DnsConfig(servers=servers, interface="", method="systemd-resolved")
        except OSError:
            pass

    # Fall back to resolvectl status output
    out = _run(["resolvectl", "status", "--no-pager"])
    servers: list[str] = []
    for line in out.splitlines():
        m = re.search(r"DNS Servers?:\s*(.+)", line)
        if m:
            for tok in m.group(1).split():
                if _ip_valid(tok) and tok not in servers:
                    servers.append(tok)
    if servers:
        return DnsConfig(servers=servers, interface="", method="systemd-resolved")

    # Last resort: parse /etc/resolv.conf as-is
    return _get_dns_resolv_conf()


# -- macOS -------------------------------------------------------------------


def _get_dns_macos() -> DnsConfig:
    """Read DNS on macOS using networksetup and scutil."""
    services = get_interfaces()
    all_servers: list[str] = []
    primary_iface = ""

    for svc in services:
        out = _run(["networksetup", "-getdnsservers", svc])
        # Success output: one IP per line
        # Failure output: "There aren't any DNS Servers set..."
        if "aren't" in out or "aren" in out.lower() or "empty" in out.lower():
            continue
        for line in out.splitlines():
            ip = line.strip()
            if _ip_valid(ip) and ip not in all_servers:
                all_servers.append(ip)
                if not primary_iface:
                    primary_iface = svc

    if not all_servers:
        # Fall back to scutil --dns
        out = _run(["scutil", "--dns"])
        for line in out.splitlines():
            m = re.search(r"nameserver\[\d+\]\s*:\s*(\S+)", line)
            if m:
                ip = m.group(1)
                if _ip_valid(ip) and ip not in all_servers:
                    all_servers.append(ip)

    return DnsConfig(
        servers=all_servers,
        interface=primary_iface,
        method="networksetup",
    )


# -- Windows -----------------------------------------------------------------


def _get_dns_windows() -> DnsConfig:
    """Read DNS on Windows using netsh."""
    out = _run(["netsh", "interface", "ip", "show", "dns"])
    servers: list[str] = []
    current_iface = ""
    primary_iface = ""

    for line in out.splitlines():
        line = line.strip()
        # New interface block header
        m_iface = re.search(r'Configuration for interface "([^"]+)"', line)
        if m_iface:
            current_iface = m_iface.group(1)
            continue
        # DNS server line
        m_dns = re.search(
            r"(?:DNS Servers|Statically Configured DNS Servers|Register with which suffix).*?:\s*(\S+)",
            line,
            re.IGNORECASE,
        )
        if m_dns:
            ip = m_dns.group(1)
            if _ip_valid(ip) and ip not in servers:
                servers.append(ip)
                if not primary_iface:
                    primary_iface = current_iface
            continue
        # Continuation: bare IP on its own line
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", line) or re.match(
            r"^[0-9a-fA-F:]+$", line
        ):
            if _ip_valid(line) and line not in servers:
                servers.append(line)

    return DnsConfig(
        servers=servers,
        interface=primary_iface,
        method="netsh",
    )


# ---------------------------------------------------------------------------
# set_dns
# ---------------------------------------------------------------------------


def set_dns(
    servers: list[str],
    interface: Optional[str] = None,
) -> bool:
    """
    Change the system DNS configuration to *servers*.

    Args:
        servers:   Ordered list of DNS server IP addresses.  At least one
                   must be provided.
        interface: Network interface / service to configure.  If None the
                   function will attempt to determine the primary interface
                   automatically.

    Returns:
        True on success.

    Raises:
        PermissionError: If the process does not have root/admin privileges.
        ValueError:      If *servers* is empty or contains invalid IPs.
    """
    if not servers:
        raise ValueError("servers list must not be empty")
    for ip in servers:
        if not _ip_valid(ip):
            raise ValueError(f"Invalid IP address: {ip!r}")
    if not check_root():
        raise PermissionError(
            "Root / administrator privileges are required to change the system DNS."
        )

    system = platform.system()

    if system in ("Linux", "FreeBSD"):
        return _set_dns_linux(servers, interface)
    elif system == "Darwin":
        return _set_dns_macos(servers, interface)
    elif system == "Windows":
        return _set_dns_windows(servers, interface)
    else:
        return _set_dns_linux(servers, interface)


# -- Linux -------------------------------------------------------------------


def _set_dns_linux(servers: list[str], interface: Optional[str]) -> bool:
    """Set DNS on Linux."""
    if _is_systemd_resolved_active() and shutil.which("resolvectl"):
        return _set_dns_resolvectl(servers, interface)
    return _set_dns_resolv_conf(servers)


def _set_dns_resolvectl(servers: list[str], interface: Optional[str]) -> bool:
    """Use resolvectl to configure DNS."""
    iface = interface or _pick_primary_interface_linux()
    cmd = ["resolvectl", "dns", iface] + servers
    ok, _, err = _run_checked(cmd)
    if not ok:
        # Fallback: write resolv.conf directly
        return _set_dns_resolv_conf(servers)
    return True


def _pick_primary_interface_linux() -> str:
    """Guess the primary non-loopback interface."""
    ifaces = get_interfaces()
    # Prefer typical wireless/ethernet names
    for preferred in ("eth0", "ens3", "ens33", "enp0s3", "wlan0", "wlp2s0"):
        if preferred in ifaces:
            return preferred
    return ifaces[0] if ifaces else "eth0"


def _set_dns_resolv_conf(
    servers: list[str],
    path: str = "/etc/resolv.conf",
) -> bool:
    """Write nameserver entries to /etc/resolv.conf, preserving other lines."""
    # Read existing content
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            old_lines = fh.readlines()
    except OSError:
        old_lines = []

    # Keep everything that's not a nameserver line
    kept: list[str] = [
        ln for ln in old_lines
        if not re.match(r"^\s*nameserver\s", ln, re.IGNORECASE)
    ]

    new_ns = [f"nameserver {ip}\n" for ip in servers]

    # Write atomically via a temp file in the same directory
    dir_ = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp = tempfile.mkstemp(dir=dir_, prefix=".resolv_tmp_")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.writelines(new_ns + kept)
        os.replace(tmp, path)
        return True
    except OSError:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        return False


# -- macOS -------------------------------------------------------------------


def _set_dns_macos(servers: list[str], interface: Optional[str]) -> bool:
    """Set DNS on macOS using networksetup."""
    services = [interface] if interface else get_interfaces()
    success = False
    for svc in services:
        cmd = ["networksetup", "-setdnsservers", svc] + servers
        ok, _, _ = _run_checked(cmd)
        if ok:
            success = True
    return success


# -- Windows -----------------------------------------------------------------


def _set_dns_windows(servers: list[str], interface: Optional[str]) -> bool:
    """Set DNS on Windows using netsh."""
    if not interface:
        ifaces = get_interfaces()
        interface = ifaces[0] if ifaces else "Local Area Connection"

    # Set primary DNS
    primary = servers[0]
    cmd_primary = [
        "netsh", "interface", "ip", "set", "dns",
        f"name={interface}", "static", primary,
    ]
    ok, _, _ = _run_checked(cmd_primary)
    if not ok:
        return False

    # Add additional servers
    for i, ip in enumerate(servers[1:], start=2):
        cmd_add = [
            "netsh", "interface", "ip", "add", "dns",
            f"name={interface}", ip, f"index={i}",
        ]
        _run_checked(cmd_add)  # best-effort

    return True


# ---------------------------------------------------------------------------
# restore_dns
# ---------------------------------------------------------------------------


def restore_dns(config: DnsConfig) -> bool:
    """
    Restore a previously saved :class:`DnsConfig`.

    This is a convenience wrapper around :func:`set_dns` that uses the
    interface and method stored inside *config*.

    Args:
        config: A :class:`DnsConfig` returned by a previous call to
                :func:`get_current_dns`.

    Returns:
        True on success.

    Raises:
        PermissionError: If not root/admin.
        ValueError:      If config.servers is empty.
    """
    return set_dns(
        servers=config.servers,
        interface=config.interface or None,
    )


# ---------------------------------------------------------------------------
# Convenience: detect + format
# ---------------------------------------------------------------------------


def current_dns_summary() -> str:
    """
    Return a short human-readable string of the current DNS servers.

    Example: "8.8.8.8, 8.8.4.4 (resolv)"
    """
    cfg = get_current_dns()
    ips = ", ".join(cfg.servers) if cfg.servers else "(none)"
    return f"{ips} ({cfg.method})"
