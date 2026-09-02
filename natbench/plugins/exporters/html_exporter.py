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

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: #0f1117;
  color: #e0e0e6;
  padding: 24px;
  line-height: 1.5;
}
h1 { font-size: 1.8rem; color: #a78bfa; margin-bottom: 4px; }
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
  <style>{_CSS}</style>
</head>
<body>
  <h1>NatBench Benchmark Results</h1>
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

  <script>{_JS}</script>
</body>
</html>
"""
