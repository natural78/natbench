"""
natbench.vpn
============
VPN connect/disconnect/verify for test profiles.

Supports:
  - WireGuard  (wg-quick up/down <conf>)
  - OpenVPN    (openvpn --config <conf>)
  - Custom     (arbitrary shell commands)
  - NordVPN    (nordvpn connect/disconnect CLI)
  - Mullvad    (mullvad connect/disconnect CLI)
"""

from __future__ import annotations

import logging
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# VpnSession dataclass
# ---------------------------------------------------------------------------


@dataclass
class VpnSession:
    """Represents an active VPN connection during a benchmark."""

    name: str
    vpn_type: str             # "wireguard" | "openvpn" | "nordvpn" | "mullvad" | "custom"
    connect_cmd: str | None
    disconnect_cmd: str | None
    ip_before: str | None     # public IP before connect
    ip_after: str | None      # public IP after connect
    connected: bool
    connect_time: float       # seconds taken to connect
    _process: Any = field(default=None, repr=False)  # subprocess handle for daemons


# ---------------------------------------------------------------------------
# Public IP detection
# ---------------------------------------------------------------------------

_IP_URLS = [
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://icanhazip.com",
]


def get_public_ip(timeout: float = 5.0) -> str | None:
    """
    Get current public IP via api.ipify.org (fallback: ifconfig.me).

    Returns:
        IP address string, or None on error.
    """
    for url in _IP_URLS:
        try:
            with urlopen(url, timeout=timeout) as resp:
                ip = resp.read().decode("ascii", errors="ignore").strip()
                if ip:
                    return ip
        except (URLError, OSError, TimeoutError):
            continue
    return None


# ---------------------------------------------------------------------------
# Command builder
# ---------------------------------------------------------------------------


def build_connect_cmd(vpn_config: dict) -> tuple[str, str]:
    """
    Build (connect_cmd, disconnect_cmd) from vpn_config.

    For type "wireguard": uses vpn_config["name"] or "wg0" as the interface.
    For type "openvpn":   uses vpn_config["connect_cmd"] as config path if set.
    For type "nordvpn":   fixed CLI commands.
    For type "mullvad":   fixed CLI commands.
    For type "custom":    uses connect_cmd/disconnect_cmd from config directly.

    Returns:
        (connect_cmd, disconnect_cmd) tuple of shell command strings.

    Raises:
        ValueError: if vpn_type is unknown or required fields are missing.
    """
    vpn_type = (vpn_config.get("type") or "").lower()
    name = vpn_config.get("name") or ""
    explicit_connect = vpn_config.get("connect_cmd") or ""
    explicit_disconnect = vpn_config.get("disconnect_cmd") or ""

    if vpn_type == "wireguard":
        # Use explicit commands if provided, otherwise build from name
        if explicit_connect and explicit_disconnect:
            return explicit_connect, explicit_disconnect
        iface = _extract_wg_iface(explicit_connect) or name or "wg0"
        return f"wg-quick up {iface}", f"wg-quick down {iface}"

    elif vpn_type == "openvpn":
        if explicit_connect and explicit_disconnect:
            return explicit_connect, explicit_disconnect
        # If connect_cmd looks like a file path, wrap in openvpn call
        config_path = explicit_connect or "/etc/openvpn/client.conf"
        return (
            f"openvpn --config {config_path} --daemon --log /tmp/natbench_ovpn.log",
            "pkill -f openvpn",
        )

    elif vpn_type == "nordvpn":
        return "nordvpn connect", "nordvpn disconnect"

    elif vpn_type == "mullvad":
        return "mullvad connect", "mullvad disconnect"

    elif vpn_type == "custom":
        if not explicit_connect:
            raise ValueError(
                "VPN type 'custom' requires 'connect_cmd' to be set in the profile"
            )
        if not explicit_disconnect:
            raise ValueError(
                "VPN type 'custom' requires 'disconnect_cmd' to be set in the profile"
            )
        return explicit_connect, explicit_disconnect

    else:
        raise ValueError(
            f"Unknown VPN type: {vpn_type!r}. "
            f"Valid types: wireguard, openvpn, nordvpn, mullvad, custom"
        )


def _extract_wg_iface(cmd: str) -> str | None:
    """Extract WireGuard interface name from a wg-quick command, or return None."""
    parts = cmd.split()
    # "wg-quick up wg0" → "wg0"
    if len(parts) >= 3 and parts[0] in ("wg-quick", "wg"):
        return parts[-1]
    return None


# ---------------------------------------------------------------------------
# VPN client detection
# ---------------------------------------------------------------------------


def detect_vpn_clients() -> list[str]:
    """
    Return list of detected VPN clients available in PATH.

    Returns any subset of: ["wireguard", "openvpn", "nordvpn", "mullvad"]
    """
    candidates = {
        "wireguard": "wg-quick",
        "openvpn": "openvpn",
        "nordvpn": "nordvpn",
        "mullvad": "mullvad",
    }
    return [name for name, binary in candidates.items() if shutil.which(binary)]


# ---------------------------------------------------------------------------
# Connect / disconnect helpers
# ---------------------------------------------------------------------------


def _run_cmd(cmd: str, timeout: int = 30) -> tuple[bool, str]:
    """
    Run a shell command. Returns (success, combined_output).
    Never raises.
    """
    try:
        result = subprocess.run(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            text=True,
        )
        return result.returncode == 0, result.stdout or ""
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout}s: {cmd}"
    except FileNotFoundError as exc:
        return False, f"Command not found: {exc}"
    except Exception as exc:
        return False, str(exc)


