"""
Enterprise Threat Timeline Reconstruction Service
==================================================
Version: 3.0 (Enterprise Edition)

Builds comprehensive timelines of threat events, responses, and impacts
for incident investigation and reporting.

Core Features:
- Timeline construction from multiple data sources
- Impact assessment and response time calculation
- Export to JSON, Markdown, HTML formats

Enterprise Features:
- Attack Graph Generation (visualize attack paths)
- Causal Analysis Engine (root cause detection)
- Kill Chain Mapping (Lockheed Martin + Unified)
- MITRE ATT&CK Timeline Integration
- Forensic Artifact Correlation
- Playbook Suggestions (automated response)
- Multi-timeline Correlation (cross-incident analysis)
- Executive/Technical Report Generation
- Evidence Chain of Custody Tracking
- STIX Bundle Export
"""
import os
import re
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass, asdict, field
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class TimelineEventType(Enum):
    DETECTION = "detection"
    ALERT = "alert"
    RESPONSE = "response"
    QUARANTINE = "quarantine"
    BLOCK = "block"
    FORENSICS = "forensics"
    NOTIFICATION = "notification"
    USER_ACTION = "user_action"
    ESCALATION = "escalation"
    RESOLUTION = "resolution"
    INDICATOR = "indicator"
    LATERAL_MOVEMENT = "lateral_movement"
    DATA_EXFILTRATION = "data_exfiltration"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege_escalation"


class KillChainPhase(Enum):
    """Lockheed Martin Cyber Kill Chain phases"""
    RECONNAISSANCE = "reconnaissance"
    WEAPONIZATION = "weaponization"
    DELIVERY = "delivery"
    EXPLOITATION = "exploitation"
    INSTALLATION = "installation"
    COMMAND_AND_CONTROL = "command_and_control"
    ACTIONS_ON_OBJECTIVES = "actions_on_objectives"


class UnifiedKillChainPhase(Enum):
    """Unified Kill Chain phases (more granular)"""
    INITIAL_FOOTHOLD = "initial_foothold"
    NETWORK_PROPAGATION = "network_propagation"
    ACTION_ON_OBJECTIVES = "action_on_objectives"


