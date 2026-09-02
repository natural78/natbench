# NatBench on Android

NatBench supports three ways to run on Android:

1. **Via Termux (CLI)** — full CLI experience directly on the device
2. **Via the web UI on your PC** — run on LAN, access from Android browser
3. **Via the web UI on Android directly** — Termux + Python + `natbench-web`

---

## Method 1: Termux CLI

Run NatBench entirely on your Android device using [Termux](https://termux.dev/).

### Step-by-step

1. **Install Termux** from [F-Droid](https://f-droid.org/packages/com.termux/) (recommended) or Google Play.

2. **Update packages and install Python:**

   ```bash
   pkg update && pkg upgrade
   pkg install python git
   ```

3. **Install NatBench:**

   ```bash
   # From PyPI (when published):
   pip install natbench

   # Or directly from GitHub:
   pip install git+https://github.com/natural78/natbench.git
   ```

4. **Run a benchmark:**

   ```bash
   natbench bench --protocol udp --count 5
   ```

5. **Common CLI options:**

   ```bash
   natbench bench --protocol doh --count 10 --top 10
   natbench bench --tag no-log --protocol dot
   natbench list                    # list all servers
   natbench list --tag privacy      # filter by tag
   natbench --help
   ```

> **Note:** Setting system DNS (`natbench set-dns`) requires root access.
> On non-rooted devices, set DNS manually in Wi-Fi settings
> (Settings → Wi-Fi → [Network] → Edit → Advanced → DNS).

---

## Method 2: Web UI on your PC, Access from Android

Run the web server on your PC/server and access it from any device on the same network.

### On your PC (Linux/macOS/Windows):

```bash
# Install NatBench
pip install natbench

# Start the web UI (listens on all interfaces by default)
natbench-web
```

You will see output like:
```
NatBench Web UI — http://192.168.1.42:8765
Listening on http://0.0.0.0:8765
```

### On your Android device:

1. Connect to the **same Wi-Fi network** as your PC.
2. Open Chrome, Firefox, or any browser.
3. Navigate to the URL shown (e.g. `http://192.168.1.42:8765`).
4. Use the full web UI: select servers, choose protocol, run benchmark.

### Firewall note

If you cannot reach the URL, allow port 8765 on your PC's firewall:

```bash
# Linux (ufw)
sudo ufw allow 8765/tcp

# Linux (firewalld)
sudo firewall-cmd --add-port=8765/tcp --permanent && sudo firewall-cmd --reload
```

---

## Method 3: Web UI Directly on Android (Termux)

Run the web server on your Android device and access it from the same device's browser,
or from other devices on the same LAN.

### Step-by-step

1. **Set up Termux and install NatBench** (see Method 1, steps 1–3).

2. **Start the web server:**

   ```bash
   natbench-web
   ```

   Or with a custom port:

   ```bash
   natbench-web 0.0.0.0 8765
   ```

3. **Open in browser:**

   - On the **same device**: `http://127.0.0.1:8765`
   - From **other devices on LAN**: `http://<android-ip>:8765`

   Find your Android IP with:
   ```bash
   ip addr show wlan0 | grep 'inet '
   ```

4. **Run benchmarks** from the browser interface.

> **Tip:** Pin the Termux session and keep it running in the background
> while you use the browser. On Android 12+ you may need to disable
> battery optimization for Termux to prevent the background process from
> being killed.

---

## Recommended DNS Settings for Mobile

After running a benchmark, set the best resolver in your Android DNS settings:

1. **Android 9+ (Private DNS):**
   Settings → Network & Internet → Private DNS → enter a DoT hostname
   (e.g. `dns.quad9.net`, `dns.adguard-dns.com`, `dns.nextdns.io`)

2. **Wi-Fi DNS override:**
   Settings → Wi-Fi → [Your Network] → Edit (pencil icon) → Advanced options
   → IP settings: Static → enter DNS 1 / DNS 2

3. **Via NatBench web UI:**
   After benchmarking, click the **Set DNS** button next to a result row.
   Requires Termux with root access (`tsu` / Magisk).

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `pkg: command not found` | You are not in Termux — install it first |
| `pip install` fails | Run `pkg install python` first |
| Browser shows "Connection refused" | Check the IP/port; ensure firewall allows 8765 |
| Termux killed in background | Disable battery optimization for Termux |
| DoT/DoH benchmark very slow | Some resolvers block non-standard ports on mobile networks; try UDP first |
| "Permission denied" on set-dns | Root required — set DNS manually instead |
