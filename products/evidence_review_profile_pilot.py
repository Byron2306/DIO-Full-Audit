from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from products.evidence_review_studio import ENGINE_IDENTITY as STUDIO_ENGINE_IDENTITY, run_profile_evidence_studio
from products.governed_case import new_case
from products.professional_evidence_projection import sha256, write_json
from products.unpromoted_evidence_profile import load_unpromoted_evidence_profile, run_unpromoted_evidence_review


ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "config" / "evidence_review_pilots"
SCHEMA = "dio.evidence_review.profile_pilot_receipt.v1"
ENGINE_IDENTITY = "products.evidence_review_profile_pilot.run_profile_native_pilot"
SPEC_SCHEMA = "dio.evidence_review.profile_pilot_spec.v1"


def _fingerprint_manifest(manifest: dict[str, Any]) -> str:
    core = {key: value for key, value in manifest.items() if key != "packet_fingerprint"}
    raw = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load_profile_pilot_spec(profile_id: str) -> dict[str, Any]:
    profile = load_unpromoted_evidence_profile(profile_id)
    path = SPEC_ROOT / f"{profile_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Evidence-review pilot spec not found: {profile_id}")
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("schema") != SPEC_SCHEMA:
        raise RuntimeError(f"{profile_id}: pilot spec schema drifted")
    if spec.get("profile_id") != profile_id:
        raise RuntimeError(f"{profile_id}: pilot spec profile identity drifted")
    if not str(spec.get("display_name") or "").strip():
        raise RuntimeError(f"{profile_id}: pilot spec requires display_name")
    if not spec.get("sources") or not spec.get("requirements") or not spec.get("evidence"):
        raise RuntimeError(f"{profile_id}: pilot spec requires sources, requirements and evidence")
    if not spec.get("issues"):
        raise RuntimeError(f"{profile_id}: pilot spec requires at least one declared evidence issue")
    expected_states = {str(value) for value in spec.get("expected_review_states") or [] if str(value)}
    if not expected_states or not expected_states.issubset({"CONTESTED", "PARTIAL", "UNKNOWN", "STALE"}):
        raise RuntimeError(f"{profile_id}: pilot spec expected review states are invalid")
    spec["product_id"] = profile["product_id"]
    spec["forbidden_outcomes"] = list(profile["forbidden_outcomes"])
    return spec


def _write_source(path: Path, source: dict[str, Any]) -> None:
    kind = str(source.get("kind") or "")
    if kind == "text":
        path.write_text(str(source.get("content") or ""), encoding="utf-8")
        return
    if kind == "csv":
        headers = [str(value) for value in source.get("headers") or []]
        rows = list(source.get("rows") or [])
        if not headers:
            raise RuntimeError(f"CSV pilot source requires headers: {path.name}")
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)
        return
    raise RuntimeError(f"Unsupported pilot source kind {kind!r} for {path.name}")


