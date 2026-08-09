import logging
from typing import Dict, Any

from backend.valinor.light_bridge import LightBridge
from backend.valinor.tirion_noldor import TirionProcessGovernor
from backend.valinor.valmar_vanyar import GaladrielLightArbiter
from backend.valinor.alqualonde_teleri import OlweHarborMaster, CirdanShipwright, EareFlowGovernor
from backend.valinor.taniquetil_core import TaniquetilCore, ResonanceEvent, AlqualondeHarbor

logger = logging.getLogger(__name__)

class ValinorRuntime:
    """
    Phase 1: Calaquendi Kernel Adapter (Userland Bridge)
    Intercepts processes, syscalls, and protects secrets in runtime.
    This acts "Side by Side" with Ilmarin (Ainur), allowing Resonance
    to instantly affect executable reality.
    """

    def __init__(self, bridge: LightBridge, taniquetil: TaniquetilCore):
        self.bridge = bridge
        self.taniquetil = taniquetil

    def spawn_process(self, child_id: str, parent_id: str, node_id: str) -> Dict[str, Any]:
        """
        Kernel hook simulating sys_clone, sys_fork, or CreateProcess.
        Lineage enforcement via Tirion, converged in Taniquetil.
        """
        logger.info(f"Valinor Runtime: Intercepted spawn request {child_id} from parent {parent_id}")
        
        event = ResonanceEvent(
            entity_id=parent_id,
            action_type="spawn",
            metadata={"child_id": child_id, "node_id": node_id}
        )
        decision = self.taniquetil.evaluate(event)

        if not decision["allowed"]:
            raise Exception(f"Spawn Denied: {decision['reason']}")

        logger.info(f"Valinor Hook: Spawn Proceeding for {child_id}. Memory Class: {decision['memory_class']}")

        return {
            "status": "Lawful Spawn",
            "memory_class": decision["memory_class"],
            "inherited_state": self.bridge.get_state(child_id).constitutional_state
        }

    def syscall(self, entity_id: str, syscall_name: str) -> str:
        """
        Kernel hook simulating sys_enter (e.g. via eBPF or LD_PRELOAD in Phase 1).
        Execution gating via Valmar through Taniquetil.
        """
        event = ResonanceEvent(
            entity_id=entity_id,
            action_type="syscall",
            target=syscall_name
        )
        decision = self.taniquetil.evaluate(event)

        if not decision["allowed"]:
            raise PermissionError(f"Syscall Denied by Taniquetil Convergence: {decision['reason']}")

        modifiers = decision["modifiers"]
        if "restrict" in modifiers:
            return f"{syscall_name}: restricted"

        if "attenuate" in modifiers:
            return f"{syscall_name}: slowed"

        return f"{syscall_name}: allowed"
        
    def access_secret(self, entity_id: str, secret_name: str) -> bool:
        """Guards Flame-bound secrets or TPM access (Valmar)."""
        event = ResonanceEvent(entity_id=entity_id, action_type="secret", target=secret_name)
        decision = self.taniquetil.evaluate(event)
        if not decision["allowed"]:
             raise PermissionError(f"Secret Access Denied: {decision['reason']}")
        return True

    # ========================================================
    # ALQUALONDE (TELERI) - The Law of Flow
    # ========================================================

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
        """Determines bandwidth and queue dropping pressure for an active stream."""
        # This is already evaluated implicitly in Taniquetil, but as a direct call:
        event = ResonanceEvent(entity_id=entity_id, action_type="flow")
        # For a raw flow check, we just check the sea governor or let Taniquetil default to flow shaping check.
        # But we can just direct to Alqualonde for explicit raw flow shape fetch:
        return self.taniquetil.alqualonde.sea_governor.shape_flow(entity_id)

# True Singleton setup
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
        
        from backend.valinor.mandos_ledger import MandosLedger
        mandos = MandosLedger()
        
        al_harbor = AlqualondeHarbor(harbor, wright, flow)
        taniquetil = TaniquetilCore(bridge, tirion, valmar, al_harbor, mandos)
        
        _valinor_instance = ValinorRuntime(bridge, taniquetil)
        
    return _valinor_instance
