import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

try:
    from services.kernel_signal_adapter import get_kernel_signal_adapter
    from services.order_engine import get_order_engine
except Exception:
    from backend.services.kernel_signal_adapter import get_kernel_signal_adapter
    from backend.services.order_engine import get_order_engine

logger = logging.getLogger(__name__)

class KernelOrderFeedService:
    """
    The Clock of Creation.
    Feeds kernel-level birth rhythms into the Triune's temporal engine.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self._last_birth_at: Optional[datetime] = None
        self._jitter_buffer: List[float] = []

    async def feed_birth_signal(self, pid: int, binary_path: str):
        """
        Record the 'manifestation rhythm' of a new process.
        """
        now = datetime.now(timezone.utc)
        
        if self._last_birth_at:
            delta = (now - self._last_birth_at).total_seconds()
            self._jitter_buffer.append(delta)
            if len(self._jitter_buffer) > 50: self._jitter_buffer.pop(0)

            # High jitter or birth-burstiness affects Order Resonance
            if delta < 0.1: # Suspiciously fast births (e.g. fork-bomb)
                logger.warning(f"PHASE V: Birth Burst detected for {binary_path}. Temporal jitter rising.")
                await self._inject_order_instability(delta)
                
        self._last_birth_at = now

    async def _inject_order_instability(self, delta: float):
        """
        Feed low-level temporal instability back into the Local Order Engine.
        """
        order_engine = get_order_engine(self.db)
        # This is the 'Force Fracture' bridge if birth jitter is extreme
        if delta < 0.01:
            logger.error("PHASE V: EXTREME TEMPORAL CRACK! Forcing Order Fracture.")
            # (In production, order_engine.record_fracture())
            pass

    def get_jitter_average(self) -> float:
        if not self._jitter_buffer: return 0.0
        return sum(self._jitter_buffer) / len(self._jitter_buffer)

# Global singleton
kernel_order_feed = KernelOrderFeedService()

def get_kernel_order_feed(db: Any = None) -> KernelOrderFeedService:
    global kernel_order_feed
    if db: kernel_order_feed.db = db
    return kernel_order_feed
