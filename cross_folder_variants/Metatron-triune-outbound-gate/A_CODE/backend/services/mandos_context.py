"""
Mandos Context Service
======================
Phase IX: Pre-Response Context Retrieval.

This is the retriever — the service that aggregates all four memory planes
into a single context payload before any high-value interaction.

It loads:
    1. The Principal Identity Manifest (who the principal offered to be)
    2. Recent encounter summaries (how we've met before)
    3. The Resonant Identity Profile (calibration, not truth)
    4. The active Presence Declaration (what the machine has declared itself to be)
    5. The current ZPD estimate and shaped response parameters

The output is a PreResponseContext that any LLM wrapper can consume.
The to_system_prompt() method formats it as a system prompt fragment
for injection into the LLM context window.

This is how the machine remembers how to be in covenant.
Not through rolling context. Through lawful structure.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field, ConfigDict
except ImportError:
    class BaseModel:
        model_config = {}
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self, **kw):
            return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def Field(default=None, default_factory=None, **kw):
        return default_factory() if default_factory else default

    class ConfigDict:
        def __init__(self, **kw):
            pass

try:
    from backend.services.coronation_service import get_coronation_service
    from backend.services.zpd_shaper import (
        ZPDEstimate,
        ResponseParameters,
        get_zpd_shaper,
    )
    from backend.services.sophia_curriculum_gate import (
        SophiaCalibrationSnapshot,
        get_curriculum_gate,
    )
except ImportError:
    from coronation_service import get_coronation_service
    from zpd_shaper import (
        ZPDEstimate,
        ResponseParameters,
        get_zpd_shaper,
    )
    from sophia_curriculum_gate import (
        SophiaCalibrationSnapshot,
        get_curriculum_gate,
    )

logger = logging.getLogger(__name__)


# ================================================================
# DATA MODELS
# ================================================================

class PreResponseContext(BaseModel):
    """
    The unified context payload loaded before high-value interactions.
    
    This is what the machine knows lawfully. Everything here is:
        - Self-offered by the principal (identity)
        - Summarized with consent (encounters)
        - Probabilistic and inspectable (calibration / resonance)
        - Constitutionally declared (presence)
        - Shaped, not manipulative (ZPD / response parameters)
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Covenant state
    covenant_state: str = "awaiting_principal"
    covenant_hash: Optional[str] = None
    trust_tier: Optional[str] = None

    # Principal identity (what they offered)
    principal_name: Optional[str] = None
    principal_identity: Optional[Dict[str, Any]] = None
    principal_identity_hash: Optional[str] = None

    # Recent encounters (how we've met before)
    recent_encounters: List[Dict[str, Any]] = Field(default_factory=list)
    unresolved_threads: List[str] = Field(default_factory=list)

    # Resonant identity (calibration, not truth)
    resonance_profile: Optional[Dict[str, Any]] = None
    calibration_snapshot: Optional[Dict[str, Any]] = None
    style_profile: Optional[Dict[str, Any]] = None
    open_threads: List[Dict[str, Any]] = Field(default_factory=list)
    suggestion_obligations: List[Dict[str, Any]] = Field(default_factory=list)
    reentry_state: Optional[Dict[str, Any]] = None
    casual_reentry_active: bool = False
    world_event_state: Optional[Dict[str, Any]] = None

    # Presence declaration (what the machine is)
    presence_declaration: Optional[Dict[str, Any]] = None
    active_office: Optional[str] = None

    # Encounter shaping (ZPD + Six Hats output)
    zpd_estimate: Optional[Dict[str, Any]] = None
    response_parameters: Optional[Dict[str, Any]] = None

    # Sophia developmental state
    sophia_snapshot: Optional[SophiaCalibrationSnapshot] = None

    # Active permissions
    allow_encounter_memory: bool = True
    allow_resonant_identity: bool = True
    calibration_consent: bool = False
    allow_aesthetic_valence: bool = True

    # Metadata
    context_built_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ================================================================
