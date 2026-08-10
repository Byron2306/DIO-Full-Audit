from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
VENDORED_SOPHIA_ROOT = REPO_ROOT / "cross_folder_variants" / "Integritas-Mechanicus" / "A_CODE"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _support_state(label: Any, entailment: Any) -> str:
    support = _norm(label).lower().replace("_", " ")
    ent = _norm(entailment).lower().replace("_", " ")
    if any(token in ent for token in ("contradict", "does not support", "not supported")):
        return "does_not_support"
    if support in {"supports", "directly supports", "direct support"}:
        return "support_ready"
    if "partial" in support or "partial" in ent:
        return "partial_support"
    if support in {"background only", "background", "context only"}:
        return "background_only"
    if not support:
        return "unmapped"
    return support.replace(" ", "_")


def _risk_severity(claim_risk: str, state: str) -> str:
    risk = str(claim_risk or "medium").lower()
    if state in {"does_not_support", "unmapped"} and risk == "high":
        return "critical_review"
    if state in {"does_not_support", "unmapped", "background_only"} or risk == "high":
        return "high"
    if state == "partial_support" or risk == "medium":
        return "medium"
    return "low"


def build_scholarly_risk_register(
    claim_payload: dict[str, Any],
    reference_audit: dict[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(claim_payload.get("claims") or [], 1):
        claim = item.get("claim_record") or {}
        mapping = item.get("source_map") or {}
        candidates = list(mapping.get("results") or [])
        best = candidates[0] if candidates else {}
        state = _support_state(best.get("support_label"), best.get("entailment_status"))
        risk = str(claim.get("evidence_risk") or "medium")
        problems: list[str] = []
        if not candidates:
            problems.append("no_candidate_source_mapping")
        if state == "background_only":
            problems.append("candidate_is_background_not_direct_support")
        elif state == "partial_support":
            problems.append("candidate_only_partially_supports_claim")
        elif state == "does_not_support":
            problems.append("candidate_does_not_support_claim")
        if not best.get("exact_span"):
            problems.append("no_visible_source_span")
        if not best.get("page_locator"):
            problems.append("no_page_locator_visible")
        warnings = [str(value) for value in (best.get("entailment_warnings") or []) if str(value).strip()]
        problems.extend(f"entailment:{value}" for value in warnings[:4])
        rows.append({
            "risk_id": f"C{index}",
            "kind": "claim_evidence_fit",
            "severity": _risk_severity(risk, state),
            "claim": claim.get("claim"),
            "claim_type": claim.get("claim_type"),
            "evidence_risk": risk,
            "evidence_standard": claim.get("evidence_standard"),
            "support_state": state,
            "candidate_source": best.get("source_name"),
            "support_label": best.get("support_label"),
            "entailment_status": best.get("entailment_status"),
            "entailment_score": best.get("entailment_score"),
            "source_quality_score": best.get("quality_score"),
            "source_quality_rubric": best.get("source_quality_rubric") or {},
            "visible_span": best.get("exact_span"),
            "page_locator": best.get("page_locator"),
            "problems": problems,
            "human_action": (
                "Inspect the full source and either narrow the claim, replace/add evidence, or make the warrant and limitation explicit."
                if problems
                else "Verify the full source before retaining the claim as supported."
            ),
        })

    for row in reference_audit.get("missing_from_reference_list") or []:
        rows.append({
            "risk_id": f"R-MISSING-{len(rows)+1}",
            "kind": "reference_integrity",
            "severity": "high",
            "citation": f"{row.get('author')} ({row.get('year')})",
            "problems": ["cited_in_text_but_missing_from_reference_list"],
            "human_action": "Verify the cited work and add a complete reference entry or remove/correct the citation.",
        })
    for row in reference_audit.get("reference_list_entries_not_cited") or []:
        rows.append({
            "risk_id": f"R-UNCITED-{len(rows)+1}",
            "kind": "reference_integrity",
            "severity": "medium",
            "reference": row.get("entry"),
            "problems": ["reference_list_entry_not_cited_in_manuscript"],
            "human_action": "Confirm whether the reference belongs in the manuscript and cite or remove it deliberately.",
        })
    for duplicate in reference_audit.get("duplicate_entries") or []:
        rows.append({
            "risk_id": f"R-DUP-{len(rows)+1}",
            "kind": "reference_integrity",
            "severity": "medium",
            "reference": duplicate,
            "problems": ["duplicate_reference_entry"],
            "human_action": "Resolve the duplicate after checking whether the records are truly identical.",
        })

    counts = Counter(str(row.get("severity") or "unknown") for row in rows)
    open_rows = [row for row in rows if row.get("problems")]
    return {
        "schema": "dio.sophia_scholarly_risk_register.v1",
        "created_at": utc_now(),
        "state": "attention_required" if open_rows else "clear_first_pass",
        "counts": dict(counts),
        "risk_count": len(rows),
        "open_risk_count": len(open_rows),
        "risks": rows,
        "boundary": (
            "These are scholarly review risks, not findings of misconduct. Sophia does not infer plagiarism, fabrication, or authorship fraud from these signals."
        ),
    }


def build_verification_queue(claim_payload: dict[str, Any], reference_audit: dict[str, Any]) -> dict[str, Any]:
    queue: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, item in enumerate(claim_payload.get("claims") or [], 1):
        claim = item.get("claim_record") or {}
        for rank, source in enumerate((item.get("source_map") or {}).get("results") or [], 1):
            state = _support_state(source.get("support_label"), source.get("entailment_status"))
            key = (str(source.get("doi") or ""), str(source.get("url") or ""), str(source.get("source_name") or ""))
            if key in seen:
                continue
            seen.add(key)
            queue.append({
                "queue_id": f"V{len(queue)+1}",
                "claim_id": f"C{index}",
                "claim_type": claim.get("claim_type"),
                "evidence_standard": claim.get("evidence_standard"),
                "source_rank": rank,
                "source_name": source.get("source_name"),
                "authors": source.get("authors") or [],
                "year": source.get("year"),
                "doi": source.get("doi"),
                "url": source.get("url"),
                "metadata_status": source.get("metadata_status"),
                "provenance_status": source.get("provenance_status"),
                "page_status": source.get("page_status"),
                "support_label": source.get("support_label"),
                "support_state": state,
                "entailment_status": source.get("entailment_status"),
                "source_quality_score": source.get("quality_score"),
                "verification_required": True,
                "verification_task": (
                    "Open the full publication. Verify bibliographic metadata, locate the exact passage, and decide whether the evidence meets this claim's evidence standard."
                ),
            })
    for row in reference_audit.get("reference_entries") or []:
        if row.get("issues") or (row.get("style_check") or {}).get("fail_count"):
            key = (str(row.get("doi") or ""), "", str(row.get("entry") or ""))
            if key in seen:
                continue
            seen.add(key)
            queue.append({
                "queue_id": f"V{len(queue)+1}",
                "claim_id": None,
                "source_name": row.get("entry"),
                "doi": row.get("doi"),
                "support_state": "reference_metadata_check",
                "verification_required": True,
                "verification_task": "Verify the full bibliographic record and correct only after checking the publisher or scholarly index.",
            })
    return {
        "schema": "dio.sophia_source_verification_queue.v1",
        "created_at": utc_now(),
        "queue_count": len(queue),
        "items": queue,
        "release_rule": "No queue item is promoted from lead to verified support automatically.",
    }


def _find_sophia_root(preferred_root: Path | None) -> Path:
    candidates = [preferred_root, VENDORED_SOPHIA_ROOT]
    for root in candidates:
        if root and (Path(root) / "arda_os" / "backend" / "services" / "sophia_project_store.py").is_file():
            return Path(root)
    raise FileNotFoundError("Sophia project-store engine was not found in the requested or vendored root.")


def _load_project_store(preferred_root: Path | None):
    root = _find_sophia_root(preferred_root)
    arda_root = (root / "arda_os").resolve()
    if str(arda_root) not in sys.path:
        sys.path.insert(0, str(arda_root))
    module_path = arda_root / "backend" / "services" / "sophia_project_store.py"
    spec = importlib.util.spec_from_file_location("sophia_c9_project_store", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load SophiaProjectStore from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SophiaProjectStore, root


def _map_claim_records(claim_payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, item in enumerate(claim_payload.get("claims") or [], 1):
        claim = item.get("claim_record") or {}
        results = list((item.get("source_map") or {}).get("results") or [])
        source = results[0] if results else {}
        state = _support_state(source.get("support_label"), source.get("entailment_status"))
        status = {
            "support_ready": "supported",
            "partial_support": "partial",
            "background_only": "needs-source",
            "does_not_support": "unsupported",
            "unmapped": "needs-source",
        }.get(state, "open")
        limitations = [str(value) for value in (source.get("entailment_warnings") or []) if str(value).strip()]
        records.append({
            "record_id": f"C{index}",
            "claim": claim.get("claim"),
            "claim_type": claim.get("claim_type"),
            "evidence_standard": claim.get("evidence_standard"),
            "evidence_risk": claim.get("evidence_risk"),
            "source_name": source.get("source_name") or "Unassigned",
            "support_label": source.get("support_label") or "unmapped",
            "exact_span": source.get("exact_span") or "",
            "warrant": "",
            "limitation": "; ".join(limitations),
            "citation": source.get("apa_candidate") or source.get("url") or "",
            "doi": source.get("doi") or "",
            "url": source.get("url") or "",
            "quality_score": source.get("quality_score"),
            "relevance": source.get("relevance"),
            "source_quality_rubric": source.get("source_quality_rubric") or {},
            "status": status,
            "entailment_status": source.get("entailment_status") or "",
            "entailment_score": source.get("entailment_score"),
            "semantic_similarity": source.get("semantic_score"),
            "support_source": "commercial_review_claim_source_ledger",
            "page_locator": source.get("page_locator") or "",
            "page_status": source.get("page_status") or "",
        })
    return records


def _integrity_findings(risk_register: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    for row in risk_register.get("risks") or []:
        prefix = "SUPPORT GAP" if row.get("kind") == "claim_evidence_fit" else "REFERENCE GAP"
        risk_id = row.get("risk_id") or "risk"
        problems = ", ".join(row.get("problems") or []) or "review required"
        findings.append(f"{prefix}: {risk_id} - {problems}")
    return findings[:40]


def build_speculum_integrity_record(
    *,
    job_id: str,
    output_dir: Path,
    manuscript_path: Path,
    sophia_root: Path | None,
    claim_payload: dict[str, Any],
    literature_payload: dict[str, Any],
    commentary: dict[str, Any],
    risk_register: dict[str, Any],
) -> dict[str, Any]:
    ProjectStore, resolved_root = _load_project_store(sophia_root)
    state_root = output_dir / ".c9_integrity_state"
    store = ProjectStore(state_root)
    manuscript_hash = sha256_file(manuscript_path)
    text = ""
    try:
        from adapters.sophia.review_pipeline import extract_document_text
        text, _parser = extract_document_text(manuscript_path)
    except Exception:
        text = manuscript_path.read_text(encoding="utf-8", errors="replace") if manuscript_path.suffix.lower() in {".txt", ".md"} else ""
    store.upsert_project(
        project_id=job_id,
        session_token="",
        document_name=manuscript_path.name,
        document_hash=manuscript_hash,
        mandos_category="writing_desk",
    )
    version = store.add_draft_version(project_id=job_id, draft_text=text, source="dio_sophia_c9_product_review")
    store.append_retrieved_sources(
        project_id=job_id,
        sources=literature_payload.get("deduplicated_sources") or [],
    )
    source_records = []
    for item in claim_payload.get("claims") or []:
        for source in (item.get("source_map") or {}).get("results") or []:
            source_records.append({
                "name": source.get("source_name") or "Unnamed source",
                "category": source.get("source_type") or "scholarly_lead",
                "text": source.get("exact_span") or "",
            })
    store.append_source_records(project_id=job_id, sources=source_records)
    claim_records = _map_claim_records(claim_payload)
    store.append_claim_records(project_id=job_id, draft_version_id=version["version_id"], records=claim_records)
    release_ledger = {
        "mandos_judgment": commentary.get("mandos_judgment") or {},
        "article_conformity": commentary.get("article_conformity") or {},
        "validation": commentary.get("validation") or {},
        "provider": commentary.get("provider"),
        "model": commentary.get("model"),
    }
    store.append_intervention_record(
        project_id=job_id,
        draft_version_id=version["version_id"],
        record={
            "task": "commercial_scholarly_integrity_review",
            "task_label": "Sophia Scholarly Integrity Review",
            "selected_excerpt": "Whole manuscript section under governed review",
            "findings": _integrity_findings(risk_register),
            "pedagogical_move": "Office: integrity auditor. Move: claim classification, evidence fit, warrant/limitation check, then authorship handback.",
            "next_revision_move": "Resolve the highest-severity support and reference risks first, then re-run the revision integrity check.",
            "authorship_boundary": "Sophia diagnoses evidence and integrity risk; the human author decides all final wording, sources, interpretation, and submission choices.",
            "pedagogical_plan": {
                "selected_office": "integrity_auditor",
                "assessment_layer": "formative",
                "zpd_level": "advanced_academic",
                "bloom_target": "evaluate",
                "scaffold_intensity": "medium",
                "feedback_style": "claim_evidence_warrant_limitation",
                "pedagogical_need_state": "scholarly_integrity_review",
            },
            "response_source": "hybrid_model_with_constitutional_judgment" if commentary.get("provider") else "runtime_synthesis",
            "response_source_detail": f"{commentary.get('provider') or 'local'} / {commentary.get('model') or 'deterministic'}",
            "repair_steps": commentary.get("repair_steps") or [],
            "response_release_ledger": release_ledger,
            "repair_without_rewriting": [
                "verify source", "narrow or qualify claim", "make warrant explicit", "add limitation", "correct reference metadata"
            ],
        },
    )
    record = store.export_integrity_record(project_id=job_id)
    record["c9_product_binding"] = {
        "job_id": job_id,
        "source_sha256": manuscript_hash,
        "sophia_root": str(resolved_root),
        "commercial_pack": str(output_dir),
        "authorship_metric_boundary": "The Authorship Preservation Index is an unvalidated engineering signal, not a forensic authorship or misconduct detector.",
    }
    return record


def build_integrity_passport(
    *,
    job_id: str,
    output_dir: Path,
    manuscript_path: Path,
    commentary: dict[str, Any],
    receipt: dict[str, Any],
    speculum_record: dict[str, Any],
    risk_register: dict[str, Any],
) -> dict[str, Any]:
    generated = []
    for path in sorted(output_dir.iterdir()):
        if path.is_file() and path.suffix.lower() not in {".zip"}:
            generated.append({"name": path.name, "sha256": sha256_file(path)})
    articles = ((commentary.get("article_conformity") or {}).get("summary") or {})
    return {
        "schema": "dio.sophia_integrity_passport.v1",
        "created_at": utc_now(),
        "job_id": job_id,
        "manuscript": {
            "name": manuscript_path.name,
            "sha256": sha256_file(manuscript_path),
            "word_count": (receipt.get("source") or {}).get("word_count"),
        },
        "governed_review": {
            "provider": commentary.get("provider"),
            "model": commentary.get("model"),
            "reasoned_integrity_lane": commentary.get("source") == "reasoned_integrity_lane",
            "grounding_passed": bool((commentary.get("validation") or {}).get("passed")),
            "mandos_passed": bool((commentary.get("mandos_judgment") or {}).get("passed")),
            "genesis_articles_passed": bool(articles.get("all_passed")),
            "repair_applied": bool(commentary.get("repair_applied")),
            "repair_steps": commentary.get("repair_steps") or [],
        },
        "scholarly_risk_state": risk_register.get("state"),
        "open_risk_count": risk_register.get("open_risk_count"),
        "speculum_integrity_record_hash": speculum_record.get("integrity_record_hash"),
        "authorship_preservation": {
            "index": speculum_record.get("authorship_preservation_index") or {},
            "boundary": "Engineering signal only. It does not prove who authored the text and must not be used as a misconduct detector.",
        },
        "output_hashes": generated,
        "authority": {
            "human_author_owns_final_wording": True,
            "human_reviewer_required_before_delivery": True,
            "misconduct_finding_authority": False,
            "automatic_source_promotion": False,
        },
    }


def markdown_risk_register(payload: dict[str, Any]) -> str:
    lines = [
        "# Sophia Scholarly Risk Register",
        "",
        f"State: **{payload.get('state')}**",
        f"Open scholarly risks: **{payload.get('open_risk_count')}**",
        "",
        "> These are review risks, not findings of misconduct.",
        "",
    ]
    for row in payload.get("risks") or []:
        lines.extend([
            f"## {row.get('risk_id')} · {row.get('severity')}",
            "",
            f"- Kind: {row.get('kind')}",
            f"- Claim/citation: {row.get('claim') or row.get('citation') or row.get('reference') or 'n/a'}",
            f"- Problems: {', '.join(row.get('problems') or []) or 'none'}",
            f"- Human action: {row.get('human_action')}",
            "",
        ])
    return "\n".join(lines)


def markdown_verification_queue(payload: dict[str, Any]) -> str:
    lines = [
        "# Sophia Source Verification Queue",
        "",
        f"Items requiring human verification: **{payload.get('queue_count')}**",
        "",
        "No candidate source becomes verified support automatically.",
        "",
    ]
    for row in payload.get("items") or []:
        lines.extend([
            f"## {row.get('queue_id')} · {row.get('claim_id') or 'reference'}",
            "",
            f"- Source: {row.get('source_name')}",
            f"- DOI/URL: {row.get('doi') or row.get('url') or 'not resolved'}",
            f"- Current support state: {row.get('support_state')}",
            f"- Task: {row.get('verification_task')}",
            "",
        ])
    return "\n".join(lines)


def markdown_passport(payload: dict[str, Any]) -> str:
    review = payload.get("governed_review") or {}
    authority = payload.get("authority") or {}
    index = (payload.get("authorship_preservation") or {}).get("index") or {}
    return "\n".join([
        "# Sophia Integrity Passport",
        "",
        f"Job: `{payload.get('job_id')}`",
        f"Manuscript SHA-256: `{(payload.get('manuscript') or {}).get('sha256')}`",
        "",
        "## Governed Review",
        "",
        f"- Grounding passed: {review.get('grounding_passed')}",
        f"- Mandos passed: {review.get('mandos_passed')}",
        f"- Genesis Articles I-XII passed: {review.get('genesis_articles_passed')}",
        f"- Provider/model: {review.get('provider')} / {review.get('model')}",
        f"- Speculum integrity-record hash: `{payload.get('speculum_integrity_record_hash')}`",
        "",
        "## Authorship Preservation",
        "",
        f"- Engineering signal: {index.get('score')}",
        f"- Band: {index.get('band')}",
        f"- Validation status: {index.get('validation_status')}",
        "- Boundary: This is not a forensic authorship or misconduct detector.",
        "",
        "## Authority",
        "",
        f"- Human author owns final wording: {authority.get('human_author_owns_final_wording')}",
        f"- Human review required before delivery: {authority.get('human_reviewer_required_before_delivery')}",
        f"- Sophia has misconduct-finding authority: {authority.get('misconduct_finding_authority')}",
        f"- Candidate sources auto-promoted to support: {authority.get('automatic_source_promotion')}",
    ])


def rebuild_archive(output_dir: Path, job_id: str) -> Path:
    archive = output_dir / f"{job_id}_SOPHIA_REVIEW_PACK.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(output_dir.iterdir()):
            if path.is_file() and path != archive:
                zf.write(path, arcname=path.name)
    return archive


def enrich_review_pack(
    *,
    job_id: str,
    output_dir: Path,
    manuscript_path: Path,
    sophia_root: Path | None = None,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    claim_payload = load_json(output_dir / "CLAIM_SOURCE_LEDGER.json")
    reference_audit = load_json(output_dir / "REFERENCE_AUDIT.json")
    literature_payload = load_json(output_dir / "LITERATURE_MAP.json")
    commentary = load_json(output_dir / "REVIEWER_COMMENTARY.json")
    receipt = load_json(output_dir / "SOPHIA_REVIEW_RECEIPT.json")

    risk_register = build_scholarly_risk_register(claim_payload, reference_audit)
    verification_queue = build_verification_queue(claim_payload, reference_audit)
    speculum_record = build_speculum_integrity_record(
        job_id=job_id,
        output_dir=output_dir,
        manuscript_path=manuscript_path,
        sophia_root=sophia_root,
        claim_payload=claim_payload,
        literature_payload=literature_payload,
        commentary=commentary,
        risk_register=risk_register,
    )
    write_json(output_dir / "SCHOLARLY_RISK_REGISTER.json", risk_register)
    write_text(output_dir / "SCHOLARLY_RISK_REGISTER.md", markdown_risk_register(risk_register))
    write_json(output_dir / "SOURCE_VERIFICATION_QUEUE.json", verification_queue)
    write_text(output_dir / "SOURCE_VERIFICATION_QUEUE.md", markdown_verification_queue(verification_queue))
    write_json(output_dir / "SOPHIA_INTEGRITY_RECORD.json", speculum_record)
    write_text(output_dir / "SOPHIA_INTEGRITY_RECORD.md", str(speculum_record.get("markdown") or "# Sophia Integrity Record\n\nMachine-readable record written to SOPHIA_INTEGRITY_RECORD.json."))
    write_json(output_dir / "AUTHORSHIP_PRESERVATION_INDEX.json", speculum_record.get("authorship_preservation_index") or {})

    passport = build_integrity_passport(
        job_id=job_id,
        output_dir=output_dir,
        manuscript_path=manuscript_path,
        commentary=commentary,
        receipt=receipt,
        speculum_record=speculum_record,
        risk_register=risk_register,
    )
    write_json(output_dir / "INTEGRITY_PASSPORT.json", passport)
    write_text(output_dir / "INTEGRITY_PASSPORT.md", markdown_passport(passport))
    archive = rebuild_archive(output_dir, job_id)
    return {
        "schema": "dio.sophia_c9_product_enrichment.v1",
        "job_id": job_id,
        "state": "integrity_pack_ready",
        "risk_state": risk_register.get("state"),
        "open_risk_count": risk_register.get("open_risk_count"),
        "verification_queue_count": verification_queue.get("queue_count"),
        "speculum_integrity_record_hash": speculum_record.get("integrity_record_hash"),
        "authorship_preservation_index": speculum_record.get("authorship_preservation_index") or {},
        "archive": str(archive),
    }


def compare_revision_packs(
    *,
    original_dir: Path,
    revised_dir: Path,
    original_document: Path,
    revised_document: Path,
) -> dict[str, Any]:
    original_risk = load_json(original_dir / "SCHOLARLY_RISK_REGISTER.json")
    revised_risk = load_json(revised_dir / "SCHOLARLY_RISK_REGISTER.json")
    original_ref = load_json(original_dir / "REFERENCE_AUDIT.json")
    revised_ref = load_json(revised_dir / "REFERENCE_AUDIT.json")
    original_claims = load_json(original_dir / "CLAIM_SOURCE_LEDGER.json")
    revised_claims = load_json(revised_dir / "CLAIM_SOURCE_LEDGER.json")

    old_claim_texts = {_norm((item.get("claim_record") or {}).get("claim")).lower() for item in original_claims.get("claims") or []}
    new_high_risk = []
    for index, item in enumerate(revised_claims.get("claims") or [], 1):
        claim = item.get("claim_record") or {}
        text = _norm(claim.get("claim"))
        if text.lower() not in old_claim_texts and str(claim.get("evidence_risk") or "").lower() == "high":
            new_high_risk.append({"claim_id": f"C{index}", "claim": text, "evidence_standard": claim.get("evidence_standard")})

    old_open = int(original_risk.get("open_risk_count") or 0)
    new_open = int(revised_risk.get("open_risk_count") or 0)
    old_refs = int(original_ref.get("actionable_issue_count") or 0)
    new_refs = int(revised_ref.get("actionable_issue_count") or 0)
    if new_open < old_open and new_refs <= old_refs and not new_high_risk:
        movement = "improved"
    elif new_open > old_open or new_refs > old_refs or new_high_risk:
        movement = "new_or_shifted_risk"
    elif new_open == old_open and new_refs == old_refs:
        movement = "stable"
    else:
        movement = "mixed"
    return {
        "schema": "dio.sophia_revision_integrity_report.v1",
        "created_at": utc_now(),
        "movement": movement,
        "original": {
            "document": original_document.name,
            "sha256": sha256_file(original_document),
            "open_scholarly_risks": old_open,
            "reference_findings": old_refs,
        },
        "revised": {
            "document": revised_document.name,
            "sha256": sha256_file(revised_document),
            "open_scholarly_risks": new_open,
            "reference_findings": new_refs,
        },
        "delta": {
            "open_scholarly_risks": new_open - old_open,
            "reference_findings": new_refs - old_refs,
        },
        "new_high_risk_claims": new_high_risk,
        "authorship_boundary": (
            "This report evaluates visible scholarly-integrity movement. It does not forensically determine who authored the revised prose. Final wording and revision decisions remain the human author's responsibility."
        ),
        "human_review_required": True,
    }


def markdown_revision_report(payload: dict[str, Any]) -> str:
    delta = payload.get("delta") or {}
    lines = [
        "# Sophia Revision Integrity Report",
        "",
        f"Movement: **{payload.get('movement')}**",
        "",
        "## Before → After",
        "",
        f"- Open scholarly risks: {(payload.get('original') or {}).get('open_scholarly_risks')} → {(payload.get('revised') or {}).get('open_scholarly_risks')} ({delta.get('open_scholarly_risks'):+})",
        f"- Reference findings: {(payload.get('original') or {}).get('reference_findings')} → {(payload.get('revised') or {}).get('reference_findings')} ({delta.get('reference_findings'):+})",
        "",
        "## New High-Risk Claims",
        "",
    ]
    if payload.get("new_high_risk_claims"):
        for row in payload["new_high_risk_claims"]:
            lines.append(f"- {row.get('claim_id')}: {row.get('claim')}")
    else:
        lines.append("- None newly surfaced by the reviewed high-risk claim set.")
    lines.extend(["", "## Authorship Boundary", "", str(payload.get("authorship_boundary"))])
    return "\n".join(lines)
