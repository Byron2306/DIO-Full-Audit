import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class MandosRecord:
    entity_id: str
    current_state: str = "harmonic"
    last_lawful_epoch: Optional[str] = None
    fallen_score: int = 0
    denial_count: int = 0
    voice_mismatch_count: int = 0
    fire_breach_count: int = 0
    event_history: List[Dict[str, Any]] = field(default_factory=list)

class MandosLedger:
    """
    Mandos — the House of Dooms.
    Remembers constitutional wounds, repeated dissonance, and fallen lineage.
    """

    def __init__(self):
        self.records: Dict[str, MandosRecord] = {}

    def get_record(self, entity_id: str) -> MandosRecord:
        if entity_id not in self.records:
            self.records[entity_id] = MandosRecord(entity_id=entity_id)
        return self.records[entity_id]

    def record_event(self, entity_id: str, event_type: str, state: str, reason: str = "", epoch: Optional[str] = None):
        rec = self.get_record(entity_id)
        rec.current_state = state
        
        if state == "harmonic":
            rec.last_lawful_epoch = epoch or rec.last_lawful_epoch

        rec.event_history.append({
            "ts": time.time(),
            "event_type": event_type,
            "state": state,
            "reason": reason,
            "epoch": epoch
        })

        # Keep history bounded
        if len(rec.event_history) > 20:
             rec.event_history = rec.event_history[-20:]

        if state in ["withheld", "muted", "fallen", "vetoed", "dissonant", "strained"]:
            # Only strictly tally denials
            if event_type == "denial":
                 rec.denial_count += 1

        if reason and "Voice" in reason:
            rec.voice_mismatch_count += 1

        if reason and ("Secret Fire" in reason or "Witnessing" in reason or "Lineage Denied" in reason):
            rec.fire_breach_count += 1

        if (state in ["fallen", "vetoed", "muted"] and event_type == "denial") or (event_type == "earendil_sync" and state in ["fallen", "muted"]):
            rec.fallen_score += 1
            
        logger.debug(f"Mandos: Recorded {event_type} for {entity_id}. Fallen Score: {rec.fallen_score}, Denials: {rec.denial_count}")

    def is_fallen(self, entity_id: str) -> bool:
        rec = self.get_record(entity_id)
        return rec.fallen_score >= 3 or rec.denial_count >= 10

    def is_recoverable(self, entity_id: str) -> bool:
        rec = self.get_record(entity_id)
        return not self.is_fallen(entity_id) and rec.fire_breach_count < 3 and rec.voice_mismatch_count < 3
