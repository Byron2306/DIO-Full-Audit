from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum

class ExecutionClass(str, Enum):
    PROTECTED = "protected"       # Local admin/service binaries
    SENSITIVE = "sensitive"       # Network or data-heavy tools
    LOW_RISK = "low_risk"         # Non-privileged utilities
    UNTRUSTED = "untrusted"       # Unmeasured or external execution

class ManifestationStatus(str, Enum):
    PERMITTED = "permitted"       # Full execution manifest
    SANDBOXED = "sandboxed"       # Permitted with seccomp/LSM constraints
    VETOED = "vetoed"             # Cluster-level quorum veto
    REJECTED = "rejected"         # Local policy or covenant failure
    PENDING = "pending"           # Still awaiting Triune judgment

class ProcessBirthRequest(BaseModel):
    """
    The legal request for a process to manifest in the Arda substrate.
    """
    request_id: str = Field(default_factory=lambda: f"birth-{datetime.now(timezone.utc).timestamp()}")
    binary_path: str
    target_uid: int
    target_gid: int
    execution_class: ExecutionClass
    parent_pid: Optional[int] = None
    capability_token: Optional[str] = None
    herald_context_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ProcessBirthDecision(BaseModel):
    """
    The final constitutional verdict for process manifestation.
    """
    decision_id: str
    request_ref: str
    status: ManifestationStatus
    reason: str
    seccomp_profile: Optional[str] = None
    granted_capabilities: List[str] = Field(default_factory=list)
    consensus_score: float = 0.0
    vetted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    audit_hash: str  # Tamper-evident hash of the decision

class ExecLineage(BaseModel):
    """
    The constitutional ancestry of a running process.
    Connects kernel PIDs to Triune truths.
    """
    pid: int
    ppid: int
    node_id: str
    herald_identity: str
    covenant_ref: str
    token_id: Optional[str] = None
    manifested_at: datetime
    execution_class: ExecutionClass
    status: str = "active"

class KernelObservation(BaseModel):
    """
    A low-level signal captured by the Kernel Signal Adapter.
    """
    observation_id: str = Field(default_factory=lambda: f"k-obs-{datetime.now(timezone.utc).timestamp()}")
    node_id: str
    event_type: str  # exec, fork, setuid, cap_gain, syscall_risk
    source_pid: int
    target_resource: Optional[str] = None
    risk_score: float = 0.0
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PrivilegeTransition(BaseModel):
    """
    Captures potential state escalations (UID/GID/Cap changes).
    """
    pid: int
    old_uid: int
    new_uid: int
    old_caps: List[str] = Field(default_factory=list)
    new_caps: List[str] = Field(default_factory=list)
    is_suspicious: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SyscallRiskEvent(BaseModel):
    """
    Captures dangerous syscall patterns or unusual manifestation jitter.
    """
    pid: int
    syscall_name: str
    context: str # "birth", "runtime", "exit"
    impact: str # "observation", "block", "alert"
    order_ref: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class EnforcementScope(BaseModel):
    """
    Defines the kernel boundaries for the current Epoch.
    """
    scope_id: str
    protected_paths: List[str]
    protected_uids: List[int]
    restricted_syscalls: List[str]
    strictness_level: str = "cluster-enforced"

class KernelBridgeState(BaseModel):
    """
    The high-level status of the Phase V bridge on this node.
    """
    node_id: str
    is_ebpf_active: bool = False
    is_seccomp_active: bool = False
    is_audit_active: bool = False
    birth_veto_count: int = 0
    lineage_integrity: float = 1.0 # 0.0 - 1.0
    active_protected_pids: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
