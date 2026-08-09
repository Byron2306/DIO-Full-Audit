from fastapi import APIRouter
from typing import Any
from datetime import datetime, timezone

try:
    from services.world_model import WorldModelService
except Exception:
    from backend.services.world_model import WorldModelService

router = APIRouter()

class MetatronService:
    def __init__(self, db: Any = None):
        self.db = db
        if db is not None:
            self.entities = db.world_entities
            self.edges = db.world_edges
            self.campaigns = db.campaigns

    def set_database(self, db: Any):
        """Set Mongo database instance for service."""
        self.__init__(db)

    async def tick(self) -> dict:
        """Perform periodic reasoning cycle (stub)."""
        if self.db is None:
            return {"error": "database not configured"}
        count = await self.entities.count_documents({})
        return {"entities": count}

    async def assess_world_state(self, snapshot: dict, event_type: str = "unknown", context: dict | None = None) -> dict:
        """Produce a structured strategic judgment from canonical world state.

        This keeps Metatron focused on *meaning/judgment* from state snapshots,
        not raw collection concerns.
        """
        context = context or {}
        if self.db is None:
            return {
                "status": "degraded",
                "reason": "database not configured",
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        wm = WorldModelService(self.db)
        hotspots = await wm.list_hotspots(limit=5)
        actions = await wm.list_actions(limit=8)
        timeline = await wm.list_timeline(limit=15)

        hotspot_docs = [h.model_dump() if hasattr(h, "model_dump") else h.dict() for h in hotspots]
        max_hotspot_risk = max([float((h.get("attributes") or {}).get("risk_score") or 0.0) for h in hotspot_docs] + [0.0])

        campaigns = snapshot.get("campaigns") or []
        trust_state = snapshot.get("trust_state") or {}
        recent_events = snapshot.get("recent_world_events") or []
        active_responses = snapshot.get("active_responses") or []
        sector_risk = snapshot.get("sector_risk") or {}
        attack_path_summary = snapshot.get("attack_path_summary") or {}
        cognition = snapshot.get("cognition") or {}
        fused_signal = cognition.get("fused_signal") or {}
        ai_reasoning = cognition.get("ai_reasoning") or {}

        sector_risk_values = [
            float((details or {}).get("avg_risk") or 0.0)
            for details in sector_risk.values()
            if isinstance(details, dict)
        ]
        max_sector_risk = max(sector_risk_values + [0.0])
        strategic_pressure = min(
            1.0,
            0.5 * max_hotspot_risk
            + 0.3 * max_sector_risk
            + 0.2 * min(1.0, len(active_responses) / 10.0),
        )
        cognitive_pressure = max(0.0, min(1.0, float(fused_signal.get("cognitive_pressure") or 0.0)))
        autonomous_confidence = max(0.0, min(1.0, float(fused_signal.get("autonomous_confidence") or 0.0)))
        strategic_pressure = min(1.0, strategic_pressure * 0.72 + cognitive_pressure * 0.28)

        degraded_trust_count = len(
            [v for v in trust_state.values() if str(v).lower().strip() in {"degraded", "quarantined", "compromised"}]
        )
        # Phase 1: Constitutional weighting (Tree of Truth)
        constitutional = snapshot.get("constitutional") or {}
        boot_truth = constitutional.get("boot_truth") or {}
        boot_status = str(boot_truth.get("status") or "unverified").lower()
        
        constitutional_risk = 0.0
        if boot_status == "unlawful":
             constitutional_risk = 1.0
             strategic_pressure = 1.0 # Force maximum pressure if the birth is unlawful
        elif boot_status == "compromised":
             constitutional_risk = 0.9
             strategic_pressure = max(strategic_pressure, 0.9)
        elif boot_status == "unverified":
             constitutional_risk = 0.5
             strategic_pressure = max(strategic_pressure, 0.5)

        confidence = max(0.25, min(0.98, 0.35 + (0.45 * strategic_pressure) - (0.2 * constitutional_risk)))

        top_sector_pairs = sorted(
            [
                (sector, float((details or {}).get("avg_risk") or 0.0))
                for sector, details in sector_risk.items()
            ],
            key=lambda item: item[1],
            reverse=True,
        )
        top_predicted_sectors = [sector for sector, _ in top_sector_pairs[:3]]
        cognitive_predicted_sectors = [str(s) for s in (fused_signal.get("predicted_next_sectors") or []) if s]
        if cognitive_predicted_sectors:
            top_predicted_sectors = list(dict.fromkeys(cognitive_predicted_sectors + top_predicted_sectors))
        if not top_predicted_sectors:
            top_predicted_sectors = ["identity", "endpoint", "network"] if strategic_pressure >= 0.5 else ["monitoring"]

        if strategic_pressure >= 0.85:
            policy_tier = "critical"
        elif strategic_pressure >= 0.65:
            policy_tier = "high"
        elif strategic_pressure >= 0.4:
            policy_tier = "medium"
        else:
            policy_tier = "low"
        
        # Force critical for unlawful boot
        if boot_status == "unlawful":
             policy_tier = "critical"

        cognitive_tier = str(fused_signal.get("recommended_policy_tier") or "").strip().lower()
        tier_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        if cognitive_tier in tier_rank and tier_rank[cognitive_tier] > tier_rank.get(policy_tier, 0):
            policy_tier = cognitive_tier

        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "context": context,
            "metatron_belief": {
                "strategic_pressure": round(strategic_pressure, 4),
                "degraded_trust_count": degraded_trust_count,
                "active_response_count": len(active_responses),
                "recent_event_count": len(recent_events),
                "cognitive_pressure": round(cognitive_pressure, 4),
                "autonomous_confidence": round(autonomous_confidence, 4),
                "constitutional_risk": round(constitutional_risk, 4),
            },
            "constitutional_status": {
                "boot_status": boot_status,
                "herald_id": constitutional.get("herald_id"),
                "manifold_id": constitutional.get("manifold_id"),
            },
            "environment_state": {
                "entity_count": snapshot.get("entity_count", 0),
                "top_risky_entities": hotspot_docs,
                "timeline_window": timeline,
                "attack_path_summary": attack_path_summary,
            },
            "cognition_state": {
                "fused_signal": fused_signal,
                "cce": cognition.get("cce") or {},
                "aatl": cognition.get("aatl") or {},
                "aatr": cognition.get("aatr") or {},
                "ai_reasoning_predictions": {
                    "predicted_next_step": ai_reasoning.get("predicted_next_step"),
                    "predicted_lateral_path": ai_reasoning.get("predicted_lateral_path") or [],
                },
            },
            "campaign_narratives": campaigns[:10],
            "predicted_next_sectors": top_predicted_sectors[:5],
            "recommended_response_posture": "containment_ready" if strategic_pressure >= 0.7 else "elevated_monitoring",
            "policy_tier_suggestion": policy_tier,
            # Backward compatibility for downstream consumers.
            "approval_tier_suggestion": policy_tier,
            "confidence": round(confidence, 4),
            "recommended_actions": actions,
        }

@router.get("/metatron/hello")
async def hello():
    return {"msg": "Metatron is alive"}

@router.get("/metatron/tick")
async def tick():
    # import here to avoid circular dependencies
    from backend.triune.metatron import MetatronService
    from backend.server import db
    service = MetatronService(db)
    result = await service.tick()
    return result