def enrich_packet_from_profile_spec(packet_dir: Path, spec: dict[str, Any]) -> dict[str, Any]:
    packet_dir = Path(packet_dir).resolve()
    manifest_path = packet_dir / "CUSTOMER_PACKET_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources_dir = packet_dir / "SOURCES"
    sources_dir.mkdir(parents=True, exist_ok=True)
    added: list[Path] = []

    for source in spec.get("sources") or []:
        filename = str(source.get("filename") or "").strip()
        if not filename or Path(filename).name != filename:
            raise RuntimeError("Pilot source filename must be a single safe filename")
        path = sources_dir / filename
        _write_source(path, source)
        added.append(path)

    by_path = {str(row.get("path") or ""): row for row in manifest.get("files") or []}
    for path in added:
        relative = str(path.relative_to(packet_dir))
        by_path[relative] = {
            "path": relative,
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
    manifest["files"] = [by_path[key] for key in sorted(by_path)]
    manifest["product_shaped_enrichment"] = True
    manifest["evidence_review_profile_pilot_enrichment"] = str(spec["profile_id"])
    manifest["enriched_file_count"] = int(manifest.get("enriched_file_count") or 0) + len(added)
    manifest["packet_fingerprint"] = _fingerprint_manifest(manifest)
    write_json(manifest_path, manifest)
    return manifest


def build_profile_review_inputs(packet: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    packet_dir = Path(packet["packet_dir"]).resolve()
    sources_dir = packet_dir / "SOURCES"
    source_paths = {
        str(source["filename"]): sources_dir / str(source["filename"])
        for source in spec.get("sources") or []
    }
    missing = [name for name, path in source_paths.items() if not path.is_file()]
    if missing:
        raise RuntimeError(f"{spec['profile_id']}: pilot source records missing: {missing}")

    requirements: list[dict[str, Any]] = []
    for row in spec.get("requirements") or []:
        filename = str(row.get("source_filename") or "")
        if filename not in source_paths:
            raise RuntimeError(f"{spec['profile_id']}: requirement source not declared: {filename}")
        key = str(row.get("requirement_key") or "").strip()
        if not key:
            raise RuntimeError(f"{spec['profile_id']}: requirement key missing")
        anchor = str(row.get("source_anchor") or key)
        requirements.append(
            {
                "requirement_key": key,
                "statement": str(row.get("statement") or "").strip(),
                "kind": str(row.get("kind") or "request"),
                "source_ref": f"customer-packet://SOURCES/{filename}#{anchor}",
                "mandatory": bool(row.get("mandatory", True)),
                "dependency_requirement_keys": [str(value) for value in row.get("dependency_requirement_keys") or []],
            }
        )

    requirement_keys = {row["requirement_key"] for row in requirements}
    evidence_inputs: list[dict[str, Any]] = []
    for row in spec.get("evidence") or []:
        filename = str(row.get("filename") or "")
        if filename not in source_paths:
            raise RuntimeError(f"{spec['profile_id']}: evidence source not declared: {filename}")
        targets = [str(value) for value in row.get("targets") or []]
        unknown = sorted(set(targets) - requirement_keys)
        if unknown:
            raise RuntimeError(f"{spec['profile_id']}: evidence targets unknown requirements: {unknown}")
        evidence_inputs.append(
            {
                "evidence_kind": "customer_source_record",
                "source_ref": f"customer-packet://SOURCES/{filename}#{str(row.get('evidence_key') or filename)}",
                "sha256": sha256(source_paths[filename]),
                "target_requirement_keys": targets,
                "relation": str(row.get("relation") or "supports"),
                "authority_grade": str(row.get("authority_grade") or "source_backed"),
                "trust_state": str(row.get("trust_state") or "trusted_for_review"),
                "freshness_state": str(row.get("freshness_state") or "current"),
            }
        )

    issues: list[dict[str, Any]] = []
    for row in spec.get("issues") or []:
        key = str(row.get("requirement_key") or "")
        if key not in requirement_keys:
            raise RuntimeError(f"{spec['profile_id']}: issue targets unknown requirement {key!r}")
        issues.append(
            {
                "requirement_key": key,
                "challenge_type": str(row.get("challenge_type") or "missing_evidence"),
                "severity": str(row.get("severity") or "material"),
                "hypothesis": str(row.get("hypothesis") or "").strip(),
                "evidence_ids": [],
            }
        )

    return {
        "requirements": requirements,
        "evidence_inputs": evidence_inputs,
        "issues": issues,
        "source_paths": {name: str(path) for name, path in source_paths.items()},
        "customer_assertions_used_as_self_supporting_evidence": False,
    }


def _new_case(packet: dict[str, Any], spec: dict[str, Any], now: str) -> dict[str, Any]:
    profile_id = str(spec["profile_id"])
    source_path = Path(packet["packet_dir"]) / f"{profile_id.upper()}_CASE_SOURCE.json"
    source = {
        "source": {
            "kind": "literal_customer_packet",
            "packet_fingerprint": packet["packet_fingerprint"],
            "manifest": "CUSTOMER_PACKET_MANIFEST.json",
            "authority_scope": "customer_authorised_processing_only",
        },
        "evidence": [],
    }
    write_json(source_path, source)
    return new_case(
        product=str(spec["product_id"]),
        job_id=f"PRO-{profile_id.upper()}-NATIVE-PILOT",
        source=source,
        source_path=source_path,
        evidence_inputs=[str(value) for value in spec.get("evidence_input_labels") or ["Vesper-rehydrated customer source records"]],
        expected_outputs=[str(value) for value in spec.get("expected_outputs") or ["typed controlled evidence review pack"]],
        required_authorities=[str(value) for value in spec.get("required_authorities") or ["customer_source_owner", "authorised_professional_reviewer"]],
        intake_state="approved",
        now=now,
    )


def run_profile_native_pilot(
    packet: dict[str, Any],
    execution_dir: Path,
    *,
    spec: dict[str, Any],
    operator_id: str,
    now: str,
    renderer=None,
) -> dict[str, Any]:
    profile_id = str(spec["profile_id"])
    display_name = str(spec["display_name"])
    inputs = build_profile_review_inputs(packet, spec)
    case = _new_case(packet, spec, now)

    def profile_runner(
        case_value: dict[str, Any],
        *,
        requirements: list[dict[str, Any]],
        evidence_inputs: list[dict[str, Any]],
        issues: list[dict[str, Any]] | None,
        output_dir: Path,
        operator_id: str,
        now: str,
    ) -> dict[str, Any]:
        return run_unpromoted_evidence_review(
            case_value,
            profile_id=profile_id,
            requirements=requirements,
            evidence_inputs=evidence_inputs,
            issues=issues,
            output_dir=output_dir,
            operator_id=operator_id,
            now=now,
        )

    result = run_profile_evidence_studio(
        packet,
        profile_id=profile_id,
        display_name=display_name,
        case=case,
        requirements=inputs["requirements"],
        evidence_inputs=inputs["evidence_inputs"],
        issues=inputs["issues"],
        output_dir=execution_dir,
        operator_id=operator_id,
        now=now,
        profile_runner=profile_runner,
        renderer=renderer,
    )
    studio_receipt = dict(result["receipt"])
    observed_states = {str(value) for value in studio_receipt.get("review_states") or []}
    expected_states = {str(value) for value in spec.get("expected_review_states") or []}
    if not expected_states.intersection(observed_states):
        raise RuntimeError(
            f"{profile_id}: expected review state {sorted(expected_states)} absent from {sorted(observed_states)}"
        )
    if int(studio_receipt.get("issue_count") or 0) < int(spec.get("min_issues") or 1):
        raise RuntimeError(f"{profile_id}: profile pilot did not preserve the required evidence issues")
    forbidden = dict(studio_receipt.get("forbidden_outcomes_created") or {})
    if set(forbidden) != {str(value) for value in spec.get("forbidden_outcomes") or []} or any(forbidden.values()):
        raise RuntimeError(f"{profile_id}: forbidden outcome boundary drifted")

    pilot_receipt = {
        "schema": SCHEMA,
        "engine_identity": ENGINE_IDENTITY,
        "studio_engine_identity": STUDIO_ENGINE_IDENTITY,
        "profile_id": profile_id,
        "product_id": spec["product_id"],
        "display_name": display_name,
        "packet_fingerprint": packet["packet_fingerprint"],
        "studio_receipt": result["receipt_path"],
        "bundle": result["bundle"],
        "format_core_receipt": result["format_core_receipt"],
        "semantic_content": result["semantic_content"],
        "separately_supplied_record_count": studio_receipt["separately_supplied_record_count"],
        "requirement_count": studio_receipt["requirement_count"],
        "issue_count": studio_receipt["issue_count"],
        "open_question_count": studio_receipt["open_question_count"],
        "review_states": studio_receipt["review_states"],
        "expected_review_states": sorted(expected_states),
        "forbidden_outcomes_created": forbidden,
        "customer_assertions_used_as_self_supporting_evidence": False,
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "product_pipeline_executed": True,
        "domain_action_executed": False,
        "identity_state": "controlled_pilot_unpromoted",
        "canonical_portfolio_registration": False,
        "promotion_performed": False,
        "site_promotion_allowed": False,
        "commercial_validation": "UNPROVED",
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "provider_called": False,
    }
    pilot_path = Path(execution_dir) / f"{profile_id.upper()}_NATIVE_PILOT_RECEIPT.json"
    write_json(pilot_path, pilot_receipt)

    binding = {
        "schema": "dio.professional_evidence.profile_native_binding.v1",
        "profile_id": profile_id,
        "product_id": spec["product_id"],
        "display_name": display_name,
        "native_engine_identity": ENGINE_IDENTITY,
        "studio_engine_identity": STUDIO_ENGINE_IDENTITY,
        "packet_fingerprint": packet["packet_fingerprint"],
        "native_pilot_receipt": str(pilot_path),
        "studio_receipt": result["receipt_path"],
        "bundle": result["bundle"],
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    binding_path = Path(execution_dir) / f"{profile_id.upper()}_NATIVE_ROUTE_BINDING.json"
    write_json(binding_path, binding)

    return {
        "native_engine_identity": ENGINE_IDENTITY,
        "studio_engine_identity": STUDIO_ENGINE_IDENTITY,
        "product_id": spec["product_id"],
        "profile_id": profile_id,
        "terminal_artifact_kind": "profile_driven_native_typed_evidence_review_bundle",
        "product_pipeline_executed": True,
        "domain_action_executed": False,
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "receipt": pilot_receipt,
        "binding_path": str(binding_path),
        "studio_result": result,
    }


__all__ = [
    "ENGINE_IDENTITY",
    "SCHEMA",
    "SPEC_SCHEMA",
    "build_profile_review_inputs",
    "enrich_packet_from_profile_spec",
    "load_profile_pilot_spec",
    "run_profile_native_pilot",
]
