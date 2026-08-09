from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum

class StabilityClass(str, Enum):
    CRYSTALLINE = "crystalline"  # perfect order
    STABLE = "stable"            # normal order
    STRAINED = "strained"        # jitter/drift detected
    DISSONANT = "dissonant"      # high disorder
    FRACTURED = "fractured"      # complete breakdown

class BootTruthStatus(str, Enum):
    LAWFUL = "lawful"            # verified via TPM/SecureBoot
    UNVERIFIED = "unverified"    # not yet attested
    UNLAWFUL = "unlawful"        # attestation failed
    COMPROMISED = "compromised"  # runtime trust lost
    FRACTURED = "fractured"      # formation sequence violation
    VETOED = "vetoed"             # cluster-level quorum veto

class BootTruthBundle(BaseModel):
    """The measured light of the machine's birth (Arda's first light)."""
    bundle_id: str
    attestation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # TPM 2.0 Measurements
    pcr_values: Dict[int, str]  # PCR index -> hash
    quote: Optional[str] = None # TPM Quote (RSASSA-PSS or similar)
    quote_signature: Optional[str] = None
    tpm_version: str = "2.0"
    
    # Secure Boot Evidence
    secure_boot_enabled: bool
    setup_mode: bool
    policy_hash: str            # expected VS actual boot manifest hash
    
    # Metadata
    kernel_version: str
    initramfs_hash: str
    bootloader_id: str
    
    status: BootTruthStatus = BootTruthStatus.UNVERIFIED
    verified_at: Optional[datetime] = None
    signature: Optional[str] = None # signature over the entire bundle by attestation service

class OrderState(BaseModel):
    """The lawful flow of what may become (The Music of the Ainur)."""
    order_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Temporal Law
    stability_class: StabilityClass
    temporal_strictness: float = 0.5  # 0..1
    entry_window_ms: List[int]        # [min, max] allowed process birth window
    
    # Sequence & Constraints
    active_sequence_constraints: Dict[str, Any]
    harmonic_summary: Dict[str, Any]  # fusion of harmonic_engine outputs
    
    # Identity Binding
    herald_id_ref: str
    epoch_id_ref: str

class WorldManifoldSnapshot(BaseModel):
    """The spacetime manifold where truth and order are fused."""
    manifold_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Context Fusion
    world_state_hash: str             # snapshot of world_model state
    boot_truth_ref: str               # link to BootTruthBundle
    order_state_ref: str              # link to OrderState
    
    # Relational & Temporal
    active_epoch: str
    genre_mode: str
    dependency_edges: List[Dict[str, str]]  # relational graph of active actors/services
    recent_precedents: List[str]            # vector memory recall identifiers
    
    # Governance
    trust_zone_state: Dict[str, str]        # domain-specific trust statuses
    epoch_strictness: float

class HeraldState(BaseModel):
    """The state of Manwë, the lawful herald of manifestation."""
    herald_id: str
    device_id: str
    runtime_identity: str             # e.g. SPIFFE ID or Cert Fingerprint
    
    # Ties to the constitutional Trees
    boot_truth_status: BootTruthStatus
    attested_state_ref: Optional[str] = None # Phase VI: Ref to AttestedNodeState
    current_epoch: str
    current_score: float
    current_manifold: Optional[str]
    choir_verdict: Optional[str] = None # Phase I: arda.ainur result (heralded, withheld, vetoed)
    choir_confidence: float = 0.0
    
    status: str = "active"
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
