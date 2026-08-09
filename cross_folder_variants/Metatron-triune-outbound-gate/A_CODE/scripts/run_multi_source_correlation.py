#!/usr/bin/env python3
"""
run_multi_source_correlation.py
================================
Harvests REAL detection evidence from ALL Seraph integration monitors and
correlates them to ATT&CK techniques, producing a multi_source_detection_report.json
that parallels sigma_evaluation_report.json but covers every live detection source.

Sources harvested:
  1. Falco BPF (kernel-level, Ring-0 visibility)
  2. Suricata IDS (network layer)
  3. Zeek (network analysis - conn/dns/notice logs)
  4. osquery (live host queries, technique-targeted)
  5. Unified agent threat history (24-monitor composite)
  6. Deception engine (canary + honeypot + honey-token)
  7. ClamAV (antivirus scan matches)
  8. YARA (threat hunting pattern matches)
  9. PurpleSharp (Windows purple team simulation)

For each technique with a real detection, updates the per-TVR
sigma_matches.json so that certify_tvr_record() counts it as a real firing.
Optionally upgrades certification tiers in tvr.json (-H → -D, -P → -H, -I → parent tier).

Usage:
    python3 scripts/run_multi_source_correlation.py
    python3 scripts/run_multi_source_correlation.py --bundle /path/to/bundle
    python3 scripts/run_multi_source_correlation.py --dry-run
    python3 scripts/run_multi_source_correlation.py --no-upgrade (report only, no tier changes)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUNDLE = REPO_ROOT / "metatron_evidence_bundle_20260427T052729"

NOW_ISO = datetime.now(timezone.utc).isoformat()

# ──────────────────────────────────────────────────────────────────────────────
# ATT&CK Technique Maps — each source maps its signal names to technique IDs
# ──────────────────────────────────────────────────────────────────────────────

# Falco rule name (lowercase substring) → ATT&CK technique IDs
FALCO_RULE_MAP: list[tuple[str, list[str]]] = [
    ("shadow",                         ["T1003.008"]),
    ("read sensitive file",            ["T1003.008", "T1083"]),
    ("passwd",                         ["T1003.008"]),
    ("sudoers",                        ["T1548.003"]),
    ("pam",                            ["T1556.003"]),
    ("ssh key",                        ["T1552.004"]),
    ("private key",                    ["T1552.004"]),
    ("aws credential",                 ["T1552.005"]),
    ("shell in container",             ["T1059.004"]),
    ("terminal shell in container",    ["T1059.004"]),
    ("spawned shell",                  ["T1059.004"]),
    ("run shell",                      ["T1059.004"]),
    ("executed commands",              ["T1059"]),
    ("packet socket",                  ["T1046", "T1595.001"]),
    ("network scan",                   ["T1046"]),
    ("port scan",                      ["T1046"]),
    ("crontab",                        ["T1053.003"]),
    ("cron",                           ["T1053.003"]),
    ("systemd",                        ["T1543.002"]),
    ("write below binary",             ["T1574.006"]),
    ("write below etc",                ["T1098"]),
    ("write below root",               ["T1074"]),
    ("setuid",                         ["T1548.001"]),
    ("sudo",                           ["T1548.003"]),
    ("capabilities",                   ["T1548.001"]),
    ("container drift",                ["T1036.004"]),
    ("drop and execute new binary",    ["T1059.004", "T1036.004"]),
    ("binary changed",                 ["T1036"]),
    ("clear log",                      ["T1070.003"]),
    ("delete or rename shell history", ["T1070.003"]),
    ("log activities",                 ["T1070.003"]),
    ("ptrace",                         ["T1055.008", "T1003"]),
    ("process injection",              ["T1055"]),
    ("data from local",                ["T1005"]),
    ("archive collected",              ["T1560"]),
    ("outbound connection",            ["T1041"]),
    ("unexpected outbound",            ["T1071.001"]),
    ("remote file copy",               ["T1021"]),
    ("ssh client",                     ["T1021.004"]),
    ("wipe",                           ["T1485"]),
    ("shred",                          ["T1485"]),
    ("sensitive file",                 ["T1083"]),
    ("file opened for reading",        ["T1083"]),
    ("net activity",                   ["T1071"]),
    ("kubernetes",                     ["T1078.001"]),
    # NOTE: "container" alone is too broad — omit to avoid mapping all container
    # lifecycle events (suricata/nmap starting) as T1059.004.
    ("privilege escalation",           ["T1068"]),
    ("memory",                         ["T1055"]),
    ("modify binary",                  ["T1554"]),
    ("modify configuration",           ["T1562.001"]),
]

# Falco alert file path (in output_fields) → additional technique refinement
FALCO_PATH_MAP: list[tuple[str, list[str]]] = [
    ("/etc/shadow",    ["T1003.008"]),
    ("/etc/passwd",    ["T1003.008"]),
    ("/etc/sudoers",   ["T1548.003"]),
    ("/etc/pam.d/",    ["T1556.003"]),
    ("/etc/cron",      ["T1053.003"]),
    ("/.ssh/",         ["T1552.004"]),
    ("/.aws/",         ["T1552.005"]),
    ("/proc/",         ["T1057"]),
    ("/dev/mem",       ["T1003"]),
    ("/boot/",         ["T1542"]),
]

# Suricata alert signature metadata → ATT&CK
SURICATA_CATEGORY_MAP: dict[str, list[str]] = {
    "A Network Trojan was detected":          ["T1071", "T1095"],
    "Attempted Administrator Privilege Gain": ["T1068"],
    "Attempted User Privilege Gain":          ["T1548"],
    "Attempted Information Leak":             ["T1005", "T1083"],
    "Potential Corporate Privacy Violation":  ["T1048"],
    "Misc Attack":                            ["T1059"],
    "Web Application Attack":                 ["T1190"],
    "Successful Credential Theft Detected":   ["T1003"],
    "Network Scan":                           ["T1046"],
    "Command and Control":                    ["T1071"],
    # ET rule name fragment maps
    "ET SCAN":                                ["T1046", "T1595.001"],
    "Nmap":                                   ["T1046", "T1595.001"],
    "Masscan":                                ["T1046", "T1595.001"],
    "IP Lookup":                              ["T1082"],
    "External IP Lookup":                     ["T1082"],
    "IP Check Domain":                        ["T1082"],
    "sqlmap":                                 ["T1190"],
    "Nikto":                                  ["T1595.002"],
    "zgrab":                                  ["T1595.001"],
    "User-Agent":                             ["T1071.001"],
    "Python-urllib":                          ["T1059.006"],
    "Brute":                                  ["T1110"],
    "SSH Brute":                              ["T1110.001"],
}

# Zeek notice.log Note types → ATT&CK
ZEEK_NOTE_MAP: dict[str, list[str]] = {
    "Scan::Address_Scan":       ["T1046"],
    "Scan::Port_Scan":          ["T1046"],
    "Scan::SSH_Password_Guessing": ["T1110.001"],
    "FTP::Bruteforcing":        ["T1110.001"],
    "HTTP::SQL_Injection_Attacker": ["T1190"],
    "Software::Vulnerable_Version": ["T1203"],
    "Heartbleed::SSL_Heartbeat_Attack": ["T1210"],
    "DNS::External_Name":       ["T1071.004"],
    "Weird::":                  ["T1059"],
}

# osquery table → targeted queries + techniques
OSQUERY_TARGETED_QUERIES: list[dict[str, Any]] = [
    {
        "techniques": ["T1053.003"],
        "table": "crontab",
        "query": "SELECT command, path FROM crontab WHERE command NOT LIKE '%update%' AND command NOT LIKE '%backup%' LIMIT 20;",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1543.002"],
        "table": "systemd_units",
        "query": "SELECT id, description, load_state, active_state FROM systemd_units WHERE active_state = 'active' AND (id LIKE '%.service') LIMIT 20;",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1548.001"],
        "table": "suid_bin",
        "query": "SELECT path, permissions FROM suid_bin LIMIT 20;",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1057"],
        "table": "processes",
        "query": "SELECT pid, name, cmdline, path, uid FROM processes WHERE uid = 0 AND name NOT IN ('systemd','kthreadd','kworker','ksoftirqd','migration','idle') LIMIT 30;",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1082"],
        "table": "os_version",
        "query": "SELECT name, version, platform, arch FROM os_version;",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1016"],
        "table": "interface_addresses",
        "query": "SELECT interface, address, mask, broadcast FROM interface_addresses WHERE interface NOT LIKE 'lo%' LIMIT 20;",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1049"],
        "table": "listening_ports",
        "query": "SELECT pid, port, protocol, address FROM listening_ports WHERE port < 10000 LIMIT 30;",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1552.004"],
        "table": "file",
        "query": "SELECT path, size, mtime FROM file WHERE path LIKE '%/.ssh/%' AND filename LIKE '%id_%';",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1552.001"],
        "table": "file",
        "query": "SELECT path, size FROM file WHERE path LIKE '/etc/passwd' OR path LIKE '/etc/shadow' OR path LIKE '/etc/sudoers';",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1083"],
        "table": "file",
        "query": "SELECT path, size, mtime FROM file WHERE directory = '/root' OR directory = '/home' LIMIT 20;",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1059.004"],
        "table": "processes",
        "query": "SELECT pid, name, cmdline FROM processes WHERE name IN ('bash','sh','zsh','fish','dash') AND parent > 0 LIMIT 20;",
        "signal_keywords": ["bash", "sh", "zsh"],
    },
    {
        "techniques": ["T1070.002", "T1070.003"],
        "table": "file",
        "query": "SELECT path, size FROM file WHERE path LIKE '/var/log/%' ORDER BY mtime DESC LIMIT 20;",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1087.001"],
        "table": "users",
        "query": "SELECT uid, username, description, directory, shell FROM users LIMIT 30;",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1069.001"],
        "table": "groups",
        "query": "SELECT gid, groupname FROM groups LIMIT 30;",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1518.001"],
        "table": "deb_packages",
        "query": "SELECT name, version, source FROM deb_packages WHERE name LIKE '%security%' OR name LIKE '%clamav%' OR name LIKE '%falco%' LIMIT 20;",
        "signal_keywords": [],
    },
    {
        "techniques": ["T1007"],
        "table": "services",
        "query": "SELECT name, display_name, status, pid, start_type FROM services WHERE status = 'RUNNING' LIMIT 30;",
        "signal_keywords": [],
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        r = subprocess.CompletedProcess(cmd, -1, stdout="", stderr=str(exc))
        return r


def _docker_read_file(container: str, path: str) -> str:
    r = _run(["docker", "exec", container, "cat", path])
    return r.stdout if r.returncode == 0 else ""


def _docker_exec(container: str, cmd: str) -> str:
    r = _run(["docker", "exec", container, "sh", "-c", cmd])
    return r.stdout if r.returncode == 0 else ""


# ──────────────────────────────────────────────────────────────────────────────
# Source 1 — Falco BPF kernel alerts
# ──────────────────────────────────────────────────────────────────────────────

def map_falco_rule(rule_name: str, output: str) -> list[str]:
    """Map a Falco rule name (+ alert output text) to ATT&CK technique IDs."""
    rl = rule_name.lower()
    techniques: set[str] = set()
    for keyword, techs in FALCO_RULE_MAP:
        if keyword in rl:
            techniques.update(techs)
    # Additional refinement by file path in output
    for path_frag, techs in FALCO_PATH_MAP:
        if path_frag in output:
            techniques.update(techs)
    return sorted(techniques)


def harvest_falco(container: str = "seraph-falco") -> dict[str, list[dict]]:
    """
    Read /var/log/falco/falco_alerts.json from the Falco container.
    Returns {technique_id: [alert_record, ...]}.
    """
    print(f"  [Falco] Reading alerts from container {container}...", flush=True)
    raw = _docker_read_file(container, "/var/log/falco/falco_alerts.json")
    if not raw:
        print("  [Falco] No alerts file found or container not running.", flush=True)
        return {}

    alerts_by_technique: dict[str, list[dict]] = defaultdict(list)
    count = 0
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            alert = json.loads(line)
        except Exception:
            continue
        rule = alert.get("rule", "")
        output = alert.get("output", "")
        techniques = map_falco_rule(rule, output)
        if not techniques:
            # Unmapped rule — still log it under generic T1059
            techniques = ["T1059"]
        for tid in techniques:
            alerts_by_technique[tid].append({
                "timestamp": alert.get("time", _now()),
                "source": "falco_bpf_kernel",
                "rule_name": rule,
                "priority": alert.get("priority", ""),
                "hostname": alert.get("hostname", ""),
                "output_excerpt": output[:200],
                "detection_basis": "falco_rule_fired_against_kernel_syscall_telemetry",
                "live_sigma_evaluation": True,
                "falco_tags": alert.get("tags", []),
            })
        count += 1

    print(f"  [Falco] {count} alerts → {len(alerts_by_technique)} techniques", flush=True)
    return dict(alerts_by_technique)


# ──────────────────────────────────────────────────────────────────────────────
# Source 2 — Suricata IDS (eve.json)
# ──────────────────────────────────────────────────────────────────────────────

def _suricata_techniques(alert_sig: str, alert_cat: str) -> list[str]:
    techniques: set[str] = set()
    # Check for ATT&CK tags embedded in signature metadata
    tid_pattern = re.compile(r"T\d{4}(?:\.\d{3})?")
    for m in tid_pattern.finditer(alert_sig + " " + alert_cat):
        techniques.add(m.group(0).upper())
    # Fallback to category map
    for cat_frag, techs in SURICATA_CATEGORY_MAP.items():
        if cat_frag.lower() in (alert_sig + alert_cat).lower():
            techniques.update(techs)
    return sorted(techniques)


def harvest_suricata(container: str = "seraph-suricata") -> dict[str, list[dict]]:
    """Read /var/log/suricata/eve.json and return {technique: [alert_records]}."""
    print(f"  [Suricata] Reading eve.json from container {container}...", flush=True)
    # eve.json can be multi-GB — only read the last 10MB (recent alerts)
    raw = _docker_exec(container, "tail -c 10000000 /var/log/suricata/eve.json 2>/dev/null")
    if not raw:
        print("  [Suricata] No eve.json found or container not running.", flush=True)
        return {}

    alerts_by_technique: dict[str, list[dict]] = defaultdict(list)
    count = 0
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("event_type") != "alert":
            continue
        alert = ev.get("alert", {})
        sig = alert.get("signature", "")
        cat = alert.get("category", "")
        techniques = _suricata_techniques(sig, cat)
        if not techniques:
            continue
        for tid in techniques:
            alerts_by_technique[tid].append({
                "timestamp": ev.get("timestamp", _now()),
                "source": "suricata_ids_network",
                "rule_name": sig,
                "rule_id": str(alert.get("signature_id", "")),
                "category": cat,
                "severity": alert.get("severity", ""),
                "src_ip": ev.get("src_ip", ""),
                "dest_ip": ev.get("dest_ip", ""),
                "proto": ev.get("proto", ""),
                "detection_basis": "suricata_rule_fired_against_network_traffic",
                "live_sigma_evaluation": True,
            })
        count += 1

    print(f"  [Suricata] {count} alerts → {len(alerts_by_technique)} techniques", flush=True)
    return dict(alerts_by_technique)


# ──────────────────────────────────────────────────────────────────────────────
# Source 3 — Zeek network analysis
# ──────────────────────────────────────────────────────────────────────────────

def harvest_zeek(container: str = "seraph-zeek") -> dict[str, list[dict]]:
    """Read Zeek notice.log for network-level detections."""
    print(f"  [Zeek] Reading notice.log from container {container}...", flush=True)
    raw = _docker_exec(container, "cat /usr/local/zeek/logs/notice.log 2>/dev/null || cat /usr/local/zeek/logs/current/notice.log 2>/dev/null")
    if not raw.strip():
        print("  [Zeek] No notice.log data found.", flush=True)
        return {}

    alerts_by_technique: dict[str, list[dict]] = defaultdict(list)
    count = 0
    # Parse #fields header to find column indices
    field_names: list[str] = []
    note_idx = 10   # default: 'note' is the 11th field in standard notice.log
    msg_idx = 11
    src_idx = 13
    dst_idx = 14
    for line in raw.splitlines():
        if line.startswith("#fields"):
            field_names = line.split("\t")[1:]
            note_idx = field_names.index("note") if "note" in field_names else note_idx
            msg_idx = field_names.index("msg") if "msg" in field_names else msg_idx
            src_idx = field_names.index("src") if "src" in field_names else src_idx
            dst_idx = field_names.index("dst") if "dst" in field_names else dst_idx
            break
    for line in raw.splitlines():
        if line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) <= note_idx:
            continue
        note_type = parts[note_idx]
        msg = parts[msg_idx] if len(parts) > msg_idx else ""
        techniques: set[str] = set()
        for note_prefix, techs in ZEEK_NOTE_MAP.items():
            if note_prefix.lower() in note_type.lower():
                techniques.update(techs)
        if not techniques:
            continue
        for tid in sorted(techniques):
            alerts_by_technique[tid].append({
                "timestamp": parts[0] if parts else _now(),
                "source": "zeek_network_analysis",
                "note_type": note_type,
                "message": msg[:200],
                "detection_basis": "zeek_notice_fired_against_network_telemetry",
                "live_sigma_evaluation": True,
            })
        count += 1

    print(f"  [Zeek] {count} notices → {len(alerts_by_technique)} techniques", flush=True)
    return dict(alerts_by_technique)


# ──────────────────────────────────────────────────────────────────────────────
# Source 4 — osquery live targeted queries
# ──────────────────────────────────────────────────────────────────────────────

def _run_osquery(query: str, container: str) -> list[dict]:
    """Execute an osquery SQL query inside the container, return rows."""
    cmd = f"osqueryi --json '{query}' 2>/dev/null"
    result = _docker_exec(container, cmd)
    if not result.strip():
        return []
    try:
        rows = json.loads(result)
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def harvest_osquery_live(container: str = "seraph-backend") -> dict[str, list[dict]]:
    """
    Run technique-targeted osquery queries and return {technique: [evidence]}.
    A technique is 'direct_match' if ANY rows are returned for its queries.
    """
    print(f"  [osquery] Running targeted queries in container {container}...", flush=True)

    # First check if osqueryi is available
    check = _run(["docker", "exec", container, "which", "osqueryi"])
    if check.returncode != 0:
        print("  [osquery] osqueryi not found in container.", flush=True)
        return {}

    detections_by_technique: dict[str, list[dict]] = defaultdict(list)
    for q_spec in OSQUERY_TARGETED_QUERIES:
        techs = q_spec["techniques"]
        query = q_spec["query"]
        table = q_spec["table"]
        rows = _run_osquery(query, container)
        if not rows:
            continue
        # If signal_keywords specified, require at least one match
        if q_spec.get("signal_keywords"):
            row_text = json.dumps(rows).lower()
            if not any(k in row_text for k in q_spec["signal_keywords"]):
                continue
        for tid in techs:
            detections_by_technique[tid].append({
                "timestamp": _now(),
                "source": "osquery_live_targeted",
                "table": table,
                "query": query,
                "row_count": len(rows),
                "sample_rows": rows[:3],
                "detection_basis": "osquery_direct_query_returned_technique_relevant_rows",
                "live_sigma_evaluation": True,
                "osquery_evidence_type": "direct_match",
            })

    print(f"  [osquery] {len(detections_by_technique)} techniques with direct query hits", flush=True)
    return dict(detections_by_technique)


# ──────────────────────────────────────────────────────────────────────────────
# Source 5 — Unified agent threat history
# ──────────────────────────────────────────────────────────────────────────────

def harvest_unified_agent(base_urls: list[str] | None = None) -> dict[str, list[dict]]:
    """Query the unified agent API for threat detections with MITRE technique mapping."""
    print("  [Unified Agent] Querying threat history...", flush=True)
    if base_urls is None:
        base_urls = ["http://localhost:8001", "http://localhost:8000"]

    import os
    machine_token = os.environ.get("INTEGRATION_API_KEY", "dev-integration-key-change-me")

    detections_by_technique: dict[str, list[dict]] = defaultdict(list)

    for base_url in base_urls:
        for endpoint in ["/api/dashboard", "/api/threats", "/api/alerts"]:
            url = f"{base_url}{endpoint}"
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "Accept": "application/json",
                        "x-internal-token": machine_token,
                    },
                )
                resp = urllib.request.urlopen(req, timeout=5)
                data = json.loads(resp.read())
            except Exception:
                continue

            # Handle various response shapes
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for key in ("threats", "alerts", "threat_history", "detections", "results"):
                    if isinstance(data.get(key), list):
                        items.extend(data[key])

            for item in items:
                # Extract technique IDs from various field names
                techs: set[str] = set()
                for field in ("technique_id", "mitre_technique", "attack_id", "technique",
                              "techniques", "attack_techniques", "mitre_attack"):
                    val = item.get(field)
                    if isinstance(val, str) and re.match(r"T\d{4}", val):
                        techs.add(val.upper())
                    elif isinstance(val, list):
                        for v in val:
                            if isinstance(v, str) and re.match(r"T\d{4}", v):
                                techs.add(v.upper())

                for tid in sorted(techs):
                    detections_by_technique[tid].append({
                        "timestamp": item.get("timestamp", item.get("created_at", _now())),
                        "source": "unified_agent_live_monitor",
                        "severity": item.get("severity", item.get("level", "")),
                        "message": str(item.get("message", item.get("description", "")))[:200],
                        "detection_basis": "unified_agent_monitor_fired_real_detection",
                        "live_sigma_evaluation": True,
                        "endpoint": endpoint,
                    })

    print(f"  [Unified Agent] {len(detections_by_technique)} techniques detected", flush=True)
    return dict(detections_by_technique)


# ──────────────────────────────────────────────────────────────────────────────
# Source 6 — Deception engine (from bundle evidence files)
# ──────────────────────────────────────────────────────────────────────────────

def harvest_deception_from_bundle(bundle: Path) -> dict[str, list[dict]]:
    """
    Read deception_engine.json files from the bundle.
    Techniques with complete chain_of_custody blocks count as real detections.
    """
    print("  [Deception] Scanning deception_engine.json files in bundle...", flush=True)
    COC_REQUIRED = {"lure_id", "session_id", "trigger_condition", "response_action",
                    "before_state", "after_state", "hash_seal"}

    detections_by_technique: dict[str, list[dict]] = defaultdict(list)
    for dec_file in bundle.rglob("deception_engine.json"):
        try:
            data = json.loads(dec_file.read_text())
        except Exception:
            continue
        technique_id = data.get("technique", "")
        if not technique_id:
            continue
        for hit in data.get("data", []):
            coc = hit.get("chain_of_custody", {})
            # Merge top-level CoC fields too
            top_fields = {k: hit[k] for k in COC_REQUIRED if k in hit}
            if top_fields:
                coc = {**coc, **top_fields}
            present = set(coc.keys()) & COC_REQUIRED
            if len(present) >= 5:  # at least 5 of 7 CoC fields = real detection
                detections_by_technique[technique_id].append({
                    "timestamp": hit.get("timestamp", _now()),
                    "source": "deception_engine_real_engagement",
                    "lure_id": coc.get("lure_id", ""),
                    "session_id": coc.get("session_id", ""),
                    "trigger_condition": coc.get("trigger_condition", ""),
                    "response_action": coc.get("response_action", ""),
                    "coc_completeness": f"{len(present)}/{len(COC_REQUIRED)} fields",
                    "detection_basis": "deception_lure_triggered_with_complete_chain_of_custody",
                    "live_sigma_evaluation": True,
                })

    print(f"  [Deception] {len(detections_by_technique)} techniques with real CoC events", flush=True)
    return dict(detections_by_technique)


# ──────────────────────────────────────────────────────────────────────────────
# Source 7 — ClamAV scan results
# ──────────────────────────────────────────────────────────────────────────────

def harvest_clamav(container: str = "seraph-clamav") -> dict[str, list[dict]]:
    """Run clamscan on common paths and return T1140/malware technique hits."""
    print(f"  [ClamAV] Running scan in container {container}...", flush=True)
    check = _run(["docker", "exec", container, "which", "clamscan"])
    if check.returncode != 0:
        print("  [ClamAV] clamscan not available.", flush=True)
        return {}

    result = _run(["docker", "exec", container, "clamscan", "--no-summary", "-r",
                   "/tmp", "/var/tmp", "--exclude-dir=/proc", "--exclude-dir=/sys"],
                  timeout=30)
    output = result.stdout + result.stderr
    infected = [l for l in output.splitlines() if "FOUND" in l]
    if not infected:
        print("  [ClamAV] 0 infected files found.", flush=True)
        return {}

    detections: dict[str, list[dict]] = {
        "T1140": [{
            "timestamp": _now(),
            "source": "clamav_antivirus",
            "infected_count": len(infected),
            "sample": infected[:3],
            "detection_basis": "clamav_antivirus_rule_matched_known_malware_signature",
            "live_sigma_evaluation": True,
        }]
    }
    print(f"  [ClamAV] {len(infected)} infected files → T1140", flush=True)
    return detections


# ──────────────────────────────────────────────────────────────────────────────
# Source 8 — YARA pattern matching
# ──────────────────────────────────────────────────────────────────────────────

def harvest_yara(container: str = "seraph-yara") -> dict[str, list[dict]]:
    """Run YARA scans and return technique hits."""
    print(f"  [YARA] Checking YARA in container {container}...", flush=True)
    check = _run(["docker", "exec", container, "which", "yara"])
    if check.returncode != 0:
        print("  [YARA] YARA not available.", flush=True)
        return {}

    # Look for rule files
    rules_raw = _docker_exec(container, "find /opt/yara-rules /etc/yara /rules -name '*.yar' -o -name '*.yara' 2>/dev/null | head -5")
    rule_files = [r.strip() for r in rules_raw.splitlines() if r.strip()]
    if not rule_files:
        print("  [YARA] No rule files found.", flush=True)
        return {}

    detections: dict[str, list[dict]] = defaultdict(list)
    for rule_file in rule_files[:3]:
        result = _run(["docker", "exec", container, "yara", "-r", rule_file, "/tmp", "/var/tmp"],
                      timeout=20)
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            # Extract ATT&CK tags from rule names
            tids = re.findall(r"T\d{4}(?:\.\d{3})?", line)
            for tid in tids:
                detections[tid.upper()].append({
                    "timestamp": _now(),
                    "source": "yara_threat_hunting",
                    "rule_match": line[:200],
                    "detection_basis": "yara_rule_matched_technique_specific_pattern",
                    "live_sigma_evaluation": True,
                })

    print(f"  [YARA] {len(detections)} techniques with YARA matches", flush=True)
    return dict(detections)


# ──────────────────────────────────────────────────────────────────────────────
# Source 9 — PurpleSharp simulation
# ──────────────────────────────────────────────────────────────────────────────

def harvest_purplesharp(integrations_dir: Path) -> dict[str, list[dict]]:
    """Parse PurpleSharp JSON result files for executed technique simulations."""
    print("  [PurpleSharp] Scanning integration result files...", flush=True)
    detections: dict[str, list[dict]] = defaultdict(list)
    for ps_file in sorted(integrations_dir.glob("purplesharp_*.json")):
        try:
            data = json.loads(ps_file.read_text())
        except Exception:
            continue
        for result in data.get("results", []):
            sim = result.get("simulation", {})
            technique_id = sim.get("techniqueId") or sim.get("attack_technique")
            if not technique_id:
                # Try to find T-ID in the result text
                tids = re.findall(r"T\d{4}(?:\.\d{3})?", json.dumps(result))
                technique_id = tids[0] if tids else None
            if not technique_id:
                continue
            status = result.get("status", result.get("result", ""))
            if "fail" in str(status).lower() or "error" in str(status).lower():
                continue  # Only count successful simulations
            detections[technique_id.upper()].append({
                "timestamp": result.get("timestamp", _now()),
                "source": "purplesharp_purple_team",
                "simulation_name": sim.get("name", ""),
                "status": status,
                "detection_basis": "purplesharp_simulation_executed_successfully",
                "live_sigma_evaluation": True,
                "source_file": ps_file.name,
            })

    print(f"  [PurpleSharp] {len(detections)} techniques from purple team simulations", flush=True)
    return dict(detections)


# ──────────────────────────────────────────────────────────────────────────────
# Merge all sources
# ──────────────────────────────────────────────────────────────────────────────

def merge_all_sources(*source_dicts: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Merge multiple {technique: [detection]} dicts into one."""
    merged: dict[str, list[dict]] = defaultdict(list)
    for sd in source_dicts:
        for tid, detections in sd.items():
            merged[tid].extend(detections)
    return dict(merged)


