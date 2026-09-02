"""
examples/custom_exporter.py
============================
Complete example of a custom YAML exporter plugin for NatBench.

This example uses basic manual YAML serialisation so it works without any
third-party dependencies. For production use, you may want to replace the
manual serialisation with pyyaml:

    pip install pyyaml

    import yaml
    with open(filepath, "w") as fh:
        yaml.dump(doc, fh, allow_unicode=True, default_flow_style=False)

INSTALLATION:
    mkdir -p ~/.natbench/plugins/exporters/
    cp examples/custom_exporter.py ~/.natbench/plugins/exporters/yaml_exporter.py

    # Then export results:
    natbench --export-format yaml --output results.yaml

PLUGIN_INFO REFERENCE:
    - type:           Must be "exporter"
    - format:         Registration key, used with --export-format flag
    - file_extension: Default output file extension (including the dot)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from natbench.plugin_base import ExporterPlugin, ServerStats

# Try to import pyyaml if available; fall back to manual serialisation
try:
    import yaml as _yaml
    _HAS_PYYAML = True
except ImportError:
    _HAS_PYYAML = False


# ---------------------------------------------------------------------------
# Plugin manifest
# ---------------------------------------------------------------------------

PLUGIN_INFO = {
    "name":        "YAML Exporter (example)",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "Your Name <you@example.com>",
    "description": "Export DNS benchmark results to YAML. Optionally uses pyyaml.",
    "type":        "exporter",
    "format":      "yaml",
    "requires":    [],            # pyyaml is optional; falls back to manual YAML
    "tags":        ["yaml", "text"],
}


# ---------------------------------------------------------------------------
# Manual YAML serialisation helpers (stdlib-only fallback)
# ---------------------------------------------------------------------------

def _indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.splitlines())


def _yaml_value(value: object, indent: int = 0) -> str:
    """Serialise a Python value to a YAML-compatible string."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        items = "\n".join(
            _indent(f"- {_yaml_value(v)}", indent) for v in value
        )
        return "\n" + items
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = []
        for k, v in value.items():
            v_str = _yaml_value(v, indent + 2)
            if "\n" in v_str:
                lines.append(f"{' ' * indent}{k}:{v_str}")
            else:
                lines.append(f"{' ' * indent}{k}: {v_str}")
        return "\n" + "\n".join(lines)
    # String: quote if it contains special chars
    s = str(value)
    if any(c in s for c in ":#{}[]|>&*!,"):
        s = s.replace('"', '\\"')
        return f'"{s}"'
    return s


def _serialise_yaml(doc: dict) -> str:
    """Serialise a nested dict to a YAML string (manual, no deps)."""
    lines = ["---"]
    for key, value in doc.items():
        v_str = _yaml_value(value, indent=2)
        if v_str.startswith("\n"):
            lines.append(f"{key}:{v_str}")
        else:
            lines.append(f"{key}: {v_str}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------

class YamlExporter(ExporterPlugin):
    """Export benchmark results to YAML.

    Uses pyyaml if installed, otherwise falls back to a simple manual
    YAML serialiser that handles the basic types used by NatBench.
    """

    format         = "yaml"
    file_extension = ".yaml"

    def export(
        self,
        results:  list[ServerStats],
        filepath: str,
        *,
        lang:  str = "en",
        meta:  Optional[dict[str, Any]] = None,
    ) -> bool:
        """Serialise *results* to a YAML file at *filepath*."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        ts = datetime.now(tz=timezone.utc).isoformat()
        doc = {
            "meta": {
                "generated_at": ts,
                "tool":         "NatBench",
                "lang":         lang,
                "server_count": len(results),
                **(meta or {}),
            },
            "servers": [self._server_to_dict(rank + 1, s)
                        for rank, s in enumerate(results)],
        }

        if _HAS_PYYAML:
            content = _yaml.dump(doc, allow_unicode=True, default_flow_style=False,
                                 sort_keys=False)
            content = "---\n" + content
        else:
            content = _serialise_yaml(doc)

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(content)

        return True

    def preview(
        self,
        results:  list[ServerStats],
        max_rows: int = 5,
        lang:     str = "en",
    ) -> str:
        rows = [self._server_to_dict(i + 1, s) for i, s in enumerate(results[:max_rows])]
        if _HAS_PYYAML:
            return _yaml.dump({"servers": rows}, allow_unicode=True, default_flow_style=False)
        return _serialise_yaml({"servers": rows})

    @staticmethod
    def _server_to_dict(rank: int, s: ServerStats) -> dict[str, Any]:
        srv = s.server
        return {
            "rank":            rank,
            "name":            srv.get("name", ""),
            "ip4":             srv.get("ip4", ""),
            "score":           round(s.score, 2),
            "avg_ms":          round(s.avg_ms, 2) if s.avg_ms is not None else None,
            "median_ms":       round(s.median_ms, 2) if s.median_ms is not None else None,
            "p95_ms":          round(s.p95_ms, 2) if s.p95_ms is not None else None,
            "jitter_ms":       round(s.jitter_ms, 2) if s.jitter_ms is not None else None,
            "success_rate":    round(s.success_rate, 4),
            "dnssec_ok":       s.dnssec_ok,
            "malware_blocked": s.malware_blocked,
            "ads_blocked":     s.ads_blocked,
        }


# ---------------------------------------------------------------------------
# Quick smoke test (run directly: python examples/custom_exporter.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import tempfile

    print(f"PLUGIN_INFO: {PLUGIN_INFO['name']} v{PLUGIN_INFO['version']}")
    print(f"pyyaml available: {_HAS_PYYAML}")

    # Create a fake ServerStats to test the exporter
    from natbench.plugin_base import ServerStats

    fake_server = {"name": "Test Server", "ip4": "1.1.1.1"}
    fake_stats = ServerStats(
        server=fake_server,
        score=87.3,
        avg_ms=11.2,
        median_ms=10.8,
        p95_ms=14.1,
        jitter_ms=1.3,
        success_rate=0.99,
        dnssec_ok=True,
        malware_blocked=False,
        ads_blocked=None,
    )

    exporter = YamlExporter()
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
        filepath = f.name

    ok = exporter.export([fake_stats], filepath, meta={"protocol": "udp", "queries": 50})
    if ok:
        with open(filepath) as f:
            print(f.read())
    else:
        print("Export failed", file=sys.stderr)
