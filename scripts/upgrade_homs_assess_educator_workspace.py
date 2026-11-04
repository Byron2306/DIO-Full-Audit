#!/usr/bin/env python3
"""Refresh the current HOMS Assess educator review surface without rescoring."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261102_G10_V33_INTERACTIVE_EDUCATOR_REVIEW"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from products.homs_assess_customer import build_pointwise_educator_review

    package_path = RUN / "CUSTOMER_PACKAGE_RECEIPT.json"
    execution_path = RUN / "CUSTOMER_EXECUTION_RECEIPT.json"
    package = read_json(package_path)
    old_page_path = RUN / package["outputs"]["pointwise_educator_review"]
    old_page_sha256 = digest(old_page_path)
    results_path = RUN / package["outputs"]["results"]
    results = json.loads(results_path.read_text(encoding="utf-8"))
    input_dir = RUN / "input"
    rubric = read_json(input_dir / "rubric.json")
    pointwise = build_pointwise_educator_review(
        input_dir,
        rubric,
        results,
        results_path,
        RUN / "educator_review",
        customer_packet_fingerprint=package["customer_packet_fingerprint"],
    )

    workspace = Path(str(package["outputs"]["pointwise_educator_review"]))
    receipt = read_json(pointwise["receipt_path"])
    adjudication_receipt = pointwise["adjudication_receipt"]
    review_zip = RUN / package["outputs"]["review_zip"]
    replaced = {
        "educator_review/index.html",
        "educator_review/POINTWISE_REVIEW_RECEIPT.json",
        "educator_review/EDUCATOR_POINTWISE_ADJUDICATION.csv",
        "educator_review/EDUCATOR_MARKING_QUALITY_FLAGS.csv",
        "educator_review/EDUCATOR_POINTWISE_ADJUDICATION_RECEIPT.json",
        "educator_review/EDUCATOR_POINTWISE_ADJUDICATION_GUIDE.md",
    }
    with tempfile.NamedTemporaryFile(prefix="homs-assess-review-", suffix=".zip", dir=review_zip.parent, delete=False) as tmp:
        temp_zip = Path(tmp.name)
    try:
        with zipfile.ZipFile(review_zip, "r") as source, zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for entry in source.infolist():
                if entry.filename not in replaced:
                    target.writestr(entry, source.read(entry.filename))
            for name in sorted(replaced):
                target.write(RUN / name, name)
        os.replace(temp_zip, review_zip)
    finally:
        temp_zip.unlink(missing_ok=True)

    package.update({
        "pointwise_review_sha256": pointwise["sha256"],
        "pointwise_review_receipt_sha256": pointwise["receipt_sha256"],
        "draft_context_sha256": receipt.get("draft_context_sha256"),
        "pointwise_adjudication_sha256": pointwise["adjudication_sha256"],
        "quality_flag_review_sha256": pointwise["quality_flags_sha256"],
        "pointwise_adjudication_receipt_sha256": pointwise["adjudication_receipt_sha256"],
        "pointwise_adjudication_guide_sha256": pointwise["adjudication_guide_sha256"],
    })
    changed = {name: digest(RUN / name) for name in replaced}
    upgrade_receipt = {
        "schema": "dio.homs.assess.educator_review_workspace_upgrade.v1",
        "product": "HOMS Assess",
        "grade": package.get("grade"),
        "subject": package.get("subject"),
        "customer_packet_fingerprint": package["customer_packet_fingerprint"],
        "previous_review_page_sha256": old_page_sha256,
        "current_review_page_sha256": pointwise["sha256"],
        "source_results_sha256": digest(results_path),
        "pointwise_review_receipt_sha256": pointwise["receipt_sha256"],
        "point_row_count": adjudication_receipt.get("point_row_count"),
        "quality_flag_row_count": adjudication_receipt.get("source_quality_flag_row_count"),
        "features": {
            "filter_by_learner": True,
            "search_answer_question_memo_and_flags": True,
            "show_unresolved_only": True,
            "save_draft_json": True,
            "resume_draft_json": True,
            "draft_packet_and_row_identity_binding": True,
            "draft_context_binds_source_and_model_proposals": receipt.get("draft_context_binds_source_and_model_proposals") is True,
            "draft_contains_educator_fields_only": True,
            "browser_storage_used": False,
            "network_requests_from_review_surface": False,
        },
        "changed_artifact_sha256": changed,
        "scores_issued": False,
        "classroom_release_authorized": False,
        "external_processing": False,
    }
    upgrade_path = RUN / "educator_review/EDUCATOR_REVIEW_WORKSPACE_UPGRADE_RECEIPT.json"
    write_json(upgrade_path, upgrade_receipt)
    package["educator_review_workspace_upgrade_receipt"] = {
        "path": upgrade_path.relative_to(RUN).as_posix(),
        "sha256": digest(upgrade_path),
    }
    write_json(package_path, package)

    execution = read_json(execution_path)
    artifacts = {row["path"]: row for row in execution.get("artifacts") or []}
    for relative in sorted(replaced):
        path = RUN / relative
        row = artifacts.setdefault(relative, {"path": relative})
        row.update({"bytes": path.stat().st_size, "sha256": digest(path)})
    relative_upgrade = upgrade_path.relative_to(RUN).as_posix()
    artifacts[relative_upgrade] = {"path": relative_upgrade, "bytes": upgrade_path.stat().st_size, "sha256": digest(upgrade_path)}
    relative_zip = review_zip.relative_to(RUN).as_posix()
    artifacts[relative_zip] = {"path": relative_zip, "bytes": review_zip.stat().st_size, "sha256": digest(review_zip)}
    execution["artifacts"] = [artifacts[key] for key in sorted(artifacts)]
    write_json(execution_path, execution)

    if digest(old_page_path) != pointwise["sha256"] or digest(old_page_path) != receipt["page_sha256"]:
        raise ValueError("HOMS Assess educator review surface failed its hash binding")
    if adjudication_receipt.get("point_row_count") != 100 or adjudication_receipt.get("source_quality_flag_row_count") != 33:
        raise ValueError("HOMS Assess educator review workspace input counts differ from the bound source run")
    print(json.dumps({
        "review_page": workspace.as_posix(),
        "review_page_sha256": pointwise["sha256"],
        "point_rows": adjudication_receipt["point_row_count"],
        "quality_flags": adjudication_receipt["source_quality_flag_row_count"],
        "review_zip_sha256": digest(review_zip),
        "scores_issued": False,
        "classroom_release_authorized": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
