from pydantic import BaseModel, ConfigDict
from typing import Optional

class DissonantStateModel(BaseModel):
    """
    The Constitutional State of an entity in Arda (formerly ResonanceStateModel).
    This replaces binary 'allow/deny' with the 'Resonance of and for the Machine'.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    entity_id: str
    constitutional_state: str  # harmonic, strained, dissonant, muted, fallen

    quorum_weight: float = 0.0
    network_trust: float = 0.0
    exec_rights: str = "observer"
    memory_class: str = "restricted"
    syscall_scope: str = "limited"
    secret_access: bool = False
    egress_rights: str = "none" # "none", "sanctuary_only", "star_seal", "void_open"

    parent_ref: Optional[str] = None
    node_ref: Optional[str] = None
    epoch: Optional[str] = None
    reason: Optional[str] = None

class InfluenceMapper:
    """
    The Influence Mapper (formerly Resonance Mapper).
    Maps Choir Verdicts into physical Constitutional States (Dissonance Models).
    This defines the 'volume' of an entity's existence in Arda.
    """

    @staticmethod
    def from_choir_state(entity_id: str, state: str, reason: str = None) -> DissonantStateModel:
        state = state.lower()
        
        # Harmonic: Fully lawful, fresh, witnessed, coherent.
        if state in ["lawful", "harmonic", "clear", "heralded"]:
            return ResonanceStateModel(
                entity_id=entity_id,
                constitutional_state="harmonic",
                quorum_weight=1.0,
                network_trust=1.0,
                exec_rights="herald",
                memory_class="protected",
                syscall_scope="full",
                secret_access=True,
                egress_rights="sanctuary_only",
                reason=reason
            )
            
        # Strained: Mostly lawful, but carrying warning signals.
        elif state in ["strained", "dimmed", "troubled", "remembered"]:
            return ResonanceStateModel(
                entity_id=entity_id,
                constitutional_state="strained",
                quorum_weight=0.5,
                network_trust=0.6,
                exec_rights="worker",
                memory_class="normal",
                syscall_scope="limited",
                secret_access=False,
                reason=reason
            )
            
        # Dissonant: Contradictory, stale, or partially corrupted.
        elif state in ["dissonant", "fractured", "flowing", "stalled"]:
            return ResonanceStateModel(
                entity_id=entity_id,
                constitutional_state="dissonant",
                quorum_weight=0.0,
                network_trust=0.1,  # Can only talk to recovery services
                exec_rights="observer",
                memory_class="restricted",
                syscall_scope="minimal",
                secret_access=False,
                reason=reason
            )
            
        # Muted: Still present, but no meaningful voice remains (The Voice of Sauron denied).
        elif state in ["muted", "fading", "withheld"]:
            return ResonanceStateModel(
                entity_id=entity_id,
                constitutional_state="muted",
                quorum_weight=0.0,
                network_trust=0.0,
                exec_rights="quarantine",
                memory_class="quarantine",
                syscall_scope="none",
                secret_access=False,
                reason=reason
            )
            
        # Fallen: Persistently dissonant, exiled (The Doom of Mandos).
        else: # "fallen", "voided", "false", "vetoed", "dark"
            return ResonanceStateModel(
                entity_id=entity_id,
                constitutional_state="fallen",
                quorum_weight=0.0,
                network_trust=0.0,
                exec_rights="none",
                memory_class="none",
                syscall_scope="none",
                secret_access=False,
                reason=reason
            )

    @staticmethod
    def resolve_inheritance(parent: DissonantStateModel, node: DissonantStateModel) -> DissonantStateModel:
        """
        A child cannot exceed the resonant amplitude of its parent or host node.
        """
        states = ["fallen", "muted", "dissonant", "strained", "harmonic"]
        
        p_idx = states.index(parent.constitutional_state) if parent.constitutional_state in states else 0
        n_idx = states.index(node.constitutional_state) if node.constitutional_state in states else 0
        
        # Take the lowest state
        inherited_idx = min(p_idx, n_idx)
        inherited_state = states[inherited_idx]
        
        # Use a mock ID to get the budgetary limits, caller must override ID
        return InfluenceMapper.from_choir_state("child-inheritance", inherited_state, reason="Inherited constraint")

# --- Sovereign Aliases (The Tolkienized Names) ---
ResonanceStateModel = DissonantStateModel
ResonanceMapper = InfluenceMapper
