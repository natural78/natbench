"""
natbench built-in resolver: DNS-over-TLS (DoT)
==============================================
Sends a length-prefixed DNS query over a TLS-wrapped TCP connection.
Connects to server["dot_host"] on port 853 (or server["dot_port"]).
"""

from __future__ import annotations

import socket
import ssl
import struct
import time
from typing import Any, Optional

from natbench.plugin_base import QueryResult, ResolverPlugin
from natbench.core import build_dns_query, parse_dns_response

PLUGIN_INFO = {
    "name":        "DoT Resolver",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "NatBench contributors",
    "description": "DNS-over-TLS (RFC 7858), port 853",
    "type":        "resolver",
    "protocol":    "dot",
    "requires":    [],
    "tags":        ["builtin", "encrypted", "privacy"],
}

_QTYPE_MAP: dict[str, int] = {
    "A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "MX": 15,
    "AAAA": 28, "SRV": 33, "ANY": 255,
}


def _qtype_to_int(qtype: str) -> int:
    return _QTYPE_MAP.get(qtype.upper(), 1)


def _recv_exact(sock: ssl.SSLSocket, n: int) -> Optional[bytes]:
    """Read exactly *n* bytes from an SSL socket. Returns None on failure."""
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


class DotResolver(ResolverPlugin):
    """DNS-over-TLS resolver (RFC 7858)."""

    protocol = "dot"

    def query(
        self,
        server: dict[str, Any],
        domain: str,
        qtype: str = "A",
        timeout: float = 3.0,
    ) -> QueryResult:
        """Send a DoT query and return the result. Never raises."""
        try:
            host = server.get("dot_host", "")
            if not host:
                # Fall back to ip4 if no dedicated dot_host
                host = server.get("ip4", "")
            if not host:
                return QueryResult(
                    latency_ms=None, success=False, protocol="dot",
                    error="No dot_host or ip4 in server dict",
                )
            port = int(server.get("dot_port", 853))

            qtype_int = _qtype_to_int(qtype)
            packet = build_dns_query(domain, qtype_int)
            framed = struct.pack("!H", len(packet)) + packet

            ctx = ssl.create_default_context()
            # Allow TLS 1.2+ only
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2

            # Use raw socket so we can set timeout before TLS handshake
            family = socket.AF_INET6 if ":" in host else socket.AF_INET
            raw_sock = socket.socket(family, socket.SOCK_STREAM)
            raw_sock.settimeout(timeout)

            t0 = time.perf_counter()
            try:
                raw_sock.connect((host, port))
                # server_hostname is needed for SNI and cert verification
                # If host is a bare IP, cert verification may fail — catch and retry
                try:
                    tls_sock = ctx.wrap_socket(raw_sock, server_hostname=host)
                except ssl.CertificateError:
                    # Some servers use IP-only certs; try without verification
                    raw_sock.close()
                    raw_sock = socket.socket(family, socket.SOCK_STREAM)
                    raw_sock.settimeout(timeout)
                    raw_sock.connect((host, port))
                    ctx_noverify = ssl.create_default_context()
                    ctx_noverify.check_hostname = False
                    ctx_noverify.verify_mode = ssl.CERT_NONE
                    tls_sock = ctx_noverify.wrap_socket(raw_sock, server_hostname=None)

                try:
                    tls_sock.sendall(framed)
                    raw_len = _recv_exact(tls_sock, 2)
                    if raw_len is None:
                        return QueryResult(
                            latency_ms=None, success=False, protocol="dot",
                            error="No response length prefix received",
                        )
                    resp_len = struct.unpack("!H", raw_len)[0]
                    resp = _recv_exact(tls_sock, resp_len)
                    latency_ms = (time.perf_counter() - t0) * 1000.0
                finally:
                    tls_sock.close()

            finally:
                raw_sock.close()

            if resp is None:
                return QueryResult(
                    latency_ms=None, success=False, protocol="dot",
                    error="Incomplete response received",
                )

            rcode, answer_count = parse_dns_response(resp)
            success = rcode in (0, 3) and len(resp) >= 12

            return QueryResult(
                latency_ms=latency_ms,
                success=success,
                rcode=rcode,
                answer_count=answer_count,
                protocol="dot",
            )

        except Exception as exc:
            return QueryResult(
                latency_ms=None,
                success=False,
                rcode=-1,
                answer_count=0,
                protocol="dot",
                error=str(exc),
            )

    def is_available(self, server: dict[str, Any]) -> bool:
        return bool(server.get("dot_host") or server.get("ip4"))
