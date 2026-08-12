from __future__ import annotations

import hashlib
import html
import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from dio.obligations.engine import build as build_obligations
from dio.obligations.engine import project as project_obligations
from dio.obligations.extractor import extract
from evidence.sufficiency import assess_sufficiency
from products.compiler import compile_manifest
from products.governed_case import add_evidence, new_case, validate_case


ROOT = Path(__file__).resolve().parents[2]
PROVIDER_ID = "obligation_family_proof_pack_v1"
EXECUTOR_ID = "obligation_family_internal_runner_v1"
REQUIRED_ARTIFACT_TYPES = ("JSON", "DOCX", "PDF", "HTML", "proof_room_manifest")
FAMILY_DEFINITIONS = {
    "dio_tenderproof": {"slug": "tenderproof", "title": "DIO TenderProof", "source_type": "tender", "framework": "framework.tender_submission", "owner_role": "tender_owner"},
    "dio_grantproof": {"slug": "grantproof", "title": "DIO GrantProof", "source_type": "grant", "framework": "framework.grant_award", "owner_role": "grant_owner"},
    "dio_permitproof": {"slug": "permitproof", "title": "DIO PermitProof", "source_type": "permit", "framework": "framework.permit_conditions", "owner_role": "permit_owner"},
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write(path: Path, value: bytes) -> str:
    path.write_bytes(value)
    return _sha(value)


def _docx(title: str, pack: dict[str, Any]) -> bytes:
    body = [title, json.dumps(pack, sort_keys=True, ensure_ascii=False)]
    xml = "<?xml version='1.0' encoding='UTF-8' standalone='yes'?><w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body>" + "".join(f"<w:p><w:r><w:t xml:space='preserve'>{xml_escape(row)}</w:t></w:r></w:p>" for row in body) + "<w:sectPr/></w:body></w:document>"
    types = "<?xml version='1.0' encoding='UTF-8'?><Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'><Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/><Default Extension='xml' ContentType='application/xml'/><Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/></Types>"
    rels = "<?xml version='1.0' encoding='UTF-8'?><Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'><Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/></Relationships>"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in (("[Content_Types].xml", types), ("_rels/.rels", rels), ("word/document.xml", xml)):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content.encode("utf-8"))
    return buffer.getvalue()


def _pdf(title: str, pack: dict[str, Any]) -> bytes:
    text = (title + " | " + json.dumps(pack, sort_keys=True, ensure_ascii=True)).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    chunks = [text[i:i + 88] for i in range(0, min(len(text), 6000), 88)]
    stream = ("BT /F1 8 Tf 36 806 Td 10 TL " + " ".join(("T* " if i else "") + f"({row}) Tj" for i, row in enumerate(chunks)) + " ET").encode("latin-1", "replace")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>", b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out)); out.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(out); out.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]: out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(out)


