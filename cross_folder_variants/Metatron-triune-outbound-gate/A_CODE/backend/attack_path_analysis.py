"""
Enterprise Attack Path Analysis Service
========================================
Version: 1.0

Graph-based attack path analysis with crown jewels identification.
Competitive feature parity with XM Cyber, SentinelOne Attack Paths.

Core Capabilities:
- Crown Jewels Asset Classification
- Attack Path Simulation (how attackers reach critical assets)
- Choke Point Identification (remediation priorities)
- Risk Scoring per Attack Path
- Lateral Movement Visualization
- Privilege Escalation Chain Detection
- Blast Radius Analysis
- Remediation Impact Scoring

MITRE ATT&CK Integration:
- T1078: Valid Accounts
- T1021: Remote Services
- T1210: Exploitation of Remote Services
- T1134: Access Token Manipulation
- T1548: Abuse Elevation Control Mechanism

Architecture:
- Graph-based asset relationships
- Dijkstra's algorithm for shortest attack paths
- Monte Carlo simulation for attack probability
- Network topology inference from telemetry
"""
import os
import re
import json
import logging
import uuid
import heapq
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Set, NamedTuple
from dataclasses import dataclass, asdict, field
from collections import defaultdict
from enum import Enum, auto
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class AssetCriticality(Enum):
    """Asset criticality levels for crown jewels classification"""
    CROWN_JEWEL = "crown_jewel"       # 100 - Most critical assets
    CRITICAL = "critical"              # 90  - Very high value assets
    HIGH = "high"                      # 70  - Important assets
    MEDIUM = "medium"                  # 50  - Standard assets
    LOW = "low"                        # 30  - Low value assets
    UNKNOWN = "unknown"                # 10  - Unclassified

    def to_score(self) -> int:
        mapping = {
            "crown_jewel": 100,
            "critical": 90,
            "high": 70,
            "medium": 50,
            "low": 30,
            "unknown": 10
        }
        return mapping.get(self.value, 10)


class AssetType(Enum):
    """Asset types in the environment"""
    DOMAIN_CONTROLLER = "domain_controller"
    DATABASE_SERVER = "database_server"
    FILE_SERVER = "file_server"
    WEB_SERVER = "web_server"
    APPLICATION_SERVER = "application_server"
    WORKSTATION = "workstation"
    PRIVILEGED_WORKSTATION = "privileged_workstation"
    VPN_GATEWAY = "vpn_gateway"
    FIREWALL = "firewall"
    EMAIL_SERVER = "email_server"
    BACKUP_SERVER = "backup_server"
    CICD_SERVER = "cicd_server"
    SECRET_VAULT = "secret_vault"
    CLOUD_CONTROLLER = "cloud_controller"
    CONTAINER_ORCHESTRATOR = "container_orchestrator"
    NETWORK_DEVICE = "network_device"
    IOT_DEVICE = "iot_device"
    USER_ACCOUNT = "user_account"
    SERVICE_ACCOUNT = "service_account"
    ADMIN_ACCOUNT = "admin_account"
    UNKNOWN = "unknown"


class AttackTechnique(Enum):
    """Attack techniques for edges"""
    CREDENTIAL_THEFT = "credential_theft"
    PASSWORD_SPRAY = "password_spray"
    KERBEROASTING = "kerberoasting"
    PASS_THE_HASH = "pass_the_hash"
    PASS_THE_TICKET = "pass_the_ticket"
    GOLDEN_TICKET = "golden_ticket"
    SILVER_TICKET = "silver_ticket"
    DCSYNC = "dcsync"
    ASREPROASTING = "asreproasting"
    LDAP_ENUMERATION = "ldap_enumeration"
    SMB_RELAY = "smb_relay"
    RDP_HIJACKING = "rdp_hijacking"
    PSEXEC = "psexec"
    WMI_LATERAL = "wmi_lateral"
    SSH_LATERAL = "ssh_lateral"
    LOCAL_ADMIN_ABUSE = "local_admin_abuse"
    GROUP_POLICY_ABUSE = "group_policy_abuse"
    DELEGATION_ABUSE = "delegation_abuse"
    ACL_ABUSE = "acl_abuse"
    CERTIFICATE_ABUSE = "certificate_abuse"
    SQL_INJECTION = "sql_injection"
    RCE_EXPLOIT = "rce_exploit"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DEFAULT_CREDENTIALS = "default_credentials"


# MITRE ATT&CK technique mappings
TECHNIQUE_TO_MITRE = {
    AttackTechnique.CREDENTIAL_THEFT: ["T1003", "T1555"],
    AttackTechnique.PASSWORD_SPRAY: ["T1110.003"],
    AttackTechnique.KERBEROASTING: ["T1558.003"],
    AttackTechnique.PASS_THE_HASH: ["T1550.002"],
    AttackTechnique.PASS_THE_TICKET: ["T1550.003"],
    AttackTechnique.GOLDEN_TICKET: ["T1558.001"],
    AttackTechnique.SILVER_TICKET: ["T1558.002"],
    AttackTechnique.DCSYNC: ["T1003.006"],
    AttackTechnique.ASREPROASTING: ["T1558.004"],
    AttackTechnique.LDAP_ENUMERATION: ["T1087.002"],
    AttackTechnique.SMB_RELAY: ["T1557.001"],
    AttackTechnique.RDP_HIJACKING: ["T1563.002"],
    AttackTechnique.PSEXEC: ["T1569.002"],
    AttackTechnique.WMI_LATERAL: ["T1047"],
    AttackTechnique.SSH_LATERAL: ["T1021.004"],
    AttackTechnique.LOCAL_ADMIN_ABUSE: ["T1078.003"],
    AttackTechnique.GROUP_POLICY_ABUSE: ["T1484.001"],
    AttackTechnique.DELEGATION_ABUSE: ["T1134.001"],
    AttackTechnique.ACL_ABUSE: ["T1222"],
    AttackTechnique.CERTIFICATE_ABUSE: ["T1649"],
    AttackTechnique.SQL_INJECTION: ["T1190"],
    AttackTechnique.RCE_EXPLOIT: ["T1203"],
    AttackTechnique.PRIVILEGE_ESCALATION: ["T1068"],
    AttackTechnique.DEFAULT_CREDENTIALS: ["T1078.001"],
}


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class Asset:
    """Represents an asset in the environment"""
    asset_id: str
    name: str
    asset_type: AssetType
    criticality: AssetCriticality
    hostname: Optional[str] = None
    ip_addresses: List[str] = field(default_factory=list)
    os_type: Optional[str] = None
    owner: Optional[str] = None
    department: Optional[str] = None
    data_classification: Optional[str] = None  # PII, PHI, Financial, etc.
    tags: List[str] = field(default_factory=list)
    vulnerabilities: List[Dict] = field(default_factory=list)
    exposed_services: List[Dict] = field(default_factory=list)
    last_seen: Optional[str] = None
    risk_score: float = 0.0
    is_compromised: bool = False
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            "asset_type": self.asset_type.value,
            "criticality": self.criticality.value,
            "criticality_score": self.criticality.to_score()
        }


