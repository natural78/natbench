"""
natbench built-in exporter: HTML
=================================
Exports benchmark results as a self-contained HTML file with:
  - Dark-theme CSS
  - Sortable table (pure JavaScript, zero dependencies)
  - Score bar visualization (colored div width proportional to score)
"""

from __future__ import annotations

import html
import os
from datetime import datetime, timezone
from typing import Any, Optional

from natbench.plugin_base import ExporterPlugin, ServerStats

PLUGIN_INFO = {
    "name":        "HTML Exporter",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "NatBench contributors",
    "description": "Export results as a self-contained dark-theme HTML page with sortable table",
    "type":        "exporter",
    "format":      "html",
    "requires":    [],
    "tags":        ["builtin", "visual"],
}

_FAVICON_DATA_URI = (
    "data:image/svg+xml,"
    "%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2032%2032%22%3E"
    "%3Cdefs%3E%3ClinearGradient%20id%3D%22fgArc%22%20x1%3D%220%22%20y1%3D%220%22%20x2%3D%221%22%20y2%3D%220%22%3E"
    "%3Cstop%20offset%3D%220%25%22%20stop-color%3D%22%230066cc%22%2F%3E"
    "%3Cstop%20offset%3D%22100%25%22%20stop-color%3D%22%2300d4ff%22%2F%3E"
    "%3C%2FlinearGradient%3E%3C%2Fdefs%3E"
    "%3Crect%20width%3D%2232%22%20height%3D%2232%22%20rx%3D%227%22%20fill%3D%22%230a1628%22%2F%3E"
    "%3Cpath%20d%3D%22M%208%2028%20A%2011%2011%200%201%200%2024%2028%22%20fill%3D%22none%22%20stroke%3D%22%231e3a5f%22%20stroke-width%3D%223%22%20stroke-linecap%3D%22round%22%2F%3E"
    "%3Cpath%20d%3D%22M%208%2028%20A%2011%2011%200%201%200%2026%2015%22%20fill%3D%22none%22%20stroke%3D%22url%28%2523fgArc%29%22%20stroke-width%3D%223%22%20stroke-linecap%3D%22round%22%2F%3E"
    "%3Ccircle%20cx%3D%2226%22%20cy%3D%2215%22%20r%3D%222.5%22%20fill%3D%22%2300ff88%22%2F%3E"
    "%3Ccircle%20cx%3D%2216%22%20cy%3D%2218%22%20r%3D%222.5%22%20fill%3D%22%2300d4ff%22%20opacity%3D%220.9%22%2F%3E"
    "%3C%2Fsvg%3E"
)

_LOGO_INLINE_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 200" style="height:60px;width:auto;display:block;">
  <defs>
    <linearGradient id="nb_bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0d1f3c"/><stop offset="100%" stop-color="#0a1628"/>
    </linearGradient>
    <linearGradient id="nb_arc" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#0066cc"/><stop offset="100%" stop-color="#00d4ff"/>
    </linearGradient>
    <linearGradient id="nb_txt" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#ffffff"/><stop offset="100%" stop-color="#c8e0ff"/>
    </linearGradient>
    <filter id="nb_g"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <rect width="800" height="200" rx="20" fill="url(#nb_bg)"/>
  <path d="M 54 161 A 65 65 0 1 0 146 161" fill="none" stroke="#1e3a5f" stroke-width="12" stroke-linecap="round"/>
  <path d="M 54 161 A 65 65 0 1 0 156 83" fill="none" stroke="url(#nb_arc)" stroke-width="12" stroke-linecap="round" filter="url(#nb_g)"/>
  <circle cx="156" cy="83" r="9" fill="#00ff88" filter="url(#nb_g)"/>
  <circle cx="100" cy="48" r="5" fill="#00d4ff" opacity="0.8"/>
  <circle cx="65" cy="68" r="4" fill="#00d4ff" opacity="0.55"/>
  <circle cx="135" cy="68" r="4" fill="#00d4ff" opacity="0.55"/>
  <g stroke="#00d4ff" stroke-width="1" opacity="0.3">
    <line x1="100" y1="105" x2="100" y2="53"/>
    <line x1="100" y1="105" x2="68" y2="71"/>
    <line x1="100" y1="105" x2="132" y2="71"/>
  </g>
  <circle cx="100" cy="105" r="10" fill="#0a1628" stroke="#00d4ff" stroke-width="1.5"/>
  <circle cx="100" cy="105" r="4" fill="#00d4ff"/>
  <text x="220" y="108" font-family="'Segoe UI',system-ui,-apple-system,Arial,sans-serif" font-size="72" font-weight="800" letter-spacing="-2" fill="url(#nb_txt)">Nat</text>
  <text x="353" y="108" font-family="'Segoe UI',system-ui,-apple-system,Arial,sans-serif" font-size="72" font-weight="300" letter-spacing="-1" fill="#00d4ff">Bench</text>
  <text x="220" y="142" font-family="'Segoe UI',system-ui,-apple-system,Arial,sans-serif" font-size="20" font-weight="400" fill="#8ba3c7" letter-spacing="2">DNS BENCHMARK &amp; OPTIMIZER</text>
  <line x1="220" y1="120" x2="700" y2="120" stroke="#1e3a5f" stroke-width="1" opacity="0.6"/>
