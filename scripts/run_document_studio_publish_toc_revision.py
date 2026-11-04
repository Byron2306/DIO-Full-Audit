#!/usr/bin/env python3
"""Re-render the held Document Studio Publish case without a blank TOC field."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = ROOT / "acceptance_runs/68-product-sellability-20261027"
SOURCE_RUN = BASE / "DOCUMENT_STUDIO_PUBLISH_CUSTOMER_EXECUTION_20261102_V1"
OUTPUT = BASE / "DOCUMENT_STUDIO_PUBLISH_CUSTOMER_EXECUTION_20261104_V4"
EVIDENCE = BASE / "DOCUMENT_STUDIO_PUBLISH_LAYOUT_REVISION_20261104_V4.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise ValueError(f"refusing to overwrite existing publication run: {OUTPUT}")
    prior = json.loads((SOURCE_RUN / "PUBLICATION_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    source = SOURCE_RUN / prior["source"]["unchanged_copy"]
    packet = {
        "document_path": str(source),
        "source_sha256": prior["source"]["sha256"],
        "owner_authorized": True,
        "content_owner_approved": True,
        "external_release_authorized": False,
        "human_review_required": True,
        "title": prior["metadata"]["title"],
        "authors": prior["metadata"]["authors"],
        "doi": prior["metadata"]["doi_state"],
        "language": prior["metadata"]["language"],
        "channels": ["docx", "pdf", "html"],
        "style_profile": "institutional_academic",
    }
    from products.customer_product_router import run_customer_product

    result = run_customer_product("Document Studio Publish", packet, OUTPUT, render_pdf=True)
    execution = result.get("receipt") or {}
    package_path = OUTPUT / "PUBLICATION_PACKAGE_MANIFEST.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    review_page = (OUTPUT / "PUBLICATION_REVIEW.html").read_text(encoding="utf-8")
    review_notes = (OUTPUT / "HUMAN_PUBLICATION_REVIEW.md").read_text(encoding="utf-8")
    artifact_paths = {row["channel"]: OUTPUT / "formatted" / row["path"] for row in package["format_core"]["outputs"]}
    pdf = artifact_paths["pdf"]
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True, text=True, timeout=60).stdout
    pages = int(subprocess.run(["pdfinfo", str(pdf)], check=True, capture_output=True, text=True, timeout=60).stdout.split("Pages:", 1)[1].splitlines()[0].strip())
    docx = artifact_paths["docx"]
    docx_xml = subprocess.run(["unzip", "-p", str(docx), "word/document.xml"], check=True, capture_output=True, text=True, timeout=60).stdout
    expected_source_hash = prior["source"]["sha256"]
    source_copy = OUTPUT / package["source"]["unchanged_copy"]
    checks = {
        "source_copy_hash_preserved": source_copy.is_file() and sha(source_copy) == expected_source_hash,
        "all_three_formats_rendered": set(package["source_text_preservation_checks"]) == {"docx", "pdf", "html"}
        and all(package["source_text_preservation_checks"].values()),
        "unpopulated_contents_field_removed_from_pdf": "Update this field in Word or LibreOffice" not in text,
        "unpopulated_contents_field_removed_from_docx": "Update this field in Word or LibreOffice" not in docx_xml,
        "extra_contents_page_removed": pages == 2,
        "explicit_draft_markers_flagged": package.get("source_content_review", {}).get("state") == "OWNER_RECONCILIATION_REQUIRED"
        and len(package.get("source_content_review", {}).get("draft_markers") or []) >= 2,
        "approval_conflict_visible_in_review_gate": "Source approval conflict" in review_page
        and "reconcile that status" in review_notes,
        "release_boundary_held": result.get("release_authorized") is False
        and result.get("external_effects") is False
        and execution.get("external_publication_authorized") is False,
    }
    if not all(checks.values()):
        raise ValueError(f"Document Studio Publish layout revision failed: {checks}")
    evidence = {
        "schema": "dio.document_studio.publish_layout_revision_evidence.v1",
        "product": "Document Studio Publish",
        "source_run": str(SOURCE_RUN.relative_to(ROOT)),
        "source_sha256": expected_source_hash,
        "output_run": str(OUTPUT.relative_to(ROOT)),
        "package_manifest_sha256": sha(package_path),
        "pdf_sha256": sha(pdf),
        "pdf_page_count": pages,
        "docx_sha256": sha(docx),
        "html_sha256": sha(artifact_paths["html"]),
        "source_text_unchanged": True,
        "contents_page_policy": "Omit an automatic contents field when the owner has not supplied an approved contents list; never render an unpopulated field placeholder.",
        "source_content_review": package.get("source_content_review"),
        "checks": checks,
        "formatting_only": True,
        "external_publication_authorized": False,
        "external_effects": False,
        "qualification": "UNPROVED",
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
