import logging
import hashlib
import os
import asyncio
from typing import Optional, Dict, Any, Tuple
from backend.services.preboot_state_sealer import get_preboot_state_sealer
from backend.services.tulkas_executor import TulkasExecutor
from backend.services.world_model import WorldModelService
from backend.services.verity_engine import get_verity_engine
from backend.arda.ainur.verdicts import ChoirVerdict

logger = logging.getLogger(__name__)

class LawfulHandoffService:
    """
    Gate 1: The Lawful Handoff. 
    Enforces that the mounted root filesystem matches the pre-boot covenant. 
    Closing the gap between pre-boot measurement and runtime continuation.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.sealer = get_preboot_state_sealer()
        self.world_model = WorldModelService(db)
        self.tulkas = TulkasExecutor(self.world_model)

    async def verify_handoff(self) -> Tuple[bool, str]:
        """
        Verifies that the current runtime root matches the sealed pre-boot truth.
        """
        logger.info("PHASE VII: Commencing Lawful Handoff verification...")
        
        # 1. Unseal Preboot Covenant
        covenant = await self.sealer.unseal_covenant()
        if not covenant:
            logger.critical("CONSTITUTIONAL FAILURE: No sealed preboot covenant found. System is UNLAWFUL.")
            return False, "missing_preboot_covenant"

        # 2. Calculate Runtime Rootfs Identity
        # In a real OS, this would be a dm-verity Merkle root check. 
        # Here we simulate by hashing the critical manifests.
        runtime_hash = await self._calculate_runtime_rootfs_hash()
        
        logger.info(f"Handoff: Expected Hash (Sealed): {covenant.rootfs_hash[:16]}")
        logger.info(f"Handoff: Actual Hash (Runtime): {runtime_hash[:16]}")

        # 3. Decision Logic based on Reaction Mode
        is_lawful = (runtime_hash == covenant.rootfs_hash)
        
        if not is_lawful:
            reason = f"Rootfs Dissonance: Runtime identity {runtime_hash[:8]} does NOT match sealed covenant {covenant.rootfs_hash[:8]}."
            logger.error(f"PHASE VII: {reason}")
            
            # Engage Tulkas based on the Reaction Mode
            await self._handle_violation(covenant.reaction_mode, reason)
            return False, reason
        
        self.covenant = covenant
        logger.info("PHASE VII: Lawful Handoff SUCCESS. The Kingdom of Arda is coherent.")
        return True, "lawful_handoff"

    async def _calculate_runtime_rootfs_hash(self) -> str:
        """Computes the SHA256 of the Merkle Root for the entire substrate."""
        verity = get_verity_engine()
        root_hash, _ = await verity.build_merkle_tree()
        return root_hash

    async def _handle_violation(self, mode: str, reason: str):
        """Reacts to a handoff failure based on the sovereign mode."""
        logger.warning(f"Handoff: Reacting to violation in '{mode}' mode.")
        
        state_map = {
             "development": "strained",
             "guarded": "dissonant",
             "sovereign": "muted",
             "genesis": "fallen"
        }
        
        assigned_state = state_map.get(mode, "dissonant")
        
        logger.warning(f"Handoff: Applying Dissonance State [{assigned_state.upper()}] via Tulkas.")
        
        mock_verdict = ChoirVerdict(
            overall_state=assigned_state,
            reasons=[reason],
            heralding_allowed=False,
            confidence=0.0,
            ainur=[]
        )
        await self.tulkas.execute_enforcement(mock_verdict, "local-substrate")

# Global singleton
lawful_handoff = None
def get_lawful_handoff(db: Any = None):
    global lawful_handoff
    if lawful_handoff is None:
        lawful_handoff = LawfulHandoffService(db)
    return lawful_handoff
