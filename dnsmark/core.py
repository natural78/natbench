"""
DNSMark core.py — DNS benchmarking engine.

Supports UDP, TCP, DoT (DNS-over-TLS), and DoH (DNS-over-HTTPS) queries.
No external dependencies except 'requests' for DoH (optional).
"""

from __future__ import annotations

import os
import platform
import socket
import ssl
import statistics
import struct
import subprocess
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Optional

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_DOMAINS: list[str] = [
    "google.com",
    "youtube.com",
    "facebook.com",
    "twitter.com",
    "reddit.com",
    "wikipedia.org",
    "amazon.com",
    "github.com",
    "cloudflare.com",
    "microsoft.com",
    "apple.com",
    "netflix.com",
    # NXDOMAIN control — should always return NXDOMAIN (rcode 3)
    "this-domain-should-never-exist-xyzzy123.com",
]

# Target used for the malware-block test; legitimate resolvers that do
# malware filtering should return NXDOMAIN (rcode 3) or REFUSED (rcode 5).
_MALWARE_TEST_DOMAIN = "malware.testcategory.com"

# Target used for the ad-block test.  Ad-blocking resolvers should *not*
# return a real routable IP for this domain.
_AD_TEST_DOMAIN = "doubleclick.net"

# Known "sinkhole" / loopback answers used by ad/malware-blocking resolvers.
_BLOCKED_IPS: frozenset[str] = frozenset(
    [
        "0.0.0.0",
        "127.0.0.1",
        "::1",
        "::ffff:0.0.0.0",
        "0.0.0.1",
    ]
)

_DNSSEC_TEST_DOMAIN = "dnssec-failed.org"  # Should fail validation if DNSSEC enforced

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class QueryResult:
    """Result of a single DNS query."""

    latency_ms: Optional[float]   # None on error/timeout
    success: bool                  # Got a valid DNS response (any rcode counts)
    rcode: int                     # DNS RCODE (0=NOERROR, 2=SERVFAIL, 3=NXDOMAIN …)
    answer_count: int = 0          # Number of answer RRs in the response
    protocol: str = "udp"          # udp | tcp | dot | doh


