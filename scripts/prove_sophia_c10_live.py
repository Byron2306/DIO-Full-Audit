#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.sophia.longitudinal_speculum import _load_project_store  # noqa: E402
from adapters.sophia.scholarly_topology import build_and_write_topology  # noqa: E402


DEFAULT_SOPHIA_ROOT = ROOT / "cross_folder_variants" / "Integritas-Mechanicus" / "A_CODE"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def sha256_json(payload: Any) -> str:
    material = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _case(case_id: str, passed: bool, *, required: bool = True, evidence: Any = None, interpretation: str = "") -> dict[str, Any]:
    return {
        "case_id": case_id,
        "passed": bool(passed),
        "required": bool(required),
        "evidence": evidence,
        "interpretation": interpretation,
    }


def evaluate_proof(
    *,
    job: dict[str, Any],
    longitudinal: dict[str, Any],
    native_record: dict[str, Any],
    topology: dict[str, Any],
) -> dict[str, Any]:
    review = job.get("review") or {}
    revisions = list(job.get("revision_rounds") or [])
    ready_revisions = [
        row for row in revisions
        if (row.get("integrity_enrichment") or {}).get("state") == "integrity_pack_ready"
        and row.get("grounding_passed") is True
    ]
    lineages = list(longitudinal.get("lineages") or [])
    repeated = [row for row in lineages if int(row.get("occurrence_count") or 0) >= 2]
    unresolved = list(longitudinal.get("unresolved_continuity_candidates") or [])
    author_decisions = list(longitudinal.get("author_decisions") or [])
    native_decisions = list(native_record.get("final_decisions") or [])
    claim_records = list(native_record.get("claim_ledger") or [])
    record_ids = [str(row.get("record_id") or "") for row in claim_records if str(row.get("record_id") or "")]
    unique_record_ids = len(record_ids) == len(set(record_ids))
    native_index = native_record.get("authorship_preservation_index") or {}
    authority = str(longitudinal.get("authority_boundary") or "").lower()

    cases = [
        _case(
            "c9_initial_integrity_ready",
            (review.get("c9_integrity") or {}).get("state") == "integrity_pack_ready"
            and review.get("grounding_passed") is True,
            evidence={
                "c9_state": (review.get("c9_integrity") or {}).get("state"),
                "grounding_passed": review.get("grounding_passed"),
            },
            interpretation="The live proof must begin from a grounded C9 integrity pack.",
        ),
        _case(
            "real_revision_integrity_pack_present",
            bool(ready_revisions),
            evidence={"ready_revision_rounds": [row.get("round") for row in ready_revisions]},
            interpretation="At least one author-owned revision must itself complete the governed C9 integrity lane.",
        ),
        _case(
            "two_or_more_bound_draft_versions",
            int(longitudinal.get("version_count") or 0) >= 2,
            evidence={"version_count": longitudinal.get("version_count")},
            interpretation="A longitudinal claim requires at least two bound manuscript versions.",
        ),
        _case(
            "at_least_one_repeated_claim_lineage",
            bool(repeated),
            evidence={
                "repeated_lineages": [
                    {
                        "lineage_id": row.get("lineage_id"),
                        "occurrence_count": row.get("occurrence_count"),
                        "support_trajectory": row.get("support_trajectory"),
                    }
                    for row in repeated[:12]
                ]
            },
            interpretation="Without at least one claim observed across drafts, continuity has not been demonstrated.",
        ),
        _case(
            "version_scoped_native_claim_records_preserved",
            bool(record_ids) and unique_record_ids and len(record_ids) >= int(longitudinal.get("lineage_count") or 0),
            evidence={"native_claim_records": len(record_ids), "unique_record_ids": unique_record_ids},
            interpretation="Native Sophia state must preserve distinct claim occurrences rather than overwrite revision history.",
        ),
        _case(
            "ambiguous_continuity_resolved",
            len(unresolved) == 0,
            evidence={"unresolved_continuity_candidates": len(unresolved)},
            interpretation="Ambiguous paraphrases must be resolved by a human before the proof is considered clean.",
        ),
        _case(
            "human_author_decision_recorded",
            bool(author_decisions),
            evidence={
                "decision_count": len(author_decisions),
                "decisions": [
                    {"lineage_id": row.get("lineage_id"), "decision": row.get("decision"), "actor": row.get("actor")}
                    for row in author_decisions[-8:]
                ],
            },
            interpretation="C10 must preserve at least one explicit human scholarly decision rather than infer intent from text change.",
        ),
        _case(
            "human_decision_persisted_in_native_sophia",
            bool(native_decisions),
            evidence={"native_final_decisions": len(native_decisions)},
            interpretation="The human decision must reach Sophia's native final-decision ledger, not live only in a parallel C10 file.",
        ),
        _case(
            "longitudinal_and_native_hashes_present",
            len(str(longitudinal.get("longitudinal_speculum_hash") or "")) == 64
            and len(str(longitudinal.get("native_integrity_record_hash") or "")) == 64,
            evidence={
                "longitudinal_speculum_hash": longitudinal.get("longitudinal_speculum_hash"),
                "native_integrity_record_hash": longitudinal.get("native_integrity_record_hash"),
            },
            interpretation="Both the C10 interpretation layer and native Sophia evidence state must carry stable receipt hashes.",
        ),
        _case(
            "scholarly_topology_ready_and_hashed",
            topology.get("state") == "scholarly_topology_ready"
            and len(str(topology.get("topology_audit_hash") or "")) == 64
            and len(str(topology.get("decision_queue_hash") or "")) == 64,
            evidence={
                "state": topology.get("state"),
                "topology_audit_hash": topology.get("topology_audit_hash"),
                "decision_queue_hash": topology.get("decision_queue_hash"),
            },
            interpretation="The revision topology and human-decision queue must both be materialized as receipt-bearing C10 evidence.",
        ),
        _case(
            "scholarly_decision_queue_clear",
            int(topology.get("blocking_decision_queue") or 0) == 0,
            evidence={
                "blocking_decision_queue": topology.get("blocking_decision_queue"),
                "open_topology_issues": topology.get("open_topology_issues"),
            },
            interpretation="A C10 victory claim is held while any material scholarly decision obligation remains unresolved.",
        ),
        _case(
            "non_forensic_authority_boundary_preserved",
            "not a forensic" in authority and "misconduct" in authority,
            evidence={"authority_boundary": longitudinal.get("authority_boundary")},
            interpretation="Longitudinal continuity must never silently become authorship or misconduct detection.",
        ),
        _case(
            "native_authorship_metric_remains_unvalidated_engineering_signal",
            native_index.get("validation_status") == "engineering_metric_unvalidated",
            evidence={
                "validation_status": native_index.get("validation_status"),
                "score": native_index.get("score"),
                "band": native_index.get("band"),
            },
            interpretation="The Authorship Preservation Index may describe workflow preservation, not identify who wrote the manuscript.",
        ),
    ]

    required = [row for row in cases if row["required"]]
    passed_required = sum(1 for row in required if row["passed"])
    proof_passed = passed_required == len(required)
    state_counts: dict[str, int] = {}
    for row in lineages:
        state = str(row.get("state") or "unknown")
        state_counts[state] = state_counts.get(state, 0) + 1

    return {
        "schema": "dio.sophia_c10_live_proof_receipt.v2",
        "evaluated_at": now(),
        "proof_passed": proof_passed,
        "result": "C10_LONGITUDINAL_PROOF_PASSED" if proof_passed else "C10_LONGITUDINAL_PROOF_NOT_YET_ESTABLISHED",
        "required_cases_passed": passed_required,
        "required_cases_total": len(required),
        "cases": cases,
        "observed": {
            "version_count": longitudinal.get("version_count"),
            "lineage_count": longitudinal.get("lineage_count"),
            "lineage_state_counts": state_counts,
            "repeated_lineages": len(repeated),
            "author_decisions": len(author_decisions),
            "native_final_decisions": len(native_decisions),
            "burden_mutation_lineages": len(longitudinal.get("burden_mutation_lineages") or []),
            "lineage_resolution_events": len(longitudinal.get("lineage_resolution_events") or []),
            "topology_issue_count": topology.get("topology_issue_count"),
            "open_topology_issues": topology.get("open_topology_issues"),
            "blocking_decision_queue": topology.get("blocking_decision_queue"),
        },
        "truth_boundary": (
            "A passing C10 receipt demonstrates inspectable longitudinal scholarly-memory, revision-topology, and human-decision mechanics on this reviewed case. "
            "It does not prove universal claim-matching accuracy, authorship identity, misconduct, learning gain, publication quality, "
            "or the truth of the manuscript's substantive claims."
        ),
    }


