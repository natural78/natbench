"""
natbench built-in resolver: UDP
==============================
Sends a raw DNS query over UDP (standard port 53).
"""

from __future__ import annotations

import socket
import struct
import time
from typing import Any

from natbench.plugin_base import QueryResult, ResolverPlugin
from natbench.core import build_dns_query, parse_dns_response

PLUGIN_INFO = {
    "name":        "UDP Resolver",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "NatBench contributors",
    "description": "Standard DNS-over-UDP (port 53)",
    "type":        "resolver",
    "protocol":    "udp",
    "requires":    [],
    "tags":        ["builtin", "standard"],
}

# DNS response flags: QR bit must be set in a valid response
_QR_BIT = 0x8000


class UdpResolver(ResolverPlugin):
    """DNS resolver using raw UDP datagrams."""

    protocol = "udp"

    def query(
        self,
        server: dict[str, Any],
        domain: str,
        qtype: str = "A",
        timeout: float = 2.0,
    ) -> QueryResult:
        """Send a single UDP DNS query and return the result."""
        try:
            ip = server.get("ip4") or server.get("ip6", "")
            if not ip:
                return QueryResult(
                    latency_ms=None, success=False, protocol="udp",
                    error="No IP address in server dict",
                )
            port = int(server.get("port", 53))

            qtype_int = _qtype_to_int(qtype)
            packet = build_dns_query(domain, qtype_int)

            family = socket.AF_INET6 if ":" in ip else socket.AF_INET
            with socket.socket(family, socket.SOCK_DGRAM) as sock:
                sock.settimeout(timeout)
                t0 = time.perf_counter()
                sock.sendto(packet, (ip, port))
                resp = sock.recv(4096)
                latency_ms = (time.perf_counter() - t0) * 1000.0

            rcode, answer_count = parse_dns_response(resp)
            # Accept NOERROR (0) and NXDOMAIN (3) as successful responses
            success = rcode in (0, 3) and len(resp) >= 12

            return QueryResult(
                latency_ms=latency_ms,
                success=success,
                rcode=rcode,
                answer_count=answer_count,
                protocol="udp",
            )

        except Exception as exc:
            return QueryResult(
                latency_ms=None,
                success=False,
                rcode=-1,
                answer_count=0,
                protocol="udp",
                error=str(exc),
            )

    def is_available(self, server: dict[str, Any]) -> bool:
        return bool(server.get("ip4") or server.get("ip6"))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_QTYPE_MAP: dict[str, int] = {
    "A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "MX": 15,
    "AAAA": 28, "SRV": 33, "ANY": 255,
}


def _qtype_to_int(qtype: str) -> int:
    return _QTYPE_MAP.get(qtype.upper(), 1)