@dataclass
class ServerStats:
    """Aggregated statistics for one DNS server across N queries."""

    name: str
    ip: str
    protocol: str

    # Latency metrics (ms); None if no successful queries
    min_ms: Optional[float] = None
    avg_ms: Optional[float] = None
    median_ms: Optional[float] = None
    p95_ms: Optional[float] = None
    max_ms: Optional[float] = None
    jitter_ms: Optional[float] = None   # std-dev of successful latencies

    success_rate: float = 0.0           # 0.0–1.0
    total_queries: int = 0
    failed_queries: int = 0

    # Security checks
    dnssec_ok: bool = False             # Resolver enforces DNSSEC validation
    malware_blocked: bool = False       # Resolver blocks known malware domains
    ads_blocked: bool = False           # Resolver blocks known ad domains

    score: float = 0.0                  # Composite score 0–100

    # Pass-through of original server dict for display purposes
    server_info: dict = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Top-level result returned after a full benchmark run."""

    servers: list[ServerStats]          # Sorted by score descending
    n_queries: int
    protocol: str
    duration_s: float
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Raw DNS packet helpers (no external dependencies)
# ---------------------------------------------------------------------------


def _random_txid() -> int:
    return random.randint(0, 0xFFFF)


def build_dns_query(domain: str, qtype: int = 1) -> bytes:
    """
    Build a minimal DNS query packet for *domain* and query type *qtype*.

    Args:
        domain: Fully-qualified or relative domain name, e.g. "google.com".
        qtype:  RR type (default 1 = A).

    Returns:
        Raw bytes suitable for sending over UDP or TCP (without the
        2-byte length prefix required by TCP/DoT — callers add that).
    """
    txid = _random_txid()
    # Flags: QR=0 (query), OPCODE=0 (QUERY), RD=1 (recursion desired)
    flags = 0x0100
    qdcount = 1
    ancount = arcount = nscount = 0

    header = struct.pack("!HHHHHH", txid, flags, qdcount, ancount, nscount, arcount)

    # Encode QNAME
    qname = b""
    for label in domain.rstrip(".").split("."):
        encoded = label.encode("ascii")
        qname += struct.pack("!B", len(encoded)) + encoded
    qname += b"\x00"  # root label

    question = qname + struct.pack("!HH", qtype, 1)  # QTYPE, QCLASS=IN

    return header + question


def parse_dns_response(data: bytes) -> tuple[int, int]:
    """
    Parse a raw DNS response and return (rcode, answer_count).

    Args:
        data: Raw DNS response bytes (without TCP/DoT length prefix).

    Returns:
        (rcode, answer_count)  — rcode is the 4-bit RCODE field;
        answer_count is the ANCOUNT header field.
        Returns (-1, 0) if the response is too short to be valid.
    """
    if len(data) < 12:
        return -1, 0
    _txid, flags, _qdcount, ancount, _nscount, _arcount = struct.unpack(
        "!HHHHHH", data[:12]
    )
    rcode = flags & 0x000F
    return rcode, ancount


# ---------------------------------------------------------------------------
# Protocol-level query functions
# ---------------------------------------------------------------------------


def _query_udp(
    ip: str,
    port: int,
    packet: bytes,
    timeout: float,
) -> tuple[Optional[float], bool, int, int]:
    """
    Send *packet* via UDP to *ip*:*port*.

    Returns:
        (latency_ms, success, rcode, answer_count)
    """
    try:
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        with socket.socket(family, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            t0 = time.perf_counter()
            sock.sendto(packet, (ip, port))
            resp = sock.recv(4096)
            latency = (time.perf_counter() - t0) * 1000.0
        rcode, ancount = parse_dns_response(resp)
        return latency, True, rcode, ancount
    except Exception:
        return None, False, -1, 0


def _query_tcp(
    ip: str,
    port: int,
    packet: bytes,
    timeout: float,
) -> tuple[Optional[float], bool, int, int]:
    """
    Send *packet* via TCP (with the 2-byte length prefix) to *ip*:*port*.

    Returns:
        (latency_ms, success, rcode, answer_count)
    """
    try:
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            t0 = time.perf_counter()
            sock.connect((ip, port))
            # DNS-over-TCP: 2-byte big-endian length prefix
            framed = struct.pack("!H", len(packet)) + packet
            sock.sendall(framed)
            # Read 2-byte length
            raw_len = _recv_exact(sock, 2)
            if raw_len is None:
                return None, False, -1, 0
            resp_len = struct.unpack("!H", raw_len)[0]
            resp = _recv_exact(sock, resp_len)
            latency = (time.perf_counter() - t0) * 1000.0
        if resp is None:
            return None, False, -1, 0
        rcode, ancount = parse_dns_response(resp)
        return latency, True, rcode, ancount
    except Exception:
        return None, False, -1, 0


def _recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
    """Read exactly *n* bytes from *sock*, or return None on error/EOF."""
    buf = b""
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except Exception:
            return None
        if not chunk:
            return None
        buf += chunk
    return buf


def _query_dot(
    host: str,
    port: int,
    packet: bytes,
    timeout: float,
) -> tuple[Optional[float], bool, int, int]:
    """
    DNS-over-TLS query to *host*:*port*.

    The TLS SNI / hostname verification uses *host* directly, so *host* must
    be a hostname, not a bare IP address, for proper certificate verification.
    Falls back to IP if host looks like an IP (verification still attempted).

    Returns:
        (latency_ms, success, rcode, answer_count)
    """
    try:
        ctx = ssl.create_default_context()
        # Resolve host to IP for the actual connection
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as raw_sock:
            raw_sock.settimeout(timeout)
            t0 = time.perf_counter()
            raw_sock.connect((host, port))
            with ctx.wrap_socket(raw_sock, server_hostname=host) as tls_sock:
                framed = struct.pack("!H", len(packet)) + packet
                tls_sock.sendall(framed)
                raw_len = _recv_exact(tls_sock, 2)
                if raw_len is None:
                    return None, False, -1, 0
                resp_len = struct.unpack("!H", raw_len)[0]
                resp = _recv_exact(tls_sock, resp_len)
                latency = (time.perf_counter() - t0) * 1000.0
        if resp is None:
            return None, False, -1, 0
        rcode, ancount = parse_dns_response(resp)
        return latency, True, rcode, ancount
    except Exception:
        return None, False, -1, 0


def _query_doh(
    url: str,
    packet: bytes,
    timeout: float,
) -> tuple[Optional[float], bool, int, int]:
    """
    DNS-over-HTTPS query (RFC 8484 application/dns-message).

    Returns:
        (latency_ms, success, rcode, answer_count)

    Raises ImportError if 'requests' is not available.
    """
    if not _HAS_REQUESTS:
        raise ImportError("'requests' is required for DoH queries")
    import requests  # noqa: PLC0415

    headers = {
        "Content-Type": "application/dns-message",
        "Accept": "application/dns-message",
    }
    try:
        t0 = time.perf_counter()
        resp = requests.post(
            url,
            data=packet,
            headers=headers,
            timeout=timeout,
        )
        latency = (time.perf_counter() - t0) * 1000.0
        if resp.status_code != 200:
            return latency, False, -1, 0
        rcode, ancount = parse_dns_response(resp.content)
        return latency, True, rcode, ancount
    except Exception:
        return None, False, -1, 0


# ---------------------------------------------------------------------------
# Unified query dispatcher
# ---------------------------------------------------------------------------


def query_server(
    server: dict,
    domain: str,
    protocol: str = "udp",
    timeout: float = 3.0,
    qtype: int = 1,
) -> QueryResult:
    """
    Run a single DNS query against *server* for *domain* using *protocol*.

    Args:
        server:   Server dict (same shape as entries in servers.SERVER_DB).
        domain:   Domain name to resolve.
        protocol: One of "udp", "tcp", "dot", "doh".
        timeout:  Socket/request timeout in seconds.
        qtype:    DNS query type (default 1 = A).

    Returns:
        QueryResult
    """
    packet = build_dns_query(domain, qtype)
    ip = server.get("ip4") or server.get("ip6", "")
    port = int(server.get("port", 53))

    if protocol == "udp":
        if not ip:
            return QueryResult(None, False, -1, 0, protocol)
        latency, success, rcode, ancount = _query_udp(ip, port, packet, timeout)

    elif protocol == "tcp":
        if not ip:
            return QueryResult(None, False, -1, 0, protocol)
        latency, success, rcode, ancount = _query_tcp(ip, port, packet, timeout)

    elif protocol == "dot":
        dot_host = server.get("dot_host")
        if not dot_host:
            return QueryResult(None, False, -1, 0, protocol)
        dot_port = int(server.get("dot_port", 853))
        latency, success, rcode, ancount = _query_dot(dot_host, dot_port, packet, timeout)

    elif protocol == "doh":
        doh_url = server.get("doh_url")
        if not doh_url:
            return QueryResult(None, False, -1, 0, protocol)
        latency, success, rcode, ancount = _query_doh(doh_url, packet, timeout)

    else:
        raise ValueError(f"Unknown protocol: {protocol!r}")

    return QueryResult(
        latency_ms=latency,
        success=success,
        rcode=rcode,
        answer_count=ancount,
        protocol=protocol,
    )


# ---------------------------------------------------------------------------
# Security checks
# ---------------------------------------------------------------------------


def _check_dnssec(server: dict, protocol: str, timeout: float) -> bool:
    """
    Return True if the resolver enforces DNSSEC validation.

    Strategy: query a domain whose DNSSEC signatures are intentionally broken
    (_DNSSEC_TEST_DOMAIN).  A validating resolver returns SERVFAIL (rcode 2).
    A non-validating resolver returns NOERROR with answers.
    """
    result = query_server(server, _DNSSEC_TEST_DOMAIN, protocol=protocol, timeout=timeout)
    # SERVFAIL (2) = resolver refused to return broken-DNSSEC data → good
    return result.rcode == 2


def _check_malware_blocked(server: dict, protocol: str, timeout: float) -> bool:
    """
    Return True if the resolver blocks the malware test domain.

    Blocking resolvers return NXDOMAIN (3), REFUSED (5), or a sinkhole IP.
    """
    result = query_server(server, _MALWARE_TEST_DOMAIN, protocol=protocol, timeout=timeout)
    if not result.success:
        return False
    # NXDOMAIN or REFUSED indicates blocking
    if result.rcode in (3, 5):
        return True
    # Zero answers also a strong indicator of blocking
    if result.answer_count == 0:
        return True
    return False


def _check_ads_blocked(server: dict, protocol: str, timeout: float) -> bool:
    """
    Return True if the resolver blocks doubleclick.net (an ad/tracker domain).

    Ad-blocking resolvers return NXDOMAIN, REFUSED, or a sinkhole address.
    Non-blocking resolvers return real IPs.
    """
    result = query_server(server, _AD_TEST_DOMAIN, protocol=protocol, timeout=timeout)
    if not result.success:
        return False
    if result.rcode in (3, 5):
        return True
    if result.answer_count == 0:
        return True
    return False


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_server(stats: ServerStats) -> float:
    """
    Compute a composite score in the range [0, 100].

    Weights:
        Speed       50% — based on median latency
        Reliability 30% — based on success_rate
        Consistency 10% — based on jitter (lower is better)
        Security    10% — based on dnssec_ok, malware_blocked, ads_blocked

    Returns:
        float in [0.0, 100.0]
    """
    # --- Speed (50 pts) ---
    if stats.median_ms is not None:
        # 0 ms → 100 pts, 500 ms → 0 pts, linear clamp
        speed_pts = max(0.0, 100.0 - (stats.median_ms / 500.0) * 100.0)
    else:
        speed_pts = 0.0
    speed_score = speed_pts * 0.50

    # --- Reliability (30 pts) ---
    reliability_score = stats.success_rate * 100.0 * 0.30

    # --- Consistency (10 pts) ---
    if stats.jitter_ms is not None:
        # 0 ms jitter → 100 pts, 200 ms jitter → 0 pts, linear clamp
        consistency_pts = max(0.0, 100.0 - (stats.jitter_ms / 200.0) * 100.0)
    else:
        consistency_pts = 0.0
    consistency_score = consistency_pts * 0.10

    # --- Security (10 pts) ---
    # dnssec_ok:        40% of security budget
    # malware_blocked:  40% of security budget
    # ads_blocked:      20% of security budget
    security_pts = (
        (40.0 if stats.dnssec_ok else 0.0)
        + (40.0 if stats.malware_blocked else 0.0)
        + (20.0 if stats.ads_blocked else 0.0)
    )
    security_score = security_pts * 0.10  # 0–10 pts

    total = speed_score + reliability_score + consistency_score + security_score
    return round(min(100.0, max(0.0, total)), 2)


# ---------------------------------------------------------------------------
# Per-server test
# ---------------------------------------------------------------------------


def test_server(
    server_dict: dict,
    n_queries: int = 10,
    timeout: float = 3.0,
    protocol: str = "udp",
) -> ServerStats:
    """
    Run a full benchmark for a single DNS server.

    Queries TEST_DOMAINS in round-robin order (up to *n_queries* total),
    measures latency statistics, performs security checks, and returns a
    populated :class:`ServerStats` instance.

    Args:
        server_dict: One entry from servers.SERVER_DB.
        n_queries:   Number of latency-measurement queries to send.
        timeout:     Per-query socket timeout in seconds.
        protocol:    "udp", "tcp", "dot", or "doh".

    Returns:
        ServerStats (score is computed and set before returning).
    """
    name = server_dict.get("name", "unknown")
    ip = server_dict.get("ip4") or server_dict.get("ip6", "")

    # --- Latency queries ---
    latencies: list[float] = []
    failed = 0

    domains_cycle = TEST_DOMAINS[:]
    # Only use domains that make sense for latency (skip the NXDOMAIN domain
    # since some resolvers may be slow on NXDOMAIN lookups in odd ways).
    measurement_domains = [d for d in domains_cycle if "xyzzy123" not in d]

    for i in range(n_queries):
        domain = measurement_domains[i % len(measurement_domains)]
        result = query_server(server_dict, domain, protocol=protocol, timeout=timeout)
        if result.success and result.latency_ms is not None:
            latencies.append(result.latency_ms)
        else:
            failed += 1

    total = n_queries
    success_rate = len(latencies) / total if total > 0 else 0.0

    # Compute latency stats
    if latencies:
        sorted_lat = sorted(latencies)
        min_ms = sorted_lat[0]
        max_ms = sorted_lat[-1]
        avg_ms = statistics.mean(latencies)
        median_ms = statistics.median(latencies)
        p95_ms = sorted_lat[min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)]
        jitter_ms = statistics.stdev(latencies) if len(latencies) > 1 else 0.0
    else:
        min_ms = avg_ms = median_ms = p95_ms = max_ms = jitter_ms = None

    # --- Security checks ---
    dnssec_ok = _check_dnssec(server_dict, protocol, timeout)
    malware_blocked = _check_malware_blocked(server_dict, protocol, timeout)
    ads_blocked = _check_ads_blocked(server_dict, protocol, timeout)

    stats = ServerStats(
        name=name,
        ip=ip,
        protocol=protocol,
        min_ms=min_ms,
        avg_ms=avg_ms,
        median_ms=median_ms,
        p95_ms=p95_ms,
        max_ms=max_ms,
        jitter_ms=jitter_ms,
        success_rate=success_rate,
        total_queries=total,
        failed_queries=failed,
        dnssec_ok=dnssec_ok,
        malware_blocked=malware_blocked,
        ads_blocked=ads_blocked,
        server_info=server_dict,
    )
    stats.score = score_server(stats)
    return stats


# ---------------------------------------------------------------------------
# Parallel benchmark runner
# ---------------------------------------------------------------------------


class AsyncBenchmark:
    """
    Runs benchmark tests against multiple DNS servers in parallel using
    a :class:`~concurrent.futures.ThreadPoolExecutor`.

    Usage::

        bench = AsyncBenchmark(max_workers=16)
        results = bench.run(servers.SERVER_DB[:10], n_queries=10)
    """

    def __init__(self, max_workers: int = 16) -> None:
        self.max_workers = max_workers

    def run(
        self,
        servers: list[dict],
        n_queries: int = 10,
        timeout: float = 3.0,
        protocol: str = "udp",
        progress_cb: Optional[Callable[[str, int, int], None]] = None,
    ) -> list[ServerStats]:
        """
        Benchmark *servers* in parallel.

        Args:
            servers:     List of server dicts (from servers.SERVER_DB).
            n_queries:   Queries per server for latency measurement.
            timeout:     Per-query timeout in seconds.
            protocol:    "udp", "tcp", "dot", or "doh".
            progress_cb: Optional callback called after each server completes,
                         signature: ``progress_cb(server_name, done, total)``.

        Returns:
            List of :class:`ServerStats`, sorted by score descending.
        """
        results: list[ServerStats] = []
        total = len(servers)
        done_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_to_server = {
                pool.submit(
                    test_server,
                    srv,
                    n_queries,
                    timeout,
                    protocol,
                ): srv
                for srv in servers
            }
            for future in as_completed(future_to_server):
                srv = future_to_server[future]
                done_count += 1
                try:
                    stats = future.result()
                except Exception as exc:
                    # Build a minimal failure record
                    stats = ServerStats(
                        name=srv.get("name", "unknown"),
                        ip=srv.get("ip4") or srv.get("ip6", ""),
                        protocol=protocol,
                        server_info=srv,
                    )
                    stats.score = 0.0
                if progress_cb is not None:
                    progress_cb(stats.name, done_count, total)
                results.append(stats)

        results.sort(key=lambda s: s.score, reverse=True)
        return results


# ---------------------------------------------------------------------------
# Top-level convenience function
# ---------------------------------------------------------------------------


def run_benchmark(
    servers: list[dict],
    n_queries: int = 10,
    timeout: float = 3.0,
    protocol: str = "udp",
    progress_cb: Optional[Callable[[str, int, int], None]] = None,
    max_workers: int = 16,
) -> list[ServerStats]:
    """
    Convenience wrapper: run a full benchmark and return results sorted by score.

    Args:
        servers:     List of server dicts.
        n_queries:   Queries per server for latency measurement.
        timeout:     Per-query socket timeout in seconds.
        protocol:    "udp", "tcp", "dot", or "doh".
        progress_cb: Optional callback ``(server_name, done, total) -> None``.
        max_workers: Thread-pool size.

    Returns:
        List of :class:`ServerStats`, sorted by score descending.
    """
    bench = AsyncBenchmark(max_workers=max_workers)
    return bench.run(
        servers,
        n_queries=n_queries,
        timeout=timeout,
        protocol=protocol,
        progress_cb=progress_cb,
    )


# ---------------------------------------------------------------------------
# System DNS detection
# ---------------------------------------------------------------------------


def detect_system_dns() -> list[str]:
    """
    Detect the system's configured DNS resolvers.

    Reads from:
    - Linux/BSD: ``/etc/resolv.conf``
    - macOS:     ``scutil --dns``
    - Windows:   ``netsh interface ip show dns``

    Returns:
        List of IP address strings (may be empty if none found).
    """
    system = platform.system()

    if system == "Linux" or system == "FreeBSD":
        return _detect_resolv_conf()
    elif system == "Darwin":
        return _detect_macos()
    elif system == "Windows":
        return _detect_windows()
    else:
        # Fallback: try resolv.conf
        return _detect_resolv_conf()


def _detect_resolv_conf(path: str = "/etc/resolv.conf") -> list[str]:
    """Parse nameserver lines from *path* (usually /etc/resolv.conf)."""
    servers: list[str] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        servers.append(parts[1])
    except OSError:
        pass
    return servers


def _detect_macos() -> list[str]:
    """Use ``scutil --dns`` to find DNS resolvers on macOS."""
    servers: list[str] = []
    try:
        out = subprocess.check_output(
            ["scutil", "--dns"], stderr=subprocess.DEVNULL, text=True, timeout=5
        )
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("nameserver["):
                # Format: nameserver[0] : 8.8.8.8
                parts = line.split(":")
                if len(parts) >= 2:
                    ip = parts[-1].strip()
                    if ip and ip not in servers:
                        servers.append(ip)
    except Exception:
        # Fall back to resolv.conf if scutil fails
        servers = _detect_resolv_conf()
    return servers


def _detect_windows() -> list[str]:
    """Use ``netsh interface ip show dns`` to find DNS resolvers on Windows."""
    servers: list[str] = []
    try:
        out = subprocess.check_output(
            ["netsh", "interface", "ip", "show", "dns"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        for line in out.splitlines():
            line = line.strip()
            # Lines like: "DNS Servers: 8.8.8.8" or "8.8.4.4"
            if "DNS Servers" in line or "Statically Configured DNS Servers" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    ip = parts[-1].strip()
                    if ip and ip not in servers:
                        servers.append(ip)
            else:
                # Continuation lines are just the IP
                parts = line.split()
                if len(parts) == 1:
                    candidate = parts[0]
                    # Rudimentary IP validation
                    if _looks_like_ip(candidate) and candidate not in servers:
                        servers.append(candidate)
    except Exception:
        pass
    return servers


def _looks_like_ip(s: str) -> bool:
    """Very lightweight check: does *s* look like an IPv4 or IPv6 address?"""
    try:
        socket.inet_pton(socket.AF_INET, s)
        return True
    except OSError:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, s)
        return True
    except OSError:
        pass
    return False
