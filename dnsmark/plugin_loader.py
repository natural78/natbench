"""
dnsmark.plugin_loader
=====================
Dynamic discovery, validation, and caching of DNSMark plugins.

Search order (first match per registration key wins):
  1. ``dnsmark/plugins/<type>/``           — built-in plugins
  2. ``~/.dnsmark/plugins/<type>/``        — user-installed plugins
  3. Dirs in ``DNSMARK_PLUGIN_PATH`` env   — extra paths (colon/semicolon-sep)

Each directory is scanned for ``*.py`` files (non-``__``-prefixed).
A module is accepted when it:
  * exposes a top-level ``PLUGIN_INFO`` dict with the required keys
  * passes PLUGIN_API_VERSION MAJOR check
  * contains exactly one class that subclasses the expected ABC

Loaded plugins are cached in-process; call :func:`reload_plugins` to bust.

Public API
----------
::

    from dnsmark.plugin_loader import PluginLoader

    loader = PluginLoader()

    # Access registries (dict keyed by protocol/format/scorer_id/provider_id)
    resolver  = loader.resolvers["udp"]
    exporter  = loader.exporters["json"]
    scorer    = loader.scorers["default"]
    provider  = loader.providers["builtin"]

    # Reload everything (e.g. after user installs a new plugin)
    loader.reload()
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Optional, Tuple, Type

from dnsmark.__version__ import PLUGIN_API_VERSION_INFO
from dnsmark.plugin_base import (
    ExporterPlugin,
    LocalePlugin,
    ResolverPlugin,
    ScorerPlugin,
    ServerProviderPlugin,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Sub-directory name per plugin type.
_TYPE_DIRS: dict[str, str] = {
    "resolver": "resolvers",
    "exporter": "exporters",
    "scorer":   "scorers",
    "provider": "providers",
    "locale":   "locales",
}

#: ABC that each plugin type must subclass.
_TYPE_ABC: dict[str, type] = {
    "resolver": ResolverPlugin,
    "exporter": ExporterPlugin,
    "scorer":   ScorerPlugin,
    "provider": ServerProviderPlugin,
    "locale":   LocalePlugin,
}

#: Required top-level keys in ``PLUGIN_INFO``.
_REQUIRED_INFO_KEYS = {"name", "version", "api_version", "type"}


# ---------------------------------------------------------------------------
# Helper: resolve search paths for a given plugin type
# ---------------------------------------------------------------------------

def _search_paths(plugin_type: str) -> List[Path]:
    """Return ordered list of directories to scan for *plugin_type* plugins."""
    sub = _TYPE_DIRS[plugin_type]
    paths: list[Path] = []

    # 1. Built-in plugins bundled with the package
    builtin = Path(__file__).parent / "plugins" / sub
    paths.append(builtin)

    # 2. User plugins in home directory
    user = Path.home() / ".dnsmark" / "plugins" / sub
    paths.append(user)

    # 3. DNSMARK_PLUGIN_PATH environment variable
    env_raw = os.environ.get("DNSMARK_PLUGIN_PATH", "")
    sep = ";" if sys.platform == "win32" else ":"
    for part in env_raw.split(sep):
        part = part.strip()
        if part:
            paths.append(Path(part) / sub)

    return paths


# ---------------------------------------------------------------------------
# Helper: load a single .py file as an anonymous module
# ---------------------------------------------------------------------------

def _load_module(path: Path) -> Optional[ModuleType]:
    """Import *path* as a module and return it, or ``None`` on error."""
    module_name = f"dnsmark._plugin_{path.stem}_{id(path)}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            log.debug("Cannot create spec for %s", path)
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception as exc:
        log.warning("Failed to load plugin %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# Helper: validate PLUGIN_INFO and API version
# ---------------------------------------------------------------------------

def _validate_info(info: object, path: Path) -> Tuple[bool, str]:
    """Return ``(ok, reason)``."""
    if not isinstance(info, dict):
        return False, "PLUGIN_INFO is not a dict"

    missing = _REQUIRED_INFO_KEYS - info.keys()
    if missing:
        return False, f"PLUGIN_INFO missing keys: {missing}"

    # API version MAJOR check
    declared: str = str(info.get("api_version", "0.0"))
    try:
        declared_major = int(declared.split(".")[0])
    except ValueError:
        return False, f"api_version not parseable: {declared!r}"

    runtime_major = PLUGIN_API_VERSION_INFO[0]
    if declared_major != runtime_major:
        return False, (
            f"api_version MAJOR mismatch: plugin declares {declared!r}, "
            f"runtime is {'.'.join(str(x) for x in PLUGIN_API_VERSION_INFO)}"
        )

    return True, ""


# ---------------------------------------------------------------------------
# Helper: find the plugin class inside a module
# ---------------------------------------------------------------------------

def _find_plugin_class(mod: ModuleType, plugin_type: str) -> Optional[type]:
    """Return the first class in *mod* that is a concrete subclass of the ABC."""
    abc_cls = _TYPE_ABC[plugin_type]
    for name in dir(mod):
        obj = getattr(mod, name)
        if (
            isinstance(obj, type)
            and issubclass(obj, abc_cls)
            and obj is not abc_cls
            and not getattr(obj, "__abstractmethods__", None)
        ):
            return obj
    return None


# ---------------------------------------------------------------------------
# Core loader
# ---------------------------------------------------------------------------

class PluginLoader:
    """Discover, validate and cache all DNSMark plugins.

    Instantiate once and pass around, or use the module-level singleton
    :data:`default_loader`.

    Attributes
    ----------
    resolvers:
        ``dict[protocol_str, ResolverPlugin instance]``
    exporters:
        ``dict[format_str, ExporterPlugin instance]``
    scorers:
        ``dict[scorer_id_str, ScorerPlugin instance]``
    providers:
        ``dict[provider_id_str, ServerProviderPlugin instance]``
    locale_plugins:
        ``dict[lang_code_str, LocalePlugin instance]``
    errors:
        List of ``(path, reason)`` tuples for plugins that failed to load.
    """

    def __init__(self) -> None:
        self.resolvers:      Dict[str, ResolverPlugin]      = {}
        self.exporters:      Dict[str, ExporterPlugin]      = {}
        self.scorers:        Dict[str, ScorerPlugin]        = {}
        self.providers:      Dict[str, ServerProviderPlugin]= {}
        self.locale_plugins: Dict[str, LocalePlugin]        = {}
        self.errors:         List[Tuple[str, str]]          = []
        self._loaded = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def load_all(self) -> "PluginLoader":
        """Discover and load all plugin types.  Idempotent (no-op if already loaded)."""
        if self._loaded:
            return self
        for plugin_type in _TYPE_DIRS:
            self._load_type(plugin_type)
        self._loaded = True
        log.info(
            "PluginLoader: %d resolvers, %d exporters, %d scorers, %d providers, %d locales loaded",
            len(self.resolvers), len(self.exporters),
            len(self.scorers), len(self.providers), len(self.locale_plugins),
        )
        return self

    def reload(self) -> "PluginLoader":
        """Clear all caches and re-scan all plugin directories."""
        self.resolvers.clear()
        self.exporters.clear()
        self.scorers.clear()
        self.providers.clear()
        self.locale_plugins.clear()
        self.errors.clear()
        self._loaded = False
        return self.load_all()

    def get_resolver(self, protocol: str) -> Optional[ResolverPlugin]:
        """Return resolver for *protocol* or ``None``."""
        self.load_all()
        return self.resolvers.get(protocol)

    def get_exporter(self, fmt: str) -> Optional[ExporterPlugin]:
        """Return exporter for *fmt* or ``None``."""
        self.load_all()
        return self.exporters.get(fmt)

    def get_scorer(self, scorer_id: str = "default") -> Optional[ScorerPlugin]:
        """Return scorer by *scorer_id* or ``None``."""
        self.load_all()
        return self.scorers.get(scorer_id)

    def get_provider(self, provider_id: str) -> Optional[ServerProviderPlugin]:
        """Return provider by *provider_id* or ``None``."""
        self.load_all()
        return self.providers.get(provider_id)

    def list_resolvers(self) -> List[str]:
        self.load_all(); return sorted(self.resolvers)

    def list_exporters(self) -> List[str]:
        self.load_all(); return sorted(self.exporters)

    def list_scorers(self) -> List[str]:
        self.load_all(); return sorted(self.scorers)

    def list_providers(self) -> List[str]:
        self.load_all(); return sorted(self.providers)

    def summary(self) -> str:
        """Human-readable summary of loaded plugins."""
        self.load_all()
        lines = [
            f"Resolvers  ({len(self.resolvers)}): "  + ", ".join(self.list_resolvers())  or "—",
            f"Exporters  ({len(self.exporters)}): "  + ", ".join(self.list_exporters())  or "—",
            f"Scorers    ({len(self.scorers)}): "    + ", ".join(self.list_scorers())    or "—",
            f"Providers  ({len(self.providers)}): "  + ", ".join(self.list_providers())  or "—",
        ]
        if self.errors:
            lines.append(f"Errors ({len(self.errors)}):")
            for p, r in self.errors:
                lines.append(f"  {p}: {r}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_type(self, plugin_type: str) -> None:
        """Scan all search paths for *plugin_type* and register plugins."""
        registry = self._registry_for(plugin_type)
        key_attr = self._key_attr_for(plugin_type)

        for search_dir in _search_paths(plugin_type):
            if not search_dir.is_dir():
                continue
            for py_file in sorted(search_dir.glob("*.py")):
                if py_file.stem.startswith("_"):
                    continue
                self._load_one(py_file, plugin_type, registry, key_attr)

    def _load_one(
        self,
        path: Path,
        plugin_type: str,
        registry: dict,
        key_attr: str,
    ) -> None:
        mod = _load_module(path)
        if mod is None:
            return

        info = getattr(mod, "PLUGIN_INFO", None)
        ok, reason = _validate_info(info, path)
        if not ok:
            log.warning("Skipping %s: %s", path, reason)
            self.errors.append((str(path), reason))
            return

        # Check that declared type matches the directory we're scanning
        declared_type = info.get("type", "")  # type: ignore[union-attr]
        if declared_type != plugin_type:
            reason = f"type mismatch: declared {declared_type!r}, expected {plugin_type!r}"
            log.warning("Skipping %s: %s", path, reason)
            self.errors.append((str(path), reason))
            return

        cls = _find_plugin_class(mod, plugin_type)
        if cls is None:
            reason = f"No concrete {plugin_type} class found"
            log.warning("Skipping %s: %s", path, reason)
            self.errors.append((str(path), reason))
            return

        try:
            instance = cls()
        except Exception as exc:
            reason = f"Instantiation failed: {exc}"
            log.warning("Skipping %s: %s", path, reason)
            self.errors.append((str(path), reason))
            return

        key = getattr(instance, key_attr, "")
        if not key:
            reason = f"Plugin class has empty {key_attr!r} attribute"
            log.warning("Skipping %s: %s", path, reason)
            self.errors.append((str(path), reason))
            return

        if key in registry:
            log.debug("Plugin %r overrides existing key %r", path.stem, key)

        registry[key] = instance
        log.debug("Loaded %s plugin %r from %s", plugin_type, key, path)

    def _registry_for(self, plugin_type: str) -> dict:
        return {
            "resolver": self.resolvers,
            "exporter": self.exporters,
            "scorer":   self.scorers,
            "provider": self.providers,
            "locale":   self.locale_plugins,
        }[plugin_type]

    @staticmethod
    def _key_attr_for(plugin_type: str) -> str:
        return {
            "resolver": "protocol",
            "exporter": "format",
            "scorer":   "scorer_id",
            "provider": "provider_id",
            "locale":   "lang_code",
        }[plugin_type]

    def __repr__(self) -> str:
        if not self._loaded:
            return "<PluginLoader (not yet loaded)>"
        return (
            f"<PluginLoader resolvers={list(self.resolvers)} "
            f"exporters={list(self.exporters)} "
            f"scorers={list(self.scorers)} "
            f"providers={list(self.providers)}>"
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

#: Shared loader instance — import and call ``.load_all()`` once at startup.
default_loader = PluginLoader()
