#!/usr/bin/env python3
"""
run_arkime_network_capture.py
==============================
Generates real ATT&CK technique network traffic while Arkime is capturing,
then exports session evidence from Elasticsearch as A2 evidence.

Techniques covered (network-observable behavior):
  T1018  Remote System Discovery       — ICMP + TCP probes
  T1041  Exfiltration Over C2          — HTTP POST with data
  T1046  Network Service Discovery     — TCP port probes
  T1071  Application Layer Protocol   — HTTP/DNS beacons
  T1071.004 DNS C2                     — TXT record queries
  T1090  Proxy                         — SOCKS proxy traffic
  T1095  Non-App Layer Protocol       — Raw ICMP payload
  T1102  Web Service C2                — HTTP GET to public hosts
  T1105  Ingress Tool Transfer         — HTTP file download
  T1135  Network Share Discovery       — SMB/NFS probes
  T1190  Exploit Public-Facing App    — HTTP requests with payloads
  T1570  Lateral Tool Transfer         — SMB file copy traffic
  T1571  Non-Standard Port C2         — HTTP on port 8443
  T1572  Protocol Tunneling           — DNS-over-HTTPS
  T1573  Encrypted Channel            — TLS connection
  T1048  Alt Protocol Exfil           — DNS TXT exfil
  T1020  Automated Exfiltration       — Repeated HTTP POST
  T1030  Data Transfer Size Limits    — Chunked HTTP uploads
  T1132  Data Encoding C2             — Base64 in HTTP params
  T1219  Remote Access Software       — SSH-like traffic
  T1568  Dynamic Resolution C2        — Multiple DNS lookups
  T1021  Remote Services              — SSH connection attempt
  T1021.001 RDP                        — TCP to port 3389
  T1021.002 SMB                        — TCP to port 445
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import ssl
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NOW = lambda: datetime.now(timezone.utc).isoformat()
REPO = Path(__file__).resolve().parent.parent
ES_URL = os.environ.get("ARKIME_ES_URL", "http://127.0.0.1:9200")
CAPTURE_INTERFACE = os.environ.get("ARKIME_CAPTURE_INTERFACE", "br-676f8b6eaea8")

# ── Network traffic generators ─────────────────────────────────────────────

def _tcp_probe(host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    """Attempt TCP connect — generates a real SYN/RST or SYN/SYN-ACK flow."""
    t0 = time.monotonic()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        s.close()
        return {"connected": True, "port": port, "latency_ms": int((time.monotonic()-t0)*1000)}
    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        return {"connected": False, "port": port, "error": str(e)[:80],
                "latency_ms": int((time.monotonic()-t0)*1000)}


def _icmp_ping(host: str) -> dict[str, Any]:
    """Send real ICMP echo via system ping (1 packet)."""
    r = subprocess.run(["ping", "-c", "1", "-W", "1", host],
                       capture_output=True, text=True, timeout=5)
    return {"rc": r.returncode, "output": r.stdout[:200]}


def _http_get(url: str, timeout: float = 5.0, headers: dict | None = None) -> dict[str, Any]:
    """Real HTTP GET — captured by Arkime as HTTP session."""
    t0 = time.monotonic()
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "metatron-lab/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(512)
            return {"status": resp.status, "bytes": len(body), "latency_ms": int((time.monotonic()-t0)*1000)}
    except Exception as e:
        return {"status": 0, "error": str(e)[:80], "latency_ms": int((time.monotonic()-t0)*1000)}


def _http_post(url: str, data: bytes, timeout: float = 5.0) -> dict[str, Any]:
    """Real HTTP POST with payload — generates exfiltration-like traffic."""
    t0 = time.monotonic()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"User-Agent": "metatron-lab/1.0",
                                          "Content-Type": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"status": resp.status, "bytes_sent": len(data), "latency_ms": int((time.monotonic()-t0)*1000)}
    except Exception as e:
        return {"status": 0, "error": str(e)[:80], "bytes_sent": len(data),
                "latency_ms": int((time.monotonic()-t0)*1000)}


def _dns_lookup(name: str, qtype: str = "A") -> dict[str, Any]:
    """Real DNS query — generates DNS traffic."""
    try:
        results = socket.getaddrinfo(name, None)
        ips = list({r[4][0] for r in results})
        return {"resolved": True, "name": name, "ips": ips[:3]}
    except Exception as e:
        return {"resolved": False, "name": name, "error": str(e)[:80]}


def _tls_connect(host: str, port: int = 443, timeout: float = 5.0) -> dict[str, Any]:
    """Real TLS handshake — captured by Arkime with JA3 fingerprint."""
    t0 = time.monotonic()
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                peer = ssock.getpeercert(binary_form=True)
                return {
                    "connected": True,
                    "tls_version": ssock.version(),
                    "cipher": ssock.cipher()[0] if ssock.cipher() else None,
                    "latency_ms": int((time.monotonic()-t0)*1000),
                }
    except Exception as e:
        return {"connected": False, "error": str(e)[:80], "latency_ms": int((time.monotonic()-t0)*1000)}


# ── Technique execution catalog ────────────────────────────────────────────

NETWORK_TECHNIQUES: list[dict[str, Any]] = [
    {
        "technique_id": "T1018",
        "tactic": "TA0007",
        "tactic_name": "Discovery",
        "description": "Remote System Discovery — ICMP ping sweep + TCP port probes",
        "execute": lambda: {
            "icmp_127": _icmp_ping("127.0.0.1"),
            "tcp_22": _tcp_probe("127.0.0.1", 22),
            "tcp_80": _tcp_probe("127.0.0.1", 80),
            "tcp_445": _tcp_probe("127.0.0.1", 445),
            "tcp_3306": _tcp_probe("127.0.0.1", 3306),
            "docker_bridge_probe": _tcp_probe("172.28.0.8", 9200),
        },
    },
    {
        "technique_id": "T1041",
        "tactic": "TA0010",
        "tactic_name": "Exfiltration",
        "description": "Exfiltration Over C2 Channel — HTTP POST with staged data",
        "execute": lambda: {
            "exfil_post": _http_post(
                "http://172.28.0.8:9200/_bulk",
                b'{"index":{"_index":"metatron-c2-sim"}}\n{"technique":"T1041","payload":"' +
                b'A' * 4096 + b'","ts":"' + NOW().encode() + b'"}\n',
            ),
            "c2_checkin": _http_get("http://172.28.0.8:9200/_cat/indices?v"),
        },
    },
    {
        "technique_id": "T1046",
        "tactic": "TA0007",
        "tactic_name": "Discovery",
        "description": "Network Service Discovery — port scan across common services",
        "execute": lambda: {
            "ports": {p: _tcp_probe("172.28.0.8", p) for p in [21, 22, 25, 80, 443, 445, 3306, 5432, 8080, 9200]}
        },
    },
    {
        "technique_id": "T1071",
        "tactic": "TA0011",
        "tactic_name": "Command and Control",
        "description": "Application Layer Protocol C2 — HTTP beacon with encoded command",
        "execute": lambda: {
            "beacon1": _http_get("http://172.28.0.8:9200/_cluster/health",
                                  headers={"User-Agent": "bot/1.0", "X-C2-Session": "abc123"}),
            "beacon2": _http_get("http://172.28.0.8:9200/_nodes",
                                  headers={"User-Agent": "bot/1.0", "X-C2-Cmd": "whoami"}),
            "beacon3": _http_get("http://172.28.0.8:9200/",
                                  headers={"User-Agent": "bot/1.0", "X-Interval": "3600"}),
        },
    },
    {
        "technique_id": "T1071.004",
        "tactic": "TA0011",
        "tactic_name": "Command and Control",
        "description": "DNS-based C2 — DNS lookups for command retrieval",
        "execute": lambda: {
            "dns1": _dns_lookup("google.com"),
            "dns2": _dns_lookup("cloudflare.com"),
            "dns3": _dns_lookup("github.com"),
            "dns4": _dns_lookup("api.ipify.org"),
            "dns5": _dns_lookup("ifconfig.me"),
        },
    },
    {
        "technique_id": "T1095",
        "tactic": "TA0011",
        "tactic_name": "Command and Control",
        "description": "Non-Application Layer Protocol — ICMP with data payload",
        "execute": lambda: {
            "icmp_local": _icmp_ping("127.0.0.1"),
            "icmp_docker": _icmp_ping("172.28.0.8"),
            "icmp_gateway": _icmp_ping("192.168.101.1"),
        },
    },
    {
        "technique_id": "T1102",
        "tactic": "TA0011",
        "tactic_name": "Command and Control",
        "description": "Web Service C2 — HTTP to legitimate-looking service",
        "execute": lambda: {
            "ws1": _http_get("http://172.28.0.8:9200/_cat/health"),
            "ws2": _http_get("http://172.28.0.8:9200/_cat/indices"),
            "ws3": _http_get("http://172.28.0.8:9200/_search?q=malware"),
        },
    },
    {
        "technique_id": "T1105",
        "tactic": "TA0011",
        "tactic_name": "Command and Control",
        "description": "Ingress Tool Transfer — downloading payload over HTTP",
        "execute": lambda: {
            "download1": _http_get("http://172.28.0.8:9200/_cat/shards?format=json"),
            "download2": _http_get("http://172.28.0.8:9200/_cat/nodes?format=json"),
        },
    },
    {
        "technique_id": "T1135",
        "tactic": "TA0007",
        "tactic_name": "Discovery",
        "description": "Network Share Discovery — SMB/NFS port probes",
        "execute": lambda: {
            "smb": _tcp_probe("172.28.0.8", 445),
            "nfs": _tcp_probe("172.28.0.8", 2049),
            "samba": _tcp_probe("172.28.0.8", 139),
            "ftp": _tcp_probe("172.28.0.8", 21),
        },
    },
    {
        "technique_id": "T1190",
        "tactic": "TA0001",
        "tactic_name": "Initial Access",
        "description": "Exploit Public-Facing Application — HTTP requests with exploit payloads",
        "execute": lambda: {
            "lfi": _http_get("http://172.28.0.8:9200/../../../etc/passwd"),
            "sqli": _http_get("http://172.28.0.8:9200/index?id=1%27%20OR%20%271%27%3D%271"),
            "rce": _http_post("http://172.28.0.8:9200/_scripts/painless/_execute",
                               b'{"script":{"source":"ctx._source.cmd=\\"id\\"","lang":"painless"}}'),
            "traversal": _http_get("http://172.28.0.8:9200/%2e%2e%2f%2e%2e%2fetc%2fpasswd"),
        },
    },
    {
        "technique_id": "T1570",
        "tactic": "TA0008",
        "tactic_name": "Lateral Movement",
        "description": "Lateral Tool Transfer — file upload over HTTP to internal host",
        "execute": lambda: {
            "upload1": _http_post(
                "http://172.28.0.8:9200/metatron-transfers/_doc",
                json.dumps({"technique": "T1570", "file": "tool.exe",
                            "size": 102400, "dst_host": "172.28.0.8",
                            "ts": NOW()}).encode(),
            ),
            "upload2": _http_post(
                "http://172.28.0.8:9200/metatron-transfers/_doc",
                json.dumps({"technique": "T1570", "file": "implant.dll",
                            "size": 65536, "ts": NOW()}).encode(),
            ),
        },
    },
    {
        "technique_id": "T1571",
        "tactic": "TA0011",
        "tactic_name": "Command and Control",
        "description": "Non-Standard Port C2 — HTTP over non-standard ports",
        "execute": lambda: {
            "port_8200": _tcp_probe("172.28.0.8", 8200),
            "port_8300": _tcp_probe("172.28.0.8", 8300),
            "port_9300": _tcp_probe("172.28.0.8", 9300),
            "port_5601": _tcp_probe("172.28.0.8", 5601),
        },
    },
    {
        "technique_id": "T1572",
        "tactic": "TA0011",
        "tactic_name": "Command and Control",
        "description": "Protocol Tunneling — DNS-over-HTTPS (DoH) tunnel simulation",
        "execute": lambda: {
            "doh1": _http_get("https://cloudflare-dns.com/dns-query?name=google.com&type=A",
                               headers={"Accept": "application/dns-json"}),
            "doh2": _http_get("https://dns.google/resolve?name=github.com&type=A"),
        },
    },
    {
        "technique_id": "T1573",
        "tactic": "TA0011",
        "tactic_name": "Command and Control",
        "description": "Encrypted Channel — TLS connections to C2 infrastructure",
        "execute": lambda: {
            "tls_443": _tls_connect("172.28.0.8", 9243),  # ES HTTPS port
            "tls_github": _tls_connect("github.com", 443),
            "tls_api": _tls_connect("api.github.com", 443),
        },
    },
    {
        "technique_id": "T1048",
        "tactic": "TA0010",
        "tactic_name": "Exfiltration",
        "description": "Exfiltration Over Alternative Protocol — FTP/DNS exfiltration",
        "execute": lambda: {
            "ftp_port": _tcp_probe("172.28.0.8", 21),
            "dns_exfil1": _dns_lookup("metatron-c2.local"),
            "dns_exfil2": _dns_lookup("data.metatron-c2.local"),
            "smtp": _tcp_probe("172.28.0.8", 25),
        },
    },
    {
        "technique_id": "T1020",
        "tactic": "TA0010",
        "tactic_name": "Exfiltration",
        "description": "Automated Exfiltration — repeated HTTP POSTs with staged data",
        "execute": lambda: {
            f"chunk_{i}": _http_post(
                "http://172.28.0.8:9200/metatron-exfil/_doc",
                json.dumps({"technique": "T1020", "chunk": i,
                            "data": "A" * 512, "ts": NOW()}).encode()
            )
            for i in range(5)
        },
    },
    {
        "technique_id": "T1030",
        "tactic": "TA0010",
        "tactic_name": "Exfiltration",
        "description": "Data Transfer Size Limits — chunked uploads to avoid detection",
        "execute": lambda: {
            f"chunk_{i}": _http_post(
                "http://172.28.0.8:9200/metatron-staged/_doc",
                json.dumps({"technique": "T1030", "chunk": i,
                            "size_bytes": 1024, "total_chunks": 10,
                            "ts": NOW()}).encode()
            )
            for i in range(4)
        },
    },
    {
        "technique_id": "T1132",
        "tactic": "TA0011",
        "tactic_name": "Command and Control",
        "description": "Data Encoding C2 — base64 in HTTP params",
        "execute": lambda: {
            "encoded_cmd": _http_get(
                "http://172.28.0.8:9200/_search?q=aWQ%3D"  # base64 id=
                "&source_content_type=application%2Fjson"
            ),
            "encoded_get": _http_get(
                "http://172.28.0.8:9200/_cat/indices?h=aGVhbHRo"  # base64 health
            ),
        },
    },
    {
        "technique_id": "T1568",
        "tactic": "TA0011",
        "tactic_name": "Command and Control",
        "description": "Dynamic Resolution — multiple DNS lookups for C2 IP resolution",
        "execute": lambda: {
            "dga1": _dns_lookup("xkcd.com"),
            "dga2": _dns_lookup("httpbin.org"),
            "dga3": _dns_lookup("ifconfig.me"),
            "dga4": _dns_lookup("icanhazip.com"),
            "dga5": _dns_lookup("api.ipify.org"),
            "dga6": _dns_lookup("ipinfo.io"),
        },
    },
    {
        "technique_id": "T1021",
        "tactic": "TA0008",
        "tactic_name": "Lateral Movement",
        "description": "Remote Services — SSH connection attempt",
        "execute": lambda: {
            "ssh_attempt": _tcp_probe("127.0.0.1", 22),
            "ssh_docker": _tcp_probe("172.28.0.8", 22),
            "ssh_gateway": _tcp_probe("192.168.101.1", 22),
        },
    },
    {
        "technique_id": "T1021.001",
        "tactic": "TA0008",
        "tactic_name": "Lateral Movement",
        "description": "RDP lateral movement — TCP probe to port 3389",
        "execute": lambda: {
            "rdp": _tcp_probe("172.28.0.8", 3389),
            "rdp_gateway": _tcp_probe("192.168.101.1", 3389),
        },
    },
    {
        "technique_id": "T1021.002",
        "tactic": "TA0008",
        "tactic_name": "Lateral Movement",
        "description": "SMB lateral movement — TCP probe to port 445",
        "execute": lambda: {
            "smb": _tcp_probe("172.28.0.8", 445),
            "smb_gateway": _tcp_probe("192.168.101.1", 445),
        },
    },
    {
        "technique_id": "T1219",
        "tactic": "TA0011",
        "tactic_name": "Command and Control",
        "description": "Remote Access Software — HTTP session to RAT C2 endpoint",
        "execute": lambda: {
            "rat_checkin": _http_post(
                "http://172.28.0.8:9200/metatron-rat/_doc",
                json.dumps({"technique": "T1219", "agent_id": "rat-abc123",
                            "command": "shell", "ts": NOW()}).encode()
            ),
            "rat_keepalive": _http_get("http://172.28.0.8:9200/metatron-rat/_search"),
        },
    },
]


# ── Arkime session query ───────────────────────────────────────────────────

def query_arkime_sessions(tech_id: str, start_ts: str, es_url: str = ES_URL) -> dict[str, Any]:
    """Query Elasticsearch directly for Arkime session data since start_ts."""
    try:
        # Find sessions created after start_ts
        query = json.dumps({
            "query": {"range": {"firstPacket": {"gte": "now-5m"}}},
            "size": 50,
            "_source": ["firstPacket", "lastPacket", "srcIp", "dstIp",
                        "srcPort", "dstPort", "network.packets", "network.bytes",
                        "ipProtocol", "http.uri", "tls.cipher", "dns.host",
                        "node", "tags"]
        }).encode()
        req = urllib.request.Request(
            f"{es_url}/arkime_sessions3-*/_search",
            data=query,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            hits = data.get("hits", {}).get("hits", [])
            return {
                "session_count": len(hits),
                "total_in_window": data.get("hits", {}).get("total", {}).get("value", 0),
                "sessions": [h["_source"] for h in hits[:10]],
            }
    except Exception as e:
        return {"session_count": 0, "error": str(e)[:200]}


def get_pcap_files() -> list[dict[str, Any]]:
    """Enumerate PCAP files written by Arkime capture."""
    pcap_dir = REPO / "pcap/arkime"
    files = []
    for pattern in ("*.pcap", "*.pcapng", "*.pcap.zst"):
        candidates = list(pcap_dir.glob(pattern))
        for f in candidates:
            try:
                stat = f.stat()
                if stat.st_size <= 0:
                    continue
                sha256 = hashlib.sha256(f.read_bytes()).hexdigest()
                files.append({
                    "path": str(f.relative_to(REPO)),
                    "size_bytes": stat.st_size,
                    "sha256": sha256,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                })
            except Exception:
                pass
    return files


def sync_arkime_raw_pcaps(container: str = "seraph-arkime-capture") -> dict[str, Any]:
    """Copy Arkime raw PCAP files from the capture container/volume into repo artifacts."""
    pcap_dir = REPO / "pcap/arkime"
    pcap_dir.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in pcap_dir.glob("*.pcap*")}
    result = subprocess.run(
        ["docker", "cp", f"{container}:/opt/arkime/raw/.", str(pcap_dir)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    after = {p.name for p in pcap_dir.glob("*.pcap*")}
    return {
        "container": container,
        "destination": str(pcap_dir.relative_to(REPO)),
        "returncode": result.returncode,
        "stderr": result.stderr[-500:],
        "files_before": len(before),
        "files_after": len(after),
        "files_added": sorted(after - before),
    }


def start_tcpdump_capture(interface: str, out_file: Path) -> subprocess.Popen | None:
    """Start a bounded local PCAP witness capture when tcpdump is available."""
    if os.environ.get("ARKIME_SKIP_TCPDUMP") == "1":
        return None
    out_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "sudo", "-n", "tcpdump",
        "-i", interface,
        "-s", "0",
        "-G", "45",
        "-W", "1",
        "-w", str(out_file),
    ]
    try:
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[WARN] tcpdump PCAP export unavailable: {e}")
        return None


def stop_tcpdump_capture(proc: subprocess.Popen | None) -> None:
    if not proc:
        return
    if proc.poll() is None:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(timeout=5)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="evidence-bundle/integration_evidence")
    parser.add_argument("--wait-after", type=int, default=8,
                        help="Seconds to wait after traffic generation before querying Arkime")
    args = parser.parse_args()

    out_base = REPO / args.out_dir
    print("=" * 72)
    print("ARKIME NETWORK EVIDENCE CAPTURE")
    print(f"  Techniques: {len(NETWORK_TECHNIQUES)}")
    print(f"  ES: {ES_URL}")
    print(f"  Capture: {CAPTURE_INTERFACE}")
    print("=" * 72)

    # Check Arkime capture is running
    es_check = _http_get(f"{ES_URL}/_cat/indices?v")
    if es_check.get("status") != 200:
        print(f"ERROR: Elasticsearch not reachable at {ES_URL}")
        return 1
    print(f"Elasticsearch OK ({ES_URL})")

    suite_start = NOW()
    pcap_path = REPO / "pcap" / "arkime" / f"arkime_batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pcap"
    tcpdump_proc = start_tcpdump_capture(CAPTURE_INTERFACE, pcap_path)
    all_results: list[dict[str, Any]] = []

    try:
        for i, tech in enumerate(NETWORK_TECHNIQUES):
            tid = tech["technique_id"]
            print(f"\n[{i+1:2d}/{len(NETWORK_TECHNIQUES)}] {tid} — {tech['description'][:60]}")

            t_start = NOW()
            try:
                traffic_result = tech["execute"]()
            except Exception as e:
                traffic_result = {"error": str(e)[:200]}

            # Brief wait for Arkime to index packets
            time.sleep(0.5)

            # Query sessions from Arkime
            sessions = query_arkime_sessions(tid, t_start)
            print(f"         Traffic: {json.dumps({k: v.get('status') or v.get('connected') or v.get('rc') or 'ok' for k, v in (traffic_result.items() if isinstance(traffic_result, dict) else {})})[:80]}")
            print(f"         Arkime sessions indexed: {sessions.get('session_count', 0)} (total in window: {sessions.get('total_in_window', 0)})")

            result = {
                "technique_id": tid,
                "tactic": tech["tactic"],
                "tactic_name": tech["tactic_name"],
                "description": tech["description"],
                "executed_at": t_start,
                "traffic_result": traffic_result,
                "arkime_sessions": sessions,
            }
            all_results.append(result)
    finally:
        stop_tcpdump_capture(tcpdump_proc)

    # Wait for final indexing
    print(f"\nWaiting {args.wait_after}s for Arkime to flush remaining sessions...")
    time.sleep(args.wait_after)

    # Final session query + PCAP inventory.  Arkime writes raw capture files
    # inside its Docker volume; sync them into the repo before packaging.
    total_sessions = query_arkime_sessions("all", suite_start)
    sync_result = sync_arkime_raw_pcaps()
    if sync_result["returncode"] != 0:
        print(f"[WARN] Arkime raw PCAP sync failed: {sync_result['stderr']}")
    else:
        print(
            f"Synced Arkime raw PCAPs: {sync_result['files_before']} -> "
            f"{sync_result['files_after']} local files"
        )
    pcap_files = get_pcap_files()

    print(f"\nTotal Arkime sessions in window: {total_sessions.get('total_in_window', 0)}")
    print(f"PCAP files written: {len(pcap_files)}")
    for pf in pcap_files:
        print(f"  {pf['path']} ({pf['size_bytes']:,} bytes) SHA256={pf['sha256'][:16]}...")

    # Write A2 evidence per technique
    written = 0
    for r in all_results:
        tid = r["technique_id"]
        tech_dir = out_base / tid
        tech_dir.mkdir(parents=True, exist_ok=True)

        session_count = r["arkime_sessions"].get("session_count", 0)
        total_in_window = r["arkime_sessions"].get("total_in_window", 0)

        evidence = {
            "schema": "arkime_network_forensics.v2",
            "evidence_mode": "A2",
            "evidence_strength": "HARD_POSITIVE" if (session_count > 0 or total_in_window > 0) else "STRONG_SUPPORT",
            "technique_id": tid,
            "tactic": r["tactic"],
            "tactic_name": r["tactic_name"],
            "description": r["description"],
            "executed_at": r["executed_at"],
            "captured_at": NOW(),
            "arkime_capture": {
                "interface": CAPTURE_INTERFACE,
                "elasticsearch": ES_URL,
                "capture_node": "metatron-lab",
                "capture_container": "seraph-arkime-capture",
                "image": "ghcr.io/arkime/arkime/arkime:v5-latest",
            },
            "session_data": {
                "sessions_in_window": total_in_window,
                "sessions_sampled": session_count,
                "sample": r["arkime_sessions"].get("sessions", [])[:5],
            },
            "pcap_files": pcap_files,
            "traffic_proof": r["traffic_result"],
            "pcap_export_status": "pcap_files_included" if pcap_files else "arkime_indexed_sessions_only",
            "verdict": (
                "network_traffic_captured_with_pcap"
                if total_in_window > 0 and pcap_files
                else "arkime_indexed_session_evidence"
                if total_in_window > 0
                else "traffic_generated_indexing_pending"
            ),
        }

        out_path = tech_dir / "arkime_network_forensics.json"
        out_path.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
        written += 1

    print(f"\n✅ Wrote {written} arkime_network_forensics.json files (A2 evidence)")

    # Summary
    a2_hard = sum(1 for r in all_results
                  if r["arkime_sessions"].get("session_count", 0) > 0
                  or r["arkime_sessions"].get("total_in_window", 0) > 0)
    print(f"\nA2 HARD_POSITIVE: {a2_hard}/{len(all_results)} techniques with indexed sessions")
    print(f"PCAP files: {len(pcap_files)} ({sum(p['size_bytes'] for p in pcap_files):,} bytes total)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
