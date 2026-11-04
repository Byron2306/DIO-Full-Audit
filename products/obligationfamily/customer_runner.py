"""Customer-source runner for GrantProof, PermitProof, PolicyProof and TenderProof."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from dio.obligations.models import OBLIGATION_KINDS
from products.obligationfamily.runner import FAMILY_DEFINITIONS, run_family_proof


PRODUCTS = {
    "GrantProof": "dio_grantproof",
    "PermitProof": "dio_permitproof",
    "PolicyProof": "dio_policyproof",
    "TenderProof": "dio_tenderproof",
}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_quote_provenance(source_text: str, statement: str, *, source_hash: str) -> dict[str, Any]:
    """Bind each exact candidate quote to all matching source byte/line ranges."""
    matches: list[dict[str, int]] = []
    cursor = 0
    while True:
        start = source_text.find(statement, cursor)
        if start < 0:
            break
        end = start + len(statement)
        matches.append({
            "character_start": start,
            "character_end_exclusive": end,
            "byte_start": len(source_text[:start].encode("utf-8")),
            "byte_end_exclusive": len(source_text[:end].encode("utf-8")),
            "line_start": source_text.count("\n", 0, start) + 1,
            "line_end": source_text.count("\n", 0, max(start, end - 1)) + 1,
        })
        cursor = start + 1
    if not matches:
        raise ValueError("source quote provenance could not reproduce a previously accepted exact obligation quote")
    return {
        "source_file_ref": "customer_sources/governing_instrument.txt",
        "source_file_sha256": source_hash,
        "source_statement_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
        "source_statement_utf8_bytes": len(statement.encode("utf-8")),
        "source_match_count": len(matches),
        "source_match_state": "UNIQUE_EXACT_MATCH" if len(matches) == 1 else "REPEATED_EXACT_MATCH_REVIEW_REQUIRED",
        "source_matches": matches,
        "source_byte_start": matches[0]["byte_start"] if len(matches) == 1 else None,
        "source_byte_end_exclusive": matches[0]["byte_end_exclusive"] if len(matches) == 1 else None,
        "source_line_start": matches[0]["line_start"] if len(matches) == 1 else None,
        "source_line_end": matches[0]["line_end"] if len(matches) == 1 else None,
    }


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value.strip()


def build_obligation_family_customer_package(
    product_name: str, packet: Mapping[str, Any], output_dir: str | Path,
) -> dict[str, Any]:
    """Compile explicit source-quoted obligation candidates into a held review pack."""
    product_id = PRODUCTS.get(product_name)
    if not product_id:
        raise ValueError(f"unsupported obligation-family customer product: {product_name}")
    if packet.get("owner_authorized") is not True:
        raise ValueError("owner_authorized=true is required for source processing")
    definition = FAMILY_DEFINITIONS[product_id]
    source_text = _text(packet.get("source_text"), "source_text")
    source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    source_id = _text(packet.get("source_id") or f"CUSTOMER-{definition['slug'].upper()}", "source_id")
    if not IDENTIFIER.fullmatch(source_id):
        raise ValueError("source_id must be a safe identifier")
    obligations_input = packet.get("obligations")
    if not isinstance(obligations_input, list) or not obligations_input:
        raise ValueError("obligations must contain source-quoted review candidates")
    clauses = []
    locators: set[str] = set()
    for index, row in enumerate(obligations_input, 1):
        if not isinstance(row, Mapping):
            raise ValueError("each obligation candidate must be an object")
        locator = _text(row.get("locator"), f"obligations[{index}].locator")
        statement = _text(row.get("statement"), f"obligations[{index}].statement")
        if not IDENTIFIER.fullmatch(locator) or locator in locators:
            raise ValueError("obligation locators must be unique safe identifiers")
        if statement not in source_text:
            raise ValueError(f"obligation candidate {locator} is not an exact quote from source_text")
        kind = str(row.get("kind") or "other")
        if kind not in OBLIGATION_KINDS:
            raise ValueError(f"obligation candidate {locator} has unsupported kind {kind}")
        locators.add(locator)
        clauses.append({
            "clause_id": locator, "text": statement, "statement": statement,
            "source_provenance": _source_quote_provenance(source_text, statement, source_hash=source_hash),
            "obligation": True, "obligation_kind": kind,
            "responsible_party": str(row.get("responsible_party") or "Unassigned by source"),
            "due_at": row.get("due_at"), "expires_at": row.get("expires_at"),
            "review_required": True,
            "evidence_requirements": [str(value) for value in row.get("evidence_requirements") or ["customer evidence"]],
        })

    evidence_inputs = packet.get("evidence") or []
    if not isinstance(evidence_inputs, list):
        raise ValueError("evidence must be a list")
    out = Path(output_dir).resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("customer output directory must be empty")
    out.mkdir(parents=True, exist_ok=True)
    source_dir = out / "customer_sources"
    source_dir.mkdir()
    source_path = source_dir / "governing_instrument.txt"
    source_path.write_text(source_text, encoding="utf-8")
    evidence_records = []
    for index, row in enumerate(evidence_inputs, 1):
        if not isinstance(row, Mapping):
            raise ValueError("each evidence item must be an object")
        evidence_id = _text(row.get("evidence_id") or f"E-{index:03d}", "evidence_id")
        evidence_text = _text(row.get("text"), f"evidence[{evidence_id}].text")
        targets = [str(value) for value in row.get("target_locators") or []]
        if not targets or not set(targets).issubset(locators):
            raise ValueError(f"evidence {evidence_id} must target known obligation locators")
        relation = str(row.get("relation") or "supports")
        if relation not in {"supports", "contradicts"}:
            raise ValueError(f"evidence {evidence_id} relation must be supports or contradicts")
        evidence_path = source_dir / f"evidence_{index:03d}.txt"
        evidence_path.write_text(evidence_text, encoding="utf-8")
        evidence_bytes = evidence_path.read_bytes()
        evidence_sha256 = hashlib.sha256(evidence_bytes).hexdigest()
        evidence_records.append({
            "evidence_id": evidence_id,
            "record_id": evidence_id,
            "source_ref": str(row.get("source_ref") or f"customer-evidence://{evidence_id}"),
            "source_file_ref": str(evidence_path.relative_to(out)),
            "sha256": evidence_sha256,
            "source_file_sha256": evidence_sha256,
            "source_row_sha256": evidence_sha256,
            "source_statement_sha256": hashlib.sha256(evidence_text.encode("utf-8")).hexdigest(),
            "source_byte_start": 0,
            "source_byte_end_exclusive": len(evidence_bytes),
            "association_state": "CUSTOMER_MAPPED_TO_SOURCE_LOCATOR",
            "association_note": "Caller-supplied evidence relation and target locator remain unverified.",
            "evidence_kind": str(row.get("evidence_kind") or "customer_record"),
            "observed_at": row.get("observed_at"), "effective_at": row.get("effective_at"),
            "expires_at": row.get("expires_at"), "target_locators": targets,
            "relation": relation, "authority_grade": "self_asserted",
            "trust_state": "captured_untrusted", "freshness_state": "unknown",
        })

    source = {
        "source_id": source_id,
        "source_type": definition["source_type"],
        "source_ref": str(packet.get("source_ref") or f"customer-instrument://{source_id}"),
        "sha256": source_hash,
        "effective_at": packet.get("effective_at"), "expires_at": packet.get("expires_at"),
        "clauses": clauses,
    }
    if packet.get("source_sha256") and str(packet["source_sha256"]).removeprefix("sha256:") != source_hash:
        raise ValueError("source_sha256 does not match the exact UTF-8 source_text")
    now = str(packet.get("as_of") or datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    result = run_family_proof(
        product_id, source, evidence_records, output_dir=out / "evidence_pack",
        operator_id=str(packet.get("operator_id") or "customer-packet-operator"),
        now=now, job_id=str(packet.get("case_id") or source_id),
    )
    if result["receipt"].get("external_release_gate") != "REFUSE" or result["receipt"].get("human_fulfilment_gate") != "NEEDS_YOU":
        raise RuntimeError("obligation-family customer route crossed its human/release boundary")
    manifest = {
        "schema": "dio.obligation_family.customer_package.v1",
        "product_name": product_name, "product_id": product_id,
        "case_id": result["receipt"]["case_id"],
        "source_sha256": source_hash,
        "evidence_count": len(evidence_records),
        "obligation_candidate_count": len(clauses),
        "obligation_status_counts": result["receipt"]["obligation_status_counts"],
        "evidence_sufficiency_state": result["receipt"]["evidence_sufficiency_state"],
        "artifacts": [
            {"path": str(path.relative_to(out)), "bytes": path.stat().st_size, "sha256": _sha(path)}
            for path in sorted(out.rglob("*")) if path.is_file()
        ],
        "human_review_required": True,
        "legal_opinion_created": False,
        "award_or_permit_decision_created": False,
        "authority_created": False,
        "external_effects": False,
        "external_release": "REFUSE",
        "synthetic_acceptance_case": packet.get("synthetic_acceptance_not_customer_evidence") is True,
        "claim_boundary": "Candidate extraction and evidence bindings are preparation for human review. Customer statements remain untrusted; this is not legal advice, policy approval, permit or grant determination, tender submission or proof of fulfilment.",
    }
    (out / "CUSTOMER_OBLIGATION_FAMILY_RECEIPT.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest
