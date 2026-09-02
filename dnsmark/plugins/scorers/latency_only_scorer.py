"""
dnsmark built-in scorer: Latency Only
=======================================
Scores servers purely on median latency. Ignores reliability, security.
Useful when you only care about raw DNS lookup speed.
"""

from __future__ import annotations

from dnsmark.plugin_base import ScorerPlugin, ServerStats

PLUGIN_INFO = {
    "name":        "Latency Only Scorer",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "DNSMark contributors",
    "description": "Score based purely on median latency — fastest = best",
    "type":        "scorer",
    "scorer_id":   "latency_only",
    "requires":    [],
    "tags":        ["builtin"],
}

# Same breakpoints as the speed component in default_scorer
_SPEED_BREAKPOINTS: list[tuple[float, float]] = [
    (0.0,    100.0),
    (10.0,    95.0),
    (50.0,    80.0),
    (100.0,   60.0),
    (200.0,   35.0),
    (500.0,   10.0),
    (1000.0,   0.0),
]


def _interpolate(breakpoints: list[tuple[float, float]], value: float) -> float:
    if value <= breakpoints[0][0]:
        return breakpoints[0][1]
    if value >= breakpoints[-1][0]:
        return breakpoints[-1][1]
    for i in range(len(breakpoints) - 1):
        x0, y0 = breakpoints[i]
        x1, y1 = breakpoints[i + 1]
        if x0 <= value <= x1:
            if x1 == x0:
                return y0
            t = (value - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return breakpoints[-1][1]


class LatencyOnlyScorer(ScorerPlugin):
    """Score servers based solely on median latency."""

    scorer_id   = "latency_only"
    scorer_name = "Latency Only"

    def score(self, stats: ServerStats) -> float:
        """Return a pure speed score in [0.0, 100.0] based on median_ms."""
        median = stats.median_ms
        if median is None:
            # No successful queries
            return 0.0
        raw = _interpolate(_SPEED_BREAKPOINTS, median)
        return max(0.0, min(100.0, raw))

    def describe(self) -> str:
        return "Latency-only scorer: score is derived entirely from median response time."

    def weights(self) -> dict[str, float]:
        return {"speed": 1.0}