</svg>"""

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: #0a1628;
  color: #e0e0e6;
  padding: 0;
  line-height: 1.5;
}
.nb-header {
  background: #0d2040;
  border-bottom: 1px solid #1e3a5f;
  padding: 16px 32px;
  display: flex;
  align-items: center;
  gap: 20px;
}
.nb-header-title {
  font-size: 0.85rem;
  color: #8ba3c7;
  letter-spacing: 0.05em;
}
.nb-content { padding: 24px 32px; }
.subtitle { color: #6b7280; font-size: 0.9rem; margin-bottom: 24px; }
.meta-box {
  background: #1a1d27;
  border: 1px solid #2d3148;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 24px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px 32px;
}
.meta-item { font-size: 0.85rem; }
.meta-label { color: #6b7280; }
.meta-value { color: #c4b5fd; font-weight: 600; }
.table-wrap { overflow-x: auto; border-radius: 10px; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
  min-width: 900px;
}
thead th {
  background: #1e2130;
  color: #a78bfa;
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  border-bottom: 2px solid #3730a3;
  position: sticky;
  top: 0;
}
thead th:hover { background: #252840; }
thead th.sorted-asc::after  { content: ' ↑'; color: #7c3aed; }
thead th.sorted-desc::after { content: ' ↓'; color: #7c3aed; }
tbody tr { border-bottom: 1px solid #1e2130; transition: background 0.1s; }
tbody tr:hover { background: #1a1d2a; }
tbody tr:first-child td { color: #fde68a; }
tbody tr:nth-child(2) td { color: #d1d5db; }
tbody tr:nth-child(3) td { color: #c4a77d; }
td { padding: 9px 12px; vertical-align: middle; }
.rank { font-weight: 700; text-align: center; min-width: 40px; }
.score-cell { min-width: 110px; }
.score-bar-wrap {
  background: #1e2130;
  border-radius: 4px;
  height: 6px;
  width: 80px;
  margin-top: 4px;
  overflow: hidden;
}
.score-bar {
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, #7c3aed, #a78bfa);
}
.score-val { font-weight: 700; color: #a78bfa; }
.ms { color: #67e8f9; font-variant-numeric: tabular-nums; }
.pct { color: #86efac; }
.yes { color: #4ade80; }
.no  { color: #f87171; }
.unk { color: #6b7280; }
.tag {
  display: inline-block;
  background: #1e2130;
  border: 1px solid #3730a3;
  color: #818cf8;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 0.75rem;
  margin-right: 2px;
}
footer {
  margin-top: 32px;
  font-size: 0.8rem;
  color: #4b5563;
  text-align: center;
}
footer a { color: #6d28d9; text-decoration: none; }
"""

_JS = """
(function() {
  var table = document.getElementById('results-table');
  var tbody = table.tBodies[0];
  var headers = table.tHead.rows[0].cells;
  var sortDir = {};

  function getCellVal(row, idx) {
    return row.cells[idx].getAttribute('data-val') || row.cells[idx].innerText.trim();
  }

  function comparer(idx, asc) {
    return function(a, b) {
      var va = getCellVal(asc ? a : b, idx);
      var vb = getCellVal(asc ? b : a, idx);
      var na = parseFloat(va), nb = parseFloat(vb);
      if (!isNaN(na) && !isNaN(nb)) return na - nb;
      return va.localeCompare(vb);
    };
  }

  Array.from(headers).forEach(function(th, idx) {
    th.addEventListener('click', function() {
      // Remove sort classes from all headers
      Array.from(headers).forEach(function(h) {
        h.classList.remove('sorted-asc', 'sorted-desc');
      });
      sortDir[idx] = !sortDir[idx];
      var asc = sortDir[idx];
      th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');
      var rows = Array.from(tbody.rows);
      rows.sort(comparer(idx, asc));
      rows.forEach(function(r) { tbody.appendChild(r); });
    });
  });
})();
"""


def _h(text: Any) -> str:
    """HTML-escape a value."""
    return html.escape(str(text) if text is not None else "")


def _bool_cell(v: Optional[bool]) -> str:
    if v is None:
        return '<span class="unk">?</span>'
    if v:
        return '<span class="yes">Yes</span>'
    return '<span class="no">No</span>'


