"""
dnsmark built-in resolver: DNS-over-HTTPS (DoH)
================================================
Sends an RFC 8484 DoH POST request using stdlib urllib only (no requests dep).
Uses server["doh_url"] as the endpoint.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Any

from dnsmark.plugin_base import QueryResult, ResolverPlugin
from dnsmark.core import build_dns_query, parse_dns_response

PLUGIN_INFO = {
    "name":        "DoH Resolver",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "DNSMark contributors",
    "description": "DNS-over-HTTPS (RFC 8484) POST, stdlib only",
    "type":        "resolver",
    "protocol":    "doh",
    "requires":    [],
    "tags":        ["builtin", "encrypted", "privacy", "https"],
}

_QTYPE_MAP: dict[str, int] = {
    "A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "MX": 15,
    "AAAA": 28, "SRV": 33, "ANY": 255,
}

# RFC 8484 §4.1 content-type
_DOH_CONTENT_TYPE = "application/dns-message"


def _qtype_to_int(qtype: str) -> int:
    return _QTYPE_MAP.get(qtype.upper(), 1)


class DohResolver(ResolverPlugin):
    """DNS-over-HTTPS resolver (RFC 8484 POST mode)."""

    protocol = "doh"

    def query(
        self,
        server: dict[str, Any],
        domain: str,
        qtype: str = "A",
        timeout: float = 3.0,
    ) -> QueryResult:
        """Send a DoH query via HTTP POST and return the result. Never raises."""
        try:
            url = server.get("doh_url", "")
            if not url:
                return QueryResult(
                    latency_ms=None, success=False, protocol="doh",
                    error="No doh_url in server dict",
                )

            qtype_int = _qtype_to_int(qtype)
            dns_packet = build_dns_query(domain, qtype_int)

            req = urllib.request.Request(
                url,
                data=dns_packet,
                method="POST",
                headers={
                    "Content-Type": _DOH_CONTENT_TYPE,
                    "Accept":       _DOH_CONTENT_TYPE,
                    "User-Agent":   "DNSMark/1.0",
                    "Content-Length": str(len(dns_packet)),
                },
            )

            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    body = resp.read()
                    latency_ms = (time.perf_counter() - t0) * 1000.0
                    http_status = resp.status
            except urllib.error.HTTPError as http_err:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                return QueryResult(
                    latency_ms=latency_ms,
                    success=False,
                    rcode=-1,
                    protocol="doh",
                    error=f"HTTP {http_err.code}: {http_err.reason}",
                )

            if http_status != 200:
                return QueryResult(
                    latency_ms=latency_ms,
                    success=False,
                    rcode=-1,
                    protocol="doh",
                    error=f"HTTP status {http_status}",
                )

            if not body:
                return QueryResult(
                    latency_ms=latency_ms,
                    success=False,
                    rcode=-1,
                    protocol="doh",
                    error="Empty response body",
                )

            rcode, answer_count = parse_dns_response(body)
            success = rcode in (0, 3) and len(body) >= 12

            return QueryResult(
                latency_ms=latency_ms,
                success=success,
                rcode=rcode,
                answer_count=answer_count,
                protocol="doh",
            )

        except Exception as exc:
            return QueryResult(
                latency_ms=None,
                success=False,
                rcode=-1,
                answer_count=0,
                protocol="doh",
                error=str(exc),
            )

    def is_available(self, server: dict[str, Any]) -> bool:
        return bool(server.get("doh_url"))
