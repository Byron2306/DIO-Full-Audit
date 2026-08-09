import logging
import time
from typing import Dict, Set

try:
    from schemas.phase4_models import VerifiedHeartbeat
    from services.telemetry_chain import tamper_evident_telemetry
except Exception:
    from backend.schemas.phase4_models import VerifiedHeartbeat
    from backend.services.telemetry_chain import tamper_evident_telemetry

logger = logging.getLogger(__name__)

class ReplayGuardService:
    """
    The Sentinel of the Chorus.
    Prevents stale, replayed, or duplicate heartbeats from infecting the resonance.
    Essential for true distributed trust.
    """
    
    def __init__(self, history_size: int = 1000, max_age_seconds: int = 60):
        self._history_size = history_size
        self._max_age_seconds = max_age_seconds
        
        # Track last sequence number per node
        self._last_sequence: Dict[str, int] = {}
        
        # Short-term cache of processed proof IDs (envelope IDs)
        self._processed_ids: Set[str] = set()
        self._processed_timestamps: Dict[str, float] = {}

    def check_and_record(self, heartbeat: VerifiedHeartbeat) -> bool:
        """
        Verify that this heartbeat is not a replay.
        Returns False if heartbeat is rejected.
        """
        node_id = heartbeat.node_id
        seq = heartbeat.sequence_number
        proof_id = heartbeat.proof_id
        
        # 1. Deduplication (O(1) lookup)
        if proof_id in self._processed_ids:
            logger.warning(f"PHASE IV: DUPLICATE REJECTION! Heartbeat {proof_id} from {node_id} already processed.")
            return False
            
        # 2. Monotonicity Counter (Sequential integrity)
        last_seq = self._last_sequence.get(node_id, -1)
        if seq <= last_seq:
            logger.warning(f"PHASE IV: REPLAY REJECTION! Seq {seq} <= {last_seq} for node {node_id}. Stale proof.")
            return False
            
        # 3. Clean up old IDs to prevent memory leaks
        self._cleanup_old_ids()
        
        # 4. Record Success
        self._last_sequence[node_id] = seq
        self._processed_ids.add(proof_id)
        self._processed_timestamps[proof_id] = time.time()
        
        logger.debug(f"PHASE IV: Replay Guard recorded seq {seq} for {node_id}")
        return True

    def _cleanup_old_ids(self):
        """Evict proof IDs older than max_age_seconds."""
        now = time.time()
        expired = [pid for pid, ts in self._processed_timestamps.items() if (now - ts) > self._max_age_seconds]
        
        for pid in expired:
            self._processed_ids.discard(pid)
            del self._processed_timestamps[pid]
            
        # Limit history size if needed
        if len(self._processed_ids) > self._history_size:
            # Simple FIFO eviction if overrun
            sorted_pids = sorted(self._processed_timestamps.keys(), key=lambda x: self._processed_timestamps[x])
            to_remove = sorted_pids[:(len(self._processed_ids) - self._history_size)]
            for pid in to_remove:
                self._processed_ids.discard(pid)
                del self._processed_timestamps[pid]

# Global singleton
replay_guard = ReplayGuardService()

def get_replay_guard() -> ReplayGuardService:
    global replay_guard
    return replay_guard