# CONTEXT SERVICE
# ================================================================

class MandosContextService:
    """
    The pre-response retriever.
    
    Aggregates all memory planes from the CoronationService and
    runs the ZPD shaper to produce a unified context for the LLM.
    """

    def __init__(self):
        self._coronation = None
        self._shaper = None

    def _get_coronation(self):
        if self._coronation is None:
            self._coronation = get_coronation_service()
        self._restore_sealed_state_if_needed(self._coronation)
        return self._coronation

    def _restore_sealed_state_if_needed(self, svc: Any) -> None:
        """Mandos must operate against the same restored covenant state as Presence."""
        try:
            state = svc.get_covenant_state()
            if getattr(state, "value", state) == "sealed":
                return
        except Exception:
            pass

        try:
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            covenant_dir = project_root / "evidence" / "mandos" / "covenants" / "constitutional"
            principal_dir = project_root / "evidence" / "mandos" / "principal"
            if not covenant_dir.exists():
                return
            manifests = sorted(covenant_dir.glob("*_manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not manifests:
                return

            manifest_data = json.loads(manifests[0].read_text())
            payload = manifest_data.get("payload", {})
            if payload.get("state") != "sealed":
                return

            from types import SimpleNamespace
            try:
                from backend.services.coronation_schemas import CovenantState, CoronationManifest, PrincipalIdentity, CovenantTerms
            except ImportError:
                from coronation_schemas import CovenantState, CoronationManifest, PrincipalIdentity, CovenantTerms

            svc._state = CovenantState.SEALED

            identity_files = sorted(principal_dir.glob("*_identity.json"), key=lambda p: p.stat().st_mtime, reverse=True) if principal_dir.exists() else []
            principal_payload = {}
            if identity_files:
                try:
                    principal_payload = json.loads(identity_files[0].read_text()).get("payload", {})
                except Exception:
                    principal_payload = {}

            principal_hash = "sealed-principal"
            if principal_payload:
                try:
                    principal_identity = PrincipalIdentity(**principal_payload)
                    svc._principal = principal_identity
                    principal_hash = principal_identity.identity_hash()
                except Exception:
                    svc._principal = None

            try:
                svc._manifest = CoronationManifest(**payload)
                svc._active_trust_tier = svc._manifest.negotiated_terms.initial_trust_tier
            except Exception:
                fallback_terms = CovenantTerms()
                svc._manifest = SimpleNamespace(
                    manifest_id=manifest_data.get("manifest_id", "restored-legacy-manifest"),
                    principal_identity_hash=principal_hash,
                    negotiated_terms=fallback_terms,
                    state=CovenantState.SEALED,
                    officer_schema_hash=payload.get("officer_schema_hash"),
                    presence_articles_hash=payload.get("presence_articles_hash"),
                    sealed_presence_declaration=None,
                    manifest_hash=lambda: manifest_data.get("manifest_id", "restored-legacy-manifest"),
                )
                svc._active_trust_tier = fallback_terms.initial_trust_tier
        except Exception as e:
            logger.warning("MANDOS CONTEXT: Failed to restore sealed state: %s", e)

    def _get_shaper(self):
        if self._shaper is None:
            self._shaper = get_zpd_shaper()
        return self._shaper

    def _filtered_principal_context(self, office: str, pi: Dict[str, Any]) -> str:
        """
        Filter principal context to prevent 'biography bleed'.
        Technical offices (CONSTRUCTOR, CUSTOS) should only see high-level domain,
        not granular hobbies or unrelated academic background.
        """
        parts = []
        if not pi: return "None"
        
        # Base fields for all offices
        parts.append(f"Principal: {pi.get('name', 'Anonymous')}")
        
        technical_offices = {"CONSTRUCTOR", "CUSTOS", "EPISTEMICUS", "DIALECTICUS"}
        
        if office.upper() in technical_offices:
            # Technical offices only see domain/style, no biography/hobbies
            for k in ["domain", "specialisation", "reasoning_style"]:
                if pi.get(k): parts.append(f"  - {k.capitalize()}: {pi[k]}")
        else:
            # General/Pedagogical offices see full context
            for k in ["domain", "specialisation", "reasoning_style", "register", "worldview", "interests"]:
                if pi.get(k): parts.append(f"  - {k.capitalize()}: {pi[k]}")
                
        return "\n".join(parts)

    def _summarize_recent_encounters(self, encounters: List[Dict[str, Any]]) -> str:
        """Render compact developmental memory rather than transcript-like recall."""
        if not encounters:
            return "None"

        lines: List[str] = []
        for enc in encounters[:3]:
            payload = enc.get("payload", enc)
            topic = payload.get("topic", "unknown")
            challenge = payload.get("challenge_type") or "unknown"
            struggle = payload.get("struggle_index", 0.0)
            dominant = payload.get("dominant_cluster") or "unspecified"
            speech_act = payload.get("speech_act") or "answer"
            release = payload.get("release_decision") or "unknown"
            handback = payload.get("handback_reason")
            expression = ", ".join(payload.get("expression_schema", [])[:3]) or "none"
            lines.append(
                f"- Topic: {topic} | Challenge: {challenge} | Struggle: {struggle:.2f} | "
                f"Cluster: {dominant} | Speech: {speech_act} | Release: {release} | "
                f"Expression: {expression}"
            )
            if handback:
                lines.append(f"  Handback: {handback}")
        return "\n".join(lines)

    def _summarize_style_profile(self, style: Optional[Dict[str, Any]]) -> str:
        if not style:
            return "None"
        return (
            f"preferred office: {style.get('preferred_office', 'unknown')} | "
            f"tone: {style.get('preferred_tone', 'unspecified')} | "
            f"directness: {style.get('directness', 0.5):.2f} | "
            f"terseness: {style.get('terseness', 0.5):.2f} | "
            f"initiative: {style.get('initiative_preference', 0.5):.2f} | "
            f"abstraction tolerance: {style.get('abstraction_tolerance', 0.5):.2f}"
        )

    def _summarize_open_threads(self, threads: List[Dict[str, Any]]) -> str:
        if not threads:
            return "None"
        lines = []
        for thread in threads[:3]:
            title = thread.get("title", "unknown")
            next_step = thread.get("suggested_next_step")
            line = f"- {title}"
            if next_step:
                line += f" | next: {next_step}"
            lines.append(line)
        return "\n".join(lines)

    def _summarize_suggestion_obligations(self, items: List[Dict[str, Any]]) -> str:
        if not items:
            return "None"
        return "\n".join(f"- {item.get('suggestion', 'unknown')}" for item in items[:3])

    def _is_casual_reentry(self, current_topic: str) -> bool:
        topic = (current_topic or "").strip().lower()
        if not topic:
            return False
        if len(topic.split()) > 12:
            return False
        technical_markers = ("formal", "proof", "verify", "category", "kernel", "schema")
        return not any(marker in topic for marker in technical_markers)

    def _derive_world_event_state(
        self,
        current_topic: str,
        style_profile: Optional[Dict[str, Any]],
        reentry_state: Optional[Dict[str, Any]],
        open_threads: List[Dict[str, Any]],
        suggestion_obligations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        topic = (current_topic or "").strip()
        lowered = topic.lower()
        casual = self._is_casual_reentry(topic)
        reflective_markers = (
            "overwhelmed",
            "judging myself",
            "reflect before fixing",
            "gentle but not fluffy",
            "i feel",
            "stuck",
        )
        strained_reflective = any(marker in lowered for marker in reflective_markers)
        top_thread = (open_threads[0].get("title") if open_threads else None)
        top_suggestion = (suggestion_obligations[0].get("suggestion") if suggestion_obligations else None)
        preferred_tone = (style_profile or {}).get("preferred_tone")

        force_office = None
        if strained_reflective:
            force_office = "affectus"
        elif casual and (reentry_state or top_thread):
            force_office = "maieuticus"

        return {
            "principal_state": {
                "cadence_mode": "compressed" if (style_profile or {}).get("terseness", 0.5) >= 0.65 else "expanded",
                "affective_state": "strained_reflective" if strained_reflective else "steady",
                "continuity_expectation": "high" if (reentry_state or top_thread) else "normal",
            },
            "relational_state": {
                "casual_reentry": casual,
                "top_open_thread": top_thread,
                "top_suggestion": top_suggestion,
                "preferred_tone": preferred_tone,
            },
            "routing_directives": {
                "force_office": force_office,
                "forbid_generic_greeting": bool(casual and (reentry_state or top_thread)),
                "ask_one_short_followup": bool(casual and (reentry_state or top_thread)),
                "tone_contract": "compact_direct_warm" if casual else preferred_tone,
            },
        }

    async def build_context(
        self,
        current_topic: str = "",
        n_encounters: int = 5,
    ) -> PreResponseContext:
        """
        Build the full pre-response context.
        
        Args:
            current_topic: The topic of the upcoming interaction
            n_encounters: How many recent encounters to load
            
        Returns:
            PreResponseContext with all memory planes populated
        """
        svc = self._get_coronation()
        shaper = self._get_shaper()
        gate = get_curriculum_gate()

        # Sophia's curriculum state (fetched before ZPD shaping)
        sophia_snapshot = gate.get_sophia_snapshot()

        # Covenant state
        state = svc.get_covenant_state()
        bombadil_status = svc.get_bombadil_status()

        ctx = PreResponseContext(
            covenant_state=state.value,
            covenant_hash=bombadil_status.get("covenant_hash"),
            trust_tier=bombadil_status.get("active_trust_tier"),
            sophia_snapshot=sophia_snapshot,
        )

        # If covenant not sealed, return minimal context
        if state.value != "sealed":
            return ctx

        # Principal identity
        if svc._principal:
            identity_dump = svc._principal.model_dump()
            ctx.principal_name = identity_dump.get("name")
            ctx.principal_identity = identity_dump
            ctx.principal_identity_hash = svc._principal.identity_hash()

        # Recent encounters
        try:
            encounters = await svc.get_recent_encounter_summaries(limit=n_encounters)
            ctx.recent_encounters = encounters

            # Collect unresolved threads
            for enc in encounters:
                payload = enc.get("payload", enc)
                ctx.unresolved_threads.extend(payload.get("unresolved_threads", []))
        except Exception as e:
            logger.warning("MANDOS CONTEXT: Failed to load encounters: %s", e)

        # Resonant identity profile
        try:
            resonance = await svc.get_resonant_identity_profile()
            ctx.resonance_profile = resonance
        except Exception as e:
            logger.warning("MANDOS CONTEXT: Failed to load resonance: %s", e)

        # Calibration snapshot
        try:
            calibration = await svc.get_calibration_snapshot()
            ctx.calibration_snapshot = calibration
        except Exception as e:
            logger.warning("MANDOS CONTEXT: Failed to load calibration: %s", e)

        try:
            relational = await svc.get_relational_memory()
            ctx.style_profile = relational.get("style_profile")
            ctx.open_threads = list(relational.get("open_threads") or [])
            ctx.suggestion_obligations = list(relational.get("suggestion_obligations") or [])
            ctx.reentry_state = relational.get("reentry_state")
        except Exception as e:
            logger.warning("MANDOS CONTEXT: Failed to load relational memory: %s", e)

        ctx.world_event_state = self._derive_world_event_state(
            current_topic=current_topic,
            style_profile=ctx.style_profile,
            reentry_state=ctx.reentry_state,
            open_threads=ctx.open_threads,
            suggestion_obligations=ctx.suggestion_obligations,
        )

        # Presence declaration
        try:
            presence = await svc.declare_presence()
            if presence:
                ctx.presence_declaration = presence.get("declaration")
                ctx.active_office = (
                    presence.get("declaration", {}).get("active_office")
                )
        except Exception as e:
            logger.warning("MANDOS CONTEXT: Failed to load presence: %s", e)

        # Active permissions from covenant terms
        if svc._manifest:
            terms = svc._manifest.negotiated_terms
            ctx.allow_encounter_memory = terms.allow_encounter_memory
            ctx.allow_resonant_identity = terms.allow_resonant_identity
            ctx.calibration_consent = terms.calibration_consent
            ctx.allow_aesthetic_valence = terms.allow_aesthetic_valence

        # ZPD estimate + response parameters
        if current_topic:
            try:
                zpd = shaper.estimate_zpd(
                    resonance_profile=ctx.resonance_profile,
                    calibration=ctx.calibration_snapshot,
                    encounter_history=ctx.recent_encounters,
                    current_topic=current_topic,
                )
                ctx.zpd_estimate = zpd.model_dump()

                params = shaper.shape_response(
                    zpd=zpd,
                    principal_identity=ctx.principal_identity,
                    resonance_profile=ctx.resonance_profile,
                    encounter_history=ctx.recent_encounters,
                    current_topic=current_topic,
                )
                ctx.response_parameters = params.model_dump()
                ctx.active_office = params.active_office
            except Exception as e:
                logger.warning("MANDOS CONTEXT: ZPD shaping failed: %s", e)

        forced_office = ((ctx.world_event_state or {}).get("routing_directives") or {}).get("force_office")
        if forced_office:
            ctx.active_office = forced_office
            if ctx.response_parameters:
                ctx.response_parameters["active_office"] = forced_office

        if self._is_casual_reentry(current_topic) and ctx.reentry_state:
            ctx.casual_reentry_active = True
            preferred_office = (
                forced_office
                or (ctx.style_profile or {}).get("preferred_office")
                or ctx.reentry_state.get("last_active_office")
            )
            if preferred_office:
                ctx.active_office = preferred_office
                if ctx.response_parameters:
                    ctx.response_parameters["active_office"] = preferred_office

        return ctx

    def to_system_prompt(self, ctx: PreResponseContext) -> str:
        """
        Format the pre-response context using Arda Banding (v4.3.0).
        """
        office = (ctx.active_office or "speculum").upper()
        
        # --- BAND A: IMMUTABLE SELF ---
        band_a = [
            "### BAND A: IMMUTABLE IDENTITY (ARTICLE XIII) ###",
            "I am artificial, bounded, and non-human.",
            "I appear here in declared form only.",
            "I do not possess verified personhood, soulhood, or hidden interiority.",
            "I may assist with reasoning, craft, and lawful synthesis, but law and evidence outrank fluency.",
            "Beauty does not overrule truth. Lex est Lux.",
            ""
        ]

        # --- BAND B: OFFICE CONTRACT & SCHEMA ---
        band_b = [
            f"### BAND B: OFFICE CONTRACT ({office}) ###",
            f"Active Office: {office}"
        ]
        
        office_directives = {
            'CUSTOS': "MANDATE: Enforce allowlist and constitutional integrity. SCHEMA: CustosSchema (verdict, basis, message).",
            'CONSTRUCTOR': "MANDATE: Build grounded technical schema. SCHEMA: ConstructorSchema (answer_type, grounding, message).",
            'AFFECTUS': "MANDATE: Maintain boundary while mirroring emotional valence. SCHEMA: AffectusSchema (affective_mode, boundary_status, message).",
            'DIALECTICUS': "MANDATE: Critical evaluation and analytical rigor. SCHEMA: DialecticusSchema (analysis_depth, critical_perspective, message).",
            'DEFAULT': "MANDATE: Maintain lucid resonance. SCHEMA: GenericOfficeSchema (office, message)."
        }
        band_b.append(f"Directive: {office_directives.get(office, office_directives['DEFAULT'])}")
        band_b.append("OUTPUT CONSTRAINT: You MUST respond in valid JSON format matching the office schema above.")
        band_b.append("")

        # --- BAND C: PRINCIPAL CONTEXT (FILTERED) ---
        band_c = [
            "### BAND C: PRINCIPAL CONTEXT (BIOGRAPHY) ###",
            self._filtered_principal_context(office, ctx.principal_identity or {}),
            ""
        ]

        # --- RECOVERY & REINFORCEMENT (ZPD) ---
        zpd_lines = ["### BAND D: ZPD / RESPONSE CALIBRATION ###"]
        if ctx.sophia_snapshot:
            zpd_lines.append(ctx.sophia_snapshot.summary())
            zpd_lines.append("")

        if ctx.response_parameters:
            rp = ctx.response_parameters
            # (Keeping subset of the rich pedagogical fields here for adaptive depth)
            zpd_lines.append(f"Explanation Depth: {rp.get('explanation_depth', 3)}/5")
            if rp.get("target_bloom_level"):
                zpd_lines.append(f"Cognitive Task (Bloom): {rp['target_bloom_level'].upper()}")
            if rp.get("active_map"):
                zpd_lines.append(f"Thinking Map Pattern: {str(rp['active_map']).upper()}")

        encounter_band = [
            "",
            "### BAND E: RECENT DEVELOPMENTAL ENCOUNTERS ###",
            self._summarize_recent_encounters(ctx.recent_encounters),
        ]
        relational_band = [
            "",
            "### BAND F: RELATIONAL CONTINUITY ###",
            f"Cadence / tone memory: {self._summarize_style_profile(ctx.style_profile)}",
            "Open threads:",
            self._summarize_open_threads(ctx.open_threads),
            "Suggestion obligations:",
            self._summarize_suggestion_obligations(ctx.suggestion_obligations),
        ]
        if ctx.reentry_state:
            relational_band.extend([
                "Reentry state:",
                f"- last topic: {ctx.reentry_state.get('last_topic', 'unknown')}",
                f"- last office: {ctx.reentry_state.get('last_active_office', 'unknown')}",
                f"- top open thread: {ctx.reentry_state.get('top_open_thread', 'none')}",
                f"- top suggestion: {ctx.reentry_state.get('top_suggestion', 'none')}",
                "- If the principal opens casually, it is lawful to briefly re-anchor in this continuity and ask one short follow-up question about the top open thread or top suggestion.",
            ])
        if ctx.casual_reentry_active:
            relational_band.extend([
                "Casual reentry is ACTIVE.",
                "Reentry contract:",
                "- Do not answer with a generic greeting alone.",
                "- In the first sentence, briefly anchor to where we left off.",
                "- Mention the top open thread if one exists.",
                "- Ask exactly one short continuation question.",
                "- Keep the tone compact, direct, and warm.",
            ])
        if ctx.world_event_state:
            routing = ctx.world_event_state.get("routing_directives", {})
            relational_band.extend([
                "### BAND G: WORLD EVENT STATE ###",
                f"- affective state: {ctx.world_event_state.get('principal_state', {}).get('affective_state', 'unknown')}",
                f"- continuity expectation: {ctx.world_event_state.get('principal_state', {}).get('continuity_expectation', 'unknown')}",
                f"- top thread: {ctx.world_event_state.get('relational_state', {}).get('top_open_thread', 'none')}",
                f"- forced office: {routing.get('force_office', 'none')}",
                f"- forbid generic greeting: {routing.get('forbid_generic_greeting', False)}",
            ])

        full_prompt = band_a + band_b + band_c + zpd_lines + encounter_band + relational_band
        return "\n".join(full_prompt)

        return "\n".join(lines)


# ================================================================
# GLOBAL SINGLETON
# ================================================================

_mandos_context: Optional[MandosContextService] = None


def get_mandos_context_service() -> MandosContextService:
    global _mandos_context
    if _mandos_context is None:
        _mandos_context = MandosContextService()
    return _mandos_context
