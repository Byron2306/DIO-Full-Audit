from dataclasses import dataclass, field
import logging
import time
from typing import Any, Dict, List, Optional

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
    """Bounded in-memory ledger for Valinor runtime decisions."""

    def __init__(self):
        self.records: Dict[str, MandosRecord] = {}

    def get_record(self, entity_id: str) -> MandosRecord:
        if entity_id not in self.records:
            self.records[entity_id] = MandosRecord(entity_id=entity_id)
        return self.records[entity_id]

    def record_event(self, entity_id: str, event_type: str, state: str, reason: str = "", epoch: Optional[str] = None) -> None:
        record = self.get_record(entity_id)
        record.current_state = state
        if state == "harmonic":
            record.last_lawful_epoch = epoch or record.last_lawful_epoch

        record.event_history.append(
            {
                "ts": time.time(),
                "event_type": event_type,
                "state": state,
                "reason": reason,
                "epoch": epoch,
            }
        )
        if len(record.event_history) > 20:
            record.event_history = record.event_history[-20:]

        if state in ["withheld", "muted", "fallen", "vetoed", "dissonant", "strained"] and event_type == "denial":
            record.denial_count += 1
        if reason and "Voice" in reason:
            record.voice_mismatch_count += 1
        if reason and ("Secret Fire" in reason or "Witnessing" in reason or "Lineage Denied" in reason):
            record.fire_breach_count += 1
        if (state in ["fallen", "vetoed", "muted"] and event_type == "denial") or (
            event_type == "earendil_sync" and state in ["fallen", "muted"]
        ):
            record.fallen_score += 1

        logger.debug(
            "Mandos: Recorded %s for %s. Fallen Score: %s, Denials: %s",
            event_type,
            entity_id,
            record.fallen_score,
            record.denial_count,
        )

    def is_fallen(self, entity_id: str) -> bool:
        record = self.get_record(entity_id)
        return record.fallen_score >= 3 or record.denial_count >= 10

    def is_recoverable(self, entity_id: str) -> bool:
        record = self.get_record(entity_id)
        return not self.is_fallen(entity_id) and record.fire_breach_count < 3 and record.voice_mismatch_count < 3