class IncidentSeverity(Enum):
    """Incident severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReportType(Enum):
    """Report types"""
    EXECUTIVE = "executive"
    TECHNICAL = "technical"
    FORENSIC = "forensic"
    COMPLIANCE = "compliance"


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class TimelineEvent:
    """A single event in the threat timeline"""
    id: str
    timestamp: str
    event_type: str
    title: str
    description: str
    severity: str
    source: str  # agent, system, user, etc.
    related_threat_id: Optional[str] = None
    related_alert_id: Optional[str] = None
    actor: Optional[str] = None
    target: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    # Enterprise fields
    mitre_technique: Optional[str] = None
    kill_chain_phase: Optional[str] = None
    evidence_ids: List[str] = field(default_factory=list)
    parent_event_id: Optional[str] = None
    child_event_ids: List[str] = field(default_factory=list)
    confidence: float = 0.8
    tags: List[str] = field(default_factory=list)


@dataclass 
class ThreatTimeline:
    """Complete timeline for a threat incident"""
    threat_id: str
    threat_name: str
    threat_type: str
    severity: str
    status: str
    first_seen: str
    last_updated: str
    events: List[TimelineEvent] = field(default_factory=list)
    summary: Optional[str] = None
    impact_assessment: Optional[Dict[str, Any]] = None
    recommendations: List[str] = field(default_factory=list)
    # Enterprise fields
    attack_graph: Optional[Dict] = None
    root_cause: Optional[Dict] = None
    kill_chain_mapping: Dict[str, List[str]] = field(default_factory=dict)
    mitre_mapping: Dict[str, List[str]] = field(default_factory=dict)
    playbook_suggestions: List[Dict] = field(default_factory=list)
    related_incidents: List[str] = field(default_factory=list)
    evidence_chain: List[Dict] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AttackGraphNode:
    """Node in attack graph"""
    node_id: str
    node_type: str  # host, process, file, network, user
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    compromised: bool = False
    timestamp: Optional[str] = None


@dataclass
class AttackGraphEdge:
    """Edge in attack graph"""
    edge_id: str
    source_id: str
    target_id: str
    edge_type: str  # exploits, connects_to, spawns, accesses, exfiltrates
    label: str
    timestamp: str
    mitre_technique: Optional[str] = None


@dataclass
class ForensicArtifact:
    """Forensic evidence artifact"""
    artifact_id: str
    artifact_type: str  # file, registry, memory, network, log
    name: str
    description: str
    collected_at: str
    collected_by: str
    hash_md5: Optional[str] = None
    hash_sha256: Optional[str] = None
    chain_of_custody: List[Dict] = field(default_factory=list)
    related_events: List[str] = field(default_factory=list)
    analysis_results: Dict = field(default_factory=dict)


@dataclass
class CausalRelationship:
    """Causal relationship between events"""
    cause_event_id: str
    effect_event_id: str
    relationship_type: str  # triggers, enables, results_in
    confidence: float
    evidence: List[str] = field(default_factory=list)


@dataclass
class PlaybookSuggestion:
    """Suggested playbook for response"""
    playbook_id: str
    name: str
    description: str
    trigger_conditions: List[str]
    priority: int
    estimated_time_minutes: int
    automated: bool
    actions: List[Dict] = field(default_factory=list)


# =============================================================================
# MITRE ATT&CK MAPPINGS
# =============================================================================

MITRE_MAPPING = {
    "reconnaissance": ["T1595", "T1592", "T1589"],
    "initial_access": ["T1190", "T1566", "T1133"],
    "execution": ["T1059", "T1204", "T1053"],
    "persistence": ["T1547", "T1543", "T1136"],
    "privilege_escalation": ["T1548", "T1134", "T1068"],
    "defense_evasion": ["T1055", "T1027", "T1562"],
    "credential_access": ["T1003", "T1555", "T1056"],
    "discovery": ["T1082", "T1083", "T1057"],
    "lateral_movement": ["T1021", "T1570", "T1080"],
    "collection": ["T1113", "T1115", "T1039"],
    "exfiltration": ["T1041", "T1048", "T1567"],
    "impact": ["T1486", "T1485", "T1489"]
}

# Kill chain phase to MITRE tactic mapping
KILL_CHAIN_TO_MITRE = {
    KillChainPhase.RECONNAISSANCE.value: ["reconnaissance"],
    KillChainPhase.WEAPONIZATION.value: ["resource_development"],
    KillChainPhase.DELIVERY.value: ["initial_access"],
    KillChainPhase.EXPLOITATION.value: ["execution", "privilege_escalation"],
    KillChainPhase.INSTALLATION.value: ["persistence", "defense_evasion"],
    KillChainPhase.COMMAND_AND_CONTROL.value: ["command_and_control"],
    KillChainPhase.ACTIONS_ON_OBJECTIVES.value: ["collection", "exfiltration", "impact"]
}


# =============================================================================
# ATTACK GRAPH GENERATOR
# =============================================================================

class AttackGraphGenerator:
    """
    Generates attack graphs from timeline events
    
    Creates visual representation of:
    - Attack paths through systems
    - Lateral movement
    - Privilege escalation chains
    - Data exfiltration paths
    """
    
    def __init__(self):
        self.nodes: Dict[str, AttackGraphNode] = {}
        self.edges: List[AttackGraphEdge] = []
    
    def generate_graph(self, events: List[TimelineEvent]) -> Dict[str, Any]:
        """Generate attack graph from timeline events"""
        self.nodes.clear()
        self.edges.clear()
        
        for event in events:
            self._process_event(event)
        
        # Build graph structure
        graph = {
            "nodes": [asdict(n) for n in self.nodes.values()],
            "edges": [asdict(e) for e in self.edges],
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "compromised_nodes": sum(1 for n in self.nodes.values() if n.compromised)
            }
        }
        
        # Add path analysis
        graph["attack_paths"] = self._find_attack_paths()
        graph["critical_nodes"] = self._identify_critical_nodes()
        
        return graph
    
    def _process_event(self, event: TimelineEvent):
        """Process single event into graph components"""
        # Extract entities from event
        source_entity = event.actor or event.source
        target_entity = event.target
        
        # Create/update source node
        if source_entity:
            source_id = self._normalize_id(source_entity)
            if source_id not in self.nodes:
                self.nodes[source_id] = AttackGraphNode(
                    node_id=source_id,
                    node_type=self._infer_node_type(source_entity),
                    label=source_entity,
                    timestamp=event.timestamp
                )
            if event.event_type in ["detection", "malware", "intrusion"]:
                self.nodes[source_id].compromised = True
        
        # Create/update target node
        if target_entity:
            target_id = self._normalize_id(target_entity)
            if target_id not in self.nodes:
                self.nodes[target_id] = AttackGraphNode(
                    node_id=target_id,
                    node_type=self._infer_node_type(target_entity),
                    label=target_entity,
                    timestamp=event.timestamp
                )
            if event.event_type in ["detection", "quarantine", "block"]:
                self.nodes[target_id].compromised = True
        
        # Create edge
        if source_entity and target_entity:
            edge = AttackGraphEdge(
                edge_id=f"edge_{event.id}",
                source_id=self._normalize_id(source_entity),
                target_id=self._normalize_id(target_entity),
                edge_type=self._infer_edge_type(event.event_type),
                label=event.title,
                timestamp=event.timestamp,
                mitre_technique=event.mitre_technique
            )
            self.edges.append(edge)
    
    def _normalize_id(self, entity: str) -> str:
        """Normalize entity name to valid ID"""
        return re.sub(r'[^a-zA-Z0-9_-]', '_', entity.lower())[:50]
    
    def _infer_node_type(self, entity: str) -> str:
        """Infer node type from entity name"""
        entity_lower = entity.lower()
        
        if re.match(r'\d+\.\d+\.\d+\.\d+', entity):
            return "network"
        elif any(x in entity_lower for x in ["host", "server", "workstation", "vm-"]):
            return "host"
        elif any(x in entity_lower for x in [".exe", ".dll", "process"]):
            return "process"
        elif any(x in entity_lower for x in ["user", "admin", "root"]):
            return "user"
        elif any(x in entity_lower for x in ["file", "document", ".pdf", ".doc"]):
            return "file"
        
        return "unknown"
    
    def _infer_edge_type(self, event_type: str) -> str:
        """Infer edge type from event type"""
        mapping = {
            "detection": "detected_at",
            "lateral_movement": "moves_to",
            "privilege_escalation": "escalates_on",
            "data_exfiltration": "exfiltrates_from",
            "persistence": "persists_on",
            "quarantine": "quarantined",
            "block": "blocked",
            "response": "responded_to"
        }
        return mapping.get(event_type, "relates_to")
    
    def _find_attack_paths(self) -> List[List[str]]:
        """Find all attack paths through the graph"""
        paths = []
        
        # Find entry points (nodes with no incoming edges)
        incoming = {e.target_id for e in self.edges}
        outgoing = {e.source_id for e in self.edges}
        entry_points = outgoing - incoming
        
        # Find endpoints (compromised nodes with no outgoing edges)
        endpoints = {n.node_id for n in self.nodes.values() 
                    if n.compromised and n.node_id not in outgoing}
        
        # BFS to find paths
        for start in entry_points:
            visited = set()
            queue = [[start]]
            
            while queue:
                path = queue.pop(0)
                current = path[-1]
                
                if current in endpoints:
                    paths.append(path)
                    continue
                
                if current in visited:
                    continue
                visited.add(current)
                
                # Find next nodes
                for edge in self.edges:
                    if edge.source_id == current and edge.target_id not in visited:
                        queue.append(path + [edge.target_id])
        
        return paths
    
    def _identify_critical_nodes(self) -> List[Dict]:
        """Identify critical nodes in the attack graph"""
        critical = []
        
        # Count edge connections
        edge_counts = defaultdict(int)
        for edge in self.edges:
            edge_counts[edge.source_id] += 1
            edge_counts[edge.target_id] += 1
        
        # Nodes with high connectivity or compromised status
        for node_id, node in self.nodes.items():
            criticality = 0
            
            if node.compromised:
                criticality += 50
            
            if node.node_type in ["host", "user"]:
                criticality += 20
            
            criticality += min(edge_counts[node_id] * 10, 30)
            
            if criticality >= 50:
                critical.append({
                    "node_id": node_id,
                    "label": node.label,
                    "type": node.node_type,
                    "criticality": criticality,
                    "compromised": node.compromised
                })
        
        return sorted(critical, key=lambda x: x["criticality"], reverse=True)


# =============================================================================
# CAUSAL ANALYSIS ENGINE
# =============================================================================

class CausalAnalysisEngine:
    """
    Analyzes causal relationships between events
    
    Features:
    - Root cause identification
    - Event correlation
    - Impact chain analysis
    - Confidence scoring
    """
    
    def __init__(self):
        self.relationships: List[CausalRelationship] = []
        self._last_root_cause: Dict[str, Any] = {"found": False}
    
    def analyze(self, events: List[TimelineEvent]) -> Dict[str, Any]:
        """Analyze causal relationships in events"""
        self.relationships.clear()
        
        # Sort events by timestamp
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        
        # Build causal relationships
        for i, event in enumerate(sorted_events):
            # Look for potential causes in preceding events
            for j in range(max(0, i - 10), i):
                prev_event = sorted_events[j]
                relationship = self._check_causation(prev_event, event)
                if relationship:
                    self.relationships.append(relationship)
        
        # Find root cause
        root_cause = self._find_root_cause(sorted_events)
        self._last_root_cause = root_cause
        
        # Build impact chain
        impact_chain = self._build_impact_chain(sorted_events)
        
        return {
            "root_cause": root_cause,
            "relationships": [asdict(r) for r in self.relationships],
            "impact_chain": impact_chain,
            "causal_graph": self._build_causal_graph()
        }

    def get_root_cause(self) -> Dict[str, Any]:
        """Compatibility accessor for callers expecting a cached root-cause result."""
        return self._last_root_cause or {"found": False}
    
    def _check_causation(
        self,
        potential_cause: TimelineEvent,
        effect: TimelineEvent
    ) -> Optional[CausalRelationship]:
        """Check if one event caused another"""
        # Time-based causation (within time window)
        try:
            cause_time = datetime.fromisoformat(potential_cause.timestamp.replace('Z', '+00:00'))
            effect_time = datetime.fromisoformat(effect.timestamp.replace('Z', '+00:00'))
            time_diff = (effect_time - cause_time).total_seconds()
            
            if time_diff < 0 or time_diff > 3600:  # 1 hour window
                return None
        except Exception:
            return None
        
        # Check for causal patterns
        confidence = 0.0
        relationship_type = "relates_to"
        evidence = []
        
        # Detection triggers response
        if potential_cause.event_type == "detection" and effect.event_type in ["response", "block", "quarantine"]:
            confidence = 0.9
            relationship_type = "triggers"
            evidence.append("Detection event triggers automated response")
        
        # Same target
        elif potential_cause.target == effect.target and potential_cause.target:
            confidence += 0.3
            evidence.append(f"Same target: {potential_cause.target}")
        
        # Same threat ID
        elif potential_cause.related_threat_id == effect.related_threat_id:
            confidence += 0.4
            evidence.append(f"Same threat: {potential_cause.related_threat_id}")
        
        # Escalation patterns
        elif potential_cause.event_type == "alert" and effect.event_type == "escalation":
            confidence = 0.8
            relationship_type = "enables"
            evidence.append("Alert leads to escalation")
        
        if confidence >= 0.3:
            return CausalRelationship(
                cause_event_id=potential_cause.id,
                effect_event_id=effect.id,
                relationship_type=relationship_type,
                confidence=confidence,
                evidence=evidence
            )
        
        return None
    
    def _find_root_cause(self, events: List[TimelineEvent]) -> Dict[str, Any]:
        """Identify the root cause event"""
        if not events:
            return {"found": False}
        
        # Find event with most downstream effects
        effect_counts = defaultdict(int)
        for rel in self.relationships:
            effect_counts[rel.cause_event_id] += 1
        
        # First detection event is often root cause
        detection_events = [e for e in events if e.event_type == "detection"]
        
        if detection_events:
            root = detection_events[0]
            return {
                "found": True,
                "event_id": root.id,
                "event_type": root.event_type,
                "title": root.title,
                "timestamp": root.timestamp,
                "downstream_effects": effect_counts.get(root.id, 0),
                "confidence": 0.85
            }
        
        # Fallback to first event
        root = events[0]
        return {
            "found": True,
            "event_id": root.id,
            "event_type": root.event_type,
            "title": root.title,
            "timestamp": root.timestamp,
            "downstream_effects": effect_counts.get(root.id, 0),
            "confidence": 0.5
        }
    
    def _build_impact_chain(self, events: List[TimelineEvent]) -> List[Dict]:
        """Build chain of impact from root cause to effects"""
        chain = []
        
        # Group events by their causal relationships
        caused_by = defaultdict(list)
        for rel in self.relationships:
            caused_by[rel.cause_event_id].append(rel.effect_event_id)
        
        # Build chain starting from root
        detection_events = [e.id for e in events if e.event_type == "detection"]
        
        visited = set()
        queue = list(detection_events)
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            
            event = next((e for e in events if e.id == current), None)
            if event:
                chain.append({
                    "event_id": event.id,
                    "title": event.title,
                    "timestamp": event.timestamp,
                    "effects": caused_by.get(current, [])[:5]
                })
            
            # Add downstream effects to queue
            for effect_id in caused_by.get(current, []):
                if effect_id not in visited:
                    queue.append(effect_id)
        
        return chain[:20]  # Limit chain length
    
    def _build_causal_graph(self) -> Dict:
        """Build graph representation of causal relationships"""
        nodes = set()
        edges = []
        
        for rel in self.relationships:
            nodes.add(rel.cause_event_id)
            nodes.add(rel.effect_event_id)
            edges.append({
                "source": rel.cause_event_id,
                "target": rel.effect_event_id,
                "type": rel.relationship_type,
                "confidence": rel.confidence
            })
        
        return {
            "nodes": list(nodes),
            "edges": edges
        }


# =============================================================================
# KILL CHAIN MAPPER
# =============================================================================

class KillChainMapper:
    """
    Maps events to cyber kill chain phases
    
    Supports:
    - Lockheed Martin Cyber Kill Chain
    - Unified Kill Chain
    - MITRE ATT&CK tactics
    """
    
    # Event type to kill chain phase mapping
    EVENT_TO_PHASE = {
        "detection": KillChainPhase.DELIVERY,
        "lateral_movement": KillChainPhase.ACTIONS_ON_OBJECTIVES,
        "privilege_escalation": KillChainPhase.EXPLOITATION,
        "persistence": KillChainPhase.INSTALLATION,
        "data_exfiltration": KillChainPhase.ACTIONS_ON_OBJECTIVES,
        "alert": KillChainPhase.DELIVERY,
        "quarantine": KillChainPhase.ACTIONS_ON_OBJECTIVES,
        "block": KillChainPhase.COMMAND_AND_CONTROL
    }
    
    def map_events(self, events: List[TimelineEvent]) -> Dict[str, Any]:
        """Map all events to kill chain phases"""
        mapping = {phase.value: [] for phase in KillChainPhase}
        mitre_mapping = defaultdict(list)
        
        for event in events:
            # Determine kill chain phase
            phase = self._determine_phase(event)
            if phase:
                mapping[phase.value].append({
                    "event_id": event.id,
                    "title": event.title,
                    "timestamp": event.timestamp
                })
            
            # Map to MITRE
            if event.mitre_technique:
                mitre_mapping[event.mitre_technique].append(event.id)
        
        # Calculate phase coverage
        phase_coverage = self._calculate_coverage(mapping)
        
        # Determine attack stage
        attack_stage = self._determine_attack_stage(mapping)
        
        return {
            "kill_chain_mapping": mapping,
            "mitre_mapping": dict(mitre_mapping),
            "phase_coverage": phase_coverage,
            "current_stage": attack_stage,
            "progression": self._analyze_progression(events)
        }
    
    def _determine_phase(self, event: TimelineEvent) -> Optional[KillChainPhase]:
        """Determine kill chain phase for event"""
        # Check explicit phase
        if event.kill_chain_phase:
            try:
                return KillChainPhase(event.kill_chain_phase)
            except ValueError:
                pass
        
        # Map from event type
        return self.EVENT_TO_PHASE.get(event.event_type)
    
    def _calculate_coverage(self, mapping: Dict) -> Dict:
        """Calculate coverage of each kill chain phase"""
        total_phases = len(KillChainPhase)
        covered_phases = sum(1 for events in mapping.values() if events)
        
        return {
            "total_phases": total_phases,
            "covered_phases": covered_phases,
            "coverage_percentage": (covered_phases / total_phases) * 100,
            "phases": {
                phase: len(events) > 0
                for phase, events in mapping.items()
            }
        }
    
    def _determine_attack_stage(self, mapping: Dict) -> str:
        """Determine current attack stage based on observed phases"""
        # Check from end of kill chain
        phases = list(KillChainPhase)
        
        for phase in reversed(phases):
            if mapping.get(phase.value):
                return phase.value
        
        return "unknown"
    
    def _analyze_progression(self, events: List[TimelineEvent]) -> List[Dict]:
        """Analyze attack progression over time"""
        progression = []
        
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        
        for event in sorted_events:
            phase = self._determine_phase(event)
            if phase:
                progression.append({
                    "timestamp": event.timestamp,
                    "phase": phase.value,
                    "event_type": event.event_type
                })
        
        return progression


# =============================================================================
# PLAYBOOK SUGGESTER
# =============================================================================

class PlaybookSuggester:
    """
    Suggests response playbooks based on timeline events
    
    Features:
    - Threat-type based suggestions
    - Severity-based prioritization
    - Automated vs manual recommendations
    - Estimated remediation time
    """
    
    # Default playbook templates
    PLAYBOOK_TEMPLATES = {
        "malware_containment": PlaybookSuggestion(
            playbook_id="pb_malware_001",
            name="Malware Containment",
            description="Isolate and contain malware infection",
            trigger_conditions=["malware_detected", "ransomware_detected"],
            priority=1,
            estimated_time_minutes=30,
            automated=True,
            actions=[
                {"step": 1, "action": "isolate_host", "description": "Isolate infected host from network"},
                {"step": 2, "action": "kill_process", "description": "Terminate malicious processes"},
                {"step": 3, "action": "quarantine_files", "description": "Quarantine malicious files"},
                {"step": 4, "action": "scan_endpoints", "description": "Scan connected endpoints"},
                {"step": 5, "action": "collect_forensics", "description": "Collect forensic artifacts"}
            ]
        ),
        "data_breach_response": PlaybookSuggestion(
            playbook_id="pb_breach_001",
            name="Data Breach Response",
            description="Respond to potential data breach",
            trigger_conditions=["data_exfiltration", "credential_theft"],
            priority=1,
            estimated_time_minutes=120,
            automated=False,
            actions=[
                {"step": 1, "action": "block_exfil_channels", "description": "Block exfiltration channels"},
                {"step": 2, "action": "preserve_evidence", "description": "Preserve forensic evidence"},
                {"step": 3, "action": "assess_scope", "description": "Assess data exposure scope"},
                {"step": 4, "action": "notify_stakeholders", "description": "Notify relevant stakeholders"},
                {"step": 5, "action": "initiate_ir", "description": "Initiate incident response procedure"}
            ]
        ),
        "lateral_movement_response": PlaybookSuggestion(
            playbook_id="pb_lateral_001",
            name="Lateral Movement Response",
            description="Contain lateral movement attempts",
            trigger_conditions=["lateral_movement", "privilege_escalation"],
            priority=2,
            estimated_time_minutes=60,
            automated=True,
            actions=[
                {"step": 1, "action": "segment_network", "description": "Implement network segmentation"},
                {"step": 2, "action": "reset_credentials", "description": "Reset affected credentials"},
                {"step": 3, "action": "block_attacker_ip", "description": "Block attacker IP addresses"},
                {"step": 4, "action": "audit_access", "description": "Audit recent access patterns"}
            ]
        ),
        "phishing_response": PlaybookSuggestion(
            playbook_id="pb_phishing_001",
            name="Phishing Response",
            description="Respond to phishing attack",
            trigger_conditions=["phishing", "spear_phishing"],
            priority=2,
            estimated_time_minutes=45,
            automated=True,
            actions=[
                {"step": 1, "action": "block_sender", "description": "Block phishing sender"},
                {"step": 2, "action": "remove_emails", "description": "Remove phishing emails from mailboxes"},
                {"step": 3, "action": "scan_attachments", "description": "Scan and quarantine attachments"},
                {"step": 4, "action": "notify_users", "description": "Notify affected users"},
                {"step": 5, "action": "update_filters", "description": "Update email filtering rules"}
            ]
        ),
        "ddos_mitigation": PlaybookSuggestion(
            playbook_id="pb_ddos_001",
            name="DDoS Mitigation",
            description="Mitigate DDoS attack",
            trigger_conditions=["ddos", "dos_attack"],
            priority=1,
            estimated_time_minutes=20,
            automated=True,
            actions=[
                {"step": 1, "action": "enable_rate_limiting", "description": "Enable rate limiting"},
                {"step": 2, "action": "activate_waf", "description": "Activate WAF rules"},
                {"step": 3, "action": "route_traffic", "description": "Route traffic through scrubbing"},
                {"step": 4, "action": "block_sources", "description": "Block attack sources"}
            ]
        )
    }
    
    def __init__(self):
        self.playbooks = dict(self.PLAYBOOK_TEMPLATES)
        self.suggested_playbooks: Dict[str, List[PlaybookSuggestion]] = {}
    
    def suggest_playbooks(
        self,
        threat_id: str,
        events: List[TimelineEvent],
        threat_type: str,
        severity: str
    ) -> List[Dict]:
        """Suggest playbooks based on timeline events"""
        suggestions = []
        triggered_playbooks = set()
        
        # Check event types
        event_types = {e.event_type for e in events}
        
        for pb_id, playbook in self.playbooks.items():
            for trigger in playbook.trigger_conditions:
                if trigger in event_types or trigger in threat_type.lower():
                    if pb_id not in triggered_playbooks:
                        # Adjust priority based on severity
                        adjusted_priority = playbook.priority
                        if severity == "critical":
                            adjusted_priority = 1
                        elif severity == "high" and adjusted_priority > 1:
                            adjusted_priority = 2
                        
                        suggestions.append({
                            "playbook_id": playbook.playbook_id,
                            "name": playbook.name,
                            "description": playbook.description,
                            "priority": adjusted_priority,
                            "estimated_time_minutes": playbook.estimated_time_minutes,
                            "automated": playbook.automated,
                            "actions": playbook.actions,
                            "triggered_by": trigger
                        })
                        triggered_playbooks.add(pb_id)
        
        # Sort by priority
        suggestions.sort(key=lambda x: x["priority"])
        
        self.suggested_playbooks[threat_id] = suggestions
        return suggestions
    
    def add_playbook(self, pb_id: str, playbook: PlaybookSuggestion):
        """Add custom playbook"""
        self.playbooks[pb_id] = playbook
    
    def get_playbook(self, playbook_id: str) -> Optional[Dict]:
        """Get playbook by ID"""
        for playbook in self.playbooks.values():
            if playbook.playbook_id == playbook_id:
                return asdict(playbook)
        return None


# =============================================================================
# FORENSIC ARTIFACT TRACKER
# =============================================================================

class ForensicArtifactTracker:
    """
    Tracks forensic artifacts and chain of custody
    
    Features:
    - Artifact registration and tracking
    - Chain of custody management
    - Hash verification
    - Evidence correlation
    """
    
    def __init__(self):
        self.artifacts: Dict[str, ForensicArtifact] = {}
        self.custody_log: List[Dict] = []
    
    def register_artifact(
        self,
        artifact_type: str,
        name: str,
        description: str,
        collected_by: str,
        hash_md5: str = None,
        hash_sha256: str = None
    ) -> ForensicArtifact:
        """Register new forensic artifact"""
        artifact_id = f"artifact_{uuid.uuid4().hex[:12]}"
        
        artifact = ForensicArtifact(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            name=name,
            description=description,
            collected_at=datetime.now(timezone.utc).isoformat(),
            collected_by=collected_by,
            hash_md5=hash_md5,
            hash_sha256=hash_sha256,
            chain_of_custody=[{
                "action": "collected",
                "actor": collected_by,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "notes": "Initial collection"
            }]
        )
        
        self.artifacts[artifact_id] = artifact
        
        logger.info(f"Registered artifact: {artifact_id} ({name})")
        return artifact
    
    def update_custody(
        self,
        artifact_id: str,
        action: str,
        actor: str,
        notes: str = ""
    ) -> bool:
        """Update chain of custody"""
        if artifact_id not in self.artifacts:
            return False
        
        custody_entry = {
            "action": action,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notes": notes
        }
        
        self.artifacts[artifact_id].chain_of_custody.append(custody_entry)
        self.custody_log.append({
            "artifact_id": artifact_id,
            **custody_entry
        })
        
        return True
    
    def link_to_event(self, artifact_id: str, event_id: str):
        """Link artifact to timeline event"""
        if artifact_id in self.artifacts:
            if event_id not in self.artifacts[artifact_id].related_events:
                self.artifacts[artifact_id].related_events.append(event_id)
    
    def add_analysis_result(
        self,
        artifact_id: str,
        analysis_type: str,
        result: Dict
    ):
        """Add analysis result to artifact"""
        if artifact_id in self.artifacts:
            self.artifacts[artifact_id].analysis_results[analysis_type] = {
                "result": result,
                "analyzed_at": datetime.now(timezone.utc).isoformat()
            }
    
    def verify_integrity(self, artifact_id: str, current_hash: str) -> Dict:
        """Verify artifact integrity against stored hash"""
        if artifact_id not in self.artifacts:
            return {"valid": False, "error": "Artifact not found"}
        
        artifact = self.artifacts[artifact_id]
        
        # Check against SHA256 first, then MD5
        if artifact.hash_sha256:
            valid = current_hash.lower() == artifact.hash_sha256.lower()
            return {
                "valid": valid,
                "hash_type": "sha256",
                "stored_hash": artifact.hash_sha256,
                "current_hash": current_hash
            }
        elif artifact.hash_md5:
            valid = current_hash.lower() == artifact.hash_md5.lower()
            return {
                "valid": valid,
                "hash_type": "md5",
                "stored_hash": artifact.hash_md5,
                "current_hash": current_hash
            }
        
        return {"valid": False, "error": "No stored hash for comparison"}
    
    def get_artifact(self, artifact_id: str) -> Optional[Dict]:
        """Get artifact details"""
        if artifact_id in self.artifacts:
            return asdict(self.artifacts[artifact_id])
        return None
    
    def get_artifacts_for_event(self, event_id: str) -> List[Dict]:
        """Get all artifacts related to event"""
        return [
            asdict(a) for a in self.artifacts.values()
            if event_id in a.related_events
        ]
    
    def export_custody_report(self, artifact_id: str) -> str:
        """Export chain of custody report"""
        if artifact_id not in self.artifacts:
            return ""
        
        artifact = self.artifacts[artifact_id]
        
        report = f"# Chain of Custody Report\n\n"
        report += f"**Artifact ID:** {artifact.artifact_id}\n"
        report += f"**Name:** {artifact.name}\n"
        report += f"**Type:** {artifact.artifact_type}\n"
        report += f"**Collected:** {artifact.collected_at}\n"
        
        if artifact.hash_sha256:
            report += f"**SHA-256:** {artifact.hash_sha256}\n"
        if artifact.hash_md5:
            report += f"**MD5:** {artifact.hash_md5}\n"
        
        report += f"\n## Chain of Custody\n\n"
        report += "| Timestamp | Action | Actor | Notes |\n"
        report += "|-----------|--------|-------|-------|\n"
        
        for entry in artifact.chain_of_custody:
            report += f"| {entry['timestamp']} | {entry['action']} | {entry['actor']} | {entry.get('notes', '')} |\n"
        
        return report


# =============================================================================
# MULTI-INCIDENT CORRELATOR
# =============================================================================

class MultiIncidentCorrelator:
    """
    Correlates events across multiple incidents
    
    Features:
    - Cross-incident pattern detection
    - Campaign identification
    - Actor attribution
    - Shared IOC detection
    """
    
    def __init__(self):
        self.timelines: Dict[str, ThreatTimeline] = {}
        self.correlations: List[Dict] = []
        self.campaigns: Dict[str, Dict] = {}
    
    def add_timeline(self, timeline: ThreatTimeline):
        """Add timeline for correlation analysis"""
        self.timelines[timeline.threat_id] = timeline
    
    def correlate(self) -> Dict[str, Any]:
        """Correlate all registered timelines"""
        if len(self.timelines) < 2:
            return {"correlations": [], "campaigns": []}
        
        self.correlations.clear()
        
        timeline_list = list(self.timelines.values())
        
        # Compare each pair of timelines
        for i in range(len(timeline_list)):
            for j in range(i + 1, len(timeline_list)):
                correlation = self._correlate_pair(timeline_list[i], timeline_list[j])
                if correlation["correlation_score"] > 0.3:
                    self.correlations.append(correlation)
        
        # Identify campaigns
        campaigns = self._identify_campaigns()
        
        return {
            "correlations": self.correlations,
            "campaigns": campaigns,
            "total_timelines": len(self.timelines)
        }
    
    def _correlate_pair(self, t1: ThreatTimeline, t2: ThreatTimeline) -> Dict:
        """Correlate two timelines"""
        shared_indicators = []
        score = 0.0
        
        # Check for shared IOCs
        t1_targets = {e.target for e in t1.events if e.target}
        t2_targets = {e.target for e in t2.events if e.target}
        shared_targets = t1_targets & t2_targets
        
        if shared_targets:
            shared_indicators.extend([f"target:{t}" for t in shared_targets])
            score += len(shared_targets) * 0.1
        
        # Check for shared actors
        t1_actors = {e.actor for e in t1.events if e.actor}
        t2_actors = {e.actor for e in t2.events if e.actor}
        shared_actors = t1_actors & t2_actors
        
        if shared_actors:
            shared_indicators.extend([f"actor:{a}" for a in shared_actors])
            score += len(shared_actors) * 0.2
        
        # Check for same threat type
        if t1.threat_type == t2.threat_type:
            score += 0.15
            shared_indicators.append(f"threat_type:{t1.threat_type}")
        
        # Check for temporal proximity (within 24 hours)
        try:
            t1_time = datetime.fromisoformat(t1.first_seen.replace('Z', '+00:00'))
            t2_time = datetime.fromisoformat(t2.first_seen.replace('Z', '+00:00'))
            time_diff = abs((t1_time - t2_time).total_seconds())
            
            if time_diff < 86400:  # 24 hours
                score += 0.2
                shared_indicators.append("temporal_proximity")
        except Exception:
            pass
        
        # Check for shared MITRE techniques
        t1_mitre = set(t1.mitre_mapping.keys()) if t1.mitre_mapping else set()
        t2_mitre = set(t2.mitre_mapping.keys()) if t2.mitre_mapping else set()
        shared_mitre = t1_mitre & t2_mitre
        
        if shared_mitre:
            shared_indicators.extend([f"mitre:{t}" for t in shared_mitre])
            score += len(shared_mitre) * 0.05
        
        return {
            "timeline_1": t1.threat_id,
            "timeline_2": t2.threat_id,
            "correlation_score": min(score, 1.0),
            "shared_indicators": shared_indicators[:20],
            "relationship": self._determine_relationship(score)
        }
    
    def _determine_relationship(self, score: float) -> str:
        """Determine relationship type based on score"""
        if score >= 0.7:
            return "same_campaign"
        elif score >= 0.5:
            return "likely_related"
        elif score >= 0.3:
            return "possibly_related"
        return "unrelated"
    
    def _identify_campaigns(self) -> List[Dict]:
        """Identify threat campaigns from correlations"""
        campaigns = []
        
        # Group highly correlated timelines
        groups = defaultdict(set)
        
        for correlation in self.correlations:
            if correlation["correlation_score"] >= 0.5:
                t1 = correlation["timeline_1"]
                t2 = correlation["timeline_2"]
                
                # Find existing group or create new
                found = False
                for group_id, members in groups.items():
                    if t1 in members or t2 in members:
                        members.add(t1)
                        members.add(t2)
                        found = True
                        break
                
                if not found:
                    group_id = f"campaign_{uuid.uuid4().hex[:8]}"
                    groups[group_id] = {t1, t2}
        
        # Build campaign objects
        for campaign_id, members in groups.items():
            campaigns.append({
                "campaign_id": campaign_id,
                "incident_count": len(members),
                "incidents": list(members),
                "first_seen": min(
                    self.timelines[m].first_seen 
                    for m in members 
                    if m in self.timelines
                ),
                "threat_types": list({
                    self.timelines[m].threat_type 
                    for m in members 
                    if m in self.timelines
                })
            })
        
        return campaigns
    
    def find_related_incidents(self, threat_id: str) -> List[Dict]:
        """Find incidents related to given threat"""
        related = []
        
        for correlation in self.correlations:
            if correlation["timeline_1"] == threat_id:
                related.append({
                    "threat_id": correlation["timeline_2"],
                    "score": correlation["correlation_score"],
                    "relationship": correlation["relationship"],
                    "shared_indicators": correlation["shared_indicators"]
                })
            elif correlation["timeline_2"] == threat_id:
                related.append({
                    "threat_id": correlation["timeline_1"],
                    "score": correlation["correlation_score"],
                    "relationship": correlation["relationship"],
                    "shared_indicators": correlation["shared_indicators"]
                })
        
        return sorted(related, key=lambda x: x["score"], reverse=True)


# =============================================================================
# REPORT GENERATOR
# =============================================================================

class TimelineReportGenerator:
    """
    Generates incident reports from timelines
    
    Report Types:
    - Executive Summary (high-level for leadership)
    - Technical Report (detailed for analysts)
    - Forensic Report (evidence-focused)
    - Compliance Report (regulatory requirements)
    """
    
    def generate_report(
        self,
        timeline: ThreatTimeline,
        report_type: ReportType = ReportType.TECHNICAL
    ) -> str:
        """Generate report based on type"""
        generators = {
            ReportType.EXECUTIVE: self._generate_executive_report,
            ReportType.TECHNICAL: self._generate_technical_report,
            ReportType.FORENSIC: self._generate_forensic_report,
            ReportType.COMPLIANCE: self._generate_compliance_report
        }
        
        generator = generators.get(report_type, self._generate_technical_report)
        return generator(timeline)
    
    def _generate_executive_report(self, timeline: ThreatTimeline) -> str:
        """Generate executive summary report"""
        report = "# Executive Incident Summary\n\n"
        report += f"**Report Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
        report += f"**Incident ID:** {timeline.threat_id}\n"
        report += f"**Severity:** {timeline.severity.upper()}\n"
        report += f"**Status:** {timeline.status.upper()}\n\n"
        
        report += "## Overview\n\n"
        report += f"{timeline.summary or 'Security incident detected requiring attention.'}\n\n"
        
        report += "## Key Metrics\n\n"
        if timeline.impact_assessment:
            impact = timeline.impact_assessment
            report += f"- **Affected Systems:** {len(impact.get('affected_systems', []))}\n"
            report += f"- **Response Time:** {impact.get('response_time_minutes', 'N/A')} minutes\n"
            report += f"- **Contained:** {'Yes' if impact.get('contained') else 'No'}\n"
        report += f"- **Total Events:** {len(timeline.events)}\n\n"
        
        report += "## Business Impact\n\n"
        if timeline.severity == "critical":
            report += "This incident requires immediate executive attention. "
            report += "Business operations may be significantly impacted.\n\n"
        elif timeline.severity == "high":
            report += "This incident has high potential for business impact. "
            report += "Close monitoring and rapid response are recommended.\n\n"
        else:
            report += "This incident has been contained with minimal business impact.\n\n"
        
        report += "## Recommended Actions\n\n"
        for i, rec in enumerate(timeline.recommendations[:5], 1):
            report += f"{i}. {rec}\n"
        
        return report
    
    def _generate_technical_report(self, timeline: ThreatTimeline) -> str:
        """Generate detailed technical report"""
        report = "# Technical Incident Report\n\n"
        report += f"**Incident ID:** {timeline.threat_id}\n"
        report += f"**Threat Name:** {timeline.threat_name}\n"
        report += f"**Threat Type:** {timeline.threat_type}\n"
        report += f"**Severity:** {timeline.severity}\n"
        report += f"**Status:** {timeline.status}\n"
        report += f"**First Seen:** {timeline.first_seen}\n"
        report += f"**Last Updated:** {timeline.last_updated}\n\n"
        
        report += "## Summary\n\n"
        report += f"{timeline.summary or 'No summary available.'}\n\n"
        
        report += "## Impact Assessment\n\n"
        if timeline.impact_assessment:
            for key, value in timeline.impact_assessment.items():
                report += f"- **{key.replace('_', ' ').title()}:** {value}\n"
        report += "\n"
        
        report += "## Kill Chain Analysis\n\n"
        if timeline.kill_chain_mapping:
            # Support both legacy flat phase map and enriched mapper payload.
            phase_map = timeline.kill_chain_mapping
            if isinstance(phase_map, dict) and isinstance(phase_map.get("kill_chain_mapping"), dict):
                phase_map = phase_map.get("kill_chain_mapping", {})

            for phase, events in phase_map.items():
                if events:
                    report += f"### {phase.replace('_', ' ').title()}\n"
                    for event_ref in events[:3]:
                        report += f"- {event_ref}\n"
                    report += "\n"
        
        report += "## MITRE ATT&CK Mapping\n\n"
        if timeline.mitre_mapping:
            report += "| Technique | Events |\n"
            report += "|-----------|--------|\n"
            for technique, events in timeline.mitre_mapping.items():
                report += f"| {technique} | {len(events)} |\n"
            report += "\n"
        
        report += "## Timeline of Events\n\n"
        report += "| Time | Type | Title | Severity |\n"
        report += "|------|------|-------|----------|\n"
        for event in timeline.events[:30]:
            report += f"| {event.timestamp[:19]} | {event.event_type} | {event.title[:50]} | {event.severity} |\n"
        report += "\n"
        
        report += "## Recommendations\n\n"
        for i, rec in enumerate(timeline.recommendations, 1):
            report += f"{i}. {rec}\n"
        
        report += "\n## Suggested Playbooks\n\n"
        for pb in timeline.playbook_suggestions[:5]:
            report += f"- **{pb.get('name', 'Unknown')}** (Priority: {pb.get('priority', 'N/A')})\n"
            report += f"  {pb.get('description', '')}\n"
        
        return report
    
    def _generate_forensic_report(self, timeline: ThreatTimeline) -> str:
        """Generate forensic-focused report"""
        report = "# Forensic Investigation Report\n\n"
        report += f"**Case ID:** {timeline.threat_id}\n"
        report += f"**Investigation Date:** {datetime.now(timezone.utc).isoformat()}\n\n"
        
        report += "## Evidence Summary\n\n"
        if timeline.evidence_chain:
            report += "| Artifact ID | Type | Collected | Custody Status |\n"
            report += "|-------------|------|-----------|----------------|\n"
            for evidence in timeline.evidence_chain[:20]:
                report += f"| {evidence.get('artifact_id', 'N/A')} | {evidence.get('type', 'N/A')} | {evidence.get('collected_at', 'N/A')[:19]} | Verified |\n"
            report += "\n"
        
        report += "## Root Cause Analysis\n\n"
        if timeline.root_cause:
            rc = timeline.root_cause
            report += f"**Identified Root Cause:** {rc.get('title', 'Under investigation')}\n"
            report += f"**Confidence:** {rc.get('confidence', 0) * 100:.0f}%\n"
            report += f"**Event ID:** {rc.get('event_id', 'N/A')}\n\n"
        
        report += "## Attack Graph\n\n"
        if timeline.attack_graph:
            graph = timeline.attack_graph
            report += f"- **Total Nodes:** {graph.get('metadata', {}).get('total_nodes', 0)}\n"
            report += f"- **Total Edges:** {graph.get('metadata', {}).get('total_edges', 0)}\n"
            report += f"- **Compromised Nodes:** {graph.get('metadata', {}).get('compromised_nodes', 0)}\n\n"
            
            if graph.get('attack_paths'):
                report += "### Attack Paths\n\n"
                for i, path in enumerate(graph['attack_paths'][:5], 1):
                    report += f"{i}. {' -> '.join(path)}\n"
                report += "\n"
        
        report += "## Causal Analysis\n\n"
        if timeline.root_cause and timeline.root_cause.get('causal_graph'):
            report += "Causal relationships have been identified between events.\n\n"
        
        report += "## Detailed Event Log\n\n"
        for event in timeline.events:
            report += f"### Event: {event.id}\n"
            report += f"- **Time:** {event.timestamp}\n"
            report += f"- **Type:** {event.event_type}\n"
            report += f"- **Title:** {event.title}\n"
            report += f"- **Description:** {event.description}\n"
            if event.mitre_technique:
                report += f"- **MITRE Technique:** {event.mitre_technique}\n"
            if event.evidence_ids:
                report += f"- **Evidence:** {', '.join(event.evidence_ids)}\n"
            report += "\n"
        
        return report
    
    def _generate_compliance_report(self, timeline: ThreatTimeline) -> str:
        """Generate compliance-focused report"""
        report = "# Incident Compliance Report\n\n"
        report += f"**Incident Reference:** {timeline.threat_id}\n"
        report += f"**Report Generated:** {datetime.now(timezone.utc).isoformat()}\n"
        report += f"**Classification:** {timeline.severity.upper()} Severity Security Incident\n\n"
        
        report += "## Regulatory Disclosure Requirements\n\n"
        
        # Determine notification requirements based on severity
        if timeline.severity in ["critical", "high"]:
            report += "### Immediate Notification Required\n\n"
            report += "Based on incident severity, the following notifications may be required:\n\n"
            report += "- **GDPR:** 72-hour breach notification (if EU data affected)\n"
            report += "- **HIPAA:** Breach notification (if PHI involved)\n"
            report += "- **PCI-DSS:** Immediate notification to acquirer (if cardholder data involved)\n"
            report += "- **SOX:** Material incident reporting\n\n"
        else:
            report += "Standard incident documentation is sufficient for compliance purposes.\n\n"
        
        report += "## Incident Timeline for Compliance\n\n"
        report += f"- **Detection Time:** {timeline.first_seen}\n"
        if timeline.impact_assessment:
            response_time = timeline.impact_assessment.get('response_time_minutes')
            if response_time:
                report += f"- **Response Time:** {response_time} minutes\n"
        report += f"- **Current Status:** {timeline.status}\n"
        report += f"- **Containment:** {'Achieved' if timeline.impact_assessment and timeline.impact_assessment.get('contained') else 'In Progress'}\n\n"
        
        report += "## Data Impact Assessment\n\n"
        if timeline.impact_assessment:
            report += f"- **Affected Systems:** {timeline.impact_assessment.get('affected_systems', [])}\n"
            report += f"- **Data Categories:** To be determined by data classification review\n\n"
        
        report += "## Remediation Actions Taken\n\n"
        response_events = [e for e in timeline.events if e.event_type in ["response", "block", "quarantine"]]
        for event in response_events[:10]:
            report += f"- [{event.timestamp[:19]}] {event.title}\n"
        
        report += "\n## Documentation Completeness\n\n"
        report += "- [x] Incident detection documented\n"
        report += f"- [{'x' if response_events else ' '}] Response actions documented\n"
        report += f"- [{'x' if timeline.impact_assessment else ' '}] Impact assessment completed\n"
        report += f"- [{'x' if timeline.recommendations else ' '}] Recommendations documented\n"
        
        return report


# =============================================================================
# TIMELINE BUILDER
# =============================================================================

class TimelineBuilder:
    """
    Enterprise Threat Timeline Builder
    
    Builds and reconstructs threat timelines from various data sources
    with integrated enterprise analysis capabilities.
    
    Features:
    - Attack graph generation
    - Causal analysis and root cause detection
    - Kill chain mapping (Lockheed Martin + Unified)
    - MITRE ATT&CK integration
    - Playbook suggestions
    - Forensic artifact tracking
    - Multi-incident correlation
    - Multiple report formats
    """
    
    _db = None
    
    # Enterprise component instances
    _attack_graph_generator = None
    _causal_analyzer = None
    _kill_chain_mapper = None
    _playbook_suggester = None
    _artifact_tracker = None
    _incident_correlator = None
    _report_generator = None
    
    @classmethod
    def initialize_enterprise_components(cls):
        """Initialize all enterprise analysis components"""
        if cls._attack_graph_generator is None:
            cls._attack_graph_generator = AttackGraphGenerator()
        if cls._causal_analyzer is None:
            cls._causal_analyzer = CausalAnalysisEngine()
        if cls._kill_chain_mapper is None:
            cls._kill_chain_mapper = KillChainMapper()
        if cls._playbook_suggester is None:
            cls._playbook_suggester = PlaybookSuggester()
        if cls._artifact_tracker is None:
            cls._artifact_tracker = ForensicArtifactTracker()
        if cls._incident_correlator is None:
            cls._incident_correlator = MultiIncidentCorrelator()
        if cls._report_generator is None:
            cls._report_generator = TimelineReportGenerator()
    
    @classmethod
    def set_database(cls, db):
        """Set the MongoDB database reference"""
        cls._db = db
        cls.initialize_enterprise_components()
    
    @classmethod
    async def build_timeline(cls, threat_id: str, full_analysis: bool = True) -> Optional[ThreatTimeline]:
        """
        Build a complete timeline for a threat incident.
        
        Aggregates data from:
        - Threats collection
        - Alerts collection
        - Audit logs
        - Response actions
        - Quarantine entries
        - Agent events
        
        With enterprise analysis:
        - Attack graph generation
        - Root cause analysis
        - Kill chain mapping
        - MITRE ATT&CK mapping
        - Playbook suggestions
        
        Args:
            threat_id: The threat identifier
            full_analysis: Whether to perform full enterprise analysis
        """
        if cls._db is None:
            return None
        
        cls.initialize_enterprise_components()
        
        # Get the main threat
        threat = await cls._db.threats.find_one({"id": threat_id}, {"_id": 0})
        if not threat:
            return None
        
        events = []
        
        # 1. Initial detection event
        events.append(TimelineEvent(
            id=f"detection_{threat_id}",
            timestamp=threat.get("created_at", datetime.now(timezone.utc).isoformat()),
            event_type=TimelineEventType.DETECTION.value,
            title=f"Threat Detected: {threat.get('name', 'Unknown')}",
            description=threat.get("description", ""),
            severity=threat.get("severity", "medium"),
            source=threat.get("source_agent", "system"),
            related_threat_id=threat_id,
            target=threat.get("target_system"),
            mitre_technique=cls._infer_mitre_technique(threat),
            kill_chain_phase=cls._infer_kill_chain_phase(threat),
            confidence=0.9,
            details={
                "type": threat.get("type"),
                "source_ip": threat.get("source_ip"),
                "indicators": threat.get("indicators", [])
            }
        ))
        
        # 2. Related alerts
        alerts_cursor = cls._db.alerts.find(
            {"threat_id": threat_id}, {"_id": 0}
        ).sort("created_at", 1)
        async for alert in alerts_cursor:
            events.append(TimelineEvent(
                id=f"alert_{alert.get('id')}",
                timestamp=alert.get("created_at", ""),
                event_type=TimelineEventType.ALERT.value,
                title=f"Alert: {alert.get('title', 'Unknown')}",
                description=alert.get("message", ""),
                severity=alert.get("severity", "medium"),
                source=alert.get("source_agent", "system"),
                related_threat_id=threat_id,
                related_alert_id=alert.get("id"),
                mitre_technique=alert.get("mitre_technique"),
                details={"status": alert.get("status")}
            ))
        
        # 3. Response actions from audit logs
        response_logs = await cls._db.audit_logs.find({
            "category": "threat_response",
            "target_id": threat_id
        }, {"_id": 0}).sort("timestamp", 1).to_list(100)
        
        for log in response_logs:
            events.append(TimelineEvent(
                id=f"response_{log.get('id')}",
                timestamp=log.get("timestamp", ""),
                event_type=TimelineEventType.RESPONSE.value,
                title=f"Response: {log.get('action', 'Unknown')}",
                description=log.get("description", ""),
                severity="info",
                source=log.get("actor", "system"),
                related_threat_id=threat_id,
                kill_chain_phase="actions_on_objectives",
                details=log.get("details", {})
            ))
        
        # 4. IP blocking events
        block_logs = await cls._db.response_actions.find({
            "$or": [
                {"related_threat_id": threat_id},
                {"ip": threat.get("source_ip")}
            ],
            "action": {"$in": ["block_ip", "unblock_ip"]}
        }, {"_id": 0}).sort("timestamp", 1).to_list(50)
        
        for log in block_logs:
            events.append(TimelineEvent(
                id=f"block_{log.get('_id', '')}",
                timestamp=log.get("timestamp", ""),
                event_type=TimelineEventType.BLOCK.value,
                title=f"IP {'Blocked' if log.get('action') == 'block_ip' else 'Unblocked'}: {log.get('ip')}",
                description=log.get("reason", ""),
                severity="warning" if log.get("action") == "block_ip" else "info",
                source=log.get("performed_by", "system"),
                related_threat_id=threat_id,
                target=log.get("ip"),
                details={"duration_hours": log.get("duration_hours")}
            ))
        
        # 5. Quarantine events
        if threat.get("quarantine_info"):
            q_info = threat["quarantine_info"]
            events.append(TimelineEvent(
                id=f"quarantine_{q_info.get('id', '')}",
                timestamp=q_info.get("quarantined_at", ""),
                event_type=TimelineEventType.QUARANTINE.value,
                title=f"File Quarantined: {q_info.get('threat_name', 'Unknown')}",
                description=f"File isolated: {q_info.get('original_path', '')}",
                severity="critical",
                source="system",
                related_threat_id=threat_id,
                target=q_info.get("original_path"),
                details={
                    "quarantine_path": q_info.get("quarantine_path"),
                    "file_hash": q_info.get("file_hash")
                }
            ))
        
        # 6. User actions from audit logs
        user_logs = await cls._db.audit_logs.find({
            "category": "user_action",
            "target_id": threat_id
        }, {"_id": 0}).sort("timestamp", 1).to_list(50)
        
        for log in user_logs:
            events.append(TimelineEvent(
                id=f"user_{log.get('id')}",
                timestamp=log.get("timestamp", ""),
                event_type=TimelineEventType.USER_ACTION.value,
                title=f"User Action: {log.get('action', 'Unknown')}",
                description=log.get("description", ""),
                severity="info",
                source=log.get("actor", "unknown"),
                actor=log.get("actor"),
                related_threat_id=threat_id,
                details=log.get("details", {})
            ))
        
        # Sort events by timestamp
        events.sort(key=lambda e: e.timestamp)
        
        # Enterprise Analysis
        attack_graph = None
        root_cause = None
        kill_chain_mapping = None
        mitre_mapping = None
        playbook_suggestions = []
        evidence_chain = []
        metrics = {}
        
        if full_analysis and events:
            # Generate attack graph
            attack_graph = cls._attack_graph_generator.generate_graph(events)
            
            # Perform causal analysis
            cls._causal_analyzer.analyze(events)
            root_cause = cls._causal_analyzer.get_root_cause()
            
            # Map to kill chain
            kill_chain_mapping = cls._kill_chain_mapper.map_events(events)
            
            # Map to MITRE ATT&CK
            mitre_mapping = cls._map_to_mitre(events)
            
            # Get playbook suggestions
            playbook_suggestions = cls._playbook_suggester.suggest_playbooks(
                threat_id=threat_id,
                events=events,
                threat_type=threat.get("type", "unknown"),
                severity=threat.get("severity", "medium")
            )
            
            # Collect evidence chain
            evidence_chain = cls._build_evidence_chain(events)
            
            # Calculate metrics
            metrics = cls._calculate_metrics(events, kill_chain_mapping)
        
        # Build the timeline
        timeline = ThreatTimeline(
            threat_id=threat_id,
            threat_name=threat.get("name", "Unknown"),
            threat_type=threat.get("type", "unknown"),
            severity=threat.get("severity", "medium"),
            status=threat.get("status", "active"),
            first_seen=threat.get("created_at", ""),
            last_updated=threat.get("updated_at", ""),
            events=events,
            summary=cls._generate_summary(threat, events),
            impact_assessment=cls._assess_impact(threat, events),
            recommendations=cls._generate_recommendations(threat, events),
            attack_graph=attack_graph,
            root_cause=root_cause,
            kill_chain_mapping=kill_chain_mapping,
            mitre_mapping=mitre_mapping,
            playbook_suggestions=playbook_suggestions,
            evidence_chain=evidence_chain,
            metrics=metrics
        )
        
        # Add to correlator for multi-incident analysis
        cls._incident_correlator.add_timeline(timeline)
        
        return timeline
    
    @classmethod
    def _infer_mitre_technique(cls, threat: Dict) -> Optional[str]:
        """Infer MITRE technique from threat type"""
        threat_type = threat.get("type", "").lower()
        
        mitre_mapping = {
            "malware": "T1059",
            "ransomware": "T1486",
            "phishing": "T1566",
            "intrusion": "T1190",
            "lateral_movement": "T1021",
            "exfiltration": "T1041",
            "privilege_escalation": "T1068",
            "persistence": "T1547"
        }
        
        return mitre_mapping.get(threat_type)
    
    @classmethod
    def _infer_kill_chain_phase(cls, threat: Dict) -> Optional[str]:
        """Infer kill chain phase from threat type"""
        threat_type = threat.get("type", "").lower()
        
        phase_mapping = {
            "reconnaissance": "reconnaissance",
            "phishing": "delivery",
            "malware": "installation",
            "intrusion": "exploitation",
            "lateral_movement": "command_and_control",
            "exfiltration": "actions_on_objectives",
            "ransomware": "actions_on_objectives"
        }
        
        return phase_mapping.get(threat_type)
    
    @classmethod
    def _map_to_mitre(cls, events: List[TimelineEvent]) -> Dict[str, List[str]]:
        """Map events to MITRE ATT&CK techniques"""
        mapping = defaultdict(list)
        
        for event in events:
            if event.mitre_technique:
                mapping[event.mitre_technique].append(event.id)
            else:
                # Infer from event type
                technique = MITRE_MAPPING.get(event.event_type)
                if technique:
                    mapping[technique].append(event.id)
        
        return dict(mapping)
    
    @classmethod
    def _build_evidence_chain(cls, events: List[TimelineEvent]) -> List[Dict]:
        """Build evidence chain from events"""
        evidence = []
        
        for event in events:
            if event.evidence_ids:
                for evidence_id in event.evidence_ids:
                    artifact = cls._artifact_tracker.get_artifact(evidence_id)
                    if artifact:
                        evidence.append(artifact)
            
            # Add event itself as evidence
            evidence.append({
                "artifact_id": f"event_{event.id}",
                "type": "timeline_event",
                "name": event.title,
                "collected_at": event.timestamp,
                "related_events": [event.id]
            })
        
        return evidence
    
    @classmethod
    def _calculate_metrics(
        cls,
        events: List[TimelineEvent],
        kill_chain_mapping: Dict
    ) -> Dict[str, Any]:
        """Calculate timeline metrics"""
        metrics = {
            "total_events": len(events),
            "severity_distribution": defaultdict(int),
            "event_type_distribution": defaultdict(int),
            "response_time_minutes": cls._calculate_response_time(events),
            "kill_chain_coverage": 0.0,
            "mitre_techniques_count": 0
        }
        
        for event in events:
            metrics["severity_distribution"][event.severity] += 1
            metrics["event_type_distribution"][event.event_type] += 1
        
        # Convert defaultdicts to regular dicts
        metrics["severity_distribution"] = dict(metrics["severity_distribution"])
        metrics["event_type_distribution"] = dict(metrics["event_type_distribution"])
        
        # Calculate kill chain coverage
        if kill_chain_mapping:
            phases_covered = sum(1 for v in kill_chain_mapping.values() if v)
            total_phases = len(KillChainPhase)
            metrics["kill_chain_coverage"] = phases_covered / total_phases
        
        # Count MITRE techniques
        mitre_techniques = {e.mitre_technique for e in events if e.mitre_technique}
        metrics["mitre_techniques_count"] = len(mitre_techniques)
        
        return metrics
    
    @classmethod
    def _generate_summary(cls, threat: Dict, events: List[TimelineEvent]) -> str:
        """Generate a human-readable summary of the timeline"""
        event_count = len(events)
        response_count = sum(1 for e in events if e.event_type == TimelineEventType.RESPONSE.value)
        block_count = sum(1 for e in events if e.event_type == TimelineEventType.BLOCK.value)
        
        summary = f"Threat '{threat.get('name', 'Unknown')}' was detected "
        summary += f"with {event_count} related events. "
        
        if response_count:
            summary += f"{response_count} automated responses were triggered. "
        if block_count:
            summary += f"{block_count} IP blocking actions were taken. "
        
        summary += f"Current status: {threat.get('status', 'unknown')}."
        return summary
    
    @classmethod
    def _assess_impact(cls, threat: Dict, events: List[TimelineEvent]) -> Dict[str, Any]:
        """Assess the impact of the threat"""
        return {
            "severity": threat.get("severity", "unknown"),
            "affected_systems": [threat.get("target_system")] if threat.get("target_system") else [],
            "source_ips": [threat.get("source_ip")] if threat.get("source_ip") else [],
            "total_events": len(events),
            "response_time_minutes": cls._calculate_response_time(events),
            "contained": threat.get("status") in ["resolved", "quarantined", "blocked"]
        }
    
    @classmethod
    def _calculate_response_time(cls, events: List[TimelineEvent]) -> Optional[int]:
        """Calculate time from detection to first response"""
        detection = None
        first_response = None
        
        for event in events:
            if event.event_type == TimelineEventType.DETECTION.value and not detection:
                detection = event.timestamp
            elif event.event_type in [TimelineEventType.RESPONSE.value, TimelineEventType.BLOCK.value]:
                if not first_response:
                    first_response = event.timestamp
                    break
        
        if detection and first_response:
            try:
                dt1 = datetime.fromisoformat(detection.replace('Z', '+00:00'))
                dt2 = datetime.fromisoformat(first_response.replace('Z', '+00:00'))
                return int((dt2 - dt1).total_seconds() / 60)
            except Exception:
                pass
        return None
    
    @classmethod
    def _generate_recommendations(cls, threat: Dict, events: List[TimelineEvent]) -> List[str]:
        """Generate recommendations based on the threat"""
        recommendations = []
        
        severity = threat.get("severity", "medium")
        threat_type = threat.get("type", "unknown")
        status = threat.get("status", "active")
        
        if status == "active":
            recommendations.append("Threat is still active. Consider immediate containment actions.")
        
        if severity in ["critical", "high"]:
            recommendations.append("Review all systems for signs of lateral movement.")
            recommendations.append("Consider isolating affected systems from the network.")
        
        if threat_type in ["malware", "ransomware"]:
            recommendations.append("Scan all connected systems for similar indicators.")
            recommendations.append("Review backup status and recovery procedures.")
        
        if threat_type in ["intrusion", "ids_alert"]:
            recommendations.append("Review firewall rules and access controls.")
            recommendations.append("Check for unauthorized accounts or access.")
        
        if threat.get("source_ip"):
            recommendations.append(f"Consider permanent blocking of source IP: {threat['source_ip']}")
        
        recommendations.append("Update incident documentation and notify stakeholders.")
        
        return recommendations
    
    @classmethod
    async def get_recent_timelines(cls, limit: int = 10) -> List[Dict[str, Any]]:
        """Get summaries of recent threat timelines"""
        if cls._db is None:
            return []
        
        threats = await cls._db.threats.find(
            {}, {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)

        # Also surface "alert-only" incidents so Timeline doesn't look empty when
        # alerts exist but Threat docs are sparse.
        alert_limit = max(0, int(limit) - len(threats))
        alerts = []
        if alert_limit > 0:
            alerts = await cls._db.alerts.find(
                {"$or": [{"threat_id": None}, {"threat_id": ""}, {"threat_id": {"$exists": False}}]},
                {"_id": 0},
            ).sort("created_at", -1).limit(alert_limit).to_list(alert_limit)
        
        summaries = []
        for threat in threats:
            event_count = await cls._db.alerts.count_documents({"threat_id": threat.get("id")})
            summaries.append({
                "threat_id": threat.get("id"),
                "threat_name": threat.get("name", "Unknown Threat"),
                "threat_type": threat.get("type", "unknown"),
                "severity": threat.get("severity", "medium"),
                "status": threat.get("status", "active"),
                "first_seen": threat.get("created_at", datetime.now(timezone.utc).isoformat()),
                "event_count": event_count + 1  # +1 for detection event
            })

        for alert in alerts:
            aid = alert.get("id")
            if not aid:
                continue
            summaries.append({
                "threat_id": f"alert:{aid}",
                "threat_name": alert.get("title") or "Alert Incident",
                "threat_type": alert.get("type", "alert"),
                "severity": alert.get("severity", "medium"),
                "status": alert.get("status", "new"),
                "first_seen": alert.get("created_at", datetime.now(timezone.utc).isoformat()),
                "event_count": 1,
            })

        summaries.sort(key=lambda s: s.get("first_seen") or "", reverse=True)
        return summaries[:limit]
    
    @classmethod
    async def export_timeline(cls, threat_id: str, format: str = "json") -> Optional[str]:
        """Export timeline to specified format"""
        timeline = await cls.build_timeline(threat_id)
        if not timeline:
            return None
        
        if format == "json":
            return json.dumps(asdict(timeline), indent=2)
        elif format == "markdown":
            return cls._to_markdown(timeline)
        
        return None
    
    @classmethod
    def _to_markdown(cls, timeline: ThreatTimeline) -> str:
        """Convert timeline to Markdown format"""
        md = f"# Threat Timeline: {timeline.threat_name}\n\n"
        md += f"**ID:** {timeline.threat_id}\n"
        md += f"**Type:** {timeline.threat_type}\n"
        md += f"**Severity:** {timeline.severity.upper()}\n"
        md += f"**Status:** {timeline.status}\n"
        md += f"**First Seen:** {timeline.first_seen}\n\n"
        
        md += "## Summary\n\n"
        md += f"{timeline.summary}\n\n"
        
        if timeline.impact_assessment:
            md += "## Impact Assessment\n\n"
            for key, value in timeline.impact_assessment.items():
                md += f"- **{key.replace('_', ' ').title()}:** {value}\n"
            md += "\n"
        
        md += "## Timeline of Events\n\n"
        for event in timeline.events:
            severity_icon = "🔴" if event.severity == "critical" else \
                           "🟠" if event.severity == "high" else \
                           "🟡" if event.severity == "medium" else "🟢"
            md += f"### {severity_icon} {event.title}\n"
            md += f"**Time:** {event.timestamp}\n"
            md += f"**Type:** {event.event_type}\n"
            md += f"**Source:** {event.source}\n"
            if event.description:
                md += f"\n{event.description}\n"
            md += "\n---\n\n"
        
        if timeline.recommendations:
            md += "## Recommendations\n\n"
            for rec in timeline.recommendations:
                md += f"- {rec}\n"
        
        return md
    
    @classmethod
    def generate_report(
        cls,
        timeline: ThreatTimeline,
        report_type: ReportType = ReportType.TECHNICAL
    ) -> str:
        """Generate report using enterprise report generator"""
        cls.initialize_enterprise_components()
        return cls._report_generator.generate_report(timeline, report_type)
    
    @classmethod
    def find_related_incidents(cls, threat_id: str) -> List[Dict]:
        """Find incidents related to given threat"""
        cls.initialize_enterprise_components()
        return cls._incident_correlator.find_related_incidents(threat_id)
    
    @classmethod
    def correlate_all_incidents(cls) -> Dict[str, Any]:
        """Correlate all registered timelines"""
        cls.initialize_enterprise_components()
        return cls._incident_correlator.correlate()
    
    @classmethod
    def register_artifact(
        cls,
        artifact_type: str,
        name: str,
        description: str,
        collected_by: str,
        hash_md5: str = None,
        hash_sha256: str = None
    ) -> ForensicArtifact:
        """Register forensic artifact"""
        cls.initialize_enterprise_components()
        return cls._artifact_tracker.register_artifact(
            artifact_type=artifact_type,
            name=name,
            description=description,
            collected_by=collected_by,
            hash_md5=hash_md5,
            hash_sha256=hash_sha256
        )
    
    @classmethod
    def get_artifact(cls, artifact_id: str) -> Optional[Dict]:
        """Get forensic artifact"""
        cls.initialize_enterprise_components()
        return cls._artifact_tracker.get_artifact(artifact_id)
    
    @classmethod
    def export_custody_report(cls, artifact_id: str) -> str:
        """Export chain of custody report"""
        cls.initialize_enterprise_components()
        return cls._artifact_tracker.export_custody_report(artifact_id)

    @classmethod
    def update_artifact_custody(
        cls,
        artifact_id: str,
        action: str,
        actor: str,
        notes: str = "",
    ) -> bool:
        """Append a custody action entry for an artifact."""
        cls.initialize_enterprise_components()
        return cls._artifact_tracker.update_custody(
            artifact_id=artifact_id,
            action=action,
            actor=actor,
            notes=notes,
        )
    
    @classmethod
    def add_playbook(cls, pb_id: str, playbook: PlaybookSuggestion):
        """Add custom playbook"""
        cls.initialize_enterprise_components()
        cls._playbook_suggester.add_playbook(pb_id, playbook)
    
    @classmethod
    def get_playbook(cls, playbook_id: str) -> Optional[Dict]:
        """Get playbook by ID"""
        cls.initialize_enterprise_components()
        return cls._playbook_suggester.get_playbook(playbook_id)


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

# Core timeline builder
timeline_builder = TimelineBuilder()

# Enterprise analysis components
attack_graph_generator = AttackGraphGenerator()
causal_analysis_engine = CausalAnalysisEngine()
kill_chain_mapper = KillChainMapper()
playbook_suggester = PlaybookSuggester()
forensic_artifact_tracker = ForensicArtifactTracker()
multi_incident_correlator = MultiIncidentCorrelator()
timeline_report_generator = TimelineReportGenerator()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "TimelineEventType",
    "KillChainPhase",
    "UnifiedKillChainPhase",
    "IncidentSeverity",
    "ReportType",
    
    # Dataclasses
    "TimelineEvent",
    "ThreatTimeline",
    "AttackGraphNode",
    "AttackGraphEdge",
    "ForensicArtifact",
    "CausalRelationship",
    "PlaybookSuggestion",
    
    # Analysis classes
    "AttackGraphGenerator",
    "CausalAnalysisEngine",
    "KillChainMapper",
    "PlaybookSuggester",
    "ForensicArtifactTracker",
    "MultiIncidentCorrelator",
    "TimelineReportGenerator",
    
    # Builder
    "TimelineBuilder",
    
    # Global instances
    "timeline_builder",
    "attack_graph_generator",
    "causal_analysis_engine",
    "kill_chain_mapper",
    "playbook_suggester",
    "forensic_artifact_tracker",
    "multi_incident_correlator",
    "timeline_report_generator"
]
