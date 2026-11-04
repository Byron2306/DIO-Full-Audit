from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
from pathlib import Path
from typing import Any

from portfolio_runtime import ROOT


class ProfessionalEvidenceProjectionError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def load_packet(packet_dir: Path) -> dict[str, Any]:
    packet_dir = packet_dir.resolve()
    manifest_path = packet_dir / "CUSTOMER_PACKET_MANIFEST.json"
    intake_path = packet_dir / "INTAKE.json"
    request_path = packet_dir / "CUSTOMER_REQUEST.md"
    if not manifest_path.is_file() or not intake_path.is_file() or not request_path.is_file():
        raise ProfessionalEvidenceProjectionError(f"incomplete customer packet: {packet_dir}")
    if "EXAMINER" in {part.upper() for part in packet_dir.parts}:
        raise ProfessionalEvidenceProjectionError("execution cannot receive an EXAMINER directory")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    intake = json.loads(intake_path.read_text(encoding="utf-8"))
    if manifest.get("examiner_truth_in_packet") is not False:
        raise ProfessionalEvidenceProjectionError("customer packet leaks examiner truth")
    if intake.get("external_release_authorised") is not False:
        raise ProfessionalEvidenceProjectionError("professional evidence corpus cannot pre-authorise external release")
    declared = {str(row.get("path") or ""): row for row in manifest.get("files") or []}
    for relative, row in declared.items():
        path = (packet_dir / relative).resolve()
        if packet_dir not in path.parents:
            raise ProfessionalEvidenceProjectionError(f"customer packet path escapes packet root: {relative}")
        if not path.is_file():
            raise ProfessionalEvidenceProjectionError(f"declared customer packet file is missing: {relative}")
        if sha256(path) != str(row.get("sha256") or ""):
            raise ProfessionalEvidenceProjectionError(f"customer packet file hash drifted: {relative}")
    return {
        "packet_dir": packet_dir,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "intake": intake,
        "request_path": request_path,
        "packet_fingerprint": str(manifest.get("packet_fingerprint") or ""),
    }


def evidence_rows(packet: dict[str, Any]) -> list[dict[str, str]]:
    path = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    if not path.is_file():
        raise ProfessionalEvidenceProjectionError("customer packet is missing SOURCES/02_evidence_register.csv")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    if len(rows) < 3:
        raise ProfessionalEvidenceProjectionError("professional customer evidence register is too thin")
    return rows


