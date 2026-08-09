"""
SOAR (Security Orchestration, Automation and Response) Playbook Engine
with Rogue AI Agentic Defense System

Seraph's differentiation: Advanced AI-driven threat detection and response
specifically designed to counter autonomous AI attackers.

FEATURES:
- Rogue AI Pattern Detection & Response
- Adaptive Defense Escalation Matrix
- Deception Orchestration Pipeline
- Quarantine-to-Forensics Flow
- ML-Integrated Threat Scoring
- Real-time Agent Command Generation
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Callable, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid
import logging
import hashlib
from collections import defaultdict
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from backend.services.telemetry_chain import tamper_evident_telemetry
except Exception:
    try:
        from services.telemetry_chain import tamper_evident_telemetry  # type: ignore
    except Exception:
        tamper_evident_telemetry = None


# =============================================================================
# ENHANCED ENUMS FOR AI AGENTIC DEFENSE
# =============================================================================

class PlaybookAction(str, Enum):
    # Core Actions
    BLOCK_IP = "block_ip"
    KILL_PROCESS = "kill_process"
    QUARANTINE_FILE = "quarantine_file"
    SEND_ALERT = "send_alert"
    ISOLATE_ENDPOINT = "isolate_endpoint"
    COLLECT_FORENSICS = "collect_forensics"
    DISABLE_USER = "disable_user"
    SCAN_ENDPOINT = "scan_endpoint"
    UPDATE_FIREWALL = "update_firewall"
    CREATE_TICKET = "create_ticket"
    
    # AI Agentic Defense Actions
    THROTTLE_CLI = "throttle_cli"
    INJECT_LATENCY = "inject_latency"
    CAPTURE_TRIAGE_BUNDLE = "capture_triage_bundle"
    CAPTURE_MEMORY_SNAPSHOT = "capture_memory_snapshot"
    KILL_PROCESS_TREE = "kill_process_tree"
    TAG_SESSION = "tag_session"
    DEPLOY_DECOY = "deploy_decoy"
    ROTATE_CREDENTIALS = "rotate_credentials"
    ENGAGE_TARPIT = "engage_tarpit"
    FEED_DISINFORMATION = "feed_disinformation"
    ENABLE_ENHANCED_LOGGING = "enable_enhanced_logging"
    SNAPSHOT_NETWORK_STATE = "snapshot_network_state"
    LOCK_SENSITIVE_RESOURCES = "lock_sensitive_resources"
    TRIGGER_CANARY_VALIDATION = "trigger_canary_validation"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    INVOKE_ML_ANALYSIS = "invoke_ml_analysis"
    SYNC_THREAT_INTEL = "sync_threat_intel"
    QUARANTINE_TO_SANDBOX = "quarantine_to_sandbox"
    EXECUTE_CONTAINMENT_CHAIN = "execute_containment_chain"


class PlaybookTrigger(str, Enum):
    # Standard Triggers
    THREAT_DETECTED = "threat_detected"
    MALWARE_FOUND = "malware_found"
    RANSOMWARE_DETECTED = "ransomware_detected"
    SUSPICIOUS_PROCESS = "suspicious_process"
    IOC_MATCH = "ioc_match"
    HONEYPOT_TRIGGERED = "honeypot_triggered"
    ANOMALY_DETECTED = "anomaly_detected"
    MANUAL = "manual"
    
    # AI Agentic Triggers
    AI_BEHAVIOR_DETECTED = "ai_behavior_detected"
    MACHINE_PACED_ACTIVITY = "machine_paced_activity"
    AUTONOMOUS_RECON = "autonomous_recon"
    RAPID_CREDENTIAL_ACCESS = "rapid_credential_access"
    AUTOMATED_LATERAL_MOVEMENT = "automated_lateral_movement"
    AI_EXFILTRATION_PATTERN = "ai_exfiltration_pattern"
    DECEPTION_TOKEN_ACCESS = "deception_token_access"
    GOAL_PERSISTENT_LOOP = "goal_persistent_loop"
    TOOL_CHAIN_SWITCHING = "tool_chain_switching"
    ADAPTIVE_ATTACK_DETECTED = "adaptive_attack_detected"


class PlaybookStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    TESTING = "testing"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    ESCALATED = "escalated"
    AWAITING_APPROVAL = "awaiting_approval"


class DefenseEscalationLevel(str, Enum):
    """Defense escalation levels for graduated response"""
    OBSERVE = "observe"           # Level 0: Monitor only
    DEGRADE = "degrade"           # Level 1: Slow down attacker
    DECEIVE = "deceive"           # Level 2: Feed false information
    CONTAIN = "contain"           # Level 3: Limit blast radius
    ISOLATE = "isolate"           # Level 4: Cut off from network
    ERADICATE = "eradicate"       # Level 5: Full removal


class AIThreatConfidence(str, Enum):
    """Confidence level that threat is AI-driven"""
    LOW = "low"           # < 50% - Could be human
    MEDIUM = "medium"     # 50-70% - Suspicious patterns
    HIGH = "high"         # 70-90% - Likely AI
    CRITICAL = "critical" # > 90% - Almost certainly AI

@dataclass
class PlaybookStep:
    action: PlaybookAction
    params: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 30  # seconds
    continue_on_failure: bool = False
    condition: Optional[str] = None  # e.g., "severity >= high"

@dataclass
class Playbook:
    id: str
    name: str
    description: str
    trigger: PlaybookTrigger
    trigger_conditions: Dict[str, Any]  # e.g., {"severity": ["critical", "high"]}
    steps: List[PlaybookStep]
    status: PlaybookStatus = PlaybookStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "system"
    execution_count: int = 0
    last_executed: Optional[str] = None
    is_template: bool = False
    template_id: Optional[str] = None  # If cloned from a template
    tags: List[str] = field(default_factory=list)
    mitre_techniques: List[str] = field(default_factory=list)
    state_transition_log: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.state_transition_log:
            self.state_transition_log = [
                {
                    "from_status": None,
                    "to_status": self.status.value,
                    "actor": self.created_by,
                    "reason": "playbook created",
                    "timestamp": self.created_at,
                }
            ]

@dataclass
class PlaybookTemplate:
    id: str
    name: str
    description: str
    category: str  # e.g., "malware", "ransomware", "network", "compliance"
    trigger: PlaybookTrigger
    trigger_conditions: Dict[str, Any]
    steps: List[PlaybookStep]
    tags: List[str]
    mitre_techniques: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    use_count: int = 0
    is_official: bool = False  # Official templates from the system

@dataclass
class PlaybookExecution:
    id: str
    playbook_id: str
    playbook_name: str
    trigger_event: Dict[str, Any]
    status: ExecutionStatus
    started_at: str
    completed_at: Optional[str] = None
    step_results: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    escalation_level: DefenseEscalationLevel = DefenseEscalationLevel.OBSERVE
    ai_confidence: Optional[float] = None
    quarantine_refs: List[str] = field(default_factory=list)  # Links to quarantined items
    forensics_refs: List[str] = field(default_factory=list)   # Links to forensics data
    state_transition_log: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.state_transition_log:
            self.state_transition_log = [
                {
                    "from_status": None,
                    "to_status": self.status.value,
                    "actor": "system:soar-engine",
                    "reason": "execution created",
                    "timestamp": self.started_at,
                }
            ]


# =============================================================================
# AI AGENTIC DEFENSE DATACLASSES
# =============================================================================

@dataclass
class AIThreatAssessment:
    """Assessment of AI-driven threat characteristics"""
    session_id: str
    host_id: str
    machine_likelihood: float           # 0-1 probability this is AI
    confidence_level: AIThreatConfidence
    burstiness_score: float             # How bursty the activity is
    tool_switch_latency_ms: float       # Time between tool switches
    goal_persistence: float             # How persistent toward goal
    dominant_intents: List[str]         # Detected intents (recon, lateral_movement, etc.)
    decoy_touched: bool                 # Did they touch a honey token?
    recommended_escalation: DefenseEscalationLevel
    assessment_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            "confidence_level": self.confidence_level.value,
            "recommended_escalation": self.recommended_escalation.value
        }


@dataclass
class QuarantinePipelineItem:
    """Item flowing through the quarantine-to-forensics pipeline"""
    item_id: str
    item_type: str  # "file", "process", "memory_dump", "network_capture"
    source_host: str
    source_path: Optional[str]
    quarantine_path: Optional[str]
    hash_sha256: Optional[str]
    hash_md5: Optional[str]
    size_bytes: int
    quarantined_at: str
    playbook_id: str
    execution_id: str
    
    # Pipeline stages
    stage: str = "quarantined"  # quarantined -> scanning -> analyzed -> stored
    scan_results: Dict[str, Any] = field(default_factory=dict)
    sandbox_results: Dict[str, Any] = field(default_factory=dict)
    threat_intel_hits: List[Dict] = field(default_factory=list)
    forensics_complete: bool = False
    retention_days: int = 90
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DefenseEscalationState:
    """Current defense escalation state for a host/session"""
    host_id: str
    session_id: Optional[str]
    current_level: DefenseEscalationLevel
    level_history: List[Dict]  # [{level, timestamp, reason}]
    active_measures: List[str]  # Currently active defense measures
    escalated_at: str
    auto_de_escalate_after: Optional[str]  # When to auto-reduce level
    requires_human_approval_for: List[str]  # Actions requiring approval
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["current_level"] = self.current_level.value
        return d

class SOAREngine:
    """
    Security Orchestration, Automation and Response Engine
    
    Features:
    - Standard playbook management (create, update, delete, execute)
    - AI Agentic Defense System for countering autonomous attackers
    - Defense Escalation Matrix with graduated response
    - Quarantine-to-Forensics Pipeline integration
    - Deception Orchestration
    - ML-Integrated threat scoring
    """
    
    def __init__(self):
        self.playbooks: Dict[str, Playbook] = {}
        self.templates: Dict[str, PlaybookTemplate] = {}
        self.executions: List[PlaybookExecution] = []
        
        # AI Agentic Defense State
        self.escalation_states: Dict[str, DefenseEscalationState] = {}  # host_id -> state
        self.ai_threat_assessments: Dict[str, AIThreatAssessment] = {}  # session_id -> assessment
        self.quarantine_pipeline: Dict[str, QuarantinePipelineItem] = {}  # item_id -> item
        
        # Defense escalation thresholds
        self.ai_thresholds = {
            "machine_likelihood_medium": 0.50,
            "machine_likelihood_high": 0.70,
            "machine_likelihood_critical": 0.90,
            "burstiness_high": 0.70,
            "tool_switch_fast_ms": 300,
            "goal_persistence_high": 0.70
        }
        
        # Actions requiring human approval at each level
        self.approval_matrix = {
            DefenseEscalationLevel.OBSERVE: [],
            DefenseEscalationLevel.DEGRADE: [],
            DefenseEscalationLevel.DECEIVE: [],
            DefenseEscalationLevel.CONTAIN: ["isolate_endpoint"],
            DefenseEscalationLevel.ISOLATE: [],
            DefenseEscalationLevel.ERADICATE: ["kill_process_tree", "wipe_session"]
        }
        
        self._init_default_playbooks()
        self._init_ai_defense_playbooks()
        self._init_templates()
        self._ensure_mitre_live_response_playbook()

    def _artifacts_dir(self) -> Path:
        return Path(os.environ.get("SERAPH_ARTIFACTS_DIR", "/var/lib/seraph-ai/artifacts"))

    def _archive_path(self) -> Path:
        return Path(
            os.environ.get(
                "MITRE_ARCHIVED_SOAR_EXECUTION_PATH",
                os.environ.get(
                    "SIGMA_SOAR_EXECUTION_ARCHIVE_PATH",
                    str(self._artifacts_dir() / "soar_executions_archive.json"),
                ),
            )
        )

    def _persist_execution_archive(self, execution: "PlaybookExecution") -> None:
        """Best-effort persistence of SOAR executions to a JSON archive.

        This archive is used as "live SOAR response evidence" for MITRE S5 gating.
        """
        try:
            path = self._archive_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            existing: List[Dict[str, Any]] = []
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(payload, list):
                        existing = payload
                except Exception:
                    existing = []

            exec_dict = asdict(execution)
            if isinstance(exec_dict.get("trigger_event"), dict):
                exec_dict["trigger_event"].pop("_id", None)

            by_id = {row.get("id"): row for row in existing if isinstance(row, dict) and row.get("id")}
            by_id[exec_dict.get("id")] = exec_dict
            path.write_text(json.dumps(list(by_id.values()), indent=2), encoding="utf-8")
        except Exception:
            return

    def _write_trace_artifact(self, trace: Optional[Dict[str, Any]], execution_id: str) -> None:
        if not trace:
            return
        try:
            out_dir = self._artifacts_dir() / "telemetry" / "soar"
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{execution_id}.trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
        except Exception:
            return

    def _ensure_mitre_live_response_playbook(self) -> None:
        """Playbook used to generate *live* response evidence for a technique.

        Executions of this playbook are archived and counted as SOAR linkage for MITRE S5.
        """
        playbook_id = "mitre_s5_live_response"
        if playbook_id in self.playbooks:
            return
        self.playbooks[playbook_id] = Playbook(
            id=playbook_id,
            name="MITRE S5 Live SOAR Response",
            description="Minimal but explicit response chain used to attach live SOAR response evidence to validated MITRE techniques.",
            trigger=PlaybookTrigger.MANUAL,
            trigger_conditions={},
            steps=[
                PlaybookStep(action=PlaybookAction.TAG_SESSION, params={"tags": ["mitre_s5", "soar_response"]}, timeout=5, continue_on_failure=True),
                PlaybookStep(action=PlaybookAction.ENABLE_ENHANCED_LOGGING, params={"level": "verbose", "network_capture": True}, timeout=10, continue_on_failure=True),
                PlaybookStep(action=PlaybookAction.UPDATE_FIREWALL, params={"rule_type": "rate_limit", "scope": "mitre_s5_live"}, timeout=30, continue_on_failure=True),
                PlaybookStep(action=PlaybookAction.ISOLATE_ENDPOINT, params={"block_network": False, "hard_isolation": False, "preserve_state": True}, timeout=30, continue_on_failure=True),
                PlaybookStep(action=PlaybookAction.COLLECT_FORENSICS, params={"process_tree": True, "network": True}, timeout=60, continue_on_failure=True),
                PlaybookStep(action=PlaybookAction.CREATE_TICKET, params={"category": "mitre_s5_response_link", "priority": "P2"}, timeout=10, continue_on_failure=True),
                PlaybookStep(action=PlaybookAction.SEND_ALERT, params={"channels": ["slack"], "priority": "medium", "template": "mitre_s5_live"}, timeout=10, continue_on_failure=True),
            ],
            tags=["mitre", "soar", "response", "evidence"],
            mitre_techniques=[],
        )
    
    def _init_default_playbooks(self):
        """Initialize default playbooks"""
        # Malware Response Playbook
        self.playbooks["pb_malware_response"] = Playbook(
            id="pb_malware_response",
            name="Malware Auto-Response",
            description="Automatically quarantine malware and alert security team",
            trigger=PlaybookTrigger.MALWARE_FOUND,
            trigger_conditions={"severity": ["critical", "high", "medium"]},
            steps=[
                PlaybookStep(
                    action=PlaybookAction.QUARANTINE_FILE,
                    params={"auto": True},
                    timeout=60
                ),
                PlaybookStep(
                    action=PlaybookAction.SCAN_ENDPOINT,
                    params={"full_scan": True},
                    timeout=300,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack", "email"], "priority": "high"}
                ),
                PlaybookStep(
                    action=PlaybookAction.CREATE_TICKET,
                    params={"category": "malware", "auto_assign": True}
                )
            ]
        )
        
        # Ransomware Response Playbook
        self.playbooks["pb_ransomware_response"] = Playbook(
            id="pb_ransomware_response",
            name="Ransomware Emergency Response",
            description="Isolate endpoint, kill process, and escalate immediately",
            trigger=PlaybookTrigger.RANSOMWARE_DETECTED,
            trigger_conditions={"severity": ["critical"]},
            steps=[
                PlaybookStep(
                    action=PlaybookAction.KILL_PROCESS,
                    params={"force": True},
                    timeout=10
                ),
                PlaybookStep(
                    action=PlaybookAction.ISOLATE_ENDPOINT,
                    params={"network": True, "usb": True},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.COLLECT_FORENSICS,
                    params={"memory_dump": True, "disk_image": False},
                    timeout=120,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack", "email", "sms"], "priority": "critical"}
                )
            ]
        )
        
        # IOC Match Response
        self.playbooks["pb_ioc_response"] = Playbook(
            id="pb_ioc_response",
            name="IOC Match Response",
            description="Block IPs and update firewall when IOC is matched",
            trigger=PlaybookTrigger.IOC_MATCH,
            trigger_conditions={"ioc_type": ["ip", "domain"], "confidence": ["high"]},
            steps=[
                PlaybookStep(
                    action=PlaybookAction.BLOCK_IP,
                    params={"duration": 86400},  # 24 hours
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.UPDATE_FIREWALL,
                    params={"rule_type": "block"},
                    timeout=60
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack"], "priority": "medium"}
                )
            ]
        )
        
        # Suspicious Process Response
        self.playbooks["pb_suspicious_process"] = Playbook(
            id="pb_suspicious_process",
            name="Suspicious Process Response",
            description="Investigate and potentially kill suspicious processes",
            trigger=PlaybookTrigger.SUSPICIOUS_PROCESS,
            trigger_conditions={"confidence": ["high"]},
            steps=[
                PlaybookStep(
                    action=PlaybookAction.COLLECT_FORENSICS,
                    params={"process_info": True, "network_connections": True},
                    timeout=60
                ),
                PlaybookStep(
                    action=PlaybookAction.KILL_PROCESS,
                    params={"force": False},
                    timeout=10,
                    condition="confidence >= 0.9"
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack"], "priority": "medium"}
                )
            ]
        )
        
        # Honeypot Alert Playbook
        self.playbooks["pb_honeypot_alert"] = Playbook(
            id="pb_honeypot_alert",
            name="Honeypot Alert Response",
            description="Respond to honeypot triggers with intelligence gathering",
            trigger=PlaybookTrigger.HONEYPOT_TRIGGERED,
            trigger_conditions={},
            steps=[
                PlaybookStep(
                    action=PlaybookAction.COLLECT_FORENSICS,
                    params={"attacker_info": True, "techniques": True},
                    timeout=120
                ),
                PlaybookStep(
                    action=PlaybookAction.BLOCK_IP,
                    params={"duration": 604800},  # 7 days
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack", "email"], "priority": "high"}
                ),
                PlaybookStep(
                    action=PlaybookAction.CREATE_TICKET,
                    params={"category": "honeypot", "include_iocs": True}
                )
            ]
        )
    
    def _init_ai_defense_playbooks(self):
        """
        Initialize AI Agentic Defense Playbooks
        
        These playbooks are specifically designed to counter autonomous AI attackers
        with graduated response levels and adaptive defense measures.
        """
        
        # =====================================================================
        # LEVEL 1: OBSERVE & DEGRADE - Machine-Paced Recon Loop
        # =====================================================================
        self.playbooks["ai_recon_degrade_01"] = Playbook(
            id="ai_recon_degrade_01",
            name="AI Recon Loop - Degrade & Observe",
            description="Detected machine-paced reconnaissance. Degrade performance while observing.",
            trigger=PlaybookTrigger.AUTONOMOUS_RECON,
            trigger_conditions={
                "machine_likelihood": ["high", "critical"],
                "intents": ["recon", "enumeration"],
                "burstiness": ["high"]
            },
            steps=[
                PlaybookStep(
                    action=PlaybookAction.TAG_SESSION,
                    params={"tags": ["ai_suspected", "recon", "level_1"]},
                    timeout=5
                ),
                PlaybookStep(
                    action=PlaybookAction.ENABLE_ENHANCED_LOGGING,
                    params={"level": "verbose", "include_keystrokes": True, "network_capture": True},
                    timeout=10
                ),
                PlaybookStep(
                    action=PlaybookAction.THROTTLE_CLI,
                    params={"rate_per_min": 20, "mode": "soft"},
                    timeout=10
                ),
                PlaybookStep(
                    action=PlaybookAction.INJECT_LATENCY,
                    params={"delay_ms": 250, "jitter_ms": 200, "mode": "soft"},
                    timeout=10
                ),
                PlaybookStep(
                    action=PlaybookAction.CAPTURE_TRIAGE_BUNDLE,
                    params={"window_s": 60, "include": ["processes", "network", "files"]},
                    timeout=90,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.INVOKE_ML_ANALYSIS,
                    params={"model": "ai_behavior_classifier", "continuous": True},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack"], "priority": "medium", "template": "ai_recon_detected"},
                    timeout=30
                )
            ],
            tags=["ai_defense", "recon", "level_1", "degrade"]
        )
        
        # =====================================================================
        # LEVEL 2: DECEIVE - Credential Access Pattern
        # =====================================================================
        self.playbooks["ai_cred_access_01"] = Playbook(
            id="ai_cred_access_01",
            name="AI Credential Access - Deceive & Monitor",
            description="AI attempting credential harvesting. Deploy decoys and monitor.",
            trigger=PlaybookTrigger.RAPID_CREDENTIAL_ACCESS,
            trigger_conditions={
                "machine_likelihood": ["high", "critical"],
                "intents": ["credential_access", "credential_dumping"]
            },
            steps=[
                PlaybookStep(
                    action=PlaybookAction.TAG_SESSION,
                    params={"tags": ["ai_suspected", "credential_access", "level_2"]},
                    timeout=5
                ),
                PlaybookStep(
                    action=PlaybookAction.DEPLOY_DECOY,
                    params={
                        "type": "credentials",
                        "decoys": ["aws_key", "database_cred", "api_token"],
                        "placement": "lsass_adjacent"
                    },
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.THROTTLE_CLI,
                    params={"rate_per_min": 10, "mode": "hard"},
                    timeout=10
                ),
                PlaybookStep(
                    action=PlaybookAction.INJECT_LATENCY,
                    params={"delay_ms": 600, "jitter_ms": 400, "mode": "hard"},
                    timeout=10
                ),
                PlaybookStep(
                    action=PlaybookAction.LOCK_SENSITIVE_RESOURCES,
                    params={"resources": ["sam_database", "lsass_memory", "credential_store"]},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.CAPTURE_TRIAGE_BUNDLE,
                    params={"window_s": 180, "include": ["processes", "memory", "registry"]},
                    timeout=240,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.TRIGGER_CANARY_VALIDATION,
                    params={"validate_all": True},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack", "email"], "priority": "high", "template": "ai_credential_access"},
                    timeout=30
                )
            ],
            tags=["ai_defense", "credential_access", "level_2", "deceive"]
        )
        
        # =====================================================================
        # LEVEL 3: CONTAIN - Autonomous Pivot / Tool Chain Switching
        # =====================================================================
        self.playbooks["ai_pivot_contain_01"] = Playbook(
            id="ai_pivot_contain_01",
            name="AI Lateral Movement - Contain Fast",
            description="AI performing rapid lateral movement or tool switching. Contain blast radius.",
            trigger=PlaybookTrigger.AUTOMATED_LATERAL_MOVEMENT,
            trigger_conditions={
                "machine_likelihood": ["high", "critical"],
                "intents": ["lateral_movement", "privilege_escalation"],
                "tool_switch_latency": ["fast"]
            },
            steps=[
                PlaybookStep(
                    action=PlaybookAction.TAG_SESSION,
                    params={"tags": ["ai_confirmed", "lateral_movement", "level_3", "containment"]},
                    timeout=5
                ),
                PlaybookStep(
                    action=PlaybookAction.SNAPSHOT_NETWORK_STATE,
                    params={"include_flows": True, "include_connections": True},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.UPDATE_FIREWALL,
                    params={
                        "rule_type": "contain",
                        "block_lateral": True,
                        "allow_management": True
                    },
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.LOCK_SENSITIVE_RESOURCES,
                    params={"resources": ["domain_controller", "file_shares", "database_servers"]},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.DISABLE_USER,
                    params={"preserve_session": True, "reason": "ai_containment"},
                    timeout=15
                ),
                PlaybookStep(
                    action=PlaybookAction.CAPTURE_TRIAGE_BUNDLE,
                    params={"window_s": 300, "include": ["processes", "network", "registry", "files"]},
                    timeout=360,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.SYNC_THREAT_INTEL,
                    params={"share_iocs": True, "communities": ["internal", "isac"]},
                    timeout=60,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack", "email", "sms"], "priority": "critical", "template": "ai_lateral_movement"},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.CREATE_TICKET,
                    params={"category": "ai_incident", "priority": "P1", "auto_assign": True},
                    timeout=30
                )
            ],
            tags=["ai_defense", "lateral_movement", "level_3", "contain"]
        )
        
        # =====================================================================
        # LEVEL 4: ISOLATE - Data Exfiltration Preparation
        # =====================================================================
        self.playbooks["ai_exfil_cut_01"] = Playbook(
            id="ai_exfil_cut_01",
            name="AI Exfil Prep - Cut Egress",
            description="AI staging data for exfiltration. Cut egress immediately.",
            trigger=PlaybookTrigger.AI_EXFILTRATION_PATTERN,
            trigger_conditions={
                "machine_likelihood": ["high", "critical"],
                "intents": ["exfil_prep", "data_staging", "compression"]
            },
            steps=[
                PlaybookStep(
                    action=PlaybookAction.TAG_SESSION,
                    params={"tags": ["ai_confirmed", "exfiltration", "level_4", "critical"]},
                    timeout=5
                ),
                PlaybookStep(
                    action=PlaybookAction.ISOLATE_ENDPOINT,
                    params={"block_network": True, "allow_management": True, "preserve_state": True},
                    timeout=15
                ),
                PlaybookStep(
                    action=PlaybookAction.CAPTURE_MEMORY_SNAPSHOT,
                    params={"mode": "full", "priority": "high"},
                    timeout=300,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.CAPTURE_TRIAGE_BUNDLE,
                    params={"window_s": 600, "include": ["processes", "network", "files", "memory"]},
                    timeout=660,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.QUARANTINE_FILE,
                    params={"paths": "staged_data", "auto_sandbox": True},
                    timeout=120
                ),
                PlaybookStep(
                    action=PlaybookAction.QUARANTINE_TO_SANDBOX,
                    params={"analyze": True, "detonation_time": 300},
                    timeout=360,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.ESCALATE_TO_HUMAN,
                    params={"reason": "ai_exfiltration_attempt", "required": True},
                    timeout=5
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack", "email", "sms"], "priority": "critical", "template": "ai_exfiltration"},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.CREATE_TICKET,
                    params={"category": "ai_exfiltration", "priority": "P0", "escalate_to_ciso": True},
                    timeout=30
                )
            ],
            tags=["ai_defense", "exfiltration", "level_4", "isolate"]
        )
        
        # =====================================================================
        # LEVEL 5: ERADICATE - High Confidence Complete Containment
        # =====================================================================
        self.playbooks["ai_highconf_eradicate_01"] = Playbook(
            id="ai_highconf_eradicate_01",
            name="AI High Confidence - Full Eradication",
            description="High confidence AI intrusion with decoy confirmation. Full containment and eradication.",
            trigger=PlaybookTrigger.DECEPTION_TOKEN_ACCESS,
            trigger_conditions={
                "machine_likelihood": ["critical"],
                "decoy_touched": True
            },
            steps=[
                PlaybookStep(
                    action=PlaybookAction.TAG_SESSION,
                    params={"tags": ["ai_confirmed", "decoy_triggered", "level_5", "eradication"]},
                    timeout=5
                ),
                PlaybookStep(
                    action=PlaybookAction.ISOLATE_ENDPOINT,
                    params={"block_network": True, "block_usb": True, "hard_isolation": True},
                    timeout=10
                ),
                PlaybookStep(
                    action=PlaybookAction.KILL_PROCESS_TREE,
                    params={"mode": "force", "preserve_memory": True},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.CAPTURE_MEMORY_SNAPSHOT,
                    params={"mode": "full", "priority": "critical"},
                    timeout=300,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.EXECUTE_CONTAINMENT_CHAIN,
                    params={
                        "actions": [
                            "revoke_all_tokens",
                            "rotate_credentials",
                            "block_associated_ips",
                            "quarantine_artifacts"
                        ]
                    },
                    timeout=120
                ),
                PlaybookStep(
                    action=PlaybookAction.CAPTURE_TRIAGE_BUNDLE,
                    params={"window_s": 900, "include": ["full_disk", "memory", "network", "registry"]},
                    timeout=960,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.SYNC_THREAT_INTEL,
                    params={"share_iocs": True, "urgent": True, "communities": ["internal", "isac", "partners"]},
                    timeout=60,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.ESCALATE_TO_HUMAN,
                    params={"reason": "ai_intrusion_confirmed", "required": True, "page_oncall": True},
                    timeout=5
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={
                        "channels": ["slack", "email", "sms", "pagerduty"],
                        "priority": "critical",
                        "template": "ai_intrusion_confirmed"
                    },
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.CREATE_TICKET,
                    params={
                        "category": "ai_intrusion",
                        "priority": "P0",
                        "escalate_to_ciso": True,
                        "legal_notification": True
                    },
                    timeout=30
                )
            ],
            tags=["ai_defense", "eradication", "level_5", "critical"]
        )
        
        # =====================================================================
        # DECEPTION HIT RESPONSE
        # =====================================================================
        self.playbooks["ai_decoy_hit_01"] = Playbook(
            id="ai_decoy_hit_01",
            name="Decoy/Honey Token Hit Response",
            description="Immediate response when any deception asset is accessed.",
            trigger=PlaybookTrigger.DECEPTION_TOKEN_ACCESS,
            trigger_conditions={},
            steps=[
                PlaybookStep(
                    action=PlaybookAction.TAG_SESSION,
                    params={"tags": ["decoy_triggered", "high_confidence", "investigate"]},
                    timeout=5
                ),
                PlaybookStep(
                    action=PlaybookAction.ENABLE_ENHANCED_LOGGING,
                    params={"level": "debug", "full_packet_capture": True},
                    timeout=10
                ),
                PlaybookStep(
                    action=PlaybookAction.INVOKE_ML_ANALYSIS,
                    params={"model": "ai_behavior_classifier", "urgent": True},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.CAPTURE_TRIAGE_BUNDLE,
                    params={"window_s": 120, "include": ["processes", "network", "memory"]},
                    timeout=180,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.FEED_DISINFORMATION,
                    params={"type": "fake_data", "delay_reveal": True},
                    timeout=30,
                    condition="machine_likelihood >= 0.7"
                ),
                PlaybookStep(
                    action=PlaybookAction.BLOCK_IP,
                    params={"duration": 604800, "source": "deception_hit"},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack", "email"], "priority": "high", "template": "decoy_hit"},
                    timeout=30
                )
            ],
            tags=["ai_defense", "deception", "honey_token"]
        )
        
        # =====================================================================
        # ADAPTIVE ATTACK RESPONSE
        # =====================================================================
        self.playbooks["ai_adaptive_attack_01"] = Playbook(
            id="ai_adaptive_attack_01",
            name="Adaptive AI Attack Response",
            description="AI demonstrating adaptive behavior, switching tactics. Match their adaptation.",
            trigger=PlaybookTrigger.ADAPTIVE_ATTACK_DETECTED,
            trigger_conditions={
                "machine_likelihood": ["high", "critical"],
                "goal_persistence": ["high"]
            },
            steps=[
                PlaybookStep(
                    action=PlaybookAction.TAG_SESSION,
                    params={"tags": ["ai_adaptive", "sophisticated", "priority_investigation"]},
                    timeout=5
                ),
                PlaybookStep(
                    action=PlaybookAction.INVOKE_ML_ANALYSIS,
                    params={"model": "adaptive_threat_classifier", "track_evolution": True},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.ENGAGE_TARPIT,
                    params={"mode": "adaptive", "mimic_success": True},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.DEPLOY_DECOY,
                    params={
                        "type": "dynamic",
                        "decoys": ["file_share", "database", "api_endpoint"],
                        "realistic": True
                    },
                    timeout=60
                ),
                PlaybookStep(
                    action=PlaybookAction.CAPTURE_TRIAGE_BUNDLE,
                    params={"window_s": 300, "continuous": True},
                    timeout=360,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.SYNC_THREAT_INTEL,
                    params={"query_ttps": True, "match_actor": True},
                    timeout=60
                ),
                PlaybookStep(
                    action=PlaybookAction.ESCALATE_TO_HUMAN,
                    params={"reason": "adaptive_ai_threat", "expertise_required": "threat_hunting"},
                    timeout=5
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack", "email"], "priority": "critical", "template": "adaptive_ai_threat"},
                    timeout=30
                )
            ],
            tags=["ai_defense", "adaptive", "sophisticated"]
        )
        
        # =====================================================================
        # GOAL PERSISTENT LOOP DETECTION
        # =====================================================================
        self.playbooks["ai_goal_loop_01"] = Playbook(
            id="ai_goal_loop_01",
            name="Goal Persistent Loop Detection",
            description="AI showing persistent goal-seeking behavior. Break the loop.",
            trigger=PlaybookTrigger.GOAL_PERSISTENT_LOOP,
            trigger_conditions={
                "goal_persistence": ["high"],
                "machine_likelihood": ["medium", "high", "critical"]
            },
            steps=[
                PlaybookStep(
                    action=PlaybookAction.TAG_SESSION,
                    params={"tags": ["goal_persistent", "loop_detected"]},
                    timeout=5
                ),
                PlaybookStep(
                    action=PlaybookAction.INJECT_LATENCY,
                    params={"delay_ms": 1000, "jitter_ms": 500, "progressive": True},
                    timeout=10
                ),
                PlaybookStep(
                    action=PlaybookAction.FEED_DISINFORMATION,
                    params={"type": "false_progress", "goal_misdirection": True},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.DEPLOY_DECOY,
                    params={"type": "goal_target", "attractive": True},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.CAPTURE_TRIAGE_BUNDLE,
                    params={"window_s": 180, "track_goal_progress": True},
                    timeout=240,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack"], "priority": "high", "template": "goal_persistent_loop"},
                    timeout=30
                )
            ],
            tags=["ai_defense", "goal_persistent", "loop_breaking"]
        )

        # =====================================================================
        # DISINFORMATION PERSISTENCE RESPONSE
        # Fired when a campaign has been served disinfo >= threshold times,
        # indicating an adversary who is probing through the poisoned data layer
        # and likely correlating/ignoring it.  Escalate to TRAP_SINK territory.
        # =====================================================================
        self.playbooks["ai_disinfo_persist_01"] = Playbook(
            id="ai_disinfo_persist_01",
            name="Disinformation Persistence — Escalate to Trap",
            description=(
                "Campaign has been probing through the disinformation layer "
                "beyond the persistence threshold. Adversary is likely "
                "detecting/ignoring poisoned responses. Escalate friction, "
                "deploy a high-value decoy, and alert a threat hunter."
            ),
            trigger=PlaybookTrigger.DECEPTION_TOKEN_ACCESS,
            trigger_conditions={"route": ["disinformation"]},
            steps=[
                PlaybookStep(
                    action=PlaybookAction.TAG_SESSION,
                    params={"tags": ["disinfo_persistent", "escalate_to_trap", "ai_suspected"]},
                    timeout=5
                ),
                PlaybookStep(
                    action=PlaybookAction.INJECT_LATENCY,
                    params={"delay_ms": 2000, "jitter_ms": 800, "progressive": True},
                    timeout=10
                ),
                PlaybookStep(
                    action=PlaybookAction.DEPLOY_DECOY,
                    params={
                        "type": "high_value",
                        "decoys": ["admin_credentials", "internal_api_key", "database_dsn"],
                        "realistic": True,
                        "attractive": True,
                    },
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.CAPTURE_TRIAGE_BUNDLE,
                    params={"window_s": 300, "include": ["network", "processes", "memory"]},
                    timeout=360,
                    continue_on_failure=True
                ),
                PlaybookStep(
                    action=PlaybookAction.INVOKE_ML_ANALYSIS,
                    params={"model": "ai_behavior_classifier", "urgent": True,
                            "track_evolution": True},
                    timeout=30
                ),
                PlaybookStep(
                    action=PlaybookAction.ESCALATE_TO_HUMAN,
                    params={"reason": "disinfo_persistence_detected",
                            "expertise_required": "threat_hunting"},
                    timeout=5
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack", "email"], "priority": "high",
                            "template": "disinfo_persistence"},
                    timeout=30
                ),
            ],
            tags=["ai_defense", "disinformation", "persistence", "escalation"]
        )
        # =====================================================================
        self.playbooks["ai_sys_evasion_response"] = Playbook(
            id="ai_sys_evasion_response",
            name="System Evasion & Credential Response",
            description="Respond to tool-chain switching and deep system evasion. Audit hijacked modules, revoke suspect tokens, and restore defense posture.",
            trigger=PlaybookTrigger.TOOL_CHAIN_SWITCHING,
            trigger_conditions={},
            steps=[
                PlaybookStep(
                    action=PlaybookAction.COLLECT_FORENSICS,
                    params={"process_tree": True, "loaded_modules": True, "registry_artifacts": True},
                    timeout=120,
                    continue_on_failure=True,
                ),
                PlaybookStep(
                    action=PlaybookAction.KILL_PROCESS,
                    params={"target": "suspicious_injected", "force": False},
                    timeout=30,
                    continue_on_failure=True,
                ),
                PlaybookStep(
                    action=PlaybookAction.UPDATE_FIREWALL,
                    params={"rule_type": "block", "scope": "lateral_suspect"},
                    timeout=60,
                    continue_on_failure=True,
                ),
                PlaybookStep(
                    action=PlaybookAction.SYNC_THREAT_INTEL,
                    params={"query_ttps": True, "credential_focus": True},
                    timeout=60,
                    continue_on_failure=True,
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack", "email"], "priority": "high", "template": "sys_evasion"},
                    timeout=30,
                ),
                PlaybookStep(
                    action=PlaybookAction.CREATE_TICKET,
                    params={"category": "defense_evasion", "priority": "P1"},
                    timeout=30,
                ),
            ],
            tags=["defense_evasion", "credential_access", "system_manipulation"],
            mitre_techniques=[
                "T1003.005", "T1110.001", "T1556", "T1558.002",
                "T1055.001", "T1127.001",
                "T1078.003", "T1134.001", "T1484",
                "T1222", "T1497", "T1497.003", "T1531", "T1553",
                "T1564", "T1574.001", "T1574.006", "T1601.001",
                "T1056.001", "T1538",
                "T1563",
                "T1542.002", "T1547.006",
                "T1592.002",
                "T1012",
                "T1546.003", "T1546.015",
            ],
        )

        # =====================================================================
        # CLOUD / CONTAINER INFRASTRUCTURE RESPONSE
        # =====================================================================
        self.playbooks["ai_cloud_infra_response"] = Playbook(
            id="ai_cloud_infra_response",
            name="Cloud / Container Infrastructure Response",
            description="Respond to cloud-hosted and container-based attack patterns. Revoke cloud credentials, isolate containers, and scrub misconfigured resources.",
            trigger=PlaybookTrigger.ADAPTIVE_ATTACK_DETECTED,
            trigger_conditions={"environment": ["cloud", "container", "saas"]},
            steps=[
                PlaybookStep(
                    action=PlaybookAction.COLLECT_FORENSICS,
                    params={"cloud_logs": True, "container_inspect": True},
                    timeout=120,
                    continue_on_failure=True,
                ),
                PlaybookStep(
                    action=PlaybookAction.ISOLATE_ENDPOINT,
                    params={"scope": "container", "preserve_state": True},
                    timeout=60,
                    continue_on_failure=True,
                ),
                PlaybookStep(
                    action=PlaybookAction.BLOCK_IP,
                    params={"scope": "cloud_egress", "duration": 86400},
                    timeout=30,
                    continue_on_failure=True,
                ),
                PlaybookStep(
                    action=PlaybookAction.UPDATE_FIREWALL,
                    params={"rule_type": "block", "scope": "cloud_subnet"},
                    timeout=60,
                    continue_on_failure=True,
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack", "email"], "priority": "critical", "template": "cloud_infra"},
                    timeout=30,
                ),
                PlaybookStep(
                    action=PlaybookAction.CREATE_TICKET,
                    params={"category": "cloud_compromise", "priority": "P0", "escalate_to_ciso": True},
                    timeout=30,
                ),
            ],
            tags=["cloud", "container", "infrastructure", "saas"],
            mitre_techniques=[
                "T1609", "T1610", "T1612", "T1613", "T1614", "T1619",
                "T1647", "T1648", "T1651",
                "T1606", "T1652", "T1654", "T1656", "T1657",
                "T1659", "T1665", "T1669",
                "T1554",
                "T1538", "T1530", "T1537", "T1102", "T1135", "T1592.002",
                "T1531",
            ],
        )

        # =====================================================================
        # FIRMWARE / PERSISTENT BOOTKIT RESPONSE
        # =====================================================================
        self.playbooks["ai_firmware_persist_response"] = Playbook(
            id="ai_firmware_persist_response",
            name="Firmware & Persistent Bootkit Response",
            description="Respond to firmware/bootkit persistence. Reimage firmware, enforce secure boot, rotate signing keys.",
            trigger=PlaybookTrigger.DECEPTION_TOKEN_ACCESS,
            trigger_conditions={"component": ["firmware", "bootloader", "kernel_module"]},
            steps=[
                PlaybookStep(
                    action=PlaybookAction.ISOLATE_ENDPOINT,
                    params={"network": True, "usb": True, "reason": "firmware_compromise"},
                    timeout=30,
                ),
                PlaybookStep(
                    action=PlaybookAction.COLLECT_FORENSICS,
                    params={"firmware_dump": True, "secure_boot_log": True, "kernel_modules": True},
                    timeout=180,
                    continue_on_failure=True,
                ),
                PlaybookStep(
                    action=PlaybookAction.SCAN_ENDPOINT,
                    params={"firmware_scan": True, "rootkit_check": True},
                    timeout=300,
                    continue_on_failure=True,
                ),
                PlaybookStep(
                    action=PlaybookAction.ESCALATE_TO_HUMAN,
                    params={"reason": "firmware_compromise", "required": True, "expertise_required": "hardware_security"},
                    timeout=5,
                ),
                PlaybookStep(
                    action=PlaybookAction.SEND_ALERT,
                    params={"channels": ["slack", "email", "sms"], "priority": "critical", "template": "firmware_bootkit"},
                    timeout=30,
                ),
                PlaybookStep(
                    action=PlaybookAction.CREATE_TICKET,
                    params={"category": "firmware_compromise", "priority": "P0", "escalate_to_ciso": True},
                    timeout=30,
                ),
            ],
            tags=["firmware", "bootkit", "persistence", "secure_boot"],
            mitre_techniques=[
                "T1542", "T1542.001", "T1542.002", "T1542.003",
                "T1547.006",
                "T1485", "T1489", "T1490", "T1491", "T1491.002",
                "T1495", "T1496", "T1561", "T1565", "T1565.001",
                "T1102", "T1135",
                "T1531",
            ],
        )

    def get_playbooks(self) -> List[Dict]:
        """Get all playbooks"""
        return [asdict(pb) for pb in self.playbooks.values()]
    
    def get_playbook(self, playbook_id: str) -> Optional[Dict]:
        """Get a specific playbook"""
        pb = self.playbooks.get(playbook_id)
        return asdict(pb) if pb else None
    
    def create_playbook(self, data: Dict) -> Dict:
        """Create a new playbook"""
        playbook_id = f"pb_{uuid.uuid4().hex[:8]}"
        
        steps = []
        for step_data in data.get("steps", []):
            steps.append(PlaybookStep(
                action=PlaybookAction(step_data["action"]),
                params=step_data.get("params", {}),
                timeout=step_data.get("timeout", 30),
                continue_on_failure=step_data.get("continue_on_failure", False),
                condition=step_data.get("condition")
            ))
        
        playbook = Playbook(
            id=playbook_id,
            name=data["name"],
            description=data.get("description", ""),
            trigger=PlaybookTrigger(data["trigger"]),
            trigger_conditions=data.get("trigger_conditions", {}),
            steps=steps,
            status=PlaybookStatus(data.get("status", "active")),
            created_by=data.get("created_by", "user")
        )
        
        self.playbooks[playbook_id] = playbook
        return asdict(playbook)
    
    def update_playbook(self, playbook_id: str, data: Dict) -> Optional[Dict]:
        """Update an existing playbook"""
        if playbook_id not in self.playbooks:
            return None
        
        pb = self.playbooks[playbook_id]
        
        if "name" in data:
            pb.name = data["name"]
        if "description" in data:
            pb.description = data["description"]
        if "status" in data:
            previous_status = pb.status
            pb.status = PlaybookStatus(data["status"])
            if pb.status != previous_status:
                pb.state_transition_log.append(
                    {
                        "from_status": previous_status.value,
                        "to_status": pb.status.value,
                        "actor": data.get("updated_by", "system:soar-engine"),
                        "reason": "playbook status updated",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
        if "trigger_conditions" in data:
            pb.trigger_conditions = data["trigger_conditions"]
        if "steps" in data:
            pb.steps = [
                PlaybookStep(
                    action=PlaybookAction(s["action"]),
                    params=s.get("params", {}),
                    timeout=s.get("timeout", 30),
                    continue_on_failure=s.get("continue_on_failure", False),
                    condition=s.get("condition")
                ) for s in data["steps"]
            ]
        
        pb.updated_at = datetime.now(timezone.utc).isoformat()
        return asdict(pb)
    
    def delete_playbook(self, playbook_id: str) -> bool:
        """Delete a playbook"""
        if playbook_id in self.playbooks:
            del self.playbooks[playbook_id]
            return True
        return False
    
    def matches_trigger(self, playbook: Playbook, event: Dict) -> bool:
        """Check if an event matches a playbook's trigger conditions"""
        if playbook.status != PlaybookStatus.ACTIVE:
            return False
        
        # Check trigger type
        event_trigger = event.get("trigger_type")
        if event_trigger and event_trigger != playbook.trigger.value:
            return False
        
        # Check conditions
        for key, allowed_values in playbook.trigger_conditions.items():
            event_value = event.get(key)
            if event_value and allowed_values:
                if isinstance(allowed_values, list):
                    if event_value not in allowed_values:
                        return False
                elif event_value != allowed_values:
                    return False
        
        return True
    
    async def execute_playbook(self, playbook_id: str, event: Dict, db=None) -> PlaybookExecution:
        """Execute a playbook"""
        playbook = self.playbooks.get(playbook_id)
        if not playbook:
            raise ValueError(f"Playbook {playbook_id} not found")
        
        # Enrich event with playbook metadata for downstream evidence collectors.
        enriched_event = dict(event or {})
        enriched_event.setdefault("playbook_id", playbook_id)
        enriched_event.setdefault("playbook_name", playbook.name)
        enriched_event.setdefault("mitre_techniques", list(playbook.mitre_techniques or []))

        execution = PlaybookExecution(
            id=f"exec_{uuid.uuid4().hex[:12]}",
            playbook_id=playbook_id,
            playbook_name=playbook.name,
            trigger_event=enriched_event,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat()
        )

        trace_id = None
        if tamper_evident_telemetry is not None:
            try:
                trace_id = tamper_evident_telemetry.start_trace(
                    "soar.execute_playbook",
                    metadata={"execution_id": execution.id, "playbook_id": playbook_id, "playbook_name": playbook.name},
                )
            except Exception:
                trace_id = None
        
        all_success = True
        
        for i, step in enumerate(playbook.steps):
            step_result = {
                "step": i + 1,
                "action": step.action.value,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "status": "running"
            }
            
            try:
                # Execute the action
                span_id = None
                if tamper_evident_telemetry is not None and trace_id:
                    try:
                        span_id = tamper_evident_telemetry.start_span(trace_id, f"soar.step.{step.action.value}")
                    except Exception:
                        span_id = None

                result = await self._execute_action(step, enriched_event, execution_id=execution.id, db=db)
                step_result["status"] = "completed"
                step_result["result"] = result
                step_result["completed_at"] = datetime.now(timezone.utc).isoformat()

                if tamper_evident_telemetry is not None and trace_id and span_id:
                    try:
                        tamper_evident_telemetry.end_span(trace_id, span_id, status="success", result=result)
                        tamper_evident_telemetry.ingest_event(
                            "soar.step",
                            "info",
                            {
                                "execution_id": execution.id,
                                "playbook_id": playbook_id,
                                "action": step.action.value,
                                "status": "completed",
                                "result": result,
                            },
                            agent_id=str(enriched_event.get("host_id") or enriched_event.get("agent_id") or "soar"),
                            source="server",
                            trace_id=trace_id,
                            span_id=span_id,
                        )
                    except Exception:
                        pass
            except Exception as e:
                step_result["status"] = "failed"
                step_result["error"] = str(e)
                step_result["completed_at"] = datetime.now(timezone.utc).isoformat()
                all_success = False

                if tamper_evident_telemetry is not None and trace_id and span_id:
                    try:
                        tamper_evident_telemetry.end_span(trace_id, span_id, status="failed", result={"error": str(e)})
                        tamper_evident_telemetry.ingest_event(
                            "soar.step",
                            "error",
                            {
                                "execution_id": execution.id,
                                "playbook_id": playbook_id,
                                "action": step.action.value,
                                "status": "failed",
                                "error": str(e),
                            },
                            agent_id=str(enriched_event.get("host_id") or enriched_event.get("agent_id") or "soar"),
                            source="server",
                            trace_id=trace_id,
                            span_id=span_id,
                        )
                    except Exception:
                        pass
                
                if not step.continue_on_failure:
                    execution.step_results.append(step_result)
                    previous_status = execution.status
                    execution.status = ExecutionStatus.FAILED
                    execution.error = f"Step {i+1} failed: {str(e)}"
                    execution.state_transition_log.append(
                        {
                            "from_status": previous_status.value,
                            "to_status": execution.status.value,
                            "actor": "system:soar-engine",
                            "reason": "playbook step failure",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "metadata": {"failed_step": i + 1, "action": step.action.value},
                        }
                    )
                    break
            
            execution.step_results.append(step_result)
        
        if all_success:
            previous_status = execution.status
            execution.status = ExecutionStatus.COMPLETED
            execution.state_transition_log.append(
                {
                    "from_status": previous_status.value,
                    "to_status": execution.status.value,
                    "actor": "system:soar-engine",
                    "reason": "all playbook steps completed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        elif execution.status != ExecutionStatus.FAILED:
            previous_status = execution.status
            execution.status = ExecutionStatus.PARTIAL
            execution.state_transition_log.append(
                {
                    "from_status": previous_status.value,
                    "to_status": execution.status.value,
                    "actor": "system:soar-engine",
                    "reason": "playbook completed with partial failures",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        
        execution.completed_at = datetime.now(timezone.utc).isoformat()
        
        # Update playbook stats
        playbook.execution_count += 1
        playbook.last_executed = execution.completed_at
        
        self.executions.append(execution)
        
        # Keep only last 100 executions
        if len(self.executions) > 100:
            self.executions = self.executions[-100:]

        # Persist archive evidence for MITRE S5 and write telemetry trace artifact.
        self._persist_execution_archive(execution)
        if tamper_evident_telemetry is not None and trace_id:
            try:
                trace = tamper_evident_telemetry.end_trace(trace_id)
            except Exception:
                trace = None
            self._write_trace_artifact(trace, execution.id)
        
        return execution
    
    async def _execute_action(self, step: PlaybookStep, event: Dict, execution_id: Optional[str] = None, db=None) -> Dict:
        """
        Execute a single playbook action with full pipeline integration.
        
        This method handles both standard actions and AI Agentic Defense actions,
        with proper integration into the quarantine pipeline and forensics flow.
        """
        action = step.action
        params = step.params
        host_id = event.get("host_id") or event.get("agent_id")
        session_id = event.get("session_id")
        
        # =================================================================
        # OUTBOUND GATE CHECK FOR HIGH-IMPACT ACTIONS
        # =================================================================
        # Certain actions require governance approval before execution.
        # This prevents SOAR from self-authorizing destructive operations.
        high_impact_actions = {
            PlaybookAction.BLOCK_IP: "response_block_ip",
            PlaybookAction.KILL_PROCESS: "response_execution", 
            PlaybookAction.ISOLATE_ENDPOINT: "quarantine_agent",
            PlaybookAction.DISABLE_USER: "response_execution",
            PlaybookAction.UPDATE_FIREWALL: "cross_sector_hardening",
        }
        
        if action in high_impact_actions:
            gate_result = await self._check_outbound_gate(
                action_type=high_impact_actions[action],
                actor="system:soar-engine",
                payload={
                    "action": action.value,
                    "params": params,
                    "host_id": host_id,
                    "session_id": session_id,
                    "execution_id": execution_id,
                    "event_type": event.get("event_type"),
                    "campaign_id": event.get("campaign_id"),
                    "source_ip": event.get("source_ip"),
                },
                impact_level="high",
                subject_id=host_id,
                entity_refs=[host_id, session_id, execution_id],
                db=db,
                requires_triune=True,
            )
            
            if gate_result.get("status") == "denied":
                logger.warning(
                    f"SOAR action {action.value} denied by outbound gate: {gate_result.get('message')}"
                )
                return {
                    "action": action.value,
                    "status": "denied",
                    "gate_status": gate_result.get("status"),
                    "gate_message": gate_result.get("message"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            elif gate_result.get("status") == "queued":
                logger.info(
                    f"SOAR action {action.value} queued for approval: {gate_result.get('action_id')}"
                )
                return {
                    "action": action.value,
                    "status": "queued",
                    "gate_status": gate_result.get("status"),
                    "action_id": gate_result.get("action_id"),
                    "queue_id": gate_result.get("queue_id"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
        
        # =================================================================
        # MCP ROUTING FOR DECEPTION TOOLS
        # =================================================================
        # Deception-specific actions should route through MCP for proper audit
        # and governance trail, even if they don't require outbound gate approval.
        deception_actions = {
            PlaybookAction.DEPLOY_DECOY: "mcp.defense.deploy_decoy",
            PlaybookAction.FEED_DISINFORMATION: "mcp.defense.feed_disinformation",
        }
        
        if action in deception_actions:
            mcp_result = await self._execute_via_mcp(
                tool_id=deception_actions[action],
                params={
                    "session_id": session_id,
                    "host_id": host_id,
                    "campaign_id": event.get("campaign_id"),
                    "source_ip": event.get("source_ip"),
                    "execution_id": execution_id,
                    **params,  # Include action-specific params
                },
                event=event,
            )
            
            if mcp_result.get("status") == "denied":
                logger.warning(
                    f"SOAR deception action {action.value} denied by MCP: {mcp_result.get('message')}"
                )
                return {
                    "action": action.value,
                    "status": "denied",
                    "mcp_status": mcp_result.get("status"),
                    "mcp_message": mcp_result.get("message"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            # MCP execution succeeded - return the result
            return {
                "action": action.value,
                "status": "completed",
                "mcp_tool_id": deception_actions[action],
                "mcp_result": mcp_result,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        result = {
            "action": action.value,
            "host_id": host_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # =================================================================
        # STANDARD ACTIONS
        # =================================================================
        
        if action == PlaybookAction.BLOCK_IP:
            ip = event.get("source_ip") or params.get("ip")
            duration = params.get("duration", 3600)
            logger.info(f"SOAR: Blocking IP {ip} for {duration}s")
            result.update({"blocked_ip": ip, "duration": duration, "status": "blocked"})
        
        elif action == PlaybookAction.KILL_PROCESS:
            pid = event.get("pid") or params.get("pid")
            force = params.get("force", False)
            logger.info(f"SOAR: Killing process {pid} (force={force})")
            result.update({"killed_pid": pid, "force": force, "status": "terminated"})
        
        elif action == PlaybookAction.QUARANTINE_FILE:
            file_path = event.get("file_path") or params.get("path") or params.get("paths")
            auto_sandbox = params.get("auto_sandbox", False)
            
            # Create quarantine pipeline item
            item_id = f"quar_{uuid.uuid4().hex[:12]}"
            quarantine_item = QuarantinePipelineItem(
                item_id=item_id,
                item_type="file",
                source_host=host_id or "unknown",
                source_path=file_path if isinstance(file_path, str) else str(file_path),
                quarantine_path=f"/var/seraph/quarantine/{item_id}",
                hash_sha256=event.get("file_hash"),
                hash_md5=event.get("file_md5"),
                size_bytes=event.get("file_size", 0),
                quarantined_at=datetime.now(timezone.utc).isoformat(),
                playbook_id=event.get("playbook_id", "manual"),
                execution_id=execution_id or "unknown",
                stage="quarantined"
            )
            self.quarantine_pipeline[item_id] = quarantine_item
            
            logger.info(f"SOAR: Quarantining file {file_path} -> {item_id}")
            result.update({
                "quarantined": file_path,
                "quarantine_id": item_id,
                "auto_sandbox": auto_sandbox,
                "pipeline_stage": "quarantined",
                "status": "quarantined"
            })
        
        elif action == PlaybookAction.SEND_ALERT:
            channels = params.get("channels", ["slack"])
            priority = params.get("priority", "medium")
            template = params.get("template")
            logger.info(f"SOAR: Sending alert to {channels} with priority {priority}")
            result.update({
                "channels_notified": channels,
                "priority": priority,
                "template": template,
                "status": "sent"
            })
        
        elif action == PlaybookAction.ISOLATE_ENDPOINT:
            hard_isolation = params.get("hard_isolation", False)
            block_network = params.get("block_network", True)
            block_usb = params.get("block_usb", False)
            preserve_state = params.get("preserve_state", True)
            
            # Update escalation state
            if host_id:
                self._update_escalation_state(
                    host_id, session_id,
                    DefenseEscalationLevel.ISOLATE,
                    "endpoint isolation triggered"
                )
            
            logger.info(f"SOAR: Isolating endpoint {host_id} (hard={hard_isolation})")
            result.update({
                "isolated_agent": host_id,
                "network_blocked": block_network,
                "usb_blocked": block_usb,
                "hard_isolation": hard_isolation,
                "preserve_state": preserve_state,
                "status": "isolated"
            })
        
        elif action == PlaybookAction.COLLECT_FORENSICS:
            forensics_id = f"forensics_{uuid.uuid4().hex[:12]}"
            params_copy = dict(params)
            logger.info(f"SOAR: Collecting forensics data -> {forensics_id}")
            result.update({
                "forensics_id": forensics_id,
                "forensics_collected": True,
                "params": params_copy,
                "status": "collecting"
            })
        
        elif action == PlaybookAction.DISABLE_USER:
            user = event.get("user") or params.get("user")
            force_logout = params.get("force_logout", False)
            preserve_session = params.get("preserve_session", False)
            logger.info(f"SOAR: Disabling user {user}")
            result.update({
                "disabled_user": user,
                "force_logout": force_logout,
                "preserve_session": preserve_session,
                "status": "disabled"
            })
        
        elif action == PlaybookAction.SCAN_ENDPOINT:
            full_scan = params.get("full_scan", False)
            privilege_audit = params.get("privilege_audit", False)
            logger.info(f"SOAR: Scanning endpoint {host_id}")
            result.update({
                "scan_initiated": True,
                "full_scan": full_scan,
                "privilege_audit": privilege_audit,
                "status": "scanning"
            })
        
        elif action == PlaybookAction.UPDATE_FIREWALL:
            rule_type = params.get("rule_type", "block")
            block_lateral = params.get("block_lateral", False)
            emergency_block = params.get("emergency_block", False)
            logger.info(f"SOAR: Updating firewall with {rule_type} rule")
            result.update({
                "firewall_updated": True,
                "rule_type": rule_type,
                "block_lateral": block_lateral,
                "emergency_block": emergency_block,
                "status": "updated"
            })
        
        elif action == PlaybookAction.CREATE_TICKET:
            category = params.get("category", "security")
            priority = params.get("priority", "P2")
            escalate_to_ciso = params.get("escalate_to_ciso", False)
            ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
            logger.info(f"SOAR: Creating ticket {ticket_id} for {category}")
            result.update({
                "ticket_id": ticket_id,
                "ticket_created": True,
                "category": category,
                "priority": priority,
                "escalate_to_ciso": escalate_to_ciso,
                "status": "created"
            })
        
        # =================================================================
        # AI AGENTIC DEFENSE ACTIONS
        # =================================================================
        
        elif action == PlaybookAction.THROTTLE_CLI:
            rate_per_min = params.get("rate_per_min", 30)
            mode = params.get("mode", "soft")  # soft, hard
            logger.info(f"SOAR AI: Throttling CLI to {rate_per_min}/min ({mode})")
            result.update({
                "throttle_enabled": True,
                "rate_per_min": rate_per_min,
                "mode": mode,
                "status": "throttling"
            })
        
        elif action == PlaybookAction.INJECT_LATENCY:
            delay_ms = params.get("delay_ms", 200)
            jitter_ms = params.get("jitter_ms", 100)
            mode = params.get("mode", "soft")
            progressive = params.get("progressive", False)
            logger.info(f"SOAR AI: Injecting {delay_ms}ms latency (jitter={jitter_ms}ms)")
            result.update({
                "latency_enabled": True,
                "delay_ms": delay_ms,
                "jitter_ms": jitter_ms,
                "mode": mode,
                "progressive": progressive,
                "status": "degrading"
            })
        
        elif action == PlaybookAction.CAPTURE_TRIAGE_BUNDLE:
            window_s = params.get("window_s", 60)
            include = params.get("include", ["processes", "network"])
            bundle_id = f"triage_{uuid.uuid4().hex[:12]}"
            
            # Add to forensics pipeline
            forensics_item = QuarantinePipelineItem(
                item_id=bundle_id,
                item_type="triage_bundle",
                source_host=host_id or "unknown",
                source_path=None,
                quarantine_path=f"/var/seraph/forensics/{bundle_id}",
                hash_sha256=None,
                hash_md5=None,
                size_bytes=0,
                quarantined_at=datetime.now(timezone.utc).isoformat(),
                playbook_id=event.get("playbook_id", "manual"),
                execution_id=execution_id or "unknown",
                stage="collecting"
            )
            self.quarantine_pipeline[bundle_id] = forensics_item
            
            logger.info(f"SOAR AI: Capturing triage bundle {bundle_id} for {window_s}s")
            result.update({
                "bundle_id": bundle_id,
                "window_s": window_s,
                "include": include,
                "pipeline_stage": "collecting",
                "status": "capturing"
            })
        
        elif action == PlaybookAction.CAPTURE_MEMORY_SNAPSHOT:
            mode = params.get("mode", "quick")  # quick, full
            snapshot_id = f"mem_{uuid.uuid4().hex[:12]}"
            
            # Add to pipeline
            mem_item = QuarantinePipelineItem(
                item_id=snapshot_id,
                item_type="memory_dump",
                source_host=host_id or "unknown",
                source_path="memory",
                quarantine_path=f"/var/seraph/forensics/{snapshot_id}.dmp",
                hash_sha256=None,
                hash_md5=None,
                size_bytes=0,
                quarantined_at=datetime.now(timezone.utc).isoformat(),
                playbook_id=event.get("playbook_id", "manual"),
                execution_id=execution_id or "unknown",
                stage="collecting"
            )
            self.quarantine_pipeline[snapshot_id] = mem_item
            
            logger.info(f"SOAR AI: Capturing memory snapshot {snapshot_id} ({mode})")
            result.update({
                "snapshot_id": snapshot_id,
                "mode": mode,
                "pipeline_stage": "collecting",
                "status": "capturing"
            })
        
        elif action == PlaybookAction.KILL_PROCESS_TREE:
            mode = params.get("mode", "force")
            preserve_memory = params.get("preserve_memory", True)
            pid = event.get("pid") or params.get("pid")
            logger.info(f"SOAR AI: Killing process tree from {pid} ({mode})")
            result.update({
                "root_pid": pid,
                "mode": mode,
                "preserve_memory": preserve_memory,
                "status": "terminated"
            })
        
        elif action == PlaybookAction.TAG_SESSION:
            tags = params.get("tags", [])
            session_id = event.get("session_id") or params.get("session_id")
            logger.info(f"SOAR AI: Tagging session {session_id} with {tags}")
            result.update({
                "session_id": session_id,
                "tags_applied": tags,
                "status": "tagged"
            })
        
        elif action == PlaybookAction.DEPLOY_DECOY:
            decoy_type = params.get("type", "credentials")
            decoys = params.get("decoys", [])
            placement = params.get("placement", "standard")
            decoy_ids = [f"decoy_{uuid.uuid4().hex[:8]}" for _ in decoys]
            logger.info(f"SOAR AI: Deploying {len(decoys)} decoys of type {decoy_type}")
            result.update({
                "decoy_type": decoy_type,
                "decoys_deployed": decoy_ids,
                "placement": placement,
                "status": "deployed"
            })
        
        elif action == PlaybookAction.ROTATE_CREDENTIALS:
            scope = params.get("scope", "session")  # session, user, system
            logger.info(f"SOAR AI: Rotating credentials (scope={scope})")
            result.update({
                "scope": scope,
                "credentials_rotated": True,
                "status": "rotated"
            })
        
        elif action == PlaybookAction.ENGAGE_TARPIT:
            mode = params.get("mode", "standard")  # standard, adaptive
            mimic_success = params.get("mimic_success", False)
            logger.info(f"SOAR AI: Engaging tarpit ({mode})")
            result.update({
                "tarpit_engaged": True,
                "mode": mode,
                "mimic_success": mimic_success,
                "status": "active"
            })
        
        elif action == PlaybookAction.FEED_DISINFORMATION:
            disinfo_type = params.get("type", "fake_data")
            delay_reveal = params.get("delay_reveal", False)
            goal_misdirection = params.get("goal_misdirection", False)
            logger.info(f"SOAR AI: Feeding disinformation ({disinfo_type})")
            # Gap D: delegate to DisinformationEngine so SOAR-triggered disinfo is
            # tracked, seeded per-campaign, and visible in history/stats endpoints.
            disinfo_payload = None
            try:
                from services.disinformation_engine import get_disinfo_engine as _get_de
                _disinfo_svc = _get_de()
                disinfo_payload = _disinfo_svc.generate(
                    path=event.get("path", "/api/data"),
                    session_id=session_id or event.get("source_ip") or "soar",
                    campaign_id=event.get("campaign_id"),
                    risk_score=int(event.get("risk_score") or 80),
                    reasons=["soar_playbook", f"disinfo_type:{disinfo_type}"],
                    behavior_flags={"goal_misdirection": goal_misdirection},
                )
            except Exception as _de_err:
                logger.debug(f"SOAR: DisinformationEngine unavailable: {_de_err}")
            result.update({
                "type": disinfo_type,
                "delay_reveal": delay_reveal,
                "goal_misdirection": goal_misdirection,
                "disinfo_payload": disinfo_payload,
                "status": "feeding",
            })
        
        elif action == PlaybookAction.ENABLE_ENHANCED_LOGGING:
            level = params.get("level", "verbose")
            include_keystrokes = params.get("include_keystrokes", False)
            network_capture = params.get("network_capture", False)
            full_packet_capture = params.get("full_packet_capture", False)
            logger.info(f"SOAR AI: Enabling enhanced logging ({level})")
            result.update({
                "level": level,
                "include_keystrokes": include_keystrokes,
                "network_capture": network_capture,
                "full_packet_capture": full_packet_capture,
                "status": "enabled"
            })
        
        elif action == PlaybookAction.SNAPSHOT_NETWORK_STATE:
            include_flows = params.get("include_flows", True)
            include_connections = params.get("include_connections", True)
            snapshot_id = f"netsnap_{uuid.uuid4().hex[:12]}"
            logger.info(f"SOAR AI: Capturing network state snapshot {snapshot_id}")
            result.update({
                "snapshot_id": snapshot_id,
                "include_flows": include_flows,
                "include_connections": include_connections,
                "status": "captured"
            })
        
        elif action == PlaybookAction.LOCK_SENSITIVE_RESOURCES:
            resources = params.get("resources", [])
            logger.info(f"SOAR AI: Locking {len(resources)} sensitive resources")
            result.update({
                "resources_locked": resources,
                "lock_count": len(resources),
                "status": "locked"
            })
        
        elif action == PlaybookAction.TRIGGER_CANARY_VALIDATION:
            validate_all = params.get("validate_all", False)
            logger.info(f"SOAR AI: Triggering canary validation (all={validate_all})")
            result.update({
                "validate_all": validate_all,
                "validation_triggered": True,
                "status": "validating"
            })
        
        elif action == PlaybookAction.ESCALATE_TO_HUMAN:
            reason = params.get("reason", "manual_review_required")
            required = params.get("required", False)
            page_oncall = params.get("page_oncall", False)
            expertise_required = params.get("expertise_required")
            
            escalation_id = f"esc_{uuid.uuid4().hex[:8]}"
            logger.warning(f"SOAR AI: Escalating to human: {reason} (required={required})")
            result.update({
                "escalation_id": escalation_id,
                "reason": reason,
                "required": required,
                "page_oncall": page_oncall,
                "expertise_required": expertise_required,
                "status": "escalated"
            })
        
        elif action == PlaybookAction.INVOKE_ML_ANALYSIS:
            model = params.get("model", "ai_behavior_classifier")
            continuous = params.get("continuous", False)
            urgent = params.get("urgent", False)
            track_evolution = params.get("track_evolution", False)
            logger.info(f"SOAR AI: Invoking ML analysis ({model})")
            result.update({
                "model": model,
                "continuous": continuous,
                "urgent": urgent,
                "track_evolution": track_evolution,
                "status": "analyzing"
            })
        
        elif action == PlaybookAction.SYNC_THREAT_INTEL:
            share_iocs = params.get("share_iocs", False)
            query_ttps = params.get("query_ttps", False)
            communities = params.get("communities", ["internal"])
            urgent = params.get("urgent", False)
            logger.info(f"SOAR AI: Syncing threat intel with {communities}")
            result.update({
                "share_iocs": share_iocs,
                "query_ttps": query_ttps,
                "communities": communities,
                "urgent": urgent,
                "status": "syncing"
            })
        
        elif action == PlaybookAction.QUARANTINE_TO_SANDBOX:
            analyze = params.get("analyze", True)
            detonation_time = params.get("detonation_time", 300)
            sandbox_id = f"sandbox_{uuid.uuid4().hex[:12]}"
            
            # Update pipeline item to sandbox stage
            for item in self.quarantine_pipeline.values():
                if item.source_host == host_id and item.stage == "quarantined":
                    item.stage = "sandboxing"
            
            logger.info(f"SOAR AI: Sending to sandbox {sandbox_id} for analysis")
            result.update({
                "sandbox_id": sandbox_id,
                "analyze": analyze,
                "detonation_time": detonation_time,
                "pipeline_stage": "sandboxing",
                "status": "analyzing"
            })
        
        elif action == PlaybookAction.EXECUTE_CONTAINMENT_CHAIN:
            actions = params.get("actions", [])
            chain_id = f"chain_{uuid.uuid4().hex[:8]}"
            logger.info(f"SOAR AI: Executing containment chain {chain_id} with {len(actions)} actions")
            
            chain_results = []
            for sub_action in actions:
                chain_results.append({
                    "action": sub_action,
                    "status": "executed"
                })
            
            result.update({
                "chain_id": chain_id,
                "actions_executed": len(actions),
                "chain_results": chain_results,
                "status": "completed"
            })
        
        else:
            result.update({"status": "executed"})
        
        return result
    
    async def _check_outbound_gate(
        self,
        action_type: str,
        actor: str,
        payload: Dict,
        impact_level: str,
        subject_id: str,
        entity_refs: List[str],
        db=None,
        requires_triune: bool = True,
    ) -> Dict:
        """
        Check action against outbound gate for governance approval.
        
        Returns gate result dict with status: "approved", "denied", or "queued".
        """
        if db is None:
            logger.warning(
                f"SOAR outbound gate check skipped for {action_type} - no db provided"
            )
            return {
                "status": "approved",
                "skipped": True,
                "reason": "no_db_provided",
                "action_type": action_type,
            }
        
        try:
            from services.outbound_gate import OutboundGateService
            gate = OutboundGateService(db)
            return await gate.gate_action(
                action_type=action_type,
                actor=actor,
                payload=payload,
                impact_level=impact_level,
                subject_id=subject_id,
                entity_refs=entity_refs,
                requires_triune=requires_triune,
            )
        except ImportError as e:
            logger.warning(f"SOAR outbound gate import failed: {e}")
            return {
                "status": "approved", 
                "skipped": True,
                "reason": "import_error",
                "error": str(e),
            }
        except Exception as e:
            logger.warning(f"SOAR outbound gate check failed for {action_type}: {e}")
            return {
                "status": "approved",
                "skipped": True,
                "reason": str(e),
            }
    
    async def _execute_via_mcp(
        self,
        tool_id: str,
        params: Dict,
        event: Dict,
    ) -> Dict:
        """
        Execute a tool via MCP for proper audit trail and governance.
        
        Returns MCP execution result dict.
        """
        try:
            # Import MCP server singleton
            import sys
            import os
            # Add root directory to path so we can import mcp_server
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if root_dir not in sys.path:
                sys.path.insert(0, root_dir)
            
            import mcp_server
            mcp_instance = mcp_server.mcp_server
            
            # Execute via MCP tool bus
            result = await mcp_instance.execute_tool(
                tool_id=tool_id,
                parameters=params,
                context={
                    "source": "soar_engine",
                    "event_type": event.get("event_type"),
                    "execution_id": event.get("execution_id"),
                    "session_id": event.get("session_id"),
                    "host_id": event.get("host_id"),
                }
            )
            
            return {
                "status": "completed",
                "mcp_tool_id": tool_id,
                "result": result,
            }
            
        except Exception as e:
            logger.error(f"MCP execution failed for {tool_id}: {e}")
            return {
                "status": "failed",
                "mcp_tool_id": tool_id,
                "error": str(e),
            }
    
    def _update_escalation_state(
        self,
        host_id: str,
        session_id: Optional[str],
        new_level: DefenseEscalationLevel,
        reason: str
    ):
        """Update the defense escalation state for a host"""
        now = datetime.now(timezone.utc).isoformat()
        
        if host_id in self.escalation_states:
            state = self.escalation_states[host_id]
            state.level_history.append({
                "from_level": state.current_level.value,
                "to_level": new_level.value,
                "timestamp": now,
                "reason": reason
            })
            state.current_level = new_level
            state.escalated_at = now
        else:
            state = DefenseEscalationState(
                host_id=host_id,
                session_id=session_id,
                current_level=new_level,
                level_history=[{
                    "from_level": "none",
                    "to_level": new_level.value,
                    "timestamp": now,
                    "reason": reason
                }],
                active_measures=[],
                escalated_at=now,
                auto_de_escalate_after=None,
                requires_human_approval_for=self.approval_matrix.get(new_level, [])
            )
            self.escalation_states[host_id] = state
    
    def get_escalation_state(self, host_id: str) -> Optional[Dict]:
        """Get the current escalation state for a host"""
        state = self.escalation_states.get(host_id)
        return state.to_dict() if state else None
    
    def get_quarantine_pipeline_items(
        self,
        host_id: Optional[str] = None,
        stage: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get items from the quarantine pipeline"""
        items = list(self.quarantine_pipeline.values())
        
        if host_id:
            items = [i for i in items if i.source_host == host_id]
        if stage:
            items = [i for i in items if i.stage == stage]
        
        items = sorted(items, key=lambda x: x.quarantined_at, reverse=True)[:limit]
        return [i.to_dict() for i in items]
    
    def advance_pipeline_item(self, item_id: str, new_stage: str, results: Optional[Dict] = None) -> Optional[Dict]:
        """Advance a quarantine pipeline item to the next stage"""
        item = self.quarantine_pipeline.get(item_id)
        if not item:
            return None
        
        old_stage = item.stage
        item.stage = new_stage
        
        if results:
            if new_stage == "scanning":
                item.scan_results = results
            elif new_stage == "analyzed":
                item.sandbox_results = results
            elif new_stage == "stored":
                item.forensics_complete = True
        
        logger.info(f"SOAR Pipeline: Advanced {item_id} from {old_stage} to {new_stage}")
        return item.to_dict()

    async def trigger_playbooks(self, event: Dict) -> List[PlaybookExecution]:
        """Trigger all matching playbooks for an event"""
        executions = []
        
        for playbook in self.playbooks.values():
            if self.matches_trigger(playbook, event):
                try:
                    execution = await self.execute_playbook(playbook.id, event, db)
                    executions.append(execution)
                except Exception as e:
                    logger.error(f"Failed to execute playbook {playbook.id}: {e}")
        
        return executions
    
    def get_executions(self, limit: int = 50, playbook_id: Optional[str] = None) -> List[Dict]:
        """Get playbook executions"""
        execs = self.executions
        
        if playbook_id:
            execs = [e for e in execs if e.playbook_id == playbook_id]
        
        # Return most recent first
        execs = sorted(execs, key=lambda x: x.started_at, reverse=True)[:limit]
        
        # Convert to dict and sanitize MongoDB ObjectIds
        result = []
        for e in execs:
            exec_dict = asdict(e)
            # Remove any MongoDB _id fields that might be in trigger_event
            if "trigger_event" in exec_dict and isinstance(exec_dict["trigger_event"], dict):
                exec_dict["trigger_event"].pop("_id", None)
            # Sanitize step_results
            if "step_results" in exec_dict:
                for step in exec_dict["step_results"]:
                    if isinstance(step, dict):
                        step.pop("_id", None)
            result.append(exec_dict)
        return result
    
    def get_stats(self) -> Dict:
        """Get SOAR statistics"""
        total_playbooks = len(self.playbooks)
        active_playbooks = sum(1 for pb in self.playbooks.values() if pb.status == PlaybookStatus.ACTIVE)
        total_executions = len(self.executions)
        
        successful = sum(1 for e in self.executions if e.status == ExecutionStatus.COMPLETED)
        failed = sum(1 for e in self.executions if e.status == ExecutionStatus.FAILED)
        partial = sum(1 for e in self.executions if e.status == ExecutionStatus.PARTIAL)
        
        # By trigger type
        by_trigger = {}
        for pb in self.playbooks.values():
            trigger = pb.trigger.value
            by_trigger[trigger] = by_trigger.get(trigger, 0) + 1
        
        return {
            "total_playbooks": total_playbooks,
            "active_playbooks": active_playbooks,
            "disabled_playbooks": total_playbooks - active_playbooks,
            "total_executions": total_executions,
            "executions_completed": successful,
            "executions_failed": failed,
            "executions_partial": partial,
            "success_rate": round((successful / total_executions * 100) if total_executions > 0 else 0, 1),
            "by_trigger": by_trigger,
            "available_actions": [a.value for a in PlaybookAction],
            "available_triggers": [t.value for t in PlaybookTrigger],
            "total_templates": len(self.templates)
        }
    
    def _init_templates(self):
        """Initialize playbook templates"""
        templates_data = [
            {
                "id": "tpl_data_breach",
                "name": "Data Breach Response",
                "description": "Comprehensive response to potential data breach",
                "category": "incident_response",
                "trigger": PlaybookTrigger.THREAT_DETECTED,
                "trigger_conditions": {"severity": ["critical"], "type": ["data_exfiltration"]},
                "steps": [
                    PlaybookStep(PlaybookAction.ISOLATE_ENDPOINT, {"network": True}, 30),
                    PlaybookStep(PlaybookAction.COLLECT_FORENSICS, {"memory_dump": True, "disk_image": True}, 300),
                    PlaybookStep(PlaybookAction.DISABLE_USER, {}, 10),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["slack", "email", "sms"], "priority": "critical"}, 30),
                    PlaybookStep(PlaybookAction.CREATE_TICKET, {"category": "data_breach", "escalate": True}, 30)
                ],
                "tags": ["breach", "data", "critical", "compliance"],
                "is_official": True
            },
            {
                "id": "tpl_credential_theft",
                "name": "Credential Theft Response",
                "description": "Response when credential theft is detected",
                "category": "identity",
                "trigger": PlaybookTrigger.IOC_MATCH,
                "trigger_conditions": {"ioc_type": ["credential"], "confidence": ["high"]},
                "steps": [
                    PlaybookStep(PlaybookAction.DISABLE_USER, {"force_logout": True}, 10),
                    PlaybookStep(PlaybookAction.BLOCK_IP, {"duration": 86400}, 30),
                    PlaybookStep(PlaybookAction.COLLECT_FORENSICS, {"auth_logs": True}, 60),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["slack", "email"], "priority": "high"}, 30),
                    PlaybookStep(PlaybookAction.CREATE_TICKET, {"category": "credential_theft"}, 30)
                ],
                "tags": ["identity", "credentials", "authentication"],
                "is_official": True
            },
            {
                "id": "tpl_ddos_mitigation",
                "name": "DDoS Attack Mitigation",
                "description": "Automated response to DDoS attacks",
                "category": "network",
                "trigger": PlaybookTrigger.ANOMALY_DETECTED,
                "trigger_conditions": {"anomaly_type": ["traffic_spike"], "severity": ["high", "critical"]},
                "steps": [
                    PlaybookStep(PlaybookAction.UPDATE_FIREWALL, {"rule_type": "rate_limit"}, 30),
                    PlaybookStep(PlaybookAction.BLOCK_IP, {"duration": 3600, "bulk": True}, 60),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["slack"], "priority": "high"}, 30)
                ],
                "tags": ["network", "ddos", "availability"],
                "is_official": True
            },
            {
                "id": "tpl_insider_threat",
                "name": "Insider Threat Response",
                "description": "Response to potential insider threat activity",
                "category": "insider",
                "trigger": PlaybookTrigger.ANOMALY_DETECTED,
                "trigger_conditions": {"anomaly_type": ["user_behavior"], "confidence": ["high"]},
                "steps": [
                    PlaybookStep(PlaybookAction.COLLECT_FORENSICS, {"user_activity": True, "file_access": True}, 120),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["email"], "priority": "medium", "recipients": ["security@company.com"]}, 30),
                    PlaybookStep(PlaybookAction.CREATE_TICKET, {"category": "insider_threat", "confidential": True}, 30)
                ],
                "tags": ["insider", "user", "behavior"],
                "is_official": True
            },
            {
                "id": "tpl_compliance_violation",
                "name": "Compliance Violation Alert",
                "description": "Alert and document compliance violations",
                "category": "compliance",
                "trigger": PlaybookTrigger.THREAT_DETECTED,
                "trigger_conditions": {"type": ["compliance_violation"]},
                "steps": [
                    PlaybookStep(PlaybookAction.COLLECT_FORENSICS, {"audit_trail": True}, 60),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["email"], "priority": "medium"}, 30),
                    PlaybookStep(PlaybookAction.CREATE_TICKET, {"category": "compliance", "sla": "24h"}, 30)
                ],
                "tags": ["compliance", "audit", "regulatory"],
                "is_official": True
            },
            {
                "id": "tpl_crypto_mining",
                "name": "Cryptomining Detection Response",
                "description": "Response to detected cryptomining activity",
                "category": "malware",
                "trigger": PlaybookTrigger.MALWARE_FOUND,
                "trigger_conditions": {"malware_type": ["cryptominer"]},
                "steps": [
                    PlaybookStep(PlaybookAction.KILL_PROCESS, {"force": True}, 10),
                    PlaybookStep(PlaybookAction.QUARANTINE_FILE, {}, 30),
                    PlaybookStep(PlaybookAction.SCAN_ENDPOINT, {"full_scan": True}, 300),
                    PlaybookStep(PlaybookAction.BLOCK_IP, {"duration": 604800}, 30),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["slack"], "priority": "medium"}, 30)
                ],
                "tags": ["malware", "cryptominer", "resource_abuse"],
                "is_official": True
            },
            # NEW TEMPLATES - P2 Expansion
            {
                "id": "tpl_phishing_response",
                "name": "Phishing Attack Response",
                "description": "Automated response to detected phishing attempts",
                "category": "email_security",
                "trigger": PlaybookTrigger.THREAT_DETECTED,
                "trigger_conditions": {"type": ["phishing"], "severity": ["high", "critical"]},
                "steps": [
                    PlaybookStep(PlaybookAction.BLOCK_IP, {"duration": 604800}, 30),
                    PlaybookStep(PlaybookAction.COLLECT_FORENSICS, {"email_headers": True, "url_analysis": True}, 60),
                    PlaybookStep(PlaybookAction.DISABLE_USER, {"notify": True, "reason": "potential_compromise"}, 10),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["slack", "email"], "priority": "high"}, 30),
                    PlaybookStep(PlaybookAction.CREATE_TICKET, {"category": "phishing", "include_indicators": True}, 30)
                ],
                "tags": ["phishing", "email", "social_engineering"],
                "is_official": True
            },
            {
                "id": "tpl_apt_detection",
                "name": "APT Detection Response",
                "description": "Response to Advanced Persistent Threat indicators",
                "category": "advanced_threats",
                "trigger": PlaybookTrigger.IOC_MATCH,
                "trigger_conditions": {"ioc_type": ["apt"], "confidence": ["high"]},
                "steps": [
                    PlaybookStep(PlaybookAction.ISOLATE_ENDPOINT, {"network": True, "preserve_state": True}, 30),
                    PlaybookStep(PlaybookAction.COLLECT_FORENSICS, {"full_memory": True, "network_capture": True, "registry": True}, 600),
                    PlaybookStep(PlaybookAction.UPDATE_FIREWALL, {"rule_type": "apt_block"}, 30),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["slack", "email"], "priority": "critical", "escalate": True}, 30),
                    PlaybookStep(PlaybookAction.CREATE_TICKET, {"category": "apt", "incident_response": True, "sla": "1h"}, 30)
                ],
                "tags": ["apt", "advanced_threat", "nation_state"],
                "is_official": True
            },
            {
                "id": "tpl_lateral_movement",
                "name": "Lateral Movement Detection",
                "description": "Response to detected lateral movement activity",
                "category": "network",
                "trigger": PlaybookTrigger.ANOMALY_DETECTED,
                "trigger_conditions": {"anomaly_type": ["lateral_movement"], "confidence": ["high"]},
                "steps": [
                    PlaybookStep(PlaybookAction.ISOLATE_ENDPOINT, {"network": True}, 15),
                    PlaybookStep(PlaybookAction.BLOCK_IP, {"internal": True, "duration": 3600}, 30),
                    PlaybookStep(PlaybookAction.COLLECT_FORENSICS, {"auth_logs": True, "network_flows": True}, 120),
                    PlaybookStep(PlaybookAction.DISABLE_USER, {"source_user": True}, 10),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["slack"], "priority": "critical"}, 30)
                ],
                "tags": ["lateral_movement", "network", "authentication"],
                "is_official": True
            },
            {
                "id": "tpl_privilege_escalation",
                "name": "Privilege Escalation Response",
                "description": "Response to privilege escalation attempts",
                "category": "identity",
                "trigger": PlaybookTrigger.SUSPICIOUS_PROCESS,
                "trigger_conditions": {"technique": ["privilege_escalation"], "severity": ["high", "critical"]},
                "steps": [
                    PlaybookStep(PlaybookAction.KILL_PROCESS, {"force": True}, 10),
                    PlaybookStep(PlaybookAction.DISABLE_USER, {"preserve_session": True}, 10),
                    PlaybookStep(PlaybookAction.COLLECT_FORENSICS, {"process_tree": True, "tokens": True}, 60),
                    PlaybookStep(PlaybookAction.SCAN_ENDPOINT, {"privilege_audit": True}, 120),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["slack", "email"], "priority": "high"}, 30)
                ],
                "tags": ["privilege_escalation", "identity", "persistence"],
                "is_official": True
            },
            {
                "id": "tpl_zero_day_exploit",
                "name": "Zero-Day Exploit Response",
                "description": "Emergency response to potential zero-day exploitation",
                "category": "vulnerability",
                "trigger": PlaybookTrigger.ANOMALY_DETECTED,
                "trigger_conditions": {"anomaly_type": ["unknown_exploit"], "severity": ["critical"]},
                "steps": [
                    PlaybookStep(PlaybookAction.ISOLATE_ENDPOINT, {"network": True, "preserve_state": True}, 15),
                    PlaybookStep(PlaybookAction.COLLECT_FORENSICS, {"full_memory": True, "crash_dumps": True}, 300),
                    PlaybookStep(PlaybookAction.UPDATE_FIREWALL, {"emergency_block": True}, 30),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["slack", "email", "sms"], "priority": "critical", "escalate_to_ciso": True}, 30),
                    PlaybookStep(PlaybookAction.CREATE_TICKET, {"category": "zero_day", "incident_response": True, "sla": "30m"}, 30)
                ],
                "tags": ["zero_day", "exploit", "vulnerability", "emergency"],
                "is_official": True
            },
            {
                "id": "tpl_supply_chain_attack",
                "name": "Supply Chain Attack Response",
                "description": "Response to suspected supply chain compromise",
                "category": "advanced_threats",
                "trigger": PlaybookTrigger.MALWARE_FOUND,
                "trigger_conditions": {"source": ["trusted_vendor", "update_mechanism"], "severity": ["critical"]},
                "steps": [
                    PlaybookStep(PlaybookAction.ISOLATE_ENDPOINT, {"network": True}, 15),
                    PlaybookStep(PlaybookAction.UPDATE_FIREWALL, {"block_vendor_ips": True}, 30),
                    PlaybookStep(PlaybookAction.COLLECT_FORENSICS, {"software_inventory": True, "signature_check": True}, 300),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["slack", "email"], "priority": "critical", "notify_vendor": True}, 30),
                    PlaybookStep(PlaybookAction.CREATE_TICKET, {"category": "supply_chain", "legal_notification": True}, 30)
                ],
                "tags": ["supply_chain", "vendor", "third_party"],
                "is_official": True
            },
            {
                "id": "tpl_dns_tunneling",
                "name": "DNS Tunneling Detection",
                "description": "Response to DNS tunneling/exfiltration",
                "category": "network",
                "trigger": PlaybookTrigger.ANOMALY_DETECTED,
                "trigger_conditions": {"anomaly_type": ["dns_tunneling"], "confidence": ["high"]},
                "steps": [
                    PlaybookStep(PlaybookAction.UPDATE_FIREWALL, {"block_dns_domain": True}, 30),
                    PlaybookStep(PlaybookAction.COLLECT_FORENSICS, {"dns_logs": True, "process_network": True}, 120),
                    PlaybookStep(PlaybookAction.KILL_PROCESS, {"dns_client": True}, 10),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["slack"], "priority": "high"}, 30)
                ],
                "tags": ["dns", "exfiltration", "tunneling"],
                "is_official": True
            },
            {
                "id": "tpl_cloud_breach",
                "name": "Cloud Infrastructure Breach",
                "description": "Response to cloud infrastructure compromise",
                "category": "cloud_security",
                "trigger": PlaybookTrigger.THREAT_DETECTED,
                "trigger_conditions": {"environment": ["cloud", "aws", "azure", "gcp"], "severity": ["critical"]},
                "steps": [
                    PlaybookStep(PlaybookAction.DISABLE_USER, {"cloud_iam": True}, 10),
                    PlaybookStep(PlaybookAction.UPDATE_FIREWALL, {"cloud_security_groups": True}, 30),
                    PlaybookStep(PlaybookAction.COLLECT_FORENSICS, {"cloud_trail": True, "api_logs": True}, 180),
                    PlaybookStep(PlaybookAction.SEND_ALERT, {"channels": ["slack", "email"], "priority": "critical"}, 30),
                    PlaybookStep(PlaybookAction.CREATE_TICKET, {"category": "cloud_breach", "cloud_provider_notification": True}, 30)
                ],
                "tags": ["cloud", "aws", "azure", "gcp", "infrastructure"],
                "is_official": True
            }
        ]
        
        for tpl_data in templates_data:
            template = PlaybookTemplate(
                id=tpl_data["id"],
                name=tpl_data["name"],
                description=tpl_data["description"],
                category=tpl_data["category"],
                trigger=tpl_data["trigger"],
                trigger_conditions=tpl_data["trigger_conditions"],
                steps=tpl_data["steps"],
                tags=tpl_data["tags"],
                is_official=tpl_data["is_official"]
            )
            self.templates[template.id] = template
    
    def get_templates(self, category: Optional[str] = None) -> List[Dict]:
        """Get all playbook templates"""
        templates = list(self.templates.values())
        
        if category:
            templates = [t for t in templates if t.category == category]
        
        result = []
        for tpl in templates:
            d = asdict(tpl)
            d["trigger"] = tpl.trigger.value
            d["steps"] = [{"action": s.action.value, "params": s.params, "timeout": s.timeout} for s in tpl.steps]
            result.append(d)
        
        return result
    
    def get_template(self, template_id: str) -> Optional[Dict]:
        """Get a specific template"""
        tpl = self.templates.get(template_id)
        if tpl:
            d = asdict(tpl)
            d["trigger"] = tpl.trigger.value
            d["steps"] = [{"action": s.action.value, "params": s.params, "timeout": s.timeout} for s in tpl.steps]
            return d
        return None
    
    def clone_from_template(self, template_id: str, name: str, created_by: str) -> Dict:
        """Create a new playbook from a template"""
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        playbook_id = f"pb_{uuid.uuid4().hex[:8]}"
        
        playbook = Playbook(
            id=playbook_id,
            name=name,
            description=f"Created from template: {template.name}",
            trigger=template.trigger,
            trigger_conditions=template.trigger_conditions.copy(),
            steps=template.steps.copy(),
            created_by=created_by,
            template_id=template_id,
            tags=template.tags.copy()
        )
        
        self.playbooks[playbook_id] = playbook
        template.use_count += 1
        
        return asdict(playbook)
    
    def create_template(self, data: Dict, created_by: str) -> Dict:
        """Create a custom template"""
        template_id = f"tpl_{uuid.uuid4().hex[:8]}"
        
        steps = []
        for step_data in data.get("steps", []):
            steps.append(PlaybookStep(
                action=PlaybookAction(step_data["action"]),
                params=step_data.get("params", {}),
                timeout=step_data.get("timeout", 30),
                continue_on_failure=step_data.get("continue_on_failure", False)
            ))
        
        template = PlaybookTemplate(
            id=template_id,
            name=data["name"],
            description=data.get("description", ""),
            category=data.get("category", "custom"),
            trigger=PlaybookTrigger(data["trigger"]),
            trigger_conditions=data.get("trigger_conditions", {}),
            steps=steps,
            tags=data.get("tags", []),
            is_official=False
        )
        
        self.templates[template_id] = template
        return asdict(template)
    
    def get_template_categories(self) -> List[Dict]:
        """Get all template categories with counts"""
        categories = {}
        for tpl in self.templates.values():
            if tpl.category not in categories:
                categories[tpl.category] = {"name": tpl.category, "count": 0, "templates": []}
            categories[tpl.category]["count"] += 1
            categories[tpl.category]["templates"].append(tpl.name)
        
        return list(categories.values())
    
    # =========================================================================
    # AI-AGENTIC EVENT EVALUATION
    # =========================================================================
    
    async def evaluate_event(self, event: Dict, db=None) -> List[Dict]:
        """
        Evaluate an event against AI-Agentic playbooks.
        Called by the CLI events router for session summaries and deception hits.
        
        Args:
            event: Event dict with event_type, host_id, session_id, etc.
            db: Database instance for logging
            
        Returns:
            List of triggered playbook execution results
        """
        event_type = event.get("event_type")
        results = []
        
        logger.info(f"SOAR: Evaluating event type '{event_type}' for host {event.get('host_id')}")
        
        # Map event types to playbook triggers
        if event_type == "cli.session_summary":
            results = await self._evaluate_session_summary(event, db)
        elif event_type == "deception.hit":
            results = await self._evaluate_deception_hit(event, db)
        elif event_type == "deception.disinfo":
            results = await self._evaluate_disinfo_persistence(event, db)

        return results
    
    async def _evaluate_session_summary(self, event: Dict, db=None) -> List[Dict]:
        """Evaluate a CLI session summary against AI-Agentic playbooks"""
        results = []
        host_id = event.get("host_id")
        session_id = event.get("session_id")
        machine_likelihood = event.get("machine_likelihood", 0)
        burstiness = event.get("burstiness_score", 0)
        intents = event.get("dominant_intents", [])
        decoy_touched = event.get("decoy_touched", False)
        tool_switch_ms = event.get("tool_switch_latency_ms", 1000)
        goal_persistence = event.get("goal_persistence", 0)
        
        # Threshold values
        ML_HIGH = 0.80
        ML_CRITICAL = 0.92
        BURST_HIGH = 0.75
        TOOL_SWITCH_FAST = 300
        
        triggered_playbooks = []
        
        # AI-RECON-DEGRADE-01: Machine-paced recon loop
        if (machine_likelihood >= ML_HIGH and 
            "recon" in intents and 
            burstiness >= BURST_HIGH):
            triggered_playbooks.append({
                "playbook_id": "AI-RECON-DEGRADE-01",
                "name": "Machine-Paced Recon Loop — Degrade + Observe",
                "reason": f"ML:{machine_likelihood:.2f} Burst:{burstiness:.2f} Intent:recon"
            })
        
        # AI-CRED-ACCESS-RESP-01: Credential access pattern
        if machine_likelihood >= ML_HIGH and "credential_access" in intents:
            triggered_playbooks.append({
                "playbook_id": "AI-CRED-ACCESS-RESP-01",
                "name": "Credential Access Pattern — Decoy + Credential Controls",
                "reason": f"ML:{machine_likelihood:.2f} Intent:credential_access"
            })
        
        # AI-PIVOT-CONTAIN-01: Fast tool switching + lateral movement
        if (machine_likelihood >= ML_HIGH and 
            tool_switch_ms <= TOOL_SWITCH_FAST and
            goal_persistence >= 0.70 and
            any(i in intents for i in ["lateral_movement", "privilege_escalation"])):
            triggered_playbooks.append({
                "playbook_id": "AI-PIVOT-CONTAIN-01",
                "name": "Autonomous Pivot / Toolchain Switching — Contain Fast",
                "reason": f"ML:{machine_likelihood:.2f} ToolSwitch:{tool_switch_ms}ms Persist:{goal_persistence:.2f}"
            })
        
        # AI-EXFIL-PREP-CUT-01: Exfil preparation
        if machine_likelihood >= ML_HIGH and any(i in intents for i in ["exfil_prep", "data_staging"]):
            triggered_playbooks.append({
                "playbook_id": "AI-EXFIL-PREP-CUT-01",
                "name": "Exfil Prep — Cut Egress + Snapshot",
                "reason": f"ML:{machine_likelihood:.2f} Intent:{intents}"
            })
        
        # AI-HIGHCONF-ERADICATE-01: High confidence + decoy touched
        if machine_likelihood >= ML_CRITICAL and decoy_touched:
            triggered_playbooks.append({
                "playbook_id": "AI-HIGHCONF-ERADICATE-01",
                "name": "High Confidence Agentic Intrusion — Full Containment + Eradication",
                "reason": f"ML:{machine_likelihood:.2f} + DecoyTouched"
            })
        
        # Execute triggered playbooks
        for pb in triggered_playbooks:
            try:
                execution_result = await self._execute_ai_playbook(pb, event, db)
                results.append(execution_result)
                logger.warning(
                    f"SOAR AI Playbook Triggered: {pb['playbook_id']} for {host_id}/{session_id} - {pb['reason']}"
                )
            except Exception as e:
                logger.error(f"SOAR AI Playbook execution failed: {e}")
                results.append({
                    "playbook_id": pb["playbook_id"],
                    "status": "failed",
                    "error": str(e)
                })
        
        return results
    
    async def _evaluate_disinfo_persistence(self, event: Dict, db=None) -> List[Dict]:
        """
        Evaluate a disinformation persistence alert.
        Fired when a campaign has been served disinfo >= DISINFO_PERSIST_THRESHOLD times.
        Executes ai_disinfo_persist_01: escalate friction, deploy high-value decoy, alert hunter.
        """
        results = []
        disinfo_events = event.get("disinfo_events", 0)
        campaign_id = event.get("campaign_id")
        try:
            execution = await self.execute_playbook("ai_disinfo_persist_01", event, db)
            results.append({
                "playbook_id": "ai_disinfo_persist_01",
                "execution_id": execution.id,
                "status": execution.status.value,
            })
            logger.warning(
                f"SOAR Disinfo Persistence: ai_disinfo_persist_01 for campaign={campaign_id} "
                f"disinfo_events={disinfo_events}"
            )
        except Exception as e:
            logger.error(f"SOAR ai_disinfo_persist_01 failed: {e}")
            results.append({"playbook_id": "ai_disinfo_persist_01", "status": "failed", "error": str(e)})
        return results

    async def _evaluate_deception_hit(self, event: Dict, db=None) -> List[Dict]:
        """Evaluate a deception/honey token hit"""
        results = []
        severity = event.get("severity", "medium")

        # Always execute the registered ai_decoy_hit_01 playbook.
        # This chain: TAG → LOGGING → ML → TRIAGE → FEED_DISINFORMATION → BLOCK → ALERT
        # The FEED_DISINFORMATION step now calls DisinformationEngine.generate() (Gap D).
        try:
            execution = await self.execute_playbook("ai_decoy_hit_01", event, db)
            results.append({
                "playbook_id": "ai_decoy_hit_01",
                "execution_id": execution.id,
                "status": execution.status.value,
            })
            logger.critical(
                f"SOAR Deception Hit: ai_decoy_hit_01 executed for "
                f"{event.get('host_id')} severity={severity}"
            )
        except Exception as e:
            logger.error(f"SOAR ai_decoy_hit_01 failed: {e}")
            results.append({"playbook_id": "ai_decoy_hit_01", "status": "failed", "error": str(e)})

        # For high/critical severity also run the AI exec containment chain.
        if severity in ["high", "critical"]:
            pb = {
                "playbook_id": "AI-DECOY-HIT-CONTAIN-01",
                "name": "Decoy/Honey Token Hit — Immediate Containment",
                "reason": f"Severity:{severity} Token:{event.get('token_id')}"
            }
            try:
                execution_result = await self._execute_ai_playbook(pb, event, db)
                results.append(execution_result)
                logger.critical(
                    f"SOAR Deception Hit: {pb['playbook_id']} for {event.get('host_id')} - {pb['reason']}"
                )
            except Exception as e:
                logger.error(f"SOAR Deception playbook failed: {e}")
                results.append({
                    "playbook_id": pb["playbook_id"],
                    "status": "failed",
                    "error": str(e)
                })

        return results
    
    async def _execute_ai_playbook(self, playbook_info: Dict, event: Dict, db=None) -> Dict:
        """
        Execute an AI-Agentic playbook and create agent commands.
        
        This creates commands in the agent_commands collection for manual approval.
        """
        import uuid
        
        playbook_id = playbook_info["playbook_id"]
        host_id = event.get("host_id")
        session_id = event.get("session_id")
        
        execution_id = f"ai_exec_{uuid.uuid4().hex[:12]}"
        actions_created = []
        
        # Define actions for each playbook
        playbook_actions = {
            "AI-RECON-DEGRADE-01": [
                {"action": "tag_session", "params": {"tags": ["ai_suspected", "recon"]}},
                {"action": "throttle_cli", "params": {"rate_per_min": 20, "mode": "soft"}},
                {"action": "inject_latency", "params": {"delay_ms": 250, "jitter_ms": 200, "mode": "soft"}},
                {"action": "capture_triage_bundle", "params": {"window_s": 30}}
            ],
            "AI-DECOY-HIT-CONTAIN-01": [
                {"action": "isolate_host", "params": {"block_network": True}},
                {"action": "capture_triage_bundle", "params": {"window_s": 300}},
                {"action": "kill_process_tree", "params": {"mode": "force"}}
            ],
            "AI-CRED-ACCESS-RESP-01": [
                {"action": "throttle_cli", "params": {"rate_per_min": 10, "mode": "hard"}},
                {"action": "inject_latency", "params": {"delay_ms": 600, "jitter_ms": 400, "mode": "hard"}},
                {"action": "capture_triage_bundle", "params": {"window_s": 180}}
            ],
            "AI-PIVOT-CONTAIN-01": [
                {"action": "isolate_host", "params": {"block_network": True}},
                {"action": "capture_triage_bundle", "params": {"window_s": 300}}
            ],
            "AI-EXFIL-PREP-CUT-01": [
                {"action": "isolate_host", "params": {"block_network": True}},
                {"action": "capture_triage_bundle", "params": {"window_s": 600}}
            ],
            "AI-HIGHCONF-ERADICATE-01": [
                {"action": "isolate_host", "params": {"block_network": True}},
                {"action": "kill_process_tree", "params": {"mode": "force"}},
                {"action": "capture_memory_snapshot", "params": {"mode": "quick"}},
                {"action": "capture_triage_bundle", "params": {"window_s": 900}}
            ]
        }
        
        actions = playbook_actions.get(playbook_id, [])
        
        # Create agent commands for each action (requires manual approval)
        if db is not None:
            for action in actions:
                command_id = str(uuid.uuid4())[:12]
                command = {
                    "command_id": command_id,
                    "agent_id": host_id,
                    "command_type": action["action"],
                    "command_name": f"AI Playbook: {action['action']}",
                    "parameters": {
                        **action["params"],
                        "session_id": session_id,
                        "playbook_id": playbook_id,
                        "execution_id": execution_id
                    },
                    "priority": "critical" if "isolate" in action["action"] else "high",
                    "risk_level": "high",
                    "status": "pending_approval",
                    "state_version": 1,
                    "state_transition_log": [{
                        "from_status": None,
                        "to_status": "pending_approval",
                        "actor": f"SOAR:{playbook_id}",
                        "reason": "ai playbook queued command",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }],
                    "created_by": f"SOAR:{playbook_id}",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "source": "ai_agentic_playbook",
                    "playbook_info": playbook_info
                }
                
                await db.agent_commands.insert_one(command)
                actions_created.append(command_id)
        
        # Log the execution
        execution_result = {
            "execution_id": execution_id,
            "playbook_id": playbook_id,
            "playbook_name": playbook_info["name"],
            "trigger_reason": playbook_info["reason"],
            "host_id": host_id,
            "session_id": session_id,
            "status": "commands_queued",
            "commands_created": actions_created,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }
        
        if db is not None:
            await db.soar_executions.insert_one({
                **execution_result,
                "event": event
            })
        
        # Sanitize event before storing in memory (remove MongoDB ObjectId)
        sanitized_event = {k: v for k, v in event.items() if k != "_id"}
        
        # Store in memory
        self.executions.append(PlaybookExecution(
            id=execution_id,
            playbook_id=playbook_id,
            playbook_name=playbook_info["name"],
            trigger_event=sanitized_event,
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat()
        ))
        
        return execution_result


# Global instance
soar_engine = SOAREngine()
