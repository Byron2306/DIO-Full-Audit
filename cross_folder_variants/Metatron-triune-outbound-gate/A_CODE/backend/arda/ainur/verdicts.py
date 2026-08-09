from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Literal, Optional
from datetime import datetime

VerdictState = Literal[
    "lawful", "fractured", "radiant", "dimmed", "false",
    "flowing", "strained", "stalled",
    "remembered", "fading", "lost",
    "clear", "troubled", "dark",
    "heralded", "withheld", "vetoed", "unknown",
    "harmonic", "dissonant", "voided", "fallen", "inhibited"
]

class Freshness(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    observed_at: float  # Unix timestamp
    window_ms: float
    nonce: Optional[str] = None
    epoch: Optional[str] = None

class ChoralSweep(BaseModel):
    """
    The Root Choral Challenge.
    Represents the sovereign call for a governance sweep across Arda.
    All Ainur responses and Secret Fire packets must resonate with this ID.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    sweep_id: str
    issued_at: float
    expires_at: float
    theme: str = "general_governance"
    authority_ref: Optional[str] = None # Link to the approved Governance mandate

class IluvatarVoiceChallenge(BaseModel):
    """
    The Voice of Eru — The Sovereign Summons.
    A pre-verdict protocol object that summons the whole choir to answer
    in one lawful moment. All subordinate nonces derive from this root.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    voice_id: str
    root_nonce: str
    issued_at: float
    expires_at: float
    epoch: str
    sweep_id: str
    issuer: str = "eru-voice"
    cadence_scope: str = "triune" # micro/meso/macro or full triune sweep
    derivation_mode: str = "hmac" # or hkdf
    tier_nonces: Dict[str, str] = Field(default_factory=dict) # micro, meso, macro
    ainur_nonces: Dict[str, str] = Field(default_factory=dict) # varda, vaire, etc.
    witness_quorum_ref: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SecretFirePacket(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    # Identity
    node_id: str
    covenant_id: str
    executable_path: Optional[str] = None
    
    # Ancestral Lineage (Voice of Eru)
    voice_id: Optional[str] = None
    root_nonce_ref: Optional[str] = None
    tier: Optional[str] = None
    ainur_target: Optional[str] = None
    
    sweep_id: Optional[str] = None # Linking the response to the root choral sweep

    # Challenge
    nonce: str
    issued_at: float
    expires_at: float

    # Response
    responded_at: float
    latency_ms: float

    # Reality bindings
    epoch: str
    monotonic_counter: int

    # Evidence anchors
    attestation_digest: str
    order_digest: str
    runtime_digest: str
    
    # Witnessing
    witness_id: str
    witness_signature: str

    # Optional / Behavioural (Defaults at the end)
    workload_hash: Optional[str] = None # SHA256 of the process binary
    entropy_digest: Optional[str] = None
    cadence_profile: Dict[str, float] = Field(default_factory=dict)
    replay_suspected: bool = False
    freshness_valid: bool = True
    tpm_quote: Optional[Dict[str, Any]] = None

class EvidencePacket(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    source: str
    evidence: Dict[str, Any]
    freshness: Freshness
    
    # Witnessed Resonance Linkage (The Voice of Eru)
    voice_id: Optional[str] = None
    sweep_id: Optional[str] = None
    secret_fire_ref: Optional[str] = None # The specific Secret Fire Response id (nonce)
    tier: Optional[str] = None
    ainur_target: Optional[str] = None
    
    confidence: float = 1.0

class AinurVerdict(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    ainur: str
    state: VerdictState
    score: float
    reasons: List[str]
    testimony: Optional[str] = None
    evidence: List[Any] = Field(default_factory=list)

class ChoirVerdict(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    overall_state: VerdictState
    heralding_allowed: bool
    confidence: float
    ainur: List[AinurVerdict]
    reasons: List[str]
    collective_testimony: Optional[str] = None

    subject_id: Optional[str] = None      # canonical runtime identity
    node_id: Optional[str] = None         # fabric / cluster identity
    voice_id: Optional[str] = None
    sweep_id: Optional[str] = None
    covenant_id: Optional[str] = None
    epoch: Optional[str] = None

    observed_at: float = Field(default_factory=lambda: datetime.now().timestamp())