@dataclass
class AttackEdge:
    """Represents an attack path edge (relationship between assets)"""
    edge_id: str
    source_asset_id: str
    target_asset_id: str
    technique: AttackTechnique
    probability: float  # 0.0 - 1.0 likelihood of successful exploitation
    complexity: str     # low, medium, high
    requires_user_interaction: bool
    detection_difficulty: str  # easy, medium, hard
    mitre_techniques: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    description: str = ""
    evidence: List[Dict] = field(default_factory=list)
    risk_reduction_actions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            "technique": self.technique.value
        }
    
    @property
    def weight(self) -> float:
        """Calculate edge weight for shortest path (inverse of probability)"""
        # Lower weight = easier attack path
        return 1.0 - (self.probability * 0.8)  # Scale to 0.2-1.0 range


@dataclass
class AttackPath:
    """Represents a complete attack path from entry to crown jewel"""
    path_id: str
    entry_point_id: str
    target_id: str  # Crown jewel
    asset_chain: List[str]  # List of asset IDs in path
    edge_chain: List[str]   # List of edge IDs in path
    techniques_used: List[AttackTechnique]
    total_probability: float  # Combined probability
    hop_count: int
    estimated_time_hours: float
    risk_score: float
    mitre_techniques: List[str] = field(default_factory=list)
    choke_points: List[str] = field(default_factory=list)  # Best places to break the path
    remediation_recommendations: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            "techniques_used": [t.value for t in self.techniques_used]
        }


@dataclass
class ChokePoint:
    """A critical point where multiple attack paths converge"""
    asset_id: str
    paths_through: int
    criticality_protected: float  # Sum of crown jewel criticality behind this point
    remediation_impact: float     # How much risk is reduced by securing this
    recommended_actions: List[str] = field(default_factory=list)


@dataclass
class CrownJewelDefinition:
    """Definition for auto-classifying crown jewels"""
    rule_id: str
    name: str
    description: str
    conditions: Dict[str, Any]  # Matching conditions
    criticality: AssetCriticality
    auto_tag: List[str] = field(default_factory=list)


# Default crown jewel detection rules
DEFAULT_CROWN_JEWEL_RULES = [
    CrownJewelDefinition(
        rule_id="cj-domain-controller",
        name="Domain Controller",
        description="Active Directory Domain Controllers",
        conditions={"asset_type": "domain_controller"},
        criticality=AssetCriticality.CROWN_JEWEL,
        auto_tag=["active-directory", "identity-infrastructure"]
    ),
    CrownJewelDefinition(
        rule_id="cj-database-pii",
        name="Database with PII/PHI",
        description="Databases containing sensitive personal data",
        conditions={"asset_type": "database_server", "data_classification": ["PII", "PHI"]},
        criticality=AssetCriticality.CROWN_JEWEL,
        auto_tag=["sensitive-data", "compliance-critical"]
    ),
    CrownJewelDefinition(
        rule_id="cj-secrets-vault",
        name="Secrets Management",
        description="HashiCorp Vault, CyberArk, etc.",
        conditions={"asset_type": "secret_vault"},
        criticality=AssetCriticality.CROWN_JEWEL,
        auto_tag=["secrets", "credentials"]
    ),
    CrownJewelDefinition(
        rule_id="cj-backup-server",
        name="Backup Infrastructure",
        description="Backup servers (ransomware target)",
        conditions={"asset_type": "backup_server"},
        criticality=AssetCriticality.CRITICAL,
        auto_tag=["ransomware-target", "recovery-critical"]
    ),
    CrownJewelDefinition(
        rule_id="cj-cicd",
        name="CI/CD Pipeline",
        description="Build servers and artifact repositories",
        conditions={"asset_type": "cicd_server"},
        criticality=AssetCriticality.CRITICAL,
        auto_tag=["supply-chain", "code-integrity"]
    ),
    CrownJewelDefinition(
        rule_id="cj-cloud-controller",
        name="Cloud Management Plane",
        description="Azure AD Connect, AWS SSO, GCP Organization",
        conditions={"asset_type": "cloud_controller"},
        criticality=AssetCriticality.CROWN_JEWEL,
        auto_tag=["cloud-infrastructure", "identity"]
    ),
    CrownJewelDefinition(
        rule_id="cj-container-orchestrator",
        name="Container Orchestrator",
        description="Kubernetes control plane",
        conditions={"asset_type": "container_orchestrator"},
        criticality=AssetCriticality.CRITICAL,
        auto_tag=["kubernetes", "container-infrastructure"]
    ),
    CrownJewelDefinition(
        rule_id="cj-email-server",
        name="Email Infrastructure",
        description="Exchange servers, email gateways",
        conditions={"asset_type": "email_server"},
        criticality=AssetCriticality.HIGH,
        auto_tag=["email", "communication"]
    ),
]


# =============================================================================
# ATTACK PATH ANALYZER
# =============================================================================

