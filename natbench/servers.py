"""
NatBench servers.py — curated DNS server database.

Each entry is a dict with the following keys:

    name          (str)        Human-readable label
    ip4           (str|None)   Primary IPv4 address
    ip6           (str|None)   Primary IPv6 address (optional)
    doh_url       (str|None)   DNS-over-HTTPS endpoint (RFC 8484, optional)
    dot_host      (str|None)   DNS-over-TLS hostname for SNI (optional)
    dot_port      (int)        DoT port, default 853
    port          (int)        Plain DNS port, default 53
    country       (str)        ISO 3166-1 alpha-2 country code (or region string)
    operator      (str)        Organisation / company running the resolver
    tags          (list[str])  Feature labels — see tag glossary below
    description_en (str)       Short English description

Tag glossary
------------
    malware    — resolver blocks known malware/phishing domains
    adblock    — resolver blocks common ad/tracker domains
    dnssec     — resolver validates DNSSEC signatures
    no-log     — operator claims a no-query-log policy
    anycast    — resolver is served from multiple PoPs via anycast routing
    fast       — subjectively fast / well-known low-latency resolver
    family     — applies family-safe filtering (adult content blocked)
    custom     — user-operated / self-hosted resolver
    community  — community-run resolver (OpenNIC, etc.)
    asia       — primarily serves Asia/Pacific users
    china      — primarily serves users in mainland China
    russia     — primarily serves users in Russia/CIS
    canada     — primarily serves Canadian users
"""

from __future__ import annotations

