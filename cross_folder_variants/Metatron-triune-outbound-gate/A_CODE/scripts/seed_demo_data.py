#!/usr/bin/env python3
"""
Seed Seraph AI Defense demo data.

Populates:
  - Identity incidents (identity_incidents collection)
  - Threat response history (response_history collection)
  - Deception campaigns/events  (via /v1/deception/assess API)
  - Quarantine entries          (via /api/quarantine/ingest API)
  - Attack path crown jewels    (via /api/v1/attack-paths/assets API)
  - Attack path nodes/analysis  (via /api/v1/attack-paths/analysis API)
  - Additional threats          (threats collection)
  - Users with privileged accounts (users collection, no password set)

Usage:
    python3 scripts/seed_demo_data.py
"""

import asyncio
import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

import requests
from motor.motor_asyncio import AsyncIOMotorClient

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MONGO_URL = "mongodb://172.28.0.5:27017"
DB_NAME = "seraph_ai_defense"
API_BASE = "http://localhost:8001/api"
AUTH_EMAIL = "test@seraph.local"
AUTH_PASSWORD = "Test1234!"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso(offset_minutes: int = 0) -> str:
    t = datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)
    return t.isoformat()

def rand_ip() -> str:
    prefixes = ["45.33", "185.220", "198.51", "203.0", "91.108", "162.55", "194.165"]
    return f"{random.choice(prefixes)}.{random.randint(1,254)}.{random.randint(1,254)}"

def rand_internal_ip() -> str:
    return f"192.168.{random.randint(1,10)}.{random.randint(10,200)}"

