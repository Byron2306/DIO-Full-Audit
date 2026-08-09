import logging
import time
import hashlib
import hmac
from typing import Dict, Any, Optional, List, Tuple
from backend.services.arda_fabric import get_arda_fabric
from backend.services.secret_fire import get_secret_fire_forge
from backend.services.gates_of_night import get_boundary_guard

logger = logging.getLogger(__name__)

class ArdaFabricMiddleware:
    """
    Arda-Fabric Middleware (Phase VII: The Pipe is Part of the Song).
    Intercepts outbound communications to ensure they are hardware-attested
    and bound to a 'Voice of Eru' sovereign summons.
    """
    
    def __init__(self):
        self.fabric = get_arda_fabric()
        self.forge = get_secret_fire_forge()
        # No local session_keys; use the central fabric trust
        
    async def prepare_outbound_request(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """
        Prepares an outbound request by adding Arda-Fabric attestations.
        """
        target_node_id = self._extract_node_id(url)
        if not target_node_id:
            # External (Internal/Unsafe) request: THE DOORS OF NIGHT
            logger.debug(f"Fabric Middleware: Request to {url} is EXTERNAL (Unattested). Consulting the Doors...")
            
            boundary_guard = get_boundary_guard()
            allowed = await boundary_guard.evaluate_egress(url, {"entity_id": headers.get("X-Seraph-Entity-ID", "unknown")})
            
            if not allowed:
                 headers["X-Arda-Security-Class"] = "void_egress_denied"
                 return headers, payload
            
            headers["X-Arda-Security-Class"] = "external_unattested_sanctuary"
            return headers, payload

        # 1. Check for valid handshake / session in Global Fabric
        session_key = self.fabric.get_session_key(target_node_id)
        if not session_key:
            logger.info(f"Fabric Middleware: No active session for {target_node_id}. Negotiating Trust...")
            # Simulate a JIT handshake
            session_id = await self.fabric.initiate_handshake(target_node_id)
            # In a real OS, we'd wait for the peer's Secret Fire response here.
            # For the bridge, we simulate an instant transition to LAWFUL.
            # (In reality, the first packet might be queued until handshake finishes)
            mock_packet = type('obj', (object,), {"tpm_quote": {"pcr_mask": "0,7"}, "voice_id": self.forge.get_current_packet().voice_id if self.forge.get_current_packet() else None})
            await self.fabric.verify_handshake(session_id, mock_packet)
            session_key = self.fabric.get_session_key(target_node_id)

        logger.info(f"Fabric Middleware: Target Node ID extracted as '{target_node_id}'")
        
        if not session_key:
             logger.warning(f"Fabric Middleware: Failed to establish trust with {target_node_id}. Aborting.")
             return headers, payload

        # 2. Add Voice of Eru Context
        # Every packet is bound to the latest sovereign summons
        current_packet = self.forge.get_current_packet()
        if current_packet and current_packet.voice_id:
            headers["X-Arda-Voice-ID"] = current_packet.voice_id
            headers["X-Arda-Sweep-ID"] = current_packet.sweep_id or "unknown"
            
        
        # Check Influence Budget
        budget = self.fabric.get_influence_budget(target_node_id)
        if budget:
            if budget.network_trust == 0.0:
                logger.warning(f"Fabric Middleware: Refusing to sign outbound packet. Target node {target_node_id} is MUTED.")
                headers["X-Arda-Security-Class"] = "fabric_muted"
                return headers, payload
            elif budget.network_trust < 1.0:
                logger.info(f"Fabric Middleware: Outbound packet to {target_node_id} attenuated (state: {budget.constitutional_state}).")
                headers["X-Arda-Security-Class"] = "substrate_attenuated"
            else:
                headers["X-Arda-Security-Class"] = "substrate_attested"
        else:
             headers["X-Arda-Security-Class"] = "substrate_attested"

        # 3. Sign the Request Body (The Witnessed Pipe)
        payload_bytes = str(payload).encode()
        signature = hmac.new(session_key.encode(), payload_bytes, hashlib.sha256).hexdigest()
        
        headers["X-Arda-Packet-Signature"] = signature
        headers["X-Arda-Node-ID"] = await self.fabric.get_local_node_id()
        
        logger.info(f"Fabric Middleware: Request to {target_node_id} SIGNED with session key.")
        return headers, payload

    async def verify_inbound_request(self, node_id: str, headers: Dict[str, str], body: bytes) -> bool:
        """
        Verifies an inbound request from a peer node.
        Ensures it is bound to a valid Voice and has a correct signature.
        """
        voice_id = headers.get("X-Arda-Voice-ID")
        signature = headers.get("X-Arda-Packet-Signature")
        
        # 1. Voice Verification (The Sovereign Check)
        current_packet = self.forge.get_current_packet()
        if not current_packet or voice_id != current_packet.voice_id:
            logger.warning(f"Fabric Ingress: Voice Mismatch! Received {voice_id}, expected {current_packet.voice_id if current_packet else 'none'}")
            return False
            
        # 2. Signature Verification (The Witness Check)
        session_key = self.fabric.get_session_key(node_id)
        if not session_key:
            # Check if this is the first packet and we should negotiate?
            # For Ingress, we UNCONDITIONALLY require an existing session.
            logger.warning(f"Fabric Ingress: Refusing unattested packet from unknown/expired session {node_id}")
            return False
            
        expected_sig = hmac.new(session_key.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(signature), expected_sig):
            logger.warning(f"Fabric Ingress: Signature Dissonance for node {node_id}!")
            return False
            
        # 3. Fabric Muting (The Influence Budget Check)
        budget = self.fabric.get_influence_budget(node_id)
        if budget:
            if budget.network_trust == 0.0:
                 logger.warning(f"Fabric Ingress: Refusing inbound packet. Origin node {node_id} is MUTED.")
                 return False
            elif budget.network_trust < 1.0:
                 logger.info(f"Fabric Ingress: Accepted attenuated packet from {node_id} (state: {budget.constitutional_state}, trust: {budget.network_trust})")
                 return True
                 
        logger.info(f"Fabric Ingress: Request from {node_id} VERIFIED (Lawful Pipe)")
        return True

    def _extract_node_id(self, url: str) -> Optional[str]:
        """Simple extractor for Arda Node IDs from URLs."""
        # For now, we assume peers in CHORUS_TRANSPORT or starting with 'metatron-node-'
        if "node-" in url:
             # Extract e.g. 'node-alpha' from 'http://node-alpha:3000/...'
             parts = url.replace("http://", "").replace("https://", "").split("/")
             domain = parts[0].split(":")[0]
             return domain
        return None

# Global singleton
arda_fabric_middleware = ArdaFabricMiddleware()

def get_arda_fabric_middleware():
    global arda_fabric_middleware
    return arda_fabric_middleware
