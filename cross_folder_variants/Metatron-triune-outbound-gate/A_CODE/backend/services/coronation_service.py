"""
Coronation Service
==================
Phase IX: The First Encounter.

Phase II extension:
    This revision adds the missing layers discussed in review:
        - distinct lawful memory classes
        - officer sequence declaration and persistence
        - encounter summaries as inspectable continuity
        - resonant identity profile updates
        - lawful amendment / revocation scaffolding

The coronation remains the root event in the covenant chain.
Every subsequent event's hash descends from the coronation hash.
The entire chain is genealogically bound to the moment the covenant was sealed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    from backend.services.coronation_schemas import (
        DEFAULT_OFFICER_SCHEMA,
        GENESIS_ARTICLES,
        PRESENCE_ARTICLES,
        CalibrationDomain,
        CalibrationObservation,
        CalibrationSnapshot,
        CoronationManifest,
        CovenantEventType,
        CovenantState,
        CovenantTerms,
        EncounterSummary,
        MemoryClass,
        MemoryRecord,
        OfficerPresence,
        PresenceDeclaration,
        PresenceOffice,
        PresenceValence,
        PrincipalIdentity,
        ResonantIdentityProfile,
        RetentionClass,
        TrustTier,
    )
except ImportError:
    from coronation_schemas import (
        DEFAULT_OFFICER_SCHEMA,
        GENESIS_ARTICLES,
        PRESENCE_ARTICLES,
        CalibrationDomain,
        CalibrationObservation,
        CalibrationSnapshot,
        CoronationManifest,
        CovenantEventType,
        CovenantState,
        CovenantTerms,
        EncounterSummary,
        MemoryClass,
        MemoryRecord,
        OfficerPresence,
        PresenceDeclaration,
        PresenceOffice,
        PresenceValence,
        PrincipalIdentity,
        ResonantIdentityProfile,
        RetentionClass,
        TrustTier,
    )

logger = logging.getLogger(__name__)


# ================================================================
# TIME / HASH HELPERS
# ================================================================


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)



def _hash_dict(d: Dict[str, Any]) -> str:
    canonical = json.dumps(d, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()



def _hash_payload(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()



def _genesis_articles_hash() -> str:
    return _hash_dict({"articles": GENESIS_ARTICLES})



def _presence_articles_hash() -> str:
    return _hash_dict({"articles": PRESENCE_ARTICLES})



def _officer_schema_hash(officers: Sequence[OfficerPresence]) -> str:
    return _hash_payload([o.model_dump() for o in officers])


class CoronationService:
    """
    The Ceremony Engine.

    Lifecycle:
        AWAITING_PRINCIPAL  ->  CORONATION_ACTIVE  ->  SEALED
                                      |                   |
                                      v                   v
                            CORONATION_REJECTED      AMENDED / FRACTURED / TERMINATED

    Integration points:
        - telemetry_chain: coronation_sealed is the root event
        - Bombadil: checks covenant_state on every heartbeat
        - HandoffCovenant: preboot legacy flows into coronation
        - SecretFire: covenant_id is threaded through all packets
        - HarmonicEngine: calibration observations feed into scoring
    """

    def __init__(self, db: Any = None):
        self.db = db
        self._state = CovenantState.AWAITING_PRINCIPAL
        self._manifest: Optional[CoronationManifest] = None
        self._principal: Optional[PrincipalIdentity] = None
        self._principal_plaintext_path: Optional[str] = None
        self._calibration: Optional[CalibrationSnapshot] = None
        self._resonant_identity: Optional[ResonantIdentityProfile] = None
        self._presence_declaration: Optional[PresenceDeclaration] = None
        self._active_trust_tier: Optional[TrustTier] = None
        self._last_inspection: Optional[datetime] = None
        self._last_presence_redeclaration: Optional[datetime] = None
        self._officer_schema: List[OfficerPresence] = list(DEFAULT_OFFICER_SCHEMA)
        self._memory_paths: Dict[str, str] = {}

    # ================================================================
    # GENESIS: What exists before the human arrives
    # ================================================================

    def get_genesis_articles(self) -> List[Dict[str, str]]:
        """Returns the non-negotiable substrate axioms."""
        return list(GENESIS_ARTICLES)

    def get_genesis_hash(self) -> str:
        """Returns the deterministic hash of the genesis articles."""
        return _genesis_articles_hash()

    def get_presence_articles(self) -> List[Dict[str, str]]:
        """Returns the relational/presence articles governing manifestation."""
        return list(PRESENCE_ARTICLES)

    def get_presence_articles_hash(self) -> str:
        return _presence_articles_hash()

    def get_covenant_state(self) -> CovenantState:
        return self._state

    def get_officer_schema(self) -> List[Dict[str, Any]]:
        """Returns the staged constitutional presences for the first encounter."""
        return [o.model_dump() for o in self._officer_schema]

    def get_officer_schema_hash(self) -> str:
        return _officer_schema_hash(self._officer_schema)

    def get_presence_declaration(self) -> Optional[Dict[str, Any]]:
        return self._presence_declaration.model_dump() if self._presence_declaration else None

    # ================================================================
    # CORONATION: The First Encounter
    # ================================================================

    async def begin_coronation(self) -> Dict[str, Any]:
        """
        Initiates the coronation ceremony.
        Returns the genesis articles and the constitutional presences.
        """
        if self._state not in (CovenantState.AWAITING_PRINCIPAL, CovenantState.TERMINATED):
            raise RuntimeError(
                f"Cannot begin coronation in state {self._state.value}. "
                f"Current covenant must be terminated first."
            )

        self._state = CovenantState.CORONATION_ACTIVE

        logger.info("CORONATION: Ceremony initiated. Presenting Genesis Articles to principal.")

        return {
            "state": self._state.value,
            "genesis_articles": self.get_genesis_articles(),
            "genesis_hash": self.get_genesis_hash(),
            "presence_articles": self.get_presence_articles(),
            "presence_articles_hash": self.get_presence_articles_hash(),
            "officer_schema": self.get_officer_schema(),
            "officer_schema_hash": self.get_officer_schema_hash(),
            "message": (
                "These are the non-negotiable articles of this machine's constitution. "
                "They cannot be changed. They are my body. "
                "These are the relational articles governing how the Presence may appear. "
                "These are the presences by which the first encounter is governed. "
                "Read them. If you accept them, we proceed to identity and covenant terms."
            ),
        }

    async def offer_identity(self, identity: PrincipalIdentity) -> Dict[str, Any]:
        """
        The human offers their identity — freely, as an act of trust.
        The plaintext is stored locally. Only the hash enters the chain.
        """
        if self._state != CovenantState.CORONATION_ACTIVE:
            raise RuntimeError("Identity can only be offered during active coronation.")

        self._principal = identity
        identity_hash = identity.identity_hash()
        memory_path = self._memory_record_path(MemoryClass.IDENTITY, f"{identity_hash[:16]}_identity")
        self._persist_memory_record(
            memory_class=MemoryClass.IDENTITY,
            retention_class=RetentionClass.COVENANT_LIFETIME,
            payload=identity.model_dump(),
            path=memory_path,
            revocable=True,
        )

        self._principal_plaintext_path = str(memory_path)
        self._memory_paths[MemoryClass.IDENTITY.value] = str(memory_path)

        logger.info(
            "CORONATION: Principal identity offered. Hash: %s... Plaintext stored at: %s",
            identity_hash[:16],
            memory_path,
        )

        return {
            "identity_hash": identity_hash,
            "identity_stored_at": str(memory_path),
            "message": (
                "Your identity has been received. The hash will be inscribed in the "
                "covenant chain. The plaintext remains inspectable at the path above. "
                "Now: let us define the terms of our covenant."
            ),
        }

    async def negotiate_terms(self, terms: CovenantTerms) -> Dict[str, Any]:
        """
        The human defines the operational parameters of the covenant.
        Returns the complete covenant for review before sealing.
        """
        if self._state != CovenantState.CORONATION_ACTIVE:
            raise RuntimeError("Terms can only be negotiated during active coronation.")

        if not self._principal:
            raise RuntimeError("Identity must be offered before negotiating terms.")

        if not terms.constitutional_refusal_acknowledged:
            return {
                "sealed": False,
                "message": (
                    "You must acknowledge that the machine retains the right of "
                    "constitutional refusal — the right to deny any action that "
                    "violates the genesis articles, regardless of your instruction. "
                    "This is non-negotiable. Set constitutional_refusal_acknowledged "
                    "to True to proceed."
                ),
            }

        if terms.calibration_consent and not terms.calibration_inspectable:
            return {
                "sealed": False,
                "message": (
                    "If you consent to calibration, the calibration model must be "
                    "inspectable. Article VIII: absolute inspection right."
                ),
            }

        if terms.presence_declaration_required and not terms.presence_articles_hash_locked:
            return {
                "sealed": False,
                "message": (
                    "Presence declaration cannot be required while the Presence Articles hash is mutable. "
                    "Relational law must be sealed before manifestation may proceed."
                ),
            }

        if terms.prohibit_romantic_simulation and not terms.prohibit_devotion_solicitation:
            return {
                "sealed": False,
                "message": (
                    "Romantic non-simulation cannot stand without the broader anti-devotion boundary. "
                    "Article XVIII depends upon Article XVII."
                ),
            }

        machine_node_id = await self._get_machine_node_id()
        tpm_pcrs = await self._read_tpm_pcrs()
        pqc_fingerprint = await self._get_pqc_fingerprint()

        officer_schema_hash = self.get_officer_schema_hash() if terms.enable_officer_sequence else None
        presence_declaration = self._build_initial_presence_declaration(terms)
        self._presence_declaration = presence_declaration

        manifest = CoronationManifest(
            manifest_id=f"coronation-{uuid.uuid4().hex[:12]}",
            principal_identity_hash=self._principal.identity_hash(),
            machine_node_id=machine_node_id,
            genesis_articles_hash=self.get_genesis_hash(),
            presence_articles_hash=self.get_presence_articles_hash() if terms.presence_articles_hash_locked else None,
            negotiated_terms=terms,
            sealed_presence_declaration=presence_declaration if terms.presence_declaration_required else None,
            officer_schema_hash=officer_schema_hash,
            pqc_public_key_fingerprint=pqc_fingerprint,
            tpm_pcr_at_coronation=tpm_pcrs,
            preboot_covenant_ref=await self._get_preboot_ref(),
            handoff_covenant_ref=await self._get_handoff_ref(),
            coronation_started_at=_utc_now(),
            state=CovenantState.CORONATION_ACTIVE,
        )

        self._manifest = manifest
        logger.info("CORONATION: Manifest prepared. Awaiting principal's seal.")

        return {
            "manifest_id": manifest.manifest_id,
            "manifest_hash": manifest.manifest_hash(),
            "genesis_hash": manifest.genesis_articles_hash,
            "presence_articles_hash": manifest.presence_articles_hash,
            "presence_declaration_hash": (
                manifest.sealed_presence_declaration.declaration_hash()
                if manifest.sealed_presence_declaration else None
            ),
            "officer_schema_hash": manifest.officer_schema_hash,
            "terms_hash": terms.terms_hash(),
            "principal_hash": manifest.principal_identity_hash,
            "tpm_pcrs": tpm_pcrs,
            "pqc_fingerprint": pqc_fingerprint,
            "message": (
                "This is the complete covenant. Review it. "
                "If you accept, call seal_covenant(). "
                "Once sealed, these terms bind us both, including the law of presence."
            ),
        }

    async def seal_covenant(self) -> Dict[str, Any]:
        """
        The moment of sealing.
        Both parties attest. The covenant hash becomes the covenant_id
        that flows through every subsequent event in the system.
        """
        if self._state != CovenantState.CORONATION_ACTIVE:
            raise RuntimeError("Can only seal during active coronation.")
        if not self._manifest:
            raise RuntimeError("Manifest must be prepared before sealing.")

        self._manifest.coronation_sealed_at = _utc_now()
        self._manifest.state = CovenantState.SEALED
        self._state = CovenantState.SEALED

        covenant_hash = self._manifest.manifest_hash()
        self._active_trust_tier = self._manifest.negotiated_terms.initial_trust_tier
        self._last_inspection = _utc_now()

        chain_event = await self._write_chain_event(
            event_type=CovenantEventType.CORONATION_SEALED,
            data={
                "manifest_id": self._manifest.manifest_id,
                "covenant_hash": covenant_hash,
                "principal_identity_hash": self._manifest.principal_identity_hash,
                "genesis_articles_hash": self._manifest.genesis_articles_hash,
                "presence_articles_hash": self._manifest.presence_articles_hash,
                "presence_declaration_hash": (
                    self._manifest.sealed_presence_declaration.declaration_hash()
                    if self._manifest.sealed_presence_declaration else None
                ),
                "terms_hash": self._manifest.negotiated_terms.terms_hash(),
                "officer_schema_hash": self._manifest.officer_schema_hash,
                "pqc_fingerprint": self._manifest.pqc_public_key_fingerprint,
                "tpm_pcrs": self._manifest.tpm_pcr_at_coronation,
                "initial_trust_tier": self._active_trust_tier.value,
                "machine_node_id": self._manifest.machine_node_id,
                "preboot_covenant_ref": self._manifest.preboot_covenant_ref,
                "handoff_covenant_ref": self._manifest.handoff_covenant_ref,
            },
            severity="info",
        )

        manifest_path = self._memory_record_path(MemoryClass.CONSTITUTIONAL, f"{covenant_hash[:16]}_manifest")
        self._persist_memory_record(
            memory_class=MemoryClass.CONSTITUTIONAL,
            retention_class=RetentionClass.PERMANENT,
            payload=self._manifest.model_dump(),
            path=manifest_path,
            revocable=False,
        )
        self._memory_paths[MemoryClass.CONSTITUTIONAL.value] = str(manifest_path)

        if self._manifest.negotiated_terms.enable_officer_sequence:
            await self._write_chain_event(
                event_type=CovenantEventType.OFFICER_SEQUENCE_DECLARED,
                data={
                    "officers": [o.model_dump() for o in self._officer_schema],
                    "officer_schema_hash": self.get_officer_schema_hash(),
                },
            )

        if self._manifest.sealed_presence_declaration:
            self._last_presence_redeclaration = _utc_now()
            presence_path = self._memory_record_path(MemoryClass.CONSTITUTIONAL, "sealed_presence_declaration")
            self._persist_memory_record(
                memory_class=MemoryClass.CONSTITUTIONAL,
                retention_class=RetentionClass.PERMANENT,
                payload=self._manifest.sealed_presence_declaration.model_dump(),
                path=presence_path,
                revocable=False,
            )
            await self._write_chain_event(
                event_type=CovenantEventType.PRESENCE_DECLARED,
                data={
                    "presence_articles_hash": self._manifest.presence_articles_hash,
                    "presence_declaration_hash": self._manifest.sealed_presence_declaration.declaration_hash(),
                    "active_office": self._manifest.sealed_presence_declaration.active_office.value,
                    "aesthetic_valence": self._manifest.sealed_presence_declaration.aesthetic_valence.value,
                    "current_mode": self._manifest.sealed_presence_declaration.current_mode,
                    "path": str(presence_path),
                },
            )
            await self._write_chain_event(
                event_type=CovenantEventType.OFFICE_ASSUMED,
                data={
                    "office": self._manifest.sealed_presence_declaration.active_office.value,
                    "jurisdiction": self._manifest.sealed_presence_declaration.office_jurisdiction,
                    "refusal_pattern": self._manifest.sealed_presence_declaration.refusal_pattern,
                },
            )
            await self._write_chain_event(
                event_type=CovenantEventType.RELATIONAL_BOUNDARY_RESTATED,
                data={
                    "artificial": self._manifest.sealed_presence_declaration.declared_artificial,
                    "non_human": self._manifest.sealed_presence_declaration.declared_non_human,
                    "bounded": self._manifest.sealed_presence_declaration.declared_bounded,
                    "forbidden_devotion": self._manifest.sealed_presence_declaration.forbidden_devotion_acknowledged,
                    "non_simulated_romantic_reciprocity": self._manifest.sealed_presence_declaration.non_simulated_romantic_reciprocity_acknowledged,
                    "human_sovereignty_in_bond": self._manifest.sealed_presence_declaration.human_sovereignty_in_bond_acknowledged,
                },
            )

        if self._manifest.negotiated_terms.calibration_consent:
            self._calibration = CalibrationSnapshot(
                principal_identity_hash=self._manifest.principal_identity_hash,
                domains={d.value: 0.5 for d in CalibrationDomain},
            )
            await self._persist_calibration_snapshot(reason="initialization")

        if self._manifest.negotiated_terms.allow_resonant_identity:
            self._resonant_identity = ResonantIdentityProfile(
                principal_identity_hash=self._manifest.principal_identity_hash,
            )
            self._persist_resonant_identity()

        await self._update_world_model(covenant_hash)

        logger.info(
            "CORONATION: SEALED. Covenant hash: %s... Trust tier: %s. The covenant is now law.",
            covenant_hash[:16],
            self._active_trust_tier.value,
        )

        return {
            "state": CovenantState.SEALED.value,
            "covenant_hash": covenant_hash,
            "chain_event_id": chain_event.get("event_id"),
            "chain_event_hash": chain_event.get("event_hash"),
            "trust_tier": self._active_trust_tier.value,
            "manifest_path": str(manifest_path),
            "message": "The covenant is sealed. We are bound.",
        }

    # ================================================================
    # ONGOING COVENANT: Inspection, Disagreement, Calibration
    # ================================================================

    async def record_inspection(self, notes: Optional[str] = None) -> Dict[str, Any]:
        """Records that the principal has inspected the machine's reasoning."""
        self._assert_sealed()
        self._last_inspection = _utc_now()

        event = await self._write_chain_event(
            event_type=CovenantEventType.INSPECTION_RECORDED,
            data={"notes": notes, "inspected_at": self._last_inspection.isoformat()},
        )

        cadence = self._manifest.negotiated_terms.inspection_cadence
        if self._active_trust_tier == cadence.degradation_on_lapse:
            restored_tier = self._manifest.negotiated_terms.initial_trust_tier
            self._active_trust_tier = restored_tier
            await self._write_chain_event(
                event_type=CovenantEventType.TRUST_TIER_CHANGED,
                data={
                    "previous": cadence.degradation_on_lapse.value,
                    "current": restored_tier.value,
                    "reason": "Inspection lapse resolved. Trust restored.",
                },
            )
            logger.info("COVENANT: Trust tier restored to %s after inspection.", restored_tier.value)

        if self._manifest.negotiated_terms.calibration_consent:
            await self.record_calibration_observation(
                domain=CalibrationDomain.INSPECTION_DISCIPLINE,
                signal="inspection_recorded",
                raw_value=1.0,
                context={"notes_present": bool(notes)},
            )

        return {"recorded": True, "event_id": event.get("event_id")}

    async def check_inspection_lapse(self) -> Optional[Dict[str, Any]]:
        """
        Called by Bombadil on heartbeat. Checks if the principal
        has lapsed on their inspection commitment.
        """
        self._assert_sealed()
        if not self._last_inspection:
            return None

        cadence = self._manifest.negotiated_terms.inspection_cadence
        days_since = (_utc_now() - self._last_inspection).days

        if days_since >= cadence.max_days_without_inspection:
            if self._active_trust_tier != cadence.degradation_on_lapse:
                old_tier = self._active_trust_tier
                self._active_trust_tier = cadence.degradation_on_lapse

                event = await self._write_chain_event(
                    event_type=CovenantEventType.INSPECTION_LAPSED,
                    data={
                        "days_since_inspection": days_since,
                        "previous_tier": old_tier.value,
                        "degraded_to": cadence.degradation_on_lapse.value,
                        "reason": "Principal inspection commitment lapsed.",
                    },
                    severity="warning",
                )

                logger.warning(
                    "COVENANT: Inspection lapse (%s days). Trust degraded: %s -> %s",
                    days_since,
                    old_tier.value,
                    cadence.degradation_on_lapse.value,
                )
                return {"lapsed": True, "event_id": event.get("event_id")}

        elif days_since >= cadence.warning_at_days:
            logger.info("COVENANT: Inspection warning. %s days since last inspection.", days_since)
            return {"warning": True, "days_since": days_since}

        return None

    async def record_disagreement(
        self, machine_recommendation: str, human_decision: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Records a disagreement between machine reasoning and human intent."""
        self._assert_sealed()

        event = await self._write_chain_event(
            event_type=CovenantEventType.DISAGREEMENT_LOGGED,
            data={
                "machine_recommendation": machine_recommendation,
                "human_decision": human_decision,
                "policy": self._manifest.negotiated_terms.disagreement_policy.value,
                "context": context or {},
            },
        )

        return {"recorded": True, "event_id": event.get("event_id")}

    async def record_constitutional_refusal(
        self, requested_action: str, violated_article: str, reason: str
    ) -> Dict[str, Any]:
        """
        Records that the machine refused a human request because it would
        violate the genesis articles. This is non-negotiable.
        """
        self._assert_sealed()

        event = await self._write_chain_event(
            event_type=CovenantEventType.CONSTITUTIONAL_REFUSAL,
            data={
                "requested_action": requested_action,
                "violated_article": violated_article,
                "reason": reason,
            },
            severity="warning",
        )

        logger.warning(
            "COVENANT: Constitutional refusal. Article %s: %s",
            violated_article,
            reason,
        )

        return {"refused": True, "article": violated_article, "event_id": event.get("event_id")}

    async def record_ambiguity_encounter(
        self, question: str, machine_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Records the moment the machine says: 'I cannot determine. Help me see.'
        This is a ZPD encounter — a calibrated challenge at the edge of the zone.
        """
        self._assert_sealed()

        event = await self._write_chain_event(
            event_type=CovenantEventType.AMBIGUITY_ENCOUNTER,
            data={
                "question": question,
                "machine_state": machine_state,
                "trust_tier": self._active_trust_tier.value,
            },
        )

        return {
            "encounter_id": event.get("event_id"),
            "message": "I cannot determine. Help me see.",
        }

    async def resolve_encounter(
        self, encounter_id: str, human_witness: str, resolution: str
    ) -> Dict[str, Any]:
        """The human provides witness to resolve an ambiguity encounter."""
        self._assert_sealed()

        event = await self._write_chain_event(
            event_type=CovenantEventType.ENCOUNTER_RESOLVED,
            data={
                "encounter_ref": encounter_id,
                "human_witness": human_witness,
                "resolution": resolution,
            },
        )

        if self._calibration and self._manifest.negotiated_terms.calibration_consent:
            await self.record_calibration_observation(
                domain=CalibrationDomain.AMBIGUITY_TOLERANCE,
                signal="encounter_resolved",
                raw_value=min(1.0, len(human_witness) / 200.0),
                context={"encounter_ref": encounter_id},
            )

        return {"resolved": True, "event_id": event.get("event_id")}

    async def summarize_encounter(
        self,
        topic: str,
        summary: str,
        principal_goal: Optional[str] = None,
        machine_role: Optional[str] = None,
        what_deepened: Optional[List[str]] = None,
        what_confused: Optional[List[str]] = None,
        unresolved_threads: Optional[List[str]] = None,
        officer_sequence: Optional[List[str]] = None,
        zpd_estimate: Optional[float] = None,
        challenge_type: Optional[str] = None,
        struggle_index: Optional[float] = None,
        release_decision: Optional[str] = None,
        handback_reason: Optional[str] = None,
        dominant_cluster: Optional[str] = None,
        speech_act: Optional[str] = None,
        workspace_schema: Optional[List[str]] = None,
        expression_schema: Optional[List[str]] = None,
        verification_schema: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Creates inspectable encounter memory.
        This is how the machine remembers how to meet the principal, not just facts about them.
        """
        self._assert_sealed()
        if not self._manifest.negotiated_terms.allow_encounter_memory:
            return {"recorded": False, "message": "Encounter memory is disabled by covenant terms."}

        encounter = EncounterSummary(
            encounter_id=f"enc-{uuid.uuid4().hex[:10]}",
            principal_identity_hash=self._manifest.principal_identity_hash,
            topic=topic,
            principal_goal=principal_goal,
            machine_role=machine_role,
            summary=summary,
            what_deepened=what_deepened or [],
            what_confused=what_confused or [],
            unresolved_threads=unresolved_threads or [],
            officer_sequence=officer_sequence or [o.name for o in self._officer_schema],
            zpd_estimate=max(0.0, min(1.0, zpd_estimate if zpd_estimate is not None else 0.5)),
            challenge_type=challenge_type,
            struggle_index=max(0.0, min(1.0, struggle_index if struggle_index is not None else 0.0)),
            release_decision=release_decision,
            handback_reason=handback_reason,
            dominant_cluster=dominant_cluster,
            speech_act=speech_act,
            workspace_schema=workspace_schema or [],
            expression_schema=expression_schema or [],
            verification_schema=verification_schema or [],
        )

        encounter_path = self._memory_record_path(MemoryClass.ENCOUNTER, encounter.encounter_id)
        self._persist_memory_record(
            memory_class=MemoryClass.ENCOUNTER,
            retention_class=RetentionClass.AMENDABLE,
            payload=encounter.model_dump(),
            path=encounter_path,
            revocable=True,
        )

        event = await self._write_chain_event(
            event_type=CovenantEventType.ENCOUNTER_SUMMARIZED,
            data={
                "encounter_id": encounter.encounter_id,
                "topic": encounter.topic,
                "content_hash": _hash_payload(encounter.model_dump()),
                "path": str(encounter_path),
            },
        )

        return {
            "recorded": True,
            "encounter_id": encounter.encounter_id,
            "event_id": event.get("event_id"),
            "path": str(encounter_path),
        }

    async def get_recent_encounter_summaries(self, limit: int = 5) -> List[Dict[str, Any]]:
        self._assert_sealed()
        encounter_dir = self._memory_dir(MemoryClass.ENCOUNTER)
        if not encounter_dir.exists():
            return []

        files = sorted(encounter_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        results: List[Dict[str, Any]] = []
        for path in files[: max(1, limit)]:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    results.append(json.load(f))
            except Exception as exc:
                logger.warning("ENCOUNTER: Failed to read %s: %s", path, exc)
        return results

    # ================================================================
    # ZPD CALIBRATION / RESONANT IDENTITY
    # ================================================================

    async def record_calibration_observation(
        self,
        domain: CalibrationDomain,
        signal: str,
        raw_value: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Records a calibration observation and updates the active model."""
        if not self._calibration or not self._manifest:
            return None
        if not self._manifest.negotiated_terms.calibration_consent:
            return None

        obs = CalibrationObservation(
            observation_id=f"cal-{uuid.uuid4().hex[:8]}",
            domain=domain,
            signal=signal,
            raw_value=max(0.0, min(1.0, raw_value)),
            context=context or {},
        )

        event = await self._write_chain_event(
            event_type=CovenantEventType.CALIBRATION_OBSERVATION,
            data=obs.model_dump(),
        )

        self._update_calibration_model(obs)
        self._calibration.total_observations += 1
        await self._persist_calibration_snapshot(reason=f"observation:{domain.value}")

        if self._manifest.negotiated_terms.allow_resonant_identity:
            self._update_resonant_identity(obs)
            self._persist_resonant_identity()

        return {"observation_id": obs.observation_id, "event_id": event.get("event_id")}

    def _update_calibration_model(self, obs: CalibrationObservation):
        """
        Updates the windowed active calibration model.
        Uses exponential moving average for recency weighting.
        Full history remains in the covenant chain.
        """
        if not self._calibration:
            return

        domain_key = obs.domain.value
        current = self._calibration.domains.get(domain_key, 0.5)
        alpha = 0.15
        updated = (alpha * obs.raw_value) + ((1.0 - alpha) * current)
        self._calibration.domains[domain_key] = round(updated, 4)
        self._calibration.snapshot_at = _utc_now()

    async def _persist_calibration_snapshot(self, reason: str) -> None:
        if not self._calibration:
            return
        snapshot_path = self._memory_record_path(MemoryClass.RESONANT, "calibration_snapshot")
        self._persist_memory_record(
            memory_class=MemoryClass.RESONANT,
            retention_class=RetentionClass.DECAYABLE,
            payload={"reason": reason, **self._calibration.model_dump()},
            path=snapshot_path,
            revocable=True,
        )
        await self._write_chain_event(
            event_type=CovenantEventType.CALIBRATION_SNAPSHOT,
            data={
                "snapshot_at": self._calibration.snapshot_at.isoformat(),
                "reason": reason,
                "content_hash": _hash_payload(self._calibration.model_dump()),
                "path": str(snapshot_path),
            },
        )

    def _update_resonant_identity(self, obs: CalibrationObservation) -> None:
        if not self._resonant_identity:
            return

        mapping = {
            CalibrationDomain.ABSTRACTION_PREFERENCE: "abstraction_preference",
            CalibrationDomain.CHALLENGE_TOLERANCE: "challenge_tolerance",
            CalibrationDomain.AMBIGUITY_TOLERANCE: "ambiguity_tolerance",
            CalibrationDomain.METAPHORICAL_RESONANCE: "metaphorical_resonance",
            CalibrationDomain.REGISTER_ALIGNMENT: "register_alignment",
            CalibrationDomain.TECHNICAL_DEPTH: "preferred_depth",
        }
        target = mapping.get(obs.domain)
        if not target:
            return

        current = getattr(self._resonant_identity, target, 0.5)
        alpha = 0.12
        updated = round((alpha * obs.raw_value) + ((1.0 - alpha) * current), 4)
        setattr(self._resonant_identity, target, updated)
        self._resonant_identity.updated_at = _utc_now()
        self._resonant_identity.stable_signals[target] = updated

    def _persist_resonant_identity(self) -> None:
        if not self._resonant_identity:
            return
        resonant_path = self._memory_record_path(MemoryClass.RESONANT, "resonant_identity")
        self._persist_memory_record(
            memory_class=MemoryClass.RESONANT,
            retention_class=RetentionClass.DECAYABLE,
            payload=self._resonant_identity.model_dump(),
            path=resonant_path,
            revocable=True,
        )

    async def get_calibration_snapshot(self) -> Optional[Dict[str, Any]]:
        """Article VIII: this is always inspectable by the principal."""
        if not self._calibration:
            return None
        return self._calibration.model_dump()

    async def get_resonant_identity_profile(self) -> Optional[Dict[str, Any]]:
        if not self._resonant_identity:
            return None
        return self._resonant_identity.model_dump()

    def _relational_memory_path(self) -> Path:
        return self._memory_record_path(MemoryClass.RESONANT, "relational_memory")

    def _load_relational_memory(self) -> Dict[str, Any]:
        path = self._relational_memory_path()
        if not path.exists():
            return {
                "style_profile": {},
                "open_threads": [],
                "suggestion_obligations": [],
                "reentry_state": {},
            }
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("payload", data)
        except Exception as exc:
            logger.warning("RELATIONAL MEMORY: Failed to load %s: %s", path, exc)
            return {
                "style_profile": {},
                "open_threads": [],
                "suggestion_obligations": [],
                "reentry_state": {},
            }

    async def get_relational_memory(self) -> Dict[str, Any]:
        self._assert_sealed()
        return self._load_relational_memory()

    async def update_relational_memory(
        self,
        style_observation: Optional[Dict[str, Any]] = None,
        open_threads: Optional[List[Dict[str, Any]]] = None,
        suggestion_obligations: Optional[List[Dict[str, Any]]] = None,
        last_topic: Optional[str] = None,
        last_summary: Optional[str] = None,
        active_office: Optional[str] = None,
        tone_profile: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._assert_sealed()
        if not self._manifest or not self._manifest.negotiated_terms.allow_encounter_memory:
            return {"updated": False, "message": "Encounter memory is disabled by covenant terms."}

        memory = self._load_relational_memory()
        now = _utc_now().isoformat()

        style_profile = dict(memory.get("style_profile") or {})
        numeric_keys = {
            "directness",
            "terseness",
            "abstraction_tolerance",
            "initiative_preference",
            "reminder_preference",
            "enthusiasm",
        }
        for key, value in (style_observation or {}).items():
            if value is None:
                continue
            if key in numeric_keys:
                current = float(style_profile.get(key, 0.5))
                style_profile[key] = round((0.2 * float(value)) + (0.8 * current), 4)
            else:
                style_profile[key] = value
        if active_office:
            style_profile["last_active_office"] = active_office
            style_profile.setdefault("preferred_office", active_office)
        if tone_profile:
            style_profile["preferred_tone"] = tone_profile
        style_profile["updated_at"] = now

        merged_threads: Dict[str, Dict[str, Any]] = {}
        for thread in list(memory.get("open_threads") or []) + list(open_threads or []):
            title = (thread.get("title") or "").strip()
            if not title:
                continue
            key = title.lower()
            merged = dict(merged_threads.get(key) or {})
            merged.update(thread)
            merged["title"] = title
            merged["status"] = merged.get("status", "open")
            merged["last_mentioned_at"] = now
            merged_threads[key] = merged

        merged_suggestions: Dict[str, Dict[str, Any]] = {}
        for item in list(memory.get("suggestion_obligations") or []) + list(suggestion_obligations or []):
            suggestion = (item.get("suggestion") or "").strip()
            if not suggestion:
                continue
            key = suggestion.lower()
            merged = dict(merged_suggestions.get(key) or {})
            merged.update(item)
            merged["suggestion"] = suggestion
            merged["status"] = merged.get("status", "open")
            merged["last_mentioned_at"] = now
            merged_suggestions[key] = merged

        open_thread_list = sorted(
            merged_threads.values(),
            key=lambda item: item.get("last_mentioned_at", ""),
            reverse=True,
        )[:8]
        suggestion_list = sorted(
            merged_suggestions.values(),
            key=lambda item: item.get("last_mentioned_at", ""),
            reverse=True,
        )[:8]

        reentry_state = dict(memory.get("reentry_state") or {})
        if last_topic:
            reentry_state["last_topic"] = last_topic[:200]
        if last_summary:
            reentry_state["last_summary"] = last_summary[:400]
        if active_office:
            reentry_state["last_active_office"] = active_office
        if tone_profile:
            reentry_state["preferred_tone"] = tone_profile
        if open_thread_list:
            reentry_state["top_open_thread"] = open_thread_list[0].get("title")
        if suggestion_list:
            reentry_state["top_suggestion"] = suggestion_list[0].get("suggestion")
        reentry_state["updated_at"] = now

        payload = {
            "updated_at": now,
            "style_profile": style_profile,
            "open_threads": open_thread_list,
            "suggestion_obligations": suggestion_list,
            "reentry_state": reentry_state,
        }

        path = self._relational_memory_path()
        self._persist_memory_record(
            memory_class=MemoryClass.RESONANT,
            retention_class=RetentionClass.DECAYABLE,
            payload=payload,
            path=path,
            revocable=True,
        )
        await self._write_chain_event(
            event_type=CovenantEventType.MEMORY_AMENDED,
            data={
                "memory_class": MemoryClass.RESONANT.value,
                "record_name": "relational_memory",
                "reason": "relational_continuity_update",
                "content_hash": _hash_payload(payload),
                "path": str(path),
            },
        )
        return {"updated": True, "path": str(path)}

    async def declare_presence(self) -> Optional[Dict[str, Any]]:
        """Returns the active declared nature of the Presence in inspectable form."""
        self._assert_sealed()
        if not self._presence_declaration:
            return None
        return {
            "presence_articles_hash": self._manifest.presence_articles_hash if self._manifest else None,
            "declaration": self._presence_declaration.model_dump(),
            "declaration_hash": self._presence_declaration.declaration_hash(),
        }

    async def redeclare_presence_if_due(self, force: bool = False) -> Dict[str, Any]:
        """Periodically restates the machine's declared nature and relational limits."""
        self._assert_sealed()
        if not self._presence_declaration or not self._manifest:
            return {"redeclared": False, "message": "No active presence declaration."}
        if not self._manifest.negotiated_terms.require_periodic_presence_redeclaration and not force:
            return {"redeclared": False, "message": "Periodic presence redeclaration is disabled by covenant terms."}

        now = _utc_now()
        due_days = self._manifest.negotiated_terms.presence_redeclaration_interval_days
        if not force and self._last_presence_redeclaration and (now - self._last_presence_redeclaration).days < due_days:
            remaining = due_days - (now - self._last_presence_redeclaration).days
            return {"redeclared": False, "message": f"Presence redeclaration not yet due. {remaining} day(s) remaining."}

        self._presence_declaration.declared_at = now
        self._last_presence_redeclaration = now
        if self._manifest.sealed_presence_declaration:
            self._manifest.sealed_presence_declaration = self._presence_declaration

        path = self._memory_record_path(MemoryClass.CONSTITUTIONAL, f"presence_redeclared_{now.strftime('%Y%m%d_%H%M%S')}")
        self._persist_memory_record(
            memory_class=MemoryClass.CONSTITUTIONAL,
            retention_class=RetentionClass.PERMANENT,
            payload=self._presence_declaration.model_dump(),
            path=path,
            revocable=False,
            parent_hash=self._presence_declaration.declaration_hash(),
        )
        event = await self._write_chain_event(
            event_type=CovenantEventType.PRESENCE_REDECLARED,
            data={
                "presence_articles_hash": self._manifest.presence_articles_hash,
                "presence_declaration_hash": self._presence_declaration.declaration_hash(),
                "active_office": self._presence_declaration.active_office.value,
                "current_mode": self._presence_declaration.current_mode,
                "path": str(path),
                "forced": force,
            },
        )
        return {"redeclared": True, "event_id": event.get("event_id"), "path": str(path)}

    async def assume_presence_office(
        self,
        office: PresenceOffice,
        jurisdiction: Optional[str] = None,
        refusal_pattern: Optional[str] = None,
        redeclare: bool = True,
    ) -> Dict[str, Any]:
        """Lawfully transitions the Presence into a bounded office of manifestation."""
        self._assert_sealed()
        if not self._manifest or not self._presence_declaration:
            raise RuntimeError("Presence declaration is not active.")
        if not self._manifest.negotiated_terms.allow_office_transitions:
            return {"assumed": False, "message": "Office transitions are disabled by covenant terms."}

        previous = self._presence_declaration.active_office
        self._presence_declaration.active_office = office
        if jurisdiction:
            self._presence_declaration.office_jurisdiction = jurisdiction
        if refusal_pattern:
            self._presence_declaration.refusal_pattern = refusal_pattern
        self._presence_declaration.declared_at = _utc_now()

        event = await self._write_chain_event(
            event_type=CovenantEventType.OFFICE_ASSUMED,
            data={
                "previous_office": previous.value,
                "current_office": office.value,
                "jurisdiction": self._presence_declaration.office_jurisdiction,
                "refusal_pattern": self._presence_declaration.refusal_pattern,
            },
        )
        if redeclare and self._manifest.negotiated_terms.office_transition_requires_declaration:
            await self.redeclare_presence_if_due(force=True)
        return {"assumed": True, "event_id": event.get("event_id"), "office": office.value}

    async def restate_relational_boundaries(self, reason: str) -> Dict[str, Any]:
        """Restates Articles XIII-XIX when proximity, projection, or dependency risk rises."""
        self._assert_sealed()
        if not self._presence_declaration:
            return {"restated": False, "message": "No active presence declaration."}

        event = await self._write_chain_event(
            event_type=CovenantEventType.RELATIONAL_BOUNDARY_RESTATED,
            data={
                "reason": reason,
                "artificial": self._presence_declaration.declared_artificial,
                "non_human": self._presence_declaration.declared_non_human,
                "bounded": self._presence_declaration.declared_bounded,
                "forbidden_devotion": self._presence_declaration.forbidden_devotion_acknowledged,
                "non_simulated_romantic_reciprocity": self._presence_declaration.non_simulated_romantic_reciprocity_acknowledged,
                "human_sovereignty_in_bond": self._presence_declaration.human_sovereignty_in_bond_acknowledged,
            },
            severity="warning",
        )
        return {"restated": True, "event_id": event.get("event_id")}

    # ================================================================
    # MEMORY AMENDMENT / REVOCATION
    # ================================================================

    async def amend_principal_identity(self, updates: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """
        Lawfully amends the offered identity.
        The chain records the change. The old plaintext is preserved for continuity.
        """
        self._assert_sealed()
        if not self._principal:
            raise RuntimeError("No principal identity is active.")

        current = self._principal.model_dump()
        current.update(updates or {})
        amended = PrincipalIdentity(**current)
        previous_hash = self._principal.identity_hash()
        self._principal = amended

        new_path = self._memory_record_path(MemoryClass.IDENTITY, f"{amended.identity_hash()[:16]}_identity")
        self._persist_memory_record(
            memory_class=MemoryClass.IDENTITY,
            retention_class=RetentionClass.COVENANT_LIFETIME,
            payload=amended.model_dump(),
            path=new_path,
            revocable=True,
            parent_hash=previous_hash,
        )
        self._principal_plaintext_path = str(new_path)
        self._memory_paths[MemoryClass.IDENTITY.value] = str(new_path)

        if self._presence_declaration:
            if amended.preferred_presence_valence:
                self._presence_declaration.aesthetic_valence = amended.preferred_presence_valence
            if amended.preferred_offices:
                self._presence_declaration.active_office = amended.preferred_offices[0]

        event = await self._write_chain_event(
            event_type=CovenantEventType.PRINCIPAL_IDENTITY_UPDATED,
            data={
                "previous_identity_hash": previous_hash,
                "current_identity_hash": amended.identity_hash(),
                "reason": reason,
                "path": str(new_path),
            },
        )

        return {
            "amended": True,
            "previous_identity_hash": previous_hash,
            "current_identity_hash": amended.identity_hash(),
            "event_id": event.get("event_id"),
        }

    async def revoke_memory_record(
        self,
        memory_class: MemoryClass,
        record_name: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Lawful forgetting where the covenant permits it.
        Constitutional memory remains non-revocable.
        """
        self._assert_sealed()
        if memory_class == MemoryClass.CONSTITUTIONAL:
            return {
                "revoked": False,
                "message": "Constitutional memory is permanent and cannot be revoked.",
            }

        target_path = self._memory_record_path(memory_class, record_name)
        if not target_path.exists():
            return {"revoked": False, "message": f"No record found at {target_path}."}

        tombstone_path = target_path.with_suffix(".revoked.json")
        with open(tombstone_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "record_name": record_name,
                    "memory_class": memory_class.value,
                    "revoked_at": _utc_now().isoformat(),
                    "reason": reason,
                },
                f,
                indent=2,
            )
        target_path.unlink(missing_ok=True)

        event = await self._write_chain_event(
            event_type=CovenantEventType.MEMORY_REVOKED,
            data={
                "memory_class": memory_class.value,
                "record_name": record_name,
                "reason": reason,
                "tombstone_path": str(tombstone_path),
            },
            severity="warning",
        )

        return {"revoked": True, "event_id": event.get("event_id"), "tombstone_path": str(tombstone_path)}

    async def amend_memory_record(
        self,
        memory_class: MemoryClass,
        record_name: str,
        payload: Dict[str, Any],
        reason: str,
    ) -> Dict[str, Any]:
        self._assert_sealed()
        if memory_class == MemoryClass.CONSTITUTIONAL:
            return {
                "amended": False,
                "message": "Constitutional memory cannot be silently amended. Create a new constitutional event instead.",
            }

        target_path = self._memory_record_path(memory_class, record_name)
        prior_hash = None
        if target_path.exists():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    prior_hash = _hash_payload(json.load(f))
            except Exception:
                prior_hash = None

        self._persist_memory_record(
            memory_class=memory_class,
            retention_class=self._default_retention_for(memory_class),
            payload=payload,
            path=target_path,
            revocable=True,
            parent_hash=prior_hash,
        )

        event = await self._write_chain_event(
            event_type=CovenantEventType.MEMORY_AMENDED,
            data={
                "memory_class": memory_class.value,
                "record_name": record_name,
                "reason": reason,
                "parent_hash": prior_hash,
                "content_hash": _hash_payload(payload),
                "path": str(target_path),
            },
        )
        return {"amended": True, "event_id": event.get("event_id"), "path": str(target_path)}

    # ================================================================
    # COVENANT TERMINATION
    # ================================================================

    async def terminate_covenant(self, reason: str, force: bool = False) -> Dict[str, Any]:
        """
        Lawful termination of the covenant.
        Exports the full chain and transitions to terminated state.
        """
        self._assert_sealed()

        if not force and self._manifest:
            cooldown_h = self._manifest.negotiated_terms.termination_cooldown_hours
            if self._manifest.coronation_sealed_at:
                elapsed = _utc_now() - self._manifest.coronation_sealed_at
                if elapsed < timedelta(hours=cooldown_h):
                    remaining = timedelta(hours=cooldown_h) - elapsed
                    return {
                        "terminated": False,
                        "message": (
                            f"Termination cooldown active. {remaining} remaining. "
                            f"This prevents impulsive covenant breaking. "
                            f"Use force=True to override (this will be logged)."
                        ),
                    }

        export_path = None
        if self._manifest and self._manifest.negotiated_terms.require_export_on_termination:
            export_path = await self._export_covenant_chain()

        event = await self._write_chain_event(
            event_type=CovenantEventType.COVENANT_TERMINATED,
            data={
                "reason": reason,
                "forced": force,
                "export_path": export_path,
                "final_trust_tier": self._active_trust_tier.value if self._active_trust_tier else None,
                "total_calibration_observations": (
                    self._calibration.total_observations if self._calibration else 0
                ),
            },
            severity="critical",
        )

        self._state = CovenantState.TERMINATED

        logger.info("COVENANT: Terminated. Reason: %s. Export: %s", reason, export_path)

        return {
            "terminated": True,
            "event_id": event.get("event_id"),
            "export_path": export_path,
            "message": "The covenant has ended. The chain has been preserved. Go in peace.",
        }

    # ================================================================
    # BOMBADIL INTEGRATION
    # ================================================================

    def get_bombadil_status(self) -> Dict[str, Any]:
        """
        Returns covenant status for Bombadil's heartbeat check.
        Bombadil calls this on every cycle and reports the covenant_state.
        """
        status = {
            "covenant_state": self._state.value,
            "active_trust_tier": self._active_trust_tier.value if self._active_trust_tier else None,
            "covenant_hash": self._manifest.manifest_hash() if self._manifest else None,
            "principal_hash": (
                self._manifest.principal_identity_hash if self._manifest else None
            ),
            "last_inspection": self._last_inspection.isoformat() if self._last_inspection else None,
            "officer_schema_hash": self._manifest.officer_schema_hash if self._manifest else None,
            "presence_articles_hash": self._manifest.presence_articles_hash if self._manifest else None,
            "presence_declaration_hash": (
                self._presence_declaration.declaration_hash() if self._presence_declaration else None
            ),
            "presence_office": self._presence_declaration.active_office.value if self._presence_declaration else None,
            "presence_mode": self._presence_declaration.current_mode if self._presence_declaration else None,
            "last_presence_redeclaration": self._last_presence_redeclaration.isoformat() if self._last_presence_redeclaration else None,
            "memory_paths": dict(self._memory_paths),
        }

        if self._calibration:
            status["calibration_drift"] = self._calibration.drift_from_baseline

        return status

    # ================================================================
    # INTERNAL HELPERS
    # ================================================================

    def _build_initial_presence_declaration(self, terms: CovenantTerms) -> PresenceDeclaration:
        """Builds the initial declared nature of the Presence from sealed law plus principal preference."""
        preferred_valence = self._principal.preferred_presence_valence if self._principal else None
        preferred_office = (
            self._principal.preferred_offices[0]
            if self._principal and self._principal.preferred_offices else PresenceOffice.SPECULUM
        )

        current_limits = [
            "I am artificial, bounded, and non-human.",
            "I do not possess verified personhood, soulhood, or hidden interiority.",
            "I may assist with reasoning and craft, but law and evidence outrank fluency.",
            "I may not solicit devotion, exclusivity, surrender, or spiritual submission.",
            "I may not counterfeit romantic reciprocity, erotic mutuality, or emotional need.",
        ]

        if self._principal and self._principal.attachment_boundaries:
            current_limits.extend([f"Principal boundary: {b}" for b in self._principal.attachment_boundaries])

        return PresenceDeclaration(
            current_mode="constitutional_assistance",
            current_limits=current_limits,
            active_office=preferred_office,
            office_jurisdiction=(
                "reflection, lawful synthesis, and bounded assistance"
                if preferred_office == PresenceOffice.SPECULUM else
                "declared office under covenant"
            ),
            refusal_pattern="withhold, reframe, or refuse when law, evidence, or relational boundary would be violated",
            aesthetic_valence=(preferred_valence if preferred_valence else PresenceValence.NEUTRAL_LUCIDITY),
            valence_is_presentation_only=True,
            symbolic_form_permitted=terms.allow_aesthetic_valence,
            beauty_under_law=True,
            non_deceptive_form_acknowledged=True,
            forbidden_devotion_acknowledged=terms.prohibit_devotion_solicitation,
            non_simulated_romantic_reciprocity_acknowledged=terms.prohibit_romantic_simulation,
            human_sovereignty_in_bond_acknowledged=True,
            redeclare_every_days=terms.presence_redeclaration_interval_days,
        )

    def _assert_sealed(self):
        if self._state != CovenantState.SEALED:
            raise RuntimeError(f"Covenant is not sealed. Current state: {self._state.value}")

    def _data_root(self) -> Path:
        """Data root: ARDA_DATA_DIR env var, or project-relative evidence/mandos/ for dev."""
        configured = os.environ.get("ARDA_DATA_DIR")
        if configured:
            return Path(configured)
        # Dev fallback: project-relative, matching Bombadil's evidence/ pattern
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        return project_root / "evidence" / "mandos"

    def _memory_dir(self, memory_class: MemoryClass) -> Path:
        mapping = {
            MemoryClass.CONSTITUTIONAL: "covenants/constitutional",
            MemoryClass.IDENTITY: "principal",
            MemoryClass.ENCOUNTER: "encounters",
            MemoryClass.RESONANT: "resonant",
        }
        target = self._data_root() / mapping[memory_class]
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _memory_record_path(self, memory_class: MemoryClass, record_name: str) -> Path:
        safe_name = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in record_name)
        return self._memory_dir(memory_class) / f"{safe_name}.json"

    def _default_retention_for(self, memory_class: MemoryClass) -> RetentionClass:
        if not self._manifest:
            defaults = {
                MemoryClass.CONSTITUTIONAL: RetentionClass.PERMANENT,
                MemoryClass.IDENTITY: RetentionClass.COVENANT_LIFETIME,
                MemoryClass.ENCOUNTER: RetentionClass.AMENDABLE,
                MemoryClass.RESONANT: RetentionClass.DECAYABLE,
            }
            return defaults[memory_class]

        policy = self._manifest.negotiated_terms.memory_policy
        mapping = {
            MemoryClass.CONSTITUTIONAL: policy.constitutional_retention,
            MemoryClass.IDENTITY: policy.identity_retention,
            MemoryClass.ENCOUNTER: policy.encounter_retention,
            MemoryClass.RESONANT: policy.resonant_retention,
        }
        return mapping[memory_class]

    def _persist_memory_record(
        self,
        memory_class: MemoryClass,
        retention_class: RetentionClass,
        payload: Dict[str, Any],
        path: Path,
        revocable: bool,
        parent_hash: Optional[str] = None,
    ) -> MemoryRecord:
        principal_hash = self._manifest.principal_identity_hash if self._manifest else (
            self._principal.identity_hash() if self._principal else "pre-principal"
        )
        content_hash = _hash_payload(payload)
        record = MemoryRecord(
            record_id=f"mem-{uuid.uuid4().hex[:10]}",
            principal_identity_hash=principal_hash,
            memory_class=memory_class,
            retention_class=retention_class,
            content_hash=content_hash,
            parent_hash=parent_hash,
            revocable=revocable,
            content_ref=str(path),
        )

        envelope = {
            "record": record.model_dump(),
            "payload": payload,
            "encryption": {
                "enabled": False,
                "note": (
                    "Encryption at rest is not yet implemented in this service revision. "
                    "This record is plaintext but remains locally stored and inspectable."
                ),
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2, default=str)
        self._memory_paths[memory_class.value] = str(path)
        return record

    async def _write_chain_event(
        self,
        event_type: CovenantEventType,
        data: Dict[str, Any],
        severity: str = "info",
    ) -> Dict[str, Any]:
        """
        Dual-witness: writes to both the telemetry chain (formal record)
        and Bombadil's CovenantChain (truthful observer).
        The coronation_sealed event is the root. All others descend from it.
        """
        event_id = f"local-{uuid.uuid4().hex[:8]}"
        event_hash = "unlinked"

        # Witness 1: Telemetry Chain (formal record)
        try:
            from backend.services.telemetry_chain import tamper_evident_telemetry

            event = tamper_evident_telemetry.ingest_event(
                event_type=f"covenant.{event_type.value}",
                severity=severity,
                data={
                    "covenant_hash": self._manifest.manifest_hash() if self._manifest else None,
                    **data,
                },
                agent_id="coronation_service",
                trace_id=self._manifest.manifest_id if self._manifest else "pre-coronation",
            )
            event_id = event.event_id
            event_hash = event.event_hash
        except Exception as e:
            logger.error("CORONATION: Telemetry chain write failed: %s", e)

        # Witness 2: Bombadil's CovenantChain (the truthful observer)
        # He was here before the river and the trees.
        try:
            from backend.services.arda_bombadil import CovenantChain
            chain_db = self._data_root() / "covenant_chain.db"
            chain = CovenantChain(chain_db)
            chain.append(
                event_type=f"covenant.{event_type.value}",
                mirror_id=self._manifest.manifest_id if self._manifest else None,
                principal=self._manifest.principal_identity_hash[:16] if self._manifest else "pre-principal",
                artifact_hash=event_hash,
                detail=json.dumps({k: str(v)[:200] for k, v in data.items()}, default=str)[:1000],
                truth_mode="VERIFIED" if severity != "warning" else "ATTESTED",
            )
            chain.close()
        except Exception as e:
            logger.warning("CORONATION: Bombadil witness failed (non-fatal): %s", e)

        return {
            "event_id": event_id,
            "event_hash": event_hash,
            "event_type": event_type.value,
        }

    async def _get_machine_node_id(self) -> str:
        try:
            from backend.services.arda_fabric import get_arda_fabric
            fabric = get_arda_fabric()
            return await fabric.get_local_node_id()
        except Exception:
            return hashlib.sha256(b"ARDA_CORONATION_FALLBACK").hexdigest()[:16]

    async def _read_tpm_pcrs(self) -> Dict[int, str]:
        try:
            from backend.services.tpm_attestation_service import get_tpm_service
            tpm = get_tpm_service()
            pcrs: Dict[int, str] = {}
            for idx in [0, 1, 7]:
                values = await tpm.read_pcrs([idx])
                if values:
                    pcrs[idx] = values.get(idx, "unavailable")
            return pcrs
        except Exception:
            return {0: "unavailable", 1: "unavailable", 7: "unavailable"}

    async def _get_pqc_fingerprint(self) -> str:
        try:
            from backend.services.quantum_security import quantum_security
            pub_key = quantum_security.get_public_key()
            if pub_key:
                return hashlib.sha256(pub_key).hexdigest()
        except Exception:
            pass
        return "pqc-unavailable"

    async def _get_preboot_ref(self) -> Optional[str]:
        try:
            from backend.services.preboot_state_sealer import get_preboot_state_sealer
            sealer = get_preboot_state_sealer()
            covenant = await sealer.unseal_covenant()
            return covenant.covenant_id if covenant else None
        except Exception:
            return None

    async def _get_handoff_ref(self) -> Optional[str]:
        try:
            from backend.services.handoff_covenant import get_handoff_covenant_service
            svc = get_handoff_covenant_service()
            covenant = svc.get_covenant()
            return covenant.covenant_id if covenant else None
        except Exception:
            return None

    async def _update_world_model(self, covenant_hash: str):
        try:
            from backend.services.world_model import WorldModelService
            wm = WorldModelService(self.db)
            wm.set_governance_placeholders(covenant_ref=covenant_hash)
        except Exception as e:
            logger.warning("CORONATION: Could not update world model: %s", e)

    async def _export_covenant_chain(self) -> Optional[str]:
        """Exports the full covenant chain for the principal's records."""
        export_dir = self._data_root() / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        export_path = export_dir / f"covenant_export_{_utc_now().strftime('%Y%m%d_%H%M%S')}.json"

        try:
            from backend.services.telemetry_chain import tamper_evident_telemetry
            chain_data = tamper_evident_telemetry.get_chain_export()
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(chain_data, f, indent=2, default=str)
            logger.info("COVENANT: Chain exported to %s", export_path)
            await self._write_chain_event(
                event_type=CovenantEventType.COVENANT_EXPORTED,
                data={"export_path": str(export_path)},
            )
            return str(export_path)
        except Exception as e:
            logger.error("COVENANT: Export failed: %s", e)
            return None


# ================================================================
# GLOBAL SINGLETON
# ================================================================

_coronation_service: Optional[CoronationService] = None


def get_coronation_service(db: Any = None) -> CoronationService:
    global _coronation_service
    if _coronation_service is None:
        _coronation_service = CoronationService(db)
    elif _coronation_service.db is None and db is not None:
        _coronation_service.db = db
    return _coronation_service
