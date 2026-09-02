"""
natbench built-in exporter: JSON
================================
Exports benchmark results to a JSON file (indent=2, UTF-8).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from natbench.plugin_base import ExporterPlugin, ServerStats

PLUGIN_INFO = {
    "name":        "JSON Exporter",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "NatBench contributors",
    "description": "Export results to a JSON file",
    "type":        "exporter",
    "format":      "json",
    "requires":    [],
    "tags":        ["builtin"],
}


def _stats_to_dict(rank: int, s: ServerStats) -> dict[str, Any]:
    """Serialise a single ServerStats to a plain dict."""
    srv = s.server
    return {
        "rank":            rank,
        "name":            srv.get("name", "Unknown"),
        "ip4":             srv.get("ip4", ""),
        "ip6":             srv.get("ip6", ""),
        "country":         srv.get("country", ""),
        "operator":        srv.get("operator", ""),
        "tags":            srv.get("tags", []),
        "score":           round(s.score, 2),
        "avg_ms":          round(s.avg_ms, 3) if s.avg_ms is not None else None,
        "median_ms":       round(s.median_ms, 3) if s.median_ms is not None else None,
        "p95_ms":          round(s.p95_ms, 3) if s.p95_ms is not None else None,
        "min_ms":          round(s.min_ms, 3) if s.min_ms is not None else None,
        "max_ms":          round(s.max_ms, 3) if s.max_ms is not None else None,
        "jitter_ms":       round(s.jitter_ms, 3) if s.jitter_ms is not None else None,
        "success_rate":    round(s.success_rate, 4),
        "dnssec_ok":       s.dnssec_ok,
        "malware_blocked": s.malware_blocked,
        "ads_blocked":     s.ads_blocked,
        "protocol":        srv.get("protocol", "udp"),
        "total_queries":   getattr(s, "total_queries", len(s.queries)),
        "failed_queries":  getattr(s, "failed_queries",
                                   sum(1 for q in s.queries if not q.success)),
    }


class JsonExporter(ExporterPlugin):
    """Export benchmark results to JSON (indent=2, UTF-8)."""

    format         = "json"
    file_extension = ".json"

    def export(
        self,
        results:  list[ServerStats],
        filepath: str,
        *,
        lang:  str = "en",
        meta:  Optional[dict[str, Any]] = None,
    ) -> bool:
        """Write *results* to *filepath* as pretty-printed JSON."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        meta = meta or {}
        timestamp_iso = datetime.now(tz=timezone.utc).isoformat()

        doc = {
            "meta": {
                "generated_at":   timestamp_iso,
                "tool":           "NatBench",
                "tool_version":   _get_version(),
                "lang":           lang,
                "server_count":   len(results),
                **meta,
            },
            "servers": [_stats_to_dict(rank + 1, s) for rank, s in enumerate(results)],
        }

        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)

        return True

    def preview(
        self,
        results:  list[ServerStats],
        max_rows: int = 10,
        lang:     str = "en",
    ) -> str:
        rows = results[:max_rows]
        preview_doc = {
            "servers": [_stats_to_dict(i + 1, s) for i, s in enumerate(rows)],
        }
        return json.dumps(preview_doc, indent=2, ensure_ascii=False)


def _get_version() -> str:
    try:
        from natbench.__version__ import __version__
        return __version__
    except Exception:
        return "unknown"
