"""
natbench.plugin_base
===================
Abstract base-classes (ABCs) for every NatBench plugin type.

Plugin authors import from this module:

    from natbench.plugin_base import ResolverPlugin, ExporterPlugin, ...

**Plugin manifest**
-------------------
Every plugin module (or package ``__init__.py``) must expose a top-level
``PLUGIN_INFO`` dict:

    PLUGIN_INFO = {
        "name":        "My DoQ Resolver",   # human-readable
        "version":     "1.2.0",             # plugin's own semver
        "api_version": "1.0",               # must match PLUGIN_API_VERSION
        "author":      "Alice <a@example.com>",
        "description": "DNS-over-QUIC resolver via aioquic",
        "type":        "resolver",          # resolver|exporter|scorer|provider
        "protocol":    "doq",               # plugin-type-specific key
        "requires":    ["aioquic>=0.9"],    # optional pip requirements
        "tags":        ["experimental"],    # optional tags
    }

The ``type`` field must match one of the four recognised plugin types.  The
``protocol`` (for resolvers) or ``format`` (for exporters) field is used as
the registration key under which the plugin is looked up at runtime.

**Plugin discovery**
--------------------
Search order (first match wins per key):

1. ``natbench/plugins/<type>/`` — built-in plugins bundled with the package
2. ``~/.natbench/plugins/<type>/`` — user-installed plugins
3. Directories listed in the ``NATBENCH_PLUGIN_PATH`` environment variable
   (colon-separated on POSIX, semicolon-separated on Windows)

Plugins are loaded lazily and cached by ``PluginLoader``.

**Versioning contract**
-----------------------
* The MAJOR part of ``PLUGIN_API_VERSION`` must equal the MAJOR part of the
  plugin's declared ``api_version`` for the plugin to be accepted.
* The MINOR part may differ; a plugin built for api_version "1.0" will load
  fine under api_version "1.3" (the runtime may offer *more*, never *less*).
* Breaking changes to any ABC in this file bump PLUGIN_API_VERSION MAJOR.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Callable, Generator, Optional


# ---------------------------------------------------------------------------
# Shared data-transfer types used across plugin types
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    """Result of a single DNS query attempt.

    Attributes
    ----------
    latency_ms:
        Round-trip time in milliseconds, or ``None`` when the query failed.
    success:
        ``True`` when the server returned a well-formed response (NOERROR or
        NXDOMAIN); ``False`` on timeout, connection error, or SERVFAIL.
    rcode:
        DNS RCODE from the response (0=NOERROR, 2=SERVFAIL, 3=NXDOMAIN …).
        ``-1`` when no response was received.
    answer_count:
        Number of records in the answer section (0 for NXDOMAIN / NODATA).
    protocol:
        The protocol used: ``"udp"`` | ``"tcp"`` | ``"dot"`` | ``"doh"``
        | ``"doq"`` (or any custom string from a resolver plugin).
    error:
        Optional error message for failed queries.
    """

    latency_ms:    Optional[float]
    success:       bool
    rcode:         int = -1
    answer_count:  int = 0
    protocol:      str = "udp"
    error:         Optional[str] = None


@dataclass
class ServerStats:
    """Aggregated benchmark result for one DNS server.

    Attributes
    ----------
    server:
        The server dict from ``servers.SERVER_DB`` (or a custom entry).
    queries:
        Individual ``QueryResult`` objects collected during the run.
    score:
        Weighted composite score 0–100 assigned by a ``ScorerPlugin``.
    dnssec_ok:
        Whether the server correctly validates DNSSEC (optional test).
    malware_blocked:
        Whether known malware domains are blocked (optional test).
    ads_blocked:
        Whether common ad-serving domains are blocked (optional test).
    median_ms / p95_ms / avg_ms / min_ms / max_ms / jitter_ms:
        Latency percentiles over successful queries only.
    success_rate:
        Fraction of successful queries (0.0–1.0).
    """

    server:          dict[str, Any]
    queries:         list[QueryResult] = field(default_factory=list)
    score:           float = 0.0
    dnssec_ok:       Optional[bool] = None
    malware_blocked: Optional[bool] = None
    ads_blocked:     Optional[bool] = None
    median_ms:       Optional[float] = None
    p95_ms:          Optional[float] = None
    avg_ms:          Optional[float] = None
    min_ms:          Optional[float] = None
    max_ms:          Optional[float] = None
    jitter_ms:       Optional[float] = None
    success_rate:    float = 0.0


# ---------------------------------------------------------------------------
# Progress callback type
# ---------------------------------------------------------------------------

#: Signature for progress callbacks:  cb(server_name, done_count, total_count)
ProgressCallback = Callable[[str, int, int], None]


# ---------------------------------------------------------------------------
# ABC: ResolverPlugin
# ---------------------------------------------------------------------------

class ResolverPlugin(abc.ABC):
    """Abstract base class for DNS resolver plugins.

    A resolver plugin encapsulates one transport protocol (UDP, TCP, DoT,
    DoH, DoQ, …) and exposes a single ``query`` method.

    **Required class attribute**

    ``protocol : str``
        Lower-case identifier used for registration, e.g. ``"udp"``,
        ``"doh"``.  Must be unique across all loaded resolver plugins.

    Example
    -------
    ::

        class MyDoQResolver(ResolverPlugin):
            protocol = "doq"

            def query(self, server, domain, qtype="A", timeout=2.0):
                ...  # aioquic logic
                return QueryResult(latency_ms=12.3, success=True,
                                   protocol="doq")
    """

    #: Protocol identifier — override in subclass.
    protocol: str = ""

    @abc.abstractmethod
    def query(
        self,
        server:  dict[str, Any],
        domain:  str,
        qtype:   str = "A",
        timeout: float = 2.0,
    ) -> QueryResult:
        """Execute a single DNS query.

        Parameters
        ----------
        server:
            Entry from ``servers.SERVER_DB`` (or equivalent dict).  Relevant
            fields vary by protocol; e.g. UDP uses ``server["ip4"]`` while
            DoH uses ``server["doh_url"]``.
        domain:
            Fully-qualified domain name to resolve (no trailing dot).
        qtype:
            Query type string: ``"A"``, ``"AAAA"``, ``"MX"``, ``"NS"``, …
        timeout:
            Maximum wait time in seconds.

        Returns
        -------
        QueryResult
            Always returns a ``QueryResult``; never raises.  Set
            ``success=False`` and fill ``error`` on failure.
        """

    def is_available(self, server: dict[str, Any]) -> bool:
        """Return ``True`` if *server* can be queried with this protocol.

        Default implementation checks for the protocol-specific key
        (``"ip4"`` for UDP/TCP, ``"doh_url"`` for DoH, etc.).  Override for
        custom logic.
        """
        proto_keys = {
            "udp": "ip4", "tcp": "ip4",
            "dot": "dot_host", "doh": "doh_url",
        }
        key = proto_keys.get(self.protocol)
        return bool(server.get(key)) if key else True

    def __repr__(self) -> str:
        return f"<ResolverPlugin protocol={self.protocol!r}>"


# ---------------------------------------------------------------------------
# ABC: ExporterPlugin
# ---------------------------------------------------------------------------

class ExporterPlugin(abc.ABC):
    """Abstract base class for result exporter plugins.

    An exporter serialises a list of :class:`ServerStats` to a file or
    stream in a specific format (JSON, CSV, Markdown, HTML, PDF, …).

    **Required class attribute**

    ``format : str``
        Lower-case format identifier, e.g. ``"json"``, ``"csv"``.
    ``file_extension : str``
        Default file extension including the dot, e.g. ``".json"``.
    """

    format:         str = ""
    file_extension: str = ""

    @abc.abstractmethod
    def export(
        self,
        results:  list[ServerStats],
        filepath: str,
        *,
        lang:     str = "en",
        meta:     Optional[dict[str, Any]] = None,
    ) -> bool:
        """Serialise *results* to *filepath*.

        Parameters
        ----------
        results:
            Sorted list of :class:`ServerStats` (best first).
        filepath:
            Destination path.  The plugin must create parent directories if
            needed or raise ``OSError``.
        lang:
            ISO-639-1 language code for translated column headers.
        meta:
            Optional dict with benchmark metadata (timestamp, protocol used,
            query count, …) to embed in the output.

        Returns
        -------
        bool
            ``True`` on success.  Raise ``Exception`` or return ``False`` on
            failure.
        """

    def preview(
        self,
        results:  list[ServerStats],
        max_rows: int = 10,
        lang:     str = "en",
    ) -> str:
        """Return a short string preview (for GUI preview pane).

        Default: calls ``export`` to a StringIO-like temp file if possible,
        otherwise returns a placeholder.  Override for efficiency.
        """
        return f"[{self.format.upper()} export — {len(results)} servers]"

    def __repr__(self) -> str:
        return f"<ExporterPlugin format={self.format!r}>"


# ---------------------------------------------------------------------------
# ABC: ScorerPlugin
# ---------------------------------------------------------------------------

class ScorerPlugin(abc.ABC):
    """Abstract base class for scoring algorithm plugins.

    A scorer assigns a composite quality score (0–100) to a
    :class:`ServerStats` object.  Only one scorer is active at a time;
    the active scorer can be configured in ``~/.natbench/config.json`` or
    via ``--scorer`` CLI flag.

    **Required class attribute**

    ``scorer_id : str``
        Unique identifier, e.g. ``"default"``, ``"latency_only"``.
    ``scorer_name : str``
        Human-readable name shown in the GUI.
    """

    scorer_id:   str = ""
    scorer_name: str = ""

    @abc.abstractmethod
    def score(self, stats: ServerStats) -> float:
        """Compute and return a score in [0.0, 100.0].

        The method **must** be pure (no side-effects on *stats*).  The caller
        will assign the returned value to ``stats.score``.

        Parameters
        ----------
        stats:
            Populated :class:`ServerStats` (latency fields and security
            booleans already set).

        Returns
        -------
        float
            Score in [0.0, 100.0].  Higher is better.
        """

    def describe(self) -> str:
        """Return a one-sentence description of the scoring method.

        Used in the GUI tooltip / CLI ``--scorer-info`` output.
        """
        return f"Scorer: {self.scorer_name}"

    def weights(self) -> dict[str, float]:
        """Return a dict of weight names → fractions summing to 1.0.

        Example: ``{"speed": 0.5, "reliability": 0.3, "consistency": 0.1,
        "security": 0.1}``

        Used by the GUI to show a breakdown chart.  Return ``{}`` if not
        applicable.
        """
        return {}

    def __repr__(self) -> str:
        return f"<ScorerPlugin id={self.scorer_id!r}>"


# ---------------------------------------------------------------------------
# ABC: ServerProviderPlugin
# ---------------------------------------------------------------------------

class ServerProviderPlugin(abc.ABC):
    """Abstract base class for DNS server list providers.

    A provider yields a list of server dicts compatible with
    ``servers.SERVER_DB`` entries.  Multiple providers are merged at runtime;
    duplicate IPs (``ip4`` field) are deduplicated (last provider wins).

    **Required class attribute**

    ``provider_id : str``
        Unique identifier, e.g. ``"builtin"``, ``"url"``, ``"file"``.
    """

    provider_id: str = ""

    @abc.abstractmethod
    def get_servers(self) -> list[dict[str, Any]]:
        """Return a list of server dicts.

        Each dict should have at minimum: ``name``, ``ip4`` OR ``doh_url``.
        Additional optional fields: ``ip6``, ``dot_host``, ``dot_port``,
        ``port``, ``country``, ``operator``, ``tags``, ``description_en``.

        Returns
        -------
        list[dict]
            May be empty if no servers are available / reachable.
        """

    def iter_servers(self) -> Generator[dict[str, Any], None, None]:
        """Generator variant of :meth:`get_servers`.

        Override for streaming / lazy loading.  Default delegates to
        :meth:`get_servers`.
        """
        yield from self.get_servers()

    def is_available(self) -> bool:
        """Return ``True`` if this provider can currently supply servers.

        For network-based providers, this may do a quick connectivity check.
        Default always returns ``True``.
        """
        return True

    def __repr__(self) -> str:
        return f"<ServerProviderPlugin id={self.provider_id!r}>"


# ---------------------------------------------------------------------------
# ABC: LocalePlugin  (optional, for GUI extensions)
# ---------------------------------------------------------------------------

class LocalePlugin(abc.ABC):
    """Optional plugin type for adding or overriding locale strings.

    Most users add a language simply by dropping a ``<lang>.json`` file into
    ``~/.natbench/locales/``.  This plugin type is for programmatic locale
    injection (e.g., from a database or remote source).

    **Required class attribute**

    ``lang_code : str``
        ISO-639-1 language code this plugin provides.
    """

    lang_code: str = ""

    @abc.abstractmethod
    def get_strings(self) -> dict[str, str]:
        """Return the full dict of translation strings for ``lang_code``."""
