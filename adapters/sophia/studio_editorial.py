from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from adapters.sophia.review_pipeline import parse_reference_entries, reference_key


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def audit_article_lineage(manifest: dict[str, Any]) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    if contract["kind"] != "article":
        raise ValueError("Sophia editorial audit requires Article Publication Studio")
    source_fixture = contract.get("source_fixture") or []
    reference_text = "\n\n".join(str(row["citation"]) for row in source_fixture if not str(row["citation"]).startswith("Customer packet "))
    parsed = parse_reference_entries(reference_text) if reference_text else []
    academic_index = 0
    if len(parsed) != sum(not str(row["citation"]).startswith("Customer packet ") for row in source_fixture):
        raise ValueError("Sophia reference parser did not preserve the controlled source fixture")
    source_rows = []
    source_ids = set()
    for fixture in source_fixture:
        source_id = str(fixture["source_id"])
        source_ids.add(source_id)
        citation = str(fixture["citation"])
        customer_source = re.fullmatch(
            r"Customer packet (?:sha256:)?([0-9a-f]{64}) SOURCES/02_evidence_register\.csv record (R-[0-9]{2}); customer assertion, not independently verified\.",
            citation,
        )
        if customer_source:
            parsed_entry = citation
            key = f"CUSTOMER_PACKET_RECORD:{customer_source.group(2)}:{customer_source.group(1)}"
            source_kind = "customer_packet_record"
        else:
            parsed_entry = parsed[academic_index]
            academic_index += 1
            key = reference_key(parsed_entry)
            source_kind = "academic_reference"
        if not key:
            raise ValueError(f"Sophia could not derive an author-year reference key for {source_id}")
        row = {
            "source_id": source_id,
            "citation": parsed_entry,
            "reference_key": key,
            "source_kind": source_kind,
            "supports": sorted(str(value) for value in fixture.get("supports") or []),
        }
        row["fingerprint"] = _fingerprint(row)
        source_rows.append(row)
    claim_rows = []
    for claim in contract.get("claim_fixture") or []:
        evidence_ids = [str(value) for value in claim.get("evidence_ids") or []]
        unknown = sorted(set(evidence_ids) - source_ids)
        if unknown:
            raise ValueError(f"Sophia claim references unknown source ids: {unknown}")
        if claim.get("state") == "SUPPORTED" and not evidence_ids:
            raise ValueError(f"Sophia supported claim lacks source lineage: {claim.get('claim_id')}")
        row = {
            "claim_id": str(claim["claim_id"]),
            "text": str(claim["text"]),
            "epistemic_state": str(claim["state"]),
            "evidence_ids": evidence_ids,
            "source_lineage_valid": not unknown and (bool(evidence_ids) or claim.get("state") != "SUPPORTED"),
        }
        row["fingerprint"] = _fingerprint(row)
        claim_rows.append(row)
    body = {
        "schema": "dio.sophia_article_lineage_audit.v1",
        "studio_id": manifest["studio_id"],
        "references": source_rows,
        "claims": claim_rows,
        "source_reference_audit": "PASS",
        "claim_lineage_audit": "PASS",
        "publication_authority": "REFUSE",
        "fabricated_source_authority": "REFUSE",
        "fabricated_quotation_authority": "REFUSE",
        "authority_created": False,
        "source_engine": "sophia",
        "capabilities_executed": ["source.reference.audit", "claim.lineage.audit"],
    }
    body["audit_fingerprint"] = _fingerprint(body)
    return body
