# NatBench Profile Guide

Profiles let you save and reuse benchmark configurations. Instead of typing
the same flags every time, you create a profile once and run it by name.

---

## Table of Contents

1. [What are Profiles?](#what-are-profiles)
2. [Profile Storage Locations](#profile-storage-locations)
3. [Profile Fields Reference](#profile-fields-reference)
4. [VPN Section](#vpn-section)
5. [Creating a Custom Profile](#creating-a-custom-profile)
6. [Sharing Profiles](#sharing-profiles)
7. [CLI Examples](#cli-examples)
8. [VPN Comparison Workflow](#vpn-comparison-workflow)

---

## What are Profiles?

A profile is a JSON file that stores all benchmark settings: protocol, query
count, timeout, VPN configuration, export options, and more. NatBench ships
with a set of built-in profiles for common use cases. You can create your own
user profiles that override the built-ins.

---

## Profile Storage Locations

| Location | Purpose | Editable |
|----------|---------|---------|
| `natbench/profiles/` (inside package) | Built-in profiles shipped with NatBench | No — reinstall to update |
| `~/.natbench/profiles/` | Your personal profiles | Yes |

**Search order:** User directory is checked first. A user profile with the
same stem name as a built-in profile overrides it.

---

## Profile Fields Reference

### Top-level fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | `""` | Human-readable display name |
| `description` | string | `""` | Short explanation of what this profile tests |
| `protocol` | string | `"udp"` | DNS transport: `udp`, `tcp`, `dot`, `doh` |
| `count` | integer | `10` | Queries per server for latency measurement |
| `timeout` | float | `2.0` | Per-query socket timeout in seconds |
| `workers` | integer | `20` | Thread-pool size (parallel servers) |
| `scorer` | string | `"default"` | Scoring algorithm: `default`, `latency_only`, or a plugin scorer ID |
| `top` | integer or null | `null` | Show only the top N results; `null` = show all |
| `servers` | string | `"all"` | Server set: `"all"` or `"secure"` (privacy/DNSSEC-capable only) |
| `include_system_dns` | boolean | `true` | Add the system/ISP DNS to the tested set |
| `tags` | array of strings | `[]` | Arbitrary labels for filtering/display |

### `export` object

Controls automatic result export after the benchmark completes.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | string or null | `null` | Export format: `"html"`, `"json"`, `"csv"`, `"md"` (or a plugin format), `null` = no export |
| `path` | string or null | `null` | Output directory or full file path (`~` is expanded). `null` = current directory |
| `auto_open` | boolean | `false` | Open the exported file in the default application after saving |

### `vpn` object

See the [VPN Section](#vpn-section) for details.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `false` | Whether to connect a VPN before benchmarking |
| `name` | string or null | `null` | Display name for the VPN (shown in output) |
| `type` | string or null | `null` | VPN client type: `wireguard`, `openvpn`, `nordvpn`, `mullvad`, `custom` |
| `connect_cmd` | string or null | `null` | Shell command to connect (used by `wireguard`, `openvpn`, `custom`) |
| `disconnect_cmd` | string or null | `null` | Shell command to disconnect |
| `verify_changed` | boolean | `true` | Fail if the public IP did not change after connecting |
| `wait_seconds` | integer | `3` | Seconds to wait after connect before starting the benchmark |
| `restore_on_exit` | boolean | `true` | Disconnect the VPN after the benchmark finishes |

---

## VPN Section

NatBench can connect a VPN before benchmarking and disconnect it afterwards.
This lets you measure DNS performance from inside a VPN tunnel and compare it
to your baseline.

### Supported VPN Clients

| Type | Required binary | Connect logic |
|------|----------------|---------------|
| `wireguard` | `wg-quick` | `wg-quick up <iface>` / `wg-quick down <iface>` |
| `openvpn` | `openvpn` | `openvpn --config <file> --daemon` / `pkill -f openvpn` |
| `nordvpn` | `nordvpn` | `nordvpn connect` / `nordvpn disconnect` |
| `mullvad` | `mullvad` | `mullvad connect` / `mullvad disconnect` |
| `custom` | any | Arbitrary `connect_cmd` / `disconnect_cmd` from config |

Installed clients are detected automatically — run `natbench --list-vpn-clients`
to see what NatBench found on your system.

### Configuring WireGuard

```json
"vpn": {
  "enabled": true,
  "name": "My WireGuard VPN",
  "type": "wireguard",
  "connect_cmd": "wg-quick up wg0",
  "disconnect_cmd": "wg-quick down wg0",
  "verify_changed": true,
  "wait_seconds": 3,
  "restore_on_exit": true
}
```

Replace `wg0` with your WireGuard interface name. The config file must
already exist in `/etc/wireguard/wg0.conf` (or wherever `wg-quick` expects it).
Running `wg-quick up` typically requires root/sudo.

### Configuring OpenVPN

```json
"vpn": {
  "enabled": true,
  "name": "My OpenVPN",
  "type": "openvpn",
  "connect_cmd": "sudo openvpn --config /etc/openvpn/client.conf --daemon",
  "disconnect_cmd": "sudo pkill openvpn",
  "verify_changed": true,
  "wait_seconds": 10,
  "restore_on_exit": true
}
```

OpenVPN may need several seconds to establish a connection; set
`wait_seconds` to at least 8–10.

### Configuring NordVPN

```json
"vpn": {
  "enabled": true,
  "name": "NordVPN",
  "type": "nordvpn",
  "verify_changed": true,
  "wait_seconds": 5,
  "restore_on_exit": true
}
```

The NordVPN CLI must be installed and you must already be logged in
(`nordvpn login`). No `connect_cmd` or `disconnect_cmd` needed — NatBench
uses `nordvpn connect` / `nordvpn disconnect` automatically.

### Configuring Mullvad

```json
"vpn": {
  "enabled": true,
  "name": "Mullvad",
  "type": "mullvad",
  "verify_changed": true,
  "wait_seconds": 5,
  "restore_on_exit": true
}
```

Same pattern as NordVPN. Requires the Mullvad desktop app or CLI.

### Using a Custom VPN

```json
"vpn": {
  "enabled": true,
  "name": "ProtonVPN",
  "type": "custom",
  "connect_cmd": "protonvpn-cli connect --fastest",
  "disconnect_cmd": "protonvpn-cli disconnect",
  "verify_changed": true,
  "wait_seconds": 8,
  "restore_on_exit": true
}
```

Any shell command works. The command is split with `shlex.split()` — use
shell quoting for paths with spaces.

### IP Verification

When `verify_changed` is `true` (the default), NatBench queries
`api.ipify.org` before and after connecting. If the public IP is the same,
it raises an error and disconnects. This prevents silent VPN failures from
contaminating benchmark data.

Set `verify_changed` to `false` if your VPN is a split-tunnel or if IP
checking causes false positives.

---

## Creating a Custom Profile

1. Create the user profile directory if it does not exist:

   ```bash
   mkdir -p ~/.natbench/profiles
   ```

2. Write your profile JSON. Minimal example:

   ```json
   {
     "_meta": {"natbench_profile": "1.0"},
     "name": "Home - ISP vs Alternatives",
     "description": "Compare ISP DNS against privacy resolvers from home network",
     "protocol": "udp",
     "count": 20,
     "timeout": 2.0,
     "workers": 20,
     "scorer": "default",
     "top": null,
     "servers": "all",
     "include_system_dns": true,
     "export": {
       "format": "html",
       "path": "~/natbench-results/",
       "auto_open": false
     },
     "vpn": {
       "enabled": false
     },
     "tags": ["home"]
   }
   ```

3. Save as `~/.natbench/profiles/home_isp.json`. The file stem (`home_isp`)
   becomes the profile name used with `--profile`.

4. Run it:

   ```bash
   natbench --profile home_isp
   ```

You can also create and save profiles interactively from the CLI:

```bash
natbench --save-profile my_profile \
  --protocol udp --count 20 --timeout 2 --workers 20
```

Or copy and modify an existing built-in:

```bash
natbench --export-profile speed ~/.natbench/profiles/my_speed.json
# Edit my_speed.json, then:
natbench --import-profile ~/.natbench/profiles/my_speed.json
natbench --profile my_speed
```

Fields you omit are filled in from the built-in defaults, so you only need
to specify what you want to change.

---

## Sharing Profiles

Profiles are self-contained JSON files with no system-specific paths (unless
your VPN commands reference absolute paths). To share a profile:

1. Export it to a file:

   ```bash
   natbench --export-profile my_profile /tmp/my_profile.json
   ```

2. Share the file (email, paste, git, etc.).

3. Recipient imports it:

   ```bash
   natbench --import-profile /path/to/my_profile.json
   ```

The profile is validated on import; invalid profiles are rejected with a
clear error message.

For VPN profiles: recipients must adapt the `connect_cmd` / `disconnect_cmd`
to their own VPN interface names and file paths before using them.

---

## CLI Examples

### List all available profiles

```bash
natbench --list-profiles
```

Output shows name, description, tags, and whether VPN is enabled:

```
Built-in profiles:
  speed           Speed Only              [speed, quick]
  security        Security & Privacy      [security, privacy, dnssec]
  doh             DNS-over-HTTPS          [doh, encrypted, privacy]
  isp_comparison  ISP vs Alternatives     [isp, comparison]
  vpn_wireguard   VPN WireGuard Test      [vpn, wireguard]  (VPN)
  vpn_mullvad     Mullvad VPN Test        [vpn, mullvad]    (VPN)
  vpn_nordvpn     NordVPN Test            [vpn, nordvpn]    (VPN)
  full            Full Comprehensive      [full, comprehensive]
  quick           Quick Check             [quick, speed]

User profiles:
  home_isp        Home - ISP vs Alt.      [home]
```

### Run a built-in profile

```bash
natbench --profile speed
natbench --profile quick
natbench --profile full
natbench --profile security
natbench --profile doh
```

### Run a VPN profile

```bash
# Requires Mullvad CLI installed and configured
natbench --profile vpn_mullvad

# WireGuard (may need sudo for wg-quick)
sudo natbench --profile vpn_wireguard
```

### Save current flags as a profile

```bash
natbench --protocol udp --count 25 --timeout 2 --workers 20 \
  --save-profile my_udp_25
```

### Import a profile from a file

```bash
natbench --import-profile /tmp/colleague_profile.json
```

### Export a profile to a file

```bash
natbench --export-profile speed ~/Desktop/speed_profile.json
```

### Override a profile field on the fly

Flags on the command line always override profile values:

```bash
# Use the "full" profile but with a shorter timeout
natbench --profile full --timeout 1.5
```

---

## VPN Comparison Workflow

This workflow runs the benchmark twice — once without VPN and once with —
so you can compare DNS performance from inside and outside a VPN tunnel.

### Step 1: Baseline run (no VPN)

```bash
natbench --count 20 --export html --export-path ~/natbench-results/baseline.html
```

Or using the `isp_comparison` profile:

```bash
natbench --profile isp_comparison \
  --export html --export-path ~/natbench-results/baseline.html
```

Note your best servers and scores.

### Step 2: VPN run

Connect your VPN (or use a VPN profile to do it automatically):

```bash
# Automatic — NatBench connects/disconnects the VPN for you
natbench --profile vpn_mullvad \
  --export html --export-path ~/natbench-results/vpn_mullvad.html
```

Or manually connect your VPN and then run:

```bash
mullvad connect
sleep 5
natbench --count 20 --include-system-dns \
  --export html --export-path ~/natbench-results/vpn_manual.html
mullvad disconnect
```

### Step 3: Compare

Open both HTML reports side-by-side. Key things to look for:

- **Latency increase**: VPN tunnels add overhead. A well-optimized VPN's DNS
  should still resolve in under 50 ms.
- **New top servers**: Inside the VPN, the geographically closest resolvers
  may change.
- **System DNS**: If `include_system_dns` is true, the "System DNS" entry
  shows the DNS pushed by your VPN provider. Compare it to public resolvers.
- **DNSSEC / blocking**: Some VPN providers' bundled DNS resolvers offer
  DNSSEC validation or ad-blocking. Check the security columns.

### Automating repeated comparisons

Create two profiles — one baseline, one VPN — and run them in a shell script:

```bash
#!/bin/bash
STAMP=$(date +%Y%m%d_%H%M)
DIR=~/natbench-results/$STAMP
mkdir -p "$DIR"

echo "=== Baseline ==="
natbench --profile isp_comparison \
  --export html --export-path "$DIR/baseline.html"

echo "=== Mullvad VPN ==="
natbench --profile vpn_mullvad \
  --export html --export-path "$DIR/vpn_mullvad.html"

echo "Results saved to $DIR"
```

---

## Built-in Profile Quick Reference

| Profile | Protocol | Count | Timeout | Scorer | Use case |
|---------|----------|-------|---------|--------|---------|
| `quick` | udp | 5 | 1.5s | latency_only | Fast 30-second sanity check |
| `speed` | udp | 20 | 1.5s | latency_only | Pure speed, top 10 results |
| `isp_comparison` | udp | 25 | 2.0s | default | Compare ISP vs public DNS |
| `security` | udp | 15 | 3.0s | default | DNSSEC + blocking focus |
| `doh` | doh | 10 | 4.0s | default | DoH encrypted resolvers |
| `full` | udp | 30 | 3.0s | default | Thorough, ~5 min, HTML export |
| `vpn_wireguard` | udp | 15 | 3.0s | default | WireGuard tunnel benchmark |
| `vpn_mullvad` | udp | 15 | 3.0s | default | Mullvad CLI tunnel benchmark |
| `vpn_nordvpn` | udp | 15 | 3.0s | default | NordVPN CLI tunnel benchmark |
