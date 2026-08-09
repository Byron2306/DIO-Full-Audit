import logging
from dataclasses import dataclass

from backend.valinor.light_bridge import LightBridge

logger = logging.getLogger(__name__)


@dataclass
class FlowDecision:
    action: str
    bandwidth_class: str
    queue_priority: str
    persistence_allowed: bool
    reason: str


class OlweHarborMaster:
    """Admission control for sockets and IPC harbors."""

    def __init__(self, bridge: LightBridge):
        self.bridge = bridge

    def authorize_channel(self, entity_id: str, channel_type: str) -> FlowDecision:
        state = self.bridge.get_state(entity_id)
        constitutional_state = state.constitutional_state
        if constitutional_state == "harmonic":
            return FlowDecision("allow", "full", "high", True, f"{channel_type} harbor: lawful")
        if constitutional_state == "strained":
            return FlowDecision("attenuate", "limited", "normal", True, f"{channel_type} harbor: strained")
        if constitutional_state == "dissonant":
            return FlowDecision("quarantine", "minimal", "low", False, f"{channel_type} harbor: dissonant")
        if constitutional_state == "muted":
            return FlowDecision("deny", "none", "drop", False, f"{channel_type} harbor: muted")
        return FlowDecision("deny", "none", "drop", False, f"{channel_type} harbor: fallen")


class CirdanShipwright:
    """Write and stream persistence governance."""

    def __init__(self, bridge: LightBridge):
        self.bridge = bridge

    def authorize_write(self, entity_id: str, target: str) -> FlowDecision:
        state = self.bridge.get_state(entity_id)
        constitutional_state = state.constitutional_state
        if constitutional_state == "harmonic":
            return FlowDecision("allow", "full", "high", True, f"write to {target} lawful")
        if constitutional_state == "strained":
            return FlowDecision("attenuate", "limited", "normal", True, f"write to {target} audited")
        if constitutional_state == "dissonant":
            return FlowDecision("quarantine", "minimal", "low", False, f"write to {target} quarantined")
        return FlowDecision("deny", "none", "drop", False, f"write to {target} forbidden")


class EareFlowGovernor:
    """Continuous bandwidth, pacing, queue pressure, and attenuation governor."""

    def __init__(self, bridge: LightBridge):
        self.bridge = bridge

    def shape_flow(self, entity_id: str) -> FlowDecision:
        state = self.bridge.get_state(entity_id)
        constitutional_state = state.constitutional_state
        if constitutional_state == "harmonic":
            return FlowDecision("allow", "full", "high", True, "flow: harmonic")
        if constitutional_state == "strained":
            return FlowDecision("attenuate", "limited", "normal", True, "flow: strained")
        if constitutional_state == "dissonant":
            return FlowDecision("quarantine", "minimal", "low", False, "flow: dissonant")
        if constitutional_state == "muted":
            return FlowDecision("deny", "none", "drop", False, "flow: muted")
        return FlowDecision("deny", "none", "drop", False, "flow: fallen")
