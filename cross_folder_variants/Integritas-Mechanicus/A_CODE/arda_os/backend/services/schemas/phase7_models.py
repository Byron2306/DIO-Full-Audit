from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class KernelExecRequest(BaseModel):
    """A request intercepted at the kernel level for process execution."""
    request_id: str
    pid: int
    ppid: int
    executable_path: str
    arguments: List[str]
    uid: int
    gid: int
    lineage_parent_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class KernelExecVerdict(BaseModel):
    """The constitutional verdict for a kernel-level execution request."""
    request_id: str
    verdict: str # "allow", "deny", "sandbox", "kill"
    reason: str
    applied_profile: Optional[str] = None
    enforcement_delay_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SyscallConstraint(BaseModel):
    """Constraint applied to specific syscall classes for a manifestation."""
    class_id: str # e.g., "network", "filesystem", "privilege"
    action: str # "allow", "deny", "trace", "log"
    allowed_list: List[str] = []
    denied_list: List[str] = []

class PrivilegeEscalationVerdict(BaseModel):
    """Verdict for a detected privilege transition attempt."""
    pid: int
    old_uid: int
    new_uid: int
    is_lawful: bool
    escalation_path: str # e.g., "setuid", "capabilities", "sudo"
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class KernelPolicyProjection(BaseModel):
    """A distilled, machine-enforceable projection of Seraph law."""
    policy_id: str
    covenant_authority_id: str
    enforce_exec_protection: bool = True
    enforce_lineage_strictness: bool = True
    syscall_constraints: Dict[str, List[SyscallConstraint]] = {} # Map manifestation-class to constraints
    whitelisted_binaries: List[str] = []
    blacklisted_binaries: List[str] = []
    generated_at: datetime = Field(default_factory=datetime.utcnow)

class KernelSovereigntySnapshot(BaseModel):
    """Snapshot of the machine's native enforcement health."""
    is_sovereign: bool
    active_interceptors: List[str] # ["ebpf_exec", "lsm_hook", "seccomp"]
    exec_intercept_count: int = 0
    denied_exec_count: int = 0
    privilege_anomalies: int = 0
    syscall_fracture_score: float = 0.0
    last_policy_sync: datetime
