# Contributing to NatBench

Thank you for your interest in contributing! NatBench is an open project and welcomes pull requests, bug reports, new plugins, and translations.

---

## Ways to contribute

| Type | Description |
|------|-------------|
| **Bug report** | Open an [issue](https://github.com/natural78/natbench/issues) with steps to reproduce |
| **Feature request** | Open an issue describing the use case |
| **Code** | Fork → branch → PR |
| **Plugin** | New resolver/exporter/scorer (see `docs/PLUGIN_GUIDE.md`) |
| **Translation** | Add `natbench/locales/<lang>.json` (see `docs/LOCALE_GUIDE.md`) |
| **Server list** | Add entries to `natbench/servers.py` |

---

## Development setup

```bash
git clone https://github.com/natural78/natbench.git
cd natbench
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[rich,dev]"
```

Run tests:

```bash
pytest
```

---

## Code style

- Standard Python — no formatter enforced
- Keep dependencies to zero for the core (`natbench/` — stdlib only)
- Optional extras go in `[project.optional-dependencies]` in `pyproject.toml`
- Add tests in `tests/` for any non-trivial logic

---

## Adding a server to the database

Edit `natbench/servers.py` and follow the existing entry format:

```python
{
    "name": "Example DNS",
    "ip4": "1.2.3.4",
    "ip6": None,
    "doh_url": "https://dns.example.com/dns-query",
    "dot_host": "dns.example.com",
    "dot_port": 853,
    "port": 53,
    "country": "DE",
    "operator": "Example GmbH",
    "tags": ["no-log", "dnssec"],
    "description_en": "Privacy-focused resolver operated by Example GmbH.",
},
```

Required tags (where applicable): `malware`, `adblock`, `dnssec`, `no-log`, `anycast`, `fast`.

---

## Adding a language

1. Copy `natbench/locales/en.json` → `natbench/locales/<lang>.json`
2. Translate all string values (not the keys)
3. Update `_meta.lang` and `_meta.lang_name`
4. Add the code to `SUPPORTED_LANGS` in `natbench/i18n.py`
5. Add the native name to `LANG_NAMES` in `natbench/i18n.py`

The full guide is in `docs/LOCALE_GUIDE.md`.

---

## Pull request checklist

- [ ] `pytest` passes
- [ ] No new mandatory third-party dependencies
- [ ] Server entries have at least `ip4` or `doh_url` or `dot_host`
- [ ] Locale files have all 52 keys (check with `python -c "import json; d=json.load(open('natbench/locales/xx.json')); print(len([k for k in d if not k.startswith('_')]))"`)