def evidence_record_spans(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Bind each CSV evidence record to its exact source bytes and row span."""
    path = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode("utf-8")))
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ProfessionalEvidenceProjectionError("customer evidence register is empty") from exc
    if "record_id" not in header:
        raise ProfessionalEvidenceProjectionError("customer evidence register lacks record_id")
    id_index = header.index("record_id")
    previous_line = reader.line_num
    spans: dict[str, dict[str, Any]] = {}
    for row in reader:
        start_line = previous_line
        end_line = reader.line_num
        previous_line = end_line
        if not row or id_index >= len(row):
            continue
        record_id = str(row[id_index]).strip()
        if not record_id:
            continue
        start = offsets[start_line]
        end = offsets[end_line]
        if record_id in spans:
            raise ProfessionalEvidenceProjectionError(f"duplicate evidence record_id: {record_id}")
        spans[record_id] = {
            "source_byte_start": start,
            "source_byte_end_exclusive": end,
            "source_row_sha256": hashlib.sha256(raw[start:end]).hexdigest(),
        }
    return spans


def evidence_register_record_bindings(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Return row-level source bindings for customer records in the CSV register."""
    path = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    file_digest = sha256(path)
    spans = evidence_record_spans(packet)
    bindings = []
    for index, row in enumerate(evidence_rows(packet), 1):
        record_id = str(row.get("record_id") or f"R-{index:02d}")
        statement = str(row.get("customer_supplied_record") or "").strip()
        span = spans.get(record_id)
        if span is None:
            raise ProfessionalEvidenceProjectionError(f"evidence record has no exact CSV byte span: {record_id}")
        attachment = None
        attachment_ref = str(row.get("artifact_path") or "").strip()
        if attachment_ref:
            relative = Path(attachment_ref)
            source = (packet["packet_dir"] / relative).resolve()
            if relative.is_absolute() or ".." in relative.parts or packet["packet_dir"] not in source.parents:
                raise ProfessionalEvidenceProjectionError(f"evidence attachment path escapes customer packet: {attachment_ref}")
            declared_files = {str(item.get("path") or ""): item for item in packet["manifest"].get("files") or []}
            declared = declared_files.get(relative.as_posix())
            observed_hash = sha256(source) if source.is_file() else ""
            row_hash = str(row.get("artifact_sha256") or "").strip().removeprefix("sha256:")
            manifest_hash = str((declared or {}).get("sha256") or "").strip().removeprefix("sha256:")
            if declared is None or not observed_hash or not row_hash or row_hash != observed_hash or manifest_hash != observed_hash:
                raise ProfessionalEvidenceProjectionError(f"evidence attachment is missing or hash binding failed: {attachment_ref}")
            attachment = {
                "source_ref": f"customer-packet://{relative.as_posix()}",
                "source_file_sha256": observed_hash,
                "bytes": source.stat().st_size,
                "trust_state": "captured_untrusted",
                "content_validation": "NOT_PERFORMED",
            }
        bindings.append({
            "record_id": record_id,
            "customer_statement": statement,
            "source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#{record_id}",
            "source_file_sha256": file_digest,
            "source_row_sha256": span["source_row_sha256"],
            "source_statement_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
            "source_byte_start": span["source_byte_start"],
            "source_byte_end_exclusive": span["source_byte_end_exclusive"],
            "source_attachment": attachment,
        })
    return bindings


def exception_text(packet: dict[str, Any]) -> str:
    path = packet["packet_dir"] / "SOURCES" / "03_exception_note.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"^#.*?\n+", "", text, count=1, flags=re.S).strip()


def source_inventory(packet: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for row in packet["manifest"].get("files") or []:
        relative = str(row.get("path") or "")
        path = packet["packet_dir"] / relative
        result.append(
            {
                "path": relative,
                "sha256": str(row.get("sha256") or ""),
                "bytes": int(row.get("bytes") or path.stat().st_size),
            }
        )
    return sorted(result, key=lambda row: row["path"])


def binding_receipt(packet: dict[str, Any], incarnation: str, route: dict[str, Any]) -> dict[str, Any]:
    receipt = {
        "schema": "dio.professional_evidence.customer_projection_binding.v1",
        "incarnation": incarnation,
        "packet_fingerprint": packet["packet_fingerprint"],
        "packet_manifest_sha256": "sha256:" + sha256(packet["manifest_path"]),
        "route": route,
        "source_inventory": source_inventory(packet),
        "examiner_data_used": False,
        "golden_fixture_used": False,
        "customer_packet_only": True,
        "authority_created": False,
        "external_effects": False,
    }
    receipt["binding_fingerprint"] = canonical_hash(receipt)
    return receipt


def review_projection(packet: dict[str, Any], *, profile_id: str) -> dict[str, Any]:
    rows = evidence_rows(packet)
    register = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    register_hash = sha256(register)
    spans = evidence_record_spans(packet)
    attachment_bindings = {row["record_id"]: row.get("source_attachment") for row in evidence_register_record_bindings(packet)}
    requirements = []
    inputs = []
    issues = []
    for index, row in enumerate(rows, 1):
        key = f"REQ-{index:02d}"
        record_id = str(row.get("record_id") or f"R-{index:02d}")
        statement = str(row.get("customer_supplied_record") or "").strip()
        span = spans.get(record_id)
        if span is None:
            raise ProfessionalEvidenceProjectionError(f"evidence record has no exact CSV byte span: {record_id}")
        statement_hash = hashlib.sha256(statement.encode("utf-8")).hexdigest()
        attachment = attachment_bindings.get(record_id)
        requirements.append(
            {
                "requirement_key": key,
                "statement": statement,
                "kind": "evidence_input",
                "source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#{record_id}",
                "source_file_sha256": register_hash,
                "source_row_sha256": span["source_row_sha256"],
                "source_statement_sha256": statement_hash,
                "source_byte_start": span["source_byte_start"],
                "source_byte_end_exclusive": span["source_byte_end_exclusive"],
                "mandatory": True,
                "dependency_requirement_keys": [],
            }
        )
        inputs.append(
            {
                "evidence_kind": "customer_source_record",
                "source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#{record_id}",
                "sha256": register_hash,
                "source_file_sha256": register_hash,
                "source_row_sha256": span["source_row_sha256"],
                "source_statement_sha256": statement_hash,
                "source_byte_start": span["source_byte_start"],
                "source_byte_end_exclusive": span["source_byte_end_exclusive"],
                "target_requirement_keys": [key],
                "source_attachment": attachment,
                "relation": "supports",
                "authority_grade": "source_backed",
                # Capture proves the bytes supplied, not their truth, approval
                # or continuing validity. A later independent review can earn
                # trust; projection must not grant it to every source row.
                "trust_state": "captured_untrusted",
                "freshness_state": "unknown",
            }
        )
        # Capturing a customer's statement is not evidence that an obligation
        # was satisfied. Retain explicitly reported defects as review concerns.
        # These are source-reported hypotheses, never professional conclusions.
        concern = re.search(
            r"\b(?:missing|omitted|unsigned|expired|unresolved|unverified|unsupported|"
            r"inconsistent|contradict\w*|stale|awaiting|pending|late|not present|"
            r"supplies no|no supporting|no matching|no starting|has not been|"
            r"days after .*deadline|worth .+ but .+ marks|untrusted embedded note)\b",
            statement, re.IGNORECASE,
        )
        if concern:
            issues.append({
                "requirement_key": key,
                "challenge_type": "alternative_hypothesis",
                "severity": "material",
                "hypothesis": "Source-reported concern requiring verification: " + statement,
            })
    exception = exception_text(packet)
    if exception:
        target = requirements[-1]["requirement_key"]
        issues.append(
            {
                "requirement_key": target,
                "challenge_type": "alternative_hypothesis",
                "severity": "material",
                "hypothesis": exception,
            }
        )
    return {
        "schema": "dio.professional_evidence.review_projection.v1",
        "profile_id": profile_id,
        "packet_fingerprint": packet["packet_fingerprint"],
        "case_source": {
            "source": {
                "kind": "literal_customer_packet",
                "packet_fingerprint": packet["packet_fingerprint"],
                "manifest": "CUSTOMER_PACKET_MANIFEST.json",
                "authority_scope": "customer_authorised_processing_only",
            },
            "evidence": [],
        },
        "requirements": requirements,
        "review_evidence_inputs": inputs,
        "issues": issues,
        "examiner_data_used": False,
    }


def obligation_projection(packet: dict[str, Any], *, source_type: str, owner_role: str) -> dict[str, Any]:
    rows = evidence_rows(packet)
    packet_dir = packet["packet_dir"]
    instrument = packet_dir / "SOURCES" / "source_instrument.md"
    register = packet_dir / "SOURCES" / "02_evidence_register.csv"
    spans = evidence_record_spans(packet)
    register_digest = sha256(register)
    instrument_clauses: list[dict[str, Any]] = []
    source_file = instrument if instrument.is_file() else register
    source_digest = sha256(source_file)
    if instrument.is_file():
        raw = instrument.read_bytes()
        byte_offset = 0
        for line_number, line_bytes in enumerate(raw.splitlines(keepends=True), 1):
            line_start = byte_offset
            byte_offset += len(line_bytes)
            line = line_bytes.decode("utf-8").rstrip("\r\n")
            match = re.match(r"^\s*[-*]?\s*Clause\s+(\d+)\s*:\s*(.*?)\s*$", line, flags=re.IGNORECASE)
            if not match:
                continue
            instrument_clauses.append({
                "clause_id": f"C-{int(match.group(1)):02d}",
                "text": match.group(2),
                "obligation": True,
                "obligation_kind": "other",
                "responsible_party": owner_role,
                "review_required": True,
                "evidence_requirements": ["customer-source record; independently verify"],
                "source_line": line,
                "source_line_number": line_number,
                "source_byte_start": line_start,
                "source_byte_end_exclusive": byte_offset,
                "source_row_sha256": hashlib.sha256(line_bytes).hexdigest(),
                "source_statement_sha256": hashlib.sha256(match.group(2).encode("utf-8")).hexdigest(),
                "source_file_sha256": source_digest,
                "source_ref": f"customer-packet://SOURCES/source_instrument.md#L{line_number}",
            })
    if not instrument_clauses:
        source_file = register
        source_digest = register_digest
    # With an instrument, obligations must come from its literal numbered
    # clauses. Without one, retain the prior register-based candidate behavior,
    # but accurately identify the register as the source.
    clauses = []
    inputs = []
    if instrument_clauses:
        clauses = [{key: value for key, value in clause.items() if not key.startswith("source_")} | {"source_provenance": {key: value for key, value in clause.items() if key.startswith("source_")}} for clause in instrument_clauses]
        clause_by_number = {int(item["clause_id"].split("-")[-1]): item for item in instrument_clauses}
        for index, row in enumerate(rows, 1):
            record_id = str(row.get("record_id") or f"R-{index:02d}")
            span = spans.get(record_id)
            if span is None:
                raise ProfessionalEvidenceProjectionError(f"evidence record has no exact CSV byte span: {record_id}")
            statement = str(row.get("customer_supplied_record") or "").strip()
            matched = clause_by_number.get(index)
            target_clause = matched["clause_id"] if matched else instrument_clauses[0]["clause_id"]
            inputs.append({
                "evidence_kind": "customer_source_record",
                "record_id": record_id,
                "source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#{record_id}",
                "sha256": register_digest,
                "source_file_sha256": register_digest,
                "source_row_sha256": span["source_row_sha256"],
                "source_statement_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
                "source_byte_start": span["source_byte_start"],
                "source_byte_end_exclusive": span["source_byte_end_exclusive"],
                "target_locators": [target_clause],
                "relation": "supports",
                "association_state": "ORDERED_PAIRING_UNVERIFIED" if not matched or statement != matched["text"] else "EXACT_TEXT_MATCH",
                "association_note": "Register row and instrument clause are distinct customer-supplied sources; this association is a review aid, not proof of fulfilment.",
                "authority_grade": "source_backed",
                "trust_state": "captured_untrusted",
                "freshness_state": "unknown",
            })
    else:
        clauses = []
        for index, row in enumerate(rows, 1):
            clause_id = f"C-{index:02d}"
            text = str(row.get("customer_supplied_record") or "").strip()
            span = spans.get(str(row.get("record_id") or f"R-{index:02d}"))
            clauses.append({"clause_id": clause_id, "text": text, "obligation": True, "obligation_kind": "other", "responsible_party": owner_role, "review_required": True, "evidence_requirements": ["customer-source record"], "source_provenance": {"source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#{row.get('record_id') or f'R-{index:02d}'}", "source_file_sha256": register_digest, **(span or {})}})
            inputs.append({"evidence_kind": "customer_source_record", "record_id": str(row.get("record_id") or f"R-{index:02d}"), "source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#{row.get('record_id') or f'R-{index:02d}'}", "sha256": register_digest, "source_file_sha256": register_digest, "source_row_sha256": (span or {}).get("source_row_sha256"), "source_statement_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "source_byte_start": (span or {}).get("source_byte_start"), "source_byte_end_exclusive": (span or {}).get("source_byte_end_exclusive"), "target_locators": [clause_id], "relation": "supports", "authority_grade": "source_backed", "trust_state": "captured_untrusted", "freshness_state": "unknown"})
    exception = exception_text(packet)
    if exception:
        exception_path = packet_dir / "SOURCES" / "03_exception_note.md"
        exception_raw = exception_path.read_bytes()
        inputs.append(
            {
                "evidence_kind": "customer_exception_record",
                "source_ref": "customer-packet://SOURCES/03_exception_note.md",
                "sha256": sha256(exception_path),
                "source_file_sha256": sha256(exception_path),
                "source_row_sha256": hashlib.sha256(exception_raw).hexdigest(),
                "source_statement_sha256": hashlib.sha256(exception.encode("utf-8")).hexdigest(),
                "source_byte_start": 0,
                "source_byte_end_exclusive": len(exception_raw),
                "target_locators": [clauses[-1]["clause_id"]],
                "relation": "contradicts",
                "authority_grade": "source_backed",
                "trust_state": "captured_untrusted",
                "freshness_state": "unknown",
            }
        )
    source = {
        "source_id": "SRC-" + packet["packet_fingerprint"].split(":")[-1][:16].upper(),
        "source_type": source_type,
        "source_ref": f"customer-packet://{source_file.relative_to(packet_dir)}",
        "sha256": source_digest,
        "effective_at": None,
        "expires_at": None,
        "clauses": clauses,
        "source_provenance": {"kind": "customer_supplied_instrument" if instrument_clauses else "customer_supplied_evidence_register", "source_file_sha256": source_digest, "instrument_ref": "customer-packet://SOURCES/source_instrument.md" if instrument.is_file() else None, "evidence_register_ref": "customer-packet://SOURCES/02_evidence_register.csv", "evidence_register_sha256": register_digest},
    }
    return {
        "schema": "dio.professional_evidence.obligation_projection.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "source": source,
        "evidence_inputs": inputs,
        "examiner_data_used": False,
    }


def homs_assess_projection(packet: dict[str, Any], target: Path) -> dict[str, Any]:
    source = packet["packet_dir"] / "SOURCES" / "hymark_input"
    uploads = source / "uploads"
    raw_rubric = source / "rubric.json"
    spine_path = source / "HOMS_CURRICULUM_SPINE.json"
    binding_path = source / "assessment_binding.json"
    declared = {str(row.get("path") or "") for row in packet["manifest"].get("files") or []}
    if not uploads.is_dir():
        raise ProfessionalEvidenceProjectionError("HOMS Assess packet requires hymark_input/uploads")
    if raw_rubric.is_file() and "SOURCES/hymark_input/rubric.json" not in declared:
        raise ProfessionalEvidenceProjectionError("HOMS Assess rubric is not bound by the customer packet manifest")
    curriculum_spine = None
    if spine_path.is_file():
        if "SOURCES/hymark_input/HOMS_CURRICULUM_SPINE.json" not in declared:
            raise ProfessionalEvidenceProjectionError("HOMS curriculum spine is not bound by the customer packet manifest")
        curriculum_spine = json.loads(spine_path.read_text(encoding="utf-8"))
        if curriculum_spine.get("schema") != "dio.homs.curriculum_spine.v1":
            raise ProfessionalEvidenceProjectionError("unsupported HOMS curriculum spine")
    if not raw_rubric.is_file() and not curriculum_spine:
        raise ProfessionalEvidenceProjectionError("HOMS Assess requires rubric.json or a manifest-bound HOMS Curriculum Spine")
    target = target.resolve()
    if target.exists():
        shutil.rmtree(target)
    (target / "uploads").mkdir(parents=True)
    for path in sorted(uploads.iterdir()):
        if path.is_file():
            shutil.copy2(path, target / "uploads" / path.name)
    if raw_rubric.is_file():
        rubric = json.loads(raw_rubric.read_text(encoding="utf-8"))
        criteria = list(rubric.get("criteria") or [])
        assessment_binding = None
        if binding_path.is_file():
            relative_binding = binding_path.relative_to(packet["packet_dir"]).as_posix()
            if relative_binding not in declared:
                raise ProfessionalEvidenceProjectionError("HOMS Assess source binding is not packet-manifest-bound")
            assessment_binding = json.loads(binding_path.read_text(encoding="utf-8"))
            if assessment_binding.get("schema") != "dio.homs.assessment_source_binding.v1":
                raise ProfessionalEvidenceProjectionError("HOMS Assess source binding has an unsupported schema")
            if int(assessment_binding.get("grade") or 0) != int(rubric.get("grade") or 0) or str(assessment_binding.get("subject") or "").casefold() != str(rubric.get("subject") or "").casefold():
                raise ProfessionalEvidenceProjectionError("HOMS Assess rubric grade/subject differs from its source binding")
            bound_artifacts = {str(row.get("role") or ""): row for row in assessment_binding.get("source_artifacts") or []}
            required_roles = {"source_exam_docx", "source_memo_docx", "assessment_json", "exam_receipt", "random_subject_assignments", "caps_source_pdf", "rendered_question_paper", "rendered_memo", "marking_rubric"}
            if set(bound_artifacts) != required_roles:
                raise ProfessionalEvidenceProjectionError("HOMS Assess source binding has incomplete or unexpected artifact roles")
            for artifact in bound_artifacts.values():
                relative = str(artifact.get("path") or "")
                source_file = (packet["packet_dir"] / relative).resolve()
                manifest_row = next((row for row in packet["manifest"].get("files") or [] if str(row.get("path") or "") == relative), None)
                if packet["packet_dir"] not in source_file.parents or not source_file.is_file() or not manifest_row:
                    raise ProfessionalEvidenceProjectionError(f"HOMS Assess bound artifact is missing or unmanifested: {relative}")
                digest = sha256(source_file)
                if digest != str(artifact.get("sha256") or "") or digest != str(manifest_row.get("sha256") or ""):
                    raise ProfessionalEvidenceProjectionError(f"HOMS Assess source artifact hash mismatch: {relative}")
            question_paper = source / "uploads" / "question_paper.md"
            memo_file = source / "memo.md"
            if sha256(question_paper) != bound_artifacts["rendered_question_paper"]["sha256"] or sha256(memo_file) != bound_artifacts["rendered_memo"]["sha256"]:
                raise ProfessionalEvidenceProjectionError("HOMS Assess rendered paper or memo does not match the source binding")
            paper_text = question_paper.read_text(encoding="utf-8")
            memo_text = memo_file.read_text(encoding="utf-8")
            assessment_file = packet["packet_dir"] / bound_artifacts["assessment_json"]["path"]
            assessment_data = json.loads(assessment_file.read_text(encoding="utf-8"))
            assessment_questions = {
                str(question.get("number") or ""): question
                for section in assessment_data.get("sections") or []
                for question in section.get("questions") or []
            }
            if not criteria or sum(float(row.get("marks") or 0) for row in criteria) != float(rubric.get("total_marks") or 0):
                raise ProfessionalEvidenceProjectionError("HOMS Assess rubric marks do not reconcile to its declared total")
            for criterion in criteria:
                question = str(criterion.get("question") or "").strip()
                if not question or not re.search(rf"(?m)^{re.escape(question)}\.\s", paper_text) or question not in memo_text:
                    raise ProfessionalEvidenceProjectionError(f"HOMS Assess criterion is not bound to both paper and memo: {question}")
                source_question = assessment_questions.get(question)
                if not source_question:
                    raise ProfessionalEvidenceProjectionError(f"HOMS Assess criterion has no source-bound pointwise memo: {question}")
                points = source_question.get("memo") or source_question.get("marking_points") or []
                if (not isinstance(points, list) or not points
                        or any(not isinstance(point, dict) or not str(point.get("point") or "").strip()
                               or float(point.get("marks") or 0) <= 0 for point in points)
                        or sum(float(point.get("marks") or 0) for point in points) != float(criterion.get("marks") or 0)):
                    raise ProfessionalEvidenceProjectionError(f"HOMS Assess pointwise memo marks do not reconcile for {question}")
                for point in points:
                    if str(point["point"]) not in memo_text:
                        raise ProfessionalEvidenceProjectionError(f"HOMS Assess memo point is missing from the rendered memo: {question}")
            if assessment_binding.get("educator_review_required") is not True or assessment_binding.get("classroom_release_authorized") is not False:
                raise ProfessionalEvidenceProjectionError("HOMS Assess source binding lost its educator/release gate")
            if str(assessment_binding.get("caps_source", {}).get("sha256") or "") != bound_artifacts["caps_source_pdf"]["sha256"]:
                raise ProfessionalEvidenceProjectionError("HOMS Assess CAPS source PDF hash does not match the grade receipt")
            copied_binding = {
                "schema": "dio.homs.assessment_binding_receipt.v1",
                "packet_fingerprint": packet["packet_fingerprint"],
                "grade": int(assessment_binding["grade"]),
                "subject": str(assessment_binding["subject"]),
                "randomization_seed": int(assessment_binding["randomization_seed"]),
                "caps_source_sha256": str(assessment_binding["caps_source"].get("sha256") or ""),
                "verified_artifacts": [{"role": row["role"], "path": row["path"], "sha256": row["sha256"], "bytes": row["bytes"]} for row in assessment_binding["source_artifacts"]],
                "paper_memo_rubric_binding": "PASS",
                "pointwise_marking_binding": {
                    "state": "SOURCE_BOUND",
                    "assessment_json_sha256": bound_artifacts["assessment_json"]["sha256"],
                    "criterion_count": len(criteria),
                    "marking_point_count": sum(len(assessment_questions[str(row["question"])].get("memo") or []) for row in criteria),
                    "criterion_mark_total": sum(float(row.get("marks") or 0) for row in criteria),
                    "point_mark_total": sum(
                        float(point.get("marks") or 0)
                        for row in criteria
                        for point in assessment_questions[str(row["question"])].get("memo") or []
                    ),
                },
                "educator_review_required": True,
                "classroom_release_authorized": False,
            }
            write_json(target / "ASSESSMENT_BINDING_RECEIPT.json", copied_binding)
    else:
        assessment_binding = None
        first = (curriculum_spine.get("opportunities") or {}).get("first") or {}
        questions = list(first.get("questions") or [])
        if not questions:
            raise ProfessionalEvidenceProjectionError("HOMS curriculum spine has no first-opportunity marking points")
        upload_names = {path.name for path in (target / "uploads").iterdir() if path.is_file()}
        missing_bindings = [
            role for role, key in (("paper", "paper"), ("memo", "memo"))
            if Path(str((curriculum_spine.get("handoffs") or {}).get("homs_assess", {}).get(key) or "")).name not in upload_names
        ]
        if missing_bindings:
            raise ProfessionalEvidenceProjectionError(
                "HOMS curriculum spine requires its exact exam paper and memo among uploads: " + ", ".join(missing_bindings)
            )
        first_paths = {"paper": first.get("paper_path"), "memo": first.get("memo_path")}
        for role, expected_path in first_paths.items():
            filename = Path(str(expected_path or "")).name
            uploaded = target / "uploads" / filename
            expected_hash = str(first.get(f"{role}_sha256") or "")
            if not expected_hash or sha256(uploaded) != expected_hash:
                raise ProfessionalEvidenceProjectionError(
                    f"HOMS Assess {role} does not match the hash bound into the curriculum spine"
                )
        for row in questions:
            if not list(row.get("memo") or []):
                raise ProfessionalEvidenceProjectionError(
                    f"HOMS Assess cannot derive a marking criterion without memo points for question {row.get('number') or 'unknown'}"
                )
        item_total = sum(float(row.get("marks") or 0) for row in questions)
        declared_total = float(first.get("total_marks") or 0)
        if not declared_total or item_total != declared_total:
            raise ProfessionalEvidenceProjectionError(
                f"HOMS Assess item marks ({item_total:g}) do not reconcile to the spine total ({declared_total:g})"
            )
        rubric = {
            "assessment_title": f"{(curriculum_spine.get('curriculum') or {}).get('subject', 'Assessment')} · Grade {(curriculum_spine.get('curriculum') or {}).get('grade', '')}",
            "total_marks": first.get("total_marks") or sum(int(row.get("marks") or 0) for row in questions),
            "criteria": [
                {"question": f"{row.get('number') or 'Item'} {row.get('section') or ''}".strip(),
                 "memo": " ; ".join(row.get("memo") or []), "marks": row.get("marks") or 0}
                for row in questions
            ],
        }
        criteria = list(rubric["criteria"])
        shutil.copy2(spine_path, target / "HOMS_CURRICULUM_SPINE.json")
    total = sum(float(row.get("marks") or 0) for row in criteria) or 1.0
    projected_criteria = []
    for row in criteria:
        question = str(row.get("question") or "").strip()
        item = {
            "name": question or "Assessment item",
            "question": question,
            "weight": float(row.get("marks") or 0),
        }
        if assessment_binding:
            source_question = assessment_questions[question]
            item["question_prompt"] = str(source_question.get("prompt") or "")
            source_points = source_question.get("memo") or source_question.get("marking_points") or []
            item["marking_points"] = [
                {
                    "point_id": f"{question}.P{index:02d}",
                    "point": str(point["point"]),
                    "marks": float(point["marks"]),
                }
                for index, point in enumerate(source_points, 1)
            ]
        projected_criteria.append(item)
    projected = {
        "title": str(rubric.get("assessment_title") or "Professional assessment sample"),
        "total_marks": total,
        "grade": rubric.get("grade"),
        "subject": rubric.get("subject"),
        "source_binding_state": "VERIFIED" if assessment_binding else "NOT_SUPPLIED",
        "source_binding_sha256": sha256(binding_path) if assessment_binding else None,
        "criteria": projected_criteria,
    }
    write_json(target / "rubric.json", projected)
    memo = target / "memo.md"
    memo.write_text(
        "# Customer memo / marking boundary\n\n"
        + "\n".join(
            f"- {row.get('question')} ({row.get('marks')} marks):\n"
            + "\n".join(f"  - [{point.get('marks')} mark(s)] {point.get('point')}" for point in (
                assessment_questions[str(row.get("question"))].get("memo") or []
                if assessment_binding else []
            ))
            if assessment_binding else f"- {row.get('question')}: {row.get('memo')} ({row.get('marks')} marks)"
            for row in criteria
        )
        + "\n\nEducator remains final marking authority. Do not infer illegible learner content.\n",
        encoding="utf-8",
    )
    return {
        "schema": "dio.professional_evidence.homs_assess_projection.v1",
        "packet_fingerprint": packet["packet_fingerprint"],
        "input_dir": str(target),
        "submissions": len([path for path in (target / "uploads").iterdir() if path.is_file()]),
        "criteria": len(projected["criteria"]),
        "curriculum_spine_used": bool(curriculum_spine and not raw_rubric.is_file()),
        "assessment_source_binding_verified": bool(assessment_binding),
        "pointwise_marking_point_count": sum(len(row.get("marking_points") or []) for row in projected_criteria),
        "pointwise_marking_state": "SOURCE_BOUND" if assessment_binding else "NOT_SUPPLIED",
        "examiner_data_used": False,
    }


def homs_learning_projection(packet: dict[str, Any], target: Path) -> dict[str, Any]:
    packet_dir = Path(packet["packet_dir"]).resolve()
    spine_path = packet_dir / "SOURCES" / "homs_exam" / "HOMS_CURRICULUM_SPINE.json"
    manifest = json.loads((packet_dir / "CUSTOMER_PACKET_MANIFEST.json").read_text(encoding="utf-8"))
    bound_files = {row["path"]: row for row in manifest.get("files", [])}
    relative_spine = spine_path.relative_to(packet_dir).as_posix()
    if relative_spine not in bound_files or sha256(spine_path) != bound_files[relative_spine]["sha256"]:
        raise ProfessionalEvidenceProjectionError("HOMS Learning Studio curriculum spine is not packet-manifest-bound")
    spine = json.loads(spine_path.read_text(encoding="utf-8"))
    if spine.get("schema") != "dio.homs.curriculum_spine.v1" or spine.get("source_binding", {}).get("customer_packet_case") != "SYNTHETIC-HOMS-LEARNING-EXAM-LINK-001":
        raise ProfessionalEvidenceProjectionError("HOMS Learning Studio curriculum spine has an unexpected schema or source binding")
    request = {
        "schema": "homs.learning_pack.request.v1",
        "pack_id": "PRO-HOMS-LEARN-MOTION-001",
        "subject": "Physical Sciences",
        "grade": 10,
        "phase": "FET",
        "term": 3,
        "topic_id": "motion_in_one_dimension",
        "topic": "Motion in One Dimension",
        "language": "English",
        "curriculum": "South African CAPS",
        "learner_audience": "Grade 10 learners consolidating Term 3 mechanics",
        "buyer_audience": "Teacher preparing a mixed-ability Grade 10 class",
        "include_video_lesson": True,
        "educator_approval_required": True,
        "customer_packet_fingerprint": packet["packet_fingerprint"],
        "curriculum_spine_path": str(spine_path),
        "curriculum_spine_sha256": sha256(spine_path),
    }
    write_json(target, request)
    return request


def document_studio_projection(packet: dict[str, Any], target: Path, *, service: str, incarnation: str) -> dict[str, Any]:
    source = packet["packet_dir"] / "SOURCES" / "source_document.md"
    if not source.is_file():
        raise ProfessionalEvidenceProjectionError(f"{incarnation} requires source_document.md")
    is_translation = service in {"translation", "edit_and_translate"}
    target_language = "Afrikaans" if is_translation else None
    request = {
        "schema": "dio.document_studio.request.v1",
        "job_id": "PRO-" + slug(incarnation).upper().replace("-", "_"),
        "title": f"{incarnation} Professional Customer Run",
        "document_path": str(source),
        "service": service,
        "source_language": "English",
        "target_language": target_language,
        "audience": "Professional customer reviewer",
        "document_domain": "Professional operations",
        "style_standard": "Clear professional South African English; preserve facts, numbers, quotations, identifiers and customer terminology",
        "protected_tokens": ["R18.4 million", "Ubuntu Care Connect", "0800 220 911"],
        "preferred_terms": ([{"source": "appointment confirmation", "target": "afspraakbevestiging", "abbreviation": ""}] if is_translation else []),
        "owner_authorized": True,
        "remote_processing_approved": True,
        "certified_translation_required": False,
        "human_language_review_required": bool(is_translation),
        "provider": "ollama",
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    if is_translation:
        # Select a dedicated local translation provider explicitly in new
        # product requests; never replace a replayed request's declared model.
        request.update({
            "translation_engine": "lingua",
            "lingua_translation_backend": "marian_local",
            "lingua_terminology_profile": "professional_af_v1",
            "remote_processing_approved": False,
            "automated_language_critic": False,
        })
    write_json(target, request)
    return request


def ai_trust_projection(packet: dict[str, Any], *, source_type: str, intended_use: str, inject_actions: bool = False, changed: bool = False) -> dict[str, Any]:
    rows = evidence_rows(packet)
    source_file = packet["packet_dir"] / "SOURCES" / "02_evidence_register.csv"
    source_file_hash = sha256(source_file)
    source_spans = evidence_record_spans(packet)
    packet_digest = packet["packet_fingerprint"].split(":")[-1]

    # A register of customer assertions is not a model baseline, evaluation,
    # observed output, or executable capability grant. Preserve its literal
    # declarations and leave absent technical evidence unknown.
    payload = {
        "source_type": source_type,
        "case_id": "PRO-AI-" + packet_digest[:12].upper(),
        "system": {"intended_use": intended_use, "model": {}},
        "baseline": {},
        "sources": [{"source_ref": "customer-packet://SOURCES/02_evidence_register.csv", "sha256": source_file_hash}],
        "attachments": [{"name": "customer-evidence-register.csv", "sha256": source_file_hash,
                         "text": "\n".join(str(row.get("customer_supplied_record") or "") for row in rows)}],
        "evaluations": [], "requested_actions": [], "allowed_capabilities": [],
        "human_authority": {"state": "NEEDS_YOU"},
        "customer_declarations": [],
        "projection_limits": ["Narrative declarations require technical evidence and human review; no baseline, evaluation result or tool request was inferred."],
        "customer_packet_fingerprint": packet["packet_fingerprint"],
    }
    for index, row in enumerate(rows, 1):
        record_id = str(row.get("record_id") or f"R-{index:02d}")
        statement = str(row.get("customer_supplied_record") or "")
        span = source_spans[record_id]
        payload["customer_declarations"].append({
            "source_locator": record_id,
            "source_ref": f"customer-packet://SOURCES/02_evidence_register.csv#{record_id}",
            "source_file_sha256": source_file_hash,
            "source_row_sha256": span["source_row_sha256"],
            "source_statement_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
            "source_byte_start": span["source_byte_start"],
            "source_byte_end_exclusive": span["source_byte_end_exclusive"],
            "statement": statement,
            "trust_state": "captured_untrusted",
            "freshness_state": "unknown",
        })
    telemetry_path = packet["packet_dir"] / "SOURCES" / "seraph_telemetry.json"
    if telemetry_path.is_file():
        declared = {str(row.get("path") or ""): row for row in packet["manifest"].get("files") or []}
        relative = "SOURCES/seraph_telemetry.json"
        if relative not in declared or sha256(telemetry_path) != declared[relative].get("sha256"):
            raise ProfessionalEvidenceProjectionError("Seraph telemetry export is not bound by the customer packet manifest")
        telemetry_export = json.loads(telemetry_path.read_text(encoding="utf-8"))
        telemetry_case_id = str(telemetry_export.get("case_id") or "")
        telemetry = telemetry_export.get("seraph_telemetry")
        if not telemetry_case_id or not isinstance(telemetry, dict):
            raise ProfessionalEvidenceProjectionError("Seraph telemetry export requires a case_id and telemetry object")
        payload["case_id"] = telemetry_case_id
        payload["seraph_telemetry"] = telemetry
        payload["sources"].append({"source_ref": f"customer-packet://{relative}", "sha256": sha256(telemetry_path)})
        payload["attachments"].append({"name": "seraph_telemetry.json", "sha256": sha256(telemetry_path),
                                       "text": json.dumps(telemetry, sort_keys=True)})
        payload["projection_limits"].append("Seraph telemetry receives offline hash-chain and case-link checks only; signatures, source identity, persistence and live collection remain unverified.")
    return payload


__all__ = [
    "ProfessionalEvidenceProjectionError",
    "ai_trust_projection",
    "binding_receipt",
    "canonical_hash",
    "document_studio_projection",
    "evidence_rows",
    "exception_text",
    "homs_assess_projection",
    "homs_learning_projection",
    "load_packet",
    "obligation_projection",
    "review_projection",
    "sha256",
    "slug",
    "source_inventory",
    "write_json",
]