def _fmt(v: Optional[float], ndigits: int = 1) -> str:
    if v is None:
        return "—"
    return f"{v:.{ndigits}f}"


def _score_color(score: float) -> str:
    """Return a CSS hex color from red (0) via yellow (50) to green (100)."""
    if score >= 75:
        return "#4ade80"  # green
    if score >= 50:
        return "#facc15"  # yellow
    if score >= 25:
        return "#fb923c"  # orange
    return "#f87171"       # red


class HtmlExporter(ExporterPlugin):
    """Export benchmark results to a self-contained HTML file."""

    format         = "html"
    file_extension = ".html"

    def export(
        self,
        results:  list[ServerStats],
        filepath: str,
        *,
        lang:  str = "en",
        meta:  Optional[dict[str, Any]] = None,
    ) -> bool:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        content = self._render(results, meta)
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(content)
        return True

    def preview(
        self,
        results:  list[ServerStats],
        max_rows: int = 10,
        lang:     str = "en",
    ) -> str:
        return self._render(results[:max_rows], None)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _render(
        self,
        results:  list[ServerStats],
        meta:     Optional[dict[str, Any]],
    ) -> str:
        ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        meta = meta or {}

        # Meta box items
        meta_html = ""
        meta_items = [("Generated", ts), ("Servers tested", str(len(results)))]
        for k, v in meta.items():
            meta_items.append((str(k), str(v)))
        for label, value in meta_items:
            meta_html += (
                f'<div class="meta-item">'
                f'<span class="meta-label">{_h(label)}: </span>'
                f'<span class="meta-value">{_h(value)}</span>'
                f'</div>\n'
            )

        # Table rows
        rows_html = ""
        for rank, s in enumerate(results, start=1):
            srv = s.server
            name   = srv.get("name", "Unknown")
            tags   = srv.get("tags", [])
            prot   = srv.get("protocol", "udp")
            score  = s.score
            color  = _score_color(score)
            bar_w  = int(score)

            tags_html = "".join(f'<span class="tag">{_h(t)}</span>' for t in tags)

            rows_html += f"""
  <tr>
    <td class="rank" data-val="{rank}">{rank}</td>
    <td>{_h(name)}<br><small>{tags_html}</small></td>
    <td class="score-cell" data-val="{score:.2f}">
      <span class="score-val" style="color:{color}">{score:.1f}</span>
      <div class="score-bar-wrap">
        <div class="score-bar" style="width:{bar_w}%;background:linear-gradient(90deg,{color},{color}aa)"></div>
      </div>
    </td>
    <td class="ms" data-val="{s.avg_ms if s.avg_ms is not None else 9999}">{_fmt(s.avg_ms)}</td>
    <td class="ms" data-val="{s.median_ms if s.median_ms is not None else 9999}">{_fmt(s.median_ms)}</td>
    <td class="ms" data-val="{s.p95_ms if s.p95_ms is not None else 9999}">{_fmt(s.p95_ms)}</td>
    <td class="ms" data-val="{s.min_ms if s.min_ms is not None else 9999}">{_fmt(s.min_ms)}</td>
    <td class="ms" data-val="{s.max_ms if s.max_ms is not None else 9999}">{_fmt(s.max_ms)}</td>
    <td class="ms" data-val="{s.jitter_ms if s.jitter_ms is not None else 9999}">{_fmt(s.jitter_ms)}</td>
    <td class="pct" data-val="{s.success_rate:.4f}">{s.success_rate*100:.1f}%</td>
    <td>{_bool_cell(s.dnssec_ok)}</td>
    <td>{_bool_cell(s.malware_blocked)}</td>
    <td>{_bool_cell(s.ads_blocked)}</td>
    <td>{_h(prot)}</td>
  </tr>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NatBench Results</title>
  <link rel="icon" type="image/svg+xml" href="{_FAVICON_DATA_URI}">
  <style>{_CSS}</style>
</head>
<body>
  <div class="nb-header">
    {_LOGO_INLINE_SVG}
    <span class="nb-header-title">Benchmark Report</span>
  </div>

  <div class="nb-content">
    <p class="subtitle">DNS performance analysis — generated by NatBench</p>

    <div class="meta-box">
      {meta_html}
    </div>

    <div class="table-wrap">
      <table id="results-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Server</th>
            <th>Score</th>
            <th>Avg ms</th>
            <th>Median</th>
            <th>P95</th>
            <th>Min</th>
            <th>Max</th>
            <th>Jitter</th>
            <th>Reliability</th>
            <th>DNSSEC</th>
            <th>Malware</th>
            <th>Ads</th>
            <th>Protocol</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>

    <footer>
      <p>Generated by <a href="https://natural.yt/natbench">NatBench</a> &mdash; {_h(ts)}</p>
    </footer>
  </div>

  <script>{_JS}</script>
</body>
</html>
"""
