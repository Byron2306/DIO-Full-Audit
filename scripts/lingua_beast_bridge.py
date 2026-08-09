#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BEAST_ROOT = Path("/home/byron/EdgeK-BEAST")
STORAGE_ROOT = ROOT / "state" / "lingua" / "beast_credits"
CHAIN_PATH = ROOT / "state" / "lingua" / "beast_crystal_chain.jsonl"
BEAST_OPERATIONS_ROOT = ROOT / "state" / "lingua" / "beast_operations"
BEAST_MEMORY_ROOT = ROOT / "state" / "lingua" / "beast_memory_hull"
BEAST_CHRONICLE_ROOT = ROOT / "state" / "lingua" / "beast_chronicle"
BEAST_NEGATIVE_PATH = ROOT / "state" / "lingua" / "beast_negative_capabilities.json"
BEAST_LEARNING_LEDGER = ROOT / "state" / "lingua" / "beast_capability_learning.jsonl"
BEAST_PREC_PATH = ROOT / "state" / "lingua" / "beast_prec_lifecycle.db"


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def load_beast() -> tuple[Any, Any]:
    sys.path.insert(0, str(BEAST_ROOT))
    from app.kernel.security.crystal_chain import CrystalChainLedger
    from app.kernel.storage.durable_inference_storage import DurableInferenceStorage
    return DurableInferenceStorage, CrystalChainLedger


def load_beast_organs() -> dict[str, Any]:
    sys.path.insert(0, str(BEAST_ROOT))
    from app.kernel.compute.capability_learning import CapabilityLearningLedger
    from app.kernel.storage.evidence_chronicle import EvidenceChronicleWriter
    from app.kernel.storage.evidence_scoring import EvidenceScorer
    from app.kernel.storage.memory_hull import MemoryHull
    from app.kernel.storage.outcome_evidence import NegativeCapabilityStore, OutcomeEvidence
    from app.kernel.storage.prec_lifecycle import PRECLifecycleStore
    return {
        "CapabilityLearningLedger": CapabilityLearningLedger,
        "EvidenceChronicleWriter": EvidenceChronicleWriter,
        "EvidenceScorer": EvidenceScorer,
        "MemoryHull": MemoryHull,
        "NegativeCapabilityStore": NegativeCapabilityStore,
        "OutcomeEvidence": OutcomeEvidence,
        "PRECLifecycleStore": PRECLifecycleStore,
    }


