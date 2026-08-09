from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

# --- PHASE III: COLLECTIVE TRUTH & RESONANCE ---

class ResonanceStatus(str, Enum):
    RESONANT = "resonant"       # Node is in full harmony with the Triune
    DISSONANT = "dissonant"     # Node state is drifting or tampered
    SILENT = "silent"           # Node is unreachable or offline
    FRACTURED = "fractured"     # Node's Formation Covenant was revoked

class HeartbeatProof(BaseModel):
    proof_id: str
    node_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    manifold_state_hash: str
    order_pulse_ref: str
    signature: str              # Signed by node's Herald Identity
    status: ResonanceStatus = ResonanceStatus.RESONANT
    kernel_integrity: float = 1.0       # Phase V: Kernel-Bridge integrity score
    manifested_pids: int = 0            # Phase V: Count of active protected processes
    # --- PHASE VI: Pre-Boot Sovereignty ---
    attestation_ref: Optional[str] = None
    preboot_covenant_ref: Optional[str] = None
    measured_formation_hash: Optional[str] = None
    boot_verdict_lineage: Optional[str] = None

class HarmonicScore(BaseModel):
    node_id: str
    liveness: float = 0.0       # Time since last heartbeat
    order_consistency: float = 0.0 # From Order Engine stability
    truth_integrity: float = 0.0 # From Formation Covenant status
    composite_score: float = 0.0 # Weighted average

class TriuneHealth(BaseModel):
    cluster_id: str
    nodes_active: int
    nodes_resonant: int
    collective_score: float
    is_fully_lawful: bool
    last_unison_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    active_vetoes: List[str] = Field(default_factory=list)

class CollectiveResonanceState(BaseModel):
    resonance_id: str
    epoch_id: str
    node_scores: Dict[str, HarmonicScore]
    cluster_health: TriuneHealth
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
