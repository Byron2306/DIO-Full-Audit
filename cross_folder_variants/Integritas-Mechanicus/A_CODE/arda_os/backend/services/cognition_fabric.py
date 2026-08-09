from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _avg(values: List[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _tier_from_score(score: float) -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


class CognitionFabricService:
    """
    Unified cognition snapshot builder used by Triune orchestration.

    This service aggregates and normalizes signals from:
      - AATL (autonomous-agent behavior assessments)
      - AATR (registry matching against observed behavior)
      - CCE (CLI session cognition summaries)
      - ML predictor (recent and optional snapshot predictions)
      - AI reasoning engine (snapshot analysis + predictions)
    """

    def __init__(self, db: Any):
        self.db = db

    async def _recent_docs(
        self,
        collection_name: str,
        *,
        sort_field: str = "timestamp",
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        if self.db is None or not hasattr(self.db, collection_name):
            return []
        coll = getattr(self.db, collection_name)
        try:
            cursor = coll.find({}, {"_id": 0}).sort(sort_field, -1).limit(limit)
            return await cursor.to_list(limit)
        except Exception:
            # Best-effort fallback for lightweight fakes
            try:
                cursor = coll.find({}, {"_id": 0})
                rows = await cursor.to_list(limit)
                return rows[:limit]
            except Exception:
                return []

    @staticmethod
    def _entity_ref_filter(rows: List[Dict[str, Any]], entity_ids: List[str]) -> List[Dict[str, Any]]:
        if not entity_ids:
            return rows
        ids = {str(eid) for eid in entity_ids}
        filtered = []
        for row in rows:
            host_id = str(row.get("host_id") or "")
            entity_id = str(row.get("entity_id") or "")
            if host_id in ids or entity_id in ids:
                filtered.append(row)
                continue
            refs = row.get("entity_refs") or []
            if any(str(ref) in ids for ref in refs):
                filtered.append(row)
        return filtered or rows

    def _build_reasoning_context_payload(
        self,
        *,
        world_snapshot: Dict[str, Any],
        aatl_rows: List[Dict[str, Any]],
        cce_rows: List[Dict[str, Any]],
        ml_rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        evidence: List[Dict[str, Any]] = []
        for ev in (world_snapshot.get("recent_world_events") or [])[:20]:
            evidence.append(
                {
                    "type": ev.get("type") or "world_event",
                    "source": "world_events",
                    "severity": (ev.get("payload") or {}).get("severity"),
                }
            )
        for a in aatl_rows[:10]:
            evidence.append(
                {
                    "type": f"aatl_{a.get('threat_level', 'unknown')}",
                    "source": "aatl",
                    "threat_score": a.get("threat_score", 0),
                    "lifecycle_stage": a.get("lifecycle_stage"),
                }
            )
        for c in cce_rows[:10]:
            for intent in (c.get("dominant_intents") or []):
                evidence.append({"type": f"intent_{intent}", "source": "cce"})
        for m in ml_rows[:10]:
            evidence.append(
                {
                    "type": f"ml_{m.get('predicted_category', 'unknown')}",
                    "source": "ml",
                    "threat_score": m.get("threat_score", 0),
                }
            )

        return {
            "entities": world_snapshot.get("entities") or [],
            "relationships": world_snapshot.get("attack_path_graph") or {"nodes": [], "edges": []},
            "evidence_set": evidence,
            "trust_state": world_snapshot.get("trust_state") or {},
            "timeline_window": world_snapshot.get("recent_world_events") or [],
            "window_seconds": 3600,
        }

    async def _collect_ai_reasoning(
        self,
        reasoning_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            try:
                from services.ai_reasoning import ai_reasoning, ReasoningContext
            except Exception:
                from backend.services.ai_reasoning import ai_reasoning, ReasoningContext
        except Exception:
            return {}

        try:
            ctx = ReasoningContext(
                entities=reasoning_context.get("entities") or [],
                relationships=reasoning_context.get("relationships") or {},
                evidence_set=reasoning_context.get("evidence_set") or [],
                trust_state=reasoning_context.get("trust_state") or {},
                timeline_window=reasoning_context.get("timeline_window") or [],
                window_seconds=int(reasoning_context.get("window_seconds") or 3600),
            )
            analysis = ai_reasoning.analyze_snapshot(ctx) or {}
            predictions = analysis.get("predictions") or {}
            suggested = [item.get("action") for item in (analysis.get("suggested_actions") or []) if item.get("action")]
            uncertainty = analysis.get("uncertainty_zones") or {}
            return {
                "analysis": analysis,
                "predicted_next_step": predictions.get("next_step"),
                "predicted_lateral_path": predictions.get("lateral_path") or [],
                "suggested_actions": suggested,
                "mean_uncertainty": _avg([_safe_float(v) for v in uncertainty.values()]) if isinstance(uncertainty, dict) else 0.0,
            }
        except Exception:
            return {}

    async def _collect_ml_snapshot_prediction(self, reasoning_context: Dict[str, Any]) -> Dict[str, Any]:
        enabled = os.environ.get("TRIUNE_RUN_ML_SNAPSHOT_INFERENCE", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not enabled:
            return {}
        try:
            from backend.ml_threat_prediction import ml_predictor
        except Exception:
            try:
                from ml_threat_prediction import ml_predictor
            except Exception:
                return {}

        try:
            timeout_s = _safe_float(os.environ.get("TRIUNE_ML_SNAPSHOT_TIMEOUT_S", "2.5"), default=2.5)
            # Avoid recursive world-event emissions and write amplification while
            # Triune is already processing an event.
            original_db = getattr(ml_predictor, "_db", None)
            try:
                ml_predictor._db = None
                result = await asyncio.wait_for(
                    ml_predictor.predict_from_snapshot(reasoning_context),
                    timeout=max(0.5, timeout_s),
                )
            finally:
                ml_predictor._db = original_db
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _map_action_to_candidate(action: str, preferred_entities: List[str]) -> Optional[str]:
        normalized = str(action or "").strip().lower()
        if not normalized:
            return None
        if ":" in normalized:
            return normalized
        if normalized in {"isolate_hosts", "isolate_host", "quarantine_hosts", "quarantine_host"}:
            return f"isolate:{preferred_entities[0]}" if preferred_entities else "isolate:critical_host"
        if normalized in {"block_outbound", "cut_network_egress", "tighten_egress_controls"}:
            return "block_egress:network"
        if normalized in {"investigate", "investigate_further"}:
            return f"investigate:{preferred_entities[0]}" if preferred_entities else "investigate:global"
        if normalized in {"rotate_credentials", "step_up_authentication"}:
            return "force_password_reset:identity"
        if normalized in {"full_honeypot_engagement", "deploy_decoys", "deceive"}:
            return "deploy_deception:network"
        return normalized

    async def build_cognition_snapshot(
        self,
        *,
        world_snapshot: Dict[str, Any],
        event_type: str,
        entity_ids: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        entity_ids = entity_ids or []
        context = context or {}

        aatl_rows = self._entity_ref_filter(
            await self._recent_docs("aatl_assessments", sort_field="timestamp", limit=25),
            entity_ids,
        )
        cce_rows = self._entity_ref_filter(
            await self._recent_docs("cli_session_summaries", sort_field="timestamp", limit=25),
            entity_ids,
        )
        ml_rows = self._entity_ref_filter(
            await self._recent_docs("ml_predictions", sort_field="timestamp", limit=25),
            entity_ids,
        )

        autonomous_rows = [row for row in aatl_rows if str(row.get("actor_type")) == "autonomous_agent"]
        high_aatl_rows = [row for row in aatl_rows if _safe_float(row.get("threat_score")) >= 70.0]
        max_aatl_score = max([_safe_float(row.get("threat_score")) for row in aatl_rows] + [0.0]) / 100.0
        max_machine_likelihood = max([_safe_float(row.get("machine_likelihood")) for row in cce_rows] + [0.0])
        max_ml_score = max([_safe_float(row.get("threat_score")) for row in ml_rows] + [0.0]) / 100.0

        dominant_intents: Dict[str, int] = {}
        for row in cce_rows:
            for intent in (row.get("dominant_intents") or []):
                dominant_intents[intent] = dominant_intents.get(intent, 0) + 1
        sorted_intents = [intent for intent, _ in sorted(dominant_intents.items(), key=lambda item: item[1], reverse=True)]

        behavior_fingerprint = {
            "timing_variance": _safe_float((context.get("behavior") or {}).get("timing_variance"), default=1000.0),
            "command_velocity": _safe_float((context.get("behavior") or {}).get("command_velocity"), default=0.0),
            "tool_switch_latency": _safe_float((context.get("behavior") or {}).get("tool_switch_latency"), default=5000.0),
        }
        if cce_rows:
            behavior_fingerprint["command_velocity"] = max(
                behavior_fingerprint["command_velocity"],
                _avg([_safe_float(row.get("command_count")) / 30.0 for row in cce_rows[:10]]),
            )
            behavior_fingerprint["tool_switch_latency"] = min(
                behavior_fingerprint["tool_switch_latency"],
                _avg([_safe_float(row.get("tool_switch_latency_ms"), default=5000.0) for row in cce_rows[:10]]),
            )
            behavior_fingerprint["timing_variance"] = max(1.0, behavior_fingerprint["tool_switch_latency"] / 10.0)

        aatr_summary: Dict[str, Any] = {}
        aatr_matches: List[Dict[str, Any]] = []
        try:
            try:
                from services.aatr import get_aatr
            except Exception:
                from backend.services.aatr import get_aatr
            aatr = get_aatr()
            if aatr is not None:
                aatr_summary = aatr.get_summary() or {}
                if hasattr(aatr, "match_behavior"):
                    aatr_matches = (aatr.match_behavior(behavior_fingerprint) or [])[:5]
        except Exception:
            aatr_summary = {}
            aatr_matches = []

        reasoning_context = self._build_reasoning_context_payload(
            world_snapshot=world_snapshot,
            aatl_rows=aatl_rows,
            cce_rows=cce_rows,
            ml_rows=ml_rows,
        )
        ai_reasoning = await self._collect_ai_reasoning(reasoning_context)
        ml_snapshot = await self._collect_ml_snapshot_prediction(reasoning_context)

        preferred_entities = [
            ent.get("id")
            for ent in (world_snapshot.get("entities") or [])
            if isinstance(ent, dict) and ent.get("id")
        ]
        if not preferred_entities:
            preferred_entities = [str(entity_id) for entity_id in entity_ids if entity_id]

        fused_actions: List[str] = []
        for row in high_aatl_rows[:5]:
            for action in (row.get("recommended_actions") or []):
                mapped = self._map_action_to_candidate(action, preferred_entities)
                if mapped:
                    fused_actions.append(mapped)
        for action in (ai_reasoning.get("suggested_actions") or []):
            mapped = self._map_action_to_candidate(action, preferred_entities)
            if mapped:
                fused_actions.append(mapped)
        for action in (ml_snapshot.get("predicted_next_moves") or []):
            mapped = self._map_action_to_candidate(action, preferred_entities)
            if mapped:
                fused_actions.append(mapped)

        dedup_actions: List[str] = []
        for action in fused_actions:
            if action not in dedup_actions:
                dedup_actions.append(action)

        autonomous_ratio = (len(autonomous_rows) / len(aatl_rows)) if aatl_rows else 0.0
        uncertainty_mean = _safe_float(ai_reasoning.get("mean_uncertainty"), default=0.0)
        cognitive_pressure = min(
            1.0,
            (0.35 * max_aatl_score)
            + (0.25 * max_machine_likelihood)
            + (0.25 * max_ml_score)
            + (0.15 * uncertainty_mean),
        )
        autonomous_confidence = min(1.0, (0.6 * max_machine_likelihood) + (0.4 * autonomous_ratio))
        recommended_policy_tier = _tier_from_score(max(cognitive_pressure, autonomous_confidence))

        predicted_next_sectors: List[str] = []
        for intent in sorted_intents[:3]:
            if intent in {"credential_access", "privilege_escalation"}:
                predicted_next_sectors.append("identity")
            elif intent in {"lateral_movement", "recon"}:
                predicted_next_sectors.append("network")
            elif intent in {"persistence", "execution", "defense_evasion"}:
                predicted_next_sectors.append("endpoint")
            elif intent in {"exfil_prep", "data_staging"}:
                predicted_next_sectors.append("data")
        if not predicted_next_sectors:
            predicted_next_sectors = ["identity", "endpoint"] if cognitive_pressure >= 0.6 else ["monitoring"]

        supporting_signals = []
        if max_aatl_score >= 0.7:
            supporting_signals.append("aatl_high_threat")
        if max_machine_likelihood >= 0.7:
            supporting_signals.append("cce_machine_likelihood")
        if max_ml_score >= 0.7:
            supporting_signals.append("ml_high_risk_predictions")
        if aatr_matches:
            supporting_signals.append("aatr_behavior_match")
        if uncertainty_mean >= 0.5:
            supporting_signals.append("ai_uncertainty")

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "entity_ids": entity_ids,
            "aatl": {
                "total_sessions": len(aatl_rows),
                "autonomous_sessions": len(autonomous_rows),
                "high_threat_sessions": [
                    {
                        "host_id": row.get("host_id"),
                        "session_id": row.get("session_id"),
                        "threat_score": row.get("threat_score"),
                        "threat_level": row.get("threat_level"),
                        "recommended_strategy": row.get("recommended_strategy"),
                    }
                    for row in high_aatl_rows[:10]
                ],
                "max_threat_score": round(max_aatl_score * 100.0, 2),
            },
            "aatr": {
                "summary": aatr_summary,
                "behavior_matches": aatr_matches,
            },
            "cce": {
                "recent_session_count": len(cce_rows),
                "max_machine_likelihood": round(max_machine_likelihood, 4),
                "avg_machine_likelihood": round(_avg([_safe_float(row.get("machine_likelihood")) for row in cce_rows]), 4),
                "dominant_intents": sorted_intents[:6],
            },
            "ml": {
                "recent_prediction_count": len(ml_rows),
                "high_risk_prediction_count": len([row for row in ml_rows if _safe_float(row.get("threat_score")) >= 70.0]),
                "max_threat_score": round(max_ml_score * 100.0, 2),
                "snapshot_prediction": ml_snapshot,
            },
            "ai_reasoning": ai_reasoning,
            "fused_signal": {
                "cognitive_pressure": round(cognitive_pressure, 4),
                "autonomous_confidence": round(autonomous_confidence, 4),
                "recommended_policy_tier": recommended_policy_tier,
                "recommended_actions": dedup_actions[:20],
                "predicted_next_sectors": list(dict.fromkeys(predicted_next_sectors))[:5],
                "supporting_signals": supporting_signals,
            },
        }
