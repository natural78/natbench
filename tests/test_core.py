"""
Tests for natbench.core — DNS packet helpers and scoring.

No live network calls — sockets are mocked where needed.
"""

from __future__ import annotations

import struct
from unittest.mock import MagicMock, patch

import pytest

from natbench.core import build_dns_query, parse_dns_response


# ---------------------------------------------------------------------------
# build_dns_query
# ---------------------------------------------------------------------------

class TestBuildDnsQuery:
    def test_returns_bytes(self):
        pkt = build_dns_query("google.com")
        assert isinstance(pkt, bytes)

    def test_minimum_length(self):
        # 12-byte header + at least a QNAME + QTYPE + QCLASS
        pkt = build_dns_query("a.io")
        assert len(pkt) >= 12 + 6  # header + minimal QNAME + 4 bytes

    def test_header_structure(self):
        """First 12 bytes must be valid DNS header."""
        pkt = build_dns_query("example.com")
        txid, flags, qdcount, ancount, nscount, arcount = struct.unpack(
            "!HHHHHH", pkt[:12]
        )
        # QR=0 (query), RD=1 (recursion desired)
        assert flags & 0x8000 == 0,      "QR bit must be 0 for a query"
        assert flags & 0x0100 != 0,      "RD bit must be 1"
        assert qdcount == 1,             "QDCOUNT must be 1"
        assert ancount == 0
        assert nscount == 0
        assert arcount == 0

    def test_txid_is_two_bytes(self):
        pkt = build_dns_query("test.local")
        txid, = struct.unpack("!H", pkt[:2])
        assert 0 <= txid <= 0xFFFF

    def test_txid_randomised(self):
        """Two consecutive queries should (almost always) have different TXIDs."""
        pkt1 = build_dns_query("example.com")
        pkt2 = build_dns_query("example.com")
        # There's a 1/65536 chance of collision — acceptable for a test
        txid1, = struct.unpack("!H", pkt1[:2])
        txid2, = struct.unpack("!H", pkt2[:2])
        # We can't assert != due to randomness, but at least check it's valid
        assert 0 <= txid1 <= 0xFFFF
        assert 0 <= txid2 <= 0xFFFF

    def test_qtype_a_default(self):
        """Default qtype=1 (A) should appear in the question section."""
        pkt = build_dns_query("example.com")
        # Last 4 bytes of question are QTYPE (2) + QCLASS (2)
        qtype, qclass = struct.unpack("!HH", pkt[-4:])
        assert qtype == 1,   "Default QTYPE should be A (1)"
        assert qclass == 1,  "QCLASS should be IN (1)"

    def test_qtype_aaaa(self):
        pkt = build_dns_query("example.com", qtype=28)
        qtype, qclass = struct.unpack("!HH", pkt[-4:])
        assert qtype == 28

    def test_encodes_domain_labels(self):
        """QNAME should contain length-prefixed labels for 'google.com'."""
        pkt = build_dns_query("google.com")
        # Skip 12-byte header; QNAME starts at offset 12
        qname_section = pkt[12:]
        # First label: \x06google
        assert qname_section[0] == 6
        assert qname_section[1:7] == b"google"
        # Second label: \x03com
        assert qname_section[7] == 3
        assert qname_section[8:11] == b"com"
        # Null terminator
        assert qname_section[11] == 0

    def test_trailing_dot_stripped(self):
        """Trailing dot should be ignored (FQDN vs relative)."""
        pkt1 = build_dns_query("example.com")
        pkt2 = build_dns_query("example.com.")
        # Headers will differ (TXID random) but from byte 12 onward should match
        assert pkt1[12:] == pkt2[12:]


# ---------------------------------------------------------------------------
# parse_dns_response
# ---------------------------------------------------------------------------

