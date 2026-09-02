# DNSMark

**Cross-platform DNS benchmark, analyser and optimizer.**

DNSMark measures the performance and reliability of DNS servers across multiple
protocols (UDP, TCP, DoT, DoH), ranks them by a configurable composite score,
and can apply the best server to your system DNS configuration — all with a
single command or a point-and-click GUI.

---

## Features

- **72+ built-in DNS servers** — Cloudflare, Google, Quad9, AdGuard, Mullvad,
  NextDNS, and many more from 20+ countries
- **Multi-protocol** — UDP · TCP · DNS-over-TLS (DoT) · DNS-over-HTTPS (DoH)
- **Composite scoring** — weighted latency, reliability, consistency, and
  security features (DNSSEC, malware blocking, ad blocking)
- **DNSSEC validation test** — checks whether the resolver actually enforces
  DNSSEC
- **Security checks** — tests for malware-domain blocking and ad-domain
  blocking
- **System DNS management** — reads and writes `/etc/resolv.conf` (Linux),
  `networksetup` (macOS), `netsh` (Windows)
- **Four export formats** — JSON, CSV, Markdown, HTML (dark theme, sortable
  table, no external dependencies)
- **Plugin system** — extend with custom resolvers, exporters, scorers, server
  providers, and locales
- **21 languages** — de, en, pl, ru, fr, nl, cs, hu, it, es, pt, sv, no, da,
  fi, el, ro, tr, uk, hr, bg
- **Zero mandatory dependencies** — all built-in functionality uses the Python
  standard library
- **GUI** — cross-platform tkinter interface (no extra install needed)
- **Python 3.10+**

---

## Installation

### From PyPI (recommended)

```bash
pip install dnsmark
```

### With Rich terminal output

```bash
pip install "dnsmark[rich]"
```

### From source

```bash
git clone https://github.com/natural78/dnsmark.git
cd dnsmark
pip install -e ".[rich,dev]"
```

---

## Quick Start

### CLI

```bash
# Benchmark all built-in servers using UDP (default)
dnsmark

# Use DNS-over-HTTPS
dnsmark --protocol doh

# Benchmark with more queries for higher accuracy
dnsmark --count 20 --workers 10

# Show top 10 results only
dnsmark --top 10

# Export results to all formats
dnsmark --export json,csv,html --output results

# Apply best DNS server to the system
dnsmark --apply

# Use a specific language
dnsmark --lang de

# List available protocols/exporters/scorers
dnsmark --list-protocols
dnsmark --list-exporters
dnsmark --list-scorers
```

### GUI

```bash
dnsmark-gui
# or
python -m dnsmark --gui
```

### Python API

```python
from dnsmark.core import benchmark_all
from dnsmark.servers import SERVER_DB
from dnsmark.plugin_loader import default_loader

loader = default_loader.load_all()

# Run benchmark
results = benchmark_all(
    servers=SERVER_DB,
    protocol="udp",
    n_queries=10,
    timeout=2.0,
    workers=8,
    scorer=loader.get_scorer("default"),
)

for rank, stats in enumerate(results, start=1):
    print(f"{rank}. {stats.server['name']}: {stats.score:.1f} pts, "
          f"median={stats.median_ms:.1f}ms")

# Export
exporter = loader.get_exporter("html")
exporter.export(results, "my_results.html", meta={"protocol": "udp"})
```

---

## Plugin System

DNSMark has a fully pluggable architecture. You can extend it by dropping a
`.py` file into `~/.dnsmark/plugins/<type>/`:

```
~/.dnsmark/
  plugins/
    resolvers/   my_doq_resolver.py
    exporters/   yaml_exporter.py
    scorers/     my_scorer.py
    providers/   my_servers.py
  locales/
    ja.json
```

Or set `DNSMARK_PLUGIN_PATH` to point to your plugin directory.

See `examples/custom_resolver.py` and `examples/custom_exporter.py` for
complete, runnable examples. The full plugin authoring guide is in
`docs/PLUGIN_GUIDE.md`.

### Plugin types

| Type      | Extend by                | Example                          |
|-----------|--------------------------|----------------------------------|
| Resolver  | Subclassing `ResolverPlugin`   | DoQ, ODOH, DNS-over-Tor     |
| Exporter  | Subclassing `ExporterPlugin`   | YAML, PDF, InfluxDB line    |
| Scorer    | Subclassing `ScorerPlugin`     | Security-weighted, ISP-tuned|
| Provider  | Subclassing `ServerProviderPlugin` | Custom intranet servers |

---

## Adding a Language

1. Copy `dnsmark/locales/en.json` to `~/.dnsmark/locales/<lang>.json`
2. Translate the string values (not the keys)
3. Update `_meta.lang` and `_meta.lang_name`
4. Run `dnsmark --lang <lang>` to test

To contribute your translation to the official release, open a pull request
adding the JSON file to `dnsmark/locales/`.

---

## Supported DNS Servers (sample)

| Provider     | UDP/TCP  | DoT  | DoH  | DNSSEC | Malware |
|--------------|---------|------|------|--------|---------|
| Cloudflare   | 1.1.1.1 | yes  | yes  | no     | 1.1.1.2 |
| Google       | 8.8.8.8 | yes  | yes  | yes    | no      |
| Quad9        | 9.9.9.9 | yes  | yes  | yes    | yes     |
| AdGuard DNS  | various | yes  | yes  | yes    | yes     |
| Mullvad      | various | yes  | yes  | yes    | yes     |
| NextDNS      | various | yes  | yes  | yes    | config  |
| OpenDNS      | various | no   | yes  | no     | yes     |
| ... 65 more  |         |      |      |        |         |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Run the test suite: `pytest`
4. Submit a pull request

Code style: standard Python, no formatter enforced. Keep dependencies minimal
— the core must run on pure stdlib.

---

## License

MIT License — see `LICENSE` for details.

Copyright (c) 2024 Natural (lag.natural@gmail.com)
