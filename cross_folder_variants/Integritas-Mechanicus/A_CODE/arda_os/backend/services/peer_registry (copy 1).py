import os
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

try:
    from schemas.phase4_models import NodeIdentity, PeerState
    from services.telemetry_chain import tamper_evident_telemetry
except Exception:
    from backend.schemas.phase4_models import NodeIdentity, PeerState
    from backend.services.telemetry_chain import tamper_evident_telemetry

logger = logging.getLogger(__name__)

class PeerRegistryService:
    """
    The Census of the Chorus.
    Tracks all legitimate nodes that are authorized to sing in the Triune.
    """
    
    def __init__(self, registry_path: str = "config/peer_registry.json"):
        self.registry_path = registry_path
        self._peers: Dict[str, NodeIdentity] = {}
        self._states: Dict[str, PeerState] = {}
        
    def initialize(self):
        """Load the known peer identities from the registry."""
        if os.path.exists(self.registry_path):
            self._load_registry()
        else:
            logger.info("PHASE IV: Peer registry not found. Initializing empty.")
            self._save_registry()

    def get_peer(self, node_id: str) -> Optional[NodeIdentity]:
        """Return the identity of a specific node."""
        return self._peers.get(node_id)

    def register_peer(self, identity: NodeIdentity):
        """Register a new node into the chorus."""
        self._peers[identity.node_id] = identity
        
        # Initialize state
        self._states[identity.node_id] = PeerState(
            node_id=identity.node_id,
            last_seen_at=datetime.now(timezone.utc),
            trust_score=1.0,
            is_trusted=True,
            identity_verified=True,
            status="discovered",
            latency_ms=0.0
        )
        
        self._save_registry()
        logger.info(f"PHASE IV: Registered new peer {identity.node_id}")

    def update_peer_state(self, node_id: str, status: str, latency_ms: float = 0.0):
        """Update the perceived health of a peer."""
        if node_id in self._states:
            state = self._states[node_id]
            state.last_seen_at = datetime.now(timezone.utc)
            state.status = status
            state.latency_ms = latency_ms
            
            # Simple decay logic can go here
            if status == "dissonant":
                state.trust_score -= 0.1
                if state.trust_score < 0.5:
                    state.is_trusted = False
            elif status == "resonant":
                state.trust_score = min(1.0, state.trust_score + 0.05)
                if state.trust_score >= 0.8:
                    state.is_trusted = True

    def get_all_peers(self) -> List[NodeIdentity]:
        return list(self._peers.values())

    def get_peer_state(self, node_id: str) -> Optional[PeerState]:
        return self._states.get(node_id)

    def _load_registry(self):
        """Load identities from disk."""
        try:
            with open(self.registry_path, "r") as f:
                data = json.load(f)
                for item in data:
                    identity = NodeIdentity(**item)
                    self._peers[identity.node_id] = identity
            logger.info(f"PHASE IV: Loaded {len(self._peers)} peers from registry.")
        except Exception as e:
            logger.error(f"PHASE IV: Failed to load peer registry: {e}")

    def _save_registry(self):
        """Save identities to disk."""
        try:
            os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
            with open(self.registry_path, "w") as f:
                # Store as a list of dicts
                json.dump([p.model_dump() for p in self._peers.values()], f, default=str, indent=2)
        except Exception as e:
            logger.error(f"PHASE IV: Failed to save peer registry: {e}")

# Global singleton
peer_registry = PeerRegistryService()

def get_peer_registry() -> PeerRegistryService:
    global peer_registry
    if not peer_registry._peers and not os.path.exists(peer_registry.registry_path):
        peer_registry.initialize()
    return peer_registry
