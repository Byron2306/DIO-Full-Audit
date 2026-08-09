import logging
from typing import Any, Dict

from backend.valinor.alqualonde_teleri import CirdanShipwright, EareFlowGovernor, OlweHarborMaster
from backend.valinor.light_bridge import LightBridge
from backend.valinor.mandos_ledger import MandosLedger
from backend.valinor.taniquetil_core import AlqualondeHarbor, ResonanceEvent, TaniquetilCore
from backend.valinor.tirion_noldor import TirionProcessGovernor
from backend.valinor.valmar_vanyar import GaladrielLightArbiter

logger = logging.getLogger(__name__)


class ValinorRuntime:
    """Userland Valinor bridge used by Gates of Night, Earendil, and gauntlets."""

    def __init__(self, bridge: LightBridge, taniquetil: TaniquetilCore):
        self.bridge = bridge
        self.taniquetil = taniquetil

    def spawn_process(self, child_id: str, parent_id: str, node_id: str) -> Dict[str, Any]:
        event = ResonanceEvent(
            entity_id=parent_id,
            action_type="spawn",
            metadata={"child_id": child_id, "node_id": node_id},
        )
        decision = self.taniquetil.evaluate(event)
        if not decision["allowed"]:
            raise PermissionError(f"Spawn Denied: {decision['reason']}")
        return {
            "status": "Lawful Spawn",
            "memory_class": decision["memory_class"],
            "inherited_state": self.bridge.get_state(child_id).constitutional_state,
        }

    def syscall(self, entity_id: str, syscall_name: str) -> str:
        event = ResonanceEvent(entity_id=entity_id, action_type="syscall", target=syscall_name)
        decision = self.taniquetil.evaluate(event)
        if not decision["allowed"]:
            raise PermissionError(f"Syscall Denied by Taniquetil Convergence: {decision['reason']}")
        if "restrict" in decision["modifiers"]:
            return f"{syscall_name}: restricted"
        if "attenuate" in decision["modifiers"]:
            return f"{syscall_name}: slowed"
        return f"{syscall_name}: allowed"

    def access_secret(self, entity_id: str, secret_name: str) -> bool:
        event = ResonanceEvent(entity_id=entity_id, action_type="secret", target=secret_name)
        decision = self.taniquetil.evaluate(event)
        if not decision["allowed"]:
            raise PermissionError(f"Secret Access Denied: {decision['reason']}")
        return True

    def open_socket(self, entity_id: str) -> Any:
        event = ResonanceEvent(entity_id=entity_id, action_type="socket")
        decision = self.taniquetil.evaluate(event)
        if not decision["allowed"]:
            raise PermissionError("Socket Denied: Entity lacks resonance to transmit.")
        return decision

    def send_ipc(self, entity_id: str) -> Any:
        event = ResonanceEvent(entity_id=entity_id, action_type="ipc")
        decision = self.taniquetil.evaluate(event)
        if not decision["allowed"]:
            raise PermissionError("IPC Denied: Flow constraint enacted.")
        return decision

    def write_stream(self, entity_id: str, target: str) -> Any:
        event = ResonanceEvent(entity_id=entity_id, action_type="write", target=target)
        decision = self.taniquetil.evaluate(event)
        if not decision["allowed"]:
            raise PermissionError("Write Denied: Malicious code cannot enact persistence.")
        return decision

    def apply_flow_shape(self, entity_id: str) -> Any:
        return self.taniquetil.alqualonde.sea_governor.shape_flow(entity_id)


_valinor_instance = None


def get_valinor_runtime() -> ValinorRuntime:
    global _valinor_instance
    if _valinor_instance is None:
        bridge = LightBridge()
        tirion = TirionProcessGovernor(bridge)
        valmar = GaladrielLightArbiter(bridge)
        harbor = OlweHarborMaster(bridge)
        wright = CirdanShipwright(bridge)
        flow = EareFlowGovernor(bridge)
        mandos = MandosLedger()
        al_harbor = AlqualondeHarbor(harbor, wright, flow)
        taniquetil = TaniquetilCore(bridge, tirion, valmar, al_harbor, mandos)
        _valinor_instance = ValinorRuntime(bridge, taniquetil)
    return _valinor_instance