SERVER_DB: list[dict] = [
    # -----------------------------------------------------------------------
    # Custom / Self-hosted
    # -----------------------------------------------------------------------
    {
        "name": "dns.wonx.eu",
        "ip4": None,
        "ip6": None,
        "doh_url": None,
        "dot_host": "dns.wonx.eu",
        "dot_port": 853,
        "port": 53,
        "country": "DE",
        "operator": "natural (wonx.eu)",
        "tags": ["custom", "dnssec", "no-log"],
        "description_en": "Custom self-hosted DoT resolver on dns.wonx.eu.",
    },

    # -----------------------------------------------------------------------
    # Google Public DNS
    # -----------------------------------------------------------------------
    {
        "name": "Google Primary",
        "ip4": "8.8.8.8",
        "ip6": "2001:4860:4860::8888",
        "doh_url": "https://dns.google/dns-query",
        "dot_host": "dns.google",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "Google LLC",
        "tags": ["dnssec", "anycast", "fast", "no-log"],
        "description_en": "Google Public DNS primary resolver — global anycast, DNSSEC-validating.",
    },
    {
        "name": "Google Secondary",
        "ip4": "8.8.4.4",
        "ip6": "2001:4860:4860::8844",
        "doh_url": "https://dns.google/dns-query",
        "dot_host": "dns.google",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "Google LLC",
        "tags": ["dnssec", "anycast", "fast", "no-log"],
        "description_en": "Google Public DNS secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # Cloudflare
    # -----------------------------------------------------------------------
    {
        "name": "Cloudflare Primary",
        "ip4": "1.1.1.1",
        "ip6": "2606:4700:4700::1111",
        "doh_url": "https://cloudflare-dns.com/dns-query",
        "dot_host": "cloudflare-dns.com",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "Cloudflare Inc.",
        "tags": ["dnssec", "anycast", "fast", "no-log"],
        "description_en": "Cloudflare 1.1.1.1 — privacy-first, consistently fastest resolver in global benchmarks.",
    },
    {
        "name": "Cloudflare Secondary",
        "ip4": "1.0.0.1",
        "ip6": "2606:4700:4700::1001",
        "doh_url": "https://cloudflare-dns.com/dns-query",
        "dot_host": "cloudflare-dns.com",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "Cloudflare Inc.",
        "tags": ["dnssec", "anycast", "fast", "no-log"],
        "description_en": "Cloudflare 1.0.0.1 — secondary resolver.",
    },
    {
        "name": "Cloudflare Malware Blocking",
        "ip4": "1.1.1.2",
        "ip6": "2606:4700:4700::1112",
        "doh_url": "https://security.cloudflare-dns.com/dns-query",
        "dot_host": "security.cloudflare-dns.com",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "Cloudflare Inc.",
        "tags": ["malware", "dnssec", "anycast", "fast", "no-log"],
        "description_en": "Cloudflare 1.1.1.2 — blocks malware and phishing domains.",
    },
    {
        "name": "Cloudflare Family",
        "ip4": "1.1.1.3",
        "ip6": "2606:4700:4700::1113",
        "doh_url": "https://family.cloudflare-dns.com/dns-query",
        "dot_host": "family.cloudflare-dns.com",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "Cloudflare Inc.",
        "tags": ["malware", "family", "dnssec", "anycast", "fast"],
        "description_en": "Cloudflare 1.1.1.3 — blocks malware and adult content.",
    },

    # -----------------------------------------------------------------------
    # Quad9
    # -----------------------------------------------------------------------
    {
        "name": "Quad9 Primary",
        "ip4": "9.9.9.9",
        "ip6": "2620:fe::fe",
        "doh_url": "https://dns.quad9.net/dns-query",
        "dot_host": "dns.quad9.net",
        "dot_port": 853,
        "port": 53,
        "country": "CH",
        "operator": "Quad9 Foundation",
        "tags": ["malware", "dnssec", "anycast", "no-log"],
        "description_en": "Quad9 9.9.9.9 — non-profit, DNSSEC-validating, malware-blocking, privacy-focused.",
    },
    {
        "name": "Quad9 Secondary",
        "ip4": "149.112.112.112",
        "ip6": "2620:fe::9",
        "doh_url": "https://dns.quad9.net/dns-query",
        "dot_host": "dns.quad9.net",
        "dot_port": 853,
        "port": 53,
        "country": "CH",
        "operator": "Quad9 Foundation",
        "tags": ["malware", "dnssec", "anycast", "no-log"],
        "description_en": "Quad9 149.112.112.112 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # OpenDNS (Cisco)
    # -----------------------------------------------------------------------
    {
        "name": "OpenDNS Primary",
        "ip4": "208.67.222.222",
        "ip6": "2620:119:35::35",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Cisco / OpenDNS",
        "tags": ["malware", "anycast", "fast"],
        "description_en": "OpenDNS 208.67.222.222 — long-running anycast resolver with optional content filtering.",
    },
    {
        "name": "OpenDNS Secondary",
        "ip4": "208.67.220.220",
        "ip6": "2620:119:53::53",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Cisco / OpenDNS",
        "tags": ["malware", "anycast", "fast"],
        "description_en": "OpenDNS 208.67.220.220 — secondary resolver.",
    },
    {
        "name": "OpenDNS FamilyShield",
        "ip4": "208.67.222.123",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Cisco / OpenDNS",
        "tags": ["malware", "family", "anycast"],
        "description_en": "OpenDNS FamilyShield — blocks adult content and malware, no account needed.",
    },

    # -----------------------------------------------------------------------
    # AdGuard DNS
    # -----------------------------------------------------------------------
    {
        "name": "AdGuard DNS Primary",
        "ip4": "94.140.14.14",
        "ip6": "2a10:50c0::ad1:ff",
        "doh_url": "https://dns.adguard-dns.com/dns-query",
        "dot_host": "dns.adguard-dns.com",
        "dot_port": 853,
        "port": 53,
        "country": "CY",
        "operator": "AdGuard Software Ltd.",
        "tags": ["adblock", "malware", "dnssec", "anycast", "no-log"],
        "description_en": "AdGuard DNS 94.140.14.14 — blocks ads, trackers, and malware.",
    },
    {
        "name": "AdGuard DNS Secondary",
        "ip4": "94.140.15.15",
        "ip6": "2a10:50c0::ad2:ff",
        "doh_url": "https://dns.adguard-dns.com/dns-query",
        "dot_host": "dns.adguard-dns.com",
        "dot_port": 853,
        "port": 53,
        "country": "CY",
        "operator": "AdGuard Software Ltd.",
        "tags": ["adblock", "malware", "dnssec", "anycast", "no-log"],
        "description_en": "AdGuard DNS 94.140.15.15 — secondary resolver.",
    },
    {
        "name": "AdGuard DNS Family",
        "ip4": "94.140.14.15",
        "ip6": "2a10:50c0::bad1:ff",
        "doh_url": "https://family.adguard-dns.com/dns-query",
        "dot_host": "family.adguard-dns.com",
        "dot_port": 853,
        "port": 53,
        "country": "CY",
        "operator": "AdGuard Software Ltd.",
        "tags": ["adblock", "malware", "family", "dnssec", "anycast"],
        "description_en": "AdGuard DNS Family — ads/trackers/malware/adult content blocked.",
    },
    {
        "name": "AdGuard DNS Unfiltered",
        "ip4": "94.140.14.140",
        "ip6": "2a10:50c0::1:ff",
        "doh_url": "https://unfiltered.adguard-dns.com/dns-query",
        "dot_host": "unfiltered.adguard-dns.com",
        "dot_port": 853,
        "port": 53,
        "country": "CY",
        "operator": "AdGuard Software Ltd.",
        "tags": ["dnssec", "no-log", "anycast"],
        "description_en": "AdGuard DNS Unfiltered — no blocking, DNSSEC-validating.",
    },

    # -----------------------------------------------------------------------
    # NextDNS
    # -----------------------------------------------------------------------
    {
        "name": "NextDNS",
        "ip4": None,
        "ip6": None,
        "doh_url": "https://dns.nextdns.io",
        "dot_host": "dns.nextdns.io",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "NextDNS Inc.",
        "tags": ["adblock", "malware", "dnssec", "no-log"],
        "description_en": "NextDNS — highly configurable DoH/DoT resolver; free tier available.",
    },

    # -----------------------------------------------------------------------
    # Mullvad DNS
    # -----------------------------------------------------------------------
    {
        "name": "Mullvad Adblock",
        "ip4": "194.242.2.2",
        "ip6": "2a07:e340::2",
        "doh_url": "https://adblock.doh.mullvad.net/dns-query",
        "dot_host": "adblock.doh.mullvad.net",
        "dot_port": 853,
        "port": 53,
        "country": "SE",
        "operator": "Mullvad VPN AB",
        "tags": ["adblock", "malware", "no-log", "dnssec"],
        "description_en": "Mullvad DNS adblock variant — no logging, ad/tracker/malware blocking.",
    },
    {
        "name": "Mullvad Base",
        "ip4": "194.242.2.3",
        "ip6": "2a07:e340::3",
        "doh_url": "https://base.doh.mullvad.net/dns-query",
        "dot_host": "base.doh.mullvad.net",
        "dot_port": 853,
        "port": 53,
        "country": "SE",
        "operator": "Mullvad VPN AB",
        "tags": ["no-log", "dnssec"],
        "description_en": "Mullvad DNS base (no filtering) — privacy-focused, no logging.",
    },

    # -----------------------------------------------------------------------
    # dns.sb
    # -----------------------------------------------------------------------
    {
        "name": "dns.sb Primary",
        "ip4": "185.222.222.222",
        "ip6": "2a09::",
        "doh_url": "https://doh.dns.sb/dns-query",
        "dot_host": "dot.sb",
        "dot_port": 853,
        "port": 53,
        "country": "DE",
        "operator": "dns.sb",
        "tags": ["dnssec", "no-log", "anycast"],
        "description_en": "dns.sb 185.222.222.222 — privacy-focused, DNSSEC-validating, no logging.",
    },
    {
        "name": "dns.sb Secondary",
        "ip4": "45.11.45.11",
        "ip6": "2a11::",
        "doh_url": "https://doh.dns.sb/dns-query",
        "dot_host": "dot.sb",
        "dot_port": 853,
        "port": 53,
        "country": "DE",
        "operator": "dns.sb",
        "tags": ["dnssec", "no-log", "anycast"],
        "description_en": "dns.sb 45.11.45.11 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # CleanBrowsing
    # -----------------------------------------------------------------------
    {
        "name": "CleanBrowsing Security",
        "ip4": "185.228.168.9",
        "ip6": "2a0d:2a00:1::2",
        "doh_url": "https://doh.cleanbrowsing.org/doh/security-filter/",
        "dot_host": "security-filter-dns.cleanbrowsing.org",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "CleanBrowsing",
        "tags": ["malware", "dnssec"],
        "description_en": "CleanBrowsing Security Filter — blocks malware, phishing, and typosquatting.",
    },
    {
        "name": "CleanBrowsing Security Secondary",
        "ip4": "185.228.169.9",
        "ip6": "2a0d:2a00:2::2",
        "doh_url": "https://doh.cleanbrowsing.org/doh/security-filter/",
        "dot_host": "security-filter-dns.cleanbrowsing.org",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "CleanBrowsing",
        "tags": ["malware", "dnssec"],
        "description_en": "CleanBrowsing Security Filter — secondary resolver.",
    },
    {
        "name": "CleanBrowsing Family",
        "ip4": "185.228.168.10",
        "ip6": "2a0d:2a00:1::1",
        "doh_url": "https://doh.cleanbrowsing.org/doh/family-filter/",
        "dot_host": "family-filter-dns.cleanbrowsing.org",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "CleanBrowsing",
        "tags": ["malware", "family", "dnssec"],
        "description_en": "CleanBrowsing Family Filter — blocks adult content, malware, and mixed-content sites.",
    },
    {
        "name": "CleanBrowsing Adult",
        "ip4": "185.228.168.11",
        "ip6": "2a0d:2a00:1::11",
        "doh_url": "https://doh.cleanbrowsing.org/doh/adult-filter/",
        "dot_host": "adult-filter-dns.cleanbrowsing.org",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "CleanBrowsing",
        "tags": ["family", "dnssec"],
        "description_en": "CleanBrowsing Adult Filter — blocks adult content only.",
    },

    # -----------------------------------------------------------------------
    # Comodo Secure DNS
    # -----------------------------------------------------------------------
    {
        "name": "Comodo Secure DNS Primary",
        "ip4": "8.26.56.26",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Comodo Group",
        "tags": ["malware"],
        "description_en": "Comodo Secure DNS 8.26.56.26 — blocks malware and phishing domains.",
    },
    {
        "name": "Comodo Secure DNS Secondary",
        "ip4": "8.20.247.20",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Comodo Group",
        "tags": ["malware"],
        "description_en": "Comodo Secure DNS 8.20.247.20 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # Level3 / Lumen Technologies
    # -----------------------------------------------------------------------
    {
        "name": "Level3/Lumen DNS 1",
        "ip4": "4.2.2.1",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Lumen Technologies (Level3)",
        "tags": ["anycast", "fast"],
        "description_en": "Level3/Lumen 4.2.2.1 — long-running open resolver, anycast.",
    },
    {
        "name": "Level3/Lumen DNS 2",
        "ip4": "4.2.2.2",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Lumen Technologies (Level3)",
        "tags": ["anycast", "fast"],
        "description_en": "Level3/Lumen 4.2.2.2.",
    },
    {
        "name": "Level3/Lumen DNS 3",
        "ip4": "4.2.2.3",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Lumen Technologies (Level3)",
        "tags": ["anycast"],
        "description_en": "Level3/Lumen 4.2.2.3.",
    },
    {
        "name": "Level3/Lumen DNS 4",
        "ip4": "4.2.2.4",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Lumen Technologies (Level3)",
        "tags": ["anycast"],
        "description_en": "Level3/Lumen 4.2.2.4.",
    },

    # -----------------------------------------------------------------------
    # Verisign Public DNS
    # -----------------------------------------------------------------------
    {
        "name": "Verisign Primary",
        "ip4": "64.6.64.6",
        "ip6": "2620:74:1b::1:1",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Verisign Inc.",
        "tags": ["dnssec", "anycast", "no-log"],
        "description_en": "Verisign Public DNS 64.6.64.6 — DNSSEC-validating, no logging.",
    },
    {
        "name": "Verisign Secondary",
        "ip4": "64.6.65.6",
        "ip6": "2620:74:1c::2:2",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Verisign Inc.",
        "tags": ["dnssec", "anycast", "no-log"],
        "description_en": "Verisign Public DNS 64.6.65.6 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # Yandex DNS
    # -----------------------------------------------------------------------
    {
        "name": "Yandex DNS Basic Primary",
        "ip4": "77.88.8.8",
        "ip6": "2a02:6b8::feed:0ff",
        "doh_url": "https://common.dot.dns.yandex.net/dns-query",
        "dot_host": "common.dot.dns.yandex.net",
        "dot_port": 853,
        "port": 53,
        "country": "RU",
        "operator": "Yandex LLC",
        "tags": ["russia", "anycast", "fast"],
        "description_en": "Yandex DNS 77.88.8.8 — primary Russian-operated public resolver.",
    },
    {
        "name": "Yandex DNS Basic Secondary",
        "ip4": "77.88.8.1",
        "ip6": "2a02:6b8:0:1::feed:0ff",
        "doh_url": "https://common.dot.dns.yandex.net/dns-query",
        "dot_host": "common.dot.dns.yandex.net",
        "dot_port": 853,
        "port": 53,
        "country": "RU",
        "operator": "Yandex LLC",
        "tags": ["russia", "anycast"],
        "description_en": "Yandex DNS 77.88.8.1 — secondary resolver.",
    },
    {
        "name": "Yandex DNS Safe Primary",
        "ip4": "77.88.8.88",
        "ip6": "2a02:6b8::feed:bad",
        "doh_url": "https://safe.dot.dns.yandex.net/dns-query",
        "dot_host": "safe.dot.dns.yandex.net",
        "dot_port": 853,
        "port": 53,
        "country": "RU",
        "operator": "Yandex LLC",
        "tags": ["malware", "russia", "anycast"],
        "description_en": "Yandex DNS Safe 77.88.8.88 — blocks malware and fraudulent sites.",
    },
    {
        "name": "Yandex DNS Safe Secondary",
        "ip4": "77.88.8.2",
        "ip6": "2a02:6b8:0:1::feed:bad",
        "doh_url": "https://safe.dot.dns.yandex.net/dns-query",
        "dot_host": "safe.dot.dns.yandex.net",
        "dot_port": 853,
        "port": 53,
        "country": "RU",
        "operator": "Yandex LLC",
        "tags": ["malware", "russia", "anycast"],
        "description_en": "Yandex DNS Safe 77.88.8.2 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # Alibaba DNS (AliDNS)
    # -----------------------------------------------------------------------
    {
        "name": "AliDNS Primary",
        "ip4": "223.5.5.5",
        "ip6": None,
        "doh_url": "https://dns.alidns.com/dns-query",
        "dot_host": "dns.alidns.com",
        "dot_port": 853,
        "port": 53,
        "country": "CN",
        "operator": "Alibaba Cloud (Aliyun)",
        "tags": ["asia", "china", "anycast", "fast"],
        "description_en": "Alibaba AliDNS 223.5.5.5 — primary resolver for Asia/China.",
    },
    {
        "name": "AliDNS Secondary",
        "ip4": "223.6.6.6",
        "ip6": None,
        "doh_url": "https://dns.alidns.com/dns-query",
        "dot_host": "dns.alidns.com",
        "dot_port": 853,
        "port": 53,
        "country": "CN",
        "operator": "Alibaba Cloud (Aliyun)",
        "tags": ["asia", "china", "anycast", "fast"],
        "description_en": "Alibaba AliDNS 223.6.6.6 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # Baidu DNS
    # -----------------------------------------------------------------------
    {
        "name": "Baidu DNS",
        "ip4": "180.76.76.76",
        "ip6": "2400:da00::6666",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "CN",
        "operator": "Baidu Inc.",
        "tags": ["china", "fast"],
        "description_en": "Baidu Public DNS 180.76.76.76 — primarily for mainland China users.",
    },

    # -----------------------------------------------------------------------
    # 114DNS (China)
    # -----------------------------------------------------------------------
    {
        "name": "114DNS Primary",
        "ip4": "114.114.114.114",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "CN",
        "operator": "114DNS (Nanjing Xinwang)",
        "tags": ["china", "fast", "anycast"],
        "description_en": "114DNS 114.114.114.114 — popular Chinese public resolver.",
    },
    {
        "name": "114DNS Secondary",
        "ip4": "114.114.115.115",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "CN",
        "operator": "114DNS (Nanjing Xinwang)",
        "tags": ["china", "fast", "anycast"],
        "description_en": "114DNS 114.114.115.115 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # Tencent DNSPod
    # -----------------------------------------------------------------------
    {
        "name": "DNSPod Primary",
        "ip4": "119.29.29.29",
        "ip6": None,
        "doh_url": "https://doh.pub/dns-query",
        "dot_host": "dot.pub",
        "dot_port": 853,
        "port": 53,
        "country": "CN",
        "operator": "Tencent Cloud / DNSPod",
        "tags": ["asia", "china", "anycast", "fast"],
        "description_en": "Tencent DNSPod 119.29.29.29 — optimised for Asia/China.",
    },
    {
        "name": "DNSPod Secondary",
        "ip4": "182.254.116.116",
        "ip6": None,
        "doh_url": "https://doh.pub/dns-query",
        "dot_host": "dot.pub",
        "dot_port": 853,
        "port": 53,
        "country": "CN",
        "operator": "Tencent Cloud / DNSPod",
        "tags": ["asia", "china", "anycast"],
        "description_en": "Tencent DNSPod 182.254.116.116 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # DNSFilter
    # -----------------------------------------------------------------------
    {
        "name": "DNSFilter",
        "ip4": "103.247.36.36",
        "ip6": None,
        "doh_url": "https://doh.dnsfilter.com/dns-query",
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "DNSFilter Inc.",
        "tags": ["malware", "adblock", "dnssec"],
        "description_en": "DNSFilter 103.247.36.36 — AI-powered threat intelligence, malware/ad blocking.",
    },

    # -----------------------------------------------------------------------
    # ControlD
    # -----------------------------------------------------------------------
    {
        "name": "ControlD Free (No Filters)",
        "ip4": None,
        "ip6": None,
        "doh_url": "https://freedns.controld.com/p0",
        "dot_host": "p0.freedns.controld.com",
        "dot_port": 853,
        "port": 53,
        "country": "CA",
        "operator": "ControlD Inc.",
        "tags": ["no-log", "dnssec"],
        "description_en": "ControlD Free DNS — no filtering, DNSSEC-validating, privacy-focused.",
    },
    {
        "name": "ControlD Malware Block",
        "ip4": None,
        "ip6": None,
        "doh_url": "https://freedns.controld.com/p1",
        "dot_host": "p1.freedns.controld.com",
        "dot_port": 853,
        "port": 53,
        "country": "CA",
        "operator": "ControlD Inc.",
        "tags": ["malware", "no-log", "dnssec"],
        "description_en": "ControlD p1 — blocks malware and phishing.",
    },
    {
        "name": "ControlD Ads+Malware Block",
        "ip4": None,
        "ip6": None,
        "doh_url": "https://freedns.controld.com/p2",
        "dot_host": "p2.freedns.controld.com",
        "dot_port": 853,
        "port": 53,
        "country": "CA",
        "operator": "ControlD Inc.",
        "tags": ["malware", "adblock", "no-log", "dnssec"],
        "description_en": "ControlD p2 — blocks ads, trackers, and malware.",
    },

    # -----------------------------------------------------------------------
    # F-Secure SAFE (WithSecure)
    # -----------------------------------------------------------------------
    {
        "name": "F-Secure SAFE Primary",
        "ip4": "103.86.96.100",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "FI",
        "operator": "F-Secure / WithSecure",
        "tags": ["malware"],
        "description_en": "F-Secure SAFE DNS 103.86.96.100 — blocks malware and phishing.",
    },
    {
        "name": "F-Secure SAFE Secondary",
        "ip4": "103.86.99.100",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "FI",
        "operator": "F-Secure / WithSecure",
        "tags": ["malware"],
        "description_en": "F-Secure SAFE DNS 103.86.99.100 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # Neustar UltraDNS
    # -----------------------------------------------------------------------
    {
        "name": "Neustar UltraDNS Primary",
        "ip4": "156.154.70.1",
        "ip6": "2610:a1:1018::1",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Neustar / TransUnion",
        "tags": ["anycast", "fast"],
        "description_en": "Neustar UltraDNS 156.154.70.1 — high-reliability anycast resolver.",
    },
    {
        "name": "Neustar UltraDNS Secondary",
        "ip4": "156.154.71.1",
        "ip6": "2610:a1:1019::1",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Neustar / TransUnion",
        "tags": ["anycast", "fast"],
        "description_en": "Neustar UltraDNS 156.154.71.1 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # SafeDNS
    # -----------------------------------------------------------------------
    {
        "name": "SafeDNS Primary",
        "ip4": "195.46.39.39",
        "ip6": None,
        "doh_url": "https://doh.safedns.com/dns-query",
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "SafeDNS",
        "tags": ["malware", "adblock", "family"],
        "description_en": "SafeDNS 195.46.39.39 — blocks malware, ads, and adult content.",
    },
    {
        "name": "SafeDNS Secondary",
        "ip4": "195.46.39.40",
        "ip6": None,
        "doh_url": "https://doh.safedns.com/dns-query",
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "SafeDNS",
        "tags": ["malware", "adblock", "family"],
        "description_en": "SafeDNS 195.46.39.40 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # Freenom World
    # -----------------------------------------------------------------------
    {
        "name": "Freenom World Primary",
        "ip4": "80.80.80.80",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "NL",
        "operator": "Freenom",
        "tags": [],
        "description_en": "Freenom World 80.80.80.80 — simple unfiltered public resolver.",
    },
    {
        "name": "Freenom World Secondary",
        "ip4": "80.80.81.81",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "NL",
        "operator": "Freenom",
        "tags": [],
        "description_en": "Freenom World 80.80.81.81 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # OpenNIC (community)
    # -----------------------------------------------------------------------
    {
        "name": "OpenNIC US-1",
        "ip4": "23.94.60.240",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "OpenNIC Project (community)",
        "tags": ["community", "no-log"],
        "description_en": "OpenNIC community resolver (US) — supports OpenNIC TLDs.",
    },
    {
        "name": "OpenNIC DE-1",
        "ip4": "58.6.115.42",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "DE",
        "operator": "OpenNIC Project (community)",
        "tags": ["community", "no-log"],
        "description_en": "OpenNIC community resolver (DE) — supports OpenNIC TLDs.",
    },

    # -----------------------------------------------------------------------
    # Hurricane Electric
    # -----------------------------------------------------------------------
    {
        "name": "Hurricane Electric",
        "ip4": "74.82.42.42",
        "ip6": "2001:470:20::2",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Hurricane Electric LLC",
        "tags": ["anycast"],
        "description_en": "Hurricane Electric 74.82.42.42 — well-connected ISP/datacenter resolver.",
    },

    # -----------------------------------------------------------------------
    # CIRA Canadian Shield
    # -----------------------------------------------------------------------
    {
        "name": "CIRA Canadian Shield Private",
        "ip4": "149.112.121.10",
        "ip6": "2620:10a:80bb::10",
        "doh_url": "https://private.canadianshield.cira.ca/dns-query",
        "dot_host": "private.canadianshield.cira.ca",
        "dot_port": 853,
        "port": 53,
        "country": "CA",
        "operator": "CIRA",
        "tags": ["canada", "dnssec", "no-log"],
        "description_en": "CIRA Canadian Shield 149.112.121.10 — Canadian non-profit, DNSSEC, no logging.",
    },
    {
        "name": "CIRA Canadian Shield Protected",
        "ip4": "149.112.122.10",
        "ip6": "2620:10a:80bc::10",
        "doh_url": "https://protected.canadianshield.cira.ca/dns-query",
        "dot_host": "protected.canadianshield.cira.ca",
        "dot_port": 853,
        "port": 53,
        "country": "CA",
        "operator": "CIRA",
        "tags": ["canada", "malware", "dnssec", "no-log"],
        "description_en": "CIRA Canadian Shield 149.112.122.10 — adds malware/phishing protection.",
    },

    # -----------------------------------------------------------------------
    # DNS.WATCH
    # -----------------------------------------------------------------------
    {
        "name": "DNS.WATCH Primary",
        "ip4": "84.200.69.80",
        "ip6": "2001:1608:10:25::1c04:b12f",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "DE",
        "operator": "DNS.WATCH",
        "tags": ["dnssec", "no-log"],
        "description_en": "DNS.WATCH 84.200.69.80 — uncensored, DNSSEC-validating, no logging.",
    },
    {
        "name": "DNS.WATCH Secondary",
        "ip4": "84.200.70.40",
        "ip6": "2001:1608:10:25::9249:d69b",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "DE",
        "operator": "DNS.WATCH",
        "tags": ["dnssec", "no-log"],
        "description_en": "DNS.WATCH 84.200.70.40 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # Norton ConnectSafe (legacy, may be discontinued)
    # -----------------------------------------------------------------------
    {
        "name": "Norton ConnectSafe Primary",
        "ip4": "199.85.126.10",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Norton (NortonLifeLock / Gen Digital)",
        "tags": ["malware"],
        "description_en": "Norton ConnectSafe 199.85.126.10 — blocks malware and phishing (may be discontinued).",
    },
    {
        "name": "Norton ConnectSafe Secondary",
        "ip4": "199.85.127.10",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Norton (NortonLifeLock / Gen Digital)",
        "tags": ["malware"],
        "description_en": "Norton ConnectSafe 199.85.127.10 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # doh.opendns.com (Cisco OpenDNS DoH)
    # -----------------------------------------------------------------------
    {
        "name": "OpenDNS DoH",
        "ip4": None,
        "ip6": None,
        "doh_url": "https://doh.opendns.com/dns-query",
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Cisco / OpenDNS",
        "tags": ["malware", "anycast", "fast"],
        "description_en": "OpenDNS DNS-over-HTTPS endpoint.",
    },

    # -----------------------------------------------------------------------
    # Alternate DNS (ad-blocking)
    # -----------------------------------------------------------------------
    {
        "name": "Alternate DNS Primary",
        "ip4": "76.76.19.19",
        "ip6": "2602:fcbc::ad",
        "doh_url": "https://dns.alternate-dns.com/dns-query",
        "dot_host": "dns.alternate-dns.com",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "Alternate DNS",
        "tags": ["adblock"],
        "description_en": "Alternate DNS 76.76.19.19 — ad-blocking resolver.",
    },
    {
        "name": "Alternate DNS Secondary",
        "ip4": "76.223.122.150",
        "ip6": "2602:fcbc:2::ad",
        "doh_url": "https://dns.alternate-dns.com/dns-query",
        "dot_host": "dns.alternate-dns.com",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "Alternate DNS",
        "tags": ["adblock"],
        "description_en": "Alternate DNS 76.223.122.150 — secondary ad-blocking resolver.",
    },

    # -----------------------------------------------------------------------
    # LibreDNS
    # -----------------------------------------------------------------------
    {
        "name": "LibreDNS",
        "ip4": "116.202.176.26",
        "ip6": None,
        "doh_url": "https://doh.libredns.gr/dns-query",
        "dot_host": "dot.libredns.gr",
        "dot_port": 853,
        "port": 53,
        "country": "DE",
        "operator": "LibreDNS",
        "tags": ["no-log", "dnssec"],
        "description_en": "LibreDNS — privacy-focused, no logging, DNSSEC.",
    },
    {
        "name": "LibreDNS Ads",
        "ip4": "116.202.176.26",
        "ip6": None,
        "doh_url": "https://doh.libredns.gr/ads",
        "dot_host": None,
        "port": 5353,
        "country": "DE",
        "operator": "LibreDNS",
        "tags": ["adblock", "no-log"],
        "description_en": "LibreDNS ad-blocking variant.",
    },

    # -----------------------------------------------------------------------
    # Dyn DNS (Oracle)
    # -----------------------------------------------------------------------
    {
        "name": "Dyn / Oracle DNS Primary",
        "ip4": "216.146.35.35",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Oracle / Dyn",
        "tags": ["anycast"],
        "description_en": "Dyn/Oracle DNS 216.146.35.35 — enterprise anycast resolver.",
    },
    {
        "name": "Dyn / Oracle DNS Secondary",
        "ip4": "216.146.36.36",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Oracle / Dyn",
        "tags": ["anycast"],
        "description_en": "Dyn/Oracle DNS 216.146.36.36 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # Digitalcourage e.V. (Germany, non-profit)
    # -----------------------------------------------------------------------
    {
        "name": "Digitalcourage DNS Primary",
        "ip4": "46.182.19.48",
        "ip6": "2a02:2970:1002::18",
        "doh_url": "https://digitalcourage.de/dns-query",
        "dot_host": "dns2.digitalcourage.de",
        "dot_port": 853,
        "port": 53,
        "country": "DE",
        "operator": "Digitalcourage e.V.",
        "tags": ["no-log", "dnssec"],
        "description_en": "Digitalcourage e.V. 46.182.19.48 — German non-profit, no logging, DNSSEC.",
    },
    {
        "name": "Digitalcourage DNS Secondary",
        "ip4": "89.233.43.71",
        "ip6": "2a01:3a0:53:53::0",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "DE",
        "operator": "Digitalcourage e.V. / Censurfridns.dk",
        "tags": ["no-log", "dnssec"],
        "description_en": "Digitalcourage / UncensoredDNS 89.233.43.71 — no logging, uncensored.",
    },

    # -----------------------------------------------------------------------
    # Censurfridns.dk (UncensoredDNS, Denmark)
    # -----------------------------------------------------------------------
    {
        "name": "UncensoredDNS Primary",
        "ip4": "91.239.100.100",
        "ip6": "2001:67c:28a4::",
        "doh_url": None,
        "dot_host": "unicast.censurfridns.dk",
        "dot_port": 853,
        "port": 53,
        "country": "DK",
        "operator": "Censurfridns.dk",
        "tags": ["no-log", "dnssec"],
        "description_en": "UncensoredDNS 91.239.100.100 — Danish uncensored resolver, no logging.",
    },

    # -----------------------------------------------------------------------
    # CCC e.V. (Chaos Computer Club, Germany)
    # -----------------------------------------------------------------------
    {
        "name": "CCC DNS",
        "ip4": "213.73.91.35",
        "ip6": "2001:4b98:dc0:41:216:3eff:fe27:3d3f",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "DE",
        "operator": "Chaos Computer Club e.V.",
        "tags": ["community", "no-log"],
        "description_en": "CCC e.V. 213.73.91.35 — German hacker community resolver.",
    },

    # -----------------------------------------------------------------------
    # Freifunk München (Germany)
    # -----------------------------------------------------------------------
    {
        "name": "Freifunk München DNS",
        "ip4": "5.1.66.255",
        "ip6": "2a06:8782:ffbb:1337::1",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "DE",
        "operator": "Freifunk München e.V.",
        "tags": ["community", "no-log"],
        "description_en": "Freifunk München 5.1.66.255 — German community-run resolver.",
    },

    # -----------------------------------------------------------------------
    # CIRA Canadian Shield (additional IPs — .20 subnet)
    # -----------------------------------------------------------------------
    {
        "name": "CIRA Canadian Shield Private 2",
        "ip4": "149.112.121.20",
        "ip6": "2620:10a:80bb::20",
        "doh_url": "https://private.canadianshield.cira.ca/dns-query",
        "dot_host": "private.canadianshield.cira.ca",
        "dot_port": 853,
        "port": 53,
        "country": "CA",
        "operator": "CIRA",
        "tags": ["canada", "dnssec", "no-log"],
        "description_en": "CIRA Canadian Shield Private 149.112.121.20 — second anycast node, no logging, DNSSEC.",
    },
    {
        "name": "CIRA Canadian Shield Protected 2",
        "ip4": "149.112.122.20",
        "ip6": "2620:10a:80bc::20",
        "doh_url": "https://protected.canadianshield.cira.ca/dns-query",
        "dot_host": "protected.canadianshield.cira.ca",
        "dot_port": 853,
        "port": 53,
        "country": "CA",
        "operator": "CIRA",
        "tags": ["canada", "malware", "dnssec", "no-log"],
        "description_en": "CIRA Canadian Shield Protected 149.112.122.20 — malware/phishing protection, second node.",
    },

    # -----------------------------------------------------------------------
    # RethinkDNS (privacy)
    # -----------------------------------------------------------------------
    {
        "name": "RethinkDNS Primary",
        "ip4": "76.76.2.0",
        "ip6": None,
        "doh_url": "https://basic.rethinkdns.com/dns-query",
        "dot_host": "basic.rethinkdns.com",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "RethinkDNS",
        "tags": ["no-log", "dnssec"],
        "description_en": "RethinkDNS 76.76.2.0 — privacy-focused, no logging.",
    },
    {
        "name": "RethinkDNS Secondary",
        "ip4": "76.76.10.0",
        "ip6": None,
        "doh_url": "https://basic.rethinkdns.com/dns-query",
        "dot_host": "basic.rethinkdns.com",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "RethinkDNS",
        "tags": ["no-log", "dnssec"],
        "description_en": "RethinkDNS 76.76.10.0 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # BlahDNS (privacy, multiple PoPs)
    # -----------------------------------------------------------------------
    {
        "name": "BlahDNS Germany",
        "ip4": "78.46.244.143",
        "ip6": "2a01:4f8:c17:ec67::1",
        "doh_url": "https://doh-de.blahdns.com/dns-query",
        "dot_host": "dot-de.blahdns.com",
        "dot_port": 853,
        "port": 53,
        "country": "DE",
        "operator": "BlahDNS",
        "tags": ["no-log", "adblock", "dnssec"],
        "description_en": "BlahDNS 78.46.244.143 — no-log, ad-blocking resolver hosted in Germany.",
    },
    {
        "name": "BlahDNS Finland",
        "ip4": "95.216.212.177",
        "ip6": "2a01:4f9:c010:43ce::1",
        "doh_url": "https://doh-fi.blahdns.com/dns-query",
        "dot_host": "dot-fi.blahdns.com",
        "dot_port": 853,
        "port": 53,
        "country": "FI",
        "operator": "BlahDNS",
        "tags": ["no-log", "adblock", "dnssec"],
        "description_en": "BlahDNS 95.216.212.177 — no-log, ad-blocking resolver hosted in Finland.",
    },
    {
        "name": "BlahDNS Japan",
        "ip4": "108.61.201.119",
        "ip6": "2001:19f0:7001:1ded:5400:2ff:fe90:7894",
        "doh_url": "https://doh-jp.blahdns.com/dns-query",
        "dot_host": "dot-jp.blahdns.com",
        "dot_port": 853,
        "port": 53,
        "country": "JP",
        "operator": "BlahDNS",
        "tags": ["no-log", "adblock", "dnssec", "asia"],
        "description_en": "BlahDNS 108.61.201.119 — no-log, ad-blocking resolver hosted in Japan.",
    },

    # -----------------------------------------------------------------------
    # AhaDNS (privacy, multiple PoPs)
    # -----------------------------------------------------------------------
    {
        "name": "AhaDNS Netherlands",
        "ip4": "5.2.75.75",
        "ip6": "2a04:52c0:101:75::75",
        "doh_url": "https://doh.nl.ahadns.net/dns-query",
        "dot_host": "dot.nl.ahadns.net",
        "dot_port": 853,
        "port": 53,
        "country": "NL",
        "operator": "AhaDNS",
        "tags": ["no-log", "adblock", "dnssec"],
        "description_en": "AhaDNS 5.2.75.75 — no-log, DNSSEC, ad-blocking resolver in Netherlands.",
    },
    {
        "name": "AhaDNS Norway",
        "ip4": "89.233.43.71",
        "ip6": "2a01:3a0:53:53::0",
        "doh_url": "https://doh.no.ahadns.net/dns-query",
        "dot_host": "dot.no.ahadns.net",
        "dot_port": 853,
        "port": 53,
        "country": "NO",
        "operator": "AhaDNS",
        "tags": ["no-log", "adblock", "dnssec"],
        "description_en": "AhaDNS 89.233.43.71 — no-log, DNSSEC, ad-blocking resolver in Norway.",
    },

    # -----------------------------------------------------------------------
    # FDN (French Data Network)
    # -----------------------------------------------------------------------
    {
        "name": "FDN Primary",
        "ip4": "80.67.169.12",
        "ip6": "2001:910:800::12",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "FR",
        "operator": "FDN (French Data Network)",
        "tags": ["no-log", "community"],
        "description_en": "FDN 80.67.169.12 — French non-profit ISP, uncensored resolver.",
    },
    {
        "name": "FDN Secondary",
        "ip4": "80.67.169.40",
        "ip6": "2001:910:800::40",
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "FR",
        "operator": "FDN (French Data Network)",
        "tags": ["no-log", "community"],
        "description_en": "FDN 80.67.169.40 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # Snopyta (Finland, privacy)
    # -----------------------------------------------------------------------
    {
        "name": "Snopyta DNS",
        "ip4": "95.216.229.234",
        "ip6": "2a01:4f9:2b:1919::9",
        "doh_url": "https://fi.doh.dns.snopyta.org/dns-query",
        "dot_host": "fi.dot.dns.snopyta.org",
        "dot_port": 853,
        "port": 53,
        "country": "FI",
        "operator": "Snopyta",
        "tags": ["no-log", "dnssec"],
        "description_en": "Snopyta DNS 95.216.229.234 — Finnish privacy-focused resolver, no logging.",
    },

    # -----------------------------------------------------------------------
    # OpenNIC (additional nodes)
    # -----------------------------------------------------------------------
    {
        "name": "OpenNIC EU-1",
        "ip4": "94.247.43.254",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "FR",
        "operator": "OpenNIC Project (community)",
        "tags": ["community", "no-log"],
        "description_en": "OpenNIC community resolver (EU/France) — supports OpenNIC TLDs.",
    },
    {
        "name": "OpenNIC AU-1",
        "ip4": "150.101.100.1",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "AU",
        "operator": "OpenNIC Project (community)",
        "tags": ["community", "no-log"],
        "description_en": "OpenNIC community resolver (Australia) — supports OpenNIC TLDs.",
    },

    # -----------------------------------------------------------------------
    # TWNIC (Taiwan Network Information Center)
    # -----------------------------------------------------------------------
    {
        "name": "TWNIC Primary",
        "ip4": "101.101.101.101",
        "ip6": "2001:de4::101",
        "doh_url": "https://dns.twnic.tw/dns-query",
        "dot_host": None,
        "port": 53,
        "country": "TW",
        "operator": "TWNIC (Taiwan Network Information Center)",
        "tags": ["no-log", "dnssec", "anycast", "asia", "fast"],
        "description_en": "TWNIC 101.101.101.101 — Taiwanese public resolver, no logging, DNSSEC.",
    },
    {
        "name": "TWNIC Secondary",
        "ip4": "101.102.103.104",
        "ip6": "2001:de4::102",
        "doh_url": "https://dns.twnic.tw/dns-query",
        "dot_host": None,
        "port": 53,
        "country": "TW",
        "operator": "TWNIC (Taiwan Network Information Center)",
        "tags": ["no-log", "dnssec", "anycast", "asia"],
        "description_en": "TWNIC 101.102.103.104 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # CNNIC Public DNS (China)
    # -----------------------------------------------------------------------
    {
        "name": "CNNIC DNS Primary",
        "ip4": "1.2.4.8",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "CN",
        "operator": "CNNIC (China Internet Network Information Center)",
        "tags": ["china", "fast", "anycast"],
        "description_en": "CNNIC Public DNS 1.2.4.8 — operated by China Internet NIC.",
    },
    {
        "name": "CNNIC DNS Secondary",
        "ip4": "210.2.4.8",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "CN",
        "operator": "CNNIC (China Internet Network Information Center)",
        "tags": ["china", "fast"],
        "description_en": "CNNIC Public DNS 210.2.4.8 — secondary resolver.",
    },

    # -----------------------------------------------------------------------
    # KDDI Japan
    # -----------------------------------------------------------------------
    {
        "name": "KDDI Japan DNS",
        "ip4": "203.148.64.193",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "JP",
        "operator": "KDDI Corporation",
        "tags": ["asia"],
        "description_en": "KDDI 203.148.64.193 — Japanese ISP public resolver.",
    },

    # -----------------------------------------------------------------------
    # IIJ Japan (Internet Initiative Japan)
    # -----------------------------------------------------------------------
    {
        "name": "IIJ Japan DNS",
        "ip4": "103.2.57.5",
        "ip6": None,
        "doh_url": "https://public.dns.iij.jp/dns-query",
        "dot_host": "public.dns.iij.jp",
        "dot_port": 853,
        "port": 53,
        "country": "JP",
        "operator": "Internet Initiative Japan (IIJ)",
        "tags": ["asia", "dnssec", "no-log"],
        "description_en": "IIJ 103.2.57.5 — Japanese ISP public resolver with DoH/DoT.",
    },

    # -----------------------------------------------------------------------
    # OpenDNS FamilyShield Secondary
    # -----------------------------------------------------------------------
    {
        "name": "OpenDNS FamilyShield Secondary",
        "ip4": "208.67.220.123",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Cisco / OpenDNS",
        "tags": ["malware", "family", "anycast"],
        "description_en": "OpenDNS FamilyShield 208.67.220.123 — secondary family-safe resolver.",
    },

    # -----------------------------------------------------------------------
    # Alternate DNS (original IPs from task description)
    # -----------------------------------------------------------------------
    {
        "name": "Alternate DNS Legacy Primary",
        "ip4": "198.101.242.72",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Alternate DNS",
        "tags": ["adblock"],
        "description_en": "Alternate DNS 198.101.242.72 — legacy ad-blocking resolver IP.",
    },
    {
        "name": "Alternate DNS Legacy Secondary",
        "ip4": "23.253.163.53",
        "ip6": None,
        "doh_url": None,
        "dot_host": None,
        "port": 53,
        "country": "US",
        "operator": "Alternate DNS",
        "tags": ["adblock"],
        "description_en": "Alternate DNS 23.253.163.53 — legacy secondary ad-blocking resolver IP.",
    },

    # -----------------------------------------------------------------------
    # NextDNS (DoH/DoT only — already present, skip duplicate ip4=None entry)
    # dns0.eu (European, privacy)
    # -----------------------------------------------------------------------
    {
        "name": "dns0.eu",
        "ip4": "193.110.81.0",
        "ip6": "2a0f:fc80::",
        "doh_url": "https://dns0.eu/",
        "dot_host": "dns0.eu",
        "dot_port": 853,
        "port": 53,
        "country": "EU",
        "operator": "dns0.eu",
        "tags": ["no-log", "dnssec", "privacy"],
        "description_en": "dns0.eu 193.110.81.0 — European privacy-first resolver, no logging, DNSSEC.",
    },
    {
        "name": "dns0.eu KIDS",
        "ip4": "193.110.81.1",
        "ip6": "2a0f:fc80::1",
        "doh_url": "https://kids.dns0.eu/",
        "dot_host": "kids.dns0.eu",
        "dot_port": 853,
        "port": 53,
        "country": "EU",
        "operator": "dns0.eu",
        "tags": ["family", "no-log", "dnssec"],
        "description_en": "dns0.eu KIDS 193.110.81.1 — child-safe filtering, no logging.",
    },

    # -----------------------------------------------------------------------
    # Wikimedia DNS (non-profit)
    # -----------------------------------------------------------------------
    {
        "name": "Wikimedia DNS",
        "ip4": None,
        "ip6": None,
        "doh_url": "https://wikimedia-dns.org/dns-query",
        "dot_host": "wikimedia-dns.org",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "Wikimedia Foundation",
        "tags": ["no-log", "dnssec"],
        "description_en": "Wikimedia DNS — non-profit DoH/DoT resolver, no logging, DNSSEC.",
    },

    # -----------------------------------------------------------------------
    # Cloudflare for Families (malware+adult) — additional entry beyond 1.1.1.3
    # (1.1.1.3 already present as 'Cloudflare Family', this is the DoH alias)
    # -----------------------------------------------------------------------
    {
        "name": "Cloudflare Family DoH",
        "ip4": None,
        "ip6": None,
        "doh_url": "https://family.cloudflare-dns.com/dns-query",
        "dot_host": "family.cloudflare-dns.com",
        "dot_port": 853,
        "port": 53,
        "country": "US",
        "operator": "Cloudflare Inc.",
        "tags": ["malware", "family", "dnssec", "anycast", "fast", "no-log"],
        "description_en": "Cloudflare for Families DoH endpoint — blocks malware and adult content.",
    },
]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def get_servers_by_tag(*tags: str) -> list[dict]:
    """
    Return all servers that have ALL of the specified *tags*.

    Example::

        get_servers_by_tag("malware", "dnssec")
    """
    tag_set = set(tags)
    return [s for s in SERVER_DB if tag_set.issubset(set(s.get("tags", [])))]


def get_servers_by_country(country_code: str) -> list[dict]:
    """
    Return all servers whose ``country`` field matches *country_code*
    (case-insensitive ISO 3166-1 alpha-2 or region string).
    """
    cc = country_code.upper()
    return [s for s in SERVER_DB if s.get("country", "").upper() == cc]


def get_servers_with_doh() -> list[dict]:
    """Return all servers that have a DoH endpoint configured."""
    return [s for s in SERVER_DB if s.get("doh_url")]


def get_servers_with_dot() -> list[dict]:
    """Return all servers that have a DoT hostname configured."""
    return [s for s in SERVER_DB if s.get("dot_host")]


def get_servers_with_ip() -> list[dict]:
    """Return all servers that have at least one plain IP (UDP/TCP capable)."""
    return [s for s in SERVER_DB if s.get("ip4") or s.get("ip6")]


def server_count() -> int:
    """Return the total number of entries in SERVER_DB."""
    return len(SERVER_DB)
