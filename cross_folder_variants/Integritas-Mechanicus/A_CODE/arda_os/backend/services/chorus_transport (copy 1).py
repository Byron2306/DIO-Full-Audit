import logging
import asyncio
import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

HAS_HTTPX = False
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    pass

from backend.schemas.phase4_models import HeartbeatEnvelope
from backend.services.heartbeat_signer import get_heartbeat_signer
from backend.services.arda_fabric_middleware import get_arda_fabric_middleware

logger = logging.getLogger(__name__)

class ChorusTransportService:
    """
    The Nervous System of the Chorus.
    Handles the asynchronous distribution of heartbeat envelopes across the Triune mesh.
    """
    
    def __init__(self, timeout: float = 2.0):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._peers: List[str] = []
        self._middleware = get_arda_fabric_middleware()
        
    async def start(self):
        """Initialize the transport client."""
        if HAS_HTTPX and not self._client:
            self._client = httpx.AsyncClient()
        
        # Load peer list from environment (Phase III style)
        peer_nodes = os.environ.get("PEER_NODES", "").split(",")
        self._peers = [p.strip() for p in peer_nodes if p.strip()]
        logger.info(f"PHASE IV: Chorus Transport started with {len(self._peers)} static peers.")

    async def stop(self):
        """Shutdown the transport client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("PHASE IV: Chorus Transport stopped.")

    async def broadcast_envelope(self, envelope: HeartbeatEnvelope):
        """
        Multicast a signed envelope to all known peers.
        Uses a fan-out strategy with concurrent async requests.
        """
        if not self._client or not self._peers:
            return
            
        tasks = []
        payload = envelope.model_dump() if hasattr(envelope, 'model_dump') else envelope.dict()
        
        for peer in self._peers:
            url = f"{peer}/metatron/resonance/heartbeat"
            tasks.append(self._send_to_peer(url, payload))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Audit results (Phase IV silence tracking begins here)
        success_count = sum(1 for r in results if r is True)
        if success_count < len(self._peers):
            logger.debug(f"PHASE IV: Partial transport failure ({success_count}/{len(self._peers)} reached)")

    async def _send_to_peer(self, url: str, payload: Dict[str, Any]) -> bool:
        """Single peer transmission attempt."""
        try:
            # Phase VII: Arda-Fabric Secure Middleware
            headers = {"Content-Type": "application/json"}
            headers, final_payload = await self._middleware.prepare_outbound_request(url, headers, payload)
            
            response = await self._client.post(url, json=final_payload, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                return True
            logger.warning(f"PHASE IV: Peer {url} returned {response.status_code}")
        except Exception as e:
            logger.debug(f"PHASE IV: Failed to reach peer {url}: {e}")
        return False

# Global singleton
chorus_transport = ChorusTransportService()

def get_chorus_transport() -> ChorusTransportService:
    global chorus_transport
    return chorus_transport
