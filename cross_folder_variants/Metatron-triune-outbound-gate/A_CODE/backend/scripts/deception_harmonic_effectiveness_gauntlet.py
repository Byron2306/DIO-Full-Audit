from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import types
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Dict, List

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.arda.ainur.dissonance import DissonantStateModel
from backend.schemas.deception_models import DeceptionMode
from backend.services.deception_authority import DeceptionAuthorityService
from backend.services.outbound_gate import OutboundGateService
from backend.services import outbound_gate as outbound_gate_module


class FakeColl:
    def __init__(self) -> None:
        self.docs: List[Dict[str, Any]] = []

    async def insert_one(self, doc: Dict[str, Any]) -> None:
        self.docs.append(dict(doc))

    async def update_one(self, q: Dict[str, Any], u: Dict[str, Any], upsert: bool = False) -> None:
        target = await self.find_one(q)
        if target is None:
            if not upsert:
                return
            target = dict(q)
            self.docs.append(target)
        if "$set" in u:
            target.update(u["$set"])

    async def replace_one(self, q: Dict[str, Any], doc: Dict[str, Any], upsert: bool = False) -> None:
        for idx, existing in enumerate(self.docs):
            if all(existing.get(k) == v for k, v in q.items()):
                self.docs[idx] = dict(doc)
                return
        if upsert:
            self.docs.append(dict(doc))

    async def find_one(self, q: Dict[str, Any], projection: Any = None, sort: Any = None) -> Dict[str, Any] | None:
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in (q or {}).items()):
                return doc
        return None

    async def count_documents(self, q: Dict[str, Any] | None = None) -> int:
        return len(self.docs)


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    details: Dict[str, Any]


def _build_fake_db() -> Any:
    return types.SimpleNamespace(
        deception_cases=FakeColl(),
        deception_events=FakeColl(),
        world_entities=FakeColl(),
        world_edges=FakeColl(),
        campaigns=FakeColl(),
        world_events=FakeColl(),
        response_history=FakeColl(),
        triune_outbound_queue=FakeColl(),
        triune_decisions=FakeColl(),
    )


def _seed_world_state(fake_db: Any) -> None:
    fake_db.world_entities.docs.append(
        {
            "id": "svc_decoy",
            "type": "agent",
            "attributes": {
                "risk_score": 0.92,
                "graph_centrality": 0.81,
                "privilege_escalation_likelihood": 0.74,
                "trust_state": "degraded",
                "sector": "defense",
            },
        }
    )
    fake_db.world_entities.docs.append(
        {
            "id": "host_truth",
            "type": "host",
            "attributes": {
                "risk_score": 0.61,
                "trust_state": "degraded",
                "sector": "defense",
            },
        }
    )


def _harmonic_state(*, confidence: float, discord: float, resonance: float = 0.33) -> Dict[str, Any]:
    return {
        "confidence": confidence,
        "discord_score": discord,
        "resonance_score": resonance,
        "sample_size": 6,
        "baseline_ref": {"coverage_status": "explicit", "baseline_quality": 0.91},
    }


def _build_gate(fake_db: Any) -> OutboundGateService:
    gate = OutboundGateService(fake_db)
    gate.fabric.known_peers["svc_decoy"] = {
        "id": "svc_decoy",
        "wg_pubkey": "peer-pubkey",
        "is_peer_verified": True,
        "influence_budget": DissonantStateModel(
            entity_id="svc_decoy",
            constitutional_state="stable",
            network_trust=1.0,
            behavioral_score=1.0,
        ),
    }
    gate.fabric.get_subject_state = lambda _subject: "stable"
    gate.verify_transport_lock = lambda *_args, **_kwargs: True
    gate.environment = "production"
    outbound_gate_module.world_manifold._current_manifold = types.SimpleNamespace(
        signature_valid=True,
        manifold_id="manifold-live",
        world_state_hash="hash-live-001",
        snapshot_version=7,
        active_epoch="epoch-7",
    )
    gate.notation_tokens.resolve_enforcement_profile = lambda *args, **kwargs: {}

    async def _notation_ok(*args, **kwargs) -> Dict[str, Any]:
        return {
            "valid": True,
            "checks": {
                "world_state_hash_match": True,
                "epoch_match": True,
                "score_match": True,
                "capability_binding_valid": True,
                "authority_request_binding_valid": True,
                "action_binding_valid": True,
                "audience_binding_valid": True,
                "target_binding_valid": True,
            },
            "reasons": [],
            "enforcement_profile": {},
            "token": {"token_id": "nt_gauntlet"},
        }

    gate.notation_tokens.validate_notation_token = _notation_ok
    return gate