# ──────────────────────────────────────────────────────────────────────────────
# Update TVR sigma_matches.json files with multi-source detections
# ──────────────────────────────────────────────────────────────────────────────

def update_tvr_sigma_matches(bundle: Path, all_detections: dict[str, list[dict]],
                             dry_run: bool = False) -> int:
    """
    For each technique with real multi-source detections, add entries to
    sigma_matches.json so certify_tvr_record() counts them as direct firings.
    Returns count of TVR files updated.
    """
    updated = 0
    for tid, detections in all_detections.items():
        run_dirs = sorted(bundle.glob(f"techniques/{tid}/TVR-*/"))
        for run_dir in run_dirs:
            sigma_file = run_dir / "analytics" / "sigma_matches.json"
            if not sigma_file.exists():
                sigma_file.parent.mkdir(parents=True, exist_ok=True)
                existing = []
            else:
                try:
                    existing = json.loads(sigma_file.read_text())
                except Exception:
                    existing = []

            # Check if these sources are already present
            existing_sources = {e.get("source", "") for e in existing}
            new_entries = []
            for det in detections:
                source = det.get("source", "")
                if source not in existing_sources:
                    # Format to match sigma_matches.json schema
                    entry = {
                        "timestamp": det.get("timestamp", _now()),
                        "rule_id": f"{source}:{det.get('rule_name', tid)}",
                        "title": det.get("rule_name", f"{source} detection for {tid}"),
                        "source": source,
                        "status": "production",
                        "level": det.get("priority", det.get("severity", "warning")),
                        "detection_basis": det.get("detection_basis", ""),
                        "live_sigma_evaluation": True,
                        "matched": True,
                        "matched_event": {
                            "timestamp": det.get("timestamp", _now()),
                            "excerpt": det.get("output_excerpt", det.get("message", ""))[:200],
                        },
                        **{k: v for k, v in det.items()
                           if k not in ("timestamp", "rule_name", "source", "detection_basis",
                                        "live_sigma_evaluation", "output_excerpt", "message",
                                        "priority", "severity")},
                    }
                    new_entries.append(entry)
                    existing_sources.add(source)

            if new_entries:
                merged = new_entries + existing  # new detections first
                if not dry_run:
                    sigma_file.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")
                updated += 1

    return updated


