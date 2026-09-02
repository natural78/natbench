"""
pytest fixtures shared across the NatBench test suite.
"""

from __future__ import annotations

import pytest

from natbench.plugin_base import QueryResult, ServerStats


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_server() -> dict:
    """A minimal server dict compatible with SERVER_DB entries."""
    return {
        "name":     "Test Server",
        "ip4":      "1.1.1.1",
        "ip6":      "2606:4700:4700::1111",
        "port":     53,
        "doh_url":  "https://cloudflare-dns.com/dns-query",
        "dot_host": "one.one.one.one",
        "dot_port": 853,
        "country":  "US",
        "operator": "Cloudflare",
        "tags":     ["fast", "anycast", "no_log"],
        "protocol": "udp",
    }


@pytest.fixture
def sample_query_result() -> QueryResult:
    """A successful QueryResult with realistic values."""
    return QueryResult(
        latency_ms=12.5,
        success=True,
        rcode=0,
        answer_count=1,
        protocol="udp",
    )


@pytest.fixture
def sample_server_stats(sample_server, sample_query_result) -> ServerStats:
    """A ServerStats object populated with realistic benchmark data."""
    queries = [
        QueryResult(latency_ms=10.0, success=True, rcode=0, answer_count=1, protocol="udp"),
        QueryResult(latency_ms=12.5, success=True, rcode=0, answer_count=1, protocol="udp"),
        QueryResult(latency_ms=11.0, success=True, rcode=0, answer_count=1, protocol="udp"),
        QueryResult(latency_ms=13.0, success=True, rcode=0, answer_count=1, protocol="udp"),
        QueryResult(latency_ms=None,  success=False, rcode=-1, protocol="udp", error="timeout"),
    ]
    latencies = [q.latency_ms for q in queries if q.latency_ms is not None]
    import statistics

    return ServerStats(
        server=sample_server,
        queries=queries,
        score=82.5,
        dnssec_ok=True,
        malware_blocked=False,
        ads_blocked=None,
        avg_ms=statistics.mean(latencies),
        median_ms=statistics.median(latencies),
        p95_ms=sorted(latencies)[int(len(latencies) * 0.95)],
        min_ms=min(latencies),
        max_ms=max(latencies),
        jitter_ms=statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
        success_rate=4 / 5,
    )
