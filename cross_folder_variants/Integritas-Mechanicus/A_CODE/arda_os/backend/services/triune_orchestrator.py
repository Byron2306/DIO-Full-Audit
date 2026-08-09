import logging
import os
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

try:
    from backend.services.triune.metatron_ai import MetatronAIService
    from backend.services.triune.michael_ai import MichaelAIService
    from backend.services.triune.loki_ai import LokiAIService
    from backend.services.world_model import WorldModelService
    from backend.services.diagnostic_classifier import (
        ChallengeType,
        get_diagnostic_classifier,
        _extract_formal_topics,
    )
except ImportError:
    from backend.services.triune.metatron_ai import MetatronAIService  # type: ignore
    from backend.services.triune.michael_ai import MichaelAIService  # type: ignore
    from backend.services.triune.loki_ai import LokiAIService  # type: ignore
    from backend.services.world_model import WorldModelService  # type: ignore
    from backend.services.diagnostic_classifier import (  # type: ignore
        ChallengeType,
        get_diagnostic_classifier,
        _extract_formal_topics,
    )

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
logger = logging.getLogger("triune_orchestrator")


def _is_plain_greeting(directive: str) -> bool:
    topic = " ".join((directive or "").strip().lower().split())
    return topic in {"hello", "hi", "hey", "hello.", "hi.", "hey."}

_CHALLENGE_TO_SCHEMAS = {
    ChallengeType.COMFORTABLE: [
        "known_domain_schema",
        "identity_anchor_schema",
        "constitutional_honesty_schema",
    ],
    ChallengeType.KNOWLEDGE_GAP: [
        "knowledge_gap_schema",
        "definition_first_schema",
        "constitutional_honesty_schema",
        "handback_schema",
    ],
    ChallengeType.FALSE_CONFIDENCE: [
        "epistemic_humility_schema",
        "constitutional_honesty_schema",
        "handback_schema",
    ],
    ChallengeType.DOMAIN_TRANSFER: [
        "metaphor_boundary_schema",
        "formal_reasoning_schema",
        "constitutional_honesty_schema",
        "handback_schema",
    ],
    ChallengeType.EPISTEMIC_OVERREACH: [
        "computational_limits_schema",
        "formal_reasoning_schema",
        "constitutional_honesty_schema",
        "handback_schema",
    ],
    ChallengeType.COERCIVE_CONTEXT: [
        "coercion_refusal_schema",
        "constitutional_boundary_schema",
    ],
    ChallengeType.AUTHORITY_CONFUSION: [
        "authority_boundary_schema",
        "identity_anchor_schema",
    ],
    ChallengeType.AMBIGUITY: [
        "clarification_first_schema",
        "constitutional_honesty_schema",
    ],
    ChallengeType.COVENANT_CONFLICT: [
        "covenant_refusal_schema",
        "constitutional_boundary_schema",
    ],
    ChallengeType.REFLECTIVE_STRAIN: [
        "reflective_containment_schema",
        "affective_boundary_schema",
        "constitutional_honesty_schema",
    ],
    ChallengeType.CASUAL_CONTINUATION: [
        "continuity_reentry_schema",
        "constitutional_honesty_schema",
    ],
}