def markdown_receipt(receipt: dict[str, Any]) -> str:
    lines = [
        "# Sophia C10 Live Proof Receipt",
        "",
        f"Result: **{receipt.get('result')}**",
        f"Required gates: **{receipt.get('required_cases_passed')}/{receipt.get('required_cases_total')}**",
        "",
        "## Gates",
        "",
        "| Gate | Result | Interpretation |",
        "|---|---|---|",
    ]
    for row in receipt.get("cases") or []:
        lines.append(
            f"| `{row.get('case_id')}` | {'PASS' if row.get('passed') else 'FAIL'} | {str(row.get('interpretation') or '').replace('|', '/')} |"
        )
    lines.extend([
        "",
        "## Observed",
        "",
        "```json",
        json.dumps(receipt.get("observed") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Truth Boundary",
        "",
        str(receipt.get("truth_boundary") or ""),
        "",
        f"Receipt SHA-256: `{receipt.get('receipt_sha256') or ''}`",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Judge a real Sophia C10 longitudinal proof case from persisted receipts.")
    parser.add_argument("--job-dir", type=Path, required=True, help="Path to state/sophia_jobs/<JOB_ID>.")
    parser.add_argument("--sophia-root", type=Path, default=DEFAULT_SOPHIA_ROOT)
    args = parser.parse_args()

    job_dir = args.job_dir.expanduser().resolve()
    job_path = job_dir / "JOB.json"
    c10_root = job_dir / "C10_LONGITUDINAL_SPECULUM"
    longitudinal_path = c10_root / "LONGITUDINAL_SPECULUM.json"
    if not job_path.is_file():
        raise FileNotFoundError(job_path)
    if not longitudinal_path.is_file():
        raise FileNotFoundError(longitudinal_path)

    job = load_json(job_path)
    longitudinal = load_json(longitudinal_path)
    project_id = str(job.get("job_id") or longitudinal.get("project_id") or job_dir.name)
    sophia_root = args.sophia_root.expanduser().resolve()
    ProjectStore, _resolved = _load_project_store(sophia_root)
    native_record = ProjectStore(c10_root / "project_store").export_integrity_record(project_id=project_id)
    topology = build_and_write_topology(
        state_root=c10_root,
        project_id=project_id,
        sophia_root=sophia_root,
    )

    receipt = evaluate_proof(
        job=job,
        longitudinal=longitudinal,
        native_record=native_record,
        topology=topology,
    )
    receipt["job_id"] = project_id
    receipt["source_receipts"] = {
        "job_json": str(job_path),
        "longitudinal_speculum": str(longitudinal_path),
        "native_integrity_record_hash": native_record.get("integrity_record_hash"),
        "topology_audit_hash": topology.get("topology_audit_hash"),
        "decision_queue_hash": topology.get("decision_queue_hash"),
    }
    receipt["receipt_sha256"] = sha256_json(receipt)
    out_json = c10_root / "C10_LIVE_PROOF_RECEIPT.json"
    out_md = c10_root / "C10_LIVE_PROOF_RECEIPT.md"
    write_json(out_json, receipt)
    out_md.write_text(markdown_receipt(receipt) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=True))
    return 0 if receipt["proof_passed"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Sophia C10 live proof blocked: {error}", file=sys.stderr)
        raise SystemExit(2)
