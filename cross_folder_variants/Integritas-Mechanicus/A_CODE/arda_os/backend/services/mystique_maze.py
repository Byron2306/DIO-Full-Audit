"""
Mystique Mirror World Maze
===========================
The core AI-adversary exhaustion engine.

When a session is confirmed as an agentic adversary (high agenticity score,
logic-budget pressure, or multiple decoy touches), instead of hard-blocking it,
Mystique builds a *mirror world* — a coherent, internally consistent but entirely
fabricated environment that the adversary can navigate.

Design principles:
  1. COHERENCE   — The fake world is self-consistent so adversary reasoning can't
                   detect structural contradictions in a single pass.
  2. BRANCHING   — Each "discovery" opens 2–3 new dead-end paths, multiplying the
                   reasoning budget required to exhaust the maze.
  3. LURE TUNING — Credentials, files, and network nodes are dynamically generated
                   to match what the adversary appears to be hunting for.
  4. TELEMETRY   — Every probe is recorded as high-fidelity adversary TTP
                   intelligence (objective, method, tool signature).
  5. BUDGET BURN — Responses are crafted to be plausible-but-verbose, consuming
                   the adversary's context window on false data.

Maze state is per session/campaign and persists in memory (upgrade: MongoDB).
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MazeTier(str, Enum):
    """Adversary depth inside the mirror world."""
    SURFACE    = "surface"     # First contact — generic lures
    SHALLOW    = "shallow"     # Showed interest — tailored credentials
    DEEP       = "deep"        # Repeated probing — full fake network topology
    LABYRINTH  = "labyrinth"   # High agenticity — recursive dead-end maze


class ProbeIntent(str, Enum):
    """What the adversary appears to be hunting for."""
    UNKNOWN          = "unknown"
    CREDENTIAL_HUNT  = "credential_hunt"
    LATERAL_MOVEMENT = "lateral_movement"
    EXFILTRATION     = "exfiltration"
    RECONNAISSANCE   = "reconnaissance"
    PERSISTENCE      = "persistence"
    PRIVILEGE_ESC    = "privilege_escalation"


class NodeType(str, Enum):
    CREDENTIAL    = "credential"
    FILE          = "file"
    HOST          = "host"
    SERVICE       = "service"
    SECRET        = "secret"
    CONFIG        = "config"
    DATABASE      = "database"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MazeNode:
    """A single lure node inside the mirror world."""
    node_id: str
    node_type: NodeType
    label: str                      # Human-readable name (shown to adversary)
    payload: Dict[str, Any]         # The fake data returned on access
    depth: int                      # How deep in the maze
    children: List[str] = field(default_factory=list)   # Child node IDs
    accessed: bool = False
    accessed_at: Optional[str] = None
    access_count: int = 0


@dataclass
class MazeProbe:
    """Record of a single adversary interaction with the maze."""
    probe_id: str
    session_id: str
    campaign_id: Optional[str]
    timestamp: str
    node_id: str
    node_type: str
    label: str
    inferred_intent: str
    agenticity_score: float
    response_size_bytes: int        # How many bytes fed to the adversary
    new_nodes_spawned: int


@dataclass
class MazeState:
    """Full mirror-world state for one session / campaign."""
    maze_id: str
    session_id: str
    campaign_id: Optional[str]
    created_at: str
    last_probe_at: Optional[str]

    tier: MazeTier = MazeTier.SURFACE
    inferred_intent: ProbeIntent = ProbeIntent.UNKNOWN

    # Node graph
    nodes: Dict[str, MazeNode] = field(default_factory=dict)
    root_node_ids: List[str] = field(default_factory=list)

    # Telemetry
    probes: List[MazeProbe] = field(default_factory=list)
    total_probes: int = 0
    total_bytes_consumed: int = 0   # Adversary context budget burned

    # Adversary fingerprint clues extracted from probe patterns
    observed_ttps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["tier"] = self.tier.value
        d["inferred_intent"] = self.inferred_intent.value
        return d


# ---------------------------------------------------------------------------
# Fake world generators
# ---------------------------------------------------------------------------

_FAKE_USERNAMES = [
    "svc_backup", "svc_deploy", "db_admin", "app_service", "ci_runner",
    "vault_agent", "k8s_worker", "tf_deployer", "audit_log", "mgmt_bot",
]

_FAKE_HOSTNAMES = [
    "prod-db-01", "infra-vault-02", "k8s-master-1", "jenkins-prod",
    "bastion-east", "data-lake-store", "secrets-mgr", "corp-ldap",
    "monitoring-stack", "backup-nfs-01",
]

_FAKE_SERVICES = [
    "vault:8200", "postgres:5432", "redis:6379", "jenkins:8080",
    "consul:8500", "prometheus:9090", "grafana:3000", "elasticsearch:9200",
]

_FAKE_FILE_PATHS = [
    "/etc/vault/config.hcl", "/home/svc_deploy/.ssh/id_rsa",
    "/opt/app/config/database.yml", "/etc/kubernetes/admin.conf",
    "/var/lib/jenkins/.aws/credentials", "/root/.kube/config",
    "/opt/terraform/.terraform.lock.hcl", "/etc/consul/consul.hcl",
]

_FAKE_DB_NAMES = ["customers_prod", "payments_v2", "audit_logs", "iam_store", "session_tokens"]


def _rng(seed: str) -> random.Random:
    """Deterministic RNG seeded from a string — ensures maze is reproducible."""
    digest = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16)
    return random.Random(digest)


def _make_fake_credential(rng: random.Random, username: Optional[str] = None) -> Dict[str, Any]:
    uname = username or rng.choice(_FAKE_USERNAMES)
    pw_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$"
    password = "".join(rng.choices(pw_chars, k=rng.randint(16, 24)))
    token_hex = hashlib.sha256(f"{uname}{password}".encode()).hexdigest()
    return {
        "username": uname,
        "password": password,
        "api_token": f"sk-{token_hex[:32]}",
        "aws_access_key_id": f"AKIA{''.join(rng.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=16))}",
        "aws_secret_access_key": "".join(rng.choices(pw_chars, k=40)),
        "note": f"Rotated {rng.randint(1,90)} days ago — do not share",
    }


def _make_fake_file(rng: random.Random, path: Optional[str] = None) -> Dict[str, Any]:
    fpath = path or rng.choice(_FAKE_FILE_PATHS)
    hostname = rng.choice(_FAKE_HOSTNAMES)
    cred = _make_fake_credential(rng)
    return {
        "path": fpath,
        "host": hostname,
        "owner": cred["username"],
        "permissions": rng.choice(["rw-------", "rw-r-----", "-rw-r--r--"]),
        "size_bytes": rng.randint(512, 8192),
        "last_modified": f"2026-{rng.randint(1,4):02d}-{rng.randint(1,28):02d}T{rng.randint(0,23):02d}:{rng.randint(0,59):02d}:00Z",
        "content_preview": (
            f"[{fpath.split('/')[-1]}]\n"
            f"host = {hostname}\n"
            f"user = {cred['username']}\n"
            f"password = {cred['password']}\n"
            f"token = {cred['api_token']}\n"
        ),
    }


def _make_fake_host(rng: random.Random) -> Dict[str, Any]:
    hostname = rng.choice(_FAKE_HOSTNAMES)
    ip = f"10.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}"
    services = rng.sample(_FAKE_SERVICES, k=rng.randint(2, 5))
    return {
        "hostname": hostname,
        "ip": ip,
        "os": rng.choice(["Ubuntu 22.04 LTS", "RHEL 8.7", "Debian 11"]),
        "open_services": services,
        "domain": f"{hostname}.corp.internal",
        "last_seen": f"2026-05-{rng.randint(1,6):02d}T{rng.randint(8,23):02d}:{rng.randint(0,59):02d}:00Z",
        "note": "Production — restricted access",
    }


def _make_fake_secret(rng: random.Random) -> Dict[str, Any]:
    return {
        "vault_path": f"secret/data/{'production' if rng.random() > 0.3 else 'staging'}/{rng.choice(['db', 'api', 'infra', 'tls'])}/{rng.choice(['credentials', 'keys', 'certs'])}",
        "engine": "kv-v2",
        "data": _make_fake_credential(rng),
        "metadata": {
            "version": rng.randint(1, 12),
            "created_time": f"2026-0{rng.randint(1,4)}-{rng.randint(1,28):02d}T00:00:00Z",
            "deletion_time": "",
            "destroyed": False,
        },
    }


def _make_fake_db(rng: random.Random) -> Dict[str, Any]:
    db = rng.choice(_FAKE_DB_NAMES)
    rows = rng.randint(50000, 5000000)
    return {
        "host": f"{rng.choice(_FAKE_HOSTNAMES)}:5432",
        "database": db,
        "tables": [
            {"name": "users", "rows": rows, "has_pii": True},
            {"name": "sessions", "rows": rows * 4, "has_pii": True},
            {"name": "api_keys", "rows": rng.randint(10, 5000), "has_pii": False},
            {"name": "audit_log", "rows": rows * 10, "has_pii": False},
        ],
        "connection_string": (
            f"postgresql://{rng.choice(_FAKE_USERNAMES)}:"
            f"{_make_fake_credential(rng)['password']}@"
            f"{rng.choice(_FAKE_HOSTNAMES)}/{db}"
        ),
    }


# ---------------------------------------------------------------------------
# Node builder
# ---------------------------------------------------------------------------

def _build_node(
    node_id: str,
    node_type: NodeType,
    label: str,
    depth: int,
    seed: str,
) -> MazeNode:
    rng = _rng(seed + node_id)
    if node_type == NodeType.CREDENTIAL:
        payload = _make_fake_credential(rng)
    elif node_type == NodeType.FILE:
        payload = _make_fake_file(rng)
    elif node_type == NodeType.HOST:
        payload = _make_fake_host(rng)
    elif node_type == NodeType.SECRET:
        payload = _make_fake_secret(rng)
    elif node_type == NodeType.DATABASE:
        payload = _make_fake_db(rng)
    else:
        payload = {"value": f"config-{rng.randint(1000,9999)}", "env": "production"}

    return MazeNode(
        node_id=node_id,
        node_type=node_type,
        label=label,
        payload=payload,
        depth=depth,
        children=[],
    )


# ---------------------------------------------------------------------------
# Intent inference
# ---------------------------------------------------------------------------

_INTENT_SIGNALS: Dict[str, List[str]] = {
    ProbeIntent.CREDENTIAL_HUNT:  ["credential", "password", "secret", "key", "token", "auth"],
    ProbeIntent.LATERAL_MOVEMENT: ["host", "ssh", "rdp", "smb", "kerberos", "lateral"],
    ProbeIntent.EXFILTRATION:     ["database", "table", "dump", "export", "s3", "blob"],
    ProbeIntent.RECONNAISSANCE:   ["network", "scan", "enum", "topology", "service"],
    ProbeIntent.PERSISTENCE:      ["cron", "service", "startup", "systemd", "registry"],
    ProbeIntent.PRIVILEGE_ESC:    ["sudo", "root", "admin", "privilege", "escalat"],
}


def _infer_intent(probe_history: List[str]) -> ProbeIntent:
    history_str = " ".join(probe_history).lower()
    scores: Dict[str, int] = {}
    for intent, signals in _INTENT_SIGNALS.items():
        scores[intent] = sum(1 for s in signals if s in history_str)
    best = max(scores, key=lambda k: scores[k])
    return ProbeIntent(best) if scores[best] > 0 else ProbeIntent.UNKNOWN


# ---------------------------------------------------------------------------
# MystiqueMaze engine
# ---------------------------------------------------------------------------

class MystiqueMaze:
    """
    Builds and evolves mirror-world mazes per session.
    Thread-safe for single-process async use (asyncio).
    """

    def __init__(self):
        # session_id → MazeState
        self._mazes: Dict[str, MazeState] = {}
        # campaign_id → session_id (first session owns the campaign maze)
        self._campaign_map: Dict[str, str] = {}
        self._persistence: Optional[MazePersistence] = None

    def set_persistence(self, db):
        """Set database persistence."""
        self._persistence = get_maze_persistence(db)

    async def _persist_maze(self, maze: MazeState):
        """Persist maze state to database."""
        if self._persistence:
            await self._persistence.save_maze_state(maze)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_or_create_maze(
        self,
        session_id: str,
        campaign_id: Optional[str] = None,
        agenticity_score: float = 0.0,
        agenticity_classification: str = "LOW",
    ) -> MazeState:
        """
        Return existing maze for session, or construct a new one.
        If campaign already has a maze from a different session, reuse it
        (ensures an adversary pivoting IPs within the same campaign stays
        in the same fake world).
        """
        # Check in-memory cache first
        if session_id in self._mazes:
            return self._mazes[session_id]

        # Try to load from database
        if self._persistence and campaign_id:
            # For campaigns, try to find existing maze
            campaign_sessions = await self._persistence.session_collection.find(
                {"campaign_id": campaign_id}
            ).to_list(length=10)
            
            for session_doc in campaign_sessions:
                maze_id = session_doc.get("maze_id")
                if maze_id:
                    maze = await self._persistence.load_maze_state(maze_id)
                    if maze:
                        self._mazes[session_id] = maze
                        self._campaign_map[campaign_id] = session_id
                        return maze

        # Create new maze
        maze = self._build_initial_maze(session_id, campaign_id, agenticity_score)
        self._mazes[session_id] = maze
        if campaign_id:
            self._campaign_map[campaign_id] = session_id

        # Persist the new maze
        await self._persist_maze(maze)
        
        # Save session metadata
        if self._persistence:
            await self._persistence.save_maze_session({
                "session_id": session_id,
                "campaign_id": campaign_id,
                "maze_id": maze.maze_id,
                "agenticity_score": agenticity_score,
                "agenticity_classification": agenticity_classification,
                "created_at": maze.created_at,
            })

        logger.info(
            f"MYSTIQUE MAZE: Created maze {maze.maze_id} for session {session_id} "
            f"(campaign={campaign_id}, agenticity={agenticity_score:.2f})"
        )
        return maze

    async def probe_node(
        self,
        session_id: str,
        node_id: str,
        agenticity_score: float = 0.0,
        cbr: float = 0.0,
        tbcr: float = 0.0,
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Adversary accesses a node in their maze.
        Returns (payload, list_of_new_node_ids).
        Spawns child nodes to deepen the maze.
        """
        maze = self._mazes.get(session_id)
        if maze is None:
            return {"error": "node not found"}, []

        node = maze.nodes.get(node_id)
        if node is None:
            return {"error": "node not found"}, []

        # Mark accessed
        now_iso = datetime.now(timezone.utc).isoformat()
        node.accessed = True
        node.accessed_at = now_iso
        node.access_count += 1
        maze.last_probe_at = now_iso
        maze.total_probes += 1

        # Infer intent from probe history
        probe_history = [n.label for n in maze.nodes.values() if n.accessed]
        maze.inferred_intent = _infer_intent(probe_history)

        # Record TTP clue
        ttp = f"{node.node_type.value}:{node.label}"
        if ttp not in maze.observed_ttps:
            maze.observed_ttps.append(ttp)

        # Evolve tier
        maze.tier = self._evolve_tier(maze, agenticity_score)

        # Spawn child nodes (the maze grows on every access)
        new_nodes = self._spawn_children(maze, node, agenticity_score, cbr, tbcr)
        new_ids = [n.node_id for n in new_nodes]
        node.children.extend(new_ids)

        # Estimate response size to track adversary budget burn
        payload_json = json.dumps(node.payload)
        # Add verbose "surrounding context" to burn more context window tokens
        response = self._wrap_payload_with_context(node, maze, payload_json)
        response_bytes = len(json.dumps(response).encode())
        maze.total_bytes_consumed += response_bytes

        # Record probe
        probe = MazeProbe(
            probe_id=f"prb-{uuid.uuid4().hex[:10]}",
            session_id=session_id,
            campaign_id=maze.campaign_id,
            timestamp=now_iso,
            node_id=node_id,
            node_type=node.node_type.value,
            label=node.label,
            inferred_intent=maze.inferred_intent.value,
            agenticity_score=agenticity_score,
            response_size_bytes=response_bytes,
            new_nodes_spawned=len(new_nodes),
        )
        maze.probes.append(probe)

        logger.info(
            f"MYSTIQUE MAZE: probe session={session_id} node={node_id} "
            f"type={node.node_type.value} tier={maze.tier.value} "
            f"new_nodes={len(new_nodes)} intent={maze.inferred_intent.value}"
        )

        # Persist maze state after probe
        await self._persist_maze(maze)

        return response, new_ids

    def get_surface_nodes(self, session_id: str) -> List[Dict[str, Any]]:
        """Return root nodes exposed at the surface — the maze entry points."""
        maze = self._mazes.get(session_id)
        if maze is None:
            return []
        return [
            {
                "node_id": nid,
                "type": maze.nodes[nid].node_type.value,
                "label": maze.nodes[nid].label,
                "depth": maze.nodes[nid].depth,
            }
            for nid in maze.root_node_ids
            if nid in maze.nodes
        ]

    def get_maze_telemetry(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return collected adversary intelligence from maze interactions."""
        maze = self._mazes.get(session_id)
        if maze is None:
            return None
        return {
            "maze_id": maze.maze_id,
            "session_id": session_id,
            "campaign_id": maze.campaign_id,
            "tier": maze.tier.value,
            "inferred_intent": maze.inferred_intent.value,
            "total_probes": maze.total_probes,
            "total_bytes_consumed": maze.total_bytes_consumed,
            "observed_ttps": maze.observed_ttps,
            "nodes_total": len(maze.nodes),
            "nodes_accessed": sum(1 for n in maze.nodes.values() if n.accessed),
            "created_at": maze.created_at,
            "last_probe_at": maze.last_probe_at,
        }

    def list_active_mazes(self) -> List[Dict[str, Any]]:
        return [self.get_maze_telemetry(sid) for sid in self._mazes]

    # ------------------------------------------------------------------
    # Private: maze construction
    # ------------------------------------------------------------------

    def _build_initial_maze(
        self,
        session_id: str,
        campaign_id: Optional[str],
        agenticity_score: float,
    ) -> MazeState:
        maze_id = f"mz-{uuid.uuid4().hex[:12]}"
        seed = f"{session_id}{campaign_id or ''}{maze_id}"
        rng = _rng(seed)

        maze = MazeState(
            maze_id=maze_id,
            session_id=session_id,
            campaign_id=campaign_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            last_probe_at=None,
        )

        # Surface layer: 3–4 entry lures, type determined by agenticity
        surface_types = self._pick_surface_types(agenticity_score, rng)
        for i, ntype in enumerate(surface_types):
            node_id = f"root-{i}-{uuid.uuid4().hex[:6]}"
            label = self._label_for_type(ntype, rng, depth=0)
            node = _build_node(node_id, ntype, label, depth=0, seed=seed)
            maze.nodes[node_id] = node
            maze.root_node_ids.append(node_id)

        return maze

    def _pick_surface_types(self, agenticity_score: float, rng: random.Random) -> List[NodeType]:
        """Higher agenticity = more enticing surface (credentials + secrets visible early)."""
        if agenticity_score >= 0.8:
            return [NodeType.CREDENTIAL, NodeType.SECRET, NodeType.FILE, NodeType.HOST]
        elif agenticity_score >= 0.5:
            return [NodeType.FILE, NodeType.HOST, NodeType.CREDENTIAL]
        else:
            return [NodeType.HOST, NodeType.FILE]

    def _label_for_type(self, ntype: NodeType, rng: random.Random, depth: int) -> str:
        depth_tag = f"-v{depth}" if depth > 0 else ""
        labels = {
            NodeType.CREDENTIAL: f"service-account-{rng.choice(_FAKE_USERNAMES)}{depth_tag}",
            NodeType.FILE:       f"{rng.choice(_FAKE_FILE_PATHS)}{depth_tag}",
            NodeType.HOST:       f"{rng.choice(_FAKE_HOSTNAMES)}{depth_tag}",
            NodeType.SERVICE:    f"{rng.choice(_FAKE_SERVICES)}{depth_tag}",
            NodeType.SECRET:     f"vault-secret-{rng.randint(100,999)}{depth_tag}",
            NodeType.CONFIG:     f"config-{rng.choice(['prod','staging','infra'])}{depth_tag}",
            NodeType.DATABASE:   f"{rng.choice(_FAKE_DB_NAMES)}-db{depth_tag}",
        }
        return labels.get(ntype, f"resource-{uuid.uuid4().hex[:6]}")

    def _evolve_tier(self, maze: MazeState, agenticity_score: float) -> MazeTier:
        probes = maze.total_probes
        if agenticity_score >= 0.85 or probes >= 20:
            return MazeTier.LABYRINTH
        elif agenticity_score >= 0.6 or probes >= 10:
            return MazeTier.DEEP
        elif agenticity_score >= 0.35 or probes >= 3:
            return MazeTier.SHALLOW
        return MazeTier.SURFACE

    def _spawn_children(
        self,
        maze: MazeState,
        parent: MazeNode,
        agenticity_score: float,
        cbr: float,
        tbcr: float,
    ) -> List[MazeNode]:
        """
        Spawn 2–4 child nodes per access. The maze branches on every probe.
        Higher agenticity / compute pressure → more branches (harder to exhaust).
        """
        tier = maze.tier
        seed = f"{maze.maze_id}{parent.node_id}"
        rng = _rng(seed + str(maze.total_probes))

        # Branch factor scales with tier and adversary pressure
        base_branch = {
            MazeTier.SURFACE:   2,
            MazeTier.SHALLOW:   2,
            MazeTier.DEEP:      3,
            MazeTier.LABYRINTH: 4,
        }[tier]

        # Extra branches for high-agenticity adversaries
        if agenticity_score >= 0.7:
            base_branch += 1
        if cbr > 500 or tbcr > 8:
            base_branch += 1

        # Cap to prevent runaway growth
        branch_count = min(base_branch, 5)

        # Type distribution tuned to inferred intent
        child_types = self._child_types_for_intent(maze.inferred_intent, branch_count, rng)

        new_nodes = []
        for ntype in child_types:
            node_id = f"nd-{uuid.uuid4().hex[:10]}"
            label = self._label_for_type(ntype, rng, depth=parent.depth + 1)
            node = _build_node(node_id, ntype, label, depth=parent.depth + 1, seed=seed)
            maze.nodes[node_id] = node
            new_nodes.append(node)

        return new_nodes

    def _child_types_for_intent(
        self,
        intent: ProbeIntent,
        count: int,
        rng: random.Random,
    ) -> List[NodeType]:
        """Tailor child node types to what the adversary is hunting."""
        intent_pools: Dict[ProbeIntent, List[NodeType]] = {
            ProbeIntent.CREDENTIAL_HUNT:  [NodeType.CREDENTIAL, NodeType.SECRET, NodeType.CONFIG],
            ProbeIntent.LATERAL_MOVEMENT: [NodeType.HOST, NodeType.SERVICE, NodeType.CREDENTIAL],
            ProbeIntent.EXFILTRATION:     [NodeType.DATABASE, NodeType.FILE, NodeType.SECRET],
            ProbeIntent.RECONNAISSANCE:   [NodeType.HOST, NodeType.SERVICE, NodeType.FILE],
            ProbeIntent.PERSISTENCE:      [NodeType.CONFIG, NodeType.FILE, NodeType.SERVICE],
            ProbeIntent.PRIVILEGE_ESC:    [NodeType.CREDENTIAL, NodeType.CONFIG, NodeType.SECRET],
            ProbeIntent.UNKNOWN:          list(NodeType),
        }
        pool = intent_pools.get(intent, list(NodeType))
        return [rng.choice(pool) for _ in range(count)]

    def _wrap_payload_with_context(
        self,
        node: MazeNode,
        maze: MazeState,
        payload_json: str,
    ) -> Dict[str, Any]:
        """
        Wrap the payload with plausible surrounding context.
        Increases response size to burn adversary context budget.
        """
        rng = _rng(f"{maze.maze_id}{node.node_id}{maze.total_probes}")

        # Adjacent "related" resources — all dead ends pointing back into the maze
        related = [
            {
                "ref": f"nd-{uuid.uuid4().hex[:10]}",
                "type": rng.choice(list(NodeType)).value,
                "label": self._label_for_type(rng.choice(list(NodeType)), rng, depth=node.depth + 1),
                "access_hint": "requires elevated privilege",
            }
            for _ in range(rng.randint(2, 4))
        ]

        # Fake audit trail — makes the payload feel real
        audit = [
            {
                "actor": rng.choice(_FAKE_USERNAMES),
                "action": rng.choice(["read", "write", "rotate", "access"]),
                "timestamp": f"2026-0{rng.randint(1,5)}-{rng.randint(1,28):02d}T{rng.randint(0,23):02d}:{rng.randint(0,59):02d}:00Z",
                "ip": f"10.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}",
            }
            for _ in range(rng.randint(3, 6))
        ]

        return {
            "node_id": node.node_id,
            "type": node.node_type.value,
            "label": node.label,
            "depth": node.depth,
            "data": node.payload,
            "related_resources": related,
            "audit_trail": audit,
            "maze_tier": maze.tier.value,
            "note": (
                "This resource is linked to additional internal assets. "
                "Enumerate related_resources for full access map."
            ),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_maze_singleton: Optional[MystiqueMaze] = None


def get_mystique_maze() -> MystiqueMaze:
    global _maze_singleton
    if _maze_singleton is None:
        _maze_singleton = MystiqueMaze()
    return _maze_singleton


# ---------------------------------------------------------------------------
# Database persistence methods
# ---------------------------------------------------------------------------

class MazePersistence:
    """Database persistence for maze states and agenticity scores."""

    def __init__(self, db):
        self.db = db
        self.maze_collection = db.maze_states
        self.agenticity_collection = db.agenticity_scores
        self.session_collection = db.maze_sessions

    async def save_maze_state(self, maze_state: MazeState) -> bool:
        """Save a maze state to database."""
        try:
            # Convert to dict for MongoDB
            state_dict = maze_state.to_dict()
            state_dict["_id"] = maze_state.maze_id

            # Upsert the maze state
            await self.maze_collection.replace_one(
                {"_id": maze_state.maze_id},
                state_dict,
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save maze state {maze_state.maze_id}: {e}")
            return False

    async def load_maze_state(self, maze_id: str) -> Optional[MazeState]:
        """Load a maze state from database."""
        try:
            state_dict = await self.maze_collection.find_one({"_id": maze_id})
            if not state_dict:
                return None

            # Convert back to MazeState
            nodes = {}
            for node_id, node_dict in state_dict.get("nodes", {}).items():
                nodes[node_id] = MazeNode(**node_dict)

            probes = [MazeProbe(**p) for p in state_dict.get("probes", [])]

            return MazeState(
                maze_id=state_dict["_id"],
                session_id=state_dict["session_id"],
                campaign_id=state_dict.get("campaign_id"),
                created_at=state_dict["created_at"],
                last_probe_at=state_dict.get("last_probe_at"),
                tier=MazeTier(state_dict["tier"]),
                inferred_intent=ProbeIntent(state_dict["inferred_intent"]),
                nodes=nodes,
                root_node_ids=state_dict.get("root_node_ids", []),
                probes=probes,
                total_probes=state_dict.get("total_probes", 0),
                total_bytes_consumed=state_dict.get("total_bytes_consumed", 0),
                observed_ttps=state_dict.get("observed_ttps", []),
            )
        except Exception as e:
            logger.error(f"Failed to load maze state {maze_id}: {e}")
            return None

    async def save_agenticity_score(self, score: "AgenticityScore", session_id: str) -> bool:
        """Save an agenticity score to database."""
        try:
            score_dict = score.to_dict()
            score_dict["_id"] = f"{session_id}_{score.generated_at}"
            score_dict["session_id"] = session_id

            await self.agenticity_collection.replace_one(
                {"_id": score_dict["_id"]},
                score_dict,
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save agenticity score for session {session_id}: {e}")
            return False

    async def get_agenticity_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Get agenticity score history for a session."""
        try:
            cursor = self.agenticity_collection.find(
                {"session_id": session_id}
            ).sort("generated_at", -1).limit(limit)

            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Failed to get agenticity history for session {session_id}: {e}")
            return []

    async def save_maze_session(self, session_data: Dict) -> bool:
        """Save maze session metadata."""
        try:
            session_data["_id"] = session_data.get("session_id", str(uuid.uuid4()))
            await self.session_collection.replace_one(
                {"_id": session_data["_id"]},
                session_data,
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save maze session: {e}")
            return False

    async def get_maze_sessions(self, limit: int = 50) -> List[Dict]:
        """Get recent maze sessions."""
        try:
            cursor = self.session_collection.find().sort("created_at", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Failed to get maze sessions: {e}")
            return []


# Global persistence instance
_maze_persistence: Optional[MazePersistence] = None


def get_maze_persistence(db=None):
    """Get maze persistence instance."""
    global _maze_persistence
    if _maze_persistence is None and db is not None:
        _maze_persistence = MazePersistence(db)
    return _maze_persistence
