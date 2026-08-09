#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUMMARY = ROOT / "deliverables" / "homs_core_subject_smoke_packs" / "HOMS_CORE_SUBJECT_SMOKE_SUMMARY.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def media_count(docx_path: Path) -> int:
    if not docx_path.exists():
        return 0
    with zipfile.ZipFile(docx_path) as zf:
        return sum(1 for name in zf.namelist() if name.startswith("word/media/"))


def zip_source_count(zip_path: Path) -> int:
    if not zip_path.exists():
        return 0
    with zipfile.ZipFile(zip_path) as zf:
        return sum(1 for name in zf.namelist() if name.startswith("source_material/"))


def convert_pdf(docx_path: Path, out_dir: Path) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    pdf_path = out_dir / f"{docx_path.stem}.pdf"
    if result.returncode == 0 and pdf_path.exists():
        return pdf_path
    return None


def pdf_page_count(pdf_path: Path | None) -> int:
    if not pdf_path or not pdf_path.exists():
        return 0
    result = subprocess.run(["pdfinfo", str(pdf_path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        return 0
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    return 0


def validate_pack(item: dict[str, Any]) -> dict[str, Any]:
    job_dir = Path(item["job_dir"])
    pack = load_json(job_dir / "assessment_pack.json")
    docx_path = Path(item["formatted_docx"])
    zip_path = Path(item["formatted_zip"])
    source_assets = pack.get("source_assets") or []
    flagged_sources = [asset for asset in source_assets if asset.get("quality_flags")]
    release_blocked_sources = [asset for asset in source_assets if str(asset.get("release_gate") or "").startswith("blocked")]
    pdf_path = convert_pdf(docx_path, job_dir / "pdf_check")
    docx_media = media_count(docx_path)
    source_in_zip = zip_source_count(zip_path)
    generated_visuals = max(docx_media - len(source_assets), 0)
    status = "passed"
    failures = []
    if not docx_path.exists():
        failures.append("missing_docx")
    if not zip_path.exists():
        failures.append("missing_zip")
    if len(source_assets) != item["attached_count"]:
        failures.append("source_asset_count_mismatch")
    if source_in_zip != len(source_assets):
        failures.append("zip_source_material_count_mismatch")
    if docx_media < len(source_assets):
        failures.append("docx_media_less_than_source_assets")
    if not pdf_path:
        failures.append("pdf_export_failed")
    if failures:
        status = "failed"
    return {
        "subject_id": item["subject_id"],
        "subject": item["subject"],
        "status": status,
        "failures": failures,
        "job_dir": str(job_dir),
        "source_assets": len(source_assets),
        "flagged_sources": len(flagged_sources),
        "release_blocked_sources": len(release_blocked_sources),
        "source_quality_flags": sorted({flag for asset in flagged_sources for flag in asset.get("quality_flags", [])}),
        "missing_requested_source_types": item.get("missing_requested_source_types") or [],
        "docx_media": docx_media,
        "generated_visuals": generated_visuals,
        "zip_source_material": source_in_zip,
        "pdf": str(pdf_path) if pdf_path else None,
        "pdf_pages": pdf_page_count(pdf_path),
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# HOMS Core Subject Smoke Validation",
        "",
        f"- Created at: {payload['created_at']}",
        f"- Status: `{payload['status']}`",
        f"- Passed: {payload['passed']}",
        f"- Failed: {payload['failed']}",
        f"- Release status: `{payload['release_status']}`",
        "",
        "| Subject | Status | Sources | Flagged | Release Blocked | Missing Requested | DOCX Media | Zip Sources | PDF Pages |",
        "|---|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for result in payload["results"]:
        missing = ", ".join(f"`{item}`" for item in result["missing_requested_source_types"]) or "none"
        lines.append(
            f"| {result['subject']} | `{result['status']}` | {result['source_assets']} | {result['flagged_sources']} | {result['release_blocked_sources']} | {missing} | {result['docx_media']} | {result['zip_source_material']} | {result['pdf_pages']} |"
        )
    lines.extend(["", "## Interpretation", ""])
    lines.append("A validation pass means the pack rendered, contains embedded media, exports to PDF and carries source material in the review zip.")
    lines.append("Missing requested source types are quality gaps in the source bank, not document-render failures.")
    lines.append("Flagged sources are usable for smoke proof, but need object-level crop/readability review before client delivery.")
    lines.append("Release status remains blocked while any embedded source has a blocked release gate.")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    summary = load_json(DEFAULT_SUMMARY)
    results = [validate_pack(item) for item in summary["built"]]
    payload = {
        "schema": "knowedge.homs_core_subject_smoke_validation.v1",
        "created_at": utc_now(),
        "status": "passed" if all(result["status"] == "passed" for result in results) else "failed",
        "release_status": "blocked" if any(result["release_blocked_sources"] for result in results) else "candidate_ready_for_human_review",
        "passed": sum(1 for result in results if result["status"] == "passed"),
        "failed": sum(1 for result in results if result["status"] != "passed"),
        "results": results,
    }
    out_dir = DEFAULT_SUMMARY.parent
    (out_dir / "HOMS_CORE_SUBJECT_SMOKE_VALIDATION.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(out_dir / "HOMS_CORE_SUBJECT_SMOKE_VALIDATION.md", payload)
    print(json.dumps({"status": payload["status"], "passed": payload["passed"], "failed": payload["failed"]}, indent=2))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
