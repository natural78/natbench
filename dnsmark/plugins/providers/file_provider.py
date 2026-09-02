"""
dnsmark provider: File
=======================
Loads a JSON server list from a local file.

Configuration:
  Set the environment variable DNSMARK_SERVER_FILE to the path of a JSON
  file containing a list of server dicts, e.g.:
    export DNSMARK_SERVER_FILE=/home/user/my-servers.json

  The JSON file must contain an array of server objects.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dnsmark.plugin_base import ServerProviderPlugin

log = logging.getLogger(__name__)

PLUGIN_INFO = {
    "name":        "File Server Provider",
    "version":     "1.0.0",
    "api_version": "1.0",
    "author":      "DNSMark contributors",
    "description": "Load a DNS server list from a local JSON file",
    "type":        "provider",
    "provider_id": "file",
    "requires":    [],
    "tags":        [],
}

_ENV_VAR = "DNSMARK_SERVER_FILE"


class FileProvider(ServerProviderPlugin):
    """Load a server list from a local JSON file."""

    provider_id = "file"

    def __init__(self) -> None:
        self._path: str = os.environ.get(_ENV_VAR, "")

    def get_servers(self) -> list[dict[str, Any]]:
        """Read and parse the local JSON file. Returns [] on any error."""
        if not self._path:
            log.debug("FileProvider: DNSMARK_SERVER_FILE not set")
            return []

        path = os.path.expanduser(os.path.expandvars(self._path))

        if not os.path.isfile(path):
            log.warning("FileProvider: file not found: %s", path)
            return []

        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)

            if not isinstance(data, list):
                log.warning("FileProvider: JSON root is not an array in %s", path)
                return []

            valid = [s for s in data if isinstance(s, dict)]
            log.info("FileProvider: loaded %d servers from %s", len(valid), path)
            return valid

        except json.JSONDecodeError as exc:
            log.warning("FileProvider: JSON parse error in %s: %s", path, exc)
            return []
        except OSError as exc:
            log.warning("FileProvider: cannot read %s: %s", path, exc)
            return []
        except Exception as exc:
            log.warning("FileProvider: unexpected error reading %s: %s", path, exc)
            return []

    def is_available(self) -> bool:
        """Return True if DNSMARK_SERVER_FILE points to an existing file."""
        if not self._path:
            return False
        return os.path.isfile(os.path.expanduser(os.path.expandvars(self._path)))
