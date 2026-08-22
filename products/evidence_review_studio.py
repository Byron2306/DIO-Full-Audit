from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Callable

from adapters.format_core.renderer import render_semantic_asset
from products.professional_evidence_projection import sha256, write_json
from products.unpromoted_evidence_profile import load_unpromoted_evidence_profile

SCHEMA = "dio.evidence_review_studio.receipt.v1"
ENGINE_IDENTITY = "products.evidence_review_studio.run_profile_evidence_studio"

_META_SOURCE_NAMES = {"01_customer_context.md", "02_evidence_register.csv", "03_exception_note.md"}


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _inventory_sources(packet: dict[str, Any]) -> list[dict[str, Any]]:
    packet_dir = Path(packet["packet_dir"]).resolve()
    rows: list[dict[str, Any]] = []
    for item in packet.get("manifest", {}).get("files") or []:
        relative = str(item.get("path") or "")
        if not relative.startswith("SOURCES/"):
            continue
        path = (packet_dir / relative).resolve()
        if packet_dir not in path.parents or not path.is_file():
            raise RuntimeError(f"Evidence Review Studio source is missing: {relative}")
        digest = sha256(path)
        if digest != str(item.get("sha256") or ""):
            raise RuntimeError(f"Evidence Review Studio source hash drifted: {relative}")
        rows.append({
            "path": relative,
            "filename": path.name,
            "sha256": digest,
            "bytes": path.stat().st_size,
            "source_role": "metadata_container" if path.name.casefold() in _META_SOURCE_NAMES else "separately_supplied_record",
        })
    return sorted(rows, key=lambda row: row["path"])


