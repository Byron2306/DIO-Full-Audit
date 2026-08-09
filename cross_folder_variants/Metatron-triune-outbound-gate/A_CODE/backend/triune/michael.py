try:
    from fastapi import APIRouter
    router = APIRouter()
except Exception:
    # FastAPI may not be installed in lightweight test environments; provide
    # a minimal dummy router so module-level decorators don't fail during import.
    class _DummyRouter:
        def get(self, *args, **kwargs):
            def _decorator(f):
                return f
            return _decorator

    router = _DummyRouter()
from typing import Any, List, Dict
import math
from datetime import datetime, timezone


class MichaelService:
    """Lightweight analysis/ranking service.

    This service provides simple, explainable heuristics to rank candidate
    remediation actions or hypotheses produced by the world model (Metatron).
    It is intentionally simple so it can run without heavyweight ML deps.
    """

    def __init__(self, db: Any = None):
        self.db = db
        # lazy import WorldModelService to avoid importing heavyweight
        # dependencies (pydantic, fastapi) during lightweight unit tests
        self.wm = None
        if db is not None:
            try:
                from services.world_model import WorldModelService
                self.wm = WorldModelService(db)
            except Exception:
                self.wm = None

    def set_database(self, db: Any):
        self.__init__(db)

    async def rank_responses(self, candidates: List[str]) -> List[Dict[str, float]]:
        """Score and rank candidate actions.

        Returns a list of dicts: [{"candidate": str, "score": float}, ...]
        Sorted by `score` descending.
        """
        out = []
        # best-effort: consult world-model for entity risk if present
        for cand in (candidates or []):
            # components
            base = getattr(self, "weights", {}).get("base", 0.35)
            keyword_comp = 0.0
            risk_comp = 0.0
            recency_comp = 0.0
            degree_comp = 0.0

            lc = cand.lower()
            # keyword heuristics with diminishing returns
            if "isolate" in lc or "quarantine" in lc:
                keyword_comp += 0.9
            if "kill" in lc or "terminate" in lc:
                keyword_comp += 1.0
            if "force_password_reset" in lc or "password_reset" in lc:
                keyword_comp += 0.6
            if "require_2fa" in lc or "enable_2fa" in lc:
                keyword_comp += 0.4
            if "monitor" in lc or "investigate" in lc:
                keyword_comp += 0.2

            # entity-aware augmentations
            ent_id = None
            if ":" in cand:
                parts = cand.split(":", 1)
                ent_id = parts[1]
                try:
                    if self.wm is not None:
                        # entity doc
                        doc = await self.wm.entities.find_one({"id": ent_id}, {"_id": 0})
                        if doc:
                            attrs = doc.get("attributes", {}) or {}
                            # risk_score expected in 0..1
                            risk = float(attrs.get("risk_score") or 0.0)
                            risk_comp = max(0.0, min(1.0, risk))

                            # recency: prefer recent sightings; last_seen may be iso string
                            last_seen = attrs.get("last_seen")
                            if last_seen:
                                try:
                                    if isinstance(last_seen, str):
                                        dt = datetime.fromisoformat(last_seen)
                                    elif isinstance(last_seen, (int, float)):
                                        dt = datetime.fromtimestamp(float(last_seen), tz=timezone.utc)
                                    else:
                                        dt = None
                                    if dt is not None:
                                        # treat naive datetimes as UTC
                                        if dt.tzinfo is None:
                                            dt = dt.replace(tzinfo=timezone.utc)
                                        delta = datetime.now(timezone.utc) - dt
                                        days = max(0.0, delta.total_seconds() / 86400.0)
                                        # exponential decay: recent => near 1, old => near 0
                                        recency_comp = math.exp(-days / 7.0)
                                except Exception:
                                    recency_comp = 0.0

                            # degree: how many edges connect to this entity (normalize later)
                            try:
                                # prefer edges collection if present
                                if hasattr(self.wm, "edges"):
                                    # countDocuments may be async in some implementations
                                    cnt = await self.wm.edges.count_documents({"$or": [{"source": ent_id}, {"target": ent_id}]})
                                    degree_comp = float(cnt)
                            except Exception:
                                degree_comp = 0.0
                except Exception:
                    # ignore DB lookup errors
                    risk_comp = recency_comp = degree_comp = 0.0

            # normalize degree using logistic mapping
            if degree_comp:
                degree_comp = 1.0 / (1.0 + math.exp(-0.3 * (degree_comp - 3)))

            # combine components using configured weights
            w = getattr(self, "weights", {"base": 0.35, "keyword": 0.3, "risk": 0.2, "recency": 0.1, "degree": 0.05})
            raw_score = (
                w.get("base", 0.0) * 1.0
                + w.get("keyword", 0.0) * (keyword_comp / (1.0 + keyword_comp))
                + w.get("risk", 0.0) * risk_comp
                + w.get("recency", 0.0) * recency_comp
                + w.get("degree", 0.0) * degree_comp
            )

            # final normalization to 0..1
            score = max(0.0, min(1.0, raw_score))

            out.append({
                "candidate": cand,
                "score": round(score, 4),
                "components": {
                    "base": round(base, 4),
                    "keyword": round(keyword_comp, 4),
                    "risk": round(risk_comp, 4),
                    "recency": round(recency_comp, 4),
                    "degree": round(degree_comp, 4),
                },
            })

        # optional AI reasoning: use the centralized ai_reasoning explain API if present
        try:
            from services.ai_reasoning import ai_reasoning, ReasoningContext
            if ai_reasoning is not None and hasattr(ai_reasoning, "explain_candidates"):
                # build a lightweight context from available world-model (best-effort)
                ctx = None
                try:
                    # if wm available, construct snapshot entities list
                    if getattr(self, "wm", None) is not None:
                        # fetch a small set of entities for context
                        cursor = self.wm.entities.find({}, {"_id": 0}).limit(10)
                        entities = [e async for e in cursor]
                        # attempt to fetch a small attack-path snapshot
                        rels = await self.wm.compute_attack_path()
                        # timeline: empty for lightweight context
                        ctx = ReasoningContext(entities=entities, relationships=rels, evidence_set=[], trust_state={}, timeline_window=[])
                except Exception:
                    ctx = None

                try:
                    explanations = ai_reasoning.explain_candidates([r["candidate"] for r in out], context=ctx)
                    if isinstance(explanations, dict):
                        for r in out:
                            cand = r.get("candidate")
                            info = explanations.get(cand) or {}
                            if info:
                                comps = r.setdefault("components", {})
                                comps["ai"] = info
                except Exception:
                    pass
        except Exception:
            # best-effort: do not affect scoring if ai_reasoning is unavailable
            pass

        # stable sort by score desc, candidate asc for determinism
        out.sort(key=lambda x: (-x["score"], x["candidate"]))

        # persist triune analysis to DB if available (best-effort, non-fatal)
        try:
            import uuid
            if getattr(self, "db", None) is not None and hasattr(self.db, "triune_analysis"):
                triune_doc = {
                    "id": f"triune-{uuid.uuid4().hex[:8]}",
                    "created": datetime.now(timezone.utc).isoformat(),
                    "entities": [],
                    "candidates": [r["candidate"] for r in out],
                    "ranked": out,
                }
                try:
                    await self.db.triune_analysis.insert_one(triune_doc)
                except Exception:
                    pass
        except Exception:
            pass

        return out

    @staticmethod
    def _candidate_from_cognitive_action(action: str, preferred_entities: List[str]) -> str:
        normalized = str(action or "").strip().lower()
        if not normalized:
            return ""
        if ":" in normalized:
            return normalized
        if normalized in {"isolate_hosts", "isolate_host", "quarantine_hosts"}:
            return f"isolate:{preferred_entities[0]}" if preferred_entities else "isolate:critical_host"
        if normalized in {"block_outbound", "cut_network_egress", "tighten_egress_controls"}:
            return "block_egress:network"
        if normalized in {"rotate_credentials", "step_up_authentication"}:
            return "force_password_reset:identity"
        if normalized in {"deploy_decoys", "full_honeypot_engagement", "deceive"}:
            return "deploy_deception:network"
        if normalized in {"investigate", "investigate_further"}:
            return f"investigate:{preferred_entities[0]}" if preferred_entities else "investigate:global"
        return normalized

    def _augment_candidates_with_cognition(
        self,
        base_candidates: List[str],
        world_snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        cognition = world_snapshot.get("cognition") or {}
        fused_signal = cognition.get("fused_signal") or {}
        aatl = cognition.get("aatl") or {}
        ai_reasoning = cognition.get("ai_reasoning") or {}

        preferred_entities = [
            ent.get("id")
            for ent in (world_snapshot.get("entities") or [])
            if isinstance(ent, dict) and ent.get("id")
        ]
        augmented = list(base_candidates or [])
        source_map: Dict[str, str] = {str(c): "base" for c in augmented}

        fused_actions = [str(a) for a in (fused_signal.get("recommended_actions") or []) if a]
        reasoning_actions = [str(a) for a in (ai_reasoning.get("suggested_actions") or []) if a]
        strategies = [
            str(row.get("recommended_strategy"))
            for row in (aatl.get("high_threat_sessions") or [])
            if row.get("recommended_strategy")
        ]

        for action in fused_actions + reasoning_actions:
            candidate = self._candidate_from_cognitive_action(action, preferred_entities)
            if candidate and candidate not in source_map:
                augmented.append(candidate)
                source_map[candidate] = "cognition"

        for strategy in strategies:
            if strategy == "deceive":
                candidate = "deploy_deception:network"
            elif strategy == "poison":
                candidate = "seed_decoy_credential_path:identity"
            elif strategy == "contain":
                candidate = f"isolate:{preferred_entities[0]}" if preferred_entities else "isolate:critical_host"
            elif strategy == "slow":
                candidate = "throttle_remote_execution:network"
            else:
                candidate = ""
            if candidate and candidate not in source_map:
                augmented.append(candidate)
                source_map[candidate] = "aatl_strategy"

        return {
            "candidates": augmented,
            "source_map": source_map,
            "fused_actions": fused_actions,
            "aatl_strategies": strategies,
        }

    async def plan_actions(
        self,
        candidates: List[str],
        world_snapshot: Dict[str, Any] | None = None,
        policy_tier: str = "standard",
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Produce ranked action candidates plus orchestration metadata.

        Michael remains action-planning focused and does not invent world truth.
        """
        world_snapshot = world_snapshot or {}
        context = context or {}
        cognitive_augmented = self._augment_candidates_with_cognition(candidates or [], world_snapshot)
        ranked = await self.rank_responses(cognitive_augmented["candidates"])
        top = ranked[0] if ranked else None

        # basic blast radius estimate from hotspot count + attack-path size
        hotspot_count = len(world_snapshot.get("hotspots") or [])
        path_nodes = len((world_snapshot.get("attack_path_graph") or {}).get("nodes") or [])
        blast_radius = max(hotspot_count, min(path_nodes, 25))

        # Phase 1: Constitutional Order weighting
        constitutional = world_snapshot.get("constitutional") or {}
        order_info = constitutional.get("order") or {} # Injected by orchestrator
        stability = str(order_info.get("stability_class") or "stable").lower()
        strictness = float(order_info.get("temporal_strictness") or 0.5)

        top_candidate = (top or {}).get("candidate", "")
        if any(k in top_candidate for k in ["monitor", "investigate", "collect_forensics"]):
            reversibility = "high"
            reversibility_score = 0.85
        elif any(k in top_candidate for k in ["block", "quarantine", "isolate"]):
            reversibility = "medium"
            reversibility_score = 0.55
        else:
            reversibility = "low"
            reversibility_score = 0.35
            
        # Constitutional override: If stability is fractured, force high reversibility
        if stability in {"dissonant", "fractured"}:
             reversibility = "high_forced"
             reversibility_score = max(reversibility_score, 0.9)
             logger.warning(f"PHASE I: Order stability is {stability}. Forcing high reversibility for planned actions.")

        cognition = world_snapshot.get("cognition") or {}
        fused_signal = cognition.get("fused_signal") or {}
        cognitive_pressure = float(fused_signal.get("cognitive_pressure") or 0.0)
        if cognitive_pressure >= 0.75 and reversibility_score < 0.5:
            # Favor faster action under strong converged cognitive signal.
            reversibility_score = max(reversibility_score, 0.5)

        ranked_action_sets = {
            "immediate": ranked[:3],
            "stabilization": ranked[3:6],
            "deferred": ranked[6:10],
        }

        endpoint_preparation_recommendations = [
            "pre-stage isolation scripts for high-risk endpoints",
            "validate EDR policy sync for predicted target sectors",
            "cache forensic collection packages on responders",
        ]
        if fused_signal.get("autonomous_confidence", 0) >= 0.7:
            endpoint_preparation_recommendations.append("enforce command throttling profiles for machine-paced sessions")
        if cognition.get("cce", {}).get("dominant_intents"):
            endpoint_preparation_recommendations.append(
                f"deploy hunts for dominant intents: {', '.join(cognition.get('cce', {}).get('dominant_intents')[:3])}"
            )

        sector_readiness_changes = {
            "identity": "step_up_authentication" if policy_tier in {"high", "critical"} else "monitor_auth_anomalies",
            "endpoint": "raise_prevention_mode" if blast_radius >= 3 else "increase_detection_sensitivity",
            "network": "tighten_egress_controls" if blast_radius >= 3 else "increase_flow_sampling",
        }
        predicted_next_sectors = fused_signal.get("predicted_next_sectors") or []
        for sector in predicted_next_sectors:
            if sector == "identity":
                sector_readiness_changes["identity"] = "step_up_authentication"
            elif sector == "endpoint":
                sector_readiness_changes["endpoint"] = "raise_prevention_mode"
            elif sector in {"network", "data"}:
                sector_readiness_changes["network"] = "tighten_egress_controls"

        harmonic_state = (context or {}).get("harmonic_state") or {}
        timing_features = (context or {}).get("timing_features") or {}
        baseline_ref = (context or {}).get("baseline_ref") or {}
        domain_pulse = (context or {}).get("domain_pulse_summary") or {}
        discord_score = float(harmonic_state.get("discord_score") or 0.0)
        resonance_score = float(harmonic_state.get("resonance_score") or 0.0)
        confidence = float(harmonic_state.get("confidence") or 0.0)
        tempo_volatility = float(
            timing_features.get("jitter_norm")
            or harmonic_state.get("jitter_norm")
            or 0.0
        )
        if confidence < 0.4:
            cadence_alert_level = "observe"
            recommended_rhythm_shift = "hold_and_sample"
        elif discord_score >= 0.8:
            cadence_alert_level = "critical"
            recommended_rhythm_shift = "slow_and_gate"
        elif discord_score >= 0.6:
            cadence_alert_level = "high"
            recommended_rhythm_shift = "tighten_cadence"
        elif discord_score >= 0.4 or resonance_score <= 0.45:
            cadence_alert_level = "medium"
            recommended_rhythm_shift = "monitor_drift"
        else:
            cadence_alert_level = "low"
            recommended_rhythm_shift = "maintain_tempo"

        coherence_rank_by_domain = []
        if isinstance(domain_pulse, dict) and domain_pulse:
            if "domain" in domain_pulse:
                coherence_rank_by_domain = [
                    {
                        "domain": domain_pulse.get("domain"),
                        "coherence": round(float(domain_pulse.get("pulse_stability_index") or 0.0), 4),
                        "samples": int(domain_pulse.get("samples") or 0),
                    }
                ]
            else:
                coherence_rank_by_domain = [
                    {
                        "domain": d,
                        "coherence": round(float((info or {}).get("pulse_stability_index") or 0.0), 4),
                        "samples": int((info or {}).get("samples") or 0),
                    }
                    for d, info in domain_pulse.items()
                    if isinstance(info, dict)
                ]
                coherence_rank_by_domain.sort(key=lambda row: row.get("coherence", 0.0), reverse=True)

        return {
            "policy_tier": policy_tier,
            "context": context,
            "ranked_action_candidates": ranked,
            "ranked_action_sets": ranked_action_sets,
            "selected_action": top,
            "endpoint_preparation_recommendations": endpoint_preparation_recommendations,
            "sector_readiness_changes": sector_readiness_changes,
            "sector_preparation_plan": {
                "identity": "require_step_up_auth" if blast_radius >= 2 else "monitor_idp",
                "endpoint": "prepare_isolation_profiles" if blast_radius >= 3 else "raise_edr_sensitivity",
                "network": "tighten_egress_controls" if blast_radius >= 3 else "watch_lateral_movement",
            },
            "orchestration_plan": {
                "blast_radius": blast_radius,
                "reversibility": reversibility,
                "reversibility_score": round(reversibility_score, 3),
                "requires_human_approval": policy_tier in {"high", "critical"},
            },
            "cognitive_action_alignment": {
                "recommended_actions": fused_signal.get("recommended_actions") or [],
                "candidate_sources": cognitive_augmented["source_map"],
                "aatl_strategies": cognitive_augmented["aatl_strategies"],
                "selected_candidate_source": cognitive_augmented["source_map"].get((top or {}).get("candidate", ""), "unknown"),
                "cognitive_pressure": round(float(fused_signal.get("cognitive_pressure") or 0.0), 4),
            },
            "harmonic_interpretation": {
                "tempo_volatility": round(tempo_volatility, 4),
                "coherence_rank_by_domain": coherence_rank_by_domain,
                "recommended_rhythm_shift": recommended_rhythm_shift,
                "cadence_alert_level": cadence_alert_level,
                "baseline_ref": baseline_ref,
                "harmonic_state": harmonic_state,
            },
        }


@router.get("/michael/hello")
async def hello():
    return {"msg": "Michael stands ready"}
