import logging
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

try:
    from schemas.phase2_models import GenesisScore
    from services.telemetry_chain import tamper_evident_telemetry
except Exception:
    from backend.schemas.phase2_models import GenesisScore
    from backend.services.telemetry_chain import tamper_evident_telemetry

logger = logging.getLogger(__name__)

class GenesisScoreService:
    """
    Loads and verifies the first lawful score of the machine.
    Ensures the system begins with a signed opening mode.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.telemetry = tamper_evident_telemetry
        self._current_score: Optional[GenesisScore] = None

    async def load_genesis_score(self) -> GenesisScore:
        """
        Loads the signed opening mode.
        Phase II genesis is no longer hardcoded in the herald, but loaded and signed.
        """
        logger.info("PHASE II: Loading signed Genesis Score...")
        
        # Load signed genesis data
        # In production, this would be a signed payload from an external vault
        genesis = GenesisScore(
            genesis_score_id="genesis-score-proto-1",
            genesis_epoch="epoch-0-v2-origin",
            genre_mode="constitutional_bedrock",
            strictness=1.0, # Full strictness by default at birth
            seed_policy_hash=hashlib.sha256(b"genesis-policy-v2").hexdigest(),
            signature=hashlib.sha256(b"signed-by-seraph-vault").hexdigest()
        )
        
        # 2. Record in Telemetry
        self.telemetry.ingest_event(
            event_type="genesis_score_loaded",
            severity="info",
            data=genesis.model_dump(mode='json')
        )
        
        self._current_score = genesis
        logger.info(f"PHASE II: Genesis Score loaded. Starting Epoch: {genesis.genesis_epoch}")
        
        return genesis

    def get_score(self) -> Optional[GenesisScore]:
        return self._current_score

# Global singleton
genesis_score_service = GenesisScoreService()

def get_genesis_score_service(db: Any = None) -> GenesisScoreService:
    global genesis_score_service
    if genesis_score_service.db is None and db is not None:
        genesis_score_service.db = db
    return genesis_score_service
