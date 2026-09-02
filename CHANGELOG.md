# Changelog

All notable changes to NatBench are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
NatBench uses [Semantic Versioning](https://semver.org/).

---

## [1.0.0] — 2026-09-02

### Added

#### Core
- `build_dns_query()` — pure-Python DNS packet builder (no external deps)
- `parse_dns_response()` — parses RCODE and ANCOUNT from raw DNS responses
- `benchmark_all()` — parallel benchmark engine with configurable worker count
- `BenchmarkResult` and `ServerStats` dataclasses for structured results
- DNSSEC validation test against `dnssec-failed.org`
- Malware domain blocking detection
- Ad-serving domain blocking detection
- Latency metrics: avg, median, P95, min, max, jitter (stddev)
- `success_rate` calculated per server
- Configurable query count, timeout, and concurrency

#### Built-in DNS Servers (`natbench/servers.py`)
- 72 DNS servers across 20+ countries
- Cloudflare (1.1.1.1, 1.0.0.1, 1.1.1.2 malware, 1.1.1.3 family)
- Google (8.8.8.8, 8.8.4.4, 2001:4860:4860::8888)
- Quad9 (9.9.9.9, 9.9.9.11 DNSSEC, 9.9.9.12 unsecured)
- AdGuard DNS (default, family protection, unfiltered)
- Mullvad (all nodes, privacy-focused)
- NextDNS, OpenDNS (including FamilyShield)
- DNS.WATCH, Comodo Secure DNS
- Verisign, Level3, Norton ConnectSafe
- Yandex (basic, safe, family)
- German privacy DNS (Digitalcourage, CCC, digitalerfrieden)
- European alternatives: Switch.ch, SWITCH DNS
- Privacy-focused: LibreOps, Snopyta, DisRoot

#### Plugin System
- `plugin_base.py` — ABCs for all five plugin types
- `plugin_loader.py` — dynamic discovery, validation, and singleton loader
- Plugin API version contract (MAJOR must match)
- Three-tier search order: builtin → user (`~/.natbench`) → `NATBENCH_PLUGIN_PATH`
- `PLUGIN_INFO` manifest validation at load time

#### Built-in Resolver Plugins
- `plugins/resolvers/udp.py` — UDP (port 53), raw socket
- `plugins/resolvers/tcp.py` — TCP with 2-byte RFC 1035 length prefix
- `plugins/resolvers/dot.py` — DNS-over-TLS (RFC 7858, port 853)
- `plugins/resolvers/doh.py` — DNS-over-HTTPS (RFC 8484 POST, stdlib urllib)

#### Built-in Exporter Plugins
- `plugins/exporters/json_exporter.py` — JSON with indent=2, all stats fields
- `plugins/exporters/csv_exporter.py` — CSV via `csv.DictWriter`, 18 columns
- `plugins/exporters/markdown_exporter.py` — Markdown table with meta section
- `plugins/exporters/html_exporter.py` — Self-contained HTML, dark theme CSS,
  sortable table (pure JS, zero deps), score bar visualization

#### Built-in Scorer Plugins
- `plugins/scorers/default_scorer.py` — Balanced: 50% speed, 30% reliability,
  10% consistency, 10% security. Linear interpolation between latency breakpoints
- `plugins/scorers/latency_only_scorer.py` — Pure speed score from median latency

#### Built-in Provider Plugins
- `plugins/providers/builtin_provider.py` — Returns `SERVER_DB`
- `plugins/providers/url_provider.py` — Fetches server list from URL
  (`NATBENCH_SERVER_URL` env var or `~/.natbench/config.json`)
- `plugins/providers/file_provider.py` — Loads server list from local JSON
  (`NATBENCH_SERVER_FILE` env var)

#### Internationalization (`natbench/i18n.py`)
- File-based locale system — JSON files in `natbench/locales/`
- User overrides in `~/.natbench/locales/`
- `t(key, lang, **kwargs)` with `str.format()` placeholder substitution
- `detect_lang()` — reads `LANGUAGE`/`LANG` env vars and `locale.getdefaultlocale()`
- `get_available_langs()` — scans builtin and user locale directories
- `load_lang()` with process-level cache
- English fallback for missing keys

#### Locale Files (21 languages)
- `en` English, `de` German, `fr` French, `es` Spanish, `pt` Portuguese
- `it` Italian, `nl` Dutch, `pl` Polish, `cs` Czech, `hu` Hungarian
- `sv` Swedish, `no` Norwegian, `da` Danish, `fi` Finnish
- `ru` Russian, `uk` Ukrainian, `bg` Bulgarian, `el` Greek
- `ro` Romanian, `tr` Turkish, `hr` Croatian
- Non-Latin scripts (ru, uk, bg, el) use proper Unicode

#### System DNS Management (`natbench/system.py`)
- `get_current_dns()` — reads system resolver (Linux/macOS/Windows)
- `set_dns()` — writes system resolver with platform-appropriate method
- `/etc/resolv.conf` on Linux
- `networksetup` on macOS
- `netsh` on Windows

#### CLI (`natbench/cli.py`)
- Rich-powered terminal interface (falls back gracefully without Rich)
- `--protocol` flag (udp/tcp/dot/doh)
- `--count`, `--timeout`, `--workers` tuning
- `--export` multi-format output
- `--apply` to set system DNS
- `--lang` for UI language
- `--scorer` to select scoring algorithm
- `--top N` to show only top N results

#### GUI (`natbench/gui.py`)
- tkinter-based cross-platform GUI (no extra deps)
- Tabs: Benchmark · System DNS · Export · About
- Live progress updates during benchmark
- Clickable results table
- System DNS reader/writer UI

#### Packaging
- `pyproject.toml` — modern setuptools packaging
- Entry points: `natbench` (CLI) and `natbench-gui`
- `natbench/__init__.py` — package namespace
- `natbench/__main__.py` — `python -m natbench` support
- Optional extras: `[rich]`, `[dev]`

#### Tests
- `tests/conftest.py` — `sample_server`, `sample_query_result`, `sample_server_stats`
- `tests/test_core.py` — DNS packet builder/parser, scorer logic (no network)
- `tests/test_plugins.py` — plugin discovery, ABC conformance, manifest validation
- `tests/test_i18n.py` — all 21 languages, fallback, placeholder substitution, detection

#### Examples and Documentation
- `examples/custom_resolver.py` — complete DoQ resolver skeleton
- `examples/custom_exporter.py` — YAML exporter with pyyaml/manual fallback
- `examples/custom_locale.json` — annotated locale template
- `docs/PLUGIN_GUIDE.md` — comprehensive plugin authoring guide
- `README.md` — project overview, installation, quick start, contributing

---

[1.0.0]: https://github.com/natural78/natbench/releases/tag/v1.0.0
