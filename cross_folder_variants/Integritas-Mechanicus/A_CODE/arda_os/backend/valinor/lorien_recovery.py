import logging

from backend.services.arda_fabric import get_arda_fabric
from backend.services.constitutional_projection import project_choir_truth
from backend.services.secret_fire import get_secret_fire_forge

logger = logging.getLogger(__name__)


class LorienRecovery:
    """Controlled restoration path for entities with recoverable Mandos history."""

    def __init__(self, bridge, mandos, forge=None, choir_orchestrator=None):
        self.bridge = bridge
        self.mandos = mandos
        self.forge = forge or get_secret_fire_forge()
        self.choir = choir_orchestrator
        self.fabric = get_arda_fabric()

    async def attempt_recovery(self, entity_id: str, raw_context: dict) -> dict:
        record = self.mandos.get_record(entity_id)
        if self.mandos.is_fallen(entity_id):
            return {
                "recovered": False,
                "state": "fallen",
                "reason": "Entity is fallen and requires rebuild or Genesis seed.",
            }
        if not self.mandos.is_recoverable(entity_id):
            return {
                "recovered": False,
                "state": record.current_state,
                "reason": "Entity has unrecoverable constitutional wounds.",
            }

        fabric_state = self.fabric.get_subject_state(entity_id)
        if fabric_state == "fallen":
            return {
                "recovered": False,
                "state": "fallen",
                "reason": "Permanent identity blockade: subject failed workload attestation.",
            }

        fire_packet = self.forge.get_current_packet()
        if fire_packet:
            raw_context["secret_fire"] = fire_packet
        raw_context["subject_id"] = entity_id
        raw_context["node_id"] = entity_id

        if not self.choir:
            return {
                "recovered": False,
                "state": record.current_state,
                "reason": "No choir orchestrator available for canonical recovery projection.",
            }

        verdict = await self.choir.evaluate(raw_context)
        await project_choir_truth(verdict)

        from backend.services.constitutional_projection import canonical_runtime_state

        state = canonical_runtime_state(verdict)
        self.mandos.record_event(entity_id=entity_id, event_type="recovery", state=state, reason="Lorien recovery attempt")
        return {
            "recovered": state in ["strained", "harmonic"],
            "state": state,
            "reason": "Recovery complete" if state in ["strained", "harmonic"] else "Recovery incomplete",
        }
