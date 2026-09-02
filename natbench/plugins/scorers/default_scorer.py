"""
natbench built-in scorer: Default (Balanced)
============================================
Weighted composite score:
  50% speed (based on median latency)
  30% reliability (success rate)
  10% consistency (jitter / latency stability)
  10% security (DNSSEC + malware blocking + ad blocking)
"""

from __future__ import annotations

from natbench.plugin_base import ScorerPlugin, ServerStats

PLUGIN_INFO = {
    "name":        "Default Scorer",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "NatBench contributors",
    "description": "Balanced scorer: 50% speed, 30% reliability, 10% consistency, 10% security",
    "type":        "scorer",
    "scorer_id":   "default",
    "requires":    [],
    "tags":        ["builtin"],
}

# ---------------------------------------------------------------------------
# Latency breakpoints for the speed component.
# Format: (latency_ms, score_at_that_latency)
# Linear interpolation is used between adjacent breakpoints.
# ---------------------------------------------------------------------------
_SPEED_BREAKPOINTS: list[tuple[float, float]] = [
    (0.0,    100.0),
    (10.0,    95.0),
    (50.0,    80.0),
    (100.0,   60.0),
    (200.0,   35.0),
    (500.0,   10.0),
    (1000.0,   0.0),
]

# Jitter breakpoints for the consistency component
_JITTER_BREAKPOINTS: list[tuple[float, float]] = [
    (0.0,   100.0),
    (5.0,    95.0),
    (20.0,   80.0),
    (50.0,   50.0),
    (100.0,  20.0),
    (200.0,   0.0),
]


def _interpolate(breakpoints: list[tuple[float, float]], value: float) -> float:
    """Linearly interpolate *value* over the given (x, y) breakpoints."""
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


class DefaultScorer(ScorerPlugin):
    """Balanced scorer: speed 50%, reliability 30%, consistency 10%, security 10%."""

    scorer_id   = "default"
    scorer_name = "Balanced (Speed+Reliability+Consistency+Security)"

    def score(self, stats: ServerStats) -> float:
        """Compute weighted composite score in [0.0, 100.0]."""
        # --- Speed component (50%) ---
        median = stats.median_ms
        if median is None:
            speed_score = 0.0
        else:
            speed_score = _interpolate(_SPEED_BREAKPOINTS, median)

        # --- Reliability component (30%) ---
        reliability_score = stats.success_rate * 100.0

        # --- Consistency component (10%) ---
        jitter = stats.jitter_ms
        if jitter is None:
            # If no jitter data but queries were successful, assume moderate
            consistency_score = 50.0 if stats.success_rate > 0 else 0.0
        else:
            consistency_score = _interpolate(_JITTER_BREAKPOINTS, jitter)

        # --- Security component (10%) ---
        # dnssec_ok = 50pts, malware_blocked = 30pts, ads_blocked = 20pts
        security_score = 0.0
        if stats.dnssec_ok is True:
            security_score += 50.0
        if stats.malware_blocked is True:
            security_score += 30.0
        if stats.ads_blocked is True:
            security_score += 20.0
        # If security tests were not run (all None), give neutral 50pts
        if stats.dnssec_ok is None and stats.malware_blocked is None and stats.ads_blocked is None:
            security_score = 50.0

        # --- Weighted sum ---
        composite = (
            0.50 * speed_score
            + 0.30 * reliability_score
            + 0.10 * consistency_score
            + 0.10 * security_score
        )
        return max(0.0, min(100.0, composite))

    def describe(self) -> str:
        return (
            "Balanced scorer: 50% latency speed, 30% success reliability, "
            "10% jitter consistency, 10% security features (DNSSEC/malware/ads)."
        )

    def weights(self) -> dict[str, float]:
        return {
            "speed":       0.50,
            "reliability": 0.30,
            "consistency": 0.10,
            "security":    0.10,
        }
