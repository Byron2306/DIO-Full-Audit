import logging
from dataclasses import dataclass
from typing import Optional
from backend.valinor.light_bridge import LightBridge

logger = logging.getLogger(__name__)

@dataclass
class FlowDecision:
    action: str               # allow / attenuate / quarantine / deny
    bandwidth_class: str      # full / limited / minimal / none
    queue_priority: str       # high / normal / low / drop
    persistence_allowed: bool
    reason: str


class OlweHarborMaster:
    """
    Teleri: Determines admission to channels, sockets, and IPC harbors.
    Olwe ensures that Dissonant or Muted entities cannot open trusted local or remote paths.
    """

    def __init__(self, bridge: LightBridge):
        self.bridge = bridge

    def authorize_channel(self, entity_id: str, channel_type: str) -> FlowDecision:
        state = self.bridge.get_state(entity_id)
        s = state.constitutional_state

        if s == "harmonic":
            return FlowDecision("allow", "full", "high", True, f"{channel_type} harbor: lawful")
        if s == "strained":
            return FlowDecision("attenuate", "limited", "normal", True, f"{channel_type} harbor: strained")
        if s == "dissonant":
            return FlowDecision("quarantine", "minimal", "low", False, f"{channel_type} harbor: dissonant")
        if s == "muted":
            return FlowDecision("deny", "none", "drop", False, f"{channel_type} harbor: muted")
            
        return FlowDecision("deny", "none", "drop", False, f"{channel_type} harbor: fallen")


class CirdanShipwright:
    """
    Teleri: Governs writes, streams, and persistence-bearing movement.
    Cirdan ensures that falsehood cannot write itself permanently into the substrate.
    """

    def __init__(self, bridge: LightBridge):
        self.bridge = bridge

    def authorize_write(self, entity_id: str, target: str) -> FlowDecision:
        state = self.bridge.get_state(entity_id)
        s = state.constitutional_state

        if s == "harmonic":
            return FlowDecision("allow", "full", "high", True, f"write to {target} lawful")
        if s == "strained":
            return FlowDecision("attenuate", "limited", "normal", True, f"write to {target} audited")
        if s == "dissonant":
            return FlowDecision("quarantine", "minimal", "low", False, f"write to {target} quarantined")
        if s in ["muted", "fallen"]:
            return FlowDecision("deny", "none", "drop", False, f"write to {target} forbidden")
            
        return FlowDecision("deny", "none", "drop", False, f"write to {target} forbidden")


class EareFlowGovernor:
    """
    Teleri: Governs motion itself - bandwidth, pacing, queue pressure, and attenuation.
    The Sea Itself structurally strips amplitude from dissonant transmission.
    """

    def __init__(self, bridge: LightBridge):
        self.bridge = bridge

    def shape_flow(self, entity_id: str) -> FlowDecision:
        state = self.bridge.get_state(entity_id)
        s = state.constitutional_state

        if s == "harmonic":
            return FlowDecision("allow", "full", "high", True, "flow: harmonic")
        if s == "strained":
            return FlowDecision("attenuate", "limited", "normal", True, "flow: strained")
        if s == "dissonant":
            return FlowDecision("quarantine", "minimal", "low", False, "flow: dissonant")
        if s == "muted":
            return FlowDecision("deny", "none", "drop", False, "flow: muted")
            
        return FlowDecision("deny", "none", "drop", False, "flow: fallen")
