import hashlib
import hmac
import logging
import uuid
import time
import os
import sys
from typing import Dict, Any, Optional, List, Set
from dataclasses import asdict
from backend.arda.ainur.verdicts import SecretFirePacket, IluvatarVoiceChallenge
from backend.services.tpm_attestation_service import get_tpm_service

logger = logging.getLogger(__name__)

class SecretFireService:
    """
    The Forge of the Secret Fire.
    Handles challenge-response cycles and reality witnessing.
    """
    def __init__(self, node_id: str = "node-0"):
        self.node_id = node_id
        self.active_challenges: Dict[str, float] = {}  # nonce -> expiry
        self.active_nonces: Dict[str, SecretFirePacket] = {}  # nonce/current_packet -> packet
        self.active_voices: Dict[str, IluvatarVoiceChallenge] = {}  # voice_id -> voice
        self.consumed_nonces: Set[str] = set()  # track previously used nonces for replay detection
        self.witness_id = "quorum-witness-alpha"

    def derive_nonce(self, root_nonce: str, label: str) -> str:
        """Derives a subordinate nonce genealogically linked to the root."""
        return hmac.new(
            root_nonce.encode(),
            label.encode(),
            hashlib.sha256
        ).hexdigest()

    async def issue_voice_of_eru(self, epoch: str, sweep_id: str) -> IluvatarVoiceChallenge:
        """Issues the sovereign 'Voice of Eru' challenge."""
        voice_id = f"voice-{uuid.uuid4().hex[:12]}"
        root_nonce = uuid.uuid4().hex
        
        # Derive Tiers
        tier_nonces = {
            t: self.derive_nonce(root_nonce, t)
            for t in ["micro", "meso", "macro"]
        }
        
        # Derive Ainur targets (Varda, VairÃ«, etc.)
        ainur_targets = ["varda", "vaire", "manwe", "mandos", "ulmo"]
        ainur_nonces = {
            a: self.derive_nonce(root_nonce, a)
            for a in ainur_targets
        }
        
        voice = IluvatarVoiceChallenge(
            voice_id=voice_id,
            root_nonce=root_nonce,
            issued_at=time.time(),
            expires_at=time.time() + 10.0,
            epoch=epoch,
            sweep_id=sweep_id,
            tier_nonces=tier_nonces,
            ainur_nonces=ainur_nonces
        )
        
        self.active_voices[voice_id] = voice
        self.active_challenges[root_nonce] = voice.expires_at
        # Register derived nonces in active_challenges
        for n in tier_nonces.values():
            self.active_challenges[n] = voice.expires_at
        for n in ainur_nonces.values():
            self.active_challenges[n] = voice.expires_at
            
        logger.info(f"Forge: Issued Voice of Eru {voice_id} (root: {root_nonce[:8]})")
        return voice

    async def answer_voice(self, 
                           voice: IluvatarVoiceChallenge, 
                           ainur_target: Optional[str],
                           tier: Optional[str],
                           covenant_id: str,
                           epoch: str,
                           counter: int,
                           attestation_digest: str,
                           order_digest: str,
                           runtime_digest: str,
                           entropy_digest: Optional[str] = None,
                           cadence_profile: Dict[str, float] = None) -> SecretFirePacket:
        """Forges a response specifically to the Voice of Eru."""
        
        # Determine which nonce to answer
        nonce = voice.root_nonce
        if ainur_target and ainur_target in voice.ainur_nonces:
            nonce = voice.ainur_nonces[ainur_target]
        elif tier and tier in voice.tier_nonces:
            nonce = voice.tier_nonces[tier]
            
        return await self.forge_packet(
            nonce=nonce,
            covenant_id=covenant_id,
            epoch=epoch,
            counter=counter,
            attestation_digest=attestation_digest,
            order_digest=order_digest,
            runtime_digest=runtime_digest,
            entropy_digest=entropy_digest,
            cadence_profile=cadence_profile,
            sweep_id=voice.sweep_id,
            voice_id=voice.voice_id,
            root_nonce_ref=voice.root_nonce,
            tier=tier,
            ainur_target=ainur_target
        )

    async def issue_challenge(self, ttl_ms: float = 5000) -> str:
        """Issues a new fresh nonce for a reality challenge."""
        nonce = uuid.uuid4().hex
        expiry = time.time() + (ttl_ms / 1000.0)
        self.active_challenges[nonce] = expiry
        logger.info(f"Forge: Issued challenge {nonce[:8]} (expires in {ttl_ms}ms)")
        return nonce

    def get_current_packet(self) -> Optional[SecretFirePacket]:
        """Returns the most recent forged packet for this node."""
        return self.active_nonces.get("current_packet")

    async def forge_packet(self, 
                             nonce: str, 
                             covenant_id: str,
                             epoch: str,
                             counter: int,
                             attestation_digest: str,
                             order_digest: str,
                             runtime_digest: str,
                             entropy_digest: Optional[str] = None,
                             cadence_profile: Dict[str, float] = None,
                             sweep_id: Optional[str] = None,
                             voice_id: Optional[str] = None,
                             root_nonce_ref: Optional[str] = None,
                             tier: Optional[str] = None,
                             ainur_target: Optional[str] = None) -> SecretFirePacket:
        """Responds to a challenge and captures the witnessed moment."""
        responded_at = time.time()
        
        # 1. Validate Challenge Persistence
        expiry = self.active_challenges.get(nonce)

        freshness_valid = False
        replay_suspected = False

        if expiry is None:
            logger.warning(f"Forge: Nonce {nonce[:8]} unknown or expired!")
            if nonce in self.consumed_nonces:
                replay_suspected = True
                logger.warning(f"Forge: Nonce {nonce[:8]} detected as replayed!")
        else:
            freshness_valid = responded_at <= expiry
            if not freshness_valid:
                logger.warning(f"Forge: Nonce {nonce[:8]} expired before response!")
            
            # Consume nonce (No reuse rule)
            del self.active_challenges[nonce]
            self.consumed_nonces.add(nonce)

        # 2. Calculate Latency (mocked for now)
        issued_at = responded_at - 0.01 
        latency_ms = (responded_at - issued_at) * 1000.0

        # 3. Retrieve Hardware Witnessing (Sight of ManwÃ«)
        tpm_service = get_tpm_service()
        indices_to_quote = [0, 1, 7, 11]
        print(f"DEBUG: SecretFireForge requesting quote for indices: {indices_to_quote}")
        tpm_quote = await tpm_service.get_quote(indices_to_quote, nonce)
        tpm_quote_dict = tpm_quote.model_dump() if tpm_quote else None

        # 4. Create Witness Signature (Mocked crypto for the bridge layer)
        raw_to_sign = f"{nonce}|{covenant_id}|{epoch}|{counter}|{attestation_digest}"
        witness_signature = hashlib.sha256(f"{raw_to_sign}|{self.witness_id}".encode()).hexdigest()

        # 4.5 Workload identity (best-effort, local substrate)
        executable_path = None
        workload_hash = None
        try:
            executable_path = sys.executable
            if executable_path and os.path.exists(executable_path):
                with open(executable_path, "rb") as f:
                    workload_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception:
            executable_path = None
            workload_hash = None

        packet = SecretFirePacket(
            node_id=self.node_id,
            covenant_id=covenant_id,
            executable_path=executable_path,
            voice_id=voice_id,
            root_nonce_ref=root_nonce_ref,
            tier=tier,
            ainur_target=ainur_target,
            sweep_id=sweep_id,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=issued_at + 5.0, # 5s nominal expiry
            responded_at=responded_at,
            latency_ms=latency_ms,
            epoch=epoch,
            monotonic_counter=counter,
            attestation_digest=attestation_digest,
            order_digest=order_digest,
            runtime_digest=runtime_digest,
            entropy_digest=entropy_digest,
            cadence_profile=cadence_profile or {},
            witness_id=self.witness_id,
            witness_signature=witness_signature,
            workload_hash=workload_hash,
            replay_suspected=replay_suspected,
            freshness_valid=freshness_valid,
            tpm_quote=tpm_quote_dict
        )

        # Store for Handoff (Genesis Support)
        self.active_nonces["current_packet"] = packet
        
        logger.info(f"Forge: Packet forged for nonce {nonce[:8]}. Freshness: {freshness_valid}")
        return packet

# Global singleton
secret_fire_forge = SecretFireService()

def get_secret_fire_forge() -> SecretFireService:
    global secret_fire_forge
    return secret_fire_forge
