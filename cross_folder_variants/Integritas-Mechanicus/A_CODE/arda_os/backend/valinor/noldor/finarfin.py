import logging
from typing import Any, Dict, Optional

try:
    from backend.arda.ainur.dissonance import DissonantStateModel
except Exception:
    from backend.services.ainur.dissonance import DissonantStateModel  # type: ignore
from backend.valinor.taniquetil_core import ResonanceEvent

logger = logging.getLogger(__name__)


class HouseOfFinarfin:
    """Wisdom layer for Taniquetil decision routing."""

    def __init__(self, bridge=None, taniquetil=None):
        self.bridge = bridge
        self.taniquetil = taniquetil

    def evaluate_resonance(self, event: ResonanceEvent) -> Dict[str, Any]:
        if not self.taniquetil:
            return {"allowed": True, "modifiers": [], "reason": ["Taniquetil Silent"]}
        return self.taniquetil.evaluate(event)

    def reconcile_identity(self, node_id: str) -> Optional[DissonantStateModel]:
        if not self.bridge:
            return None
        return self.bridge.get_state(node_id)

    def herald_verdict(self, verdict: Any) -> None:
        logger.info("Finarfin: verdict=%s", verdict)


finarfin = HouseOfFinarfin()


def get_house_finarfin() -> HouseOfFinarfin:
    return finarfin


ResonanceGovernor = HouseOfFinarfin
