"""
natbench.profiles
=================
Named test profile management.

Profiles are stored as JSON in ~/.natbench/profiles/.
Built-in example profiles ship in natbench/profiles/.

Profile search order: user dir → built-in dir (user wins).
"""

from __future__ import annotations

import copy
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROFILE_SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Default profile values
# ---------------------------------------------------------------------------

DEFAULT_PROFILE: dict[str, Any] = {
    "name": "",
    "description": "",
    "protocol": "udp",
    "count": 10,
    "timeout": 2.0,
    "workers": 20,
    "scorer": "default",
    "top": None,
    "servers": "all",
    "include_system_dns": True,
    "export": {"format": None, "path": None, "auto_open": False},
    "vpn": {
        "enabled": False,
        "name": None,
        "type": None,
        "connect_cmd": None,
        "disconnect_cmd": None,
        "verify_changed": True,
        "wait_seconds": 3,
        "restore_on_exit": True,
    },
    "tags": [],
}

# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------


def _user_profile_dir() -> Path:
    """Return ~/.natbench/profiles/ — the user's profile directory."""
    return Path.home() / ".natbench" / "profiles"


def _builtin_profile_dir() -> Path:
    """Return the built-in profiles directory shipped with the package."""
    return Path(__file__).parent / "profiles"


def get_profile_dirs() -> list[Path]:
    """Returns [builtin_dir, user_dir] — both may not exist."""
    return [_builtin_profile_dir(), _user_profile_dir()]


# ---------------------------------------------------------------------------
# List / search
# ---------------------------------------------------------------------------


def list_profiles() -> list[dict]:
    """
    Return list of {name, path, description, tags, vpn_enabled} dicts,
    all profiles found.

    User profiles override built-in profiles with the same name.
    """
    found: dict[str, dict] = {}  # name → entry dict

    # Walk built-in first, then user (user wins on name collision)
    for profile_dir in get_profile_dirs():
        if not profile_dir.is_dir():
            continue
        for json_file in sorted(profile_dir.glob("*.json")):
            try:
                with json_file.open(encoding="utf-8") as fh:
                    raw = json.load(fh)
            except (OSError, json.JSONDecodeError):
                continue

            stem = json_file.stem
            display_name = raw.get("name") or stem
            found[stem] = {
                "name": stem,
                "display_name": display_name,
                "path": str(json_file),
                "description": raw.get("description", ""),
                "tags": raw.get("tags", []),
                "vpn_enabled": bool(raw.get("vpn", {}).get("enabled", False)),
                "is_builtin": profile_dir == _builtin_profile_dir(),
            }

    return sorted(found.values(), key=lambda e: e["name"])


# ---------------------------------------------------------------------------
# Load / save / delete
# ---------------------------------------------------------------------------


def _merge_with_defaults(raw: dict) -> dict:
    """Deep-merge *raw* on top of DEFAULT_PROFILE. Nested dicts are merged."""
    result = copy.deepcopy(DEFAULT_PROFILE)

    for key, default_val in DEFAULT_PROFILE.items():
        if key not in raw:
            continue
        raw_val = raw[key]
        if isinstance(default_val, dict) and isinstance(raw_val, dict):
            merged_sub = copy.deepcopy(default_val)
            merged_sub.update(raw_val)
            result[key] = merged_sub
        else:
            result[key] = raw_val

    # Preserve any extra top-level keys from the file (e.g. _meta)
    for key in raw:
        if key not in result:
            result[key] = raw[key]

    return result


def load_profile(name: str) -> dict:
    """
    Load profile by name. Merges with DEFAULT_PROFILE.

    Search order: user dir first, then built-in dir.

    Raises:
        FileNotFoundError: if no profile with *name* exists.
    """
    # User profiles take priority
    for profile_dir in reversed(get_profile_dirs()):
        path = profile_dir / f"{name}.json"
        if path.is_file():
            try:
                with path.open(encoding="utf-8") as fh:
                    raw = json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"Cannot read profile {name!r}: {exc}") from exc
            return _merge_with_defaults(raw)

    raise FileNotFoundError(f"Profile {name!r} not found in any profile directory")