def _map_evidence(case: dict[str, Any], source: dict[str, Any], inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    locators = {str(row["source_locator"]): str(row["obligation_id"]) for row in extract(source)}
    mapped = []
    for index, item in enumerate(inputs, 1):
        targets = [str(value) for value in item.get("target_locators") or []]
        if not targets or any(target not in locators for target in targets):
            raise ValueError(f"family evidence input {index} requires known target_locators")
        row = add_evidence(case, kind=str(item.get("evidence_kind") or "source_record"), source_ref=str(item.get("source_ref") or f"evidence://family/{index}"), sha256=item.get("sha256"), observed_at=item.get("observed_at"), effective_at=item.get("effective_at"), expires_at=item.get("expires_at"), authority_grade=str(item.get("authority_grade") or "source_backed"), trust_state=str(item.get("trust_state") or "captured_untrusted"), freshness_state=str(item.get("freshness_state") or "unknown"))
        mapped.append({"evidence_id": row["evidence_id"], "obligation_ids": [locators[target] for target in targets], "evidence_kind": row["kind"], "source_ref": row["source_ref"], "relation": str(item.get("relation") or "supports"), "trust_state": row["trust_state"], "freshness_state": row["freshness_state"]})
    return mapped


def run_family_proof(product_id: str, source: dict[str, Any], evidence_inputs: list[dict[str, Any]], *, output_dir: Path, operator_id: str, now: str, job_id: str | None = None) -> dict[str, Any]:
    definition = FAMILY_DEFINITIONS.get(product_id)
    if not definition:
        raise ValueError(f"unsupported obligation-family product: {product_id}")
    if not str(operator_id or "").strip():
        raise ValueError("obligation-family execution requires an explicit operator_id")
    if source.get("source_type") != definition["source_type"]:
        raise ValueError(f"{product_id} requires source_type={definition['source_type']}")
    manifest = ROOT / "config" / "products" / "manifests" / f"{definition['slug']}.json"
    compiled = compile_manifest(ROOT, manifest)
    required = [row for row in compiled["capability_plan"] if row["required"]]
    if any(row["resolution_state"] != "RESOLVED" for row in required):
        raise RuntimeError("obligation-family manifest has unresolved required capabilities")
    executor = next(row for row in required if row["capability_id"] == f"product.executor.{definition['slug']}")["provider"]
    if executor.get("provider_id") != EXECUTOR_ID or compiled["gates"]["execution"]["state"] != "NEEDS_YOU" or compiled["gates"]["external_release"]["state"] != "REFUSE":
        raise RuntimeError("obligation-family authority boundary is not intact")
    output_dir = output_dir.resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    required_sections = sorted({str(item) for row in compiled["output_plan"]["outputs"] for item in row.get("required_sections") or []})
    case = new_case(product=product_id, job_id=str(job_id or f"golden-{source['source_id']}"), source={"source": {"path": source["source_ref"]}}, source_path=manifest, evidence_inputs=[], expected_outputs=list(REQUIRED_ARTIFACT_TYPES), required_authorities=[definition["owner_role"], "evidence_reviewer"], intake_state="approved", framework_ids=[definition["framework"]], subject_ref=source["source_ref"], now=now)
    bundle = build_obligations(source, evidence_records=_map_evidence(case, source, evidence_inputs), now=now)
    projection = project_obligations(bundle, case); validate_case(case)
    sufficiency = assess_sufficiency(case)
    evaluations = {row["obligation_id"]: row for row in bundle.get("evaluations") or []}
    pack = {"product_id": product_id, "case_id": case["case_id"], "requirement_or_obligation_ledger": [{**row, "evaluation": evaluations.get(row["obligation_id"])} for row in bundle.get("obligations") or []], "evidence_map": bundle.get("evidence_bindings") or [], "missing_evidence_register": sufficiency.get("gaps") or [], "contested_state_register": [row for row in bundle.get("evaluations") or [] if row.get("status") in {"CONTESTED", "NEEDS_REVIEW"}], "deadline_register": bundle.get("deadlines") or [], "human_review_register": {"fulfilment": "NEEDS_YOU", "disclosure": "NEEDS_YOU", "external_release": "REFUSE"}, "provenance_manifest": {"source": bundle.get("source"), "bundle_fingerprint": bundle["fingerprint"], "projection": projection, "authority_created": False, "external_effects": False}}
    missing_sections = sorted(set(required_sections).difference(pack))
    if missing_sections: raise RuntimeError(f"evidence pack missing required sections: {missing_sections}")
    rendered = {"JSON": ("EVIDENCE_PACK.json", json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n"), "HTML": ("EVIDENCE_PACK.html", ("<!doctype html><meta charset=utf-8><h1>" + html.escape(definition["title"]) + "</h1><pre>" + html.escape(json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False)) + "</pre>").encode()), "DOCX": ("EVIDENCE_PACK.docx", _docx(definition["title"], pack)), "PDF": ("EVIDENCE_PACK.pdf", _pdf(definition["title"], pack))}
    artifacts = [{"artifact_type": kind, "filename": name, "sha256": _write(output_dir / name, body)} for kind, (name, body) in rendered.items()]
    proof = {"schema": "dio.obligation_family.proof_manifest.v1", "provider_id": PROVIDER_ID, "product_id": product_id, "artifact_type": "proof_room_manifest", "case_id": case["case_id"], "obligation_bundle_fingerprint": bundle["fingerprint"], "required_sections": required_sections, "artifacts": artifacts, "human_gate": {"state": "NEEDS_YOU"}, "authority_created": False, "execution_performed": False, "external_release": False}
    proof["proof_fingerprint"] = "sha256:" + _sha(_canonical(proof)); _write(output_dir / "PROOF_MANIFEST.json", json.dumps(proof, indent=2, sort_keys=True).encode() + b"\n")
    counts: dict[str, int] = {}
    for row in bundle.get("evaluations") or []: counts[row["status"]] = counts.get(row["status"], 0) + 1
    receipt = {"schema": "dio.obligation_family.execution_receipt.v1", "executor_id": EXECUTOR_ID, "product_id": product_id, "case_id": case["case_id"], "operator_id": operator_id, "executed_at": now, "obligation_status_counts": counts, "evidence_sufficiency_state": sufficiency["state"], "proof_fingerprint": proof["proof_fingerprint"], "internal_processing": "COMPLETE", "human_fulfilment_gate": "NEEDS_YOU", "external_release_gate": "REFUSE", "authority_created": False, "waiver_created": False, "legal_opinion_created": False, "award_or_permit_decision_created": False, "external_effects": False, "external_release": False}
    _write(output_dir / "FAMILY_RECEIPT.json", json.dumps(receipt, indent=2, sort_keys=True).encode() + b"\n")
    return {"receipt": receipt, "case": case, "obligation_bundle": bundle, "sufficiency": sufficiency, "proof_manifest": proof, "output_dir": str(output_dir)}
