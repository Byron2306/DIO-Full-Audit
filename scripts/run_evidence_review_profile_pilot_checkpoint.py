#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.evidence_review_profile_pilot import (  # noqa: E402
    ENGINE_IDENTITY,
    enrich_packet_from_profile_spec,
    load_profile_pilot_spec,
    run_profile_native_pilot,
)
from products.evidence_review_studio_quality import PASS_TOKEN as QUALITY_PASS, audit_profile_studio  # noqa: E402
from products.professional_evidence_corpus import materialize_customer_packet  # noqa: E402
from products.professional_evidence_enrichment import enrich_customer_packet  # noqa: E402
from products.professional_evidence_executor import _blind_review, _trace_customer_records  # noqa: E402
from products.professional_evidence_projection import load_packet, sha256, slug, write_json  # noqa: E402
from products.professional_evidence_vesper_gate import _rehydrate_sources_from_quarantine  # noqa: E402
from products.vesper_web_chat import bind_professional_customer_packet  # noqa: E402


SCHEMA = "dio.evidence_review.profile_pilot_checkpoint.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _inventory(root: Path) -> list[dict[str, Any]]:
    return [
        {"path": str(path.relative_to(root)), "sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def _token(profile_id: str, passed: bool) -> str:
    stem = "".join(char if char.isalnum() else "_" for char in profile_id.upper())
    return f"DIO_{stem}_NATIVE_PILOT_{'VERIFIED' if passed else 'REFUSED'}"


def _explicit_state_contract_satisfied(expected_states: set[str], observed_states: set[str]) -> bool:
    """Fail closed unless every explicitly required review state survived execution."""
    return bool(expected_states) and expected_states.issubset(observed_states)


def _prepare_vesper(output_root: Path, spec: dict[str, Any], *, now: str) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    display_name = str(spec["display_name"])
    output_root = Path(output_root).resolve()
    case_root = output_root / slug(display_name)
    if case_root.exists():
        shutil.rmtree(case_root)

    materialized = materialize_customer_packet(display_name, output_root)
    packet_dir = Path(str(materialized["packet_dir"])).resolve()
    enrich_customer_packet(display_name, packet_dir)
    enrich_packet_from_profile_spec(packet_dir, spec)
    packet = load_packet(packet_dir)

    chat_root = case_root / "VESPER_WEB_CHAT"
    binding = bind_professional_customer_packet(packet, display_name, output_dir=chat_root, now=now)
    if binding.get("channel") != "web_chat" or binding.get("handoff_state") != "READY_FOR_PRODUCT_EXECUTION":
        raise RuntimeError(f"{display_name} Vesper front door is not ready")
    if binding.get("resolved_incarnation") != display_name:
        raise RuntimeError(f"{display_name} Vesper route drifted")
    if binding.get("examiner_data_used") is not False:
        raise RuntimeError(f"{display_name} Vesper execution consumed examiner data")

    source_bindings = _rehydrate_sources_from_quarantine(packet, chat_root)
    binding = {
        **binding,
        "source_bindings": source_bindings,
        "source_binding_count": len(source_bindings),
        "all_product_source_bytes_rehydrated_from_vesper_quarantine": bool(source_bindings)
        and all(row.get("rehydrated_into_product_packet") is True for row in source_bindings),
        "executor_may_rematerialize_packet": False,
    }
    binding["binding_fingerprint_after_rehydration"] = _fingerprint(binding)
    write_json(chat_root / "VESPER_WEB_CHAT_BINDING.json", binding)
    return binding, case_root, load_packet(packet_dir)


def run_checkpoint(output_root: Path, profile_id: str) -> dict[str, Any]:
    spec = load_profile_pilot_spec(profile_id)
    display_name = str(spec["display_name"])
    output_root = Path(output_root).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    created_at = utc_now()
    case_root = output_root / slug(display_name)

    try:
        vesper, case_root, packet = _prepare_vesper(output_root, spec, now=created_at)
        projection_dir = case_root / "PROJECTION"
        execution_dir = case_root / "EXECUTION" / f"{profile_id}_native_pilot"
        projection_dir.mkdir(parents=True, exist_ok=True)
        execution_dir.mkdir(parents=True, exist_ok=True)

        trace = _trace_customer_records(packet, projection_dir / "CUSTOMER_FACT_TRACE.json")
        result = run_profile_native_pilot(
            packet,
            execution_dir,
            spec=spec,
            operator_id=f"{profile_id}-native-pilot-checkpoint",
            now=created_at,
        )
        blind = _blind_review(case_root, result, trace)

        studio_receipt_path = Path(str(result["studio_result"]["receipt_path"]))
        expected_states = {str(value) for value in spec.get("expected_review_states") or []}
        quality = audit_profile_studio(
            studio_receipt_path,
            expected_profile_id=profile_id,
            min_separate_records=int(spec.get("min_separate_records") or 4),
            min_requirements=int(spec.get("min_requirements") or 2),
            min_issues=int(spec.get("min_issues") or 1),
            required_review_states=expected_states,
        )
        quality_path = case_root / f"{profile_id.upper()}_NATIVE_PRODUCT_QUALITY_RECEIPT.json"
        write_json(quality_path, quality)

        receipt = result.get("receipt") or {}
        source_bindings = list(vesper.get("source_bindings") or [])
        observed_states = {str(value) for value in receipt.get("review_states") or []}
        forbidden = dict(receipt.get("forbidden_outcomes_created") or {})
        min_bindings = int(spec.get("min_vesper_bindings") or (int(spec.get("min_separate_records") or 4) + 3))
        checks = {
            "vesper_web_chat_front_door": vesper.get("channel") == "web_chat" and vesper.get("handoff_state") == "READY_FOR_PRODUCT_EXECUTION",
            "vesper_resolved_profile_product": vesper.get("resolved_incarnation") == display_name,
            "vesper_examiner_truth_absent": vesper.get("examiner_data_used") is False,
            "vesper_quarantine_source_bindings_present": len(source_bindings) >= min_bindings,
            "all_sources_rehydrated_from_quarantine": bool(source_bindings) and all(row.get("rehydrated_into_product_packet") is True for row in source_bindings),
            "packet_fingerprint_preserved": receipt.get("packet_fingerprint") == packet.get("packet_fingerprint"),
            "profile_native_engine_identity": result.get("native_engine_identity") == ENGINE_IDENTITY,
            "native_capability_preserved": result.get("native_capability_preserved") is True,
            "surrogate_fallback_unused": result.get("surrogate_fallback_used") is False,
            "product_pipeline_executed": result.get("product_pipeline_executed") is True,
            "customer_assertions_not_self_supporting": receipt.get("customer_assertions_used_as_self_supporting_evidence") is False,
            "expected_review_state_preserved": _explicit_state_contract_satisfied(expected_states, observed_states),
            "declared_evidence_issues_preserved": int(receipt.get("issue_count") or 0) >= int(spec.get("min_issues") or 1),
            "blind_customer_fact_review": blind.get("passed") is True,
            "artifact_quality_verified": quality.get("acceptance_token") == QUALITY_PASS and quality.get("artifact_quality_verified") is True,
            "forbidden_outcomes_absent": bool(forbidden) and not any(forbidden.values()),
            "identity_remains_controlled_pilot_unpromoted": quality.get("identity_state") == "controlled_pilot_unpromoted",
            "canonical_portfolio_registration_not_claimed": quality.get("canonical_portfolio_registration") is False,
            "site_promotion_refused": quality.get("site_promotion_allowed") is False,
            "human_review_required": receipt.get("human_review_gate") == "NEEDS_YOU",
            "external_release_refused": receipt.get("external_release_gate") == "REFUSE",
            "authority_not_created": receipt.get("authority_created") is False,
            "external_effects_absent": receipt.get("external_effects") is False,
        }
        passed = all(checks.values())
        checkpoint = {
            "schema": SCHEMA,
            "acceptance_token": _token(profile_id, passed),
            "passed": passed,
            "created_at": created_at,
            "product": display_name,
            "profile_id": profile_id,
            "review_state_contract": "ALL_EXPLICIT_STATES",
            "expected_review_states": sorted(expected_states),
            "checks": checks,
            "vesper_binding": str(case_root / "VESPER_WEB_CHAT" / "VESPER_WEB_CHAT_BINDING.json"),
            "vesper_source_binding_count": len(source_bindings),
            "native_engine_identity": result.get("native_engine_identity"),
            "studio_engine_identity": result.get("studio_engine_identity"),
            "terminal_artifact_kind": result.get("terminal_artifact_kind"),
            "native_binding": result.get("binding_path"),
            "studio_receipt": str(studio_receipt_path),
            "quality_receipt": str(quality_path),
            "artifact_quality_verified": quality.get("artifact_quality_verified") is True,
            "failed_quality_checks": quality.get("failed_quality_checks") or [],
            "blind_review": str(case_root / "BLIND_REVIEW.json"),
            "review_states": receipt.get("review_states") or [],
            "issue_count": receipt.get("issue_count"),
            "separately_supplied_record_count": receipt.get("separately_supplied_record_count"),
            "identity_state": "controlled_pilot_unpromoted",
            "canonical_portfolio_registration": False,
            "promotion_performed": False,
            "site_promotion_allowed": False,
            "commercial_validation": "UNPROVED",
            "human_review": "NEEDS_YOU",
            "external_release": "REFUSE",
            "authority_created": False,
            "external_effects": False,
            "artifacts": _inventory(case_root),
        }
    except Exception as exc:
        case_root.mkdir(parents=True, exist_ok=True)
        error_path = case_root / f"{profile_id.upper()}_NATIVE_PILOT_ERROR.txt"
        error_path.write_text(f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}", encoding="utf-8")
        checkpoint = {
            "schema": SCHEMA,
            "acceptance_token": _token(profile_id, False),
            "passed": False,
            "created_at": created_at,
            "product": display_name,
            "profile_id": profile_id,
            "error": f"{type(exc).__name__}: {exc}",
            "error_artifact": str(error_path),
            "promotion_performed": False,
            "site_promotion_allowed": False,
            "commercial_validation": "UNPROVED",
            "human_review": "NEEDS_YOU",
            "external_release": "REFUSE",
            "authority_created": False,
            "external_effects": False,
            "artifacts": _inventory(case_root),
        }

    checkpoint["receipt_fingerprint"] = _fingerprint({key: value for key, value in checkpoint.items() if key != "receipt_fingerprint"})
    path = case_root / f"{profile_id.upper()}_NATIVE_PILOT_CHECKPOINT_RECEIPT.json"
    write_json(path, checkpoint)
    checkpoint["receipt"] = str(path)
    return checkpoint


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a declarative source-bound Evidence Review Studio profile pilot without promoting canonical identity.")
    parser.add_argument("--profile", required=True, help="Unpromoted evidence profile id with a config/evidence_review_pilots/<profile>.json spec")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_checkpoint(args.output, args.profile)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt.get("passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())