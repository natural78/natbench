"""
dnsmark built-in provider: Builtin
====================================
Returns the built-in server database from dnsmark.servers.SERVER_DB.
"""

from __future__ import annotations

from typing import Any

from dnsmark.plugin_base import ServerProviderPlugin

PLUGIN_INFO = {
    "name":        "Builtin Server Provider",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "DNSMark contributors",
    "description": "Provides the bundled list of 72+ DNS servers",
    "type":        "provider",
    "provider_id": "builtin",
    "requires":    [],
    "tags":        ["builtin"],
}


class BuiltinProvider(ServerProviderPlugin):
    """Serves the bundled DNS server database."""

    provider_id = "builtin"

    def get_servers(self) -> list[dict[str, Any]]:
        """Return all servers from the bundled SERVER_DB."""
        from dnsmark.servers import SERVER_DB
        return list(SERVER_DB)

    def is_available(self) -> bool:
        return True