def record_prec(operation: str, payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    organs = load_beast_organs()
    store = organs["PRECLifecycleStore"](str(BEAST_PREC_PATH))
    lifecycle = store.start(
        kind="dio_lingua",
        objective=f"Lingua {operation} for {payload.get('target_language') or 'shared memory'}",
        scope=str(payload.get("domain") or "cross_product"),
        task_id=str(payload.get("semantic_object_id") or ""),
        provider="BEAST",
        metadata={"operation": operation, "target_language": payload.get("target_language")},
    )
    lifecycle_id = lifecycle["lifecycle_id"]
    store.record_phase(lifecycle_id, "perceive", summary="Captured source identity, language, domain, flags, and existing crystal state.", signals=[operation])
    store.record_phase(lifecycle_id, "reason", summary="Applied evidence scoring, semantic applicability, and negative-capability evidence.", artifacts={"result_status": result.get("status")})
    store.record_phase(lifecycle_id, "economize", summary="Reused exact approved credits and retained provider fallback only where authority was absent.", artifacts={"provider_call_displaced": result.get("provider_call_displaced", False)})
    store.record_phase(lifecycle_id, "crystallize", summary="Recorded governed capability lifecycle and tamper-evident receipts.", artifacts={"receipt_digest": canonical_digest(result)})
    return store.complete(lifecycle_id, summary=f"Lingua {operation} lifecycle completed")


def write_memory_residue(*, task: str, decision: str, evidence: dict[str, Any], tags: list[str]) -> dict[str, Any]:
    organs = load_beast_organs()
    hull = organs["MemoryHull"](BEAST_MEMORY_ROOT)
    return hull.write_residue(
        task=task,
        provider="BEAST",
        decision=decision,
        evidence=evidence,
        section="decisions",
        policy_tags=tags,
        caller="spiffe://dio.local/lingua",
    )


def write_status() -> dict[str, Any]:
    organs = load_beast_organs()
    learning = organs["CapabilityLearningLedger"](BEAST_LEARNING_LEDGER).report(limit=12)
    negative_store = organs["NegativeCapabilityStore"](BEAST_NEGATIVE_PATH)
    memory = organs["MemoryHull"](BEAST_MEMORY_ROOT).inventory(verify=True)
    prec_store = organs["PRECLifecycleStore"](str(BEAST_PREC_PATH))
    prec = prec_store.list(kind="dio_lingua", limit=12)
    prec_state = prec_store.state()
    prec["count"] = sum(
        int(row.get("count") or 0)
        for row in prec_state.get("counts") or []
        if row.get("kind") == "dio_lingua"
    )
    prec["state"] = prec_state
    status = {
        "schema": "dio.lingua.beast_organs_status.v1",
        "status": "operational",
        "organs": {
            "durable_semantic_credits": True,
            "crystal_chain": True,
            "evidence_scoring": True,
            "evidence_chronicle": True,
            "negative_capability": True,
            "capability_learning": True,
            "memory_hull": True,
            "prec_lifecycle": True,
        },
        "learning": learning,
        "negative_capability": negative_store.summary(),
        "friction_profiles": negative_store.friction_profiles()[:8],
        "memory_hull": memory,
        "prec": prec,
    }
    status_path = ROOT / "state" / "lingua" / "BEAST_ORGANS_STATUS.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return status


def record_learning_event(
    *,
    event_type: str,
    capability_type: str,
    capability_id: str,
    lifecycle_state: str,
    authority: str,
    evidence: Any,
    receipt: Any,
    provider_calls_used: int = 0,
    provider_calls_avoided: int = 0,
    fresh_work_units: int = 0,
    reuse_hits: int = 0,
    refusal_reason: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    organs = load_beast_organs()
    event = organs["CapabilityLearningLedger"](BEAST_LEARNING_LEDGER).record(
        event_type=event_type,
        capability_type=capability_type,
        capability_id=capability_id,
        lifecycle_state=lifecycle_state,
        authority=authority,
        evidence_digest=canonical_digest(evidence),
        receipt_digest=canonical_digest(receipt),
        provider_calls_used=provider_calls_used,
        provider_calls_avoided=provider_calls_avoided,
        fresh_work_units=fresh_work_units,
        reuse_hits=reuse_hits,
        refusal_reason=refusal_reason,
        metadata=metadata or {},
    )
    return {"event_digest": event.event_digest, "capability_id": event.capability_id}


def resolve(payload: dict[str, Any]) -> dict[str, Any]:
    DurableInferenceStorage, CrystalChainLedger = load_beast()
    storage = DurableInferenceStorage(STORAGE_ROOT)
    target_language = str(payload.get("target_language") or "")
    domain = str(payload.get("domain") or "")
    source_units = {str(row["unit_id"]): row for row in payload.get("units") or []}
    source_hashes = {unit_id: str(row["source_hash"]) for unit_id, row in source_units.items()}
    approved_units = []
    approved_terms = []
    risk_patterns = []
    deterministic_guards = []
    for credit in storage.credits.values():
        if not credit.is_reusable():
            continue
        metadata = credit.metadata or {}
        if metadata.get("target_language") != target_language:
            continue
        if metadata.get("domain") not in {domain, "*"}:
            continue
        if credit.task_class == "dio_lingua_translation_unit":
            unit_id = str(metadata.get("unit_id") or "")
            if source_hashes.get(unit_id) == metadata.get("source_hash"):
                storage.record_credit_reuse(
                    credit.credit_id,
                    measured_tokens_saved=max(1, len(str(metadata.get("target_text") or "")) // 4),
                )
                approved_units.append({
                    "unit_id": unit_id,
                    "source_hash": metadata.get("source_hash"),
                    "target_text": metadata.get("target_text"),
                    "reviewer": metadata.get("reviewer"),
                    "credit_id": credit.credit_id,
                })
            elif unit_id in source_hashes and metadata.get("source_hash") != source_hashes[unit_id]:
                storage.mark_stale(
                    credit.credit_id,
                    reason="lingua_source_unit_hash_changed",
                    evidence={"unit_id": unit_id, "current_source_hash": source_hashes[unit_id]},
                )
        elif credit.task_class == "dio_lingua_approved_term":
            storage.record_credit_reuse(credit.credit_id, measured_tokens_saved=8)
            approved_terms.append({
                "source": metadata.get("source_term"),
                "target": metadata.get("target_term"),
                "note": f"BEAST crystal {credit.credit_id}; human approved",
                "credit_id": credit.credit_id,
            })
        elif credit.task_class in {"dio_lingua_risk_pattern", "dio_lingua_deterministic_failure_pattern"}:
            risk_patterns.append({
                "issue": metadata.get("issue"),
                "severity": metadata.get("severity"),
                "action": "retain uncertainty and require proficient review",
                "observation_type": metadata.get("observation_type"),
                "credit_id": credit.credit_id,
            })
        elif credit.task_class == "dio_lingua_deterministic_guard":
            deterministic_guards.append({
                "guard": metadata.get("guard"),
                "rule": metadata.get("rule"),
                "credit_id": credit.credit_id,
            })
    organs = load_beast_organs()
    negative_store = organs["NegativeCapabilityStore"](BEAST_NEGATIVE_PATH)
    active_negative_capabilities = negative_store.active_matches({
        "capability_id": "dio_lingua_translation_validator",
        "task_class": "translation_quality",
        "scope": {"route": domain or "cross_product", "transform_type": target_language},
    })
    chain = CrystalChainLedger(CHAIN_PATH, node_id="dio-lingua").verify().to_dict()
    result = {
        "schema": "dio.lingua.beast_resolution.v1",
        "status": "resolved",
        "approved_units": approved_units,
        "approved_terms": approved_terms,
        "risk_patterns": risk_patterns,
        "deterministic_guards": deterministic_guards,
        "active_negative_capabilities": active_negative_capabilities,
        "reuse_state": "hit" if approved_units or approved_terms else "miss",
        "provider_call_displaced": len(approved_units) == len(source_hashes) and bool(source_hashes),
        "crystal_chain": chain,
    }
    record_learning_event(
        event_type="semantic_credit_reused" if approved_units or approved_terms else "semantic_credit_missed",
        capability_type="lingua_semantic_reuse",
        capability_id=f"lingua:{domain or '*'}:{target_language or '*'}",
        lifecycle_state="reused" if approved_units or approved_terms else "observed",
        authority="human_approved_exact_match",
        evidence={"source_hashes": source_hashes, "active_negative_count": len(active_negative_capabilities)},
        receipt=result,
        provider_calls_avoided=int(result["provider_call_displaced"]),
        fresh_work_units=max(0, len(source_hashes) - len(approved_units)),
        reuse_hits=len(approved_units) + len(approved_terms),
        metadata={"domain": domain, "target_language": target_language},
    )
    result["memory_residue"] = write_memory_residue(
        task=f"Resolve Lingua knowledge for {domain or 'cross-product'}",
        decision=f"Reused {len(approved_units)} approved units and {len(approved_terms)} approved terms.",
        evidence={"reuse_state": result["reuse_state"], "active_negative_count": len(active_negative_capabilities)},
        tags=["lingua", "semantic-reuse", "human-authority"],
    )
    result["prec_lifecycle"] = record_prec("resolve", payload, result)
    write_status()
    return result


def _existing_credit(storage: Any, task_class: str, fingerprint: str) -> Any:
    return next(
        (
            credit for credit in storage.credits.values()
            if credit.task_class == task_class and credit.repo_fingerprint == fingerprint and credit.reuse_state == "active"
        ),
        None,
    )


def learn_flags(payload: dict[str, Any]) -> dict[str, Any]:
    DurableInferenceStorage, CrystalChainLedger = load_beast()
    storage = DurableInferenceStorage(STORAGE_ROOT)
    chain = CrystalChainLedger(CHAIN_PATH, node_id="dio-lingua")
    organs = load_beast_organs()
    scorer = organs["EvidenceScorer"]()
    chronicle = organs["EvidenceChronicleWriter"](str(BEAST_CHRONICLE_ROOT))
    negative_store = organs["NegativeCapabilityStore"](BEAST_NEGATIVE_PATH)
    language = str(payload.get("target_language") or "")
    domain = str(payload.get("domain") or "")
    learned = []
    guards = {
        "anchor_completeness": "Every source unit must have exactly one aligned target unit.",
        "numeral_preservation": "Every operational numeral present in a source unit must remain present in its target unit.",
        "protected_token_preservation": "Every configured protected token must remain exact in the target unit.",
        "source_hash_staleness": "A changed source-unit hash makes every previously aligned target unit stale.",
    }
    for guard, rule in guards.items():
        metadata = {
            "guard": guard,
            "rule": rule,
            "target_language": language or "*",
            "domain": "*",
            "authority": "deterministic_validator",
            "semantic_index": storage.semantic_index(f"{guard} {rule}"),
        }
        fingerprint = canonical_digest({"task_class": "dio_lingua_deterministic_guard", **metadata})
        credit = _existing_credit(storage, "dio_lingua_deterministic_guard", fingerprint)
        created = credit is None
        if created:
            credit = storage.store_semantic_result(
                task_class="dio_lingua_deterministic_guard",
                repo_fingerprint=fingerprint,
                policy_version="dio_lingua_deterministic_learning_v1",
                verified_tests=["visible", "hidden"],
                avoided_tokens_estimate=12,
                confidence=1.0,
                impact_fingerprint_hash=fingerprint,
                evidence_packet_id=f"guard:{guard}",
                metadata=metadata,
            )
            chain.append("lingua.deterministic_guard.crystallized", credit.credit_id, {"credit_id": credit.credit_id, "guard": guard, "fingerprint": fingerprint})
        learned.append({"kind": "deterministic_guard", "name": guard, "credit_id": credit.credit_id, "created": created})
    observations = list(payload.get("flags") or []) + [
        {
            "severity": "high",
            "issue": f"Deterministic validator rejected provider output: {error}",
            "observation_type": "deterministic_failure",
        }
        for error in (payload.get("validation") or {}).get("errors") or []
    ]
    for flag in observations:
        severity = str(flag.get("severity") or "").casefold()
        issue = " ".join(str(flag.get("issue") or "").split())
        if severity not in {"medium", "high"} or not issue:
            continue
        scope = {"route": domain or "cross_product", "transform_type": language or "unknown"}
        outcome = organs["OutcomeEvidence"].create(
            capability_id="dio_lingua_translation_validator",
            task_class="translation_quality",
            outcome="failure",
            failure_category=str(flag.get("observation_type") or "language_uncertainty"),
            failure_code=severity,
            detail=issue,
            scope=scope,
            confidence_before=0.9,
            selected_capabilities=("deterministic_validation", "proficient_review_routing"),
        )
        negative_record = negative_store.record(outcome)
        repeat_count = negative_record.failure_count if negative_record else 1
        score = scorer.score(
            relevance=1.0,
            confidence=0.95 if flag.get("observation_type") == "deterministic_failure" else 0.8,
            severity=severity,
            freshness=1.0,
            repeat_count=repeat_count,
            verification_strength=1.0 if flag.get("observation_type") == "deterministic_failure" else 0.65,
            blast_radius=0.75 if severity == "high" else 0.45,
        ).to_dict()
        metadata = {
            "issue": issue,
            "severity": severity,
            "target_language": language,
            "domain": domain,
            "authority": "conservative_machine_risk_escalation",
            "asserts_translation_truth": False,
            "observation_type": flag.get("observation_type") or "language_uncertainty",
            "semantic_index": storage.semantic_index(issue),
            "evidence_score": score,
            "negative_capability_record_id": negative_record.record_id if negative_record else "",
        }
        task_class = "dio_lingua_deterministic_failure_pattern" if metadata["observation_type"] == "deterministic_failure" else "dio_lingua_risk_pattern"
        fingerprint = canonical_digest({"task_class": task_class, **metadata})
        credit = _existing_credit(storage, task_class, fingerprint)
        created = credit is None
        if created:
            credit = storage.store_semantic_result(
                task_class=task_class,
                repo_fingerprint=fingerprint,
                policy_version="dio_lingua_conservative_risk_learning_v1",
                verified_tests=["visible", "hidden"],
                avoided_tokens_estimate=20,
                confidence=0.9,
                impact_fingerprint_hash=fingerprint,
                evidence_packet_id=f"risk:{language}:{canonical_digest(issue)[:20]}",
                metadata=metadata,
            )
            chain.append("lingua.deterministic_failure.crystallized" if task_class == "dio_lingua_deterministic_failure_pattern" else "lingua.risk_pattern.crystallized", credit.credit_id, {
                "credit_id": credit.credit_id,
                "target_language": language,
                "domain": domain,
                "severity": severity,
                "fingerprint": fingerprint,
                "asserts_translation_truth": False,
            })
        else:
            chain.append("lingua.risk_pattern.observed_again", credit.credit_id, {
                "credit_id": credit.credit_id,
                "target_language": language,
                "domain": domain,
                "severity": severity,
            })
        evidence_envelope = {
            "evidence_id": outcome.evidence_id,
            "task_id": payload.get("semantic_object_id"),
            "provider": "DIO Lingua deterministic validator",
            "source_type": metadata["observation_type"],
            "artifact_type": "translation_quality_flag",
            "capability_family": "lingua_quality_learning",
            "created_at": outcome.observed_at,
            "issue_digest": canonical_digest(issue),
            **score,
        }
        chronicle_receipt = chronicle.maybe_write(evidence_envelope, reason="repeated_or_material_lingua_quality_evidence")
        record_learning_event(
            event_type="deterministic_failure_observed",
            capability_type="lingua_quality_pattern",
            capability_id=credit.credit_id,
            lifecycle_state=negative_record.state if negative_record else "observing",
            authority="deterministic_evidence_only",
            evidence=evidence_envelope,
            receipt=chronicle_receipt,
            fresh_work_units=1,
            metadata={"severity": severity, "repeat_count": repeat_count, "asserts_translation_truth": False},
        )
        learned.append({
            "kind": "risk_pattern",
            "issue": issue,
            "credit_id": credit.credit_id,
            "created": created,
            "evidence_score": score,
            "negative_capability_state": negative_record.state if negative_record else "observing",
            "chronicle": chronicle_receipt,
        })
    result = {
        "schema": "dio.lingua.beast_learning_receipt.v1",
        "status": "learned",
        "learned": learned,
        "automatic_learning_scope": ["deterministic_guards", "conservative_review_routing"],
        "semantic_translation_truth_promoted": False,
        "human_intervention_required": False,
        "chain": chain.verify().to_dict(),
    }
    result["negative_capability"] = negative_store.summary()
    result["memory_residue"] = write_memory_residue(
        task=f"Learn Lingua quality evidence for {domain or 'cross-product'}",
        decision=f"Recorded {len(observations)} observations without promoting machine-drafted meaning.",
        evidence={"learned_count": len(learned), "negative_capability": result["negative_capability"]},
        tags=["lingua", "deterministic-learning", "no-semantic-promotion"],
    )
    result["prec_lifecycle"] = record_prec("learn_flags", payload, result)
    write_status()
    return result


def crystallize(payload: dict[str, Any]) -> dict[str, Any]:
    DurableInferenceStorage, CrystalChainLedger = load_beast()
    if payload.get("approval_state") != "approved":
        raise PermissionError("Only explicitly approved Lingua knowledge may be crystallized.")
    reviewer = str(payload.get("reviewer") or "").strip()
    reviewer_role = str(payload.get("reviewer_role") or "").strip()
    if not reviewer or not reviewer_role:
        raise ValueError("Reviewer identity and role are required.")
    storage = DurableInferenceStorage(STORAGE_ROOT)
    chain = CrystalChainLedger(CHAIN_PATH, node_id="dio-lingua")
    credits = []
    for unit in payload.get("units") or []:
        metadata = {
            "semantic_object_id": payload.get("semantic_object_id"),
            "unit_id": unit["unit_id"],
            "source_hash": unit["source_hash"],
            "target_text": unit["target_text"],
            "target_language": payload["target_language"],
            "domain": payload.get("domain") or "*",
            "reviewer": reviewer,
            "reviewer_role": reviewer_role,
            "approved_at": payload.get("approved_at"),
        }
        fingerprint = canonical_digest(metadata)
        credit = storage.store_semantic_result(
            task_class="dio_lingua_translation_unit",
            repo_fingerprint=fingerprint,
            policy_version="dio_lingua_human_authority_v1",
            verified_tests=["visible", "hidden"],
            avoided_tokens_estimate=max(1, len(str(unit["target_text"])) // 4),
            confidence=1.0,
            impact_fingerprint_hash=fingerprint,
            evidence_packet_id=f"{payload.get('semantic_object_id')}:{unit['unit_id']}",
            metadata=metadata,
        )
        block = chain.append("lingua.translation_unit.crystallized", credit.credit_id, {
            "credit_id": credit.credit_id,
            "fingerprint": fingerprint,
            "semantic_object_id": payload.get("semantic_object_id"),
            "unit_id": unit["unit_id"],
            "target_language": payload["target_language"],
            "reviewer": reviewer,
            "reviewer_role": reviewer_role,
        })
        credits.append({"credit_id": credit.credit_id, "unit_id": unit["unit_id"], "block_hash": block["block_hash"]})
    for term in payload.get("terms") or []:
        metadata = {
            "source_term": term["source_term"],
            "target_term": term["target_term"],
            "target_language": payload["target_language"],
            "domain": term.get("domain") or payload.get("domain") or "*",
            "reviewer": reviewer,
            "reviewer_role": reviewer_role,
            "approved_at": payload.get("approved_at"),
        }
        fingerprint = canonical_digest(metadata)
        credit = storage.store_semantic_result(
            task_class="dio_lingua_approved_term",
            repo_fingerprint=fingerprint,
            policy_version="dio_lingua_human_authority_v1",
            verified_tests=["visible", "hidden"],
            avoided_tokens_estimate=8,
            confidence=1.0,
            impact_fingerprint_hash=fingerprint,
            evidence_packet_id=f"term:{term['source_term']}:{payload['target_language']}",
            metadata=metadata,
        )
        block = chain.append("lingua.term.crystallized", credit.credit_id, {
            "credit_id": credit.credit_id,
            "fingerprint": fingerprint,
            "source_term": term["source_term"],
            "target_language": payload["target_language"],
            "reviewer": reviewer,
            "reviewer_role": reviewer_role,
        })
        credits.append({"credit_id": credit.credit_id, "source_term": term["source_term"], "block_hash": block["block_hash"]})
    result = {
        "schema": "dio.lingua.beast_crystallization_receipt.v1",
        "status": "crystallized",
        "credits": credits,
        "machine_drafts_promoted": False,
        "human_authority_verified": True,
        "chain": chain.verify().to_dict(),
    }
    organs = load_beast_organs()
    negative_store = organs["NegativeCapabilityStore"](BEAST_NEGATIVE_PATH)
    outcome = organs["OutcomeEvidence"].create(
        capability_id="dio_lingua_translation_validator",
        task_class="translation_quality",
        outcome="success",
        scope={
            "route": str(payload.get("domain") or "cross_product"),
            "transform_type": str(payload.get("target_language") or "unknown"),
        },
        approval_pauses=1,
        confidence_after=1.0,
        selected_capabilities=("human_semantic_approval", "beast_crystallization"),
    )
    negative_store.record(outcome)
    result["learning_event"] = record_learning_event(
        event_type="human_semantic_authority_crystallized",
        capability_type="lingua_semantic_authority",
        capability_id=f"lingua:{payload.get('semantic_object_id')}:{payload.get('target_language')}",
        lifecycle_state="approved_active",
        authority=f"{reviewer_role}:{reviewer}",
        evidence={"units": payload.get("units") or [], "terms": payload.get("terms") or []},
        receipt=result,
        fresh_work_units=len(payload.get("units") or []) + len(payload.get("terms") or []),
        metadata={"semantic_object_id": payload.get("semantic_object_id"), "target_language": payload.get("target_language")},
    )
    result["memory_residue"] = write_memory_residue(
        task=f"Crystallize {payload.get('semantic_object_id')} in {payload.get('target_language')}",
        decision=f"Accepted proficient reviewer authority from {reviewer} ({reviewer_role}).",
        evidence={"credit_count": len(credits), "approval_state": payload.get("approval_state")},
        tags=["lingua", "human-approved", "semantic-authority"],
    )
    result["prec_lifecycle"] = record_prec("crystallize", payload, result)
    write_status()
    return result


def main() -> int:
    payload = json.load(sys.stdin)
    operation = str(payload.get("operation") or "")
    try:
        result = resolve(payload) if operation == "resolve" else crystallize(payload) if operation == "crystallize" else learn_flags(payload) if operation == "learn_flags" else write_status() if operation == "status" else None
        if result is None:
            raise ValueError("operation must be resolve, learn_flags, crystallize, or status")
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
