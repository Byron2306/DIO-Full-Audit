import os
import logging
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

try:
    from schemas.phase2_models import OrderState, StabilityClass
    from services.harmonic_engine import get_harmonic_engine
    from services.telemetry_chain import tamper_evident_telemetry
    from services.world_model import WorldModelService
    from services.formation_order import get_formation_order_service
except Exception:
    from backend.schemas.phase2_models import OrderState, StabilityClass
    from backend.services.harmonic_engine import get_harmonic_engine
    from backend.services.telemetry_chain import tamper_evident_telemetry
    from backend.services.world_model import WorldModelService
    from backend.services.formation_order import get_formation_order_service

logger = logging.getLogger(__name__)

class OrderEngine:
    """
    The Tree of Order.
    Governs the temporal flow and cadence of legal life manifestation.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.world_model = WorldModelService(db)
        self.telemetry = tamper_evident_telemetry
        self.harmonic = get_harmonic_engine(db)
        self.formation_order = get_formation_order_service(db)
        self._current_order: Optional[OrderState] = None

    async def update_order_state(self) -> OrderState:
        """
        Ingest harmonic state and produce a rigid OrderState for Phase II.
        Inherits stability and constraints from Formation Order.
        """
        logger.info("PHASE II: Updating constitutional Order State...")
        
        # 1. Get raw harmonic pulse
        pulse = {"discord_score": 0.1, "confidence": 0.9} 
        try:
             pulse = self.harmonic.get_domain_pulse_state("global") or pulse
        except Exception:
             pass
             
        # 2. Ingest Formation Order context
        f_order = self.formation_order.get_order() or await self.formation_order.validate_formation_order()
        
        # 3. Map Dissonance to Stability Class
        stability = self._map_to_stability(pulse.get("discord_score", 0.0))
        
        # Adjust stability if formation was fractured
        if f_order.status == "fractured":
            stability = StabilityClass.FRACTURED
            
        # 4. Derive Entry Windows
        windows = [100, 500] if stability == StabilityClass.CRYSTALLINE else [50, 1000]
        
        # 5. Form OrderState
        state = OrderState(
            order_id=f"order-{uuid.uuid4().hex[:8]}",
            stability_class=stability,
            temporal_strictness=max(0.8, f_order.strictness) if stability == StabilityClass.CRYSTALLINE else 0.4,
            entry_window_ms=windows,
            active_sequence_constraints={"max_simultaneous_manifest_actions": 5},
            harmonic_summary=pulse,
            herald_id_ref="herald-root",
            epoch_id_ref=f_order.formation_order_id # Linked to formation
        )
        
        # 6. Push to World Model
        self.world_model.set_governance_placeholders(
            order_state_ref=state.order_id
        )
        
        # 7. Record in Telemetry
        self.telemetry.ingest_event(
            event_type="order_state_crystallized",
            severity="info" if stability == StabilityClass.CRYSTALLINE else "warning",
            data=state.model_dump(mode='json')
        )
        
        self._current_order = state
        logger.info(f"PHASE II: Order stability inherited: {stability}")
        
        return state

    def _map_to_stability(self, discord_score: float) -> StabilityClass:
        d = float(discord_score)
        if d < 0.1: return StabilityClass.CRYSTALLINE
        if d < 0.3: return StabilityClass.STABLE
        if d < 0.6: return StabilityClass.STRAINED
        if d < 0.8: return StabilityClass.DISSONANT
        return StabilityClass.FRACTURED

    def get_current_order(self) -> Optional[OrderState]:
        return self._current_order

# Global singleton
order_engine = OrderEngine()

def get_order_engine(db: Any = None) -> OrderEngine:
    global order_engine
    if db: order_engine.db = db
    return order_engine
