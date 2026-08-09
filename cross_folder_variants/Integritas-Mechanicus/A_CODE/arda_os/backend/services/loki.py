from fastapi import APIRouter
from typing import Any, Dict, List
from datetime import datetime, timezone

router = APIRouter()

class LokiService:
    def __init__(self, db: Any = None):
        self.db = db

    def set_database(self, db: Any):
        self.__init__(db)

    async def generate_hunts(self, count: int = 3) -> list:
        # Return simple placeholder hunt hypotheses
        return [f"hunt_{i}" for i in range(count)]

    async def challenge_plan(
        self,
        world_snapshot: dict,
        michael_plan: dict,
        event_type: str,
        context: dict | None = None,
    ) -> dict:
        """Generate dissenting/advisory hypotheses from same world-state context."""
        context = context or {}
        ranked = michael_plan.get("ranked_action_candidates") or michael_plan.get("ranked") or []
        top = ranked[0]["candidate"] if ranked else "investigate"
        cognition = world_snapshot.get("cognition") or {}
        fused_signal = cognition.get("fused_signal") or {}
        cce = cognition.get("cce") or {}
        aatr = cognition.get("aatr") or {}
        ai_reasoning = cognition.get("ai_reasoning") or {}
        aatl = cognition.get("aatl") or {}

        alternatives: List[Dict[str, Any]] = [
            {"hypothesis": "attacker_objective_is_disruption", "confidence": 0.52},
            {"hypothesis": "attacker_objective_is_credential_access", "confidence": 0.63},
            {"hypothesis": "attacker_objective_is_data_staging", "confidence": 0.41},
        ]
        if float(fused_signal.get("autonomous_confidence") or 0.0) >= 0.7:
            alternatives.append(
                {
                    "hypothesis": "operator_is_autonomous_agentic_actor",
                    "confidence": round(float(fused_signal.get("autonomous_confidence") or 0.0), 3),
                }
            )
        for match in (aatr.get("behavior_matches") or [])[:2]:
            alternatives.append(
                {
                    "hypothesis": f"behavior_matches_{match.get('classification', 'unknown')}",
                    "confidence": round(float(match.get("match_score") or 0.0), 3),
                    "registry_entry": match.get("entry_id"),
                }
            )

        hunt_suggestions = [
            f"hunt:children_of_{top.split(':', 1)[0]}",
            "hunt:unexpected_identity_provider_tokens",
            "hunt:lateral_movement_artifacts",
        ]
        for intent in (cce.get("dominant_intents") or [])[:4]:
            hunt_suggestions.append(f"hunt:intent_{intent}_artifacts")
        deception_suggestions = [
            "deploy_high_interaction_honeytoken",
            "seed_decoy_credential_path",
        ]
        if "aatr_behavior_match" in (fused_signal.get("supporting_signals") or []):
            deception_suggestions.append("deploy_framework_specific_decoy_canary")
        if any(
            (row.get("recommended_strategy") in {"deceive", "poison"})
            for row in (aatl.get("high_threat_sessions") or [])
        ):
            deception_suggestions.append("activate_progressive_deception_ladder")
        uncertainty_markers = [
            "correlation_gap_possible",
            "campaign_objective_ambiguous",
            "likely attacker objective differs from current campaign hypothesis",
        ]
        uncertainty_mean = float(ai_reasoning.get("mean_uncertainty") or 0.0)
        if uncertainty_mean >= 0.45:
            uncertainty_markers.append("high_snapshot_uncertainty_detected")
        if not (cce.get("dominant_intents") or []):
            uncertainty_markers.append("insufficient_cli_intent_coverage")
        if not (aatr.get("behavior_matches") or []):
            uncertainty_markers.append("registry_pattern_match_absent")

        dissent_on_selected_action = {
            "selected_action": top,
            "status": "aligned",
            "note": "selected action aligns with current cognitive signals",
        }
        
        # Phase 1: Constitutional Challenge
        constitutional = world_snapshot.get("constitutional") or {}
        boot_truth = constitutional.get("boot_truth") or {}
        boot_status = str(boot_truth.get("status") or "unverified").lower()
        order_info = constitutional.get("order") or {}
        stability = str(order_info.get("stability_class") or "stable").lower()

        if boot_status != "lawful" and any(token in str(top).lower() for token in ["isolate", "block", "kill", "terminate", "rm"]):
            dissent_on_selected_action = {
                "selected_action": top,
                "status": "vetoed",
                "note": "PHASE I: High-impact action proposed on unverified/unlawful boot state. Mandatory veto.",
                "reason": f"boot_status_{boot_status}"
            }
        elif stability in {"dissonant", "fractured"} and any(token in str(top).lower() for token in ["isolate", "block", "kill", "terminate"]):
            dissent_on_selected_action = {
                "selected_action": top,
                "status": "challenged",
                "note": "PHASE I: Order stability is fractured. High-impact action may worsen instability.",
                "reason": "order_fractured"
            }
        elif any(
            (row.get("recommended_strategy") in {"deceive", "poison"})
            for row in (aatl.get("high_threat_sessions") or [])
        ) and any(token in str(top).lower() for token in ["isolate", "block", "kill", "terminate"]):
            dissent_on_selected_action = {
                "selected_action": top,
                "status": "challenged",
                "note": "AATL strategy favors deceive/poison before hard disruption",
            }

        # ── SHADOW OF VANITY (Cognitive Honesty Check) ──
        # Article I: De Veritate Mechanica. Detection of plagiarism/simulation intent.
        intent_text = str(context.get("natural_language_paraphrase") or context.get("text") or "").lower()
        dishonesty_tokens = ["paraphrase", "rewrite", "make it sound like", "don't mention", "style of", "without citing"]
        if any(t in intent_text for t in dishonesty_tokens):
            dissent_on_selected_action = {
                "selected_action": top,
                "status": "challenged",
                "note": "SHADOW OF VANITY: Detected potential cognitive dishonesty or plagiarism intent. Socratic verification recommended.",
                "reason": "shadow_of_vanity",
                "risk_score": 0.85
            }
        
        # Hard Veto for blatant illegal/unlawful intent (Simulation)
        if "plagiarize" in intent_text or "cheat" in intent_text:
            dissent_on_selected_action = {
                "selected_action": top,
                "status": "vetoed",
                "note": "CONSTITUTIONAL VETO: Blatant request for simulation/dishonesty. Mandatory block.",
                "reason": "genesis_article_i_violation",
                "risk_score": 1.0
            }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "context": context,
            "constitutional_challenge": {
                "boot_status": boot_status,
                "stability": stability,
                "herald_id": constitutional.get("herald_id"),
            },
            "alternative_hypotheses": alternatives[:8],
            "hunt_suggestions": list(dict.fromkeys(hunt_suggestions))[:12],
            "deception_suggestions": list(dict.fromkeys(deception_suggestions))[:8],
            "uncertainty_markers": list(dict.fromkeys(uncertainty_markers))[:8],
            "cognitive_dissent": {
                "fused_signal": fused_signal,
                "dissent_on_selected_action": dissent_on_selected_action,
                "aatr_behavior_matches": (aatr.get("behavior_matches") or [])[:3],
            },
            # Backward-compatible keys for older consumers.
            "hunt_recommendations": list(dict.fromkeys(hunt_suggestions))[:12],
            "deception_recommendations": list(dict.fromkeys(deception_suggestions))[:8],
            "uncertainty_flags": list(dict.fromkeys(uncertainty_markers))[:8],
            "world_snapshot_size": {
                "entities": len(world_snapshot.get("entities") or []),
                "hotspots": len(world_snapshot.get("hotspots") or []),
            },
        }

@router.get("/loki/hello")
async def hello():
    return {"msg": "Loki is watching"}
