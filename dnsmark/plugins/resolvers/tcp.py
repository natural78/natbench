"""
dnsmark built-in resolver: TCP
==============================
Sends a DNS query over TCP with the RFC 1035 2-byte length prefix.
"""

from __future__ import annotations

import socket
import struct
import time
from typing import Any, Optional

from dnsmark.plugin_base import QueryResult, ResolverPlugin
from dnsmark.core import build_dns_query, parse_dns_response

PLUGIN_INFO = {
    "name":        "TCP Resolver",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "DNSMark contributors",
    "description": "DNS-over-TCP (port 53) — useful for large responses / DNSSEC",
    "type":        "resolver",
    "protocol":    "tcp",
    "requires":    [],
    "tags":        ["builtin", "standard"],
}

_QTYPE_MAP: dict[str, int] = {
    "A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "MX": 15,
    "AAAA": 28, "SRV": 33, "ANY": 255,
}


def _qtype_to_int(qtype: str) -> int:
    return _QTYPE_MAP.get(qtype.upper(), 1)


def _recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
    """Read exactly *n* bytes from *sock*, return None on EOF/error."""
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


class TcpResolver(ResolverPlugin):
    """DNS resolver using TCP with the standard 2-byte length-prefix framing."""

    protocol = "tcp"

    def query(
        self,
        server: dict[str, Any],
        domain: str,
        qtype: str = "A",
        timeout: float = 2.0,
    ) -> QueryResult:
        """Send a single TCP DNS query and return the result."""
        try:
            ip = server.get("ip4") or server.get("ip6", "")
            if not ip:
                return QueryResult(
                    latency_ms=None, success=False, protocol="tcp",
                    error="No IP address in server dict",
                )
            port = int(server.get("port", 53))

            qtype_int = _qtype_to_int(qtype)
            packet = build_dns_query(domain, qtype_int)
            # TCP DNS framing: 2-byte big-endian message length prefix
            framed = struct.pack("!H", len(packet)) + packet

            family = socket.AF_INET6 if ":" in ip else socket.AF_INET
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                t0 = time.perf_counter()
                sock.connect((ip, port))
                sock.sendall(framed)

                # Read the 2-byte response length
                raw_len = _recv_exact(sock, 2)
                if raw_len is None:
                    return QueryResult(
                        latency_ms=None, success=False, protocol="tcp",
                        error="Connection closed before length prefix",
                    )
                resp_len = struct.unpack("!H", raw_len)[0]
                resp = _recv_exact(sock, resp_len)
                latency_ms = (time.perf_counter() - t0) * 1000.0

            if resp is None:
                return QueryResult(
                    latency_ms=None, success=False, protocol="tcp",
                    error="Connection closed before full response received",
                )

            rcode, answer_count = parse_dns_response(resp)
            success = rcode in (0, 3) and len(resp) >= 12

            return QueryResult(
                latency_ms=latency_ms,
                success=success,
                rcode=rcode,
                answer_count=answer_count,
                protocol="tcp",
            )

        except Exception as exc:
            return QueryResult(
                latency_ms=None,
                success=False,
                rcode=-1,
                answer_count=0,
                protocol="tcp",
                error=str(exc),
            )

    def is_available(self, server: dict[str, Any]) -> bool:
        return bool(server.get("ip4") or server.get("ip6"))