def connect_vpn(vpn_config: dict) -> VpnSession:
    """
    Connect VPN from profile vpn dict.

    Process:
    1. Records public IP before connecting.
    2. Builds or uses configured connect/disconnect commands.
    3. Runs the connect command.
    4. Waits vpn_config['wait_seconds'] seconds for the VPN to settle.
    5. Records public IP after connecting.
    6. If vpn_config['verify_changed'] is True, checks that the IP changed.

    Returns:
        VpnSession with all connection info.

    Raises:
        RuntimeError: if the connect command fails or IP verification fails.
    """
    vpn_type = (vpn_config.get("type") or "custom").lower()
    wait_seconds = float(vpn_config.get("wait_seconds", 3))
    verify_changed = bool(vpn_config.get("verify_changed", True))
    display_name = vpn_config.get("name") or vpn_type.title()

    # Build commands (may be already set or auto-generated)
    try:
        connect_cmd, disconnect_cmd = build_connect_cmd(vpn_config)
    except ValueError as exc:
        raise RuntimeError(f"VPN configuration error: {exc}") from exc

    # Step 1: record IP before
    log.debug("VPN: recording public IP before connection")
    ip_before = get_public_ip()
    log.debug("VPN: IP before = %s", ip_before)

    # Step 2: connect
    log.info("VPN: connecting %s via command: %s", display_name, connect_cmd)
    t0 = time.monotonic()
    ok, output = _run_cmd(connect_cmd, timeout=60)
    connect_time = time.monotonic() - t0

    if not ok:
        raise RuntimeError(
            f"VPN connect command failed for {display_name!r}:\n  cmd: {connect_cmd}\n  output: {output}"
        )

    log.debug("VPN: connect command completed in %.1fs", connect_time)

    # Step 3: wait for VPN to settle
    if wait_seconds > 0:
        log.debug("VPN: waiting %.1f seconds for VPN to settle", wait_seconds)
        time.sleep(wait_seconds)

    # Step 4: record IP after
    ip_after = get_public_ip()
    log.debug("VPN: IP after = %s", ip_after)

    # Step 5: verify IP changed
    if verify_changed and ip_before and ip_after and ip_before == ip_after:
        # Disconnect before raising so we don't leave a broken state
        _run_cmd(disconnect_cmd, timeout=30)
        raise RuntimeError(
            f"VPN verification failed: public IP did not change after connecting {display_name!r}. "
            f"IP before and after: {ip_before}. Check your VPN configuration."
        )

    return VpnSession(
        name=display_name,
        vpn_type=vpn_type,
        connect_cmd=connect_cmd,
        disconnect_cmd=disconnect_cmd,
        ip_before=ip_before,
        ip_after=ip_after,
        connected=True,
        connect_time=connect_time,
    )


def disconnect_vpn(session: VpnSession, vpn_config: dict) -> bool:
    """
    Disconnect VPN using the session's stored disconnect command.

    Swallows all errors (logs them at WARNING level) — never raises during
    cleanup so that benchmarks always complete cleanly.

    Returns:
        True on success, False if the disconnect command failed.
    """
    if not session.connected:
        return True

    disconnect_cmd = session.disconnect_cmd
    if not disconnect_cmd:
        log.warning("VPN: no disconnect command stored in session for %s", session.name)
        return False

    log.info("VPN: disconnecting %s via: %s", session.name, disconnect_cmd)
    try:
        ok, output = _run_cmd(disconnect_cmd, timeout=30)
        if ok:
            log.info("VPN: disconnected %s successfully", session.name)
            session.connected = False
            return True
        else:
            log.warning("VPN: disconnect command returned non-zero for %s: %s", session.name, output)
            return False
    except Exception as exc:
        log.warning("VPN: exception while disconnecting %s: %s", session.name, exc)
        return False


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class VpnContextManager:
    """
    Context manager for VPN sessions in benchmarks.

    Usage::

        vpn_cfg = profile["vpn"]
        with VpnContextManager(vpn_cfg) as session:
            print(f"Connected via {session.name}, IP: {session.ip_after}")
            # ... run benchmark ...
        # VPN is disconnected automatically on exit

    The __exit__ method always attempts to disconnect, even if an exception
    occurred during the benchmark.
    """

    def __init__(self, vpn_config: dict, verbose: bool = True) -> None:
        self.vpn_config = vpn_config
        self.verbose = verbose
        self._session: VpnSession | None = None

    def __enter__(self) -> VpnSession:
        if self.verbose:
            name = self.vpn_config.get("name") or self.vpn_config.get("type") or "VPN"
            print(f"[VPN] Connecting {name}...")

        self._session = connect_vpn(self.vpn_config)

        if self.verbose:
            print(
                f"[VPN] Connected in {self._session.connect_time:.1f}s. "
                f"IP: {self._session.ip_before} → {self._session.ip_after}"
            )

        return self._session

    def __exit__(self, *_: Any) -> None:
        if self._session is None:
            return

        restore = self.vpn_config.get("restore_on_exit", True)
        if not restore:
            log.info("VPN: restore_on_exit=false, leaving VPN connected")
            return

        if self.verbose:
            print(f"[VPN] Disconnecting {self._session.name}...")

        ok = disconnect_vpn(self._session, self.vpn_config)

        if self.verbose:
            if ok:
                print(f"[VPN] Disconnected {self._session.name}")
            else:
                print(f"[VPN] Warning: disconnect may have failed for {self._session.name}")
