"""
NatBench web_ui.py — stdlib-only HTTP/SSE web interface.

Serves a single-page application on http://0.0.0.0:8765 (configurable).
Works in any modern browser, including Android Chrome/Firefox via LAN.

No third-party dependencies — uses only http.server, json, threading, etc.

Usage
-----
    python -m natbench.web_ui            # listen on 0.0.0.0:8765
    python -m natbench.web_ui 0.0.0.0 9090
    natbench-web                         # if installed via pip entry point
"""

from __future__ import annotations

import json
import queue
import socket
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# Internal imports (graceful fallback for running standalone)
# ---------------------------------------------------------------------------

try:
    from .core import run_benchmark, ServerStats
    from .servers import SERVER_DB
    from .system import check_root, set_dns
except ImportError:
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
    from natbench.core import run_benchmark, ServerStats
    from natbench.servers import SERVER_DB
    from natbench.system import check_root, set_dns

# ---------------------------------------------------------------------------
# Global state shared between request handler instances
# ---------------------------------------------------------------------------

_bench_lock = threading.Lock()
_bench_running = False
_bench_result: BenchmarkResult | None = None
_progress_queues: list[queue.Queue] = []      # one per SSE client
_progress_lock = threading.Lock()


def _broadcast_progress(msg: dict) -> None:
    """Push a progress message to all connected SSE clients."""
    data = "data: " + json.dumps(msg) + "\n\n"
    with _progress_lock:
        dead = []
        for q in _progress_queues:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _progress_queues.remove(q)


# ---------------------------------------------------------------------------
# HTML / CSS / JS (single-page app, inline, no external deps)
# ---------------------------------------------------------------------------

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
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 200" style="height:44px;width:auto;display:block;">
  <defs>
    <linearGradient id="wui_arc" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#0066cc"/><stop offset="100%" stop-color="#00d4ff"/>
    </linearGradient>
    <linearGradient id="wui_txt" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#ffffff"/><stop offset="100%" stop-color="#c8e0ff"/>
    </linearGradient>
    <filter id="wui_g"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <path d="M 54 161 A 65 65 0 1 0 146 161" fill="none" stroke="#1e3a5f" stroke-width="12" stroke-linecap="round"/>
  <path d="M 54 161 A 65 65 0 1 0 156 83" fill="none" stroke="url(#wui_arc)" stroke-width="12" stroke-linecap="round" filter="url(#wui_g)"/>
  <circle cx="156" cy="83" r="9" fill="#00ff88" filter="url(#wui_g)"/>
  <circle cx="100" cy="48" r="5" fill="#00d4ff" opacity="0.8"/>
  <circle cx="65" cy="68" r="4" fill="#00d4ff" opacity="0.55"/>
  <circle cx="135" cy="68" r="4" fill="#00d4ff" opacity="0.55"/>
  <g stroke="#00d4ff" stroke-width="1" opacity="0.3">
    <line x1="100" y1="105" x2="100" y2="53"/>
    <line x1="100" y1="105" x2="68" y2="71"/>
    <line x1="100" y1="105" x2="132" y2="71"/>
  </g>
  <circle cx="100" cy="105" r="10" fill="#161b22" stroke="#00d4ff" stroke-width="1.5"/>
  <circle cx="100" cy="105" r="4" fill="#00d4ff"/>
  <text x="220" y="108" font-family="'Segoe UI',system-ui,-apple-system,Arial,sans-serif" font-size="72" font-weight="800" letter-spacing="-2" fill="url(#wui_txt)">Nat</text>
  <text x="353" y="108" font-family="'Segoe UI',system-ui,-apple-system,Arial,sans-serif" font-size="72" font-weight="300" letter-spacing="-1" fill="#00d4ff">Bench</text>
  <text x="220" y="142" font-family="'Segoe UI',system-ui,-apple-system,Arial,sans-serif" font-size="20" font-weight="400" fill="#8ba3c7" letter-spacing="2">DNS BENCHMARK &amp; OPTIMIZER</text>
  <line x1="220" y1="120" x2="700" y2="120" stroke="#30363d" stroke-width="1" opacity="0.6"/>
