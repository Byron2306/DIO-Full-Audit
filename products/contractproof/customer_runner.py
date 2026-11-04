"""Vesper-fronted customer intake for the bounded ContractProof engine."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from dio.obligations.models import OBLIGATION_KINDS
from products.contractproof.runner import run_contractproof


_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value.strip()


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def run_customer_contractproof(packet: Mapping[str, Any], output_dir: str | Path) -> dict[str, Any]:
    """Quarantine literal customer sources in Vesper before ContractProof runs."""
    if packet.get("owner_authorized") is not True:
        raise ValueError("owner_authorized=true is required for source processing")
    source_text = _text(packet.get("source_text"), "source_text")
    source_id = _text(packet.get("source_id") or "CUSTOMER-CONTRACT", "source_id")
    if not _IDENTIFIER.fullmatch(source_id):
        raise ValueError("source_id must be a safe identifier")
    raw_obligations = packet.get("obligations")
    if not isinstance(raw_obligations, list) or not raw_obligations:
        raise ValueError("obligations must contain source-located contract clauses")
    obligations = []
    locators: set[str] = set()
    for row in raw_obligations:
        if not isinstance(row, Mapping):
            raise ValueError("each obligation must be an object")
        locator = _text(row.get("locator"), "obligation.locator")
        statement = _text(row.get("statement"), f"obligation[{locator}].statement")
        kind = str(row.get("kind") or "other")
        if not _IDENTIFIER.fullmatch(locator) or locator in locators:
            raise ValueError("obligation locators must be unique safe identifiers")
        if statement not in source_text:
            raise ValueError(f"obligation {locator} is not an exact quotation in source_text")
        if kind not in OBLIGATION_KINDS:
            raise ValueError(f"obligation {locator} uses an unsupported kind: {kind}")
        locators.add(locator)
        obligations.append({
            "clause_id": locator, "text": statement, "obligation": True,
            "obligation_kind": kind, "responsible_party": str(row.get("responsible_party") or "Unassigned by source"),
            "due_at": row.get("due_at"), "expires_at": row.get("expires_at"),
            "review_required": True,
            "evidence_requirements": [str(value) for value in row.get("evidence_requirements") or ["customer evidence"]],
        })

    raw_evidence = packet.get("evidence") or []
    if not isinstance(raw_evidence, list):
        raise ValueError("evidence must be a list")
    evidence_records = []
    for index, row in enumerate(raw_evidence, 1):
        if not isinstance(row, Mapping):
            raise ValueError("each evidence record must be an object")
        evidence_id = _text(row.get("evidence_id") or f"E-{index:02d}", "evidence_id")
        evidence_text = _text(row.get("text"), f"evidence[{evidence_id}].text")
        targets = [str(value) for value in row.get("target_locators") or []]
        if not targets or not set(targets).issubset(locators):
            raise ValueError(f"evidence {evidence_id} must target known obligation locators")
        relation = str(row.get("relation") or "supports")
        if relation not in {"supports", "contradicts"}:
            raise ValueError(f"evidence {evidence_id} relation must be supports or contradicts")
        evidence_records.append({
            "evidence_id": evidence_id,
            "source_ref": str(row.get("source_ref") or f"customer-evidence://{evidence_id}"),
            "filename": f"evidence_{index:03d}.txt",
            "target_locators": targets,
            "evidence_kind": str(row.get("evidence_kind") or "customer_record"),
            "observed_at": row.get("observed_at"), "effective_at": row.get("effective_at"),
            "expires_at": row.get("expires_at"), "relation": relation,
            "text": evidence_text,
        })

    out = Path(output_dir).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("ContractProof output directory must be empty")
    out.mkdir(parents=True, exist_ok=True)
    packet_dir = out / "CUSTOMER_PACKET"
    source_dir = packet_dir / "SOURCES"
    source_dir.mkdir(parents=True)
    (source_dir / "contract_source.txt").write_text(source_text + "\n", encoding="utf-8")
    for row in evidence_records:
        (source_dir / row["filename"]).write_text(row["text"] + "\n", encoding="utf-8")
    request_record = {
        "schema": "dio.contractproof.customer_source.v1",
        "case_id": str(packet.get("case_id") or source_id),
        "title": str(packet.get("title") or "Contract obligations review"),
        "source_id": source_id,
        "source_type": str(packet.get("source_type") or "contract"),
        "source_ref": str(packet.get("source_ref") or f"customer-contract://{source_id}"),
        "effective_at": packet.get("effective_at"), "expires_at": packet.get("expires_at"),
        "obligations": obligations,
        "evidence": [{key: value for key, value in row.items() if key != "text"} for row in evidence_records],
        "parties": packet.get("parties") or [],
        "owner_role": str(packet.get("owner_role") or "contract owner"),
        "human_review_required": True, "legal_interpretation_claimed": False,
    }
    if request_record["source_type"] != "contract":
        raise ValueError("ContractProof customer workflow requires source_type=contract")
    _json(source_dir / "obligation_request.json", request_record)
    request_text = _text(packet.get("request") or f"Prepare a source-bound obligation and evidence review for {request_record['title']}.", "request")
    (packet_dir / "CUSTOMER_REQUEST.md").write_text(request_text + "\n", encoding="utf-8")
    intake = {
        "case_id": request_record["case_id"], "request": request_text,
        "customer": {"organisation": str((request_record["parties"] or ["Customer"])[0]), "buyer_role": request_record["owner_role"]},
        "external_release_authorised": False,
    }
    _json(packet_dir / "INTAKE.json", intake)
    files = []
    for path in sorted(source_dir.iterdir()):
        if path.is_file():
            files.append({"path": str(path.relative_to(packet_dir)), "sha256": _sha_bytes(path.read_bytes()), "bytes": path.stat().st_size})
    fingerprint_body = json.dumps({"case_id": request_record["case_id"], "request": request_text, "files": files}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    packet_fingerprint = "sha256:" + _sha_bytes(fingerprint_body)
    manifest = {"schema": "dio.customer_packet_manifest.v1", "case_id": request_record["case_id"], "packet_fingerprint": packet_fingerprint, "examiner_truth_in_packet": False, "files": files}
    _json(packet_dir / "CUSTOMER_PACKET_MANIFEST.json", manifest)
    customer_packet = {"packet_dir": packet_dir, "manifest_path": packet_dir / "CUSTOMER_PACKET_MANIFEST.json", "manifest": manifest, "intake": intake, "packet_fingerprint": packet_fingerprint}

    now = str(packet.get("review_at") or datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    from products.vesper_web_chat import bind_professional_customer_packet
    from products.professional_evidence_vesper_gate import _rehydrate_sources_from_quarantine

    vesper_root = out / "VESPER_WEB_CHAT"
    vesper_binding = bind_professional_customer_packet(customer_packet, "ContractProof", output_dir=vesper_root, now=now)
    if vesper_binding.get("channel") != "web_chat" or vesper_binding.get("handoff_state") != "READY_FOR_PRODUCT_EXECUTION" or vesper_binding.get("resolved_incarnation") != "ContractProof":
        raise RuntimeError("Vesper did not complete the ContractProof product handoff")
    source_bindings = _rehydrate_sources_from_quarantine(customer_packet, vesper_root)
    if not source_bindings or any(row.get("rehydrated_into_product_packet") is not True for row in source_bindings):
        raise RuntimeError("ContractProof sources were not rehydrated from Vesper quarantine")

    request_record = json.loads((source_dir / "obligation_request.json").read_text(encoding="utf-8"))
    source_text = (source_dir / "contract_source.txt").read_text(encoding="utf-8").rstrip("\n")
    clauses = request_record["obligations"]
    source = {
        "source_id": request_record["source_id"], "source_type": request_record["source_type"],
        "source_ref": request_record["source_ref"],
        "sha256": _sha_bytes((source_text + "\n").encode("utf-8")),
        "effective_at": request_record.get("effective_at"), "expires_at": request_record.get("expires_at"),
        "clauses": clauses,
    }
    evidence_inputs = []
    for row in request_record["evidence"]:
        evidence_path = source_dir / row["filename"]
        evidence_inputs.append({
            "evidence_kind": row["evidence_kind"], "source_ref": row["source_ref"],
            "sha256": _sha_bytes(evidence_path.read_bytes()), "observed_at": row.get("observed_at"),
            "effective_at": row.get("effective_at"), "expires_at": row.get("expires_at"),
            "target_locators": row["target_locators"], "relation": row["relation"],
            "authority_grade": "self_asserted", "trust_state": "captured_untrusted", "freshness_state": "unknown",
        })
    source_receipt = {
        "schema": "dio.contractproof.customer_source.v1", **request_record,
        "source_text": source_text, "source": source,
        "evidence_text_hashes": {row["filename"]: _sha_bytes((source_dir / row["filename"]).read_bytes()) for row in request_record["evidence"]},
    }
    _json(out / "CUSTOMER_CONTRACTPROOF_SOURCE.json", source_receipt)
    result = run_contractproof(
        source, evidence_inputs, output_dir=out / "contractproof",
        operator_id=str(packet.get("operator_id") or "customer-contractproof-operator"),
        now=now, job_id=request_record["case_id"],
        review_context={
            "engagement": {"title": request_record["title"], "parties": request_record["parties"], "owner_role": request_record["owner_role"], "review_at": now},
            "source_clauses": clauses,
        },
    )
    processor_receipt = result.get("receipt") or {}
    if processor_receipt.get("internal_processing") != "COMPLETE" or processor_receipt.get("proof_integrity_verified") is not True:
        raise RuntimeError("ContractProof did not complete proof integrity verification")
    if processor_receipt.get("external_release_gate") != "REFUSE" or processor_receipt.get("human_fulfilment_gate") != "NEEDS_YOU":
        raise RuntimeError("ContractProof human and release boundaries changed")
    if any(processor_receipt.get(key) is not False for key in ("authority_created", "waiver_created", "legal_opinion_created", "external_effects", "external_release")):
        raise RuntimeError("ContractProof created forbidden authority or effects")
    draft = out / "CUSTOMER_NEXT_STEP_DRAFT.md"
    draft.write_text("# Draft only — not sent\n\nThe ContractProof evidence pack is ready for review by the contract owner. This draft makes no legal conclusion and remains unsent.\n", encoding="utf-8")
    artifacts = [{"path": str(path.relative_to(out)), "bytes": path.stat().st_size, "sha256": _sha_bytes(path.read_bytes())}
                 for path in sorted(out.rglob("*")) if path.is_file()]
    receipt = {
        "schema": "dio.contractproof.customer_package.v1", "case_id": request_record["case_id"],
        "product_id": "dio_contractproof", "source_sha256": source["sha256"],
        "vesper_web_chat_binding": vesper_binding, "vesper_source_bindings": source_bindings,
        "processor_receipt": processor_receipt, "proof_integrity": result.get("integrity"),
        "draft_delivery": {"path": draft.name, "state": "DRAFT_ONLY", "send_authorized": False, "sent": False},
        "human_review_required": True, "legal_opinion_created": False, "waiver_created": False,
        "external_release": "REFUSE", "authority_created": False, "external_effects": False,
        "commercial_validation": "UNPROVED",
        "synthetic_acceptance_case": packet.get("synthetic_acceptance_not_customer_evidence") is True,
        "artifacts": artifacts,
    }
    _json(out / "CONTRACTPROOF_CUSTOMER_RECEIPT.json", receipt)
    return receipt
