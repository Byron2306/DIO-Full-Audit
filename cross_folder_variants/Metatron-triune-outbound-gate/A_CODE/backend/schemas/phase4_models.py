from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum

class SignatureStatus(Enum):
    VERIFIED = "verified"
    INVALID = "invalid"
    EXPIRED = "expired"
    UNKNOWN = "unknown"

class QuorumStatus(Enum):
    RESONANT = "resonant"             # Full quorum, consensus achieved
    DEGRADED = "degraded"             # Quorum met but some peers silent or dissonant
    FRACTURED = "fractured"           # Quorum lost, partition detected
    VETOED = "vetoed"                 # Hard collective veto issued
    PENDING = "pending"               # Still gathering heartbeats

class NodeIdentity(BaseModel):
    """
    Cryptographic identity of an individual Metatron node.
    """
    node_id: str = Field(..., description="Unique node-specific ID (derived from public key)")
    public_key_pem: str = Field(..., description="Public key in PEM format")
    certified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    issuer_id: Optional[str] = None
    fingerprint: str = Field(..., description="SHA256 fingerprint of the identity")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class NodeCertificate(BaseModel):
    """
    Signed certificate binding a node identity to a cluster authority.
    """
    cert_id: str
    node_id: str
    signature: str
    issued_at: datetime
    expires_at: datetime
    is_revoked: bool = False

class HeartbeatEnvelope(BaseModel):
    """
    A transport-safe envelope containing a signed heartbeat.
    """
    envelope_id: str
    signer_node_id: str
    signed_payload: str  # Base64 or JSON string of the proof
    signature: str
    nonce: str
    timestamp_sent: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "v4.0"

class VerifiedHeartbeat(BaseModel):
    """
    A heartbeat that has passed cryptographic and temporal validation.
    """
    proof_id: str
    node_id: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    signature_status: SignatureStatus
    verification_lag_ms: float
    original_timestamp: datetime
    manifold_state_hash: str
    status: str # "resonant", "dissonant", etc.
    sequence_number: int

class QuorumPolicy(BaseModel):
    """
    Constitutional rules for cluster-wide consensus.
    """
    policy_id: str
    min_nodes: int = 3
    supermajority_threshold: float = 0.66  # 2/3 usually
    majority_threshold: float = 0.51
    silence_timeout_seconds: float = 30.0
    drift_tolerance: float = 0.1
    strictness: str = "cluster-enforced"

class QuorumDecision(BaseModel):
    """
    The collective verdict of the chorus on a specific block of truth.
    """
    decision_id: str
    status: QuorumStatus
    consensus_score: float  # 0.0 - 1.0
    nodes_total: int
    nodes_resonant: int
    nodes_dissonant: int
    nodes_silent: int
    active_vetoes: List[str]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PeerState(BaseModel):
    """
    Current view of a specific peer node from the local node's perspective.
    """
    node_id: str
    last_seen_at: datetime
    trust_score: float
    is_trusted: bool
    identity_verified: bool
    status: str
    latency_ms: float

class ClusterView(BaseModel):
    """
    The local node's high-level inventory of the Triune Chorus.
    """
    cluster_id: str
    active_nodes: List[str]
    peers: Dict[str, PeerState]
    total_quorum_score: float
    last_unison_at: Optional[datetime]
    is_split_brain_detected: bool = False

class ResonanceQuorumState(BaseModel):
    """
    Consolidated state of all resonance and quorum logic.
    """
    state_id: str = Field(default_factory=lambda: f"quorum-{datetime.now(timezone.utc).timestamp()}")
    view: ClusterView
    decision: QuorumDecision
    policy_ref: str
    manifold_hash: str