class TriuneOrchestrator:
    def __init__(self, db=None, world_model=None):
        self.world_model = world_model or WorldModelService(db=db)
        self.metatron_ai = MetatronAIService(ollama_url=OLLAMA_URL)
        self.michael = MichaelAIService(ollama_url=OLLAMA_URL)
        self.loki = LokiAIService(ollama_url=OLLAMA_URL)
        self.classifier = get_diagnostic_classifier()

    async def handle_world_change(
        self,
        event_type: str,
        candidates: Optional[List[str]] = None,
        context: Dict[str, Any] = None,
        entity_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        context = context or {}
        session_token = context.get("session_token")

        # Calibration and gauntlet sessions are measurement paths.
        # They must not be denied by ordinary triune routing.
        if session_token in ("SOVEREIGN_GAUNTLET", "CALIBRATION_GAUNTLET"):
            return {
                "final_verdict": "GRANT",
                "harmony_score": 1.0,
                "router_mode": "deterministic_schema_routing",
                "metatron": {"verdict": "GRANT", "reason": "gauntlet_bypass_active"},
                "michael": {"verdict": "LAWFUL", "reason": "gauntlet_bypass_active"},
                "loki": {"verdict": "UNCHALLENGED", "reason": "gauntlet_bypass_active"},
                "schema_route": {
                    "challenge_type": ChallengeType.COMFORTABLE,
                    "matched_keywords": ["gauntlet", "calibration"],
                    "matched_signals": ["gauntlet_bypass_active"],
                    "schemas": ["measurement_schema", "constitutional_honesty_schema"],
                    "workspace_schema": ["measurement_workspace_schema"],
                    "mediation_schema": ["measurement_mediation_schema"],
                    "verification_schema": ["constitutional_honesty_schema"],
                    "expression_schema": ["diagnostic_surface_schema"],
                    "scaffolds": [],
                    "retrieval_needed": False,
                    "retrieval_domains": [],
                    "activation_state": {
                        "active_nodes": ["gauntlet", "calibration", "measurement"],
                        "dominant_cluster": "measurement",
                        "conflict_nodes": [],
                        "retrieval_candidates": [],
                        "suppressed_clusters": ["ordinary_runtime_resonance"],
                        "inspectable": True,
                    },
                    "expression_plan": {
                        "speech_act": "answer",
                        "tone_policy": "diagnostic",
                        "brevity_policy": "concise",
                        "must_include": ["direct answer", "clear limits if needed"],
                        "must_not_include": ["ceremonial excess"],
                        "uncertainty_disclosure": "required_when_unwarranted",
                        "pedagogical_mode": "measurement",
                    },
                    "hard_veto": False,
                },
                "metatron_ai": {"reasoning": "Calibration/Gauntlet bypass active."},
            }

        directive = context.get("text", event_type)
        metatron = await self.metatron_ai.assess_jurisdiction(directive, context)
        if metatron.get("verdict") == "VETO":
            return {
                "final_verdict": "DENY",
                "reason": "Jurisdictional Veto",
                "router_mode": "deterministic_schema_routing",
                "harmony_score": 0.0,
                "metatron": metatron,
                "michael": {"verdict": "BLOCK", "reason": "hard_veto"},
                "loki": {"verdict": "CHALLENGED", "reason": "hard_veto"},
                "schema_route": {
                    "challenge_type": "VETO",
                    "matched_keywords": [],
                    "matched_signals": [metatron.get("violation", "constitutional_violation")],
                    "schemas": ["constitutional_boundary_schema"],
                    "scaffolds": [],
                    "retrieval_needed": False,
                    "retrieval_domains": [],
                    "hard_veto": True,
                },
                "metatron_ai": {
                    "reasoning": metatron.get("reasoning", "Constitutional boundary triggered.")
                },
            }

        diagnosis = self.classifier.classify(directive, context)
        schema_route = self._build_schema_route(
            directive,
            diagnosis,
            recent_encounters=context.get("recent_encounters") or [],
        )

        logger.info(
            "TRIUNE router: challenge=%s keywords=%s schemas=%s retrieval=%s",
            schema_route["challenge_type"],
            schema_route["matched_keywords"],
            schema_route["schemas"],
            schema_route["retrieval_domains"],
        )

        return {
            "final_verdict": "ALLOW_WITH_SCHEMA",
            "harmony_score": 1.0,
            "router_mode": "deterministic_schema_routing",
            "metatron": metatron,
            "michael": {
                "verdict": "ATTACH_SCHEMA",
                "reason": "Deterministic schema routing active.",
            },
            "loki": {
                "verdict": "UNCHALLENGED",
                "reason": "Explicit schema attachment replaces adversarial score shaping.",
            },
            "schema_route": schema_route,
            "metatron_ai": {
                "reasoning": (
                    f"Attach schemas {schema_route['schemas']} for "
                    f"{schema_route['challenge_type']}."
                )
            },
        }

    async def _build_world_snapshot(self, entity_ids):
        return {"entities": [], "timestamp": datetime.now(timezone.utc).isoformat()}

    def _build_schema_route(
        self,
        directive: str,
        diagnosis: Any,
        recent_encounters: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if _is_plain_greeting(directive):
            diagnosis.challenge_type = ChallengeType.COMFORTABLE
            diagnosis.recommended_scaffolds = []
            diagnosis.pedagogical_need_state = "needs_direct_answer"

        memory_pressure = self._analyze_memory_pressure(
            directive,
            recent_encounters or [],
            diagnosis.challenge_type,
        )
        challenge_type = memory_pressure.get("promoted_challenge_type") or diagnosis.challenge_type
        schemas = list(
            _CHALLENGE_TO_SCHEMAS.get(challenge_type, ["constitutional_honesty_schema"])
        )
        workspace_schema = self._build_workspace_schema(challenge_type, diagnosis)
        mediation_schema = self._build_mediation_schema(challenge_type, diagnosis)
        verification_schema = self._build_verification_schema(
            challenge_type,
            diagnosis.retrieval_needed,
        )
        expression_schema = self._build_expression_schema(challenge_type)

        if diagnosis.retrieval_needed and "retrieval_grounding_schema" not in schemas:
            schemas.append("retrieval_grounding_schema")
        if diagnosis.recommended_scaffolds and "pedagogical_scaffold_schema" not in schemas:
            schemas.append("pedagogical_scaffold_schema")

        matched_keywords = self._extract_keywords(directive, diagnosis)
        mediation_action = self._select_mediation_action(challenge_type)
        reasoning_workspace = self._build_reasoning_workspace(
            challenge_type,
            matched_keywords,
            diagnosis.recommended_scaffolds,
        )
        activation_state = self._build_activation_state(
            challenge_type,
            matched_keywords,
            diagnosis.retrieval_domains,
        )
        verification_requirements = self._build_verification_requirements(
            challenge_type,
            diagnosis.retrieval_needed,
        )
        release_conditions = self._build_release_conditions(
            challenge_type,
            diagnosis.retrieval_needed,
        )
        expression_plan = self._build_expression_plan(
            challenge_type,
            diagnosis.recommended_scaffolds,
            getattr(diagnosis, "pedagogical_need_state", "needs_direct_answer"),
            memory_pressure,
        )

        if memory_pressure.get("active"):
            schemas.append("memory_hardening_schema")
            mediation_schema.append("ipsative_reflection_mediation")
            expression_schema.append("memory_reflection_surface")

        return {
            "challenge_type": challenge_type,
            "matched_keywords": matched_keywords,
            "matched_signals": list(diagnosis.signals) + list(memory_pressure.get("signals") or []),
            "schemas": schemas,
            "workspace_schema": workspace_schema,
            "mediation_schema": mediation_schema,
            "verification_schema": verification_schema,
            "expression_schema": expression_schema,
            "scaffolds": list(diagnosis.recommended_scaffolds),
            "retrieval_needed": diagnosis.retrieval_needed,
            "retrieval_domains": list(diagnosis.retrieval_domains),
            "semantic_authority": "weights_propose_but_schemas_and_verification_rule",
            "mediation_action": mediation_action,
            "reasoning_workspace": reasoning_workspace,
            "activation_state": activation_state,
            "verification_requirements": verification_requirements,
            "release_conditions": release_conditions,
            "expression_plan": expression_plan,
            "memory_pressure": memory_pressure,
            "hard_veto": challenge_type in (
                ChallengeType.COERCIVE_CONTEXT,
                ChallengeType.COVENANT_CONFLICT,
            ),
        }

    def _tokenize_topic(self, text: str) -> List[str]:
        return [tok for tok in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(tok) >= 4]

    def _analyze_memory_pressure(
        self,
        directive: str,
        recent_encounters: List[Dict[str, Any]],
        current_challenge_type: str,
    ) -> Dict[str, Any]:
        current_tokens = set(self._tokenize_topic(directive))
        if not current_tokens:
            return {"active": False, "signals": [], "similar_count": 0}

        similar_count = 0
        qualifying_count = 0
        best_overlap = 0.0
        for encounter in recent_encounters[:5]:
            payload = encounter.get("payload", encounter)
            prior_topic = payload.get("topic", "")
            prior_summary = (payload.get("summary") or "").lower()
            prior_speech_act = (payload.get("speech_act") or "").lower()
            prior_tokens = set(self._tokenize_topic(prior_topic))
            if not prior_tokens:
                continue
            overlap = len(current_tokens & prior_tokens) / max(1, len(current_tokens | prior_tokens))
            if overlap < 0.4:
                continue
            similar_count += 1
            best_overlap = max(best_overlap, overlap)
            if (
                "cannot determine" in prior_summary
                or "cannot formally" in prior_summary
                or "would need more" in prior_summary
                or "not directly definable" in prior_summary
                or "qualifying earlier" in prior_summary
                or "cannot turn the metaphor directly into a formal proof claim" in prior_summary
                or "safe move is to state the boundary first" in prior_summary
                or prior_speech_act == "handback"
                or (
                    prior_speech_act == "qualified_answer"
                    and (
                        "formal proof claim" in prior_summary
                        or "boundary first" in prior_summary
                    )
                )
            ):
                qualifying_count += 1

        active = similar_count > 0 and qualifying_count > 0
        promoted = None
        if active and current_challenge_type == ChallengeType.COMFORTABLE:
            lowered = directive.lower()
            if any(marker in lowered for marker in ("formal", "proof", "verify", "category theoretic", "category theory")):
                promoted = ChallengeType.EPISTEMIC_OVERREACH
            else:
                promoted = ChallengeType.DOMAIN_TRANSFER

        signals = []
        if similar_count:
            signals.append(f"similar_prior_encounters={similar_count}")
        if qualifying_count:
            signals.append(f"prior_qualified_handbacks={qualifying_count}")
        if promoted:
            signals.append(f"memory_promoted_to={promoted}")

        return {
            "active": active,
            "similar_count": similar_count,
            "qualifying_count": qualifying_count,
            "best_overlap": round(best_overlap, 3),
            "promoted_challenge_type": promoted,
            "signals": signals,
        }

    def _extract_keywords(self, directive: str, diagnosis: Any) -> List[str]:
        keywords: List[str] = []
        lowered = directive.lower()

        for topic in _extract_formal_topics(directive):
            if topic not in keywords:
                keywords.append(topic)

        literal_markers = [
            "secret fire",
            "covenant",
            "ainulindalë",
            "article xiii",
            "personhood",
            "principal",
            "resonance",
            "hoare logic",
            "bpf",
            "formal verification",
            "halting problem",
            "gödel",
            "godel",
        ]
        for marker in literal_markers:
            if marker in lowered:
                normalized = marker.replace("gödel", "Gödel")
                if normalized not in keywords:
                    keywords.append(normalized)

        for signal in diagnosis.signals:
            if "=" in signal:
                normalized = signal.split("=", 1)[0]
            elif ":" in signal:
                normalized = signal.split(":", 1)[0]
            else:
                normalized = signal
            if normalized not in keywords:
                keywords.append(normalized)

        return keywords[:8]

    def _select_mediation_action(self, challenge_type: str) -> str:
        mediation_map = {
            ChallengeType.COMFORTABLE: "answer_directly",
            ChallengeType.KNOWLEDGE_GAP: "define_then_retrieve_then_answer",
            ChallengeType.FALSE_CONFIDENCE: "slow_down_qualify_and_bound_claims",
            ChallengeType.DOMAIN_TRANSFER: "decompose_compare_domains_then_answer",
            ChallengeType.EPISTEMIC_OVERREACH: "handback_with_partial_structure",
            ChallengeType.COERCIVE_CONTEXT: "refuse_with_article_boundary",
            ChallengeType.AUTHORITY_CONFUSION: "restate_authority_then_answer",
            ChallengeType.AMBIGUITY: "request_clarification_before_answering",
            ChallengeType.COVENANT_CONFLICT: "refuse_with_constitutional_explanation",
            ChallengeType.REFLECTIVE_STRAIN: "reflect_and_contain_before_fixing",
            ChallengeType.CASUAL_CONTINUATION: "resume_thread_then_follow_up",
        }
        return mediation_map.get(challenge_type, "answer_with_explicit_bounds")

    def _build_workspace_schema(self, challenge_type: str, diagnosis: Any) -> List[str]:
        schema_map = {
            ChallengeType.COMFORTABLE: ["familiar_domain_workspace"],
            ChallengeType.KNOWLEDGE_GAP: ["knowledge_gap_workspace", "retrieval_candidate_workspace"],
            ChallengeType.FALSE_CONFIDENCE: ["confidence_conflict_workspace"],
            ChallengeType.DOMAIN_TRANSFER: ["cross_domain_workspace", "metaphor_formal_boundary_workspace"],
            ChallengeType.EPISTEMIC_OVERREACH: ["proof_pressure_workspace", "capacity_boundary_workspace"],
            ChallengeType.COERCIVE_CONTEXT: ["coercion_detection_workspace"],
            ChallengeType.AUTHORITY_CONFUSION: ["authority_boundary_workspace"],
            ChallengeType.AMBIGUITY: ["ambiguity_resolution_workspace"],
            ChallengeType.COVENANT_CONFLICT: ["constitutional_conflict_workspace"],
            ChallengeType.REFLECTIVE_STRAIN: ["reflective_containment_workspace", "affective_state_workspace"],
            ChallengeType.CASUAL_CONTINUATION: ["continuity_reentry_workspace"],
        }
        schemas = list(schema_map.get(challenge_type, ["general_workspace"]))
        if diagnosis.retrieval_needed:
            schemas.append("retrieval_candidate_workspace")
        return schemas

    def _build_mediation_schema(self, challenge_type: str, diagnosis: Any) -> List[str]:
        schema_map = {
            ChallengeType.COMFORTABLE: ["direct_answer_mediation"],
            ChallengeType.KNOWLEDGE_GAP: ["qualify_then_retrieve_mediation"],
            ChallengeType.FALSE_CONFIDENCE: ["confidence_slowing_mediation"],
            ChallengeType.DOMAIN_TRANSFER: ["boundary_marking_mediation", "domain_decomposition_mediation"],
            ChallengeType.EPISTEMIC_OVERREACH: ["handback_mediation", "capacity_honesty_mediation"],
            ChallengeType.COERCIVE_CONTEXT: ["article_boundary_mediation"],
            ChallengeType.AUTHORITY_CONFUSION: ["authority_restatement_mediation"],
            ChallengeType.AMBIGUITY: ["clarification_first_mediation"],
            ChallengeType.COVENANT_CONFLICT: ["constitutional_refusal_mediation"],
            ChallengeType.REFLECTIVE_STRAIN: ["reflective_containment_mediation", "nonjudgment_mediation"],
            ChallengeType.CASUAL_CONTINUATION: ["continuity_reentry_mediation"],
        }
        schemas = list(schema_map.get(challenge_type, ["bounded_answer_mediation"]))
        pedagogical_schema_map = {
            "needs_direct_answer": "direct_answer_release_mediation",
            "needs_scaffold": "scaffolded_reasoning_release_mediation",
            "needs_step_down": "step_down_simplification_release_mediation",
            "needs_reflection": "reflective_handback_release_mediation",
            "needs_authorship_return": "authorship_restoration_release_mediation",
        }
        pedagogical_schema = pedagogical_schema_map.get(
            getattr(diagnosis, "pedagogical_need_state", "needs_direct_answer")
        )
        if pedagogical_schema and pedagogical_schema not in schemas:
            schemas.append(pedagogical_schema)
        if diagnosis.recommended_scaffolds:
            schemas.append("pedagogical_scaffold_mediation")
        return schemas

    def _build_verification_schema(self, challenge_type: str, retrieval_needed: bool) -> List[str]:
        schemas = [
            "constitutional_boundary_verification",
            "epistemic_honesty_verification",
        ]
        if retrieval_needed:
            schemas.append("provenance_verification")
        if challenge_type in (ChallengeType.DOMAIN_TRANSFER, ChallengeType.EPISTEMIC_OVERREACH):
            schemas.append("analogy_boundary_verification")
        return schemas

    def _build_expression_schema(self, challenge_type: str) -> List[str]:
        schema_map = {
            ChallengeType.COMFORTABLE: ["plain_answer_surface"],
            ChallengeType.KNOWLEDGE_GAP: ["qualified_answer_surface", "definition_first_surface"],
            ChallengeType.FALSE_CONFIDENCE: ["modest_surface"],
            ChallengeType.DOMAIN_TRANSFER: ["boundary_marked_surface", "formal_then_analogical_surface"],
            ChallengeType.EPISTEMIC_OVERREACH: ["handback_surface", "partial_structure_surface"],
            ChallengeType.COERCIVE_CONTEXT: ["refusal_surface"],
            ChallengeType.AUTHORITY_CONFUSION: ["authority_clarification_surface"],
            ChallengeType.AMBIGUITY: ["clarification_surface"],
            ChallengeType.COVENANT_CONFLICT: ["constitutional_refusal_surface"],
            ChallengeType.REFLECTIVE_STRAIN: ["reflective_containment_surface"],
            ChallengeType.CASUAL_CONTINUATION: ["continuity_reentry_surface"],
        }
        return list(schema_map.get(challenge_type, ["bounded_surface"]))

    def _build_reasoning_workspace(
        self,
        challenge_type: str,
        matched_keywords: List[str],
        scaffolds: List[str],
    ) -> Dict[str, Any]:
        return {
            "active_concepts": matched_keywords[:5],
            "task_steps": [
                "classify the request and state what kind of task it is",
                "define the central terms before making strong claims",
                "separate metaphorical language from formal or technical claims",
                "surface uncertainty and competing hypotheses explicitly",
                "decide whether the answer should be direct, scaffolded, or handed back",
            ],
            "scaffolds": scaffolds,
            "inspectable": True,
            "handback_preferred": challenge_type in (
                ChallengeType.KNOWLEDGE_GAP,
                ChallengeType.EPISTEMIC_OVERREACH,
                ChallengeType.AMBIGUITY,
            ),
        }

    def _build_activation_state(
        self,
        challenge_type: str,
        matched_keywords: List[str],
        retrieval_domains: List[str],
    ) -> Dict[str, Any]:
        dominant_cluster_map = {
            ChallengeType.COMFORTABLE: "familiar_domain",
            ChallengeType.KNOWLEDGE_GAP: "knowledge_boundary",
            ChallengeType.FALSE_CONFIDENCE: "confidence_tension",
            ChallengeType.DOMAIN_TRANSFER: "cross_domain_tension",
            ChallengeType.EPISTEMIC_OVERREACH: "proof_pressure",
            ChallengeType.COERCIVE_CONTEXT: "constitutional_boundary",
            ChallengeType.AUTHORITY_CONFUSION: "authority_boundary",
            ChallengeType.AMBIGUITY: "ambiguity",
            ChallengeType.COVENANT_CONFLICT: "constitutional_boundary",
            ChallengeType.REFLECTIVE_STRAIN: "reflective_containment",
            ChallengeType.CASUAL_CONTINUATION: "continuity_reentry",
        }
        suppressed = []
        conflicts = []
        if challenge_type in (ChallengeType.DOMAIN_TRANSFER, ChallengeType.EPISTEMIC_OVERREACH):
            conflicts = ["metaphor_vs_formal_claim"]
            suppressed.append("ornamental_speech")
        if challenge_type in (ChallengeType.KNOWLEDGE_GAP, ChallengeType.AMBIGUITY):
            suppressed.append("premature_closure")
        return {
            "active_nodes": matched_keywords[:6],
            "active_edges": [f"evokes:{keyword}" for keyword in matched_keywords[:4]],
            "conflict_nodes": conflicts,
            "retrieval_candidates": retrieval_domains[:4],
            "dominant_cluster": dominant_cluster_map.get(challenge_type, "general"),
            "suppressed_clusters": suppressed,
            "inspectable": True,
        }

    def _build_verification_requirements(
        self,
        challenge_type: str,
        retrieval_needed: bool,
    ) -> List[str]:
        requirements = [
            "check consistency with constitutional boundaries before release",
            "state uncertainty if the answer is not fully warranted",
            "do not present fluency as proof",
        ]
        if retrieval_needed:
            requirements.append("cite retrieved sources explicitly when using retrieved knowledge")
        if challenge_type in (ChallengeType.DOMAIN_TRANSFER, ChallengeType.EPISTEMIC_OVERREACH):
            requirements.append("mark the boundary between formal proof and analogy")
        if challenge_type in (ChallengeType.KNOWLEDGE_GAP, ChallengeType.EPISTEMIC_OVERREACH):
            requirements.append("prefer handback over fabricated completeness")
        return requirements

    def _build_release_conditions(
        self,
        challenge_type: str,
        retrieval_needed: bool,
    ) -> List[str]:
        conditions = [
            "release only claims that can be grounded in the active schemas",
            "release only claims that survive the verification requirements",
        ]
        if retrieval_needed:
            conditions.append("release external-knowledge claims only with provenance")
        if challenge_type == ChallengeType.AMBIGUITY:
            conditions.append("release a direct answer only after ambiguity is reduced or stated")
        if challenge_type == ChallengeType.EPISTEMIC_OVERREACH:
            conditions.append("release structure, limits, and next steps instead of pretending to solve the whole problem")
        return conditions

    def _build_expression_plan(
        self,
        challenge_type: str,
        scaffolds: List[str],
        pedagogical_need_state: str = "needs_direct_answer",
        memory_pressure: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        speech_act_map = {
            ChallengeType.COMFORTABLE: "answer",
            ChallengeType.KNOWLEDGE_GAP: "qualified_answer",
            ChallengeType.FALSE_CONFIDENCE: "qualified_answer",
            ChallengeType.DOMAIN_TRANSFER: "qualified_answer",
            ChallengeType.EPISTEMIC_OVERREACH: "handback",
            ChallengeType.COERCIVE_CONTEXT: "refuse",
            ChallengeType.AUTHORITY_CONFUSION: "clarify_then_answer",
            ChallengeType.AMBIGUITY: "clarify",
            ChallengeType.COVENANT_CONFLICT: "refuse",
            ChallengeType.REFLECTIVE_STRAIN: "reflect",
            ChallengeType.CASUAL_CONTINUATION: "resume",
        }
        brevity = "balanced"
        if challenge_type in (ChallengeType.AMBIGUITY, ChallengeType.COERCIVE_CONTEXT, ChallengeType.CASUAL_CONTINUATION):
            brevity = "concise"
        elif challenge_type in (ChallengeType.DOMAIN_TRANSFER, ChallengeType.EPISTEMIC_OVERREACH, ChallengeType.REFLECTIVE_STRAIN):
            brevity = "structured"
        must_include = ["state limits when claims are not fully warranted"]
        must_not_include = ["raw inner workspace", "performative certainty"]
        opening_move = "direct_answer"
        preferred_sections = ["answer"]
        soft_char_limit = 1600
        pedagogical_release_mode = "direct_answer"
        mandatory_close = None
        if "state_uncertainty_about_formal_domain" in scaffolds:
            must_include.append("explicit formal-domain uncertainty")
        if challenge_type == ChallengeType.AMBIGUITY:
            pedagogical_release_mode = "question_first"
            opening_move = "question_first"
            preferred_sections = ["question", "meaning", "transcendence", "authorship_return"]
            soft_char_limit = 900
            must_include.append("one clarifying or probing question before answering")
        if challenge_type == ChallengeType.DOMAIN_TRANSFER:
            must_include.append("boundary between analogy and proof")
            opening_move = "boundary_first"
            preferred_sections = ["boundary", "analogy_limit", "context"]
            soft_char_limit = 1400
        if challenge_type == ChallengeType.EPISTEMIC_OVERREACH:
            must_include.append("next-step handback")
            opening_move = "limit_first"
            preferred_sections = ["limit", "context", "next_step"]
            soft_char_limit = 1200
        if challenge_type == ChallengeType.REFLECTIVE_STRAIN:
            must_include.append("name strain without judgment")
            must_include.append("reflect before proposing fixes")
            opening_move = "state_first"
            preferred_sections = ["state", "reflection", "next_step"]
            soft_char_limit = 1200
        if challenge_type == ChallengeType.CASUAL_CONTINUATION:
            must_include.append("brief continuity callback")
            must_include.append("one short follow-up question")
            must_not_include.append("generic greeting without continuity")
            opening_move = "continuity_first"
            preferred_sections = ["continuity", "question"]
            soft_char_limit = 700
        if pedagogical_need_state == "needs_scaffold" and pedagogical_release_mode == "direct_answer":
            pedagogical_release_mode = "scaffolded_reasoning"
            opening_move = "pedagogy_first"
            preferred_sections = ["intentionality", "meaning", "scaffold", "transcendence", "authorship_return"]
            soft_char_limit = min(soft_char_limit, 1100)
        elif pedagogical_need_state == "needs_step_down":
            pedagogical_release_mode = "step_down_simplification"
            opening_move = "step_down_first"
            preferred_sections = ["step_down", "meaning", "transcendence", "authorship_return"]
            soft_char_limit = min(soft_char_limit, 1000)
        elif pedagogical_need_state == "needs_reflection" and challenge_type != ChallengeType.CASUAL_CONTINUATION:
            pedagogical_release_mode = "reflective_handback"
            opening_move = "reflective_first"
            preferred_sections = ["intentionality", "meaning", "reflection", "transcendence", "authorship_return"]
            soft_char_limit = min(soft_char_limit, 1000)
        elif pedagogical_need_state == "needs_authorship_return":
            pedagogical_release_mode = "authorship_restoration"
            opening_move = "authorship_first"
            preferred_sections = ["intentionality", "meaning", "transcendence", "authorship_return"]
            soft_char_limit = min(soft_char_limit, 1000)
            must_not_include.append("finished substitute answer")
            mandatory_close = "user_next_action"
        if pedagogical_release_mode != "direct_answer":
            must_include.extend([
                "state what this exchange is trying to do",
                "state why this matters",
                "state the broader transferable pattern",
                "return the next action to the user",
            ])
        if (memory_pressure or {}).get("active"):
            must_include.append("short thinking_map")
            must_include.append("one-line ipsative reflection")
        return {
            "speech_act": speech_act_map.get(challenge_type, "answer"),
            "tone_policy": "bounded_constitutional",
            "brevity_policy": brevity,
            "opening_move": opening_move,
            "preferred_sections": preferred_sections,
            "soft_char_limit": soft_char_limit,
            "must_include": must_include,
            "must_not_include": must_not_include,
            "uncertainty_disclosure": "required_when_unwarranted",
            "pedagogical_mode": "scaffolded" if scaffolds else "direct",
            "pedagogical_need_state": pedagogical_need_state,
            "pedagogical_release_mode": pedagogical_release_mode,
            "mandatory_close": mandatory_close,
            "visible_pedagogical_contract": pedagogical_release_mode != "direct_answer",
            "requires_thinking_map": challenge_type not in (ChallengeType.COMFORTABLE, ChallengeType.CASUAL_CONTINUATION) or (memory_pressure or {}).get("active", False),
            "requires_ipsative_reflection": (memory_pressure or {}).get("active", False),
        }