</svg>"""

_HTML_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NatBench — DNS Benchmark</title>
<link rel="icon" type="image/svg+xml" href="{favicon}">
<style>
  :root {
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --accent: #58a6ff;
    --accent2: #3fb950;
    --warn: #f78166;
    --score-good: #3fb950;
    --score-ok: #d29922;
    --score-bad: #f78166;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, monospace;
    font-size: 14px;
    line-height: 1.5;
    min-height: 100vh;
  }
  header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 12px 20px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  header h1 { font-size: 18px; color: var(--accent); letter-spacing: 0.5px; }
  header .version { color: var(--muted); font-size: 12px; }
  .container { max-width: 1100px; margin: 0 auto; padding: 20px; }
  .row { display: flex; gap: 16px; flex-wrap: wrap; }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    flex: 1;
    min-width: 280px;
  }
  .card h2 { font-size: 14px; color: var(--muted); margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
  label { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; cursor: pointer; }
  label input[type=checkbox] { accent-color: var(--accent); width: 15px; height: 15px; }
  .server-group { margin-bottom: 10px; }
  .server-group-title {
    font-size: 11px;
    text-transform: uppercase;
    color: var(--accent);
    letter-spacing: 0.7px;
    margin-bottom: 4px;
    padding-bottom: 2px;
    border-bottom: 1px solid var(--border);
  }
  .server-list { max-height: 320px; overflow-y: auto; padding-right: 4px; }
  .server-list::-webkit-scrollbar { width: 4px; }
  .server-list::-webkit-scrollbar-track { background: transparent; }
  .server-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
  select, input[type=number] {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text);
    padding: 6px 10px;
    font-size: 14px;
    width: 100%;
    margin-bottom: 10px;
  }
  .select-row { display: flex; gap: 8px; margin-bottom: 8px; }
  .select-row button {
    font-size: 11px;
    padding: 3px 8px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--muted);
    cursor: pointer;
  }
  .select-row button:hover { border-color: var(--accent); color: var(--accent); }
  button.primary {
    background: var(--accent);
    color: #0d1117;
    font-weight: 700;
    border: none;
    border-radius: 6px;
    padding: 10px 22px;
    font-size: 15px;
    cursor: pointer;
    width: 100%;
    margin-top: 8px;
    transition: opacity 0.15s;
  }
  button.primary:hover { opacity: 0.85; }
  button.primary:disabled { opacity: 0.4; cursor: not-allowed; }
  button.secondary {
    background: transparent;
    color: var(--accent2);
    border: 1px solid var(--accent2);
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    cursor: pointer;
    margin-top: 6px;
    width: 100%;
    transition: opacity 0.15s;
  }
  button.secondary:hover { opacity: 0.75; }
  button.secondary:disabled { opacity: 0.4; cursor: not-allowed; }
  #status-bar {
    margin-top: 16px;
    padding: 8px 12px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    font-family: monospace;
    font-size: 12px;
    color: var(--muted);
    min-height: 32px;
    white-space: pre-wrap;
    word-break: break-all;
  }
  #results { margin-top: 20px; }
  #results table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  #results th {
    text-align: left;
    padding: 8px 10px;
    border-bottom: 2px solid var(--border);
    color: var(--muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  #results td {
    padding: 7px 10px;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
  }
  #results tr:hover td { background: rgba(88,166,255,0.05); }
  .rank { color: var(--muted); font-size: 12px; }
  .score-bar-wrap { display: flex; align-items: center; gap: 8px; }
  .score-bar {
    height: 8px;
    border-radius: 4px;
    background: var(--score-good);
    transition: width 0.4s ease;
    min-width: 2px;
  }
  .score-bar.ok { background: var(--score-ok); }
  .score-bar.bad { background: var(--score-bad); }
  .score-val { font-weight: 700; min-width: 32px; text-align: right; font-size: 13px; }
  .latency { font-family: monospace; }
  .tag { display: inline-block; padding: 1px 5px; border-radius: 3px; font-size: 10px; margin-right: 2px; }
  .tag-malware { background: #2d1f1f; color: #f78166; border: 1px solid #7e2a1a; }
  .tag-adblock { background: #1f2a1f; color: #3fb950; border: 1px solid #1a5c26; }
  .tag-dnssec  { background: #1f2535; color: #58a6ff; border: 1px solid #1a3a6e; }
  .tag-no-log  { background: #2a2a1f; color: #d29922; border: 1px solid #5e4a10; }
  .tag-default { background: #1f1f2a; color: #8b949e; border: 1px solid #30363d; }
  .country { font-size: 11px; color: var(--muted); }
  .set-dns-btn {
    padding: 3px 8px;
    font-size: 11px;
    background: transparent;
    border: 1px solid var(--accent2);
    color: var(--accent2);
    border-radius: 3px;
    cursor: pointer;
  }
  .set-dns-btn:hover { opacity: 0.75; }
  .err { color: var(--warn); }
  .success-rate { font-family: monospace; font-size: 12px; }
  .progress-bar-wrap {
    margin-top: 10px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    height: 6px;
    overflow: hidden;
    display: none;
  }
  .progress-bar {
    height: 100%;
    background: var(--accent);
    width: 0%;
    transition: width 0.3s;
    border-radius: 4px;
  }
  @media (max-width: 700px) {
    .row { flex-direction: column; }
    #results table { font-size: 12px; }
    #results th, #results td { padding: 5px 6px; }
    .score-bar-wrap .score-bar { display: none; }
  }
</style>
</head>
<body>
<header>
  {logo}
  <span class="version">DNS Benchmark &amp; Analyser</span>
</header>

<div class="container">
  <div class="row">
    <!-- Left: server selection -->
    <div class="card" style="flex:2; min-width:300px;">
      <h2>DNS Servers</h2>
      <div class="select-row">
        <button onclick="selectAll()">All</button>
        <button onclick="selectNone()">None</button>
        <button onclick="selectFast()">Fast preset</button>
        <button onclick="selectPrivacy()">Privacy preset</button>
      </div>
      <div class="server-list" id="server-list">
        <!-- populated by JS -->
      </div>
    </div>

    <!-- Right: options -->
    <div class="card" style="flex:1; min-width:240px;">
      <h2>Options</h2>

      <label for="proto-sel" style="display:block; margin-bottom:4px; color:var(--muted);">Protocol</label>
      <select id="proto-sel">
        <option value="udp">UDP (plain, port 53)</option>
        <option value="tcp">TCP (plain, port 53)</option>
        <option value="doh">DoH (DNS-over-HTTPS)</option>
        <option value="dot">DoT (DNS-over-TLS)</option>
      </select>

      <label for="count-inp" style="display:block; margin-bottom:4px; color:var(--muted);">Queries per server</label>
      <input type="number" id="count-inp" min="1" max="50" value="5">

      <label for="timeout-inp" style="display:block; margin-bottom:4px; color:var(--muted);">Timeout (seconds)</label>
      <input type="number" id="timeout-inp" min="0.5" max="10" step="0.5" value="3">

      <label for="workers-inp" style="display:block; margin-bottom:4px; color:var(--muted);">Parallel workers</label>
      <input type="number" id="workers-inp" min="1" max="32" value="8">

      <button class="primary" id="run-btn" onclick="runBenchmark()">&#9654; Start Benchmark</button>

      <div class="progress-bar-wrap" id="progress-wrap">
        <div class="progress-bar" id="progress-bar"></div>
      </div>

      <div id="status-bar">Ready. Select servers and press Start.</div>
    </div>
  </div>

  <!-- Results -->
  <div id="results"></div>
</div>

<script>
// ---------------------------------------------------------------------------
// Server data injected from Python
// ---------------------------------------------------------------------------
const SERVERS = __SERVERS_JSON__;

// ---------------------------------------------------------------------------
// Group servers by region/operator for display
// ---------------------------------------------------------------------------
const GROUPS = {
  "Custom":    s => s.tags.includes("custom"),
  "Privacy":   s => s.tags.some(t => ["no-log","privacy"].includes(t)) && !s.tags.includes("custom"),
  "Ad-block":  s => s.tags.includes("adblock"),
  "Security":  s => s.tags.includes("malware") && !s.tags.includes("adblock"),
  "Family":    s => s.tags.includes("family"),
  "China/Asia":s => s.tags.some(t => ["china","asia"].includes(t)),
  "Russia/CIS":s => s.tags.includes("russia"),
  "Canada":    s => s.tags.includes("canada"),
  "Community": s => s.tags.includes("community"),
  "Other":     s => true,
};

function groupServers(servers) {
  const result = {};
  const used = new Set();
  for (const [gname, pred] of Object.entries(GROUPS)) {
    const members = servers.filter((s,i) => !used.has(i) && pred(s));
    members.forEach((_,j) => {
      const realIdx = servers.indexOf(members[j]);
      used.add(servers.findIndex((s2,i2) => !used.has(i2) && s2 === members[j]));
    });
    if (members.length) result[gname] = members;
  }
  return result;
}

function renderServerList() {
  const container = document.getElementById("server-list");
  container.innerHTML = "";
  const grouped = {};
  const used = new Set();
  for (const [gname, pred] of Object.entries(GROUPS)) {
    const members = SERVERS.filter((s,i) => !used.has(i) && pred(s));
    members.forEach(s => used.add(SERVERS.indexOf(s)));
    if (members.length) grouped[gname] = members;
  }
  for (const [gname, members] of Object.entries(grouped)) {
    const wrap = document.createElement("div");
    wrap.className = "server-group";
    const title = document.createElement("div");
    title.className = "server-group-title";
    title.textContent = gname + " (" + members.length + ")";
    wrap.appendChild(title);
    for (const s of members) {
      const lbl = document.createElement("label");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = true;
      cb.dataset.name = s.name;
      cb.className = "srv-cb";
      const txt = document.createTextNode(s.name + (s.ip4 ? " — " + s.ip4 : ""));
      lbl.appendChild(cb);
      lbl.appendChild(txt);
      wrap.appendChild(lbl);
    }
    container.appendChild(wrap);
  }
}

function selectAll()  { document.querySelectorAll(".srv-cb").forEach(c => c.checked = true);  }
function selectNone() { document.querySelectorAll(".srv-cb").forEach(c => c.checked = false); }
function selectFast() {
  const fastTags = ["fast","anycast"];
  document.querySelectorAll(".srv-cb").forEach(cb => {
    const s = SERVERS.find(x => x.name === cb.dataset.name);
    cb.checked = s && s.tags.some(t => fastTags.includes(t));
  });
}
function selectPrivacy() {
  document.querySelectorAll(".srv-cb").forEach(cb => {
    const s = SERVERS.find(x => x.name === cb.dataset.name);
    cb.checked = s && (s.tags.includes("no-log") || s.tags.includes("privacy"));
  });
}

// ---------------------------------------------------------------------------
// Benchmark
// ---------------------------------------------------------------------------
let evtSource = null;
let totalServers = 0;
let doneServers = 0;

function updateStatus(msg) {
  document.getElementById("status-bar").textContent = msg;
}

function runBenchmark() {
  const selected = Array.from(document.querySelectorAll(".srv-cb:checked"))
    .map(cb => cb.dataset.name);
  if (!selected.length) { updateStatus("Select at least one server."); return; }

  const proto   = document.getElementById("proto-sel").value;
  const count   = parseInt(document.getElementById("count-inp").value) || 5;
  const timeout = parseFloat(document.getElementById("timeout-inp").value) || 3;
  const workers = parseInt(document.getElementById("workers-inp").value) || 8;

  document.getElementById("run-btn").disabled = true;
  document.getElementById("results").innerHTML = "";
  totalServers = selected.length;
  doneServers = 0;
  document.getElementById("progress-wrap").style.display = "block";
  document.getElementById("progress-bar").style.width = "0%";

  updateStatus("Starting benchmark for " + selected.length + " servers...");

  // SSE for progress
  if (evtSource) { evtSource.close(); evtSource = null; }
  evtSource = new EventSource("/api/status");
  evtSource.onmessage = e => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === "progress") {
        doneServers++;
        const pct = Math.round(doneServers / totalServers * 100);
        document.getElementById("progress-bar").style.width = pct + "%";
        updateStatus("[" + doneServers + "/" + totalServers + "] " + msg.server + " — " +
          (msg.avg_ms != null ? msg.avg_ms.toFixed(1) + " ms" : "failed"));
      } else if (msg.type === "done") {
        evtSource.close();
        evtSource = null;
      } else if (msg.type === "error") {
        updateStatus("Error: " + msg.message);
        evtSource.close();
        document.getElementById("run-btn").disabled = false;
      }
    } catch(_) {}
  };
  evtSource.onerror = () => { /* server closed — normal after done */ };

  // POST bench request
  fetch("/api/bench", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({servers: selected, protocol: proto, count, timeout, workers})
  })
  .then(r => r.json())
  .then(data => {
    document.getElementById("progress-bar").style.width = "100%";
    if (data.error) {
      updateStatus("Error: " + data.error);
    } else {
      updateStatus("Done! " + data.results.length + " servers benchmarked in " +
        data.duration_s.toFixed(1) + "s");
      renderResults(data.results);
    }
    document.getElementById("run-btn").disabled = false;
  })
  .catch(err => {
    updateStatus("Request failed: " + err.message);
    document.getElementById("run-btn").disabled = false;
  });
}

function tagHtml(tags) {
  const show = ["malware","adblock","dnssec","no-log","family","anycast"].filter(t => tags.includes(t));
  return show.map(t => {
    const cls = {malware:"tag-malware",adblock:"tag-adblock",dnssec:"tag-dnssec","no-log":"tag-no-log"}[t] || "tag-default";
    return `<span class="tag ${cls}">${t}</span>`;
  }).join("");
}

function scoreColor(score) {
  if (score >= 70) return "";       // good (green default)
  if (score >= 40) return "ok";
  return "bad";
}

function renderResults(results) {
  const div = document.getElementById("results");
  if (!results.length) { div.innerHTML = "<p style='color:var(--muted);margin-top:16px'>No results.</p>"; return; }

  let html = `
  <div class="card" style="margin-top:20px">
    <h2>Results (${results.length} servers)</h2>
    <div style="overflow-x:auto">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Server</th>
          <th>Score</th>
          <th>Avg ms</th>
          <th>Min ms</th>
          <th>P95 ms</th>
          <th>Success</th>
          <th>Tags</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
  `;

  results.forEach((r, i) => {
    const scoreW = Math.round(r.score);
    const barW   = Math.min(100, scoreW);
    const barCls = scoreColor(r.score);
    const avg    = r.avg_ms != null ? r.avg_ms.toFixed(1) : '<span class="err">—</span>';
    const min_ms = r.min_ms != null ? r.min_ms.toFixed(1) : "—";
    const p95    = r.p95_ms != null ? r.p95_ms.toFixed(1) : "—";
    const succ   = (r.success_rate * 100).toFixed(0) + "%";
    const tags   = tagHtml(r.server_info ? (r.server_info.tags || []) : []);
    const ip     = r.ip || (r.server_info && r.server_info.ip4) || "";
    html += `
      <tr>
        <td class="rank">${i + 1}</td>
        <td>
          <strong>${escHtml(r.name)}</strong><br>
          <span class="country">${ip} &nbsp; ${r.server_info ? (r.server_info.country || "") : ""}</span>
        </td>
        <td>
          <div class="score-bar-wrap">
            <div class="score-bar ${barCls}" style="width:${barW}px; max-width:100px"></div>
            <span class="score-val">${scoreW}</span>
          </div>
        </td>
        <td class="latency">${avg}</td>
        <td class="latency">${min_ms}</td>
        <td class="latency">${p95}</td>
        <td class="success-rate">${succ}</td>
        <td>${tags}</td>
        <td>
          <button class="set-dns-btn" onclick="setDns('${escHtml(ip)}','${escHtml(r.name)}')">Set DNS</button>
        </td>
      </tr>
    `;
  });

  html += "</tbody></table></div></div>";
  div.innerHTML = html;
}

function escHtml(str) {
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function setDns(ip, name) {
  if (!ip) { alert("This server has no IPv4 address — cannot set as system DNS."); return; }
  if (!confirm("Set system DNS to " + name + " (" + ip + ")?\n\nRequires root/admin privileges.")) return;
  fetch("/api/set-dns", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ip})
  })
  .then(r => r.json())
  .then(data => {
    if (data.ok) alert("DNS set to " + ip + " successfully.");
    else alert("Failed: " + (data.error || "unknown error"));
  })
  .catch(err => alert("Request failed: " + err.message));
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
renderServerList();
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------


class NatBenchHandler(BaseHTTPRequestHandler):
    """Minimal HTTP request handler for NatBench web UI."""

    # Suppress default request logging; we print our own
    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._serve_page()
        elif path == "/api/status":
            self._serve_sse()
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self._read_body()
        if path == "/api/bench":
            self._handle_bench(body)
        elif path == "/api/set-dns":
            self._handle_set_dns(body)
        else:
            self._send_json({"error": "not found"}, 404)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except Exception:
            return {}

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _serve_page(self) -> None:
        # Inject server list as JSON
        server_data = [
            {
                "name": s["name"],
                "ip4": s.get("ip4"),
                "country": s.get("country", ""),
                "tags": s.get("tags", []),
                "description_en": s.get("description_en", ""),
            }
            for s in SERVER_DB
        ]
        page = (
            _HTML_PAGE
            .replace("__SERVERS_JSON__", json.dumps(server_data))
            .replace("{favicon}", _FAVICON_DATA_URI)
            .replace("{logo}", _LOGO_INLINE_SVG)
        )
        payload = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ------------------------------------------------------------------
    # SSE progress stream
    # ------------------------------------------------------------------

    def _serve_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        q: queue.Queue = queue.Queue(maxsize=256)
        with _progress_lock:
            _progress_queues.append(q)

        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    self.wfile.write(msg.encode())
                    self.wfile.flush()
                except queue.Empty:
                    # Send a keepalive comment
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with _progress_lock:
                try:
                    _progress_queues.remove(q)
                except ValueError:
                    pass

    # ------------------------------------------------------------------
    # /api/bench
    # ------------------------------------------------------------------

    def _handle_bench(self, body: dict) -> None:
        global _bench_running, _bench_result

        with _bench_lock:
            if _bench_running:
                self._send_json({"error": "A benchmark is already running."}, 409)
                return
            _bench_running = True
            _bench_result = None

        # Resolve selected server names → server dicts
        selected_names: list[str] = body.get("servers", [])
        protocol: str = body.get("protocol", "udp")
        count: int = max(1, min(50, int(body.get("count", 5))))
        timeout: float = max(0.5, min(10.0, float(body.get("timeout", 3.0))))
        workers: int = max(1, min(32, int(body.get("workers", 8))))

        name_set = set(selected_names)
        servers = [s for s in SERVER_DB if s["name"] in name_set]

        if not servers:
            with _bench_lock:
                _bench_running = False
            self._send_json({"error": "No matching servers found."}, 400)
            return

        # Build a lookup for fast stats retrieval from progress callback
        _stats_by_name: dict[str, "ServerStats"] = {}

        def _progress_cb(server_name: str, done: int, total: int) -> None:
            # Stats aren't available yet at callback time; just send progress
            _broadcast_progress({
                "type": "progress",
                "server": server_name,
                "done": done,
                "total": total,
                "avg_ms": None,
            })

        try:
            t0 = time.monotonic()
            result_list: list[ServerStats] = run_benchmark(
                servers=servers,
                protocol=protocol,
                n_queries=count,
                timeout=timeout,
                max_workers=workers,
                progress_cb=_progress_cb,
            )
            duration = time.monotonic() - t0
            _broadcast_progress({"type": "done"})

            results_list = []
            for s in result_list:
                results_list.append({
                    "name": s.name,
                    "ip": s.ip,
                    "protocol": s.protocol,
                    "avg_ms": s.avg_ms,
                    "min_ms": s.min_ms,
                    "p95_ms": s.p95_ms,
                    "max_ms": s.max_ms,
                    "jitter_ms": s.jitter_ms,
                    "success_rate": s.success_rate,
                    "total_queries": s.total_queries,
                    "failed_queries": s.failed_queries,
                    "dnssec_ok": s.dnssec_ok,
                    "malware_blocked": s.malware_blocked,
                    "ads_blocked": s.ads_blocked,
                    "score": s.score,
                    "server_info": {
                        "ip4": s.server_info.get("ip4"),
                        "country": s.server_info.get("country", ""),
                        "tags": s.server_info.get("tags", []),
                        "operator": s.server_info.get("operator", ""),
                        "description_en": s.server_info.get("description_en", ""),
                    },
                })

            self._send_json({
                "ok": True,
                "results": results_list,
                "duration_s": duration,
                "protocol": protocol,
                "n_queries": count,
                "server_count": len(result_list),
            })
        except Exception as exc:
            _broadcast_progress({"type": "error", "message": str(exc)})
            self._send_json({"error": str(exc)}, 500)
            traceback.print_exc()
        finally:
            with _bench_lock:
                _bench_running = False

    # ------------------------------------------------------------------
    # /api/set-dns
    # ------------------------------------------------------------------

    def _handle_set_dns(self, body: dict) -> None:
        ip = body.get("ip", "").strip()
        if not ip:
            self._send_json({"error": "No IP address provided."}, 400)
            return

        if not check_root():
            self._send_json(
                {"error": "Setting system DNS requires root/admin privileges. "
                          "Restart natbench-web with sudo (Linux/macOS) or "
                          "as Administrator (Windows)."},
                403,
            )
            return

        try:
            ok = set_dns([ip])
            if ok:
                self._send_json({"ok": True, "ip": ip})
            else:
                self._send_json({"error": "set_dns returned False — check logs."}, 500)
        except Exception as exc:
            self._send_json({"error": str(exc)}, 500)


# ---------------------------------------------------------------------------
# Server entrypoint
# ---------------------------------------------------------------------------


def _get_local_ip() -> str:
    """Best-effort: return the machine's LAN IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def serve(host: str = "0.0.0.0", port: int = 8765) -> None:
    """Start the HTTP server and block until Ctrl-C."""
    server = HTTPServer((host, port), NatBenchHandler)
    local_ip = _get_local_ip()
    print(f"NatBench Web UI — http://{local_ip}:{port}")
    print(f"Listening on http://{host}:{port}")
    print("Open the URL in any browser (including Android).")
    print("Press Ctrl-C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


def main() -> None:
    """Entry point: parse optional host/port from argv."""
    host = "0.0.0.0"
    port = 8765
    if len(sys.argv) >= 2:
        host = sys.argv[1]
    if len(sys.argv) >= 3:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"Invalid port '{sys.argv[2]}', using 8765.", file=sys.stderr)
    serve(host, port)


if __name__ == "__main__":
    main()
