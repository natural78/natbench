"""
dnsmark built-in exporter: CSV
================================
Exports benchmark results to a CSV file using csv.DictWriter.
"""

from __future__ import annotations

import csv
import os
from typing import Any, Optional

from dnsmark.plugin_base import ExporterPlugin, ServerStats

PLUGIN_INFO = {
    "name":        "CSV Exporter",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "DNSMark contributors",
    "description": "Export results to a CSV file",
    "type":        "exporter",
    "format":      "csv",
    "requires":    [],
    "tags":        ["builtin"],
}

_COLUMNS = [
    "rank",
    "name",
    "score",
    "avg_ms",
    "median_ms",
    "p95_ms",
    "min_ms",
    "max_ms",
    "jitter_ms",
    "success_rate",
    "dnssec_ok",
    "malware_blocked",
    "ads_blocked",
    "protocol",
    "ip4",
    "ip6",
    "country",
    "operator",
]


def _bool_str(v: Optional[bool]) -> str:
    if v is None:
        return ""
    return "yes" if v else "no"


def _round_or_empty(v: Optional[float], ndigits: int = 3) -> str:
    if v is None:
        return ""
    return str(round(v, ndigits))


def _stats_to_row(rank: int, s: ServerStats) -> dict[str, str]:
    srv = s.server
    return {
        "rank":            str(rank),
        "name":            srv.get("name", ""),
        "score":           _round_or_empty(s.score, 2),
        "avg_ms":          _round_or_empty(s.avg_ms),
        "median_ms":       _round_or_empty(s.median_ms),
        "p95_ms":          _round_or_empty(s.p95_ms),
        "min_ms":          _round_or_empty(s.min_ms),
        "max_ms":          _round_or_empty(s.max_ms),
        "jitter_ms":       _round_or_empty(s.jitter_ms),
        "success_rate":    _round_or_empty(s.success_rate, 4),
        "dnssec_ok":       _bool_str(s.dnssec_ok),
        "malware_blocked": _bool_str(s.malware_blocked),
        "ads_blocked":     _bool_str(s.ads_blocked),
        "protocol":        srv.get("protocol", "udp"),
        "ip4":             srv.get("ip4", ""),
        "ip6":             srv.get("ip6", ""),
        "country":         srv.get("country", ""),
        "operator":        srv.get("operator", ""),
    }


class CsvExporter(ExporterPlugin):
    """Export benchmark results to a CSV file."""

    format         = "csv"
    file_extension = ".csv"

    def export(
        self,
        results:  list[ServerStats],
        filepath: str,
        *,
        lang:  str = "en",
        meta:  Optional[dict[str, Any]] = None,
    ) -> bool:
        """Write *results* to *filepath* as CSV."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        with open(filepath, "w", encoding="utf-8", newline="") as fh:
            # Write metadata as comment lines at the top
            if meta:
                for k, v in meta.items():
                    fh.write(f"# {k}: {v}\n")

            writer = csv.DictWriter(fh, fieldnames=_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for rank, s in enumerate(results, start=1):
                writer.writerow(_stats_to_row(rank, s))

        return True

    def preview(
        self,
        results:  list[ServerStats],
        max_rows: int = 10,
        lang:     str = "en",
    ) -> str:
        import io
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for rank, s in enumerate(results[:max_rows], start=1):
            writer.writerow(_stats_to_row(rank, s))
        return buf.getvalue()
