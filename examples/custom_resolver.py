"""
examples/custom_resolver.py
============================
Complete example of a custom DNS-over-QUIC (DoQ) resolver plugin for DNSMark.

DNS-over-QUIC (RFC 9250) requires the `aioquic` library. This example shows
the full plugin structure but returns a graceful "not installed" error since
aioquic is not a mandatory dependency.

INSTALLATION:
    pip install aioquic

USAGE:
    # Drop this file into your user plugin directory:
    mkdir -p ~/.dnsmark/plugins/resolvers/
    cp examples/custom_resolver.py ~/.dnsmark/plugins/resolvers/doq.py

    # Or set DNSMARK_PLUGIN_PATH:
    export DNSMARK_PLUGIN_PATH=/path/to/your/plugins

    # Then run DNSMark with the DoQ protocol:
    dnsmark --protocol doq

PLUGIN_INFO REFERENCE:
    - name:        Human-readable display name
    - version:     Your plugin's semver (independent of DNSMark version)
    - api_version: Must start with "1." for DNSMark 1.x
    - type:        Must be "resolver" for resolver plugins
    - protocol:    Registration key — used with --protocol flag
    - requires:    List of pip packages needed (informational only)
    - tags:        Optional metadata tags
"""

from __future__ import annotations

import time
from typing import Any

# DNSMark's ABC and result types
from dnsmark.plugin_base import QueryResult, ResolverPlugin

# Import core helpers if available (they build raw DNS packets)
try:
    from dnsmark.core import build_dns_query, parse_dns_response
    _HAS_CORE = True
except ImportError:
    _HAS_CORE = False

# Try to import aioquic for real DoQ support
try:
    import aioquic  # noqa: F401
    _HAS_AIOQUIC = True
except ImportError:
    _HAS_AIOQUIC = False


# ---------------------------------------------------------------------------
# Plugin manifest — REQUIRED at module level
# ---------------------------------------------------------------------------

PLUGIN_INFO = {
    "name":        "DoQ Resolver (example)",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "Your Name <you@example.com>",
    "description": "DNS-over-QUIC (RFC 9250) resolver — requires aioquic",
    "type":        "resolver",
    "protocol":    "doq",
    "requires":    ["aioquic>=0.9"],
    "tags":        ["encrypted", "quic", "experimental"],
}


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------

class DoQResolver(ResolverPlugin):
    """DNS-over-QUIC (DoQ) resolver.

    Sends DNS messages over QUIC connections to port 853.
    Requires aioquic to be installed.

    Server dict fields used:
        - doq_host (str): Hostname for DoQ server. Falls back to dot_host or ip4.
        - doq_port (int): Port number. Defaults to 853.
    """

    protocol = "doq"

    # Query type name → integer mapping
    _QTYPE_MAP = {
        "A": 1, "AAAA": 28, "MX": 15, "NS": 2,
        "CNAME": 5, "TXT": 16, "SOA": 6, "ANY": 255,
    }

    def query(
        self,
        server: dict[str, Any],
        domain:  str,
        qtype:   str = "A",
        timeout: float = 3.0,
    ) -> QueryResult:
        """Perform a DoQ query.

        NOTE: This example returns success=False with a helpful error message
        if aioquic is not installed. Replace the body with real aioquic code
        once you have the library installed.

        Returns
        -------
        QueryResult
            Always returns a result — never raises an exception.
        """
        # --- Safety check for missing dependency ---
        if not _HAS_AIOQUIC:
            return QueryResult(
                latency_ms=None,
                success=False,
                rcode=-1,
                protocol="doq",
                error=(
                    "aioquic is not installed. "
                    "Install it with: pip install aioquic"
                ),
            )

        # --- Real DoQ implementation would go here ---
        # Example skeleton (not functional without aioquic integration):
        #
        # try:
        #     host = server.get("doq_host") or server.get("dot_host") or server.get("ip4")
        #     port = int(server.get("doq_port", 853))
        #     qtype_int = self._QTYPE_MAP.get(qtype.upper(), 1)
        #     packet = build_dns_query(domain, qtype_int)
        #
        #     t0 = time.perf_counter()
        #     # ... aioquic connection and DNS message exchange ...
        #     latency_ms = (time.perf_counter() - t0) * 1000.0
        #
        #     rcode, answer_count = parse_dns_response(response_bytes)
        #     return QueryResult(
        #         latency_ms=latency_ms,
        #         success=rcode in (0, 3),
        #         rcode=rcode,
        #         answer_count=answer_count,
        #         protocol="doq",
        #     )
        # except Exception as exc:
        #     return QueryResult(
        #         latency_ms=None, success=False, rcode=-1,
        #         protocol="doq", error=str(exc),
        #     )

        # Placeholder: aioquic is installed but integration not yet implemented
        return QueryResult(
            latency_ms=None,
            success=False,
            rcode=-1,
            protocol="doq",
            error="DoQ implementation skeleton — replace with real aioquic code",
        )

    def is_available(self, server: dict[str, Any]) -> bool:
        """Return True if the server has a DoQ host and aioquic is installed."""
        if not _HAS_AIOQUIC:
            return False
        host = server.get("doq_host") or server.get("dot_host") or server.get("ip4")
        return bool(host)


# ---------------------------------------------------------------------------
# Quick smoke test (run directly: python examples/custom_resolver.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"PLUGIN_INFO: {PLUGIN_INFO['name']} v{PLUGIN_INFO['version']}")
    print(f"aioquic installed: {_HAS_AIOQUIC}")

    resolver = DoQResolver()
    print(f"Protocol: {resolver.protocol}")

    test_server = {
        "name": "Cloudflare DoQ",
        "ip4": "1.1.1.1",
        "dot_host": "one.one.one.one",
        "doq_host": "one.one.one.one",
        "doq_port": 853,
    }

    print(f"is_available: {resolver.is_available(test_server)}")
    result = resolver.query(test_server, "example.com")
    print(f"Result: success={result.success}, error={result.error!r}")
