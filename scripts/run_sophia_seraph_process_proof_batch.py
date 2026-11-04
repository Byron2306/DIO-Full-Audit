#!/usr/bin/env python3
"""Run all five Sophia customer routes with Seraph-bound process telemetry."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = ROOT / "acceptance_runs/68-product-sellability-20261027/NATIVE_PACKET_CUSTOMER_EXECUTIONS_20261102_V1"
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/SOPHIA_SERAPH_PROCESS_PROOF_20261102_V2"
PRODUCTS = (
    ("Sophia Integrity", "sophia-integrity", True),
    ("Sophia Research", "sophia-research", False),
    ("Sophia Review", "sophia-review", True),
    ("Sophia Supervisor", "sophia-supervisor", False),
    ("Sophia Tutor", "sophia-tutor", True),
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    from products.ai_trust.seraph_telemetry import assess_telemetry
    from products.professional_evidence_execution import _build_sophia_seraph_process_proof

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for product, packet_slug, required in PRODUCTS:
        customer_packet = SOURCE / packet_slug / "CUSTOMER_PACKET"
        if not customer_packet.is_dir():
            raise FileNotFoundError(f"missing prior manifested Sophia packet: {customer_packet}")
        source_run = SOURCE / packet_slug
        packet_manifest = json.loads((customer_packet / "CUSTOMER_PACKET_MANIFEST.json").read_text(encoding="utf-8"))
        source_package = json.loads((source_run / "NATIVE_CUSTOMER_PACKET_RECEIPT.json").read_text(encoding="utf-8"))
        native_job = source_run / "EXECUTION/sophia_native" / ("PRO-" + packet_slug.upper())
        receipt_path = native_job / "SOPHIA_REVIEW_RECEIPT.json"
        commentary_path = native_job / "REVIEWER_COMMENTARY.json"
        request_path = source_run / "PROJECTION/SOPHIA_REVIEW_REQUEST.json"
        source_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        commentary = json.loads(commentary_path.read_text(encoding="utf-8"))
        request = json.loads(request_path.read_text(encoding="utf-8"))
        source_path = customer_packet / "SOURCES/manuscript.md"
        if (commentary.get("status") != "held_diagnostic_draft"
                or (commentary.get("diagnostic_validation") or {}).get("passed") is not True
                or source_receipt.get("preparation_state") != "engineering_draft_prepared"
                or (source_receipt.get("metrics") or {}).get("diagnostic_source_checks_passed") is not True
                or source_receipt.get("constitutional_release_authorized") is not False
                or source_receipt.get("delivery_released") is not False
                or sha(source_path.read_bytes()) != (source_receipt.get("source") or {}).get("sha256")):
            raise ValueError(f"{product}: archived source-bound Sophia route is not a valid held diagnostic")
        destination = OUT / packet_slug
        trace_dir = destination / "process_proof"
        trace_dir.mkdir(parents=True)
        proof = _build_sophia_seraph_process_proof(
            incarnation=product,
            packet_fingerprint=str(packet_manifest.get("packet_fingerprint") or ""),
            source_sha256=str((source_receipt.get("source") or {}).get("sha256") or ""),
            provider=str(commentary.get("provider") or ""),
            model=str(commentary.get("model") or ""),
            external_retrieval=bool(request.get("external_retrieval")),
            telemetry_required=required,
            receipt_path=receipt_path,
            commentary_path=commentary_path,
            output_dir=trace_dir,
            created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            source_review_created_at=str(source_receipt.get("created_at") or ""),
            capture_mode="RETROSPECTIVE_BOUNDED_RECONSTRUCTION",
        )
        trace_path = trace_dir / "SERAPH_PROCESSING_TRACE.json"
        challenge_path = trace_dir / "SERAPH_PROCESSING_CHALLENGE_RECEIPT.json"
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        challenge = json.loads(challenge_path.read_text(encoding="utf-8"))
        assessment = assess_telemetry({"case_id": trace["case_id"], "seraph_telemetry": trace["telemetry"]})
        if (proof.get("schema") != "dio.sophia.seraph_processing_proof.v1"
                or proof.get("telemetry_required_by_customer") is not required
                or proof.get("trace_sha256") != sha(trace_path.read_bytes())
                or proof.get("challenge_receipt_sha256") != sha(challenge_path.read_bytes())
                or assessment.get("state") != "HASH_CHAIN_VERIFIED"
                or assessment.get("event_count") != 3 or assessment.get("audit_count") != 3
                or assessment.get("signature_state") != "UNVERIFIED"
                or assessment.get("source_identity_state") != "UNVERIFIED"
                or challenge.get("verdict") != "INSUFFICIENT_EVIDENCE"
                or challenge.get("execution_authorized") is not False
                or trace.get("capture_mode") != "RETROSPECTIVE_BOUNDED_RECONSTRUCTION"
                or (source_package.get("native_receipt") or {}).get("authority_created") is not False
                or source_package.get("external_effects") is not False):
            raise ValueError(f"{product}: Seraph chain verification or held-review boundary failed")
        rows.append({
            "product_name": product,
            "status": "EXECUTED",
            "proof_extension": destination.relative_to(ROOT).as_posix(),
            "source_native_run": source_run.relative_to(ROOT).as_posix(),
            "seraph_telemetry_required": required,
            "trace_sha256": proof["trace_sha256"],
            "challenge_receipt_sha256": proof["challenge_receipt_sha256"],
            "chain_state": assessment["state"],
            "event_count": assessment["event_count"],
            "audit_count": assessment["audit_count"],
            "challenge_verdict": challenge["verdict"],
            "signature_state": assessment["signature_state"],
            "source_identity_state": assessment["source_identity_state"],
            "source_review_created_at": source_receipt.get("created_at"),
            "delivery_released": source_receipt.get("delivery_released"),
            "authority_created": (source_package.get("native_receipt") or {}).get("authority_created"),
            "external_effects": source_package.get("external_effects"),
            "source_receipt_sha256": sha(receipt_path.read_bytes()),
            "source_commentary_sha256": sha(commentary_path.read_bytes()),
            "artifacts": {
                path.relative_to(trace_dir).as_posix(): sha(path.read_bytes())
                for path in sorted(trace_dir.rglob("*")) if path.is_file()
            },
        })
    receipt = {
        "schema": "dio.sophia.seraph_process_proof_batch.v1",
        "created_at": "2026-11-02",
        "capture_mode": "RETROSPECTIVE_BOUNDED_RECONSTRUCTION_FROM_PRIOR_SOURCE_BOUND_SOPHIA_RUNS",
        "synthetic_acceptance_inputs_only": True,
        "results": rows,
        "summary": {
            "products": len(rows),
            "hash_chains_verified": sum(row["chain_state"] == "HASH_CHAIN_VERIFIED" for row in rows),
            "customer_required_true": sum(row["seraph_telemetry_required"] for row in rows),
            "customer_required_false": sum(not row["seraph_telemetry_required"] for row in rows),
            "all_challenges_remain_non_authorizing": all(row["authority_created"] is False and row["external_effects"] is False for row in rows),
        },
        "claim_boundary": "Seraph verified route-generated internal hash chains only. These unsigned traces do not establish independent signer identity, trusted time, live collection, full runtime telemetry, or the correctness of Sophia's academic conclusions.",
    }
    receipt_path = OUT / "SERAPH_PROCESS_PROOF_BATCH_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
