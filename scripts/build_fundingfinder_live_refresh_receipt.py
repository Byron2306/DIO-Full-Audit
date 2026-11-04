#!/usr/bin/env python3
"""Validate and summarize a FundingFinder official-source refresh run."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "acceptance_runs/68-product-sellability-20261027/funding-finder/reviewed/official-refresh-20261104-v3"
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/FUNDINGFINDER_LIVE_REFRESH_RECEIPT_20261104_V3.json"
CASES = {
    "south-africa-moya-live": {"NYDA-GRANT", "TIA-SEED"},
    "south-africa-agri-live": {"NYDA-GRANT", "TIA-SEED"},
    "uk-jurisdiction-mismatch-live": {"UK-LOTTERY"},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    acceptance = read(RUN / "acceptance_summary.json")
    if not set(CASES).issubset(acceptance):
        raise ValueError("live-source acceptance summary is missing a required scenario")
    scenarios = []
    artifact_index = []
    summary_path = RUN / "acceptance_summary.json"
    artifact_index.append({"path": summary_path.relative_to(ROOT).as_posix(), "sha256": sha(summary_path), "kind": "pipeline_acceptance_summary"})
    for label, expected_ids in CASES.items():
        summary = acceptance[label]
        if summary.get("actual_official_retrieval") is not True or summary.get("qa_passed") is not True:
            raise ValueError(f"{label} did not complete live retrieval and pipeline QA")
        if summary.get("as_of") != "2026-11-04" or summary.get("applicant_is_synthetic") is not True:
            raise ValueError(f"{label} has an unexpected date or applicant provenance")
        case = RUN / label
        source_path = case / "source_register.json"
        matrix_path = case / "eligibility_matrix.json"
        package_path = case / "package_manifest.json"
        source_doc, matrix, package = read(source_path), read(matrix_path), read(package_path)
        sources = source_doc.get("opportunities") or []
        rows = matrix.get("opportunities") or []
        if {row.get("opportunity_id") for row in sources} != expected_ids or {row.get("opportunity_id") for row in rows} != expected_ids:
            raise ValueError(f"{label} source register and eligibility matrix do not contain the expected opportunities")
        for artifact in package.get("artifacts") or []:
            path = case / str(artifact.get("path") or "")
            if not path.is_file() or sha(path) != artifact.get("sha256") or path.stat().st_size != artifact.get("bytes"):
                raise ValueError(f"{label} package manifest contains a missing or changed artifact: {artifact.get('path')}")
        for source in sources:
            raw = case / str(source.get("raw_path") or "")
            text = case / str(source.get("text_path") or "")
            if (source.get("http_status") != 200 or source.get("synthetic") is not False
                    or source.get("transport") != "HTTPS public-IP-pinned GET; no redirects"
                    or not str(source.get("retrieved_at") or "").startswith("2026-11-04T")
                    or not raw.is_file() or not text.is_file()
                    or sha(raw) != source.get("sha256") or len(raw.read_bytes()) != source.get("bytes")):
                raise ValueError(f"{label}/{source.get('opportunity_id')} is not a verified current official capture")
            artifact_index.append({"path": raw.relative_to(ROOT).as_posix(), "sha256": sha(raw), "kind": "official_source_raw_bytes"})
            artifact_index.append({"path": text.relative_to(ROOT).as_posix(), "sha256": sha(text), "kind": "official_source_visible_text"})
        results = {row.get("id"): row for row in summary.get("opportunities", [])}
        matrix_by_id = {row.get("opportunity_id"): row for row in rows}
        if set(results) != expected_ids:
            raise ValueError(f"{label} acceptance summary omitted an opportunity result")
        for opportunity_id, result in results.items():
            row = matrix_by_id[opportunity_id]
            if result.get("fit") != row.get("fit_state") or result.get("timing") != row.get("timing_state"):
                raise ValueError(f"{label}/{opportunity_id} acceptance summary differs from its eligibility matrix")
        if label.startswith("south-africa-"):
            if any(row.get("fit_state") == "appears_aligned_on_supplied_record" for row in rows):
                raise ValueError("synthetic South African applicants must not receive an apparent-alignment result")
        if label == "uk-jurisdiction-mismatch-live" and matrix_by_id["UK-LOTTERY"].get("fit_state") != "mismatch_on_supplied_record":
            raise ValueError("England-only programme did not remain a mismatch for the South African applicant")
        snapshot_path = RUN / "packets" / f"{label}-snapshot.json"
        if not snapshot_path.is_file():
            raise ValueError(f"{label} offline replay snapshot is missing")
        for path in (source_path, matrix_path, package_path, case / "controlled_funding_review.zip", snapshot_path):
            artifact_index.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "kind": "review_output"})
        scenarios.append({
            "scenario": label,
            "as_of": summary["as_of"],
            "applicant_synthetic": True,
            "qa_passed": True,
            "opportunities": [
                {"id": oid, "fit_state": matrix_by_id[oid]["fit_state"],
                 "timing_state": matrix_by_id[oid]["timing_state"],
                 "source_sha256": matrix_by_id[oid]["source_sha256"]}
                for oid in sorted(expected_ids)
            ],
            "source_register": source_path.relative_to(ROOT).as_posix(),
            "eligibility_matrix": matrix_path.relative_to(ROOT).as_posix(),
            "package_manifest": package_path.relative_to(ROOT).as_posix(),
        })
    report = {
        "schema": "dio.fundingfinder.live_source_refresh_receipt.v1",
        "product": "FundingFinder",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "as_of": "2026-11-04",
        "run_root": RUN.relative_to(ROOT).as_posix(),
        "pipeline": "scripts/run_funding_finder_acceptance.py --fetch-official",
        "status": "LIVE_OFFICIAL_SOURCES_CAPTURED_PIPELINE_QA_PASSED_PRODUCT_QUALIFICATION_UNPROVED",
        "scenarios": scenarios,
        "artifact_index": artifact_index,
        "limitations": [
            "All applicant profiles are synthetic; no customer applicant evidence was processed.",
            "Source capture and exact quotation checks do not certify full funder rules, current application availability, eligibility, award likelihood, or application outcome.",
            "NYDA/TIA eligibility or timing remains unknown or mismatched where evidence does not support a stronger result.",
            "The UK Lottery case is an England jurisdiction mismatch for a South African applicant.",
            "No application was submitted and no funding decision or product qualification was created.",
        ],
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": OUT.relative_to(ROOT).as_posix(), "scenario_count": len(scenarios),
                      "source_capture_count": sum(len(CASES[x]) for x in CASES),
                      "all_hashes_verified": True, "qualification_granted": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