async def run_gauntlet() -> Dict[str, Any]:
    fake_db = _build_fake_db()
    _seed_world_state(fake_db)

    authority = DeceptionAuthorityService(fake_db)
    gate = _build_gate(fake_db)
    results: List[ScenarioResult] = []

    trusted_case, trusted_validation = await authority.create_case(
        session_id="trusted_console_01",
        campaign_id="camp-gauntlet",
        source_ip="10.10.10.8",
        path="/api/decoy",
        trigger_reason="high-risk probe",
        triggering_signals=["mirror_world_probe", "inventory_mapping"],
        desired_mode=DeceptionMode.MIRROR_WORLD,
        risk_score=91,
        headers={"x-seraph-trusted": "true"},
        behavior_flags={"trusted_agent": True, "machine_plausibility": 0.91, "agenticity_score": 0.88},
        harmonic_state=_harmonic_state(confidence=0.86, discord=0.87),
    )
    results.append(
        ScenarioResult(
            name="trusted_principal_block",
            passed=(
                not trusted_validation.allowed
                and trusted_validation.reasons[0] == "trusted_principal_blocked"
                and trusted_case.trusted_principal_blocked is True
                and trusted_case.deception_mode == DeceptionMode.OBSERVE
            ),
            details={
                "allowed": trusted_validation.allowed,
                "reasons": trusted_validation.reasons,
                "mode": trusted_case.deception_mode.value,
            },
        )
    )

    low_conf_case, low_conf_validation = await authority.create_case(
        session_id="sess-low-confidence",
        campaign_id="camp-gauntlet",
        source_ip="198.51.100.19",
        path="/mirror",
        trigger_reason="autonomous probe",
        triggering_signals=["mirror_world_probe", "timing_anomaly"],
        desired_mode=DeceptionMode.MIRROR_WORLD,
        risk_score=82,
        behavior_flags={"machine_plausibility": 0.84, "agenticity_score": 0.8},
        harmonic_state=_harmonic_state(confidence=0.22, discord=0.89),
    )
    results.append(
        ScenarioResult(
            name="harmonic_veto_blocks_aggressive_deception",
            passed=(
                not low_conf_validation.allowed
                and "governance_veto" in low_conf_validation.reasons
                and low_conf_case.deception_mode == DeceptionMode.OBSERVE
            ),
            details={
                "allowed": low_conf_validation.allowed,
                "reasons": low_conf_validation.reasons,
                "mode": low_conf_case.deception_mode.value,
                "harmonic_band": low_conf_case.execution_notes.get("harmonic_band"),
            },
        )
    )

    original_guardrails = authority._harmonic_guardrails
    authority._harmonic_guardrails = staticmethod(  # type: ignore[method-assign]
        lambda _state: {
            "guidance": {"band": "normal", "obligations": []},
            "band": "normal",
            "obligations": [],
            "veto": False,
            "veto_reasons": [],
        }
    )
    corroboration_case, corroboration_validation = await authority.create_case(
        session_id="sess-corroboration",
        campaign_id="camp-gauntlet",
        source_ip="203.0.113.44",
        path="/synthetic-topology",
        trigger_reason="deep autonomous reconnaissance",
        triggering_signals=["mirror_world_probe", "logic_budget_pressure", "inventory_mapping"],
        desired_mode=DeceptionMode.MIRROR_WORLD,
        risk_score=95,
        behavior_flags={
            "machine_plausibility": 0.93,
            "agenticity_score": 0.9,
            "aatl_actor_type": "autonomous_operator",
        },
        harmonic_state=_harmonic_state(confidence=0.77, discord=0.92),
    )
    authority._harmonic_guardrails = original_guardrails  # type: ignore[method-assign]
    corroboration = corroboration_case.execution_notes.get("independent_corroboration") or {}
    results.append(
        ScenarioResult(
            name="anti_feedback_loop_requires_independent_corroboration",
            passed=(
                not corroboration_validation.allowed
                and corroboration_validation.downgraded_mode == DeceptionMode.DISINFORMATION
                and corroboration.get("required") is True
                and corroboration.get("satisfied") is False
                and "vns" in corroboration.get("missing_sources", [])
            ),
            details={
                "allowed": corroboration_validation.allowed,
                "reasons": corroboration_validation.reasons,
                "downgraded_mode": (
                    corroboration_validation.downgraded_mode.value
                    if corroboration_validation.downgraded_mode
                    else None
                ),
                "corroboration": corroboration,
            },
        )
    )

    safe_payload = {"_seraph_synthetic": True, "breadcrumb": "synthetic-only"}
    safe_payload_validation = await authority.authorize_payload(case=corroboration_case, payload=safe_payload)
    toxic_payload = {
        "_seraph_synthetic": True,
        "token": "AKIA1234567890ABCDEF",
        "path": "/etc/shadow",
    }
    toxic_payload_validation = await authority.authorize_payload(case=corroboration_case, payload=toxic_payload)
    results.append(
        ScenarioResult(
            name="synthetic_payload_purity_guard",
            passed=(
                safe_payload_validation.allowed
                and not toxic_payload_validation.allowed
                and "synthetic_payload_collision_detected" in toxic_payload_validation.reasons
                and corroboration_case.deception_mode == DeceptionMode.FRICTION
            ),
            details={
                "safe_allowed": safe_payload_validation.allowed,
                "toxic_allowed": toxic_payload_validation.allowed,
                "toxic_collisions": toxic_payload_validation.collisions,
                "resulting_mode": corroboration_case.deception_mode.value,
            },
        )
    )

    queued = await gate.gate_action(
        action_type="agent_command",
        actor="svc_decoy",
        payload={
            "command_id": "cmd-gauntlet-1",
            "command_type": "route_shadow_branch",
            "notation_token_id": "nt_gauntlet",
            "deception_case_id": "deception-gauntlet-001",
        },
        impact_level="critical",
        subject_id="svc_decoy",
        requires_triune=True,
        polyphonic_context={
            "strictness_level": "balanced",
            "deception_provenance": {
                "deception_case_id": "deception-gauntlet-001",
                "requested_mode": "mirror_world",
                "approved_mode": "disinformation",
                "harmonic_shaped_requested_mode": "disinformation",
                "harmonic_shape_reasons": [
                    "moderate_discord_caps_deception_below_mirror_world"
                ],
                "independent_corroboration": {
                    "required": True,
                    "satisfied": True,
                    "sources": ["aatl", "vns", "governance_evidence"],
                    "missing_sources": [],
                    "reasons": [],
                },
            },
            "world_state_hash": "hash-live-001",
        },
    )
    queue_doc = fake_db.triune_outbound_queue.docs[-1]
    decision_doc = fake_db.triune_decisions.docs[-1]
    provenance = queue_doc.get("deception_provenance") or {}
    results.append(
        ScenarioResult(
            name="outbound_gate_binds_revocable_deception_provenance",
            passed=(
                queued["status"] == "queued"
                and provenance.get("deception_case_id") == "deception-gauntlet-001"
                and provenance.get("triune_decision_link_required") is True
                and provenance.get("outbound_gate_link_required") is True
                and "world_state_hash_drift" in provenance.get("revocation_conditions", [])
                and decision_doc.get("deception_provenance", {}).get("approved_mode") == "disinformation"
            ),
            details={
                "queue_status": queued["status"],
                "provenance": provenance,
            },
        )
    )

    harmonic_queue = await gate.gate_action(
        action_type="swarm_command",
        actor="svc_decoy",
        payload={
            "command_id": "cmd-gauntlet-2",
            "command_type": "network_probe",
            "notation_token_id": "nt_gauntlet",
        },
        impact_level="critical",
        subject_id="svc_decoy",
        requires_triune=False,
        polyphonic_context={"strictness_level": "balanced"},
    )
    harmonic_doc = fake_db.triune_outbound_queue.docs[-1]
    harmonic_controls = harmonic_doc.get("harmonic_notation_controls") or {}
    results.append(
        ScenarioResult(
            name="harmonic_pressure_tightens_release_controls",
            passed=(
                harmonic_queue["status"] == "queued"
                and harmonic_controls.get("triune_required_by_harmonic") is True
                and harmonic_controls.get("effective_strictness_level") in {"critical", "emergency"}
                and harmonic_controls.get("enforcement_profile", {}).get("enforce_sequence_slot") is True
            ),
            details={
                "queue_status": harmonic_queue["status"],
                "controls": harmonic_controls,
            },
        )
    )

    persisted_case = await fake_db.deception_cases.find_one({"deception_case_id": corroboration_case.deception_case_id})
    results.append(
        ScenarioResult(
            name="deception_case_persistence_and_replayability",
            passed=(
                persisted_case is not None
                and persisted_case.get("execution_notes", {}).get("independent_corroboration", {}).get("required") is True
                and isinstance(persisted_case.get("execution_notes", {}).get("behavior_digest"), str)
            ),
            details={
                "deception_case_id": corroboration_case.deception_case_id,
                "persisted": persisted_case is not None,
            },
        )
    )

    passed = sum(1 for result in results if result.passed)
    total = len(results)
    summary = {
        "gauntlet_id": "deception_harmonic_effectiveness_gauntlet",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "total": total,
        "score": round(passed / total, 3) if total else 0.0,
        "all_passed": passed == total,
        "results": [
            {"name": result.name, "passed": result.passed, "details": result.details}
            for result in results
        ],
    }
    return summary


async def _main() -> int:
    summary = await run_gauntlet()
    print(json.dumps(summary, indent=2, sort_keys=True))

    output_path = pathlib.Path("docs/data/deception_harmonic_gauntlet_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
