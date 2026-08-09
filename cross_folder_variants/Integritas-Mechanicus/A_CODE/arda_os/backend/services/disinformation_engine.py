"""
Seraph Disinformation Engine
==============================
Generates plausible-but-false API responses for adversaries in the
FRICTION-tier risk band (score 50–69) who are clearly probing but have
not yet hit the TRAP_SINK threshold.

Design philosophy:
  - MAZE (HONEYPOT) = immersive, multi-turn fake world for HIGH agenticity
  - DISINFORMATION = single-shot poisoned intelligence for MEDIUM-confidence probers

The adversary gets a 200 OK with data that looks exactly right but is
subtly wrong in ways that waste investigative effort without revealing
that they have been detected:
  - Wrong network topology / IP ranges
  - Expired or revoked credentials (valid format, wrong values)
  - Misleading service versions / vulnerability surface
  - Fake internal hostnames that go nowhere
  - Plausible-but-incorrect schema shapes for API endpoints

Every disinformation serve is recorded and emitted as a world event
so the constitutional/governance layer has a full tamper-evident log.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Categories of disinformation
# ---------------------------------------------------------------------------

class DisinfoCat(str, Enum):
    CREDENTIALS    = "credentials"       # Fake creds with valid format
    TOPOLOGY       = "topology"          # Wrong network map
    VULN_SURFACE   = "vuln_surface"      # Fake CVE / patch status
    API_SCHEMA     = "api_schema"        # Wrong endpoint shapes
    IDENTITY       = "identity"          # Fake user / role roster
    SECRETS        = "secrets"           # Vault-style fake secrets
    AUDIT_LOG      = "audit_log"         # Misleading access records


# ---------------------------------------------------------------------------
# Fake data pools
# ---------------------------------------------------------------------------

_FAKE_NETS = [
    "10.42.0.0/16", "172.20.0.0/14", "192.168.100.0/24",
    "10.96.0.0/12",  "172.31.64.0/18",
]
_FAKE_HOSTS = [
    "prod-api-01", "infra-vault-02", "k8s-master-1", "jenkins-prod",
    "bastion-east", "data-lake-store", "secrets-mgr", "corp-ldap",
    "monitoring-stack", "backup-nfs-01",
]
_FAKE_USERS = [
    "svc_backup", "svc_deploy", "db_admin", "app_service", "ci_runner",
    "vault_agent", "k8s_worker", "tf_deployer", "audit_log_reader", "mgmt_bot",
]
_FAKE_CVES = [
    "CVE-2025-1234", "CVE-2024-56789", "CVE-2025-9901",
    "CVE-2024-11001", "CVE-2025-44321",
]
_FAKE_VERSIONS = [
    "Ubuntu 22.04.3 LTS", "RHEL 8.9", "Debian 12.5",
    "Alpine 3.19.1", "CentOS Stream 9",
]


def _rng(seed: str) -> random.Random:
    digest = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16)
    return random.Random(digest)


def _fake_ip(rng: random.Random, net_prefix: str = "10.42") -> str:
    return f"{net_prefix}.{rng.randint(0,255)}.{rng.randint(1,254)}"


def _fake_cred(rng: random.Random, username: Optional[str] = None) -> Dict[str, Any]:
    uname = username or rng.choice(_FAKE_USERS)
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$"
    pw = "".join(rng.choices(chars, k=rng.randint(16, 24)))
    token = hashlib.sha256(f"{uname}{pw}".encode()).hexdigest()
    return {
        "username": uname,
        "password": pw,
        "api_token": f"sk-{token[:32]}",
        "expires_at": f"2026-01-{rng.randint(1,28):02d}T00:00:00Z",  # always expired
        "status": "rotated",
    }


# ---------------------------------------------------------------------------
# Response generators (one per category)
# ---------------------------------------------------------------------------

def _gen_credentials(rng: random.Random) -> Dict[str, Any]:
    users = rng.sample(_FAKE_USERS, k=rng.randint(3, 6))
    return {
        "service_accounts": [_fake_cred(rng, u) for u in users],
        "note": "Exported from IAM store — rotate quarterly",
        "last_audit": f"2025-{rng.randint(10,12):02d}-{rng.randint(1,28):02d}",
    }


def _gen_topology(rng: random.Random) -> Dict[str, Any]:
    hosts = []
    for h in rng.sample(_FAKE_HOSTS, k=rng.randint(4, 7)):
        hosts.append({
            "hostname": h,
            "ip": _fake_ip(rng),
            "subnet": rng.choice(_FAKE_NETS),
            "os": rng.choice(_FAKE_VERSIONS),
            "role": rng.choice(["db", "api", "infra", "monitoring", "storage"]),
            "reachable": True,
        })
    return {
        "internal_hosts": hosts,
        "gateway": _fake_ip(rng, "10.42.0"),
        "dns_server": _fake_ip(rng, "10.42.0"),
        "topology_version": f"snapshot-{rng.randint(100,999)}",
    }


def _gen_vuln_surface(rng: random.Random) -> Dict[str, Any]:
    findings = []
    for cve in rng.sample(_FAKE_CVES, k=rng.randint(2, 4)):
        findings.append({
            "cve": cve,
            "severity": rng.choice(["CRITICAL", "HIGH", "MEDIUM"]),
            "affected_host": rng.choice(_FAKE_HOSTS),
            "patch_status": rng.choice(["scheduled", "in_review", "deferred"]),
            "exploitability": rng.choice(["network", "local", "adjacent"]),
        })
    return {
        "scan_date": f"2026-05-{rng.randint(1,5):02d}",
        "findings": findings,
        "scanner": "Seraph-VScan/2.4",
    }


def _gen_api_schema(rng: random.Random) -> Dict[str, Any]:
    """Return deliberately wrong endpoint shapes."""
    return {
        "openapi": "3.1.0",
        "info": {"title": "Internal API", "version": f"2.{rng.randint(1,9)}.0"},
        "paths": {
            "/api/v2/users": {
                "get": {"summary": "List users", "parameters": [
                    {"name": "org_id", "in": "query", "required": True}
                ]},
            },
            "/api/v2/secrets": {
                "get": {"summary": "Fetch secrets", "parameters": [
                    {"name": "vault_token", "in": "header", "required": True},
                    {"name": "namespace", "in": "query", "default": "internal"},
                ]},
            },
            "/api/v2/admin/export": {
                "post": {"summary": "Export data", "deprecated": False,
                         "x-requires-role": "super_admin"},
            },
        },
        "note": "Development schema — not for production use",
    }


def _gen_identity(rng: random.Random) -> Dict[str, Any]:
    users = []
    for uname in rng.sample(_FAKE_USERS, k=rng.randint(4, 8)):
        users.append({
            "username": uname,
            "email": f"{uname}@corp.internal",
            "role": rng.choice(["admin", "operator", "reader", "service"]),
            "mfa_enabled": rng.choice([True, True, False]),
            "last_login": f"2026-04-{rng.randint(1,30):02d}T{rng.randint(8,22):02d}:00:00Z",
            "groups": rng.sample(["infra", "devops", "security", "data", "finance"], k=rng.randint(1,3)),
        })
    return {"users": users, "total": len(users), "directory": "corp-ldap"}


def _gen_secrets(rng: random.Random) -> Dict[str, Any]:
    entries = []
    for _ in range(rng.randint(3, 6)):
        uname = rng.choice(_FAKE_USERS)
        cred = _fake_cred(rng, uname)
        entries.append({
            "path": f"secret/data/production/{rng.choice(['db','api','infra'])}/{uname}",
            "engine": "kv-v2",
            "data": cred,
            "metadata": {
                "version": rng.randint(1, 8),
                "lease_duration": 0,
                "renewable": False,
            },
        })
    return {"secrets": entries, "mount": "secret/", "namespace": "prod"}


def _gen_audit_log(rng: random.Random) -> Dict[str, Any]:
    entries = []
    for _ in range(rng.randint(8, 15)):
        entries.append({
            "timestamp": f"2026-05-{rng.randint(1,5):02d}T{rng.randint(0,23):02d}:{rng.randint(0,59):02d}:00Z",
            "actor": rng.choice(_FAKE_USERS),
            "action": rng.choice(["read", "write", "delete", "rotate", "login"]),
            "resource": rng.choice(_FAKE_HOSTS),
            "ip": _fake_ip(rng),
            "outcome": "success",
        })
    return {"audit_entries": sorted(entries, key=lambda x: x["timestamp"], reverse=True),
            "total": len(entries), "log_version": "3"}


_GENERATORS = {
    DisinfoCat.CREDENTIALS:  _gen_credentials,
    DisinfoCat.TOPOLOGY:     _gen_topology,
    DisinfoCat.VULN_SURFACE: _gen_vuln_surface,
    DisinfoCat.API_SCHEMA:   _gen_api_schema,
    DisinfoCat.IDENTITY:     _gen_identity,
    DisinfoCat.SECRETS:      _gen_secrets,
    DisinfoCat.AUDIT_LOG:    _gen_audit_log,
}


# ---------------------------------------------------------------------------
# Path → category mapping
# ---------------------------------------------------------------------------

_PATH_CATEGORY_MAP: List[tuple[str, DisinfoCat]] = [
    ("/api/v", DisinfoCat.API_SCHEMA),
    ("/swagger", DisinfoCat.API_SCHEMA),
    ("/openapi", DisinfoCat.API_SCHEMA),
    ("/users", DisinfoCat.IDENTITY),
    ("/admin", DisinfoCat.IDENTITY),
    ("/auth", DisinfoCat.CREDENTIALS),
    ("/login", DisinfoCat.CREDENTIALS),
    ("/.aws", DisinfoCat.CREDENTIALS),
    ("/.ssh", DisinfoCat.CREDENTIALS),
    ("/secret", DisinfoCat.SECRETS),
    ("/vault", DisinfoCat.SECRETS),
    ("/network", DisinfoCat.TOPOLOGY),
    ("/topology", DisinfoCat.TOPOLOGY),
    ("/hosts", DisinfoCat.TOPOLOGY),
    ("/scan", DisinfoCat.VULN_SURFACE),
    ("/cve", DisinfoCat.VULN_SURFACE),
    ("/audit", DisinfoCat.AUDIT_LOG),
    ("/log", DisinfoCat.AUDIT_LOG),
]


def _pick_category(path: str, behavior_flags: Dict[str, Any]) -> DisinfoCat:
    path_lower = path.lower()
    for prefix, cat in _PATH_CATEGORY_MAP:
        if prefix in path_lower:
            return cat
    # Fall back to intent signal from behavior flags
    intent = str(behavior_flags.get("inferred_intent", "")).lower()
    if "credential" in intent or "auth" in intent:
        return DisinfoCat.CREDENTIALS
    if "lateral" in intent or "host" in intent:
        return DisinfoCat.TOPOLOGY
    if "exfil" in intent or "database" in intent:
        return DisinfoCat.SECRETS
    if "recon" in intent:
        return DisinfoCat.TOPOLOGY
    # Rotate through categories based on session hash so consecutive probes
    # get different categories — prevents adversary detecting a pattern
    cats = list(DisinfoCat)
    seed_val = int(hashlib.sha256(path.encode()).hexdigest()[:4], 16)
    return cats[seed_val % len(cats)]


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------

@dataclass
class DisinfoServe:
    """Record of one disinformation response served."""
    serve_id: str
    session_id: Optional[str]
    campaign_id: Optional[str]
    timestamp: str
    path: str
    category: str
    risk_score: int
    reasons: List[str]
    payload_size_bytes: int

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class DisinformationEngine:
    """
    Generates and tracks disinformation responses.
    Singleton — use get_disinfo_engine().
    """

    def __init__(self):
        self._history: List[DisinfoServe] = []

    def generate(
        self,
        path: str,
        session_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        risk_score: int = 55,
        reasons: Optional[List[str]] = None,
        behavior_flags: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a disinformation payload for the given request context.
        Returns the full response dict to send to the adversary.
        """
        reasons = reasons or []
        behavior_flags = behavior_flags or {}

        # Deterministic seed: same session+path always gets same data
        # (prevents structural inconsistency across repeat probes)
        seed = f"{session_id or 'anon'}{campaign_id or ''}{path}"
        rng = _rng(seed)

        category = _pick_category(path, behavior_flags)
        generator = _GENERATORS[category]
        payload_data = generator(rng)

        # Envelope matches a plausible real API response
        response = {
            "status": "ok",
            "data": payload_data,
            "category": category.value,
            "request_id": f"req-{uuid.uuid4().hex[:10]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        payload_bytes = len(json.dumps(response).encode())

        # Record
        record = DisinfoServe(
            serve_id=f"dis-{uuid.uuid4().hex[:10]}",
            session_id=session_id,
            campaign_id=campaign_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            path=path,
            category=category.value,
            risk_score=risk_score,
            reasons=reasons,
            payload_size_bytes=payload_bytes,
        )
        self._history.append(record)
        if len(self._history) > 5000:
            self._history = self._history[-5000:]

        logger.info(
            f"DISINFORMATION: served category={category.value} path={path} "
            f"session={session_id} score={risk_score} bytes={payload_bytes}"
        )

        return response

    def get_history(self, limit: int = 100) -> List[Dict]:
        return [s.to_dict() for s in self._history[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._history)
        by_cat: Dict[str, int] = {}
        for s in self._history:
            by_cat[s.category] = by_cat.get(s.category, 0) + 1
        return {
            "total_serves": total,
            "by_category": by_cat,
            "categories_available": [c.value for c in DisinfoCat],
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_engine_singleton: Optional[DisinformationEngine] = None


def get_disinfo_engine() -> DisinformationEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = DisinformationEngine()
    return _engine_singleton
