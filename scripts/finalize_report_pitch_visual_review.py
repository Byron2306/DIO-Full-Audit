#!/usr/bin/env python3
"""Bind a completed layout review into the Report & Pitch customer package."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "acceptance_runs/68-product-sellability-20261027/report-pitch/reviewed-final-v4/baseline"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest_path = CASE / "package_manifest.json"
    review_path = CASE / "REPORT_PITCH_VISUAL_REVIEW.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if review.get("schema") != "dio.report_pitch_visual_review.v1" or review.get("result") != "PASS_LAYOUT_ONLY":
        raise ValueError("A passing, schema-matched layout review is required before finalizing the package")
    slides = [row for row in review.get("artifacts", []) if Path(row.get("path", "")).name.startswith("slide-")]
    if len(slides) != 7:
        raise ValueError("The review must bind all seven rendered slide images")
    for row in review.get("artifacts", []):
        path = CASE / row["path"]
        if not path.is_file() or digest(path) != row.get("sha256"):
            raise ValueError(f"Reviewed artifact is missing or changed: {row.get('path')}")

    original_manifest_sha256 = digest(manifest_path)
    review_sha256 = digest(review_path)
    manifest["qa"]["visual_review"] = "PASS_LAYOUT_ONLY"
    manifest["post_render_visual_review"] = {
        "status": "PASS_LAYOUT_ONLY",
        "review_artifact": review_path.name,
        "review_sha256": review_sha256,
        "reviewed_at": review.get("reviewed_at"),
        "scope": review.get("scope"),
        "limitations": review.get("not_established", []),
        "pre_finalization_manifest_sha256": original_manifest_sha256,
    }
    files = []
    for path in sorted(CASE.rglob("*")):
        if path.is_file() and path.name not in {"package_manifest.json", "controlled_review_package.zip"}:
            files.append({"path": path.relative_to(CASE).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)})
    manifest["artifacts"] = files
    manifest["finalized_package_file_count"] = len(files)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    archive_path = CASE / "controlled_review_package.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(CASE.rglob("*")):
            if path.is_file() and path != archive_path:
                archive.write(path, path.relative_to(CASE).as_posix())
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        if "REPORT_PITCH_VISUAL_REVIEW.json" not in names or "package_manifest.json" not in names:
            raise ValueError("Final review evidence was not included in the customer archive")
        archived_manifest = json.loads(archive.read("package_manifest.json"))
        if archived_manifest.get("post_render_visual_review", {}).get("review_sha256") != review_sha256:
            raise ValueError("Archived package manifest does not bind the visual review")
    print(json.dumps({"status": manifest["qa"]["visual_review"], "slide_count": len(slides),
                      "review_sha256": review_sha256, "archive_sha256": digest(archive_path),
                      "archive": str(archive_path.relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
