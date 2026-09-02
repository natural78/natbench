"""
Tests for the NatBench plugin system.

Validates:
- PluginLoader discovers built-in plugins
- Each plugin type has at least one registered entry
- PLUGIN_INFO validation rejects bad manifests
- API version check logic
- Plugin classes implement the correct ABCs
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from natbench.plugin_loader import PluginLoader, _validate_info
from natbench.plugin_base import (
    ExporterPlugin,
    ResolverPlugin,
    ScorerPlugin,
    ServerProviderPlugin,
)


# ---------------------------------------------------------------------------
# PluginLoader discovery
# ---------------------------------------------------------------------------

class TestPluginLoaderDiscovery:
    @pytest.fixture(scope="class")
    def loader(self):
        """A freshly loaded PluginLoader."""
        loader = PluginLoader()
        loader.load_all()
        return loader

    def test_has_resolvers(self, loader):
        assert len(loader.resolvers) >= 1, "At least one resolver must be loaded"

    def test_has_exporters(self, loader):
        assert len(loader.exporters) >= 1, "At least one exporter must be loaded"

    def test_has_scorers(self, loader):
        assert len(loader.scorers) >= 1, "At least one scorer must be loaded"

    def test_has_providers(self, loader):
        assert len(loader.providers) >= 1, "At least one provider must be loaded"

    def test_udp_resolver_present(self, loader):
        assert "udp" in loader.resolvers, "udp resolver must be built-in"

    def test_tcp_resolver_present(self, loader):
        assert "tcp" in loader.resolvers, "tcp resolver must be built-in"

    def test_dot_resolver_present(self, loader):
        assert "dot" in loader.resolvers

    def test_doh_resolver_present(self, loader):
        assert "doh" in loader.resolvers

    def test_json_exporter_present(self, loader):
        assert "json" in loader.exporters

    def test_csv_exporter_present(self, loader):
        assert "csv" in loader.exporters

    def test_markdown_exporter_present(self, loader):
        assert "markdown" in loader.exporters

    def test_html_exporter_present(self, loader):
        assert "html" in loader.exporters

    def test_default_scorer_present(self, loader):
        assert "default" in loader.scorers

    def test_latency_only_scorer_present(self, loader):
        assert "latency_only" in loader.scorers

    def test_builtin_provider_present(self, loader):
        assert "builtin" in loader.providers

    def test_summary_returns_string(self, loader):
        summary = loader.summary()
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_list_resolvers_sorted(self, loader):
        lst = loader.list_resolvers()
        assert lst == sorted(lst)

    def test_reload_is_idempotent(self):
        loader = PluginLoader()
        loader.load_all()
        count1 = len(loader.resolvers)
        loader.reload()
        count2 = len(loader.resolvers)
        assert count1 == count2

    def test_get_resolver_returns_instance(self, loader):
        resolver = loader.get_resolver("udp")
        assert isinstance(resolver, ResolverPlugin)

    def test_get_exporter_returns_instance(self, loader):
        exporter = loader.get_exporter("json")
        assert isinstance(exporter, ExporterPlugin)

    def test_get_scorer_returns_instance(self, loader):
        scorer = loader.get_scorer("default")
        assert isinstance(scorer, ScorerPlugin)

    def test_get_provider_returns_instance(self, loader):
        provider = loader.get_provider("builtin")
        assert isinstance(provider, ServerProviderPlugin)

    def test_unknown_key_returns_none(self, loader):
        assert loader.get_resolver("nonexistent_xyz") is None
        assert loader.get_exporter("nonexistent_xyz") is None


# ---------------------------------------------------------------------------
# PLUGIN_INFO validation
# ---------------------------------------------------------------------------

class TestPluginInfoValidation:
    def test_valid_info_passes(self):
        info = {
            "name":        "My Plugin",
            "version":     "1.0.0",
            "api_version": "1.0",
            "type":        "resolver",
        }
        ok, reason = _validate_info(info, Path("/fake/plugin.py"))
        assert ok, f"Valid info should pass but got: {reason}"

    def test_not_dict_fails(self):
        ok, reason = _validate_info("not a dict", Path("/fake/plugin.py"))
        assert not ok
        assert "not a dict" in reason

    def test_missing_name_fails(self):
        info = {"version": "1.0", "api_version": "1.0", "type": "resolver"}
        ok, reason = _validate_info(info, Path("/fake/plugin.py"))
        assert not ok
        assert "name" in reason

    def test_missing_version_fails(self):
        info = {"name": "X", "api_version": "1.0", "type": "resolver"}
        ok, reason = _validate_info(info, Path("/fake/plugin.py"))
        assert not ok

    def test_missing_api_version_fails(self):
        info = {"name": "X", "version": "1.0", "type": "resolver"}
        ok, reason = _validate_info(info, Path("/fake/plugin.py"))
        assert not ok

    def test_missing_type_fails(self):
        info = {"name": "X", "version": "1.0", "api_version": "1.0"}
        ok, reason = _validate_info(info, Path("/fake/plugin.py"))
        assert not ok

    def test_api_version_major_mismatch_fails(self):
        info = {
            "name":        "Old Plugin",
            "version":     "0.1.0",
            "api_version": "0.9",   # MAJOR=0, runtime MAJOR=1 → mismatch
            "type":        "resolver",
        }
        ok, reason = _validate_info(info, Path("/fake/plugin.py"))
        assert not ok
        assert "MAJOR mismatch" in reason or "mismatch" in reason.lower()

    def test_api_version_minor_difference_passes(self):
        """Plugin built for 1.0 should be accepted by runtime 1.x."""
        info = {
            "name":        "Fine Plugin",
            "version":     "1.0.0",
            "api_version": "1.0",
            "type":        "resolver",
        }
        ok, reason = _validate_info(info, Path("/fake/plugin.py"))
        assert ok, reason

    def test_unparseable_api_version_fails(self):
        info = {
            "name":        "Bad Plugin",
            "version":     "1.0.0",
            "api_version": "not-a-version",
            "type":        "resolver",
        }
        ok, reason = _validate_info(info, Path("/fake/plugin.py"))
        assert not ok


# ---------------------------------------------------------------------------
# Plugin class ABC conformance
# ---------------------------------------------------------------------------

class TestPluginAbcConformance:
    def test_udp_resolver_is_resolver_plugin(self):
        from natbench.plugins.resolvers.udp import UdpResolver
        assert issubclass(UdpResolver, ResolverPlugin)
        assert UdpResolver.protocol == "udp"

    def test_tcp_resolver_is_resolver_plugin(self):
        from natbench.plugins.resolvers.tcp import TcpResolver
        assert issubclass(TcpResolver, ResolverPlugin)
        assert TcpResolver.protocol == "tcp"

    def test_dot_resolver_is_resolver_plugin(self):
        from natbench.plugins.resolvers.dot import DotResolver
        assert issubclass(DotResolver, ResolverPlugin)
        assert DotResolver.protocol == "dot"

    def test_doh_resolver_is_resolver_plugin(self):
        from natbench.plugins.resolvers.doh import DohResolver
        assert issubclass(DohResolver, ResolverPlugin)
        assert DohResolver.protocol == "doh"

    def test_json_exporter_is_exporter_plugin(self):
        from natbench.plugins.exporters.json_exporter import JsonExporter
        assert issubclass(JsonExporter, ExporterPlugin)
        assert JsonExporter.format == "json"
        assert JsonExporter.file_extension == ".json"

    def test_csv_exporter_is_exporter_plugin(self):
        from natbench.plugins.exporters.csv_exporter import CsvExporter
        assert issubclass(CsvExporter, ExporterPlugin)
        assert CsvExporter.format == "csv"

    def test_markdown_exporter_is_exporter_plugin(self):
        from natbench.plugins.exporters.markdown_exporter import MarkdownExporter
        assert issubclass(MarkdownExporter, ExporterPlugin)
        assert MarkdownExporter.format == "markdown"

    def test_html_exporter_is_exporter_plugin(self):
        from natbench.plugins.exporters.html_exporter import HtmlExporter
        assert issubclass(HtmlExporter, ExporterPlugin)
        assert HtmlExporter.format == "html"

    def test_default_scorer_is_scorer_plugin(self):
        from natbench.plugins.scorers.default_scorer import DefaultScorer
        assert issubclass(DefaultScorer, ScorerPlugin)
        assert DefaultScorer.scorer_id == "default"

    def test_latency_only_scorer_is_scorer_plugin(self):
        from natbench.plugins.scorers.latency_only_scorer import LatencyOnlyScorer
        assert issubclass(LatencyOnlyScorer, ScorerPlugin)
        assert LatencyOnlyScorer.scorer_id == "latency_only"

    def test_builtin_provider_is_provider_plugin(self):
        from natbench.plugins.providers.builtin_provider import BuiltinProvider
        assert issubclass(BuiltinProvider, ServerProviderPlugin)
        assert BuiltinProvider.provider_id == "builtin"


# ---------------------------------------------------------------------------
# Resolver: is_available checks
# ---------------------------------------------------------------------------

class TestResolverAvailability:
    def test_udp_available_with_ip4(self, sample_server):
        from natbench.plugins.resolvers.udp import UdpResolver
        r = UdpResolver()
        assert r.is_available(sample_server) is True

    def test_udp_unavailable_without_ip(self):
        from natbench.plugins.resolvers.udp import UdpResolver
        r = UdpResolver()
        assert r.is_available({"name": "no-ip"}) is False

    def test_doh_available_with_url(self, sample_server):
        from natbench.plugins.resolvers.doh import DohResolver
        r = DohResolver()
        assert r.is_available(sample_server) is True

    def test_doh_unavailable_without_url(self):
        from natbench.plugins.resolvers.doh import DohResolver
        r = DohResolver()
        assert r.is_available({"ip4": "1.1.1.1"}) is False


# ---------------------------------------------------------------------------
# Provider: builtin returns non-empty list
# ---------------------------------------------------------------------------

class TestBuiltinProvider:
    def test_returns_list(self):
        from natbench.plugins.providers.builtin_provider import BuiltinProvider
        p = BuiltinProvider()
        servers = p.get_servers()
        assert isinstance(servers, list)
        assert len(servers) > 0

    def test_each_entry_has_name(self):
        from natbench.plugins.providers.builtin_provider import BuiltinProvider
        p = BuiltinProvider()
        for srv in p.get_servers():
            assert "name" in srv, f"Server entry missing 'name': {srv}"

    def test_is_always_available(self):
        from natbench.plugins.providers.builtin_provider import BuiltinProvider
        assert BuiltinProvider().is_available() is True