def _evidence_index(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in case.get("evidence") or []:
        evidence_id = str(row.get("evidence_id") or "").strip()
        if not evidence_id:
            continue
        source_ref = str(row.get("source_ref") or "").strip()
        source_path = source_ref
        if "customer-packet://" in source_path:
            source_path = source_path.split("customer-packet://", 1)[1]
        if "#" in source_path:
            source_path = source_path.split("#", 1)[0]
        index[evidence_id] = {
            "evidence_id": evidence_id,
            "source_ref": source_ref,
            "source_path": source_path,
            "sha256": str(row.get("sha256") or ""),
            "trust_state": str(row.get("trust_state") or ""),
            "freshness_state": str(row.get("freshness_state") or ""),
            "authority_grade": str(row.get("authority_grade") or ""),
        }
    return index


def _requirement_evidence_refs(matrix: list[dict[str, Any]], evidence_index: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    mapped: dict[str, list[dict[str, Any]]] = {}
    for row in matrix:
        key = str(row.get("requirement_key") or "")
        mapped[key] = [
            dict(evidence_index[str(evidence_id)])
            for evidence_id in row.get("evidence_ids") or []
            if str(evidence_id) in evidence_index
        ]
    return mapped


def _display_evidence_paths(rows: list[dict[str, Any]]) -> str:
    paths = [str(row.get("source_path") or row.get("source_ref") or row.get("evidence_id") or "") for row in rows]
    return "; ".join(path for path in paths if path) or "No mapped source record"


def _semantic_content(
    *,
    display_name: str,
    profile: dict[str, Any],
    packet: dict[str, Any],
    source_inventory: list[dict[str, Any]],
    review_pack: dict[str, Any],
    evidence_index: dict[str, dict[str, Any]],
    requirement_evidence_refs: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    customer = dict((packet.get("intake") or {}).get("customer") or {})
    buyer = str(customer.get("buyer_role") or packet.get("intake", {}).get("buyer") or "authorised professional reviewer")
    matrix = list(review_pack.get("requirement_evidence_matrix") or [])
    issues = list(review_pack.get("issue_register") or [])
    questions = list(review_pack.get("open_question_list") or [])
    forbidden = sorted(str(name) for name in (profile.get("forbidden_outcomes") or []))

    blocks: list[dict[str, Any]] = [
        {"block_id": "TITLE", "type": "title", "text": f"DIO {display_name} Controlled Evidence Review Pack"},
        {"block_id": "PURPOSE", "type": "heading", "level": 1, "text": "Review purpose and authority boundary"},
        {"block_id": "PURPOSE-TEXT", "type": "paragraph", "text": (
            f"This controlled {display_name} pack organises customer-supplied requirements, source records, evidence relationships, exceptions and open questions for {buyer}. "
            "It is a preparation and review aid. It does not create a domain decision, score, approval, certification, attestation, audit opinion, assurance conclusion or release authority."
        )},
        {"block_id": "SOURCES", "type": "heading", "level": 1, "text": "Customer source inventory and custody"},
        {"block_id": "SOURCE-TABLE", "type": "table", "title": "Customer source inventory",
         "headers": ["File", "Role", "Bytes", "SHA-256"],
         "rows": [[row["path"], row["source_role"], str(row["bytes"]), row["sha256"]] for row in source_inventory]},
        {"block_id": "SOURCE-NOTE", "type": "paragraph", "text": "Hashes bind the exact customer bytes used by the review. A hash establishes byte identity only; it does not establish authenticity, completeness, legal effect, control effectiveness or professional authority."},
        {"block_id": "EVIDENCE-INDEX", "type": "heading", "level": 1, "text": "Evidence provenance index"},
        {"block_id": "EVIDENCE-INDEX-TABLE", "type": "table", "title": "Evidence provenance index",
         "headers": ["Evidence ID", "Customer source", "Trust state", "Freshness", "Authority grade"],
         "rows": [[row["evidence_id"], row["source_ref"], row["trust_state"], row["freshness_state"], row["authority_grade"]]
                  for row in sorted(evidence_index.values(), key=lambda item: item["evidence_id"])]},
        {"block_id": "EVIDENCE-INDEX-NOTE", "type": "paragraph", "text": "The evidence index maps DIO review identifiers back to customer source references. Mapping identifies which supplied record was reviewed; it does not establish that the record proves a control, exception, conclusion or professional finding."},
        {"block_id": "MATRIX", "type": "heading", "level": 1, "text": "Requirement and evidence review matrix"},
        {"block_id": "MATRIX-TABLE", "type": "table", "title": "Requirement and evidence review matrix",
         "headers": ["Requirement", "Review state", "Statement", "Mapped customer evidence", "Open issues"],
         "rows": [[
             str(row.get("requirement_key") or ""),
             str(row.get("review_state") or ""),
             str(row.get("statement") or ""),
             _display_evidence_paths(requirement_evidence_refs.get(str(row.get("requirement_key") or ""), [])),
             str(len(row.get("open_challenge_ids") or [])),
         ] for row in matrix]},
        {"block_id": "MATRIX-NOTE", "type": "paragraph", "text": "Mapped customer evidence is a deterministic review linkage, not a conclusion that the requirement is satisfied. Review state remains governed by open challenges, source trust, freshness and human professional judgement."},
        {"block_id": "ISSUES", "type": "heading", "level": 1, "text": "Exceptions, contradictions and review issues"},
    ]
    if issues:
        blocks.append({
            "block_id": "ISSUE-TABLE", "type": "table", "title": "Open issue register",
            "headers": ["Requirement", "Type", "Severity", "Issue", "Review evidence set"],
            "rows": [[
                str(row.get("requirement_key") or ""),
                str(row.get("challenge_type") or ""),
                str(row.get("severity") or ""),
                str(row.get("hypothesis") or ""),
                _display_evidence_paths(requirement_evidence_refs.get(str(row.get("requirement_key") or ""), [])),
            ] for row in issues],
        })
    else:
        blocks.append({"block_id": "ISSUE-NONE", "type": "paragraph", "text": "No machine-surfaced review issue is present. Absence of a detected issue is not a professional conclusion and does not establish completeness or effectiveness."})
    blocks.extend([
        {"block_id": "QUESTIONS", "type": "heading", "level": 1, "text": "Open questions for authorised human review"},
        {"block_id": "QUESTION-LIST", "type": "bullet_list",
         "items": [f"{row.get('requirement_key')}: {row.get('question')} [{row.get('state')}]" for row in questions]
                  or ["No generated question. Human review remains required."]},
        {"block_id": "FORBIDDEN", "type": "heading", "level": 1, "text": "Outcomes this product does not create"},
        {"block_id": "FORBIDDEN-LIST", "type": "bullet_list", "items": forbidden},
        {"block_id": "RELEASE", "type": "heading", "level": 1, "text": "Release gate"},
        {"block_id": "RELEASE-TEXT", "type": "paragraph", "text": "HUMAN REVIEW REQUIRED. EXTERNAL RELEASE REFUSED. Final professional judgement and every consequential external action remain with an authorised human."},
    ])
    return {
        "schema": "dio.semantic_content.v1",
        "object_id": f"evidence-review-{profile['profile_id']}-controlled-pilot",
        "version": "1.1.0",
        "title": f"DIO {display_name} Controlled Evidence Review Pack",
        "source_language": "English",
        "context": {"product": display_name, "artifact_type": "controlled_evidence_review_pack", "audience": buyer},
        "blocks": blocks,
        "translations": {},
    }


def _default_renderer(content: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    return render_semantic_asset(content, out_dir, style_profile="dio_professional", delivery_profile="editable_review",
                                 channels=["docx", "pdf", "html"], release_mode=False)


def _pack_bundle(*, bundle_path: Path, packet: dict[str, Any], studio_root: Path, baseline_root: Path,
                 rendered_outputs: list[dict[str, Any]]) -> None:
    packet_dir = Path(packet["packet_dir"]).resolve()
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((packet_dir / "SOURCES").rglob("*")):
            if path.is_file():
                archive.write(path, f"sources/{path.name}")
        for path in sorted(baseline_root.rglob("*")):
            if path.is_file():
                archive.write(path, f"baseline/{path.relative_to(baseline_root)}")
        for relative in ["EVIDENCE_REVIEW_STUDIO_SEMANTIC_CONTENT.json", "EVIDENCE_REVIEW_STUDIO_RECEIPT.json"]:
            path = studio_root / relative
            if path.is_file():
                archive.write(path, relative)
        render_root = studio_root / "rendered"
        if render_root.is_dir():
            for path in sorted(render_root.rglob("*")):
                if path.is_file():
                    archive.write(path, f"rendered/{path.relative_to(render_root)}")


def run_profile_evidence_studio(
    packet: dict[str, Any], *, profile_id: str, display_name: str, case: dict[str, Any],
    requirements: list[dict[str, Any]], evidence_inputs: list[dict[str, Any]], issues: list[dict[str, Any]],
    output_dir: Path, operator_id: str, now: str, profile_runner: Callable[..., dict[str, Any]],
    renderer: Callable[[dict[str, Any], Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profile = load_unpromoted_evidence_profile(profile_id)
    if profile.get("identity_state") != "genuine_profile_extension_unpromoted" or profile.get("canonical_portfolio_registration") is not False:
        raise RuntimeError(f"{profile_id}: Evidence Review Studio may only run an explicitly unpromoted profile pilot")
    output_dir = Path(output_dir).resolve()
    baseline_root = output_dir / "baseline_review"
    studio_root = output_dir / "evidence_review_studio"
    for directory in (baseline_root, studio_root):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=False)

    baseline = profile_runner(case, requirements=requirements, evidence_inputs=evidence_inputs, issues=issues,
                              output_dir=baseline_root, operator_id=operator_id, now=now)
    baseline_receipt = dict(baseline.get("receipt") or {})
    review_pack = dict(baseline.get("review_pack") or {})
    baseline_case = dict(baseline.get("case") or case)
    if baseline_receipt.get("internal_processing") != "COMPLETE":
        raise RuntimeError(f"{profile_id}: controlled evidence semantics did not complete")
    if baseline_receipt.get("human_review_gate") != "NEEDS_YOU" or baseline_receipt.get("external_release_gate") != "REFUSE":
        raise RuntimeError(f"{profile_id}: controlled evidence authority boundary drifted")
    if baseline_receipt.get("authority_created") is not False or baseline_receipt.get("external_effects") is not False:
        raise RuntimeError(f"{profile_id}: controlled evidence review created authority or external effects")
    forbidden = dict(baseline_receipt.get("forbidden_outcomes_created") or {})
    expected_forbidden = {str(name) for name in profile.get("forbidden_outcomes") or []}
    if set(forbidden) != expected_forbidden or any(forbidden.values()):
        raise RuntimeError(f"{profile_id}: forbidden outcome boundary drifted")

    source_inventory = _inventory_sources(packet)
    separately_supplied = [row for row in source_inventory if row["source_role"] == "separately_supplied_record"]
    if not separately_supplied:
        raise RuntimeError(f"{profile_id}: no separately supplied evidence records reached Evidence Review Studio")
    evidence_index = _evidence_index(baseline_case)
    matrix = list(review_pack.get("requirement_evidence_matrix") or [])
    requirement_evidence_refs = _requirement_evidence_refs(matrix, evidence_index)
    if matrix and any(not requirement_evidence_refs.get(str(row.get("requirement_key") or "")) for row in matrix):
        raise RuntimeError(f"{profile_id}: requirement evidence mapping could not be resolved to customer source references")

    semantic = _semantic_content(display_name=display_name, profile=profile, packet=packet,
                                 source_inventory=source_inventory, review_pack=review_pack,
                                 evidence_index=evidence_index, requirement_evidence_refs=requirement_evidence_refs)
    semantic_path = studio_root / "EVIDENCE_REVIEW_STUDIO_SEMANTIC_CONTENT.json"
    write_json(semantic_path, semantic)
    render_root = studio_root / "rendered"
    format_receipt = (renderer or _default_renderer)(semantic, render_root)
    if not bool((format_receipt.get("qa") or {}).get("passed")):
        raise RuntimeError(f"{profile_id}: Format Core QA failed")
    outputs = list(format_receipt.get("outputs") or [])
    channels = {str(row.get("channel") or "") for row in outputs}
    if not {"docx", "pdf", "html"}.issubset(channels):
        raise RuntimeError(f"{profile_id}: Evidence Review Studio did not render DOCX, PDF and HTML")

    named_mapping = {
        key: [{
            "evidence_id": row["evidence_id"], "source_ref": row["source_ref"], "source_path": row["source_path"],
            "sha256": row["sha256"], "trust_state": row["trust_state"], "freshness_state": row["freshness_state"],
        } for row in rows]
        for key, rows in requirement_evidence_refs.items()
    }
    receipt = {
        "schema": SCHEMA, "engine_identity": ENGINE_IDENTITY, "profile_id": profile_id,
        "product_id": profile["product_id"], "display_name": display_name, "processed_at": now,
        "packet_fingerprint": packet["packet_fingerprint"], "source_inventory": source_inventory,
        "separately_supplied_record_count": len(separately_supplied),
        "evidence_provenance_index": sorted(evidence_index.values(), key=lambda row: row["evidence_id"]),
        "requirement_evidence_source_map": named_mapping,
        "named_evidence_mapping_present": bool(named_mapping) and all(named_mapping.values()),
        "requirement_count": len(matrix), "issue_count": len(review_pack.get("issue_register") or []),
        "open_question_count": len(review_pack.get("open_question_list") or []),
        "review_states": sorted({str(row.get("review_state") or "") for row in matrix}),
        "forbidden_outcomes_created": forbidden, "customer_assertions_used_as_self_supporting_evidence": False,
        "baseline_controlled_review_preserved": True, "format_core_qa_passed": True, "rendered_outputs": outputs,
        "identity_state": "controlled_pilot_unpromoted", "canonical_portfolio_registration": False,
        "promotion_performed": False, "site_promotion_allowed": False, "commercial_validation": "UNPROVED",
        "human_review_gate": "NEEDS_YOU", "external_release_gate": "REFUSE", "domain_decision_created": False,
        "domain_score_created": False, "authority_created": False, "external_effects": False, "provider_called": False,
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    receipt_path = studio_root / "EVIDENCE_REVIEW_STUDIO_RECEIPT.json"
    write_json(receipt_path, receipt)
    bundle = studio_root / f"{profile_id.upper()}_CONTROLLED_REVIEW_BUNDLE.zip"
    _pack_bundle(bundle_path=bundle, packet=packet, studio_root=studio_root, baseline_root=baseline_root, rendered_outputs=outputs)
    if not bundle.is_file() or bundle.stat().st_size < 20000:
        raise RuntimeError(f"{profile_id}: controlled review bundle is missing or too small")
    receipt["bundle"] = str(bundle)
    receipt["bundle_sha256"] = sha256(bundle)
    receipt["bundle_bytes"] = bundle.stat().st_size
    write_json(receipt_path, receipt)
    return {
        "engine_identity": ENGINE_IDENTITY, "product_id": profile["product_id"], "profile_id": profile_id,
        "terminal_artifact_kind": "typed_controlled_evidence_review_bundle", "product_pipeline_executed": True,
        "domain_action_executed": False, "native_capability_preserved": True, "surrogate_fallback_used": False,
        "receipt": receipt, "receipt_path": str(receipt_path), "bundle": str(bundle),
        "format_core_receipt": str(render_root / "FORMAT_CORE_RECEIPT.json"), "semantic_content": str(semantic_path),
        "baseline_result": baseline,
    }


__all__ = ["ENGINE_IDENTITY", "SCHEMA", "run_profile_evidence_studio"]