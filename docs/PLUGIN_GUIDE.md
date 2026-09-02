# NatBench Plugin Author Guide

This guide covers everything you need to know to write, install, and test
NatBench plugins.

---

## Table of Contents

1. [Overview of Plugin Types](#overview-of-plugin-types)
2. [PLUGIN_INFO Manifest Reference](#plugin_info-manifest-reference)
3. [Writing a Resolver Plugin](#writing-a-resolver-plugin)
4. [Writing an Exporter Plugin](#writing-an-exporter-plugin)
5. [Writing a Scorer Plugin](#writing-a-scorer-plugin)
6. [Writing a Provider Plugin](#writing-a-provider-plugin)
7. [Adding a Locale](#adding-a-locale)
8. [Plugin Installation](#plugin-installation)
9. [API Versioning Rules](#api-versioning-rules)
10. [Testing Your Plugin](#testing-your-plugin)

---

## Overview of Plugin Types

NatBench supports five plugin types:

| Type       | ABC                   | Registration Key | What it does                           |
|------------|----------------------|-----------------|----------------------------------------|
| `resolver` | `ResolverPlugin`     | `protocol`      | Sends DNS queries over a transport     |
| `exporter` | `ExporterPlugin`     | `format`        | Writes results to a file format        |
| `scorer`   | `ScorerPlugin`       | `scorer_id`     | Computes a quality score 0–100         |
| `provider` | `ServerProviderPlugin` | `provider_id` | Supplies a list of DNS servers         |
| `locale`   | `LocalePlugin`       | `lang_code`     | Provides translated strings            |

Each plugin is a single `.py` file. Only one class per file is allowed.

---

## PLUGIN_INFO Manifest Reference

Every plugin module **must** expose a top-level `PLUGIN_INFO` dict:

```python
PLUGIN_INFO = {
    "name":        "My DoQ Resolver",      # human-readable display name
    "version":     "1.2.0",               # plugin's own semver (not NatBench's)
    "api_version": "1.0",                 # must match MAJOR of PLUGIN_API_VERSION
    "author":      "Alice <a@example.com>",
    "description": "DNS-over-QUIC resolver via aioquic",
    "type":        "resolver",            # resolver | exporter | scorer | provider | locale
    "protocol":    "doq",                 # type-specific key (see table below)
    "requires":    ["aioquic>=0.9"],      # optional pip packages (informational)
    "tags":        ["experimental"],      # optional tags
}
```

### Type-specific required fields

| Plugin type | Key field    | Example value         |
|-------------|-------------|-----------------------|
| resolver    | `protocol`  | `"doq"`, `"tcp"`      |
| exporter    | `format`    | `"yaml"`, `"pdf"`     |
| scorer      | `scorer_id` | `"latency_only"`      |
| provider    | `provider_id` | `"url"`, `"file"`   |
| locale      | `lang_code` | `"de"`, `"ja"`        |

### Required keys in `PLUGIN_INFO`

| Key           | Required | Description                                     |
|---------------|----------|-------------------------------------------------|
| `name`        | Yes      | Human-readable plugin name                      |
| `version`     | Yes      | Plugin semver string                            |
| `api_version` | Yes      | NatBench plugin API version (e.g. `"1.0"`)      |
| `type`        | Yes      | One of the five type strings above              |
| `protocol`    | Resolver | Registration key for this resolver              |
| `format`      | Exporter | Registration key for this exporter              |
| `scorer_id`   | Scorer   | Registration key for this scorer                |
| `provider_id` | Provider | Registration key for this provider              |
| `lang_code`   | Locale   | ISO-639-1 code for this locale plugin           |
| `author`      | No       | Author name and email                           |
| `description` | No       | One-line description                            |
| `requires`    | No       | List of pip package specs (informational)       |
| `tags`        | No       | List of string tags for filtering               |

---

## Writing a Resolver Plugin

A resolver plugin implements one DNS transport protocol. It must:

1. Expose `PLUGIN_INFO` at module level with `"type": "resolver"`.
2. Define a class that subclasses `ResolverPlugin`.
3. Set the `protocol` class attribute to a unique string.
4. Implement `query()` — **must never raise**, always return a `QueryResult`.

### Minimal example

```python
# ~/.natbench/plugins/resolvers/myproto.py

import time
from typing import Any
from natbench.plugin_base import QueryResult, ResolverPlugin
from natbench.core import build_dns_query, parse_dns_response

PLUGIN_INFO = {
    "name":        "My Custom Resolver",
    "version":     "1.0.0",
    "api_version": "1.0",
    "type":        "resolver",
    "protocol":    "myproto",
}

class MyProtoResolver(ResolverPlugin):
    protocol = "myproto"

    def query(self, server: dict[str, Any], domain: str,
              qtype: str = "A", timeout: float = 2.0) -> QueryResult:
        try:
            ip = server["ip4"]
            packet = build_dns_query(domain, 1)  # 1 = A record

            # ... your transport logic here ...
            t0 = time.perf_counter()
            response = my_transport_send(ip, packet, timeout)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            rcode, answer_count = parse_dns_response(response)
            return QueryResult(
                latency_ms=latency_ms,
                success=rcode in (0, 3),
                rcode=rcode,
                answer_count=answer_count,
                protocol="myproto",
            )
        except Exception as exc:
            return QueryResult(
                latency_ms=None, success=False, rcode=-1,
                protocol="myproto", error=str(exc),
            )
```

### `query()` contract

- **Never raise** — catch all exceptions.
- Return `QueryResult(success=False, error=str(exc))` on failure.
- `latency_ms` must be `None` when `success=False`.
- `rcode` should be `-1` when no response was received.
- Accept NXDOMAIN (rcode=3) as a successful response — it means the server
  is working, just the domain does not exist.

### Available fields in `server` dict

Common fields (not all servers have all fields):

| Field        | Type   | Description                                |
|-------------|--------|--------------------------------------------|
| `ip4`       | str    | IPv4 address                               |
| `ip6`       | str    | IPv6 address                               |
| `port`      | int    | Port (default 53 for UDP/TCP)              |
| `dot_host`  | str    | Hostname for DoT (port 853)                |
| `dot_port`  | int    | DoT port (default 853)                     |
| `doh_url`   | str    | Full URL for DoH endpoint                  |
| `name`      | str    | Human-readable server name                 |
| `country`   | str    | ISO country code                           |
| `operator`  | str    | Organisation name                          |
| `tags`      | list   | String tags                                |

---

## Writing an Exporter Plugin

An exporter plugin serialises benchmark results to a file.

```python
# ~/.natbench/plugins/exporters/yaml_exporter.py

import os
from typing import Any, Optional
from natbench.plugin_base import ExporterPlugin, ServerStats

PLUGIN_INFO = {
    "name":        "YAML Exporter",
    "version":     "1.0.0",
    "api_version": "1.0",
    "type":        "exporter",
    "format":      "yaml",
}

class YamlExporter(ExporterPlugin):
    format         = "yaml"
    file_extension = ".yaml"

    def export(self, results: list[ServerStats], filepath: str,
               *, lang: str = "en", meta: Optional[dict[str, Any]] = None) -> bool:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        # ... serialise results ...
        return True
```

### `export()` contract

- Create parent directories with `os.makedirs(..., exist_ok=True)`.
- Return `True` on success; raise or return `False` on failure.
- Include the `meta` dict in output for traceability.
- `lang` is provided for translated column headers — use `natbench.i18n.t()`.

### `ServerStats` fields available to exporters

| Field           | Type           | Description                               |
|----------------|----------------|-------------------------------------------|
| `server`       | dict           | Original server entry from SERVER_DB       |
| `score`        | float          | Composite quality score 0–100             |
| `avg_ms`       | float or None  | Mean latency over successful queries      |
| `median_ms`    | float or None  | Median latency                            |
| `p95_ms`       | float or None  | 95th percentile latency                   |
| `min_ms`       | float or None  | Minimum latency                           |
| `max_ms`       | float or None  | Maximum latency                           |
| `jitter_ms`    | float or None  | Standard deviation of latencies           |
| `success_rate` | float          | Fraction 0.0–1.0 of successful queries   |
| `dnssec_ok`    | bool or None   | DNSSEC validation enforced                |
| `malware_blocked` | bool or None | Known malware domains blocked            |
| `ads_blocked`  | bool or None   | Ad-serving domains blocked               |
| `queries`      | list           | Individual `QueryResult` objects          |

---

## Writing a Scorer Plugin

A scorer computes a quality score 0–100 for a `ServerStats` object.

```python
# ~/.natbench/plugins/scorers/my_scorer.py

from natbench.plugin_base import ScorerPlugin, ServerStats

PLUGIN_INFO = {
    "name":        "My Custom Scorer",
    "version":     "1.0.0",
    "api_version": "1.0",
    "type":        "scorer",
    "scorer_id":   "my_scorer",
}

class MyScorer(ScorerPlugin):
    scorer_id   = "my_scorer"
    scorer_name = "My Custom Scorer"

    def score(self, stats: ServerStats) -> float:
        # Pure function — no side effects on stats
        if stats.median_ms is None:
            return 0.0
        # Your formula here...
        raw = max(0.0, 100.0 - stats.median_ms)
        return max(0.0, min(100.0, raw))

    def weights(self) -> dict[str, float]:
        return {"speed": 1.0}
```

### `score()` contract

- **Must be pure** — do not modify `stats`.
- Return a float in `[0.0, 100.0]`.
- Handle `None` fields gracefully (latency fields are `None` if no successful queries).

---

## Writing a Provider Plugin

A provider supplies a list of server dicts.

```python
# ~/.natbench/plugins/providers/my_provider.py

from typing import Any
from natbench.plugin_base import ServerProviderPlugin

PLUGIN_INFO = {
    "name":        "My Provider",
    "version":     "1.0.0",
    "api_version": "1.0",
    "type":        "provider",
    "provider_id": "my_provider",
}

class MyProvider(ServerProviderPlugin):
    provider_id = "my_provider"

    def get_servers(self) -> list[dict[str, Any]]:
        return [
            {"name": "My DNS", "ip4": "10.0.0.1", "tags": ["private"]},
        ]
```

---

## Adding a Locale

The simplest way to add a language is to drop a JSON file into
`~/.natbench/locales/`:

```
~/.natbench/locales/ja.json
```

See `examples/custom_locale.json` for the full key list and structure.

The `_meta` block is purely informational:

```json
{
  "_meta": {
    "lang": "ja",
    "lang_name": "日本語",
    "author": "Your Name",
    "version": "1.0"
  },
  "app_name": "NatBench",
  "app_tagline": "DNS ベンチマーク & アナライザ",
  ...
}
```

All 50+ keys from `en.json` should be provided. Any key missing in your
locale will automatically fall back to the English string.

---

## Plugin Installation

### Option 1: User plugin directory (recommended)

Drop your plugin into the appropriate subdirectory:

```
~/.natbench/plugins/
  resolvers/    my_doq.py
  exporters/    yaml_exporter.py
  scorers/      my_scorer.py
  providers/    my_provider.py
```

These are loaded automatically on every NatBench run.

### Option 2: Environment variable

```bash
export NATBENCH_PLUGIN_PATH=/path/to/my/plugins
```

NatBench will scan `$NATBENCH_PLUGIN_PATH/resolvers/`, `.../exporters/`, etc.
Multiple paths can be separated by `:` (POSIX) or `;` (Windows).

### Option 3: Bundled (for distribution)

If you're shipping a package that adds NatBench plugins, place them in
`natbench/plugins/<type>/` in your package and ensure they're included in
`package_data`.

---

## API Versioning Rules

- `PLUGIN_API_VERSION` follows semver: currently `"1.0"`.
- Your plugin declares `"api_version": "1.0"` in `PLUGIN_INFO`.
- The **MAJOR** part must match exactly. A plugin declaring `"0.9"` will be
  rejected by NatBench 1.x.
- The **MINOR** part may differ. A plugin built for `"1.0"` will load fine
  under a future `"1.5"` runtime — the runtime offers more, never less.
- Breaking changes to ABCs (adding abstract methods, changing signatures) will
  bump the MAJOR version of `PLUGIN_API_VERSION`.

---

## Testing Your Plugin

### Quick smoke test

Every example file in `examples/` can be run directly:

```bash
python examples/custom_resolver.py
python examples/custom_exporter.py
```

### Unit tests

```python
# tests/test_my_plugin.py
import pytest
from my_plugin_file import MyProtoResolver

def test_query_returns_result():
    resolver = MyProtoResolver()
    server = {"ip4": "1.1.1.1", "port": 53}
    result = resolver.query(server, "example.com")
    # query() must never raise
    assert result is not None
    assert isinstance(result.success, bool)

def test_query_never_raises():
    resolver = MyProtoResolver()
    bad_server = {"ip4": "0.0.0.0", "port": 1}  # nothing listening here
    result = resolver.query(bad_server, "example.com", timeout=0.1)
    assert result.success is False
    assert result.error is not None

def test_plugin_info_valid():
    from natbench.plugin_loader import _validate_info
    from pathlib import Path
    from my_plugin_file import PLUGIN_INFO
    ok, reason = _validate_info(PLUGIN_INFO, Path("my_plugin_file.py"))
    assert ok, reason
```

Run with:

```bash
pytest tests/test_my_plugin.py -v
```

### Integration test via loader

```python
import os
from natbench.plugin_loader import PluginLoader

os.environ["NATBENCH_PLUGIN_PATH"] = "/path/to/your/plugins"
loader = PluginLoader()
loader.load_all()
assert "myproto" in loader.resolvers
```