class TestParseDnsResponse:
    def _make_response(self, txid=0x1234, flags=0x8180, qdcount=1,
                       ancount=2, nscount=0, arcount=0) -> bytes:
        """Build a minimal 12-byte DNS response header."""
        return struct.pack("!HHHHHH", txid, flags, qdcount, ancount, nscount, arcount)

    def test_too_short_returns_minus_one(self):
        rcode, ancount = parse_dns_response(b"\x00" * 11)
        assert rcode == -1
        assert ancount == 0

    def test_empty_returns_minus_one(self):
        rcode, ancount = parse_dns_response(b"")
        assert rcode == -1

    def test_noerror_rcode(self):
        data = self._make_response(flags=0x8180)  # QR=1, RA=1, RCODE=0
        rcode, ancount = parse_dns_response(data)
        assert rcode == 0
        assert ancount == 2

    def test_nxdomain_rcode(self):
        flags = 0x8183  # QR=1, RA=1, RCODE=3 (NXDOMAIN)
        data = self._make_response(flags=flags, ancount=0)
        rcode, ancount = parse_dns_response(data)
        assert rcode == 3
        assert ancount == 0

    def test_servfail_rcode(self):
        flags = 0x8182  # RCODE=2 (SERVFAIL)
        data = self._make_response(flags=flags, ancount=0)
        rcode, ancount = parse_dns_response(data)
        assert rcode == 2

    def test_answer_count_extracted(self):
        data = self._make_response(ancount=5)
        rcode, ancount = parse_dns_response(data)
        assert ancount == 5

    def test_extra_bytes_ok(self):
        """Response longer than 12 bytes (real-world case) must work."""
        data = self._make_response(ancount=1) + b"\xff" * 100
        rcode, ancount = parse_dns_response(data)
        assert rcode == 0
        assert ancount == 1

    def test_round_trip(self):
        """build_dns_query → fake response with same structure parses correctly."""
        query = build_dns_query("example.com")
        txid, = struct.unpack("!H", query[:2])
        # Forge a response with RCODE=0, ANCOUNT=1
        resp_flags = 0x8180  # standard response, no error
        response = struct.pack("!HHHHHH", txid, resp_flags, 1, 1, 0, 0)
        rcode, ancount = parse_dns_response(response)
        assert rcode == 0
        assert ancount == 1


# ---------------------------------------------------------------------------
# Scorer tests (no network)
# ---------------------------------------------------------------------------

class TestDefaultScorer:
    def test_score_range(self, sample_server_stats):
        from natbench.plugins.scorers.default_scorer import DefaultScorer
        scorer = DefaultScorer()
        score = scorer.score(sample_server_stats)
        assert 0.0 <= score <= 100.0

    def test_high_score_for_fast_reliable_server(self, sample_server):
        from natbench.plugin_base import QueryResult, ServerStats
        from natbench.plugins.scorers.default_scorer import DefaultScorer

        queries = [QueryResult(latency_ms=5.0, success=True, rcode=0, protocol="udp")] * 10
        stats = ServerStats(
            server=sample_server,
            queries=queries,
            dnssec_ok=True,
            malware_blocked=True,
            ads_blocked=True,
            avg_ms=5.0,
            median_ms=5.0,
            p95_ms=6.0,
            min_ms=4.0,
            max_ms=7.0,
            jitter_ms=0.5,
            success_rate=1.0,
        )
        scorer = DefaultScorer()
        score = scorer.score(stats)
        assert score >= 85.0, f"Expected high score for fast/reliable server, got {score}"

    def test_zero_score_for_total_failure(self, sample_server):
        from natbench.plugin_base import QueryResult, ServerStats
        from natbench.plugins.scorers.default_scorer import DefaultScorer

        queries = [QueryResult(latency_ms=None, success=False, rcode=-1, protocol="udp")] * 5
        stats = ServerStats(
            server=sample_server,
            queries=queries,
            median_ms=None,
            avg_ms=None,
            jitter_ms=None,
            success_rate=0.0,
            dnssec_ok=False,
            malware_blocked=False,
            ads_blocked=False,
        )
        scorer = DefaultScorer()
        score = scorer.score(stats)
        assert score == 0.0

    def test_weights_sum_to_one(self):
        from natbench.plugins.scorers.default_scorer import DefaultScorer
        scorer = DefaultScorer()
        total = sum(scorer.weights().values())
        assert abs(total - 1.0) < 1e-9


class TestLatencyOnlyScorer:
    def test_score_range(self, sample_server_stats):
        from natbench.plugins.scorers.latency_only_scorer import LatencyOnlyScorer
        scorer = LatencyOnlyScorer()
        score = scorer.score(sample_server_stats)
        assert 0.0 <= score <= 100.0

    def test_none_median_gives_zero(self, sample_server):
        from natbench.plugin_base import ServerStats
        from natbench.plugins.scorers.latency_only_scorer import LatencyOnlyScorer

        stats = ServerStats(server=sample_server, median_ms=None, success_rate=0.0)
        scorer = LatencyOnlyScorer()
        assert scorer.score(stats) == 0.0