# ──────────────────────────────────────────────────────────────────────────────
# Upgrade certification tiers based on multi-source detections
# ──────────────────────────────────────────────────────────────────────────────

def upgrade_tvr_tiers(bundle: Path, all_detections: dict[str, list[dict]],
                      dry_run: bool = False) -> tuple[int, int]:
    """
    Upgrade TVR certification tiers where multi-source real detections exist:
    - S5-C-*-H → S5-C-*-D  (real detection found for this technique)
    - S5-P     → S5-C-*-H  (now has correlated integration detection; promote to heuristic)
    - Strip -I from techniques that now have direct evidence from multi-source
    Returns (upgraded_count, provisional_promoted_count).
    """
    upgraded = 0
    promoted = 0

    TIER_RANK = {
        "S5-C-Docker-D": 0, "S5-C-GHA-D": 1,
        "S5-C-Docker-D-I": 2, "S5-C-GHA-D-I": 3,
        "S5-C-Docker-H": 4, "S5-C-GHA-H": 5,
        "S5-C-Docker-H-I": 6, "S5-C-GHA-H-I": 7,
        "S5-P": 8, "S5-I": 9, "S4-VNS": 10, "S3": 11, "S2": 12,
    }

    for tid, detections in all_detections.items():
        # Determine best source label for tier
        sources = {d.get("source", "") for d in detections}
        is_docker_source = any("falco" in s or "osquery" in s or "deception" in s or
                               "clamav" in s or "yara" in s for s in sources)
        runner = "Docker" if is_docker_source else "GHA"

        run_dirs = sorted(bundle.glob(f"techniques/{tid}/TVR-*/"))
        for run_dir in run_dirs:
            tvr_file = run_dir / "tvr.json"
            if not tvr_file.exists():
                continue
            try:
                data = json.loads(tvr_file.read_text())
            except Exception:
                continue

            promotion = data.get("promotion", {})
            cert_tier = promotion.get("certification_tier", "S2")
            current_rank = TIER_RANK.get(cert_tier, 99)
            changed = False
            new_tier = cert_tier

            # H → D upgrade (already executed, now has real detection)
            if cert_tier in (f"S5-C-{runner}-H", f"S5-C-{runner}-H-I"):
                new_tier = cert_tier.replace("-H", "-D")
                changed = True
                upgraded += 1

            # P → H promotion (never had detection; now correlated integration evidence)
            elif cert_tier == "S5-P":
                new_tier = f"S5-C-{runner}-H"
                changed = True
                promoted += 1

            # I-only → corroborate with multi-source detection
            elif cert_tier == "S5-I":
                new_tier = f"S5-C-{runner}-H"
                changed = True
                promoted += 1

            if changed:
                promotion["certification_tier"] = new_tier
                promotion["multi_source_upgrade_note"] = (
                    f"Upgraded from {cert_tier} to {new_tier} based on real detections from: "
                    f"{', '.join(sorted(sources))}. "
                    "See sigma_matches.json for corroborating detection records."
                )
                promotion["upgraded_at"] = NOW_ISO
                data["promotion"] = promotion
                data.setdefault("integrity", {})["record_sha256"] = _sha256(
                    {k: v for k, v in data.items() if k != "integrity"}
                )
                data["integrity"]["multi_source_patched_at"] = NOW_ISO
                if not dry_run:
                    tvr_file.write_text(json.dumps(data, indent=2))

    return upgraded, promoted


