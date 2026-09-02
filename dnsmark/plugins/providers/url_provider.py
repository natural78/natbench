"""
dnsmark provider: URL
======================
Fetches a JSON server list from a remote URL.

Configuration:
  Set the environment variable DNSMARK_SERVER_URL to the URL of a JSON
  file containing a list of server dicts, e.g.:
    export DNSMARK_SERVER_URL=https://example.com/my-servers.json

  Alternatively, set "server_url" in ~/.dnsmark/config.json.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from dnsmark.plugin_base import ServerProviderPlugin

log = logging.getLogger(__name__)

PLUGIN_INFO = {
    "name":        "URL Server Provider",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "DNSMark contributors",
    "description": "Fetch a DNS server list from a remote JSON URL",
    "type":        "provider",
    "provider_id": "url",
    "requires":    [],
    "tags":        ["remote"],
}

_ENV_VAR = "DNSMARK_SERVER_URL"
_CONFIG_KEY = "server_url"
_TIMEOUT = 10.0


def _load_config() -> dict[str, Any]:
    """Load ~/.dnsmark/config.json if it exists."""
    config_path = os.path.join(os.path.expanduser("~"), ".dnsmark", "config.json")
    try:
        with open(config_path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


class UrlProvider(ServerProviderPlugin):
    """Fetch a server list from a remote JSON URL."""

    provider_id = "url"

    def __init__(self) -> None:
        # Prefer env var, fall back to config file
        self._url: str = (
            os.environ.get(_ENV_VAR, "")
            or _load_config().get(_CONFIG_KEY, "")
        )

    def get_servers(self) -> list[dict[str, Any]]:
        """Download and parse the remote server list. Returns [] on any error."""
        if not self._url:
            log.debug("UrlProvider: no URL configured")
            return []

        try:
            req = urllib.request.Request(
                self._url,
                headers={"User-Agent": "DNSMark/1.0", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                data = resp.read()

            servers = json.loads(data)
            if not isinstance(servers, list):
                log.warning("UrlProvider: response is not a JSON array")
                return []

            # Basic validation: each item must be a dict
            valid = [s for s in servers if isinstance(s, dict)]
            log.info("UrlProvider: loaded %d servers from %s", len(valid), self._url)
            return valid

        except urllib.error.URLError as exc:
            log.warning("UrlProvider: URL error fetching %s: %s", self._url, exc)
            return []
        except json.JSONDecodeError as exc:
            log.warning("UrlProvider: JSON parse error from %s: %s", self._url, exc)
            return []
        except Exception as exc:
            log.warning("UrlProvider: unexpected error: %s", exc)
            return []

    def is_available(self) -> bool:
        """Return True if a URL is configured."""
        return bool(self._url)
