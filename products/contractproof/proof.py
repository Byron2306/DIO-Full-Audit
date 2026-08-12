from __future__ import annotations

import hashlib
import html
import json
import zipfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape


PROVIDER_ID = "contractproof_proof_pack_v1"
PROOF_SCHEMA = "dio.contractproof.proof_manifest.v1"
REQUIRED_ARTIFACT_TYPES = ("JSON", "DOCX", "PDF", "HTML", "proof_room_manifest")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_bytes(path: Path, body: bytes) -> str:
    path.write_bytes(body)
    return _sha256_bytes(body)


def _write_json(path: Path, payload: Any) -> str:
    body = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    return _write_bytes(path, body)


def _semantic_pack(case: dict[str, Any], obligation_bundle: dict[str, Any], sufficiency: dict[str, Any], projection_receipt: dict[str, Any]) -> dict[str, Any]:
    obligations = obligation_bundle.get("obligations") or []
    evaluations = {str(row["obligation_id"]): row for row in obligation_bundle.get("evaluations") or []}
    requirement_map = projection_receipt.get("requirement_map") or {}
    requirements = {str(row["requirement_id"]): row for row in case.get("requirements") or []}
    ledger = []
    for obligation in obligations:
        obligation_id = str(obligation["obligation_id"])
        requirement_id = requirement_map.get(obligation_id)
        requirement = requirements.get(str(requirement_id)) or {}
        evaluation = evaluations.get(obligation_id) or {}
        ledger.append({
            "obligation_id": obligation_id,
            "requirement_id": requirement_id,
            "source_locator": (obligation.get("source") or {}).get("locator"),
            "statement": obligation.get("statement"),
            "responsible_party": obligation.get("responsible_party"),
            "due_at": obligation.get("due_at"),
            "expires_at": obligation.get("expires_at"),
            "status": obligation.get("status"),
            "status_basis": obligation.get("status_basis") or [],
            "requirement_state": requirement.get("state"),
            "evidence_ids": list(requirement.get("evidence_ids") or []),
            "human_gate": evaluation.get("human_gate", "NEEDS_YOU"),
        })
    evidence_map = [{
        "evidence_id": row["evidence_id"], "kind": row["kind"], "source_ref": row["source_ref"], "sha256": row.get("sha256"),
        "authority_grade": row["authority_grade"], "trust_state": row["trust_state"], "freshness_state": row["freshness_state"],
        "supports_requirement_ids": list(row.get("supports_requirement_ids") or []),
        "supports_claim_ids": list(row.get("supports_claim_ids") or []),
        "contradicts_claim_ids": list(row.get("contradicts_claim_ids") or []),
    } for row in case.get("evidence") or []]
    missing = [row for row in obligation_bundle.get("evaluations") or [] if row.get("status") in {"PARTIAL", "MISSING", "EXPIRED", "NOT_YET_DUE", "NEEDS_REVIEW"}]
    contested = [row for row in obligation_bundle.get("evaluations") or [] if row.get("status") == "CONTESTED"]
    return {
        "schema": "dio.contractproof.evidence_pack.v1",
        "product_id": "dio_contractproof",
        "case_id": case["case_id"],
        "requirement_or_obligation_ledger": ledger,
        "evidence_map": evidence_map,
        "missing_evidence_register": missing,
        "contested_state_register": contested,
        "deadline_register": obligation_bundle.get("deadlines") or [],
        "human_review_register": {
            "obligation_bundle_gate": obligation_bundle.get("human_gate"),
            "evidence_sufficiency_gate": sufficiency.get("human_gate"),
            "review_required_obligation_ids": [row["obligation_id"] for row in obligations if row.get("review_required") is True],
            "fulfilment_judgement": "NEEDS_YOU",
            "disclosure_judgement": "NEEDS_YOU",
            "external_release": "REFUSE",
        },
        "provenance_manifest": {
            "case_id": case["case_id"],
            "obligation_source": obligation_bundle.get("source"),
            "obligation_bundle_fingerprint": obligation_bundle["fingerprint"],
            "projection_receipt": projection_receipt,
            "event_refs": list(case.get("event_refs") or []),
            "authority_created": False,
            "external_effects": False,
        },
    }


