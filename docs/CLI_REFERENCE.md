# NatBench CLI Reference

## Synopsis

```
natbench [OPTIONS]
```

---

## Global options

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--protocol` | `-p` | choice | `udp` | Protocol: `udp` · `tcp` · `dot` · `doh` |
| `--servers` | `-s` | names/IPs… | `all` | Space/comma-separated server names, keywords, or IPs |
| `--count` | `-n` | int | `10` | Queries per server |
| `--timeout` | `-t` | float | `3.0` | Per-query timeout in seconds |
| `--workers` | `-w` | int | `8` | Concurrent worker threads |
| `--top` | | int | (all) | Show only the top N results |
| `--quiet` | `-q` | flag | off | Suppress progress output |
| `--lang` | `-l` | code | auto | Language code (e.g. `de`, `en`, `zh`) |

## Server selection (`--servers`)

```bash
# Predefined keywords
natbench --servers all           # all 72+ servers (default)
natbench --servers fast          # servers tagged "fast"
natbench --servers secure        # servers with DNSSEC + malware blocking
natbench --servers custom        # only user-added servers (--add-server)

# Server names (space or comma-separated, case-insensitive substring)
natbench --servers cloudflare google quad9 dns.wonx.eu
natbench --servers "cloudflare,mullvad,adguard"

# Raw IPs
natbench --servers 1.1.1.1 8.8.8.8 9.9.9.9

# Add extra server on the fly
natbench --add-server 192.168.1.1 --servers all
```

## Output and export

| Flag | Description |
|------|-------------|
| `--output table` | Pretty table (default) |
| `--output json` | JSON to stdout |
| `--output csv` | CSV to stdout |
| `--output markdown` | Markdown table |
| `--file PATH` | Write output to file |
| `--export json,csv,html` | Export to multiple formats at once |

## System DNS

```bash
# Show current system resolver
natbench --show-dns

# Run benchmark and apply best server to system DNS
sudo natbench --apply
# or
sudo natbench --set-dns 1.1.1.1   # set specific IP
```

## Profiles

```bash
# List built-in + user profiles
natbench --list-profiles

# Load a profile
natbench --profile speed
natbench --profile security
natbench --profile doh
natbench --profile vpn_wireguard

# Save current settings as a profile
natbench --protocol doh --count 20 --save-profile my_doh
```

Built-in profiles: `speed` · `security` · `doh` · `full` · `quick` · `isp_comparison` · `vpn_wireguard` · `vpn_mullvad` · `vpn_nordvpn`

## GUI

```bash
natbench --gui          # launch Tkinter GUI
natbench-gui            # same via installed entry point
```

## Informational

```bash
natbench --list-profiles
natbench --version
```

---

## Examples

```bash
# Quick comparison of four servers
natbench --servers cloudflare google quad9 dns.wonx.eu --top 4

# DoH benchmark with 20 queries, save to HTML report
natbench --protocol doh --count 20 --export html --file report.html

# Security-focused test (DNSSEC + malware blocking servers only)
natbench --profile security

# Test in German, show only top 5
natbench --lang de --top 5

# Compare ISP DNS vs public resolvers
natbench --profile isp_comparison
```
