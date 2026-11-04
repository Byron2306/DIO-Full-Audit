#!/usr/bin/env python3
"""Validate a completed HOMS pointwise adjudication CSV and reconcile educator marks without issuing them."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.homs_assess_customer import validate_pointwise_adjudication_csv


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path, help="HOMS Assess customer execution directory")
    parser.add_argument("--csv", required=True, type=Path, help="Educator-completed copy of the pointwise adjudication CSV")
    parser.add_argument("--quality-flags-csv", type=Path, help="Educator-completed source quality-flag review CSV")
    parser.add_argument("--output", type=Path, help="Validation receipt path (defaults beside the CSV)")
    args = parser.parse_args()

    run_dir = args.run_dir.expanduser().resolve()
    csv_path = args.csv.expanduser().resolve()
    if not run_dir.is_dir() or not csv_path.is_file():
        parser.error("run directory and completed CSV must both exist")
    package_path = run_dir / "CUSTOMER_PACKAGE_RECEIPT.json"
    execution_path = run_dir / "CUSTOMER_EXECUTION_RECEIPT.json"
    binding_path = run_dir / "input" / "ASSESSMENT_BINDING_RECEIPT.json"
    rubric_path = run_dir / "input" / "rubric.json"
    if not all(path.is_file() for path in (package_path, execution_path, binding_path, rubric_path)):
        parser.error("run directory lacks package, execution, assessment binding, or rubric receipt")
    package, execution, binding = map(read_json, (package_path, execution_path, binding_path))
    if (package.get("product_name") != "HOMS Assess"
            or package.get("classroom_release_authorized") is not False
            or package.get("external_processing") is not False
            or execution.get("release_authorized") is not False
            or execution.get("external_effects") is not False
            or binding.get("classroom_release_authorized") is not False
            or binding.get("paper_memo_rubric_binding") != "PASS"):
        parser.error("source run identity or held-release boundary is invalid")
    if (package.get("customer_packet_fingerprint") != binding.get("packet_fingerprint")
            or package.get("assessment_binding_sha256") != sha(binding_path)):
        parser.error("customer packet fingerprint or assessment binding hash does not match")
    results_path = (run_dir / str((package.get("outputs") or {}).get("results") or "")).resolve()
    if not results_path.is_relative_to(run_dir) or not results_path.is_file():
        parser.error("source run results path is missing or escapes the run directory")
    execution_artifacts = {str(row.get("path") or ""): str(row.get("sha256") or "") for row in execution.get("artifacts") or []}
    for source in (package_path, binding_path, rubric_path, results_path):
        relative = source.relative_to(run_dir).as_posix()
        expected_hash = execution_artifacts.get(relative)
        if not expected_hash or expected_hash != sha(source):
            parser.error(f"source artifact hash drifted: {relative}")
    point_binding = binding.get("pointwise_marking_binding") or {}
    rubric = read_json(rubric_path)
    declared_point_count = sum(len(row.get("marking_points") or []) for row in rubric.get("criteria") or [])
    if (int(point_binding.get("marking_point_count") or -1) != declared_point_count
            or point_binding.get("state") != "SOURCE_BOUND"
            or binding.get("grade") != package.get("grade")
            or str(binding.get("subject") or "").casefold() != str(package.get("subject") or "").casefold()):
        parser.error("bound grade/subject or source point allocation does not match the run rubric")

    results = read_json(results_path)
    from products.homs_assess_customer import DEFAULT_HYMARK_BACKEND, load_hymark_backend
    source_submissions = {}
    for result in results:
        student_id = str(result.get("student_id") or "")
        filename = str(result.get("submission_file") or f"{student_id}.txt")
        source_path = (run_dir / "input" / "uploads" / filename).resolve()
        uploads = (run_dir / "input" / "uploads").resolve()
        if not source_path.is_relative_to(uploads) or not source_path.is_file():
            parser.error(f"source submission is missing or escapes the uploaded source directory: {filename}")
        if source_path.suffix.lower() in {".txt", ".md"}:
            source_text = source_path.read_text(encoding="utf-8")
        else:
            extractor = load_hymark_backend(Path(DEFAULT_HYMARK_BACKEND))
            source_text = str(extractor.extract_document_content(source_path) or "")
        source_submissions[student_id] = source_text
    quality_flags_path = args.quality_flags_csv.expanduser().resolve() if args.quality_flags_csv else None
    if quality_flags_path is None:
        default_flags = run_dir / str((package.get("outputs") or {}).get("quality_flag_review_csv") or "")
        if default_flags.is_file():
            quality_flags_path = default_flags.resolve()
    validated = validate_pointwise_adjudication_csv(
        csv_path, rubric, results,
        customer_packet_fingerprint=str(package["customer_packet_fingerprint"]),
        quality_flags_csv=quality_flags_path,
        source_submissions=source_submissions,
    )
    validated.update({
        "source_run_dir": str(run_dir),
        "source_package_sha256": sha(package_path),
        "source_assessment_binding_sha256": sha(binding_path),
        "source_rubric_sha256": sha(rubric_path),
        "source_results_sha256": sha(results_path),
        "quality_flags_csv": str(quality_flags_path) if quality_flags_path else None,
        "quality_flags_csv_sha256": sha(quality_flags_path) if quality_flags_path and quality_flags_path.is_file() else None,
    })
    output = args.output.expanduser().resolve() if args.output else csv_path.with_name(csv_path.stem + "_VALIDATION.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(validated, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"state": validated["state"], "source_point_count": validated["source_point_count"],
                      "incomplete_points": validated["incomplete_points"], "unresolved_points": validated["unresolved_points"],
                      "unresolved_quality_flags": validated["unresolved_quality_flag_count"],
                      "issues": len(validated["issues"]), "totals_calculated": validated["totals_calculated"],
                      "reconciled_learner_count": len(validated["educator_reconciled_totals"]),
                      "marks_issued": False, "classroom_release_authorized": False,
                      "receipt": str(output)}, indent=2))
    return 0 if not validated["issues"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
