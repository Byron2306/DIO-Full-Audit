#!/usr/bin/env python3
"""Exercise educator-entered HOMS Assess mark reconciliation on a synthetic fixture."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUN = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261103_G10_V26"
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_EDUCATOR_RECONCILIATION_DEMO_20261102_V7"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    package = json.loads((RUN / "CUSTOMER_PACKAGE_RECEIPT.json").read_text(encoding="utf-8"))
    binding = json.loads((RUN / "input/ASSESSMENT_BINDING_RECEIPT.json").read_text(encoding="utf-8"))
    rubric = json.loads((RUN / "input/rubric.json").read_text(encoding="utf-8"))
    results_path = (RUN / str(package["outputs"]["results"])).resolve()
    results = json.loads(results_path.read_text(encoding="utf-8"))
    fingerprint = str(package["customer_packet_fingerprint"])

    from products.homs_assess_customer import build_pointwise_educator_review, validate_pointwise_adjudication_csv, _question_answer_blocks
    source_submissions = {}
    for result in results:
        source_path = (RUN / "input" / "uploads" / str(result.get("submission_file") or f"{result['student_id']}.txt")).resolve()
        if not source_path.is_relative_to((RUN / "input" / "uploads").resolve()) or not source_path.is_file():
            raise ValueError("Synthetic reconciliation fixture has no confined source submission")
        source_submissions[str(result["student_id"])] = source_path.read_text(encoding="utf-8")

    handoff = build_pointwise_educator_review(RUN / "input", rubric, results, results_path, OUT / "EDUCATOR_HANDOFF",
                                              customer_packet_fingerprint=fingerprint)
    handoff_csv = handoff["adjudication_path"]
    handoff_flags = handoff["quality_flags_path"]

    blank = validate_pointwise_adjudication_csv(handoff_csv, rubric, results, customer_packet_fingerprint=fingerprint,
                                                quality_flags_csv=handoff_flags, source_submissions=source_submissions)
    if blank["state"] != "NEEDS_EDUCATOR_COMPLETION" or blank["totals_calculated"] or blank["marks_issued"]:
        raise ValueError("blank educator handoff did not remain incomplete and unissued")

    completed = OUT / "SYNTHETIC_EDUCATOR_COMPLETED_ADJUDICATION.csv"
    with handoff_csv.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    if not rows or not fields:
        raise ValueError("source pointwise handoff is empty")
    for row in rows:
        proposal = str(row.get("model_proposed_marks") or "").strip()
        if proposal:
            row["educator_verified_marks"] = proposal
            row["educator_decision"] = "ACCEPT"
            if row.get("point_quote_state") == "NO_EXACT_QUESTION_SCOPED_QUOTE":
                blocks = _question_answer_blocks(source_submissions[str(row["student_id"])])
                block = blocks.get(str(row["criterion_id"]), {})
                row["educator_verified_source_quote"] = str(block.get("text") or "")
        else:
            # The fixture deliberately supplies a human decision for a point the
            # model did not return; this is arithmetic-path evidence, not real marking.
            row["educator_verified_marks"] = "0"
            row["educator_decision"] = "CHANGE"
            row["educator_rationale"] = "Synthetic validator fixture; not an educator judgment."
        row["educator_reviewer"] = "SYNTHETIC-QA-FIXTURE"
        row["reviewed_at"] = "2026-11-03T00:00:00Z"
    with completed.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)

    completed_flags = OUT / "SYNTHETIC_EDUCATOR_COMPLETED_QUALITY_FLAGS.csv"
    with handoff_flags.open("r", encoding="utf-8-sig", newline="") as source:
        quality_reader = csv.DictReader(source)
        quality_rows = list(quality_reader)
        quality_fields = list(quality_reader.fieldnames or [])
    for row in quality_rows:
        row["educator_resolution"] = "RESOLVE"
        row["educator_rationale"] = "Synthetic validator fixture only; not an educator judgment."
        row["educator_reviewer"] = "SYNTHETIC-QA-FIXTURE"
        row["reviewed_at"] = "2026-11-03T00:00:00Z"
    with completed_flags.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=quality_fields)
        writer.writeheader()
        writer.writerows(quality_rows)

    validated = validate_pointwise_adjudication_csv(completed, rubric, results, customer_packet_fingerprint=fingerprint,
                                                    quality_flags_csv=completed_flags, source_submissions=source_submissions)
    totals = validated["educator_reconciled_totals"]
    expected_totals: dict[str, float] = {}
    for row in rows:
        student_id = str(row["student_id"])
        expected_totals[student_id] = expected_totals.get(student_id, 0.0) + float(row["educator_verified_marks"])
    observed_totals = {row["student_id"]: float(row["total_marks"]) for row in totals}
    if (validated["state"] != "EDUCATOR_TOTALS_RECONCILED_REVIEW_REQUIRED"
            or validated["issues"] or validated["incomplete_points"] or validated["unresolved_points"]
            or validated["totals_calculated"] is not True
            or validated["totals_are_reconciliation_only"] is not True
            or validated["marks_issued"] is not False
            or validated["classroom_release_authorized"] is not False
            or len(totals) != len(results)
            or any(row["state"] != "EDUCATOR_ENTERED_RECONCILIATION_REQUIRES_FINAL_REVIEW" for row in totals)
            or observed_totals != {key: round(value, 3) for key, value in expected_totals.items()}):
        raise ValueError("completed educator-mark arithmetic did not reconcile under held, unissued boundary")

    ungrounded_rows = [row for row in rows
                       if row.get("point_quote_state") == "NO_EXACT_QUESTION_SCOPED_QUOTE"
                       and float(row.get("model_proposed_marks") or 0) > 0]
    if not ungrounded_rows:
        raise ValueError("current controlled packet has no positive ungrounded proposal for the acceptance guard")
    adversarial_rows = [dict(row) for row in rows]
    target_key = (ungrounded_rows[0]["student_id"], ungrounded_rows[0]["criterion_id"], ungrounded_rows[0]["point_id"])
    for row in adversarial_rows:
        if (row["student_id"], row["criterion_id"], row["point_id"]) == target_key:
            row["educator_verified_source_quote"] = ""
    adversarial_csv = OUT / "SYNTHETIC_UNGROUNDED_ACCEPT_WITHOUT_QUOTE.csv"
    with adversarial_csv.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(adversarial_rows)
    adversarial = validate_pointwise_adjudication_csv(
        adversarial_csv, rubric, results, customer_packet_fingerprint=fingerprint,
        quality_flags_csv=completed_flags, source_submissions=source_submissions)
    guard_code = "UNGROUNDED_POSITIVE_ACCEPT_REQUIRES_EXACT_QUESTION_SCOPED_EDUCATOR_QUOTE"
    if (not any(issue.get("code") == guard_code and issue.get("key") == list(target_key)
                for issue in adversarial["issues"])
            or adversarial.get("totals_calculated") is not False):
        raise ValueError("ungrounded positive acceptance was not blocked pending an exact educator-verified source quote")

    evidence = {
        "schema": "dio.homs.assess.educator_mark_reconciliation_execution.v1",
        "product": "HOMS Assess",
        "source_run": RUN.relative_to(ROOT).as_posix(),
        "source_execution_sha256": sha(RUN / "CUSTOMER_EXECUTION_RECEIPT.json"),
        "source_packet_fingerprint": fingerprint,
        "source_binding_sha256": sha(RUN / "input/ASSESSMENT_BINDING_RECEIPT.json"),
        "source_rubric_sha256": sha(RUN / "input/rubric.json"),
        "blank_handoff_state": blank["state"],
        "blank_handoff_totals_calculated": False,
        "completed_csv": completed.relative_to(ROOT).as_posix(),
        "completed_csv_sha256": sha(completed),
        "ungrounded_positive_proposals_accepted_with_exact_educator_quote": len(ungrounded_rows),
        "adversarial_accept_without_quote_csv": adversarial_csv.relative_to(ROOT).as_posix(),
        "adversarial_accept_without_quote_csv_sha256": sha(adversarial_csv),
        "adversarial_guard_state": adversarial["state"],
        "adversarial_guard_code": guard_code,
        "adversarial_totals_calculated": adversarial["totals_calculated"],
        "completed_quality_flags_csv": completed_flags.relative_to(ROOT).as_posix(),
        "completed_quality_flags_csv_sha256": sha(completed_flags),
        "completed_validation": validated,
        "fixture_boundary": "The rebuilt educator handoff is source-bound to the controlled run, but every completed point and flag row below is populated only to exercise validation and arithmetic. Synthetic ACCEPT/CHANGE/RESOLVE values, reviewer identity and timestamp are not actual educator decisions or marking evidence.",
        "marks_issued": False,
        "classroom_release_authorized": False,
    }
    receipt = OUT / "EDUCATOR_MARK_RECONCILIATION_EVIDENCE.json"
    receipt.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": receipt.relative_to(ROOT).as_posix(), "point_count": validated["source_point_count"],
                      "learner_count": len(totals), "state": validated["state"], "totals_calculated": True,
                      "ungrounded_acceptance_without_quote_blocked": True,
                      "marks_issued": False, "classroom_release_authorized": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
