#!/usr/bin/env python3
"""Capture a held DIO AI Assurance route with explicit Seraph case binding."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/DIO_AI_ASSURANCE_TELEMETRY_CASE_BINDING_20261102_V2"
SOURCE_PACKET = ROOT / "acceptance_runs/68-product-sellability-20261027/SERAPH_TELEMETRY_AI_PROFILE_EXECUTIONS_20261101_V2/case-04-dio-ai-assurance/CUSTOMER_PACKET"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    receipt_path = OUT / "EXECUTION" / "DIO_AI_ASSURANCE_CUSTOMER_RECEIPT.json"
    if not receipt_path.is_file():
        if OUT.exists() and any(OUT.iterdir()):
            raise ValueError(f"output directory is nonempty and has no completed route receipt: {OUT}")
        from products.customer_product_router import run_customer_product
        run_customer_product("DIO AI Assurance", {
            "owner_authorized": True,
            "customer_packet_dir": str(SOURCE_PACKET),
            "operator_id": "controlled-telemetry-binding-demo",
            "as_of": "2026-11-02T12:00:00+02:00",
            "synthetic_acceptance_not_customer_evidence": True,
        }, OUT, render_pdf=False)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    binding = receipt["seraph_telemetry_review"]["customer_source_binding"]
    assessment = receipt["seraph_telemetry_review"]["assessment"]
    if (binding.get("case_binding_state") != "DECLARED_CASE_ID_MISMATCH"
            or assessment.get("state") != "INVALID_CHAIN"
            or receipt.get("human_review_gate") != "NEEDS_YOU"
            or receipt.get("external_release_gate") != "REFUSE"
            or receipt.get("external_effects") is not False):
        raise ValueError("DIO AI Assurance failed to expose the telemetry case mismatch under its held boundary")
    pack = json.loads((OUT / "EXECUTION" / "DIOAIASSURANCE_REVIEW_PACK.json").read_text(encoding="utf-8"))
    telemetry_rows = [row for row in pack.get("requirement_evidence_matrix", []) if row.get("requirement_key") == "AI-ASSURANCE-SERAPH-TELEMETRY"]
    if len(telemetry_rows) != 1 or telemetry_rows[0].get("review_state") != "CONTESTED" or not telemetry_rows[0].get("source_provenance"):
        raise ValueError("Seraph telemetry mismatch is absent from the controlled evidence review matrix")
    evidence = {
        "schema": "dio.dio_ai_assurance.telemetry_case_binding_evidence.v1",
        "product_name": "DIO AI Assurance",
        "run": OUT.relative_to(ROOT).as_posix(),
        "customer_execution_sha256": sha(OUT / "CUSTOMER_EXECUTION_RECEIPT.json"),
        "package_receipt_sha256": sha(OUT / "NATIVE_CUSTOMER_PACKET_RECEIPT.json"),
        "assurance_receipt_sha256": sha(receipt_path),
        "telemetry_source_sha256": binding["source_sha256"],
        "telemetry_case_binding_state": binding["case_binding_state"],
        "telemetry_chain_state": assessment["state"],
        "telemetry_matrix_review_state": telemetry_rows[0]["review_state"],
        "human_review_gate": receipt["human_review_gate"],
        "external_release_gate": receipt["external_release_gate"],
        "external_effects": receipt["external_effects"],
        "synthetic_acceptance_input": True,
    }
    evidence_path = OUT / "SERAPH_TELEMETRY_CASE_BINDING_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