class AttackPathAnalyzer:
    """
    Enterprise Attack Path Analysis Engine
    
    Analyzes the environment topology to identify:
    1. Crown jewels (critical assets)
    2. Attack paths from entry points to crown jewels
    3. Choke points for remediation prioritization
    4. Risk scores per path and asset
    
    Uses graph algorithms:
    - Dijkstra's algorithm for shortest attack paths
    - BFS for all possible paths
    - Centrality analysis for choke point detection
    """
    
    def __init__(self):
        self.assets: Dict[str, Asset] = {}
        self.edges: Dict[str, AttackEdge] = {}
        self.crown_jewel_rules: List[CrownJewelDefinition] = DEFAULT_CROWN_JEWEL_RULES.copy()
        
        # Graph representations
        self.adjacency_list: Dict[str, List[Tuple[str, str]]] = defaultdict(list)  # asset_id -> [(target_id, edge_id)]
        self.reverse_adjacency: Dict[str, List[Tuple[str, str]]] = defaultdict(list)  # For backtracking
        
        # Analysis results cache
        self._attack_paths: List[AttackPath] = []
        self._choke_points: List[ChokePoint] = []
        self._analysis_timestamp: Optional[str] = None
    
    # =========================================================================
    # Asset Management
    # =========================================================================
    
    def add_asset(self, asset: Asset) -> str:
        """Add an asset to the graph"""
        # Auto-classify crown jewels
        self._classify_asset(asset)
        self.assets[asset.asset_id] = asset
        logger.debug(f"Added asset: {asset.name} ({asset.asset_type.value}) - {asset.criticality.value}")
        return asset.asset_id
    
    def add_assets_from_inventory(self, inventory: List[Dict]) -> int:
        """Bulk add assets from inventory data"""
        count = 0
        for item in inventory:
            try:
                asset = Asset(
                    asset_id=item.get("asset_id", str(uuid.uuid4())),
                    name=item.get("name", item.get("hostname", "Unknown")),
                    asset_type=AssetType(item.get("asset_type", "unknown")),
                    criticality=AssetCriticality(item.get("criticality", "unknown")),
                    hostname=item.get("hostname"),
                    ip_addresses=item.get("ip_addresses", []),
                    os_type=item.get("os_type"),
                    owner=item.get("owner"),
                    department=item.get("department"),
                    data_classification=item.get("data_classification"),
                    tags=item.get("tags", []),
                    vulnerabilities=item.get("vulnerabilities", []),
                    exposed_services=item.get("exposed_services", []),
                    metadata=item.get("metadata", {})
                )
                self.add_asset(asset)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to add asset {item.get('name')}: {e}")
        
        return count
    
    def _classify_asset(self, asset: Asset):
        """Auto-classify asset criticality based on rules"""
        for rule in self.crown_jewel_rules:
            if self._matches_rule(asset, rule):
                if asset.criticality.to_score() < rule.criticality.to_score():
                    asset.criticality = rule.criticality
                    asset.tags.extend(rule.auto_tag)
                    asset.tags = list(set(asset.tags))  # Dedupe
                    logger.info(f"Auto-classified {asset.name} as {rule.criticality.value}: {rule.name}")
                break
    
    def _matches_rule(self, asset: Asset, rule: CrownJewelDefinition) -> bool:
        """Check if asset matches a crown jewel rule"""
        conditions = rule.conditions
        
        # Check asset_type
        if "asset_type" in conditions:
            if asset.asset_type.value != conditions["asset_type"]:
                return False
        
        # Check data_classification
        if "data_classification" in conditions:
            required = conditions["data_classification"]
            if isinstance(required, list):
                if asset.data_classification not in required:
                    return False
            elif asset.data_classification != required:
                return False
        
        # Check tags
        if "tags" in conditions:
            required_tags = conditions["tags"]
            if not any(tag in asset.tags for tag in required_tags):
                return False
        
        return True
    
    def get_crown_jewels(self) -> List[Asset]:
        """Get all assets classified as crown jewels"""
        return [
            a for a in self.assets.values()
            if a.criticality in [AssetCriticality.CROWN_JEWEL, AssetCriticality.CRITICAL]
        ]
    
    def get_entry_points(self) -> List[Asset]:
        """Get potential entry points (internet-facing, workstations, etc.)"""
        entry_types = {
            AssetType.WORKSTATION,
            AssetType.WEB_SERVER,
            AssetType.VPN_GATEWAY,
            AssetType.EMAIL_SERVER,
        }
        
        entry_points = []
        for asset in self.assets.values():
            # Direct entry point types
            if asset.asset_type in entry_types:
                entry_points.append(asset)
                continue
            
            # Internet-facing services
            if any("external" in str(s).lower() or "public" in str(s).lower() 
                   for s in asset.exposed_services):
                entry_points.append(asset)
                continue
            
            # Has external vulnerabilities
            if any(v.get("exploitable_external") for v in asset.vulnerabilities):
                entry_points.append(asset)
        
        return entry_points
    
    # =========================================================================
    # Edge Management
    # =========================================================================
    
    def add_edge(self, edge: AttackEdge) -> str:
        """Add an attack relationship edge"""
        # Add MITRE mappings if not present
        if not edge.mitre_techniques:
            edge.mitre_techniques = TECHNIQUE_TO_MITRE.get(edge.technique, [])
        
        self.edges[edge.edge_id] = edge
        self.adjacency_list[edge.source_asset_id].append((edge.target_asset_id, edge.edge_id))
        self.reverse_adjacency[edge.target_asset_id].append((edge.source_asset_id, edge.edge_id))
        
        return edge.edge_id
    
    def infer_edges_from_relationships(self, relationships: List[Dict]) -> int:
        """
        Infer attack edges from known relationships.
        Examples:
        - Admin of -> Can PSExec/WMI to
        - Same subnet -> SMB relay possible
        - Has credentials for -> Can authenticate to
        """
        count = 0
        
        for rel in relationships:
            edge = self._relationship_to_edge(rel)
            if edge:
                self.add_edge(edge)
                count += 1
        
        return count
    
    def _relationship_to_edge(self, rel: Dict) -> Optional[AttackEdge]:
        """Convert a relationship to an attack edge"""
        rel_type = rel.get("type", "").lower()
        source = rel.get("source_id")
        target = rel.get("target_id")
        
        if not source or not target:
            return None
        
        # Map relationship types to attack techniques
        technique_mapping = {
            "admin_of": (AttackTechnique.PSEXEC, 0.9),
            "local_admin": (AttackTechnique.LOCAL_ADMIN_ABUSE, 0.85),
            "has_session": (AttackTechnique.CREDENTIAL_THEFT, 0.7),
            "member_of_admins": (AttackTechnique.PRIVILEGE_ESCALATION, 0.8),
            "can_rdp": (AttackTechnique.RDP_HIJACKING, 0.75),
            "can_psexec": (AttackTechnique.PSEXEC, 0.85),
            "can_wmi": (AttackTechnique.WMI_LATERAL, 0.8),
            "can_ssh": (AttackTechnique.SSH_LATERAL, 0.8),
            "can_dcsync": (AttackTechnique.DCSYNC, 0.95),
            "constrained_delegation": (AttackTechnique.DELEGATION_ABUSE, 0.8),
            "unconstrained_delegation": (AttackTechnique.DELEGATION_ABUSE, 0.9),
            "write_dacl": (AttackTechnique.ACL_ABUSE, 0.85),
            "generic_all": (AttackTechnique.ACL_ABUSE, 0.9),
            "owns": (AttackTechnique.ACL_ABUSE, 0.95),
            "gpo_link": (AttackTechnique.GROUP_POLICY_ABUSE, 0.7),
            "same_password": (AttackTechnique.PASS_THE_HASH, 0.9),
            "kerberoastable": (AttackTechnique.KERBEROASTING, 0.8),
            "asreproastable": (AttackTechnique.ASREPROASTING, 0.75),
            "sql_linked": (AttackTechnique.SQL_INJECTION, 0.7),
        }
        
        if rel_type in technique_mapping:
            technique, probability = technique_mapping[rel_type]
            
            return AttackEdge(
                edge_id=f"edge-{uuid.uuid4().hex[:8]}",
                source_asset_id=source,
                target_asset_id=target,
                technique=technique,
                probability=probability,
                complexity="medium",
                requires_user_interaction=False,
                detection_difficulty="medium",
                description=f"Attack via {rel_type}",
                risk_reduction_actions=[
                    f"Remove {rel_type} relationship",
                    "Implement least privilege",
                    "Enable detection for {technique.value}"
                ]
            )
        
        return None
    
    # =========================================================================
    # Attack Path Analysis
    # =========================================================================
    
    def analyze(self) -> Dict[str, Any]:
        """
        Perform full attack path analysis
        
        Returns comprehensive analysis including:
        - All attack paths to crown jewels
        - Choke points
        - Risk scores
        - Remediation recommendations
        """
        self._analysis_timestamp = datetime.now(timezone.utc).isoformat()
        
        # Find all crown jewels and entry points
        crown_jewels = self.get_crown_jewels()
        entry_points = self.get_entry_points()
        
        if not crown_jewels:
            logger.warning("No crown jewels identified - using CRITICAL assets")
            crown_jewels = [a for a in self.assets.values() 
                          if a.criticality == AssetCriticality.CRITICAL]
        
        if not entry_points:
            logger.warning("No entry points identified - using workstations")
            entry_points = [a for a in self.assets.values()
                          if a.asset_type == AssetType.WORKSTATION]
        
        # Find attack paths
        self._attack_paths = []
        for entry in entry_points:
            for crown_jewel in crown_jewels:
                paths = self._find_all_paths(entry.asset_id, crown_jewel.asset_id, max_depth=10)
                self._attack_paths.extend(paths)
        
        # Sort by risk (highest first)
        self._attack_paths.sort(key=lambda p: p.risk_score, reverse=True)
        
        # Identify choke points
        self._choke_points = self._identify_choke_points()
        
        # Calculate overall risk metrics
        risk_metrics = self._calculate_risk_metrics()
        
        return {
            "analysis_id": str(uuid.uuid4()),
            "timestamp": self._analysis_timestamp,
            "summary": {
                "total_assets": len(self.assets),
                "crown_jewels": len(crown_jewels),
                "entry_points": len(entry_points),
                "total_edges": len(self.edges),
                "attack_paths_found": len(self._attack_paths),
                "choke_points": len(self._choke_points),
                "overall_risk_score": risk_metrics["overall_risk"],
            },
            "crown_jewels": [cj.to_dict() for cj in crown_jewels],
            "entry_points": [ep.to_dict() for ep in entry_points],
            "attack_paths": [p.to_dict() for p in self._attack_paths[:50]],  # Top 50
            "choke_points": [asdict(cp) for cp in self._choke_points[:20]],  # Top 20
            "risk_metrics": risk_metrics,
            "remediation_priorities": self._generate_remediation_priorities(),
            "mitre_coverage": self._get_mitre_coverage(),
        }
    
    def _find_all_paths(
        self, 
        start_id: str, 
        end_id: str, 
        max_depth: int = 10
    ) -> List[AttackPath]:
        """Find all attack paths from start to end using DFS with memoization"""
        paths = []
        visited = set()
        
        def dfs(current: str, path_assets: List[str], path_edges: List[str], 
                techniques: List[AttackTechnique], current_prob: float, depth: int):
            if depth > max_depth:
                return
            
            if current == end_id:
                # Found a path
                path_id = hashlib.md5(":".join(path_assets).encode()).hexdigest()[:12]
                
                # Calculate risk score
                target_crit = self.assets.get(end_id, Asset(
                    asset_id="", name="", asset_type=AssetType.UNKNOWN,
                    criticality=AssetCriticality.UNKNOWN
                )).criticality.to_score()
                
                risk_score = current_prob * target_crit * (1.0 / (depth + 1))
                
                # Identify choke points (nodes that appear in multiple paths)
                choke_points = []
                for i, asset_id in enumerate(path_assets[1:-1], 1):
                    # Check in-degree and out-degree
                    in_degree = len(self.reverse_adjacency[asset_id])
                    out_degree = len(self.adjacency_list[asset_id])
                    if in_degree >= 2 or out_degree >= 2:
                        choke_points.append(asset_id)
                
                # Collect MITRE techniques
                mitre = []
                for t in techniques:
                    mitre.extend(TECHNIQUE_TO_MITRE.get(t, []))
                
                attack_path = AttackPath(
                    path_id=path_id,
                    entry_point_id=start_id,
                    target_id=end_id,
                    asset_chain=path_assets.copy(),
                    edge_chain=path_edges.copy(),
                    techniques_used=techniques.copy(),
                    total_probability=current_prob,
                    hop_count=depth,
                    estimated_time_hours=depth * 2.0,  # Rough estimate
                    risk_score=risk_score,
                    mitre_techniques=list(set(mitre)),
                    choke_points=choke_points,
                    remediation_recommendations=self._generate_path_remediation(
                        path_assets, path_edges
                    )
                )
                paths.append(attack_path)
                return
            
            visited.add(current)
            
            # Explore neighbors
            for neighbor_id, edge_id in self.adjacency_list[current]:
                if neighbor_id not in visited:
                    edge = self.edges.get(edge_id)
                    if edge:
                        new_prob = current_prob * edge.probability
                        if new_prob > 0.01:  # Prune very unlikely paths
                            dfs(
                                neighbor_id,
                                path_assets + [neighbor_id],
                                path_edges + [edge_id],
                                techniques + [edge.technique],
                                new_prob,
                                depth + 1
                            )
            
            visited.remove(current)
        
        # Start DFS
        if start_id in self.assets:
            dfs(start_id, [start_id], [], [], 1.0, 0)
        
        return paths
    
    def find_shortest_path(self, start_id: str, end_id: str) -> Optional[AttackPath]:
        """
        Find shortest (most likely) attack path using Dijkstra's algorithm
        Weight = inverse of probability
        """
        if start_id not in self.assets or end_id not in self.assets:
            return None
        
        # Priority queue: (distance, node_id, path_assets, path_edges, techniques)
        heap = [(0, start_id, [start_id], [], [])]
        distances = {start_id: 0}
        
        while heap:
            dist, current, path_assets, path_edges, techniques = heapq.heappop(heap)
            
            if current == end_id:
                # Found shortest path
                total_prob = 1.0
                for edge_id in path_edges:
                    edge = self.edges.get(edge_id)
                    if edge:
                        total_prob *= edge.probability
                
                mitre = []
                for t in techniques:
                    mitre.extend(TECHNIQUE_TO_MITRE.get(t, []))
                
                return AttackPath(
                    path_id=f"shortest-{uuid.uuid4().hex[:8]}",
                    entry_point_id=start_id,
                    target_id=end_id,
                    asset_chain=path_assets,
                    edge_chain=path_edges,
                    techniques_used=techniques,
                    total_probability=total_prob,
                    hop_count=len(path_assets) - 1,
                    estimated_time_hours=(len(path_assets) - 1) * 2.0,
                    risk_score=total_prob * self.assets[end_id].criticality.to_score(),
                    mitre_techniques=list(set(mitre)),
                    choke_points=[],
                    remediation_recommendations=self._generate_path_remediation(
                        path_assets, path_edges
                    )
                )
            
            if dist > distances.get(current, float('inf')):
                continue
            
            for neighbor_id, edge_id in self.adjacency_list[current]:
                edge = self.edges.get(edge_id)
                if edge:
                    new_dist = dist + edge.weight
                    if new_dist < distances.get(neighbor_id, float('inf')):
                        distances[neighbor_id] = new_dist
                        heapq.heappush(heap, (
                            new_dist,
                            neighbor_id,
                            path_assets + [neighbor_id],
                            path_edges + [edge_id],
                            techniques + [edge.technique]
                        ))
        
        return None
    
    def _generate_path_remediation(
        self, 
        path_assets: List[str], 
        path_edges: List[str]
    ) -> List[Dict]:
        """Generate remediation recommendations for a specific path"""
        recommendations = []
        
        for edge_id in path_edges:
            edge = self.edges.get(edge_id)
            if edge:
                # Add edge-specific remediations
                for action in edge.risk_reduction_actions:
                    recommendations.append({
                        "action": action,
                        "target_edge": edge_id,
                        "technique_blocked": edge.technique.value,
                        "impact": edge.probability,
                        "priority": "high" if edge.probability > 0.8 else "medium"
                    })
        
        return recommendations[:10]  # Top 10
    
    # =========================================================================
    # Choke Point Analysis
    # =========================================================================
    
    def _identify_choke_points(self) -> List[ChokePoint]:
        """
        Identify choke points - assets that appear in multiple attack paths
        Securing these provides maximum risk reduction
        """
        # Count path occurrences per asset
        asset_path_count: Dict[str, int] = defaultdict(int)
        asset_criticality_protected: Dict[str, float] = defaultdict(float)
        
        for path in self._attack_paths:
            target_crit = self.assets.get(
                path.target_id, 
                Asset("", "", AssetType.UNKNOWN, AssetCriticality.UNKNOWN)
            ).criticality.to_score()
            
            for asset_id in path.asset_chain[1:-1]:  # Exclude entry and target
                asset_path_count[asset_id] += 1
                asset_criticality_protected[asset_id] += target_crit
        
        # Build choke points
        choke_points = []
        for asset_id, count in asset_path_count.items():
            if count >= 2:  # Present in multiple paths
                asset = self.assets.get(asset_id)
                
                # Calculate remediation impact
                remediation_impact = (
                    count * 10 +  # Paths blocked
                    asset_criticality_protected[asset_id] * 0.1  # Criticality protected
                )
                
                # Generate recommended actions
                actions = []
                # Check what techniques pass through here
                for path in self._attack_paths:
                    if asset_id in path.asset_chain:
                        idx = path.asset_chain.index(asset_id)
                        if idx > 0 and idx < len(path.edge_chain):
                            edge_id = path.edge_chain[idx - 1]
                            edge = self.edges.get(edge_id)
                            if edge:
                                actions.extend(edge.risk_reduction_actions)
                
                choke_points.append(ChokePoint(
                    asset_id=asset_id,
                    paths_through=count,
                    criticality_protected=asset_criticality_protected[asset_id],
                    remediation_impact=remediation_impact,
                    recommended_actions=list(set(actions))[:5]
                ))
        
        # Sort by remediation impact
        choke_points.sort(key=lambda cp: cp.remediation_impact, reverse=True)
        return choke_points
    
    # =========================================================================
    # Risk Metrics
    # =========================================================================
    
    def _calculate_risk_metrics(self) -> Dict[str, Any]:
        """Calculate overall risk metrics"""
        if not self._attack_paths:
            return {
                "overall_risk": 0,
                "max_path_probability": 0,
                "avg_path_length": 0,
                "shortest_path_hops": 0,
                "crown_jewels_at_risk": 0,
                "critical_techniques": []
            }
        
        # Aggregate metrics
        max_prob = max(p.total_probability for p in self._attack_paths)
        avg_length = sum(p.hop_count for p in self._attack_paths) / len(self._attack_paths)
        shortest = min(p.hop_count for p in self._attack_paths) if self._attack_paths else 0
        
        # Crown jewels reachable
        reachable_cj = set(p.target_id for p in self._attack_paths)
        
        # Most used techniques
        technique_counts: Dict[str, int] = defaultdict(int)
        for path in self._attack_paths:
            for tech in path.techniques_used:
                technique_counts[tech.value] += 1
        critical_techniques = sorted(
            technique_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        # Overall risk score (0-100)
        overall_risk = min(100, int(
            max_prob * 30 +
            (1.0 / (avg_length + 1)) * 30 +
            len(reachable_cj) * 10 +
            len(self._attack_paths) * 0.5
        ))
        
        return {
            "overall_risk": overall_risk,
            "max_path_probability": round(max_prob, 3),
            "avg_path_length": round(avg_length, 1),
            "shortest_path_hops": shortest,
            "crown_jewels_at_risk": len(reachable_cj),
            "total_attack_paths": len(self._attack_paths),
            "critical_techniques": [{"technique": k, "count": v} for k, v in critical_techniques],
            "risk_level": self._risk_level(overall_risk)
        }
    
    def _risk_level(self, score: int) -> str:
        if score >= 80:
            return "CRITICAL"
        elif score >= 60:
            return "HIGH"
        elif score >= 40:
            return "MEDIUM"
        elif score >= 20:
            return "LOW"
        return "MINIMAL"
    
    # =========================================================================
    # Remediation & Reporting
    # =========================================================================
    
    def _generate_remediation_priorities(self) -> List[Dict]:
        """Generate prioritized remediation actions"""
        priorities = []
        
        # 1. Choke point remediations (highest impact)
        for cp in self._choke_points[:5]:
            asset = self.assets.get(cp.asset_id)
            priorities.append({
                "priority": 1,
                "type": "choke_point",
                "asset_id": cp.asset_id,
                "asset_name": asset.name if asset else cp.asset_id,
                "paths_blocked": cp.paths_through,
                "impact_score": cp.remediation_impact,
                "actions": cp.recommended_actions
            })
        
        # 2. High-probability edges
        high_prob_edges = [
            e for e in self.edges.values() 
            if e.probability > 0.85
        ]
        for edge in high_prob_edges[:5]:
            priorities.append({
                "priority": 2,
                "type": "high_probability_edge",
                "edge_id": edge.edge_id,
                "technique": edge.technique.value,
                "probability": edge.probability,
                "source": edge.source_asset_id,
                "target": edge.target_asset_id,
                "actions": edge.risk_reduction_actions
            })
        
        # 3. Crown jewel direct access
        for cj in self.get_crown_jewels():
            direct_edges = self.reverse_adjacency.get(cj.asset_id, [])
            if direct_edges:
                priorities.append({
                    "priority": 3,
                    "type": "direct_crown_jewel_access",
                    "crown_jewel": cj.name,
                    "direct_access_count": len(direct_edges),
                    "actions": [
                        "Implement network segmentation",
                        "Add MFA for all access",
                        "Enable enhanced monitoring",
                        "Review access permissions"
                    ]
                })
        
        return priorities
    
    def _get_mitre_coverage(self) -> Dict[str, Any]:
        """Get MITRE ATT&CK technique coverage analysis"""
        all_techniques = set()
        technique_counts: Dict[str, int] = defaultdict(int)
        
        for path in self._attack_paths:
            for mitre_id in path.mitre_techniques:
                all_techniques.add(mitre_id)
                technique_counts[mitre_id] += 1
        
        # Top techniques
        top_techniques = sorted(
            technique_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return {
            "unique_techniques": len(all_techniques),
            "technique_list": list(all_techniques),
            "top_techniques": [
                {"technique_id": k, "occurrences": v}
                for k, v in top_techniques
            ],
            "tactic_coverage": self._get_tactic_coverage(all_techniques)
        }
    
    def _get_tactic_coverage(self, techniques: Set[str]) -> Dict[str, List[str]]:
        """Map techniques to MITRE tactics"""
        tactic_mapping = {
            "T1003": "credential_access",
            "T1555": "credential_access",
            "T1110": "credential_access",
            "T1558": "credential_access",
            "T1550": "lateral_movement",
            "T1021": "lateral_movement",
            "T1047": "execution",
            "T1569": "execution",
            "T1563": "lateral_movement",
            "T1078": "privilege_escalation",
            "T1087": "discovery",
            "T1557": "collection",
            "T1134": "privilege_escalation",
            "T1068": "privilege_escalation",
            "T1484": "privilege_escalation",
            "T1222": "defense_evasion",
            "T1649": "credential_access",
            "T1190": "initial_access",
            "T1203": "execution",
        }
        
        tactics: Dict[str, List[str]] = defaultdict(list)
        for tech in techniques:
            base_tech = tech.split(".")[0] if "." in tech else tech
            tactic = tactic_mapping.get(base_tech, "unknown")
            tactics[tactic].append(tech)
        
        return dict(tactics)
    
    # =========================================================================
    # Blast Radius Analysis
    # =========================================================================
    
    def calculate_blast_radius(self, compromised_asset_id: str) -> Dict[str, Any]:
        """
        Calculate the blast radius if a specific asset is compromised.
        Shows all assets reachable from the compromised point.
        """
        if compromised_asset_id not in self.assets:
            return {"error": "Asset not found"}
        
        # BFS to find all reachable assets
        reachable = set()
        crown_jewels_reachable = []
        queue = [(compromised_asset_id, 0)]
        visited = {compromised_asset_id}
        max_depth = 0
        
        while queue:
            current, depth = queue.pop(0)
            if depth > max_depth:
                max_depth = depth
            
            for neighbor_id, edge_id in self.adjacency_list[current]:
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    reachable.add(neighbor_id)
                    queue.append((neighbor_id, depth + 1))
                    
                    # Check if crown jewel
                    neighbor = self.assets.get(neighbor_id)
                    if neighbor and neighbor.criticality in [
                        AssetCriticality.CROWN_JEWEL, 
                        AssetCriticality.CRITICAL
                    ]:
                        crown_jewels_reachable.append({
                            "asset_id": neighbor_id,
                            "name": neighbor.name,
                            "hops_away": depth + 1
                        })
        
        # Calculate total criticality at risk
        total_criticality = sum(
            self.assets.get(aid, Asset("", "", AssetType.UNKNOWN, AssetCriticality.UNKNOWN))
            .criticality.to_score()
            for aid in reachable
        )
        
        return {
            "compromised_asset": compromised_asset_id,
            "total_reachable_assets": len(reachable),
            "max_depth": max_depth,
            "crown_jewels_at_risk": len(crown_jewels_reachable),
            "crown_jewels_details": crown_jewels_reachable,
            "total_criticality_score": total_criticality,
            "reachable_assets": list(reachable)[:100],  # Limit for response size
            "blast_radius_level": self._blast_radius_level(
                len(reachable), len(crown_jewels_reachable)
            )
        }
    
    def _blast_radius_level(self, reachable: int, crown_jewels: int) -> str:
        if crown_jewels >= 3 or reachable >= 50:
            return "CATASTROPHIC"
        elif crown_jewels >= 1 or reachable >= 20:
            return "SEVERE"
        elif reachable >= 10:
            return "SIGNIFICANT"
        elif reachable >= 5:
            return "MODERATE"
        return "LIMITED"
    
    # =========================================================================
    # Serialization
    # =========================================================================
    
    def export_graph(self) -> Dict[str, Any]:
        """Export full graph for visualization"""
        return {
            "nodes": [a.to_dict() for a in self.assets.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "crown_jewels": [cj.asset_id for cj in self.get_crown_jewels()],
            "entry_points": [ep.asset_id for ep in self.get_entry_points()],
            "metadata": {
                "total_nodes": len(self.assets),
                "total_edges": len(self.edges),
                "analysis_timestamp": self._analysis_timestamp
            }
        }
    
    def to_cytoscape_format(self) -> Dict[str, Any]:
        """Export graph in Cytoscape.js compatible format for frontend visualization"""
        elements = []
        
        # Add nodes
        for asset in self.assets.values():
            elements.append({
                "data": {
                    "id": asset.asset_id,
                    "label": asset.name,
                    "type": asset.asset_type.value,
                    "criticality": asset.criticality.value,
                    "criticality_score": asset.criticality.to_score(),
                    "is_crown_jewel": asset.criticality in [
                        AssetCriticality.CROWN_JEWEL, 
                        AssetCriticality.CRITICAL
                    ],
                    "is_entry_point": asset.asset_type in [
                        AssetType.WORKSTATION,
                        AssetType.WEB_SERVER,
                        AssetType.VPN_GATEWAY
                    ],
                    "hostname": asset.hostname,
                    "risk_score": asset.risk_score
                },
                "classes": f"{asset.asset_type.value} {asset.criticality.value}"
            })
        
        # Add edges
        for edge in self.edges.values():
            elements.append({
                "data": {
                    "id": edge.edge_id,
                    "source": edge.source_asset_id,
                    "target": edge.target_asset_id,
                    "technique": edge.technique.value,
                    "probability": edge.probability,
                    "label": edge.technique.value.replace("_", " ").title()
                },
                "classes": f"attack-edge prob-{int(edge.probability * 100)}"
            })
        
        return {"elements": elements}


# =============================================================================
# SIMULATION ENGINE
# =============================================================================

class AttackSimulator:
    """
    Monte Carlo simulation for attack path probability
    Simulates many attack attempts to get realistic success rates
    """
    
    def __init__(self, analyzer: AttackPathAnalyzer):
        self.analyzer = analyzer
    
    def simulate_attack(
        self, 
        entry_point_id: str, 
        target_id: str, 
        iterations: int = 1000
    ) -> Dict[str, Any]:
        """Run Monte Carlo simulation for attack success"""
        import random
        
        successes = 0
        path_successes: Dict[str, int] = defaultdict(int)
        time_to_compromise: List[float] = []
        
        # Find all possible paths first
        paths = self.analyzer._find_all_paths(entry_point_id, target_id, max_depth=8)
        if not paths:
            return {
                "success_rate": 0,
                "message": "No attack paths found",
                "simulations_run": iterations
            }
        
        for _ in range(iterations):
            # Try each path
            for path in paths:
                success = True
                total_time = 0
                
                for edge_id in path.edge_chain:
                    edge = self.analyzer.edges.get(edge_id)
                    if edge:
                        # Random check against probability
                        if random.random() > edge.probability:
                            success = False
                            break
                        total_time += random.uniform(0.5, 4.0)  # Hours per hop
                
                if success:
                    successes += 1
                    path_successes[path.path_id] += 1
                    time_to_compromise.append(total_time)
                    break  # One success per iteration
        
        return {
            "entry_point": entry_point_id,
            "target": target_id,
            "simulations_run": iterations,
            "successful_attacks": successes,
            "success_rate": round(successes / iterations, 3),
            "avg_time_to_compromise_hours": round(
                sum(time_to_compromise) / len(time_to_compromise), 1
            ) if time_to_compromise else 0,
            "most_successful_paths": sorted(
                path_successes.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            "risk_level": self._simulation_risk_level(successes / iterations)
        }
    
    def _simulation_risk_level(self, success_rate: float) -> str:
        if success_rate >= 0.8:
            return "CRITICAL - Almost certain compromise"
        elif success_rate >= 0.5:
            return "HIGH - Likely compromise"
        elif success_rate >= 0.2:
            return "MEDIUM - Possible compromise"
        elif success_rate >= 0.05:
            return "LOW - Unlikely compromise"
        return "MINIMAL - Very unlikely"


# =============================================================================
# SERVICE INTEGRATION
# =============================================================================

class AttackPathService:
    """
    Main service class for attack path analysis
    Integrates with other Seraph services
    """
    
    def __init__(self):
        self.analyzer = AttackPathAnalyzer()
        self.simulator = AttackSimulator(self.analyzer)
        self._last_analysis: Optional[Dict] = None
    
    async def import_from_agents(self, agent_telemetry: List[Dict]) -> Dict[str, Any]:
        """
        Import asset and relationship data from agent telemetry
        """
        # Extract assets from telemetry
        assets_added = 0
        for telemetry in agent_telemetry:
            if "host_info" in telemetry:
                host = telemetry["host_info"]
                asset = Asset(
                    asset_id=host.get("hostname", str(uuid.uuid4())),
                    name=host.get("hostname", "Unknown"),
                    asset_type=self._infer_asset_type(host),
                    criticality=AssetCriticality.UNKNOWN,
                    hostname=host.get("hostname"),
                    ip_addresses=host.get("ip_addresses", []),
                    os_type=host.get("os_type"),
                )
                self.analyzer.add_asset(asset)
                assets_added += 1
        
        return {
            "assets_imported": assets_added,
            "total_assets": len(self.analyzer.assets)
        }
    
    def _infer_asset_type(self, host: Dict) -> AssetType:
        """Infer asset type from host information"""
        hostname = (host.get("hostname") or "").lower()
        
        if any(x in hostname for x in ["dc", "domain", "ad"]):
            return AssetType.DOMAIN_CONTROLLER
        elif any(x in hostname for x in ["db", "sql", "mysql", "postgres"]):
            return AssetType.DATABASE_SERVER
        elif any(x in hostname for x in ["web", "www", "nginx", "apache"]):
            return AssetType.WEB_SERVER
        elif any(x in hostname for x in ["file", "nas", "share"]):
            return AssetType.FILE_SERVER
        elif any(x in hostname for x in ["vpn", "gateway"]):
            return AssetType.VPN_GATEWAY
        elif any(x in hostname for x in ["mail", "exchange", "smtp"]):
            return AssetType.EMAIL_SERVER
        elif any(x in hostname for x in ["backup", "veeam", "avamar"]):
            return AssetType.BACKUP_SERVER
        elif any(x in hostname for x in ["kube", "k8s", "rancher"]):
            return AssetType.CONTAINER_ORCHESTRATOR
        elif any(x in hostname for x in ["jenkins", "gitlab", "github", "cicd"]):
            return AssetType.CICD_SERVER
        elif any(x in hostname for x in ["vault", "cyberark", "secret"]):
            return AssetType.SECRET_VAULT
        
        return AssetType.WORKSTATION
    
    async def run_analysis(self) -> Dict[str, Any]:
        """Run full attack path analysis"""
        self._last_analysis = self.analyzer.analyze()
        return self._last_analysis
    
    async def get_crown_jewels(self) -> List[Dict]:
        """Get all crown jewels"""
        return [cj.to_dict() for cj in self.analyzer.get_crown_jewels()]
    
    async def add_crown_jewel_rule(self, rule: Dict) -> str:
        """Add custom crown jewel classification rule"""
        cj_rule = CrownJewelDefinition(
            rule_id=rule.get("rule_id", f"custom-{uuid.uuid4().hex[:8]}"),
            name=rule["name"],
            description=rule.get("description", ""),
            conditions=rule.get("conditions", {}),
            criticality=AssetCriticality(rule.get("criticality", "critical")),
            auto_tag=rule.get("auto_tag", [])
        )
        self.analyzer.crown_jewel_rules.append(cj_rule)
        return cj_rule.rule_id
    
    async def simulate_breach(
        self, 
        compromised_asset_id: str
    ) -> Dict[str, Any]:
        """Simulate a breach starting from a specific asset"""
        return self.analyzer.calculate_blast_radius(compromised_asset_id)
    
    async def get_cytoscape_graph(self) -> Dict[str, Any]:
        """Get graph in Cytoscape.js format for visualization"""
        return self.analyzer.to_cytoscape_format()
    
    async def get_remediation_priorities(self) -> List[Dict]:
        """Get prioritized remediation actions"""
        if not self._last_analysis:
            await self.run_analysis()
        return self._last_analysis.get("remediation_priorities", []) if self._last_analysis else []


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

# Create singleton service instance
attack_path_service = AttackPathService()


def get_attack_path_service() -> AttackPathService:
    """Get the attack path service instance"""
    return attack_path_service


# =============================================================================
# LEGACY COMPATIBILITY SHIMS
# =============================================================================

class CriticalityLevel(Enum):
    """Legacy criticality enum expected by routers.attack_paths."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    CROWN_JEWEL = "crown_jewel"


@dataclass
class CrownJewelAsset:
    """Legacy asset model expected by routers.attack_paths."""
    name: str
    asset_type: AssetType
    identifier: str
    criticality: CriticalityLevel
    description: str = ""
    owner: str = ""
    data_classification: str = "confidential"
    compliance_scope: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    network_zone: str = "internal"
    asset_id: str = field(default_factory=lambda: f"cj-{uuid.uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def criticality_score(self) -> int:
        mapping = {
            CriticalityLevel.CROWN_JEWEL: 100,
            CriticalityLevel.CRITICAL: 90,
            CriticalityLevel.HIGH: 70,
            CriticalityLevel.MEDIUM: 50,
            CriticalityLevel.LOW: 30,
        }
        return mapping.get(self.criticality, 10)


@dataclass
class BlastRadiusResult:
    """Legacy blast-radius response model expected by routers.attack_paths."""
    source_asset: str
    total_affected: int
    affected_by_criticality: Dict[CriticalityLevel, int]
    affected_assets: List[CrownJewelAsset]
    impact_by_asset: Dict[str, str]
    blast_radius_score: int
    max_criticality_affected: Optional[CriticalityLevel]
    recommendations: List[str]


class _LegacyAttackPathResult(NamedTuple):
    path_id: str
    source_asset: str
    target_asset: str
    risk_score: int
    mitre_techniques: List[str]
    steps: List[Dict[str, Any]]
    mitigations: List[str]


class _LegacyAttackPathAnalyzer:
    """Minimal legacy analyzer interface used by routers.attack_paths."""

    def __init__(self):
        self.crown_jewels: Dict[str, CrownJewelAsset] = {}
        self.attack_paths: Dict[str, _LegacyAttackPathResult] = {}

    def register_crown_jewel(self, asset: CrownJewelAsset) -> str:
        asset.updated_at = datetime.now(timezone.utc).isoformat()
        self.crown_jewels[asset.asset_id] = asset
        return asset.asset_id

    async def calculate_blast_radius(self, asset_id: str, max_depth: int = 3) -> BlastRadiusResult:
        source = self.crown_jewels.get(asset_id)
        if not source:
            raise ValueError(f"Asset not found: {asset_id}")

        seen: Set[str] = {asset_id}
        frontier: List[Tuple[str, int]] = [(asset_id, 0)]

        while frontier:
            current_id, depth = frontier.pop(0)
            if depth >= max_depth:
                continue
            current = self.crown_jewels.get(current_id)
            if not current:
                continue
            for dep_id in current.dependencies:
                if dep_id in self.crown_jewels and dep_id not in seen:
                    seen.add(dep_id)
                    frontier.append((dep_id, depth + 1))

        affected_assets = [self.crown_jewels[aid] for aid in seen if aid != asset_id]
        by_criticality: Dict[CriticalityLevel, int] = defaultdict(int)
        impact_by_asset: Dict[str, str] = {}
        for a in affected_assets:
            by_criticality[a.criticality] += 1
            impact_by_asset[a.asset_id] = "high" if a.criticality_score >= 70 else "medium"

        max_crit = max((a.criticality for a in affected_assets), key=lambda c: {
            CriticalityLevel.CROWN_JEWEL: 5,
            CriticalityLevel.CRITICAL: 4,
            CriticalityLevel.HIGH: 3,
            CriticalityLevel.MEDIUM: 2,
            CriticalityLevel.LOW: 1,
        }[c], default=None)

        score = min(100, len(affected_assets) * 10 + source.criticality_score // 2)
        recommendations = [
            "Segment crown jewel dependencies with strict network policy",
            "Apply MFA and least privilege on dependency chain",
            "Prioritize hardening of highest criticality connected assets",
        ]

        return BlastRadiusResult(
            source_asset=asset_id,
            total_affected=len(affected_assets),
            affected_by_criticality=dict(by_criticality),
            affected_assets=affected_assets,
            impact_by_asset=impact_by_asset,
            blast_radius_score=score,
            max_criticality_affected=max_crit,
            recommendations=recommendations,
        )

    async def find_attack_paths(
        self,
        target_asset_id: str,
        max_paths: int = 10,
        min_risk_score: int = 0,
    ) -> List[_LegacyAttackPathResult]:
        paths: List[_LegacyAttackPathResult] = []
        target = self.crown_jewels.get(target_asset_id)
        if not target:
            return paths

        for source_id, source in self.crown_jewels.items():
            if source_id == target_asset_id:
                continue
            risk = min(100, (source.criticality_score + target.criticality_score) // 2)
            if risk < min_risk_score:
                continue
            step = {
                "from": source_id,
                "to": target_asset_id,
                "technique": "T1078",
                "description": "Potential lateral movement via trusted relationship",
            }
            result = _LegacyAttackPathResult(
                path_id=f"path-{uuid.uuid4().hex[:10]}",
                source_asset=source_id,
                target_asset=target_asset_id,
                risk_score=risk,
                mitre_techniques=["T1078"],
                steps=[step],
                mitigations=["Enforce MFA", "Review trust relationships", "Segment network zones"],
            )
            self.attack_paths[result.path_id] = result
            paths.append(result)
            if len(paths) >= max_paths:
                break

        return paths


_legacy_attack_path_analyzer = _LegacyAttackPathAnalyzer()


def get_attack_path_analyzer() -> _LegacyAttackPathAnalyzer:
    """Legacy accessor retained for router compatibility."""
    return _legacy_attack_path_analyzer
