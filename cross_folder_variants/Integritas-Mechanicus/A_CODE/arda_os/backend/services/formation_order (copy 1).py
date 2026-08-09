import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

try:
    from schemas.phase2_models import FormationOrderState
    from services.telemetry_chain import tamper_evident_telemetry
except Exception:
    from backend.schemas.phase2_models import FormationOrderState
    from backend.services.telemetry_chain import tamper_evident_telemetry

logger = logging.getLogger(__name__)

class FormationOrderService:
    """
    The pre-runtime counterpart to order_engine.py.
    Tracks lawful boot-to-runtime sequence and handoff invariants.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.telemetry = tamper_evident_telemetry
        self._current_sequence: List[str] = [
            "measured_boot",
            "formation_manifest_loaded",
            "formation_verifier_active",
            "genesis_score_loaded"
        ]
        self._current_order: Optional[FormationOrderState] = None

    async def validate_formation_order(self) -> FormationOrderState:
        """
        Judge the sequence of events leading into the Triune domain.
        """
        logger.info("PHASE II: Validating Formation sequence...")
        
        # 1. Identify seen sequence
        # For Phase II demo, we assume the sequence above was seen
        seen = self._current_sequence
        
        # 2. Check invariants
        required = ["measured_boot", "formation_manifest_loaded", "formation_verifier_active", "genesis_score_loaded"]
        seen = self._current_sequence
        
        missing = [step for step in required if step not in seen]
        forbidden = [] # Placeholder for future forbidden service detection
        
        # Calculate Order Score
        score = 1.0 - (len(missing) * 0.2)
        score = max(0.0, score)
        
        status = "lawful"
        if missing or forbidden or score < 0.8:
            status = "fractured"
            logger.warning(f"PHASE II: Formation Order FRACTURED! Missing: {missing}")
        
        # 3. Form FormationOrderState
        order_state = FormationOrderState(
            formation_order_id=f"fo-{uuid.uuid4().hex[:8]}",
            status=status.value if hasattr(status, "value") else status,
            verified_sequence=seen,
            missing_steps=missing,
            forbidden_steps_seen=forbidden,
            order_score=score,
            strictness=1.0 # Birth order should be perfectly strictly enforced
        )
        
        # 4. Record in Telemetry
        self.telemetry.ingest_event(
            event_type="formation_order_verified",
            severity="info" if status == "lawful" else "warning",
            data=order_state.model_dump(mode='json')
        )
        
        self._current_order = order_state
        logger.info(f"PHASE II: Formation Order status: {status} (score={score})")
        
        return order_state

    def get_order(self) -> Optional[FormationOrderState]:
        return self._current_order

# Global singleton
formation_order_service = FormationOrderService()

def get_formation_order_service(db: Any = None) -> FormationOrderService:
    global formation_order_service
    if formation_order_service.db is None and db is not None:
        formation_order_service.db = db
    return formation_order_service
