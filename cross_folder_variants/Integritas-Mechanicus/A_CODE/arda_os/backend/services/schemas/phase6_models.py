from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class PcrSnapshot(BaseModel):
    """Snapshot of TPM Platform Configuration Registers."""
    index: int
    value: str
    algorithm: str = "sha256"

class BootEventRecord(BaseModel):
    """A single record from the UEFI/BIOS Event Log."""
    pcr_index: int
    event_type: str
    digest: str
    event_data: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SecureBootState(BaseModel):
    """Current state of Secure Boot on the system."""
    enabled: bool
    setup_mode: bool
    secure_boot_mode: str  # e.g., "User", "Audit", "Deployed"
    vendor_keys: List[str]

class MeasuredBootRecord(BaseModel):
    """Full record of a measured boot instance."""
    boot_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    pcrs: List[PcrSnapshot]
    event_log: List[BootEventRecord]
    secure_boot: SecureBootState
    kernel_version: str
    initrd_hash: str

class AttestationQuote(BaseModel):
    """A signed quote from the TPM."""
    quote: str  # Base64 encoded TPM quote
    signature: str # Base64 encoded signature
    pcr_mask: str # Which PCRs are covered
    nonce: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class FormationVerdict(BaseModel):
    """The result of the formation verification process."""
    is_lawful: bool
    confidence_score: float
    violations: List[str] = []
    attestation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class PrebootCovenant(BaseModel):
    """A covenant sealed before the full runtime starts."""
    covenant_id: str
    formation_verdict: FormationVerdict
    boot_id: str
    manifest_hash: str
    rootfs_hash: str # Cryptographic hash of the intended root filesystem
    reaction_mode: str = "guarded" # "development", "guarded", "sovereign", "genesis"
    sealed_data: str # Encrypted or HMACed sensitive data
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class BootContinuationDecision(BaseModel):
    """The decision made by the Boot Gate Controller."""
    action: str # "allow", "degrade", "recovery", "veto"
    reason: str
    target_state: str # Target system state (e.g., "production", "maintenance")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AttestedNodeState(BaseModel):
    """The state of a node as verified by the cluster."""
    node_id: str
    is_attested: bool
    status: str # "attested", "fractured", "unknown"
    preboot_covenant_id: str
    last_attestation_timestamp: datetime
    pcr_values: Dict[int, str]
