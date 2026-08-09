import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

@dataclass
class ResonanceEvent:
    entity_id: str
    action_type: str
    target: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

# Grouping for Alqualonde to keep Taniquetil constructor clean
class AlqualondeHarbor:
    def __init__(self, harbor_master, shipwright, sea_governor):
        self.harbor_master = harbor_master
        self.shipwright = shipwright
        self.sea_governor = sea_governor

class TaniquetilCore:
    """
    The Throne of Manwë.
    All law converges here. This is the unified decision surface for Valinor.
    """

    def __init__(self, bridge, tirion, valmar, alqualonde: AlqualondeHarbor, mandos=None):
        self.bridge = bridge
        self.tirion = tirion
        self.valmar = valmar
        self.alqualonde = alqualonde
        self.mandos = mandos

    def evaluate(self, event: ResonanceEvent) -> Dict[str, Any]:
        # ✦ 0. Mandos Pre-check: Memory of Dooms
        if self.mandos and self.mandos.is_fallen(event.entity_id):
            return self._deny(event, "Mandos (Pre-check)", "Entity is fundamentally Fallen from historical wounds.")

        state = self.bridge.get_state(event.entity_id)

        target_display = f" on {event.target}" if event.target else ""
        logger.info(f"Taniquetil: Evaluating [{event.action_type.upper()}]{target_display} for {event.entity_id} [State: {state.constitutional_state.upper()}]")

        result = {
            "allowed": True,
            "modifiers": [],
            "reason": [],
            "memory_class": None # specific to spawn
        }

        # ✦ 1. Tirion — Form & Lineage
        if event.action_type == "spawn":
            child_id = event.metadata.get("child_id")
            node_id = event.metadata.get("node_id")
            
            allowed, reason = self.tirion.authorize_spawn(
                child_id=child_id,
                parent_id=event.entity_id,
                node_id=node_id
            )

            if not allowed:
                return self._deny(event, "Tirion", reason)

            memory_class = self.tirion.assign_memory_class(child_id)
            result["memory_class"] = memory_class
            result["reason"].append(reason)
            
            # Seed the new child into the LightBridge automatically
            parent_state = self.bridge.get_state(event.entity_id)
            node_state = self.bridge.get_state(node_id)
            inherited = self.bridge.inherit_state(parent_state, node_state)
            inherited.entity_id = child_id
            self.bridge.update_state(child_id, inherited)

        # ✦ 2. Valmar — Power & Privilege
        elif event.action_type == "syscall":
            decision = self.valmar.authorize_syscall(event.entity_id, event.target)

            if decision == "deny":
                return self._deny(event, "Valmar", f"Denied syscall: {event.target}")

            if decision != "allow":
                result["modifiers"].append(decision)
                
        elif event.action_type == "secret":
            decision = self.valmar.authorize_secret_access(event.entity_id, event.target)
            if not decision:
                return self._deny(event, "Valmar", f"Denied secret access: {event.target}")

        # ✦ 3. Alqualondë — Flow & Movement
        elif event.action_type in ["socket", "ipc"]:
            decision = self.alqualonde.harbor_master.authorize_channel(event.entity_id, event.action_type)

            if decision.action == "deny":
                return self._deny(event, "Alqualonde", decision.reason)

            result["modifiers"].append(f"QoS: {decision.queue_priority}")
            result["modifiers"].append(f"Bandwidth: {decision.bandwidth_class}")

        elif event.action_type == "write":
            decision = self.alqualonde.shipwright.authorize_write(event.entity_id, event.target)

            if decision.action == "deny":
                return self._deny(event, "Alqualonde", decision.reason)

            result["modifiers"].append(f"Write Mode: {decision.action}")

        # ✦ 4. Global Flow Shaping (Always applies to measure continuous presence)
        flow = self.alqualonde.sea_governor.shape_flow(event.entity_id)
        if flow.action == "deny":
            # Flow shaping can retroactively kill an action 
            # if the entity's resonance dropped mid-flight
            return self._deny(event, "Alqualonde (EareFlow)", "Motion itself denied by the sea.")
            
        result["modifiers"].append(f"Sea State: {flow.bandwidth_class}")

        # Final unified success
        logger.info(f"Taniquetil: APPROVED. Modifiers: {result['modifiers']}")
        
        # Add to Mandos Ledger
        if self.mandos:
             self.mandos.record_event(
                 entity_id=event.entity_id,
                 event_type=event.action_type,
                 state=state.constitutional_state,
                 reason="Approved via Resonance",
                 epoch=event.metadata.get("epoch")
             )
             
        return result

    def _deny(self, event: ResonanceEvent, source: str, reason: str) -> Dict[str, Any]:
        logger.error(f"Taniquetil: DENIED by [{source}] → {reason}")
        
        if self.mandos:
             # Identify the current state of the entity to record correct context in Mandos
             current_state = self.bridge.get_state(event.entity_id).constitutional_state
             self.mandos.record_event(
                  entity_id=event.entity_id, 
                  event_type="denial", 
                  state=current_state, 
                  reason=reason
             )
             
        return {
            "allowed": False,
            "modifiers": [],
            "reason": [reason],
            "memory_class": None
        }