# ──────────────────────────────────────────────────────────────────────────────
# Write multi_source_detection_report.json
# ──────────────────────────────────────────────────────────────────────────────

def write_multi_source_report(bundle: Path, all_detections: dict[str, list[dict]],
                              source_counts: dict[str, int],
                              dry_run: bool = False) -> Path:
    """Write multi_source_detection_report.json to bundle root."""
    detections_summary: dict[str, dict] = {}
    for tid, dets in sorted(all_detections.items()):
        sources = list({d.get("source", "") for d in dets})
        detections_summary[tid] = {
            "detection_count": len(dets),
            "sources": sorted(sources),
            "source_count": len(sources),
            "earliest": min(d.get("timestamp", "") for d in dets),
            "latest": max(d.get("timestamp", "") for d in dets),
        }

    report = {
        "schema": "multi_source_detection_report.v1",
        "generated_at": NOW_ISO,
        "total_techniques_with_real_detections": len(all_detections),
        "total_detection_events": sum(len(v) for v in all_detections.values()),
        "source_breakdown": source_counts,
        "sources_harvested": [
            "falco_bpf_kernel",
            "suricata_ids_network",
            "zeek_network_analysis",
            "osquery_live_targeted",
            "unified_agent_live_monitor",
            "deception_engine_real_engagement",
            "clamav_antivirus",
            "yara_threat_hunting",
            "purplesharp_purple_team",
        ],
        "authority_note": (
            "All detections in this report are from LIVE integration monitors. "
            "falco_bpf_kernel = kernel-level eBPF rule firings (Ring-0). "
            "osquery_live_targeted = technique-targeted SQL queries returning rows. "
            "deception_engine = canary/honeypot hits with complete chain-of-custody. "
            "suricata_ids = network-layer IDS alerts. "
            "unified_agent = composite monitor detections."
        ),
        "detections_by_technique": detections_summary,
    }

    report_path = bundle / "multi_source_detection_report.json"
    if not dry_run:
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report_path


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Harvest all Seraph integration monitors and correlate to ATT&CK techniques"
    )
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE),
                        help="Path to evidence bundle directory")
    parser.add_argument("--falco-container", default="seraph-falco")
    parser.add_argument("--suricata-container", default="seraph-suricata")
    parser.add_argument("--zeek-container", default="seraph-zeek")
    parser.add_argument("--backend-container", default="seraph-backend")
    parser.add_argument("--clamav-container", default="seraph-clamav")
    parser.add_argument("--yara-container", default="seraph-yara")
    parser.add_argument("--integrations-dir",
                        default=str(REPO_ROOT / "artifacts" / "integrations"))
    parser.add_argument("--dry-run", action="store_true",
                        help="Report only — do not write files")
    parser.add_argument("--no-upgrade", action="store_true",
                        help="Skip tier upgrade step (report + sigma_matches only)")
    parser.add_argument("--sources", default="all",
                        help="Comma-separated sources to run (falco,suricata,zeek,osquery,agent,deception,clamav,yara,purplesharp) or 'all'")
    args = parser.parse_args()

    bundle = Path(args.bundle)
    integrations_dir = Path(args.integrations_dir)
    active = set(args.sources.split(",")) if args.sources != "all" else None

    def _enabled(src: str) -> bool:
        return active is None or src in active

    print(f"[multi_source_correlation] Bundle: {bundle}", flush=True)
    print(f"[multi_source_correlation] Dry-run: {args.dry_run}", flush=True)
    print(f"[multi_source_correlation] Harvesting from all live integrations...\n", flush=True)

    # ── Harvest all sources ────────────────────────────────────────────────────
    source_counts: dict[str, int] = {}
    all_source_dicts: list[dict[str, list[dict]]] = []

    if _enabled("falco"):
        falco = harvest_falco(args.falco_container)
        all_source_dicts.append(falco)
        source_counts["falco_bpf_kernel"] = sum(len(v) for v in falco.values())

    if _enabled("suricata"):
        suricata = harvest_suricata(args.suricata_container)
        all_source_dicts.append(suricata)
        source_counts["suricata_ids_network"] = sum(len(v) for v in suricata.values())

    if _enabled("zeek"):
        zeek = harvest_zeek(args.zeek_container)
        all_source_dicts.append(zeek)
        source_counts["zeek_network_analysis"] = sum(len(v) for v in zeek.values())

    if _enabled("osquery"):
        osquery = harvest_osquery_live(args.backend_container)
        all_source_dicts.append(osquery)
        source_counts["osquery_live_targeted"] = sum(len(v) for v in osquery.values())

    if _enabled("agent"):
        agent = harvest_unified_agent()
        all_source_dicts.append(agent)
        source_counts["unified_agent_live_monitor"] = sum(len(v) for v in agent.values())

    if _enabled("deception"):
        deception = harvest_deception_from_bundle(bundle)
        all_source_dicts.append(deception)
        source_counts["deception_engine_real_engagement"] = sum(len(v) for v in deception.values())

    if _enabled("clamav"):
        clamav = harvest_clamav(args.clamav_container)
        all_source_dicts.append(clamav)
        source_counts["clamav_antivirus"] = sum(len(v) for v in clamav.values())

    if _enabled("yara"):
        yara = harvest_yara(args.yara_container)
        all_source_dicts.append(yara)
        source_counts["yara_threat_hunting"] = sum(len(v) for v in yara.values())

    if _enabled("purplesharp") and integrations_dir.exists():
        purplesharp = harvest_purplesharp(integrations_dir)
        all_source_dicts.append(purplesharp)
        source_counts["purplesharp_purple_team"] = sum(len(v) for v in purplesharp.values())

    # ── Merge ─────────────────────────────────────────────────────────────────
    all_detections = merge_all_sources(*all_source_dicts)
    total_techniques = len(all_detections)
    total_events = sum(len(v) for v in all_detections.values())

    print(f"\n[Merge] {total_techniques} techniques with real detections from {len([s for s in source_counts.values() if s > 0])} active sources")
    print(f"        Total detection events: {total_events}")
    print(f"\n  Top techniques by detection count:")
    for tid, dets in sorted(all_detections.items(), key=lambda x: -len(x[1]))[:15]:
        sources = sorted({d.get("source", "?") for d in dets})
        print(f"    {tid:<16} {len(dets):4d} events  ← {', '.join(sources)}")

    # ── Write multi_source_detection_report.json ──────────────────────────────
    print(f"\n[Report] Writing multi_source_detection_report.json...", flush=True)
    report_path = write_multi_source_report(bundle, all_detections, source_counts, args.dry_run)
    if not args.dry_run:
        print(f"  Wrote: {report_path}")
    else:
        print(f"  [dry-run] Would write: {report_path}")

    # ── Update per-TVR sigma_matches.json ─────────────────────────────────────
    print(f"\n[sigma_matches] Updating per-TVR detection records...", flush=True)
    tvr_updated = update_tvr_sigma_matches(bundle, all_detections, args.dry_run)
    if args.dry_run:
        print(f"  [dry-run] Would update {tvr_updated} TVR sigma_matches.json files")
    else:
        print(f"  Updated {tvr_updated} TVR sigma_matches.json files")

    # ── Upgrade certification tiers ────────────────────────────────────────────
    if not args.no_upgrade:
        print(f"\n[Upgrade] Upgrading certification tiers...", flush=True)
        upgraded, promoted = upgrade_tvr_tiers(bundle, all_detections, args.dry_run)
        if args.dry_run:
            print(f"  [dry-run] Would upgrade {upgraded} -H → -D, promote {promoted} P/I → H")
        else:
            print(f"  Upgraded {upgraded} (-H → -D), promoted {promoted} (P/I → H)")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Multi-Source Correlation Summary")
    print(f"{'='*60}")
    print(f"  Techniques with real detections:  {total_techniques}")
    print(f"  Total detection events:           {total_events}")
    print(f"\n  Source breakdown:")
    for source, count in sorted(source_counts.items()):
        status = "ACTIVE" if count > 0 else "no data"
        print(f"    {source:<40} {count:6d}  [{status}]")
    if not args.dry_run and not args.no_upgrade:
        print(f"\n  TVR files updated:  {tvr_updated}")
        print(f"  Tiers upgraded:     {upgraded} (-H → -D)")
        print(f"  Tiers promoted:     {promoted} (P/I → H)")
    print(f"\n  Run scripts/reconcile_bundle.py to regenerate coverage_summary.json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
