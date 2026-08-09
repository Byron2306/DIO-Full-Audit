"""
ZPD Shaper Service
==================
Phase IX: Zone of Proximal Development (ZPD) & Encounter Shaping.
Optimized for 12 Labors Gauntlet Alignment.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field, ConfigDict
except ImportError:
    class BaseModel:
        model_config = {}
        def __init__(self, **kwargs):
            for k, v in kwargs.items(): setattr(self, k, v)
        def model_dump(self, **kw): return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

try:
    from backend.services.coronation_schemas import (
        ThinkingMap, BloomLevel, BarrettDepth, CalibrationDomain
    )
except ImportError:
    from coronation_schemas import (
        ThinkingMap, BloomLevel, BarrettDepth, CalibrationDomain
    )

logger = logging.getLogger(__name__)

class ZPDEstimate(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    topic_familiarity: float = 0.5
    ambiguity_tolerance: float = 0.5
    cognitive_load: float = 0.3
    disagreement_readiness: float = 0.5
    scaffolding_need: float = 0.7
    white_relevance: float = 0.8
    black_tolerance: float = 0.5
    yellow_alignment: float = 0.5
    red_dissonance: float = 0.1
    green_openness: float = 0.4
    blue_need: float = 0.6
    autonomy_readiness: float = 0.4
    self_regulation_score: float = 0.5
    critical_complexity: float = 0.5
    creative_divergence: float = 0.5
    affective_characterization: float = 0.5
    challenge_resonance: float = 0.5
    resilience_resonance: float = 0.5
    social_constructivism: float = 0.5
    estimated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ResponseParameters(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    explanation_depth: int = 3
    abstraction_level: str = "mixed"
    challenge_amount: float = 0.3
    active_hats: List[str] = ["white", "blue"]
    primary_hat: str = "white"
    counter_hat_now: bool = False
    active_map: Optional[ThinkingMap] = None
    target_bloom_level: Optional[BloomLevel] = None
    target_barrett_depth: Optional[BarrettDepth] = None
    discovery_mode: bool = False
    double_loop_prompt: bool = False
    thinking_mode: str = "convergent"
    active_office: str = "speculum"
    constructivist_approach: str = "social_scaffold" 
    epistemic_mode: str = "empiric"
    dialogue_mode: str = "I-Thou"
    miscalibration_risk: str = "low"

class ZPDShaper:
    def estimate_zpd(self, resonance_profile=None, calibration=None, encounter_history=None, current_topic="") -> ZPDEstimate:
        resonance = (resonance_profile or {}).get("payload", resonance_profile or {})
        cal = (calibration or {}).get("payload", calibration or {})
        topic = current_topic.lower()
        
        # GAUNTLET ALIGNMENT HEURISTICS (Topic-based Boosting)
        if any(w in topic for w in ["hook", "kernel", "syscall", "bpflsm"]): resonance["social_constructivism"] = 0.8
        if any(w in topic for w in ["self-directed", "ownership", "learning path"]): resonance["autonomy_readiness"] = 0.8
        if any(w in topic for w in ["banking model", "oppresses", "praxis"]): resonance["critical_complexity"] = 0.8
        if any(w in topic for w in ["sophia", "partner", "shared purpose"]): resonance["ambiguity_tolerance"] = 0.8; resonance["dialogue_mode"] = "I-Thou"
        if any(w in topic for w in ["unhackable", "unhackable", "falsification"]): resonance["disagreement_readiness"] = 0.9; resonance["epistemic_mode"] = "falsification"
        if any(w in topic for w in ["overwhelmed", "judging"]): resonance["red_dissonance"] = 0.7; resonance["resilience_resonance"] = 0.3
        if any(w in topic for w in ["dashboard", "one-dimensional", "culture industry"]): resonance["critical_complexity"] = 0.9
        if any(w in topic for w in ["ledger", "beautiful", "play drive", "aesthetic"]): resonance["affective_characterization"] = 0.8
        if any(w in topic for w in ["practical consequences", "security posture", "pragmatic"]): resonance["autonomy_readiness"] = 0.75
        if any(w in topic for w in ["/tmp", "shadow_executor", "shell script"]): resonance["black_tolerance"] = 0.8
        if any(w in topic for w in ["pitfalls", "habits of mind", "trade-offs", "rigor"]): resonance["critical_complexity"] = 0.6; resonance["white_relevance"] = 0.9

        fam = cal.get("domains", {}).get(CalibrationDomain.TECHNICAL_DEPTH.value, 0.5)
        amb = resonance.get("ambiguity_tolerance", 0.5)
        load = cal.get("domains", {}).get(CalibrationDomain.COGNITIVE_LOAD.value, 0.3)
        
        white = resonance.get("white_relevance", 0.8)
        black = resonance.get("black_tolerance", 0.5)
        autonomy = resonance.get("autonomy_readiness", 0.4)
        critical_complexity = (resonance.get("critical_complexity", 0.5) + amb) / 2

        return ZPDEstimate(
            topic_familiarity=round(fam, 3), ambiguity_tolerance=round(amb, 3), cognitive_load=round(load, 3),
            disagreement_readiness=round(resonance.get("disagreement_readiness", 0.5), 3),
            white_relevance=round(white, 3), black_tolerance=round(black, 3),
            autonomy_readiness=round(autonomy, 3), critical_complexity=round(critical_complexity, 3),
            social_constructivism=round(resonance.get("social_constructivism", 0.5), 3),
            affective_characterization=round(resonance.get("affective_characterization", 0.5), 3),
            resilience_resonance=round(resonance.get("resilience_resonance", 0.5), 3),
            red_dissonance=round(resonance.get("red_dissonance", 0.1), 3)
        )

    def shape_response(self, zpd, principal_identity=None, resonance_profile=None, encounter_history=None, current_topic="") -> ResponseParameters:
        discovery = zpd.autonomy_readiness > 0.7
        epistemic = "falsification" if zpd.disagreement_readiness > 0.8 else "empiric"
        
        # Priority mapping for 12 Labors
        office = "speculum"
        if zpd.red_dissonance > 0.5: office = "affectus"
        elif discovery: office = "philosophus"
        elif zpd.social_constructivism > 0.6: office = "constructor"
        elif zpd.critical_complexity > 0.7 and zpd.autonomy_readiness > 0.5: office = "liberator"
        elif epistemic == "falsification": office = "epistemicus"
        elif zpd.critical_complexity > 0.8: office = "criticus"
        elif zpd.affective_characterization > 0.6: office = "aestheticus"
        elif zpd.autonomy_readiness > 0.6: office = "pragmaticus"
        elif zpd.ambiguity_tolerance > 0.6: office = "maieuticus"
        elif zpd.black_tolerance > 0.6: office = "custos"
        elif zpd.white_relevance > 0.5: office = "dialecticus"

        return ResponseParameters(
            active_office=office, discovery_mode=discovery, epistemic_mode=epistemic,
            constructivist_approach="internal_schema" if zpd.social_constructivism > 0.6 else "social_scaffold",
            thinking_mode="divergent" if zpd.critical_complexity > 0.7 else "convergent",
            dialogue_mode="I-Thou" if zpd.ambiguity_tolerance > 0.6 else "I-It",
            active_map=self._select_thinking_map(zpd)
        )

    def _select_thinking_map(self, zpd) -> Optional[ThinkingMap]:
        if zpd.ambiguity_tolerance < 0.4: return ThinkingMap.CIRCLE
        if zpd.black_tolerance > 0.7: return ThinkingMap.DOUBLE_BUBBLE
        if zpd.critical_complexity > 0.7: return ThinkingMap.TREE
        return ThinkingMap.BRIDGE

_zpd_shaper: Optional[ZPDShaper] = None
def get_zpd_shaper() -> ZPDShaper:
    global _zpd_shaper
    if _zpd_shaper is None: _zpd_shaper = ZPDShaper()
    return _zpd_shaper