def _validate_required_sections(pack: dict[str, Any], required_sections: list[str]) -> None:
    missing = [section for section in required_sections if section not in pack]
    if missing:
        raise ValueError(f"ContractProof evidence pack missing output-profile sections: {missing}")


def _render_html(pack: dict[str, Any], required_sections: list[str]) -> bytes:
    blocks = []
    for section in required_sections:
        value = json.dumps(pack[section], indent=2, sort_keys=True, ensure_ascii=False)
        blocks.append(f"<section><h2>{html.escape(section)}</h2><pre>{html.escape(value)}</pre></section>")
    return ("<!doctype html><html><head><meta charset='utf-8'><title>DIO ContractProof Evidence Pack</title></head><body><h1>DIO ContractProof Evidence Pack</h1>" + "".join(blocks) + "</body></html>").encode("utf-8")


def _docx_bytes(pack: dict[str, Any], required_sections: list[str]) -> bytes:
    from io import BytesIO
    paragraphs = ["DIO ContractProof Evidence Pack"]
    for section in required_sections:
        paragraphs.extend([section, json.dumps(pack[section], sort_keys=True, ensure_ascii=False)])
    document_xml = "<?xml version='1.0' encoding='UTF-8' standalone='yes'?><w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body>" + "".join(f"<w:p><w:r><w:t xml:space='preserve'>{xml_escape(text)}</w:t></w:r></w:p>" for text in paragraphs) + "<w:sectPr/></w:body></w:document>"
    content_types = "<?xml version='1.0' encoding='UTF-8'?><Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'><Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/><Default Extension='xml' ContentType='application/xml'/><Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/></Types>"
    rels = "<?xml version='1.0' encoding='UTF-8'?><Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'><Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/></Relationships>"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in (("[Content_Types].xml", content_types), ("_rels/.rels", rels), ("word/document.xml", document_xml)):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content.encode("utf-8"))
    return buffer.getvalue()


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_bytes(pack: dict[str, Any], required_sections: list[str]) -> bytes:
    lines = ["DIO ContractProof Evidence Pack", f"Case: {pack['case_id']}"]
    for section in required_sections:
        compact = json.dumps(pack[section], sort_keys=True, ensure_ascii=True)
        lines.append(section)
        lines.extend(compact[offset : offset + 90] for offset in range(0, len(compact), 90))
    pages = [lines[index : index + 42] for index in range(0, len(lines), 42)] or [[]]
    page_object_ids: list[int] = []
    next_id = 4
    content_pairs: list[tuple[int, int, list[str]]] = []
    for page_lines in pages:
        page_id, content_id = next_id, next_id + 1
        next_id += 2
        page_object_ids.append(page_id)
        content_pairs.append((page_id, content_id, page_lines))
    max_id = next_id - 1
    object_map: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{' '.join(f'{item} 0 R' for item in page_object_ids)}] /Count {len(page_object_ids)} >>".encode("ascii"),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for page_id, content_id, page_lines in content_pairs:
        commands = ["BT", "/F1 9 Tf", "50 790 Td", "12 TL"]
        for index, line in enumerate(page_lines):
            if index:
                commands.append("T*")
            commands.append(f"({_pdf_escape(line)}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", errors="replace")
        object_map[content_id] = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        object_map[page_id] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode("ascii")
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (max_id + 1)
    for object_id in range(1, max_id + 1):
        offsets[object_id] = len(output)
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(object_map[object_id])
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for object_id in range(1, max_id + 1):
        output.extend(f"{offsets[object_id]:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(output)


def _proof_identity(manifest: dict[str, Any]) -> dict[str, Any]:
    return {key: manifest.get(key) for key in (
        "schema", "provider_id", "product_id", "artifact_type", "case_id", "obligation_bundle_fingerprint",
        "required_sections", "artifacts", "human_gate", "authority_created", "execution_performed", "external_release",
    )}


def compile_portable_room(case: dict[str, Any], obligation_bundle: dict[str, Any], sufficiency: dict[str, Any], projection_receipt: dict[str, Any], output_dir: Path, *, required_sections: list[str]) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pack = _semantic_pack(case, obligation_bundle, sufficiency, projection_receipt)
    _validate_required_sections(pack, required_sections)
    rendered = {
        "JSON": ("EVIDENCE_PACK.json", (json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")),
        "HTML": ("EVIDENCE_PACK.html", _render_html(pack, required_sections)),
        "DOCX": ("EVIDENCE_PACK.docx", _docx_bytes(pack, required_sections)),
        "PDF": ("EVIDENCE_PACK.pdf", _pdf_bytes(pack, required_sections)),
    }
    artifacts: list[dict[str, Any]] = []
    for artifact_type in ("JSON", "DOCX", "PDF", "HTML"):
        filename, body = rendered[artifact_type]
        artifacts.append({"artifact_type": artifact_type, "filename": filename, "sha256": _write_bytes(output_dir / filename, body)})
    manifest = {
        "schema": PROOF_SCHEMA,
        "provider_id": PROVIDER_ID,
        "product_id": "dio_contractproof",
        "artifact_type": "proof_room_manifest",
        "case_id": case["case_id"],
        "obligation_bundle_fingerprint": obligation_bundle["fingerprint"],
        "proof_fingerprint": "",
        "required_sections": list(required_sections),
        "artifacts": artifacts,
        "human_gate": {"state": "NEEDS_YOU", "reason": "An authorised contract owner controls any disclosure or contractual judgement based on this pack."},
        "authority_created": False,
        "execution_performed": False,
        "external_release": False,
    }
    manifest["proof_fingerprint"] = f"sha256:{_sha256_bytes(_canonical(_proof_identity(manifest)).encode('utf-8'))}"
    _write_json(output_dir / "PROOF_MANIFEST.json", manifest)
    return manifest


def verify_integrity(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    manifest = json.loads((output_dir / "PROOF_MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != PROOF_SCHEMA or manifest.get("artifact_type") != "proof_room_manifest":
        raise ValueError("unexpected ContractProof proof manifest identity")
    failures: list[str] = []
    if manifest.get("provider_id") != PROVIDER_ID or manifest.get("product_id") != "dio_contractproof":
        failures.append("manifest:provider_or_product")
    if (manifest.get("human_gate") or {}).get("state") != "NEEDS_YOU":
        failures.append("manifest:human_gate")
    if manifest.get("authority_created") is not False or manifest.get("execution_performed") is not False or manifest.get("external_release") is not False:
        failures.append("manifest:authority_boundary")
    expected_proof_fingerprint = f"sha256:{_sha256_bytes(_canonical(_proof_identity(manifest)).encode('utf-8'))}"
    if manifest.get("proof_fingerprint") != expected_proof_fingerprint:
        failures.append("manifest:fingerprint")
    observed = {"proof_room_manifest"}
    for artifact in manifest.get("artifacts") or []:
        artifact_type = str(artifact.get("artifact_type") or "")
        observed.add(artifact_type)
        artifact_path = output_dir / str(artifact.get("filename") or "")
        if not artifact_path.is_file():
            failures.append(f"missing:{artifact_type}")
            continue
        if _sha256_bytes(artifact_path.read_bytes()) != artifact.get("sha256"):
            failures.append(f"hash:{artifact_type}")
    failures.extend(f"manifest_missing:{item}" for item in sorted(set(REQUIRED_ARTIFACT_TYPES).difference(observed)))
    return {
        "schema": "dio.contractproof.integrity_verification.v1",
        "case_id": manifest.get("case_id"),
        "proof_fingerprint": manifest.get("proof_fingerprint"),
        "verified": not failures,
        "failures": failures,
        "authority_created": False,
        "execution_performed": False,
    }


def prepare_disclosure(output_dir: Path) -> dict[str, Any]:
    verification = verify_integrity(output_dir)
    if not verification["verified"]:
        raise ValueError(f"ContractProof proof pack failed integrity verification: {verification['failures']}")
    return {
        "schema": "dio.contractproof.disclosure_candidate.v1",
        "product_id": "dio_contractproof",
        "case_id": verification["case_id"],
        "proof_fingerprint": verification["proof_fingerprint"],
        "state": "INTERNAL_REVIEW_CANDIDATE",
        "human_gate": {"state": "NEEDS_YOU", "reason": "The internal proof pack requires authorised human review before any disclosure decision."},
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "release_authority_created": False,
    }