def get_token() -> str:
    r = requests.post(
        f"{API_BASE}/auth/login",
        json={"email": AUTH_EMAIL, "password": AUTH_PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]

def api(token: str, method: str, path: str, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    r = getattr(requests, method)(f"{API_BASE}/{path}", headers=headers, timeout=15, **kwargs)
    return r

# ---------------------------------------------------------------------------
# 1. Seed identity incidents (MongoDB direct)
# ---------------------------------------------------------------------------
async def seed_identity_incidents(db):
    collection = db["identity_incidents"]
    existing = await collection.count_documents({})
    if existing >= 10:
        print(f"  identity_incidents already has {existing} docs, skipping")
        return

    now = datetime.now(timezone.utc)
    incidents = []
    types = [
        ("kerberoasting", "high", "Kerberoasting attack detected — TGS ticket requested for krbtgt/CORP.LOCAL"),
        ("pass_the_hash", "critical", "Pass-the-Hash lateral movement detected from WS-IT-03"),
        ("credential_dump", "critical", "LSASS memory dump attempted via procdump on DC-PROD-01"),
        ("dcsync", "high", "DCSync replication request blocked — AD replication API abused"),
        ("golden_ticket", "critical", "Golden Ticket forgery detected — forged TGT presented to KDC"),
        ("ldap_enum", "medium", "LDAP reconnaissance — adminCount=1 query from 192.168.1.50"),
        ("pass_the_ticket", "high", "Pass-the-Ticket attack: stolen TGT reused across hosts"),
        ("as_rep_roasting", "high", "AS-REP Roasting — accounts with no Kerberos pre-auth queried"),
        ("brute_force", "medium", "Credential brute-force detected — 347 failed logins in 60 seconds"),
        ("privilege_escalation", "high", "Privilege escalation — standard user obtained SeDebugPrivilege"),
        ("anomalous_login", "medium", "Anomalous login — account accessed from new country (RU)"),
        ("token_impersonation", "high", "Token impersonation attack — impersonation token created via CreateProcessWithToken"),
    ]

    for i, (itype, severity, message) in enumerate(types):
        iid = str(uuid.uuid4())
        offset = i * 47  # stagger times
        incidents.append({
            "id": iid,
            "type": itype,
            "severity": severity,
            "message": message,
            "status": random.choice(["active", "active", "investigating", "resolved"]),
            "user": random.choice(["admin_compromised", "svc_backup", "john.smith", "sa_sql", "svc_exchange", "guest_legacy"]),
            "source_ip": rand_ip() if random.random() > 0.5 else rand_internal_ip(),
            "target": random.choice(["DC-PROD-01", "WS-IT-03", "SQL-PROD-02", "EXCH-01", "FILE-SRV-01"]),
            "endpoint": random.choice(["WS-IT-02", "WS-IT-05", "LAPTOP-ADM-01", "KIOSK-07"]),
            "mitre_technique": random.choice(["T1558.003", "T1550.002", "T1003.001", "T1207", "T1558.001", "T1087.002"]),
            "mitre_tactic": random.choice(["credential_access", "lateral_movement", "privilege_escalation", "discovery"]),
            "created_at": now_iso(offset),
            "updated_at": now_iso(offset - 5),
            "state_version": 1,
            "state_transition_log": [
                {
                    "timestamp": now_iso(offset),
                    "from_status": None,
                    "to_status": "active",
                    "actor": "system:identity",
                    "reason": "incident discovered by identity engine",
                }
            ],
            "auto_responses_triggered": random.randint(0, 3),
            "confidence": round(random.uniform(0.7, 0.99), 2),
        })

    if incidents:
        await collection.insert_many(incidents)
        print(f"  Inserted {len(incidents)} identity incidents")


# ---------------------------------------------------------------------------
# 2. Seed privileged users
# ---------------------------------------------------------------------------
async def seed_privileged_users(db):
    collection = db["users"]
    existing_privileged = await collection.count_documents({"is_privileged": True})
    if existing_privileged >= 5:
        print(f"  Already have {existing_privileged} privileged users, skipping")
        return

    priv_accounts = [
        {"username": "Administrator", "email": "administrator@corp.local", "role": "admin", "is_privileged": True,
         "department": "IT", "groups": ["Domain Admins", "Enterprise Admins"], "last_login": now_iso(120)},
        {"username": "svc_backup", "email": "svc_backup@corp.local", "role": "service", "is_privileged": True,
         "department": "Operations", "groups": ["Backup Operators"], "last_login": now_iso(300)},
        {"username": "svc_exchange", "email": "svc_exchange@corp.local", "role": "service", "is_privileged": True,
         "department": "IT", "groups": ["Exchange Servers", "Organization Management"], "last_login": now_iso(60)},
        {"username": "john.smith", "email": "john.smith@corp.local", "role": "analyst", "is_privileged": False,
         "department": "Security", "groups": ["Domain Users", "SOC Team"], "last_login": now_iso(30)},
        {"username": "sa_sql", "email": "sa_sql@corp.local", "role": "service", "is_privileged": True,
         "department": "Database", "groups": ["SQL Server Admins"], "last_login": now_iso(15)},
        {"username": "guest_legacy", "email": "guest@corp.local", "role": "viewer", "is_privileged": False,
         "department": "Unknown", "groups": ["Guest"], "last_login": now_iso(4320)},
    ]

    for acct in priv_accounts:
        exists = await collection.find_one({"email": acct["email"]})
        if not exists:
            acct["id"] = str(uuid.uuid4())
            acct["created_at"] = now_iso(9999)
            await collection.insert_one(acct)

    total = await collection.count_documents({})
    privileged = await collection.count_documents({"is_privileged": True})
    print(f"  Users: {total} total, {privileged} privileged")


# ---------------------------------------------------------------------------
# 3. Seed threat response history (MongoDB direct)
# ---------------------------------------------------------------------------
async def seed_response_history(db):
    collection = db["response_history"]
    existing = await collection.count_documents({})
    if existing >= 20:
        print(f"  response_history already has {existing} docs, skipping")
        return

    actions = ["block_ip", "quarantine_file", "kill_process", "isolate_endpoint",
               "disable_user", "update_firewall", "collect_forensics", "send_alert"]
    severities = ["critical", "high", "medium", "low"]
    source_ips = [rand_ip() for _ in range(12)]

    entries = []
    for i in range(40):
        severity = random.choice(severities)
        action = random.choice(actions)
        src_ip = random.choice(source_ips)
        offset = i * 23
        entries.append({
            "id": str(uuid.uuid4()),
            "action": action,
            "severity": severity,
            "source_ip": src_ip,
            "target": random.choice(["192.168.1.50", "192.168.2.100", "WS-IT-03", "DC-PROD-01"]),
            "threat_id": str(uuid.uuid4()),
            "playbook_id": random.choice(["pb_malware_response", "pb_ransomware_response", "ai_recon_degrade_01"]),
            "status": random.choice(["completed", "completed", "completed", "partial", "failed"]),
            "blocked": action == "block_ip",
            "duration_ms": random.randint(150, 4500),
            "created_at": now_iso(offset),
            "completed_at": now_iso(offset - 2),
            "agent_id": str(uuid.uuid4()),
            "notes": f"Auto-response to {severity} {action.replace('_',' ')} event from {src_ip}",
        })

    await collection.insert_many(entries)
    print(f"  Inserted {len(entries)} response history entries")


# ---------------------------------------------------------------------------
# 4. Seed deception events via API
# ---------------------------------------------------------------------------
def seed_deception_events(token: str):
    traffic_scenarios = [
        # (ip, path, score_hint_headers)
        ("45.33.32.156",   "/api/login",          {"User-Agent": "python-requests/2.28.0", "X-Scan": "1"}),
        ("185.220.101.5",  "/wp-admin",            {"User-Agent": "Nmap/7.94"}),
        ("198.51.100.23",  "/api/users",           {"User-Agent": "masscan/1.3", "X-Forwarded-For": "10.0.0.1"}),
        ("91.108.4.1",     "/admin/config",        {"User-Agent": "sqlmap/1.7"}),
        ("162.55.200.100", "/api/secrets",         {"User-Agent": "curl/7.68.0", "Authorization": "Bearer INVALID"}),
        ("45.33.32.200",   "/.env",                {"User-Agent": "Go-http-client/1.1"}),
        ("194.165.16.52",  "/api/admin/users",     {"User-Agent": "python-requests/2.25.0"}),
        ("203.0.113.50",   "/phpmyadmin",          {"User-Agent": "Mozilla/5.0 (compatible; zgrab/0.x)"}),
        ("45.33.32.156",   "/api/tokens/list",     {"User-Agent": "python-requests/2.28.0"}),
        ("185.220.101.5",  "/api/health",          {"User-Agent": "Mozilla/5.0"}),
        ("91.108.4.1",     "/api/integrations",    {"User-Agent": "sqlmap/1.7"}),
        ("162.55.200.100", "/api/agents",          {"User-Agent": "Nessus/10.0"}),
        ("198.51.100.23",  "/api/vpn/peers",       {"User-Agent": "masscan/1.3"}),
        ("45.33.32.200",   "/api/soar/playbooks",  {"User-Agent": "curl/7.68.0"}),
        ("203.0.113.50",   "/api/edr/process-tree", {"User-Agent": "python-urllib3/1.26"}),
        ("194.165.16.52",  "/backup.sql",          {"User-Agent": "Go-http-client/1.1"}),
        ("91.108.4.1",     "/api/auth/login",      {"User-Agent": "Hydra"}),
        ("45.33.32.156",   "/api/threats",         {"User-Agent": "python-requests/2.28.0"}),
        ("185.220.101.5",  "/.git/config",         {"User-Agent": "Nmap/7.94"}),
        ("203.0.113.50",   "/api/users/admin",     {"User-Agent": "zgrab/0.x"}),
    ]

    succeeded = 0
    for ip, path, extra_headers in traffic_scenarios:
        try:
            r = api(token, "post", "v1/deception/assess", json={
                "ip": ip,
                "path": path,
                "headers": extra_headers,
                "session_id": str(uuid.uuid4()),
                "behavior_flags": {
                    "is_automated": True,
                    "rapid_requests": random.random() > 0.4,
                    "unusual_user_agent": True,
                },
            })
            if r.status_code in (200, 201):
                succeeded += 1
        except Exception as e:
            print(f"  WARN deception assess failed for {ip}{path}: {e}")

    print(f"  Seeded {succeeded}/{len(traffic_scenarios)} deception events")


# ---------------------------------------------------------------------------
# 5. Seed quarantine entries directly to MongoDB
#    (The /demo-ingest API endpoint is blocked by /{entry_id} GET route ordering)
# ---------------------------------------------------------------------------
async def seed_quarantine(db):
    collection = db["quarantine"]
    existing = await collection.count_documents({})
    if existing >= 5:
        print(f"  quarantine already has {existing} docs, skipping")
        return

    raw_entries = [
        {"filepath": "/tmp/malware_dropper.exe", "threat_name": "Trojan.GenericKD.47291832",
         "threat_type": "trojan", "detection_source": "clamav", "file_size": 245760,
         "sha256": "a3f2c1d4e5b6a7f8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2"},
        {"filepath": "/home/user/.local/bin/backdoor.py", "threat_name": "Python.Backdoor.Agent",
         "threat_type": "backdoor", "detection_source": "yara", "file_size": 8192,
         "sha256": "b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5"},
        {"filepath": "/var/www/html/webshell.php", "threat_name": "PHP.WebShell.Generic",
         "threat_type": "webshell", "detection_source": "sigma", "file_size": 4096,
         "sha256": "c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"},
        {"filepath": "/root/.ssh/authorized_keys.bak", "threat_name": "Persistence.SSHKey.Injected",
         "threat_type": "persistence", "detection_source": "fim", "file_size": 1024,
         "sha256": "d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7"},
        {"filepath": "/tmp/.hidden/mimikatz.exe", "threat_name": "HackTool.Win32.Mimikatz",
         "threat_type": "hackTool", "detection_source": "clamav", "file_size": 1048576,
         "sha256": "e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8"},
        {"filepath": "/tmp/ransomware_payload.bin", "threat_name": "Ransom.LockBit.3",
         "threat_type": "ransomware", "detection_source": "clamav", "file_size": 524288,
         "sha256": "f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9"},
        {"filepath": "/etc/cron.d/malicious_cron", "threat_name": "Linux.Persistence.CronJob",
         "threat_type": "persistence", "detection_source": "sigma", "file_size": 512,
         "sha256": "a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"},
        {"filepath": "/tmp/cobaltstrike_beacon.bin", "threat_name": "Backdoor.CobaltStrike.Beacon",
         "threat_type": "c2_implant", "detection_source": "yara", "file_size": 393216,
         "sha256": "b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1"},
    ]

    docs = []
    for i, e in enumerate(raw_entries):
        eid = str(uuid.uuid4())
        offset = i * 37
        docs.append({
            "id": eid,
            "original_path": e["filepath"],
            "quarantine_path": f"/var/lib/anti-ai-defense/quarantine/{eid[:8]}/{eid}",
            "file_hash": e["sha256"],
            "file_hash_md5": None,
            "file_hash_sha1": None,
            "file_size": e["file_size"],
            "file_type": e["filepath"].rsplit(".", 1)[-1] if "." in e["filepath"] else "unknown",
            "mime_type": "application/octet-stream",
            "threat_name": e["threat_name"],
            "threat_type": e["threat_type"],
            "detection_source": e["detection_source"],
            "agent_id": str(uuid.uuid4()),
            "agent_name": random.choice(["seraph-agent-prod-01", "seraph-agent-ws03", "seraph-agent-srv02"]),
            "quarantined_at": now_iso(offset),
            "status": random.choice(["quarantined", "quarantined", "quarantined", "analyzing", "deleted"]),
            "pipeline_stage": "quarantined",
            "stage_history": [],
            "scan_results": [{"scanner": e["detection_source"], "detection": True,
                              "threat_name": e["threat_name"], "confidence": 0.95,
                              "scan_time": now_iso(offset - 2)}],
            "sandbox_result": None,
            "threat_intel_hits": [],
            "final_verdict": "malicious",
            "forensics_id": None,
            "chain_of_custody": [],
            "evidence_preserved": False,
            "playbook_id": "pb_malware_response",
            "execution_id": None,
            "soar_synced": False,
            "retention_days": 90,
            "auto_delete_at": None,
            "state_version": 1,
            "state_transition_log": [{"timestamp": now_iso(offset), "from_status": None,
                                       "to_status": "quarantined", "actor": "system:clamav", "reason": "threat detected"}],
            "metadata": {"ingested_by": "seed_demo_data.py"},
        })

    await collection.insert_many(docs)
    print(f"  Inserted {len(docs)} quarantine entries")


# ---------------------------------------------------------------------------
# 6. Seed attack path crown jewels directly to MongoDB
# ---------------------------------------------------------------------------
async def seed_crown_jewels(db):
    collection = db["attack_path_crown_jewels"]
    existing = await collection.count_documents({})
    if existing >= 4:
        print(f"  crown jewels already has {existing} docs, skipping")
        return

    assets = [
        {
            "asset_id": str(uuid.uuid4()),
            "name": "Domain Controller PROD-DC-01",
            "asset_type": "domain_controller",
            "identifier": "dc-prod-01.corp.local",
            "criticality": "crown_jewel",
            "description": "Primary Active Directory domain controller hosting all authentication services",
            "owner": "IT Security Team",
            "data_classification": "RESTRICTED",
            "compliance_scope": ["SOC2", "ISO27001", "PCI-DSS"],
            "network_zone": "internal_critical",
            "tags": {"environment": "production", "os": "Windows Server 2022"},
            "dependencies": ["sql-prod-02.corp.local", "exch-prod-01.corp.local"],
            "created_at": now_iso(9000),
            "updated_at": now_iso(60),
        },
        {
            "asset_id": str(uuid.uuid4()),
            "name": "SQL Production Database",
            "asset_type": "database_server",
            "identifier": "sql-prod-02.corp.local",
            "criticality": "crown_jewel",
            "description": "Primary SQL Server hosting customer PII and financial records",
            "owner": "Database Administration",
            "data_classification": "PII",
            "compliance_scope": ["PCI-DSS", "GDPR", "SOC2"],
            "network_zone": "internal_data",
            "tags": {"environment": "production", "db": "SQL Server 2019"},
            "dependencies": [],
            "created_at": now_iso(9000),
            "updated_at": now_iso(60),
        },
        {
            "asset_id": str(uuid.uuid4()),
            "name": "Secrets Vault / PKI CA",
            "asset_type": "secrets_vault",
            "identifier": "vault.corp.local",
            "criticality": "critical",
            "description": "HashiCorp Vault storing all secrets, certificates and CA",
            "owner": "Security Engineering",
            "data_classification": "RESTRICTED",
            "compliance_scope": ["SOC2", "ISO27001"],
            "network_zone": "dmz_secure",
            "tags": {"environment": "production", "type": "vault"},
            "dependencies": [],
            "created_at": now_iso(9000),
            "updated_at": now_iso(60),
        },
        {
            "asset_id": str(uuid.uuid4()),
            "name": "CI/CD Pipeline Server (Jenkins)",
            "asset_type": "cicd_server",
            "identifier": "jenkins.corp.local",
            "criticality": "high",
            "description": "Jenkins CI/CD server with production deployment credentials",
            "owner": "DevOps Team",
            "data_classification": "CONFIDENTIAL",
            "compliance_scope": ["SOC2"],
            "network_zone": "internal_dev",
            "tags": {"environment": "production", "type": "jenkins"},
            "dependencies": [],
            "created_at": now_iso(9000),
            "updated_at": now_iso(60),
        },
        {
            "asset_id": str(uuid.uuid4()),
            "name": "Exchange Mail Server",
            "asset_type": "email_server",
            "identifier": "exch-prod-01.corp.local",
            "criticality": "high",
            "description": "Microsoft Exchange — critical for business communications",
            "owner": "IT Operations",
            "data_classification": "CONFIDENTIAL",
            "compliance_scope": ["SOC2", "GDPR"],
            "network_zone": "internal",
            "tags": {"environment": "production", "type": "exchange"},
            "dependencies": ["dc-prod-01.corp.local"],
            "created_at": now_iso(9000),
            "updated_at": now_iso(60),
        },
        {
            "asset_id": str(uuid.uuid4()),
            "name": "AWS Cloud Management Console",
            "asset_type": "cloud_controller",
            "identifier": "aws-console.corp.local",
            "criticality": "critical",
            "description": "AWS management account — root access to all cloud resources",
            "owner": "Cloud Platform Team",
            "data_classification": "RESTRICTED",
            "compliance_scope": ["SOC2", "ISO27001", "CSPM"],
            "network_zone": "cloud",
            "tags": {"environment": "production", "provider": "aws"},
            "dependencies": [],
            "created_at": now_iso(9000),
            "updated_at": now_iso(60),
        },
    ]

    await collection.insert_many(assets)
    print(f"  Inserted {len(assets)} crown jewel assets")


# ---------------------------------------------------------------------------
# 7. Trigger attack path analysis
# ---------------------------------------------------------------------------
def trigger_attack_analysis(token: str):
    try:
        r = api(token, "post", "v1/attack-paths/analyze", json={
            "network_nodes": [
                {"id": "node-dc01",    "type": "domain_controller", "ip": "192.168.1.10",  "hostname": "DC-PROD-01",      "risk_score": 85, "vulnerabilities": ["CVE-2021-42278", "CVE-2021-42287"]},
                {"id": "node-sql01",   "type": "database_server",   "ip": "192.168.1.20",  "hostname": "SQL-PROD-02",     "risk_score": 75, "vulnerabilities": ["CVE-2022-21999"]},
                {"id": "node-ws01",    "type": "workstation",       "ip": "192.168.5.15",  "hostname": "WS-IT-03",        "risk_score": 45, "vulnerabilities": ["CVE-2021-34527"]},
                {"id": "node-jenkins", "type": "cicd_server",       "ip": "192.168.3.50",  "hostname": "jenkins.corp",    "risk_score": 70, "vulnerabilities": []},
                {"id": "node-exch01",  "type": "email_server",      "ip": "192.168.1.30",  "hostname": "EXCH-PROD-01",    "risk_score": 60, "vulnerabilities": ["CVE-2021-26855"]},
                {"id": "node-ext01",   "type": "attacker",          "ip": "45.33.32.156",  "hostname": "unknown",         "risk_score": 100, "vulnerabilities": []},
            ],
            "network_edges": [
                {"source": "node-ext01", "target": "node-ws01",    "protocol": "RDP",  "port": 3389, "weight": 0.7},
                {"source": "node-ws01",  "target": "node-dc01",    "protocol": "LDAP", "port": 389,  "weight": 0.9},
                {"source": "node-ws01",  "target": "node-sql01",   "protocol": "SQL",  "port": 1433, "weight": 0.6},
                {"source": "node-dc01",  "target": "node-sql01",   "protocol": "SMB",  "port": 445,  "weight": 0.8},
                {"source": "node-ws01",  "target": "node-jenkins",  "protocol": "HTTP", "port": 8080, "weight": 0.5},
                {"source": "node-dc01",  "target": "node-exch01",  "protocol": "LDAP", "port": 636,  "weight": 0.7},
            ],
        })
        if r.status_code in (200, 201, 202):
            print(f"  Attack path analysis triggered successfully")
        else:
            print(f"  WARN attack path analysis: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"  WARN attack path analysis failed: {e}")


# ---------------------------------------------------------------------------
# 8. Seed additional threats (MongoDB direct) to make timeline richer
# ---------------------------------------------------------------------------
async def seed_threats(db):
    collection = db["threats"]
    existing = await collection.count_documents({})
    if existing >= 20:
        print(f"  threats already has {existing} docs, skipping")
        return

    threat_templates = [
        ("Lateral Movement via SMB",      "lateral_movement",     "high",     "T1021.002"),
        ("DCSync Attack Detected",        "credential_access",    "critical", "T1003.006"),
        ("Cobalt Strike Beacon C2",       "command_and_control",  "critical", "T1071.001"),
        ("PowerShell Empire Activity",    "execution",            "high",     "T1059.001"),
        ("LDAP Enumeration Sweep",        "discovery",            "medium",   "T1018"),
        ("Pass-the-Hash Attempt",         "lateral_movement",     "high",     "T1550.002"),
        ("Kerberoasting Activity",        "credential_access",    "high",     "T1558.003"),
        ("Suspicious Scheduled Task",     "persistence",          "medium",   "T1053.005"),
        ("Exfiltration via DNS",          "exfiltration",         "high",     "T1048.003"),
        ("Golden Ticket Detected",        "privilege_escalation", "critical", "T1558.001"),
        ("WMI Lateral Movement",          "lateral_movement",     "high",     "T1047"),
        ("NTDS.dit Extraction",           "credential_access",    "critical", "T1003.003"),
    ]

    new_threats = []
    for i, (name, ttype, severity, mitre) in enumerate(threat_templates):
        offset = (i + 1) * 61
        new_threats.append({
            "id": str(uuid.uuid4()),
            "name": f"{name} {uuid.uuid4().hex[:6]}",
            "type": ttype,
            "severity": severity,
            "status": random.choice(["active", "active", "investigating", "resolved"]),
            "source_ip": rand_ip(),
            "destination_ip": rand_internal_ip(),
            "mitre_technique": mitre,
            "mitre_tactic": ttype.replace("_", "-"),
            "confidence": round(random.uniform(0.75, 0.98), 2),
            "description": f"Threat detected: {name}. Immediate investigation required.",
            "created_at": now_iso(offset),
            "updated_at": now_iso(offset - 10),
            "agent_id": str(uuid.uuid4()),
            "endpoint": random.choice(["WS-IT-03", "DC-PROD-01", "SQL-PROD-02", "EXCH-01"]),
        })

    await collection.insert_many(new_threats)
    print(f"  Inserted {len(new_threats)} additional threats (total: {existing + len(new_threats)})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    print("=== Seraph Demo Data Seeder ===")

    # MongoDB
    print("\n[MongoDB] Connecting...")
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
        print("  MongoDB connected OK")
    except Exception as e:
        print(f"  ERROR: Cannot connect to MongoDB: {e}")
        sys.exit(1)
    db = client[DB_NAME]

    print("\n[1] Identity incidents...")
    await seed_identity_incidents(db)

    print("\n[2] Privileged users...")
    await seed_privileged_users(db)

    print("\n[3] Threat response history...")
    await seed_response_history(db)

    print("\n[4] Additional threats (for timeline)...")
    await seed_threats(db)

    # API token
    print("\n[API] Getting auth token...")
    try:
        token = get_token()
        print("  Token obtained OK")
    except Exception as e:
        print(f"  ERROR: Cannot get token: {e}")
        print("  Skipping API-based seeding")
        return

    print("\n[5] Deception events (via API)...")
    seed_deception_events(token)

    print("\n[6] Quarantine entries (MongoDB direct)...")
    await seed_quarantine(db)

    print("\n[7] Crown jewel assets (MongoDB direct)...")
    await seed_crown_jewels(db)

    print("\n[8] Attack path analysis (via API)...")
    trigger_attack_analysis(token)

    # Final summary
    print("\n=== Collection Counts ===")
    for cname in ["threats", "identity_incidents", "response_history", "quarantine", "attack_path_crown_jewels", "users"]:
        n = await db[cname].count_documents({})
        print(f"  {cname}: {n}")

    client.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
