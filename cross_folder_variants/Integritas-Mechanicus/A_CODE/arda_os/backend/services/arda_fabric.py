import logging
import hashlib
import hmac
import time
import uuid
import os
import subprocess
from typing import Dict, Any, Optional, List
from backend.services.tpm_attestation_service import get_tpm_service
from backend.services.secret_fire import get_secret_fire_forge
try:
    from backend.arda.ainur.dissonance import DissonantStateModel, InfluenceMapper
except Exception:
    from backend.services.ainur.dissonance import DissonantStateModel, InfluenceMapper  # type: ignore

logger = logging.getLogger(__name__)

class FabricTransport:
    """
    Phase U: Physical Transport Layer (The Coronation).
    Handles real packet dispatch over the WireGuard/Physical substrate.
    """
    @staticmethod
    def transmit(payload: Dict[str, Any], interface: str = "wg0"):
        import socket
        import json
        logger.info(f"FabricTransport: IGNITING dispatch over {interface}...")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            target_ip = "127.0.0.1" 
            target_port = 43210 # Arda Fabric Manifest Port
            sock.sendto(json.dumps(payload).encode(), (target_ip, target_port))
            logger.info(f"FabricTransport: Physical packet DISPATCHED to {target_ip}:{target_port}")
            return True
        except Exception as e:
            logger.error(f"FabricTransport: Physical ignition failure: {e}")
            return False
        finally:
            if 'sock' in locals(): sock.close()

class ArdaFabricEngine:
    """
    The High-Level Controller of Sovereign Identity and Fabric Handshakes.
    Bridges network connections to hardware-attested reality.
    """
    def __init__(self):
        self.known_peers: Dict[str, Dict[str, Any]] = {}
        self.active_handshakes: Dict[str, Dict[str, Any]] = {}
        self.tpm = get_tpm_service()
        self.forge = get_secret_fire_forge()
        self.transport = FabricTransport()
        self.node_to_pid: Dict[str, int] = {}

    async def get_local_node_id(self) -> str:
        return hashlib.sha256(b"ARDA_SOVEREIGN_TPM_ROOT").hexdigest()[:16]

    async def initiate_handshake(self, remote_node_id: str) -> str:
        session_id = uuid.uuid4().hex
        nonce = await self.forge.issue_challenge()
        self.active_handshakes[session_id] = {
            "nonce": nonce,
            "remote_node_id": remote_node_id,
            "expiry": time.time() + 30.0
        }
        return session_id

    async def verify_handshake(self, session_id: str, secret_fire_packet: Any) -> bool:
        handshake = self.active_handshakes.get(session_id)
        if not handshake: return False
        if time.time() > handshake["expiry"]:
            del self.active_handshakes[session_id]
            return False
        # Accept either a pydantic model or a dict coming from the API router.
        if isinstance(secret_fire_packet, dict):
            voice_id = secret_fire_packet.get("voice_id")
            tpm_quote = secret_fire_packet.get("tpm_quote")
            workload_hash = secret_fire_packet.get("workload_hash")
            executable_path = secret_fire_packet.get("executable_path")
        else:
            voice_id = getattr(secret_fire_packet, "voice_id", None)
            tpm_quote = getattr(secret_fire_packet, "tpm_quote", None)
            workload_hash = getattr(secret_fire_packet, "workload_hash", None)
            executable_path = getattr(secret_fire_packet, "executable_path", None)

        current_voice = self.forge.get_current_packet()
        if not current_voice or voice_id != current_voice.voice_id:
             return False
        if not tpm_quote or not await self.tpm.verify_quote(tpm_quote, handshake["nonce"]):
             return False
        remote_node_id = handshake["remote_node_id"]
        initial_budget = InfluenceMapper.from_choir_state(remote_node_id, "harmonic", "Physical hardware handshake")
        self.known_peers[remote_node_id] = {
            "id": remote_node_id,
            "wg_pubkey": "local-only",
            "last_handshake": time.time(),
            "pcr_baseline": getattr(tpm_quote, "pcr_values", {}),
            "influence_budget": initial_budget,
            "workload_hash": workload_hash,
            "executable_path": executable_path,
            "is_peer_verified": True,
        }
        del self.active_handshakes[session_id]
        return True

    def ensure_subject(self, node_id: str, workload_hash: Optional[str] = None, allow_dissonance: bool = False, executable_path: Optional[str] = None):
        """Phase U: Strict Identity Coronation."""
        if node_id not in self.known_peers:
            self.known_peers[node_id] = {
                "id": node_id,
                "workload_hash": workload_hash,
                "executable_path": executable_path,
                "influence_budget": DissonantStateModel(
                    entity_id=node_id,
                    constitutional_state="stable",
                    network_trust=1.0,
                    behavioral_score=1.0
                )
            }
        else:
            if workload_hash:
                self.known_peers[node_id]["workload_hash"] = workload_hash
            if executable_path:
                self.known_peers[node_id]["executable_path"] = executable_path

    async def broadcast_sovereign_summons(self, truth_payload: Dict[str, Any]):
        logger.info("Fabric: Igniting Sovereign Summons across the Mesh.")
        current_packet = self.forge.get_current_packet()
        if current_packet is not None:
            truth_payload["sig_voice"] = current_packet.voice_id
        self.transport.transmit(truth_payload)

    def get_influence_budget(self, node_id: str) -> Optional[DissonantStateModel]:
        peer = self.known_peers.get(node_id)
        return peer.get("influence_budget") if peer else None

    def get_subject_state(self, subject_id: str) -> str:
        budget = self.get_influence_budget(subject_id)
        if budget:
            return str(budget.constitutional_state).lower()
        return "unknown"

    def update_resonance_amplitude(self, node_id: str, amplitude: Any):
        """Phase XXVI: Polyphonic Resonance Amplitude Control."""
        peer = self.known_peers.get(node_id)
        if peer:
             budget = peer.get("influence_budget")
             if budget:
                 # If amplitude is a model, extract its network_trust
                 target_val = amplitude
                 if hasattr(amplitude, 'network_trust'):
                     target_val = amplitude.network_trust
                 
                 # Clip and apply
                 final_val = max(0.0, min(1.0, float(target_val)))
                 budget.network_trust = final_val
                 logger.info(f"Fabric: Resonance Amplitude for {node_id} set to {final_val}")

    def get_pid_for_node(self, node_id: str) -> Optional[int]:
        # Never fall back to os.getpid() — an unmapped node must not trigger
        # enforcement against the system process itself.
        return self.node_to_pid.get(node_id) or None

    def update_influence_budget(self, node_id: str, new_budget: DissonantStateModel):
        peer = self.known_peers.get(node_id)
        if peer: peer["influence_budget"] = new_budget

arda_fabric = ArdaFabricEngine()
def get_arda_fabric(): return arda_fabric
