#!/usr/bin/env python3
"""Make the saved HOMS Grades 1–12 candidate bundle self-contained and reproducible."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "deliverables/homs_best_randomized_exam_candidates_20261104_v2"
SHORTLIST = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_BEST_EXAM_CANDIDATES_SHORTLIST_20261104.json"
MANIFEST = BUNDLE / "CANDIDATE_BUNDLE_MANIFEST.json"
ARCHIVE = BUNDLE / "HOMS_RANDOMIZED_EXAM_CANDIDATES_GRADES_01_12.zip"
PORTABLE_SHORTLIST = BUNDLE / "source_receipts/HOMS_BEST_EXAM_CANDIDATES_SHORTLIST_20261104.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    source_path = SHORTLIST if SHORTLIST.is_file() else PORTABLE_SHORTLIST
    if not source_path.is_file():
        raise FileNotFoundError("The current HOMS selection manifest is missing from the workspace and saved bundle")
    source_bytes = source_path.read_bytes()
    selection = json.loads(source_bytes)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = manifest.get("selection_manifest_sha256")
    if sha(source_bytes) != expected or selection.get("grade_count") != 12:
        raise ValueError("Current HOMS shortlist does not match the saved candidate-bundle selection hash")
    if (manifest.get("classroom_release_authorized") is not False
            or manifest.get("educator_review_required") is not True
            or manifest.get("independent_moderation_decision") != "NOT_ISSUED"):
        raise ValueError("Candidate bundle release and educator-review boundaries must remain held")

    PORTABLE_SHORTLIST.parent.mkdir(parents=True, exist_ok=True)
    if not PORTABLE_SHORTLIST.is_file() or PORTABLE_SHORTLIST.read_bytes() != source_bytes:
        PORTABLE_SHORTLIST.write_bytes(source_bytes)
    rel = PORTABLE_SHORTLIST.relative_to(BUNDLE).as_posix()
    row = {"path": rel, "sha256": sha(source_bytes), "bytes": len(source_bytes)}
    artifacts = [item for item in manifest.get("bundle_artifacts", []) if item.get("path") != rel]
    artifacts.append(row)
    readme = BUNDLE / "README.md"
    readme_bytes = readme.read_bytes()
    artifacts = [item for item in artifacts if item.get("path") != "README.md"]
    artifacts.append({"path": "README.md", "sha256": sha(readme_bytes), "bytes": len(readme_bytes)})
    artifacts.sort(key=lambda item: item["path"])
    manifest["selection_manifest_path"] = rel
    manifest["bundle_artifacts"] = artifacts

    # Validate every declared child before writing the archive.
    for item in artifacts:
        path = (BUNDLE / item["path"]).resolve()
        if not path.is_relative_to(BUNDLE.resolve()) or not path.is_file():
            raise ValueError(f"Candidate bundle member is missing or unsafe: {item['path']}")
        content = path.read_bytes()
        if len(content) != item.get("bytes") or sha(content) != item.get("sha256"):
            raise ValueError(f"Candidate bundle member hash/size mismatch: {item['path']}")

    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for item in artifacts:
            info = zipfile.ZipInfo(item["path"], date_time=(2026, 11, 4, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (BUNDLE / item["path"]).read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        info = zipfile.ZipInfo("CANDIDATE_BUNDLE_MANIFEST.json", date_time=(2026, 11, 4, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, MANIFEST.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    with zipfile.ZipFile(ARCHIVE) as archive:
        names = set(archive.namelist())
        required = {item["path"] for item in artifacts} | {"CANDIDATE_BUNDLE_MANIFEST.json"}
        if names != required:
            raise ValueError("Candidate archive member list does not match its manifest")
        for item in artifacts:
            if sha(archive.read(item["path"])) != item["sha256"]:
                raise ValueError(f"Archived candidate member failed hash check: {item['path']}")
        if sha(archive.read("CANDIDATE_BUNDLE_MANIFEST.json")) != sha(MANIFEST.read_bytes()):
            raise ValueError("Archived candidate manifest does not match the saved manifest")

    print(json.dumps({"grade_count": manifest["grade_count"], "bundle_artifact_count": len(artifacts),
                      "archive_member_count": len(required), "selection_manifest": rel,
                      "selection_manifest_sha256": expected,
                      "zip": str(ARCHIVE.relative_to(ROOT)), "zip_sha256": sha(ARCHIVE.read_bytes()),
                      "archive_members_verified": True}, indent=2))


if __name__ == "__main__":
    main()