def save_profile(profile: dict, name: str | None = None) -> Path:
    """
    Save profile to ~/.natbench/profiles/<name>.json.

    Sets _meta.created (first save) and _meta.modified (every save).

    Args:
        profile: Profile dict (will be modified in-place with _meta).
        name:    Override file stem. If None, uses profile["name"] (slugified).

    Returns:
        Path to the saved file.

    Raises:
        ValueError: if no name can be determined.
    """
    stem = name or profile.get("name") or ""
    if not stem:
        raise ValueError("Profile must have a name or a name must be provided")

    # Slugify: lowercase, spaces → underscores, keep alphanum/dash/underscore
    safe_stem = _slugify(stem)
    if not safe_stem:
        raise ValueError(f"Profile name {stem!r} produces an empty slug")

    dest_dir = _user_profile_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{safe_stem}.json"

    now_iso = datetime.now(tz=timezone.utc).isoformat()

    meta = profile.get("_meta", {})
    if not isinstance(meta, dict):
        meta = {}
    if "created" not in meta:
        meta["created"] = now_iso
    meta["modified"] = now_iso
    meta["natbench_profile"] = PROFILE_SCHEMA_VERSION

    profile = dict(profile)  # shallow copy so we don't mutate caller's dict
    profile["_meta"] = meta

    with dest_path.open("w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    return dest_path


def _slugify(text: str) -> str:
    """Convert text to a safe filename stem."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s]+", "_", slug)
    slug = re.sub(r"[_-]+", "_", slug)
    return slug.strip("_-")


def delete_profile(name: str) -> bool:
    """
    Delete user profile by name.

    Returns:
        True if deleted, False if not found in user dir.

    Raises:
        PermissionError: if the profile is built-in.
    """
    builtin_path = _builtin_profile_dir() / f"{name}.json"
    if builtin_path.is_file():
        raise PermissionError(f"Profile {name!r} is a built-in profile and cannot be deleted")

    user_path = _user_profile_dir() / f"{name}.json"
    if user_path.is_file():
        user_path.unlink()
        return True

    return False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_VALID_PROTOCOLS = {"udp", "tcp", "dot", "doh"}
_VALID_SCORERS = {"default", "latency_only"}
_VALID_VPN_TYPES = {"wireguard", "openvpn", "nordvpn", "mullvad", "custom"}


def validate_profile(profile: dict) -> list[str]:
    """
    Validate a profile dict.

    Returns:
        List of validation error strings. Empty list means valid.
    """
    errors: list[str] = []

    if not profile.get("name"):
        errors.append("'name' is required and must not be empty")

    protocol = profile.get("protocol", "udp")
    if protocol not in _VALID_PROTOCOLS:
        errors.append(
            f"'protocol' must be one of {sorted(_VALID_PROTOCOLS)}, got {protocol!r}"
        )

    count = profile.get("count", 10)
    if not isinstance(count, int) or count < 1:
        errors.append(f"'count' must be a positive integer, got {count!r}")

    timeout = profile.get("timeout", 2.0)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        errors.append(f"'timeout' must be a positive number, got {timeout!r}")

    workers = profile.get("workers", 20)
    if not isinstance(workers, int) or workers < 1:
        errors.append(f"'workers' must be a positive integer, got {workers!r}")

    scorer = profile.get("scorer", "default")
    if not isinstance(scorer, str) or not scorer:
        errors.append("'scorer' must be a non-empty string")

    top = profile.get("top")
    if top is not None and (not isinstance(top, int) or top < 1):
        errors.append(f"'top' must be a positive integer or null, got {top!r}")

    if not isinstance(profile.get("include_system_dns", True), bool):
        errors.append("'include_system_dns' must be a boolean")

    # Export section
    export = profile.get("export", {})
    if isinstance(export, dict):
        exp_format = export.get("format")
        if exp_format is not None and not isinstance(exp_format, str):
            errors.append("'export.format' must be a string or null")
    elif export is not None:
        errors.append("'export' must be an object or null")

    # VPN section
    vpn = profile.get("vpn", {})
    if isinstance(vpn, dict) and vpn.get("enabled"):
        vpn_type = vpn.get("type")
        if vpn_type is not None and vpn_type not in _VALID_VPN_TYPES:
            errors.append(
                f"'vpn.type' must be one of {sorted(_VALID_VPN_TYPES)}, got {vpn_type!r}"
            )
        wait = vpn.get("wait_seconds", 3)
        if not isinstance(wait, (int, float)) or wait < 0:
            errors.append(f"'vpn.wait_seconds' must be a non-negative number, got {wait!r}")
    elif vpn is not None and not isinstance(vpn, dict):
        errors.append("'vpn' must be an object")

    return errors


# ---------------------------------------------------------------------------
# Profile → benchmark kwargs
# ---------------------------------------------------------------------------


def profile_to_args(profile: dict) -> dict:
    """
    Convert a profile dict to flat kwargs dict suitable for run_benchmark().

    Maps profile fields to the parameter names expected by core.run_benchmark()
    and related functions.

    Returns:
        dict with keys: n_queries, timeout, protocol, max_workers, scorer,
        top, servers, include_system_dns, export, vpn, tags.
    """
    return {
        "n_queries": profile.get("count", DEFAULT_PROFILE["count"]),
        "timeout": profile.get("timeout", DEFAULT_PROFILE["timeout"]),
        "protocol": profile.get("protocol", DEFAULT_PROFILE["protocol"]),
        "max_workers": profile.get("workers", DEFAULT_PROFILE["workers"]),
        "scorer": profile.get("scorer", DEFAULT_PROFILE["scorer"]),
        "top": profile.get("top"),
        "servers": profile.get("servers", DEFAULT_PROFILE["servers"]),
        "include_system_dns": profile.get(
            "include_system_dns", DEFAULT_PROFILE["include_system_dns"]
        ),
        "export": profile.get("export", copy.deepcopy(DEFAULT_PROFILE["export"])),
        "vpn": profile.get("vpn", copy.deepcopy(DEFAULT_PROFILE["vpn"])),
        "tags": profile.get("tags", []),
    }


# ---------------------------------------------------------------------------
# Import / Export (file-level)
# ---------------------------------------------------------------------------


def import_profile(path: str | Path) -> dict:
    """
    Load a profile from an arbitrary file path.

    Validates the profile and returns the merged (with defaults) profile dict.

    Raises:
        FileNotFoundError: if *path* does not exist.
        ValueError:        if the file is not valid JSON or fails validation.
    """
    src = Path(path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Profile file not found: {src}")

    try:
        with src.open(encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {src}: {exc}") from exc

    merged = _merge_with_defaults(raw)
    errors = validate_profile(merged)
    if errors:
        raise ValueError(
            f"Profile {src} has validation errors:\n  " + "\n  ".join(errors)
        )

    return merged


def export_profile(name: str, dest: str | Path) -> Path:
    """
    Copy a profile file (by name) to *dest* path.

    *dest* may be a directory (the file will be placed inside with its
    original filename) or a full file path.

    Returns:
        The destination path written.

    Raises:
        FileNotFoundError: if profile *name* is not found.
    """
    # Locate source
    src_path: Path | None = None
    for profile_dir in reversed(get_profile_dirs()):
        candidate = profile_dir / f"{name}.json"
        if candidate.is_file():
            src_path = candidate
            break

    if src_path is None:
        raise FileNotFoundError(f"Profile {name!r} not found")

    dest_path = Path(dest).expanduser()
    if dest_path.is_dir():
        dest_path = dest_path / src_path.name

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dest_path)
    return dest_path
