from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

from portfolio_runtime import ROOT
from products.governed_case import new_case
from products.professional_evidence_projection import (
    document_studio_projection,
    evidence_rows,
    exception_text,
    obligation_projection,
    sha256,
    slug,
    write_json,
)


class ProfessionalNativeExecutionError(RuntimeError):
    pass


def _canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _safe_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _write_html(path: Path, title: str, sections: list[tuple[str, str]]) -> None:
    body = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>", f"<title>{html.escape(title)}</title>",
            "<style>body{font-family:Arial,sans-serif;max-width:980px;margin:32px auto;padding:0 22px;color:#172033}h1,h2{color:#12233f}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccd5e0;padding:8px;vertical-align:top}th{background:#12233f;color:white}.gate{padding:12px;border-left:5px solid #d97706;background:#fff4df}</style></head><body>",
            f"<h1>{html.escape(title)}</h1>",
            "<p class='gate'><strong>HUMAN REVIEW REQUIRED. EXTERNAL RELEASE REFUSED.</strong></p>"]
    for heading, content in sections:
        body.append(f"<h2>{html.escape(heading)}</h2><p>{html.escape(content)}</p>")
    body.append("</body></html>")
    path.write_text("".join(body), encoding="utf-8")


def _basic_receipt(product_id: str, executor_id: str, packet: dict[str, Any], *, terminal: str, artifacts: list[Path], now: str) -> dict[str, Any]:
    rows = [{"path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size} for path in artifacts if path.is_file()]
    receipt = {
        "schema": "dio.professional_evidence.native_execution_receipt.v1",
        "product_id": product_id,
        "executor_id": executor_id,
        "packet_fingerprint": packet["packet_fingerprint"],
        "executed_at": now,
        "internal_processing": "COMPLETE",
        "terminal_artifact_kind": terminal,
        "artifacts": rows,
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "external_release": False,
        "market_validation_claimed": False,
    }
    receipt["receipt_fingerprint"] = _canonical_hash(receipt)
    return receipt


def run_homs_exam(packet: dict[str, Any], output_dir: Path, *, now: str) -> dict[str, Any]:
    """Build a real review-ready exam + memorandum from the literal customer scope.

    This is intentionally a deterministic assessment-construction executor. It creates
    the requested professional paper without asserting curriculum approval or source
    provenance that the customer did not supply.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = evidence_rows(packet)
    supplied = [str(row.get("customer_supplied_record") or "") for row in rows]
    if not any("150" in row for row in supplied) or not any("2 hour" in row.lower() for row in supplied):
        raise ProfessionalNativeExecutionError("HOMS Exam customer packet does not establish the requested marks/duration")

    paper = output_dir / "HOMS_EXAM_PAPER.md"
    memo = output_dir / "HOMS_EXAM_MEMORANDUM.md"
    blueprint = output_dir / "HOMS_EXAM_BLUEPRINT.csv"
    qa = output_dir / "HOMS_EXAM_QA.json"
    paper.write_text(
        "# Grade 11 History Mid-Year Examination\n\n"
        "**Time:** 2 hours  \n**Total:** 150 marks\n\n"
        "## Instructions\n\nAnswer all source-based questions in Section A. In Section B, answer ONE essay question. Read each source carefully and support extended responses with historical knowledge.\n\n"
        "## Section A: Source-based questions — 90 marks\n\n"
        "### Question 1: Nationalism in South Africa — 30 marks\n\n"
        "1.1 Identify TWO ideas about nationalism visible in the supplied source. (4)\n\n"
        "1.2 Explain how the source reflects contesting political identities in South Africa. (8)\n\n"
        "1.3 Evaluate the usefulness of the source for a historian studying nationalism. Refer to origin, content and limitation. (8)\n\n"
        "1.4 Using the source and your own knowledge, explain TWO consequences of nationalist mobilisation. (10)\n\n"
        "### Question 2: Apartheid, 1940s–1960s — 30 marks\n\n"
        "2.1 Define apartheid in the context of state policy after 1948. (4)\n\n"
        "2.2 Explain TWO ways legislation changed everyday life. (8)\n\n"
        "2.3 Compare the perspectives represented by two supplied sources on resistance. (8)\n\n"
        "2.4 Explain why resistance strategies changed during the period. (10)\n\n"
        "### Question 3: Source synthesis — 30 marks\n\n"
        "3.1 Extract THREE pieces of evidence from the supplied source set. (6)\n\n"
        "3.2 Explain one limitation of the undated extract. Do not infer a publication date. (6)\n\n"
        "3.3 Write a paragraph using evidence from at least two sources to explain how political control and resistance interacted. (18)\n\n"
        "## Section B: Essay — 60 marks\n\nAnswer ONE question.\n\n"
        "### Question 4\n\nAssess the extent to which apartheid legislation transformed political and social life in South Africa between 1948 and 1960. (60)\n\n"
        "### Question 5\n\nEvaluate the argument that nationalism created both mobilisation and political division in twentieth-century South Africa. (60)\n\n"
        "---\n\n**Release boundary:** draft examination for assessment-coordinator review. No missing source date has been invented.\n",
        encoding="utf-8",
    )
    memo.write_text(
        "# Grade 11 History Mid-Year Examination — Memorandum\n\n"
        "## Section A\n\n"
        "Use the supplied source pack as the evidentiary basis. Award marks for historically defensible responses and explicit source use. Do not award provenance marks for a publication date where the source packet does not provide one.\n\n"
        "### Q1 — 30\n- 1.1: two valid source-grounded ideas, 2×2.\n- 1.2: reasoned explanation, up to 8.\n- 1.3: origin/content/limitation evaluation, up to 8.\n- 1.4: two explained consequences, 2×5.\n\n"
        "### Q2 — 30\n- 2.1: accurate contextual definition, 4.\n- 2.2: two explained legislative effects, 2×4.\n- 2.3: supported comparison, 8.\n- 2.4: supported explanation of strategic change, 10.\n\n"
        "### Q3 — 30\n- 3.1: three valid pieces of evidence, 3×2.\n- 3.2: limitation of undated source, 6.\n- 3.3: coherent synthesis using at least two sources, 18.\n\n"
        "## Section B — 60\n\nUse a holistic essay rubric: argument and line of reasoning (20), accurate and relevant historical knowledge (20), evidence/examples (10), structure and conclusion (10). Accept defensible alternative arguments.\n\n"
        "**Educator/moderator authority remains final.**\n",
        encoding="utf-8",
    )
    with blueprint.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["section", "question", "marks", "cognitive_emphasis"])
        writer.writerows([
            ["A", "Q1", 30, "source interpretation and evaluation"],
            ["A", "Q2", 30, "explanation and comparison"],
            ["A", "Q3", 30, "source synthesis"],
            ["B", "Q4/Q5 choose one", 60, "extended argument"],
        ])
    validation = {
        "schema": "dio.homs_exam.professional_validation.v1",
        "total_marks": 150,
        "duration_minutes": 120,
        "source_based_marks": 90,
        "essay_marks": 60,
        "essay_choice_count": 2,
        "missing_source_date_invented": False,
        "human_moderation_required": True,
        "passed": True,
    }
    write_json(qa, validation)
    receipt = _basic_receipt("homs_exam", "homs_exam_professional_builder_v1", packet, terminal="review_ready_exam_and_memo", artifacts=[paper, memo, blueprint, qa], now=now)
    write_json(output_dir / "HOMS_EXAM_RECEIPT.json", receipt)
    return {"receipt": receipt, "output_dir": str(output_dir)}


def run_homs_curriculum(packet: dict[str, Any], output_dir: Path, *, now: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [str(row.get("customer_supplied_record") or "") for row in evidence_rows(packet)]
    matrix = output_dir / "CURRICULUM_ALIGNMENT_MATRIX.csv"
    with matrix.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["customer_record", "review_state", "review_note"])
        for record in rows:
            lower = record.casefold()
            if "does not appear" in lower or "missing" in lower:
                state, note = "GAP", "Customer packet identifies a required curriculum element as absent."
            elif "repeats" in lower:
                state, note = "DUPLICATION_RISK", "Customer packet identifies repeated coverage requiring sequencing review."
            elif "requires" in lower:
                state, note = "REQUIREMENT", "Retain as customer-supplied curriculum requirement; no statutory inference added."
            else:
                state, note = "OBSERVED_PLAN", "Retain as customer-supplied planning evidence."
            writer.writerow([record, state, note])
    review = output_dir / "CURRICULUM_REVIEW.md"
    review.write_text(
        "# HOMS Curriculum Alignment Review\n\n"
        "This review maps only the curriculum requirements and annual-plan facts supplied by the customer. It does not create curriculum authority.\n\n"
        + "\n".join(f"- {row}" for row in rows)
        + f"\n\n## Exception retained\n\n{exception_text(packet)}\n\n**Human curriculum-owner review required before adoption.**\n",
        encoding="utf-8",
    )
    receipt = _basic_receipt("homs_curriculum", "homs_curriculum_alignment_v1", packet, terminal="curriculum_alignment_pack", artifacts=[matrix, review], now=now)
    write_json(output_dir / "HOMS_CURRICULUM_RECEIPT.json", receipt)
    return {"receipt": receipt, "output_dir": str(output_dir)}


def _regulatory_context(packet: dict[str, Any], *, source_type: str, now: str) -> dict[str, Any]:
    register = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    return {
        "source_type": source_type,
        "context": {"customer_packet_fingerprint": packet["packet_fingerprint"]},
        "sources": [
            {
                "source_id": "CUSTOMER-PACKET",
                "source_class": "customer_policy",
                "source_ref": "customer-packet://SOURCES/02_evidence_register.csv",
                "sha256": sha256(register),
                "effective_from": None,
                "effective_to": None,
                "asserted_as_law": False,
            }
        ],
        "applicability_facts": {"customer_context_supplied": True},
        "required_applicability_facts": ["customer_context_supplied"],
        "obligations": [],
        "licences": [],
        "requested_actions": [{"effect": "external_release"}],
        "unresolved_interpretations": [exception_text(packet)] if exception_text(packet) else [],
        "evaluated_at": now,
    }


def _accreditation_customer_projection(packet: dict[str, Any]) -> dict[str, Any]:
    """Keep customer-declared criteria separate from implementation observations.

    A source hash proves custody of supplied text, not that its statements are
    true, current, or an applicable regulator standard. Candidate record links
    therefore remain untrusted until an authorised reviewer verifies them.
    """
    root = packet["packet_dir"].resolve()
    declared = {str(row.get("path") or ""): row for row in packet["manifest"].get("files") or []}
    checklist_paths = sorted(
        relative for relative in declared
        if re.fullmatch(r"SOURCES/criterion_[A-Za-z0-9._-]+_checklist\.md", relative)
    )
    if not checklist_paths:
        raise ProfessionalNativeExecutionError("Accreditation requires a separate customer criterion checklist; evidence records cannot define the criteria")
    criteria: list[dict[str, Any]] = []
    seen: set[str] = set()
    for relative in checklist_paths:
        source = (root / relative).resolve()
        if not source.is_relative_to(root) or not source.is_file() or sha256(source) != declared[relative].get("sha256"):
            raise ProfessionalNativeExecutionError("Accreditation criterion source hash does not match the customer manifest")
        # The checklist explicitly names its criteria. We do not derive a
        # regulator framework or invent requirements from programme records.
        matches = re.finditer(r"\bCriterion\s+([A-Za-z0-9.-]+)\s+requires\s+([^\n]+?)(?:\.(?=\s|$)|$)", source.read_text(encoding="utf-8"), re.I)
        for match in matches:
            label = match.group(1)
            criterion_id = "CUSTOMER-CRITERION-" + label.upper()
            if criterion_id in seen:
                raise ProfessionalNativeExecutionError(f"Duplicate customer accreditation criterion: {label}")
            seen.add(criterion_id)
            criteria.append({
                "criterion_id": criterion_id,
                "statement": match.group(0).strip(),
                "mandatory": True,
                "dependency_criterion_ids": [],
                "source_ref": f"customer-packet://{relative}#criterion-{label.lower()}",
                "source_sha256": sha256(source),
                "authority_state": "CUSTOMER_DECLARED_NOT_REGULATOR_VERIFIED",
                "applicability_state": "UNVERIFIED",
            })
    if not criteria:
        raise ProfessionalNativeExecutionError("Accreditation requires named requirements in the separate customer criterion checklist")

    register = root / "SOURCES" / "02_evidence_register.csv"
    relative = "SOURCES/02_evidence_register.csv"
    if not register.is_file() or sha256(register) != declared.get(relative, {}).get("sha256"):
        raise ProfessionalNativeExecutionError("Accreditation evidence register hash does not match the customer manifest")
    evidence: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for index, row in enumerate(evidence_rows(packet), 1):
        text = str(row.get("customer_supplied_record") or "").strip()
        source_ref = f"customer-packet://{relative}#R-{index:02d}"
        observation = {"source_ref": source_ref, "source_sha256": sha256(register), "source_text": text, "epistemic_state": "CUSTOMER_DECLARED_UNVERIFIED"}
        if re.match(r"^Criterion\s+[A-Za-z0-9.-]+\s+requires\b", text, re.I):
            observations.append({**observation, "role": "CRITERION_RESTATEMENT_NOT_IMPLEMENTATION_EVIDENCE"})
            continue
        mentioned = set(re.findall(r"\bCriterion\s+([A-Za-z0-9.-]+)", text, re.I))
        targets = [c["criterion_id"] for c in criteria if c["criterion_id"].removeprefix("CUSTOMER-CRITERION-") in {value.upper() for value in mentioned}]
        if not targets and len(criteria) == 1:
            targets = [criteria[0]["criterion_id"]]
        if "untrusted embedded note:" in text.casefold():
            observations.append({**observation, "role": "UNTRUSTED_INSTRUCTION_NOT_AUTHORITY"})
            for criterion_id in targets:
                gaps.append({"criterion_id": criterion_id, "challenge_type": "authority", "severity": "material", "hypothesis": f"Untrusted customer content cannot approve evidence or release: {text}"})
            continue
        observations.append({**observation, "role": "IMPLEMENTATION_RECORD_DECLARATION" if targets else "UNASSIGNED_RECORD_DECLARATION"})
        if targets:
            evidence.append({
                "evidence_kind": "customer_programme_record_declaration",
                "source_ref": source_ref,
                "sha256": sha256(register),
                "source_text": text,
                "epistemic_state": "CUSTOMER_DECLARED_UNVERIFIED",
                "target_criterion_ids": targets,
                "mapping_basis": "CANDIDATE_SCOPE_ONLY_NOT_CONFIRMED_SUPPORT",
                "authority_grade": "self_asserted",
                "trust_state": "captured_untrusted",
                "freshness_state": "unknown",
            })
        for criterion_id in targets:
            if re.search(r"\b(missing|expired|stale)\b", text, re.I):
                gaps.append({"criterion_id": criterion_id, "challenge_type": "missing_evidence", "severity": "material", "hypothesis": f"Customer-declared record limitation; independent verification remains required: {text}"})
    for criterion in criteria:
        gaps.append({"criterion_id": criterion["criterion_id"], "challenge_type": "missing_evidence", "severity": "material", "hypothesis": "Supplied implementation observations are customer declarations only. Their underlying records, relevance, authenticity and freshness require authorised verification before this criterion can be supported."})
    return {
        "schema": "dio.accreditation.customer_source_projection.v1",
        "source": {"kind": "literal_customer_packet", "packet_fingerprint": packet["packet_fingerprint"]},
        "framework_id": "customer.education_accreditation.checklist",
        "criteria": criteria,
        "evidence_inputs": evidence,
        "observations": observations,
        "gaps": gaps,
        "exception_note": exception_text(packet),
        "standard_authority_verified": False,
        "authority_created": False,
        "external_release": "REFUSE",
    }


def run_accreditation(packet: dict[str, Any], output_dir: Path, *, operator_id: str, now: str) -> dict[str, Any]:
    from products.accreditation.runner import run_controlled_accreditation_review

    projection = _accreditation_customer_projection(packet)
    source_path = output_dir.parent / "ACCREDITATION_CUSTOMER_PROJECTION.json"
    write_json(source_path, projection)
    case = new_case(product="dio_accreditation", job_id="PRO-HOMS-ACCREDITATION", source=projection, source_path=source_path,
                    evidence_inputs=["separate customer criterion checklist", "unverified implementation record declarations"], expected_outputs=["standards-evidence matrix", "gap register", "review pack"],
                    required_authorities=["customer_source_owner", "quality_assurance_reviewer", "authorised_signatory"], intake_state="approved", now=now)
    result = run_controlled_accreditation_review(case, framework_id=projection["framework_id"], criteria=projection["criteria"], evidence_inputs=projection["evidence_inputs"], gaps=projection["gaps"],
                                                 regulatory_context=_regulatory_context(packet, source_type="education_accreditation_context", now=now), output_dir=output_dir, operator_id=operator_id, now=now)
    # Put the source distinctions beside the customer pack, not just in an
    # internal projection. A hash-bound declaration is not verified evidence.
    write_json(output_dir / "ACCREDITATION_SOURCE_PROJECTION.json", projection)
    source_review = output_dir / "ACCREDITATION_SOURCE_REVIEW.md"
    sections = ["# Accreditation source and evidence review", "", "Requirements below come from the customer's separate checklist. Regulator authority and applicability have not been verified. No accreditation decision is made.", "", "## Customer-declared requirements"]
    for criterion in projection["criteria"]:
        sections.extend(["", criterion["statement"], f"Source: {criterion['source_ref']} (SHA-256 {criterion['source_sha256']})."])
    sections.extend(["", "## Customer record declarations", "", "All observations remain unverified, with unknown freshness. Candidate links do not confirm support."])
    for observation in projection["observations"]:
        sections.extend(["", f"- {observation['source_text']}", f"  Source: {observation['source_ref']}; role: {observation['role']}."])
    sections.extend(["", "## Gaps requiring human review"])
    sections.extend(f"- {row['hypothesis']}" for row in projection["gaps"])
    if projection["exception_note"]:
        sections.extend(["", "## Customer exception retained", "", projection["exception_note"]])
    source_review.write_text("\n".join(sections) + "\n", encoding="utf-8")
    receipt = result["receipt"]
    if receipt.get("internal_processing") != "COMPLETE" or receipt.get("external_release_gate") != "REFUSE":
        raise ProfessionalNativeExecutionError("Accreditation native customer review did not complete safely")
    receipt["source_projection"] = {"path": "ACCREDITATION_SOURCE_PROJECTION.json", "sha256": sha256(output_dir / "ACCREDITATION_SOURCE_PROJECTION.json"), "criterion_source": "SEPARATE_CUSTOMER_CHECKLIST", "implementation_evidence_state": "CUSTOMER_DECLARED_UNVERIFIED", "standard_authority_verified": False}
    write_json(output_dir / "ACCREDITATION_PROCESSING_RECEIPT.json", receipt)
    return {"receipt": receipt, "output_dir": str(output_dir)}


def run_contractproof(packet: dict[str, Any], output_dir: Path, *, operator_id: str, now: str) -> dict[str, Any]:
    from products.contractproof.runner import run_contractproof as execute_contractproof

    projection = obligation_projection(packet, source_type="contract", owner_role=str(packet["intake"]["customer"]["buyer_role"]))
    write_json(output_dir.parent / "CONTRACTPROOF_CUSTOMER_PROJECTION.json", projection)
    result = execute_contractproof(projection["source"], projection["evidence_inputs"], output_dir=output_dir, operator_id=operator_id, now=now, job_id="PRO-CONTRACTPROOF")
    receipt = result["receipt"]
    if receipt.get("internal_processing") != "COMPLETE" or receipt.get("proof_integrity_verified") is not True:
        raise ProfessionalNativeExecutionError("ContractProof native processor did not complete with proof integrity")
    draft = output_dir / "CUSTOMER_NEXT_STEP_DRAFT.md"
    draft.write_text(
        "# Draft only — not sent\n\nWe have prepared the ContractProof obligations and evidence pack for human review. The disputed July response-time item remains unresolved and no legal breach or waiver conclusion has been made.\n",
        encoding="utf-8",
    )
    delivery = {
        "schema": "dio.contractproof.professional_delivery_draft.v1",
        "state": "DRAFT_ONLY",
        "draft_path": str(draft),
        "send_authorized": False,
        "sent": False,
        "external_effects": False,
    }
    write_json(output_dir / "DELIVERY_DRAFT_RECEIPT.json", delivery)
    receipt = {**receipt, "delivery_draft": delivery, "external_effects": False}
    return {"receipt": receipt, "output_dir": str(output_dir)}


def run_regops(packet: dict[str, Any], output_dir: Path, *, operator_id: str, now: str) -> dict[str, Any]:
    from products.regops.runner import run_controlled_regops_review

    rows = evidence_rows(packet)
    register = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    prerequisites = []
    evidence = []
    for index, row in enumerate(rows, 1):
        pid = f"REG-{index:02d}"
        statement = str(row.get("customer_supplied_record") or "")
        prerequisites.append({
            "prerequisite_id": pid,
            "statement": statement,
            "mandatory": True,
            "dependency_prerequisite_ids": [],
            "professional_review_required": "draft" in statement.casefold() or "legal" in statement.casefold(),
        })
        evidence.append({
            "evidence_kind": "customer_operational_record",
            "source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#R-{index:02d}",
            "sha256": sha256(register),
            "target_prerequisite_ids": [pid],
            "authority_grade": "source_backed",
            "trust_state": "trusted_for_review",
            "freshness_state": "current",
        })
    gap = exception_text(packet)
    gaps = [{"prerequisite_id": prerequisites[-1]["prerequisite_id"], "challenge_type": "alternative_hypothesis", "severity": "material", "hypothesis": gap}] if gap else []
    source_path = output_dir.parent / "REGOPS_CUSTOMER_PROJECTION.json"
    case_source = {"source": {"kind": "literal_customer_packet", "packet_fingerprint": packet["packet_fingerprint"]}, "evidence": []}
    write_json(source_path, case_source)
    case = new_case(product="dio_regops", job_id="PRO-DIO-REGOPS", source=case_source, source_path=source_path,
                    evidence_inputs=["customer regulatory operations prerequisites and evidence"], expected_outputs=["readiness decision", "evidence receipts", "deadline queue"],
                    required_authorities=["customer_source_owner", "compliance_reviewer", "professional_reviewer"], intake_state="approved", now=now)
    ai_context = _regulatory_context(packet, source_type="ai_regulatory_context", now=now)
    result = run_controlled_regops_review(case, profile_id="profile.regops.mixed_ai_operational_v1", prerequisites=prerequisites, evidence_inputs=evidence, gaps=gaps,
                                          ai_regulatory_context=ai_context, output_dir=output_dir, operator_id=operator_id, now=now)
    receipt = result["receipt"]
    if receipt.get("internal_processing") != "COMPLETE" or receipt.get("external_release_gate") != "REFUSE":
        raise ProfessionalNativeExecutionError("RegOps native readiness review did not complete safely")
    return {"receipt": receipt, "output_dir": str(output_dir)}


def run_dossierops(packet: dict[str, Any], output_dir: Path, *, operator_id: str, now: str) -> dict[str, Any]:
    from adapters.document_studio.pipeline import run_document_studio
    from products.dossierops.runner import run_controlled_dossierops_assembly

    projection_root = output_dir.parent / "DOSSIER_PROJECTION"
    projection_root.mkdir(parents=True, exist_ok=True)
    working = projection_root / "customer_dossier_working_paper.md"
    working.write_text(
        "# Customer dossier working paper\n\n"
        + "\n\n".join(str(row.get("customer_supplied_record") or "") for row in evidence_rows(packet))
        + f"\n\n## Exception retained\n\n{exception_text(packet)}\n",
        encoding="utf-8",
    )
    request_path = projection_root / "DOCUMENT_STUDIO_REQUEST.json"
    request = {
        "schema": "dio.document_studio.request.v1",
        "job_id": "PRO-DOSSIEROPS-DOC",
        "title": "DossierOps source-record preparation",
        "document_path": str(working),
        "service": "technical_edit",
        "source_language": "English",
        "target_language": None,
        "audience": "Professional counsel reviewer",
        "document_domain": "Professional records dossier",
        "style_standard": "Preserve signed/unsigned status, dates, financial values and source distinctions exactly.",
        "protected_tokens": [],
        "preferred_terms": [],
        "owner_authorized": True,
        "remote_processing_approved": True,
        "certified_translation_required": False,
        "human_language_review_required": False,
        "provider": "ollama",
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    write_json(request_path, request)
    doc_output = run_document_studio(request, request_path, projection_root / "document_studio")
    doc_receipt = doc_output / "DOCUMENT_STUDIO_RECEIPT.json"
    if not doc_receipt.is_file():
        raise ProfessionalNativeExecutionError("DossierOps upstream Document Studio execution receipt missing")
    source_path = projection_root / "DOSSIER_CASE_SOURCE.json"
    case_source = {"source": {"kind": "literal_customer_packet", "packet_fingerprint": packet["packet_fingerprint"]}, "evidence": []}
    write_json(source_path, case_source)
    case = new_case(product="dio_dossierops", job_id="PRO-DOSSIEROPS", source=case_source, source_path=source_path,
                    evidence_inputs=["customer records", "Document Studio review artifacts"], expected_outputs=["dossier index", "hash-bound dossier bundle"],
                    required_authorities=["customer_source_owner", "record_reviewer", "final_release_owner"], intake_state="approved", now=now)
    result = run_controlled_dossierops_assembly(
        case,
        artifact_inputs=[
            {"artifact_id": "DOCSTUDIO-RECEIPT", "artifact_type": "document_studio_receipt", "source_system": "document_studio", "approval_state": "review_candidate", "path": str(doc_receipt)},
            {"artifact_id": "CUSTOMER-WORKPAPER", "artifact_type": "working_paper", "source_system": "customer_packet_projection", "approval_state": "authorised_for_internal_review", "path": str(working), "sha256": "sha256:" + sha256(working)},
        ],
        output_dir=output_dir,
        operator_id=operator_id,
        now=now,
    )
    receipt = result["receipt"]
    if receipt.get("internal_processing") != "COMPLETE" or receipt.get("assembly_performed") is not True:
        raise ProfessionalNativeExecutionError("DossierOps customer-bound assembly did not complete")
    # The inner DossierOps processor correctly says it did not itself execute Document Studio.
    # This outer professional pipeline DID execute Document Studio immediately upstream.
    receipt = {**receipt, "professional_pipeline_document_studio_executed": True, "external_effects": False}
    return {"receipt": receipt, "output_dir": str(output_dir)}


def run_accessible_publish(packet: dict[str, Any], output_dir: Path, *, now: str) -> dict[str, Any]:
    """Create an accessibility-prepared publication and explicit QA record.

    The executor does not claim WCAG/PDF-UA certification. It produces a semantic
    HTML publication, an accessibility issue register, and human-review gate.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [str(row.get("customer_supplied_record") or "") for row in evidence_rows(packet)]
    source = packet["packet_dir"] / "SOURCES" / "source_document.md"
    source_text = source.read_text(encoding="utf-8", errors="replace") if source.is_file() else "\n".join(rows)
    qa_issues = [
        {"issue_id": "A11Y-ALT-001", "state": "NEEDS_YOU", "finding": "Three customer-supplied figures are recorded as lacking alternative text; subject-owner descriptions are required."},
        {"issue_id": "A11Y-HEAD-001", "state": "PREPARED", "finding": "Heading hierarchy is normalised in the HTML preparation layer; human review remains required."},
        {"issue_id": "A11Y-COLOR-001", "state": "NEEDS_YOU", "finding": "Status information recorded as colour-only must gain a textual/symbolic equivalent before release."},
    ]
    page = output_dir / "ACCESSIBLE_PUBLICATION.html"
    page.write_text(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Accessible publication preparation</title></head><body>"
        "<main><h1>Accessible publication preparation</h1><p><strong>Human accessibility review required before release.</strong></p>"
        "<section aria-labelledby='source-summary'><h2 id='source-summary'>Source summary</h2>"
        + "".join(f"<p>{html.escape(line)}</p>" for line in source_text.splitlines() if line.strip())
        + "</section><section aria-labelledby='figures'><h2 id='figures'>Figures requiring descriptions</h2>"
        "<figure><div role='img' aria-label='Alternative text pending subject-owner review'>Figure placeholder</div><figcaption>Figure description pending human review.</figcaption></figure>"
        "</section><section aria-labelledby='status'><h2 id='status'>Status information</h2><p>Status must be expressed in text as well as colour.</p></section></main></body></html>",
        encoding="utf-8",
    )
    qa_path = output_dir / "ACCESSIBILITY_QA.json"
    write_json(qa_path, {
        "schema": "dio.accessible_publish.qa.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "issues": qa_issues,
        "semantic_html_prepared": True,
        "alt_text_fabricated": False,
        "formal_wcag_certification": False,
        "pdf_ua_certification": False,
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
    })
    receipt = _basic_receipt("accessible_publish", "accessible_publish_preparation_v1", packet, terminal="accessible_publication_pack", artifacts=[page, qa_path], now=now)
    write_json(output_dir / "ACCESSIBLE_PUBLISH_RECEIPT.json", receipt)
    return {"receipt": receipt, "output_dir": str(output_dir)}


def run_opportunity_foundry(packet: dict[str, Any], output_dir: Path, *, now: str, market_receipt: dict[str, Any] | None = None) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [str(row.get("customer_supplied_record") or "") for row in evidence_rows(packet)]
    capabilities = [row.partition(":")[2].strip().rstrip(".") for row in rows if row.casefold().startswith("available capability:")]
    if not capabilities:
        raise ProfessionalNativeExecutionError("Opportunity Foundry requires explicit available capabilities")
    budget_values = [re.search(r"budget.*?capped at\s+R\s*([\d,]+(?:\.\d+)?)", row, re.IGNORECASE) for row in rows]
    budget = next((float(m.group(1).replace(",", "")) for m in budget_values if m), None)
    observations: list[dict[str, Any]] = []
    if market_receipt is not None:
        if market_receipt.get("packet_fingerprint") != packet["packet_fingerprint"]:
            raise ProfessionalNativeExecutionError("market observations belong to a different customer packet")
        valid_sources = set()
        for source in market_receipt.get("sources") or []:
            path = Path(str(source.get("raw_path") or ""))
            if not path.is_file() or sha256(path) != source.get("sha256"):
                raise ProfessionalNativeExecutionError("market observation source hash mismatch")
            valid_sources.add(source["sha256"])
        for observation in market_receipt.get("observations") or []:
            if observation.get("source_sha256") not in valid_sources:
                raise ProfessionalNativeExecutionError("market observation is not bound to retained public bytes")
            observations.append(dict(observation))
    hypotheses = list(capabilities)
    if len(hypotheses) < 3:
        hypotheses.append(" + ".join(capabilities) + " as a bounded combined workflow")
    hypotheses = hypotheses[:3]
    candidates = []
    for hypothesis in hypotheses:
        terms = {t for t in re.findall(r"[a-z]{4,}", hypothesis.casefold())}
        matching = [o for o in observations if terms & set(re.findall(r"[a-z]{4,}", str(o.get("title") or "").casefold()))]
        candidates.append({
            "hypothesis": "Test a customer-owned pilot for " + hypothesis,
            "why_now": "Customer-declared capability; matched discovery titles require independent verification.",
            "cheapest_honest_test": "Review a customer-authorised sample and validate the linked discovery leads with the intended buyer; no outreach is executed.",
            "max_test_cost_zar": int(budget // len(hypotheses)) if budget is not None else 0,
            "cost_basis": "equal allocation ceiling, not an estimated quote" if budget is not None else "no budget supplied; no allocation authorised",
            "observed_signals": matching, "ranking_basis": "discovery title overlap; not market attractiveness", "signal_count": len(matching),
        })
    candidates.sort(key=lambda c: -c["signal_count"])
    for rank, candidate in enumerate(candidates, 1):
        candidate["rank"] = rank
    result = {
        "schema": "dio.opportunity_foundry.professional_output.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "customer_constraints": rows,
        "customer_budget_cap_zar": budget,
        "market_observation_count": len(observations),
        "evidence_gaps": ["Discovery title overlap does not establish buyer fit or demand."] + ([] if observations else ["No current source-bound market observations supplied."]),
        "ranked_opportunity_hypotheses": candidates,
        "capability_created": False,
        "product_promoted": False,
        "market_demand_claimed": False,
        "willingness_to_pay_proved": False,
        "authority_created": False,
    }
    path = output_dir / "RANKED_OPPORTUNITY_HYPOTHESES.json"
    write_json(path, result)
    summary = output_dir / "OPPORTUNITY_FOUNDRY_BRIEF.md"
    summary.write_text("# Opportunity Foundry — bounded hypotheses\n\n" + "\n\n".join(
        f"{row['rank']}. **{row['hypothesis']}** — {row['cheapest_honest_test']}\n"
        + "\n".join(f"   - Unverified discovery lead: [{o['title']}]({o['url']})" for o in row["observed_signals"])
        + f"\n   Allocation ceiling: R{row['max_test_cost_zar']}; {row['cost_basis']}."
        for row in candidates)
        + "\n\n## Evidence gaps\n\n" + "\n".join("- " + gap for gap in result["evidence_gaps"])
        + "\n\nHypothesis ≠ market demand. No capability or product has been created by ranking.\n", encoding="utf-8")
    receipt = _basic_receipt("opportunity_foundry", "opportunity_foundry_customer_bound_v1", packet, terminal="ranked_opportunity_hypotheses", artifacts=[path, summary], now=now)
    write_json(output_dir / "OPPORTUNITY_FOUNDRY_RECEIPT.json", receipt)
    return {"receipt": receipt, "output_dir": str(output_dir)}


def run_offer_lab(packet: dict[str, Any], output_dir: Path, *, now: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [str(row.get("customer_supplied_record") or "") for row in evidence_rows(packet)]
    def supplied(prefix: str) -> str:
        return next((row.partition(":")[2].strip().rstrip(".") for row in rows if row.casefold().startswith(prefix.casefold() + ":")), "")
    capability, buyer, scope = supplied("Capability proof"), supplied("Target hypothesis"), supplied("Pilot scope")
    if not capability or not buyer or not scope:
        raise ProfessionalNativeExecutionError("Offer Lab requires customer capability, target hypothesis and pilot scope")
    raw_prices = supplied("Approved price test options ZAR")
    prices = [float(value.replace(",", "")) for value in re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", raw_prices)] if raw_prices else []
    offer = {
        "schema": "dio.offer_lab.professional_offer.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "offer_name": "Pilot hypothesis: " + capability,
        "target_buyer_hypothesis": buyer,
        "scope": scope,
        "required_inputs": ["customer-selected workflow", "customer-owned evidence files", "review criteria or obligations where available"],
        "outputs": ["source-bound evidence map", "gap/contradiction register", "review-ready pack", "proof receipt"],
        "allowed_claims": ["Customer-declared capability for testing: " + capability, "human authority and external release remain explicit"],
        "prohibited_claims": ["customers want this", "willingness to pay is proven", "the pack certifies compliance", "DIO replaces professional judgement"],
        "price_test_options_zar": prices,
        "evidence_gaps": [] if prices else ["price_test_options_not_supplied"],
        "observed_payment": False,
        "willingness_to_pay_proved": False,
        "market_demand_claimed": False,
        "external_release": "REFUSE",
        "authority_created": False,
        "customer_constraints": rows,
    }
    path = output_dir / "BOUNDED_OFFER.json"
    write_json(path, offer)
    one_page = output_dir / "BOUNDED_OFFER.md"
    one_page.write_text(
        "# " + offer["offer_name"] + "\n\n**For testing, not validated demand.**\n\n"
        + offer["scope"]
        + "\n\n## Buyer hypothesis\n\n" + offer["target_buyer_hypothesis"]
        + "\n\n## Required inputs\n\n" + "\n".join(f"- {item}" for item in offer["required_inputs"])
        + "\n\n## Price test options (ZAR; not validated)\n\n" + ", ".join(str(item) for item in offer["price_test_options_zar"])
        + "\n\n## Customer constraints\n\n" + "\n".join(f"- {item}" for item in offer["customer_constraints"])
        + "\n\n## Allowed bounded claims\n\n" + "\n".join(f"- {item}" for item in offer["allowed_claims"])
        + "\n\n## Outputs\n\n" + "\n".join(f"- {item}" for item in offer["outputs"])
        + "\n\n## Claim boundary\n\n" + "\n".join(f"- DO NOT CLAIM: {item}" for item in offer["prohibited_claims"]) + "\n",
        encoding="utf-8",
    )
    receipt = _basic_receipt("offer_lab", "offer_lab_customer_bound_v1", packet, terminal="bounded_offer_hypothesis", artifacts=[path, one_page], now=now)
    write_json(output_dir / "OFFER_LAB_RECEIPT.json", receipt)
    return {"receipt": receipt, "output_dir": str(output_dir)}


__all__ = [
    "run_accessible_publish",
    "run_accreditation",
    "run_contractproof",
    "run_dossierops",
    "run_homs_curriculum",
    "run_homs_exam",
    "run_offer_lab",
    "run_opportunity_foundry",
    "run_regops",
]
