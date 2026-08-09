from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

try:
    from schemas.phase1_models import StabilityClass, BootTruthStatus, BootTruthBundle, OrderState, HeraldState
except Exception:
    from backend.schemas.phase1_models import StabilityClass, BootTruthStatus, BootTruthBundle, OrderState, HeraldState

class WorldManifoldSnapshot(BaseModel):
    manifold_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    world_state_hash: str
    boot_truth_ref: str
    formation_truth_ref: str
    order_state_ref: str
    formation_order_ref: str
    genesis_score_ref: str
    covenant_ref: str
    active_epoch: str
    genre_mode: str
    # --- PHASE III/IV: Resonance & Quorum ---
    collective_resonance_ref: Optional[str] = None
    triune_health_score: float = 1.0
    quorum_status: str = "resonant"             # Phase IV (resonant, degraded, fractured, vetoed)
    nodes_verified: int = 1
    nodes_silent: int = 0
    nodes_fractured: int = 0
    dependency_edges: List[Dict[str, str]] = Field(default_factory=list)
    # --- PHASE V: Kernel Bridge ---
    kernel_integrity_score: float = 1.0
    protected_processes_count: int = 0
    kernel_bridge_status: str = "connected"      # Phase V: connected, monitoring, fractured
    # --- PHASE VI: Pre-Boot Sovereignty ---
    attestation_ref: Optional[str] = None
    measured_birth_hash: Optional[str] = None
    boot_lineage_status: str = "unknown"         # Phase VI: lawful, fractured, unverified
    # -------------------------------------
    # --- PHASE VII: Kernel Sovereignty ---
    is_substrate_sovereign: bool = False
    active_interceptors: List[str] = Field(default_factory=list)
    denied_exec_count: int = 0
    lineage_integrity_score: float = 1.0
    # -------------------------------------
    recent_precedents: List[str] = Field(default_factory=list)
    trust_zone_state: Dict[str, str] = Field(default_factory=dict)
    epoch_strictness: float
    signature_ref: Optional[str] = None
    signature_algorithm: Optional[str] = None
    signature: Optional[str] = None
    signature_valid: Optional[bool] = None

# Phase II: Formation & Covenant State
# Using string literals for status to ensure cross-package compatibility.
# Status values: "lawful", "unlawful", "fractured", "pending"

class FormationManifest(BaseModel):
    manifest_id: str
    version: str
    expected_pcr_constraints: Dict[int, str]
    required_boot_components: List[str]
    required_early_services: List[str]
    forbidden_pre_herald_services: List[str]
    allowed_workloads: Dict[str, str] = Field(default_factory=dict) # workload_id -> hash
    genesis_score_id: str
    failure_policy: str = "veto"
    signature: Optional[str] = None
    public_key_pem: Optional[str] = None

class FormationTruthBundle(BaseModel):
    formation_truth_id: str
    boot_truth_ref: str
    manifest_ref: str
    status: str
    component_verification: Dict[str, bool] = Field(default_factory=dict)
    measurement_consistency: float = 0.0
    sealed_identity_seed: str = ""
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Sophia Dashboard detail fields
    pcr_satisfied: Optional[bool] = None
    secure_boot_enabled: Optional[bool] = None
    manifest_valid: Optional[bool] = None

class FormationOrderState(BaseModel):
    formation_order_id: str
    status: str = "pending"
    verified_sequence: List[str] = Field(default_factory=list)
    missing_steps: List[str] = Field(default_factory=list)
    forbidden_steps_seen: List[str] = Field(default_factory=list)
    order_score: float = 0.0
    strictness: float = 0.5

class GenesisScore(BaseModel):
    genesis_score_id: str
    genesis_epoch: str
    genre_mode: str
    strictness: float
    seed_policy_hash: str
    signature: str
    loaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class HandoffCovenant(BaseModel):
    covenant_id: str
    formation_truth_ref: str
    formation_order_ref: str
    genesis_score_ref: str
    herald_id_ref: str
    preboot_covenant_ref: Optional[str] = None
    status: str = "pending"
    runtime_permission: bool = False
    choir_verdict: Optional[str] = None
    choir_result: Optional[Any] = None
    choir_confidence: float = 0.0
    reason: Optional[str] = None
