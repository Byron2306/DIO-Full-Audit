#!/usr/bin/env python3
"""
generate_osquery_queries.py
============================
Generate technique-specific osquery queries based on MITRE ATT&CK tactic and
technique behavior.  Replaces the old 3-template-per-technique approach with
queries that actually target what each technique does.

Techniques that don't map to any osquery-observable behavior get 0 queries.

Usage:
    python3 scripts/generate_osquery_queries.py \
        --attack-json atomic-red-team/atomic_red_team/enterprise-attack.json \
        --techniques-catalog backend/data/generated_mitre_techniques.json \
        --output backend/data/generated_osquery_builtin_queries.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

# ── Tactic → query templates ──────────────────────────────────────────────
# Each tactic maps to a set of osquery query templates that are relevant.
# The templates use {tech_id_lower} as a placeholder for unique naming.
#
# Key design: NOT every technique gets a query.  Techniques in PRE, Cloud,
# or abstract tactics that have no local OS observability get nothing.

TACTIC_QUERY_TEMPLATES = {
    "execution": [
        {
            "suffix": "proc_exec",
            "description": "Detect process execution patterns for {name} ({tech_id})",
            "sql": "SELECT pid, parent, name, path, cmdline, cwd, uid, gid, on_disk FROM processes WHERE cmdline != '' ORDER BY start_time DESC LIMIT 100;",
            "table": "processes",
        },
        {
            "suffix": "proc_events",
            "description": "Process creation events relevant to {name} ({tech_id})",
            "sql": "SELECT pid, parent, path, cmdline, uid, time FROM process_events ORDER BY time DESC LIMIT 100;",
            "table": "process_events",
        },
    ],
    "persistence": [
        {
            "suffix": "crontab",
            "description": "Cron-based persistence for {name} ({tech_id})",
            "sql": "SELECT event, minute, hour, day_of_month, month, day_of_week, command, path FROM crontab;",
            "table": "crontab",
        },
        {
            "suffix": "startup",
            "description": "Startup/init persistence for {name} ({tech_id})",
            "sql": "SELECT name, path, source, status, type FROM startup_items;",
            "table": "startup_items",
        },
    ],
    "privilege-escalation": [
        {
            "suffix": "suid",
            "description": "SUID/SGID binaries relevant to {name} ({tech_id})",
            "sql": "SELECT path, username, groupname, permissions FROM suid_bin;",
            "table": "suid_bin",
        },
        {
            "suffix": "proc_priv",
            "description": "Processes running as root for {name} ({tech_id})",
            "sql": "SELECT pid, name, path, cmdline, uid, gid FROM processes WHERE uid = 0 AND parent != 0 ORDER BY start_time DESC LIMIT 100;",
            "table": "processes",
        },
    ],
    "defense-evasion": [
        {
            "suffix": "proc_hidden",
            "description": "Suspicious process attributes for {name} ({tech_id})",
            "sql": "SELECT pid, name, path, cmdline, on_disk, cwd FROM processes WHERE on_disk = 0 OR path = '' ORDER BY start_time DESC LIMIT 100;",
            "table": "processes",
        },
        {
            "suffix": "file_mod",
            "description": "Recently modified files in suspicious locations for {name} ({tech_id})",
            "sql": "SELECT path, filename, size, uid, gid, mode, mtime, atime FROM file WHERE (path LIKE '/tmp/%' OR path LIKE '/dev/shm/%' OR path LIKE '/var/tmp/%') AND mtime > (strftime('%s','now') - 3600) LIMIT 100;",
            "table": "file",
        },
    ],
    "credential-access": [
        {
            "suffix": "shadow_read",
            "description": "Access to credential files for {name} ({tech_id})",
            "sql": "SELECT target_path, action, uid, time FROM file_events WHERE (target_path LIKE '%shadow%' OR target_path LIKE '%passwd%' OR target_path LIKE '%.ssh/%' OR target_path LIKE '%credential%') LIMIT 100;",
            "table": "file_events",
        },
        {
            "suffix": "proc_cred",
            "description": "Processes accessing credential stores for {name} ({tech_id})",
            "sql": "SELECT pid, name, path, cmdline FROM processes WHERE cmdline LIKE '%shadow%' OR cmdline LIKE '%passwd%' OR cmdline LIKE '%mimikatz%' OR cmdline LIKE '%credential%' OR cmdline LIKE '%hashdump%' LIMIT 100;",
            "table": "processes",
        },
    ],
    "discovery": [
        {
            "suffix": "sys_info",
            "description": "System enumeration queries for {name} ({tech_id})",
            "sql": "SELECT hostname, cpu_type, physical_memory, hardware_vendor, hardware_model FROM system_info;",
            "table": "system_info",
        },
        {
            "suffix": "net_enum",
            "description": "Network enumeration for {name} ({tech_id})",
            "sql": "SELECT interface, address, mask, type FROM interface_addresses WHERE interface != 'lo';",
            "table": "interface_addresses",
        },
    ],
    "lateral-movement": [
        {
            "suffix": "ssh_keys",
            "description": "SSH key access for {name} ({tech_id})",
            "sql": "SELECT uid, path, filename, size, mtime FROM file WHERE path LIKE '%/.ssh/%' LIMIT 50;",
            "table": "file",
        },
        {
            "suffix": "net_conn",
            "description": "Outbound connections for {name} ({tech_id})",
            "sql": "SELECT pid, local_address, local_port, remote_address, remote_port, state FROM process_open_sockets WHERE remote_port IN (22, 135, 139, 445, 3389, 5985, 5986) AND state = 'ESTABLISHED' LIMIT 100;",
            "table": "process_open_sockets",
        },
    ],
    "collection": [
        {
            "suffix": "file_access",
            "description": "File access patterns for {name} ({tech_id})",
            "sql": "SELECT target_path, action, uid, time FROM file_events WHERE action IN ('OPEN', 'READ') AND target_path NOT LIKE '/proc/%' ORDER BY time DESC LIMIT 100;",
            "table": "file_events",
        },
    ],
    "command-and-control": [
        {
            "suffix": "c2_sockets",
            "description": "Suspicious outbound connections for {name} ({tech_id})",
            "sql": "SELECT p.pid, p.name, p.path, p.cmdline, s.remote_address, s.remote_port, s.state FROM process_open_sockets s JOIN processes p ON s.pid = p.pid WHERE s.remote_address != '' AND s.remote_address != '127.0.0.1' AND s.remote_address != '::1' AND s.state = 'ESTABLISHED' LIMIT 100;",
            "table": "process_open_sockets",
        },
        {
            "suffix": "dns_cache",
            "description": "DNS resolution for {name} ({tech_id})",
            "sql": "SELECT pid, fd, socket, remote_address, remote_port FROM process_open_sockets WHERE remote_port = 53 LIMIT 50;",
            "table": "process_open_sockets",
        },
    ],
    "exfiltration": [
        {
            "suffix": "exfil_net",
            "description": "Outbound data transfer for {name} ({tech_id})",
            "sql": "SELECT p.pid, p.name, p.cmdline, s.remote_address, s.remote_port FROM process_open_sockets s JOIN processes p ON s.pid = p.pid WHERE s.remote_address != '' AND s.remote_address NOT LIKE '127.%' AND s.remote_address NOT LIKE '10.%' AND s.remote_address NOT LIKE '192.168.%' LIMIT 100;",
            "table": "process_open_sockets",
        },
    ],
    "impact": [
        {
            "suffix": "proc_impact",
            "description": "Destructive process activity for {name} ({tech_id})",
            "sql": "SELECT pid, name, path, cmdline, uid FROM processes WHERE cmdline LIKE '%rm -rf%' OR cmdline LIKE '%mkfs%' OR cmdline LIKE '%dd if=%' OR cmdline LIKE '%shred%' OR cmdline LIKE '%wipe%' LIMIT 100;",
            "table": "processes",
        },
        {
            "suffix": "disk_events",
            "description": "File deletion events for {name} ({tech_id})",
            "sql": "SELECT target_path, action, uid, time FROM file_events WHERE action = 'DELETE' ORDER BY time DESC LIMIT 100;",
            "table": "file_events",
        },
    ],
    "initial-access": [
        # Most initial-access is not locally observable via osquery
    ],
    "reconnaissance": [
        # PRE-phase — not locally observable
    ],
    "resource-development": [
        # PRE-phase — not locally observable
    ],
}

# ── Technique-specific query overrides ─────────────────────────────────────
# For techniques with well-known detection patterns, use specialized queries
# instead of the generic tactic templates.
TECHNIQUE_SPECIFIC_QUERIES = {
    "T1053": [  # Scheduled Task/Job
        {"suffix": "crontab", "description": "Cron entries for scheduled task persistence", "sql": "SELECT event, minute, hour, day_of_month, month, day_of_week, command, path FROM crontab;", "table": "crontab"},
        {"suffix": "at_jobs", "description": "at(1) scheduled jobs", "sql": "SELECT path, filename, size, mtime FROM file WHERE path LIKE '/var/spool/cron/atjobs/%' OR path LIKE '/var/spool/at/%';", "table": "file"},
    ],
    "T1053.003": [  # Cron
        {"suffix": "crontab", "description": "Crontab entries", "sql": "SELECT event, minute, hour, day_of_month, month, day_of_week, command, path FROM crontab;", "table": "crontab"},
    ],
    "T1059.004": [  # Unix Shell
        {"suffix": "shell_proc", "description": "Shell processes", "sql": "SELECT pid, parent, name, path, cmdline, uid FROM processes WHERE name IN ('bash','sh','dash','zsh','ksh','csh','tcsh','fish') ORDER BY start_time DESC LIMIT 100;", "table": "processes"},
        {"suffix": "shell_history", "description": "Shell history files", "sql": "SELECT path, filename, size, mtime FROM file WHERE path LIKE '%/.bash_history' OR path LIKE '%/.zsh_history' OR path LIKE '%/.sh_history';", "table": "file"},
    ],
    "T1059.006": [  # Python
        {"suffix": "python_proc", "description": "Python process execution", "sql": "SELECT pid, parent, name, path, cmdline FROM processes WHERE name LIKE 'python%' OR cmdline LIKE '%python%' ORDER BY start_time DESC LIMIT 100;", "table": "processes"},
    ],
    "T1070.004": [  # File Deletion
        {"suffix": "file_del", "description": "File deletion events", "sql": "SELECT target_path, action, uid, time FROM file_events WHERE action = 'DELETE' ORDER BY time DESC LIMIT 100;", "table": "file_events"},
    ],
    "T1543.002": [  # Systemd Service
        {"suffix": "systemd_svc", "description": "Systemd unit files", "sql": "SELECT path, filename, size, uid, gid, mode, mtime FROM file WHERE path LIKE '/etc/systemd/system/%' OR path LIKE '/usr/lib/systemd/system/%';", "table": "file"},
    ],
    "T1547.001": [  # Registry Run Keys / Startup Folder
        {"suffix": "startup", "description": "Startup items", "sql": "SELECT name, path, source, status, type FROM startup_items;", "table": "startup_items"},
    ],
    "T1548.001": [  # Setuid and Setgid
        {"suffix": "suid", "description": "SUID/SGID binaries", "sql": "SELECT path, username, groupname, permissions FROM suid_bin;", "table": "suid_bin"},
    ],
    "T1014": [  # Rootkit
        {"suffix": "kernel_mod", "description": "Loaded kernel modules", "sql": "SELECT name, size, status, address FROM kernel_modules;", "table": "kernel_modules"},
    ],
    "T1040": [  # Network Sniffing
        {"suffix": "promisc", "description": "Network interfaces in promiscuous mode", "sql": "SELECT interface, flags FROM interface_details WHERE flags LIKE '%PROMISC%';", "table": "interface_details"},
    ],
    "T1046": [  # Network Service Discovery
        {"suffix": "listening", "description": "Listening ports", "sql": "SELECT pid, port, address, protocol, path FROM listening_ports;", "table": "listening_ports"},
    ],
    "T1057": [  # Process Discovery
        {"suffix": "proc_list", "description": "Process listing", "sql": "SELECT pid, parent, name, path, cmdline, uid, gid, state FROM processes ORDER BY start_time DESC LIMIT 200;", "table": "processes"},
    ],
    "T1082": [  # System Information Discovery
        {"suffix": "sys_info", "description": "System information", "sql": "SELECT hostname, cpu_type, cpu_brand, physical_memory, hardware_vendor, hardware_model, computer_name FROM system_info;", "table": "system_info"},
        {"suffix": "os_ver", "description": "OS version", "sql": "SELECT name, version, major, minor, patch, build, platform FROM os_version;", "table": "os_version"},
    ],
    "T1016": [  # System Network Configuration Discovery
        {"suffix": "iface", "description": "Network interfaces", "sql": "SELECT interface, address, mask, type, friendly_name FROM interface_addresses WHERE interface != 'lo';", "table": "interface_addresses"},
        {"suffix": "routes", "description": "Routing table", "sql": "SELECT destination, gateway, interface, type FROM routes WHERE destination != '::1' LIMIT 100;", "table": "routes"},
    ],
    "T1049": [  # System Network Connections Discovery
        {"suffix": "sockets", "description": "Open network connections", "sql": "SELECT pid, local_address, local_port, remote_address, remote_port, state, protocol FROM process_open_sockets WHERE state = 'ESTABLISHED' LIMIT 100;", "table": "process_open_sockets"},
    ],
    "T1087.001": [  # Account Discovery: Local Account
        {"suffix": "users", "description": "Local user accounts", "sql": "SELECT uid, gid, username, directory, shell, description FROM users;", "table": "users"},
        {"suffix": "groups", "description": "Local groups", "sql": "SELECT gid, groupname FROM groups;", "table": "groups"},
    ],
    "T1069.001": [  # Permission Groups Discovery: Local Groups
        {"suffix": "groups", "description": "Local permission groups", "sql": "SELECT gid, groupname FROM groups;", "table": "groups"},
    ],
    "T1007": [  # System Service Discovery
        {"suffix": "svc_proc", "description": "Service processes", "sql": "SELECT pid, parent, name, path, cmdline, uid FROM processes WHERE parent IN (1, 2) OR path LIKE '/usr/sbin/%' ORDER BY start_time DESC LIMIT 100;", "table": "processes"},
    ],
    "T1518": [  # Software Discovery
        {"suffix": "packages", "description": "Installed packages", "sql": "SELECT name, version, source, arch FROM deb_packages LIMIT 200;", "table": "deb_packages"},
    ],
}


def load_attack_data(path: str) -> dict:
    """Load MITRE ATT&CK STIX JSON and return tech_id → {name, tactics, platforms}."""
    with open(path) as f:
        bundle = json.load(f)

    techniques = {}
    for obj in bundle.get("objects", []):
        if obj.get("type") != "attack-pattern" or obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        refs = obj.get("external_references") or []
        tech_id = None
        for r in refs:
            if r.get("source_name") == "mitre-attack":
                tech_id = r.get("external_id")
                break
        if not tech_id or not tech_id.startswith("T"):
            continue
        tactics = [p["phase_name"] for p in (obj.get("kill_chain_phases") or [])]
        techniques[tech_id] = {
            "name": obj.get("name", tech_id),
            "tactics": tactics,
            "platforms": obj.get("x_mitre_platforms") or [],
        }
    return techniques


def generate_queries(attack_data: dict, catalog_ids: list) -> list:
    """Generate technique-specific osquery queries."""
    queries = []
    seen_ids = set()

    for tech_id in catalog_ids:
        tech_lower = tech_id.lower().replace(".", "_")
        info = attack_data.get(tech_id, {})
        name = info.get("name", tech_id)
        tactics = info.get("tactics", [])

        # Use technique-specific override if available
        if tech_id in TECHNIQUE_SPECIFIC_QUERIES:
            for tmpl in TECHNIQUE_SPECIFIC_QUERIES[tech_id]:
                q_name = f"{tech_lower}_{tmpl['suffix']}"
                if q_name in seen_ids:
                    continue
                seen_ids.add(q_name)
                queries.append({
                    "name": q_name,
                    "description": tmpl["description"].format(name=name, tech_id=tech_id),
                    "sql": tmpl["sql"],
                    "attack_techniques": [tech_id],
                    "table": tmpl["table"],
                })
            continue

        # Check subtechnique parent for override
        if "." in tech_id:
            parent = tech_id.split(".")[0]
            if parent in TECHNIQUE_SPECIFIC_QUERIES:
                for tmpl in TECHNIQUE_SPECIFIC_QUERIES[parent]:
                    q_name = f"{tech_lower}_{tmpl['suffix']}"
                    if q_name in seen_ids:
                        continue
                    seen_ids.add(q_name)
                    queries.append({
                        "name": q_name,
                        "description": tmpl["description"].format(name=name, tech_id=tech_id),
                        "sql": tmpl["sql"],
                        "attack_techniques": [tech_id],
                        "table": tmpl["table"],
                    })
                continue

        # Fall back to tactic-based templates
        added = 0
        for tactic in tactics:
            templates = TACTIC_QUERY_TEMPLATES.get(tactic, [])
            for tmpl in templates:
                q_name = f"{tech_lower}_{tmpl['suffix']}"
                if q_name in seen_ids:
                    continue
                seen_ids.add(q_name)
                queries.append({
                    "name": q_name,
                    "description": tmpl["description"].format(name=name, tech_id=tech_id),
                    "sql": tmpl["sql"],
                    "attack_techniques": [tech_id],
                    "table": tmpl["table"],
                })
                added += 1

        # Techniques with no tactic-mapped queries get nothing — honest

    return queries


def main():
    parser = argparse.ArgumentParser(description="Generate technique-specific osquery queries")
    parser.add_argument("--attack-json", required=True, help="Path to enterprise-attack.json")
    parser.add_argument("--techniques-catalog", required=True, help="Path to generated_mitre_techniques.json")
    parser.add_argument("--output", required=True, help="Output path for generated_osquery_builtin_queries.json")
    args = parser.parse_args()

    attack_data = load_attack_data(args.attack_json)
    print(f"Loaded {len(attack_data)} techniques from ATT&CK STIX data")

    with open(args.techniques_catalog) as f:
        catalog = json.load(f)
    catalog_ids = catalog.get("catalog_techniques") or catalog.get("techniques") or []
    print(f"Catalog has {len(catalog_ids)} technique IDs")

    queries = generate_queries(attack_data, catalog_ids)

    # Count techniques with queries vs without
    techs_with = set()
    for q in queries:
        for t in q.get("attack_techniques", []):
            techs_with.add(t)
    techs_without = set(catalog_ids) - techs_with

    output = {
        "schema_version": "1.0.0",
        "generated_by": "generate_osquery_queries.py",
        "total_queries": len(queries),
        "techniques_with_queries": len(techs_with),
        "techniques_without_queries": len(techs_without),
        "queries": queries,
    }

    Path(args.output).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {len(queries)} queries for {len(techs_with)} techniques")
    print(f"{len(techs_without)} techniques have no osquery queries (honest)")

    # Distribution
    from collections import Counter
    tech_count = Counter()
    for q in queries:
        for t in q.get("attack_techniques", []):
            tech_count[t] += 1
    dist = Counter(tech_count.values())
    print(f"Query count distribution: {dict(sorted(dist.items()))}")


if __name__ == "__main__":
    main()
