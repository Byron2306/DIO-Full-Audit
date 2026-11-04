#!/usr/bin/env python3
"""Build a portable, evidence-bounded portfolio of the 68 catalog product proofs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import mimetypes
import os
import re
import shutil
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse, urlunparse


EXTENSION_RANK = {
    ".pdf": 0,
    ".pptx": 1,
    ".docx": 2,
    ".xlsx": 3,
    ".html": 4,
    ".png": 5,
    ".jpg": 5,
    ".jpeg": 5,
    ".webp": 5,
    ".zip": 6,
    ".md": 7,
    ".csv": 8,
    ".json": 9,
}
HTML_LINK_RE = re.compile(r"url\((?:\"|')?([^)'\"]+)(?:\"|')?\)", re.I)


DATE_TOKEN_RE = re.compile(r"(?<!\d)(20\d{6})(?!\d)")
ROOT_PATH_ATTR_RE = re.compile(r"(?P<prefix>\b(?:href|src|poster)\s*=\s*)(?P<quote>[\"'])(?P<url>deliverables/[^\"']+)(?P=quote)", re.I)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scenario_rank(path: Path) -> int:
    lowered = str(path).lower()
    if "reviewed-final" in lowered:
        return 0
    if "customer-release-candidate" in lowered:
        return 1
    if "controlled-baseline" in lowered or "/baseline/" in lowered or "/normal/" in lowered:
        return 2
    if "reviewed" in lowered:
        return 3
    if "unseen" in lowered:
        return 4
    if "messy-adversarial" in lowered or "controlled-messy" in lowered:
        return 5
    return 6


def in_snapshot(path: Path, evidence_as_of: str) -> bool:
    cutoff = int(evidence_as_of.replace("-", ""))
    dates = [int(value) for value in DATE_TOKEN_RE.findall(str(path))]
    return not dates or max(dates) <= cutoff


def best_deliverable(repo: Path, product: dict, evidence_as_of: str) -> tuple[Path, str, int]:
    refs = product.get("customer_deliverable_refs", [])
    all_options = [repo / item for item in refs]
    future_count = sum(1 for item in all_options if not in_snapshot(item, evidence_as_of))
    options = [item for item in all_options if item.is_file() and in_snapshot(item, evidence_as_of)]
    source_class = "current_customer_deliverable"
    if not options:
        options = [repo / item for item in product.get("historical_artifact_refs", [])]
        options = [item for item in options if item.is_file() and in_snapshot(item, evidence_as_of)]
        source_class = "historical_baseline_fallback"
    if not options:
        raise ValueError(f"No in-snapshot deliverable for {product['product_id']}")

    if product["product_id"] == "homs_exam":
        candidate = repo / "deliverables/homs_grade12_business_studies_full_nsc_candidate_20261104/HOMS_GRADE12_FULL_NSC_CANDIDATE.zip"
        if candidate.is_file() and in_snapshot(candidate, evidence_as_of):
            return candidate, "homs_grades_01_11_candidate_bundle_plus_full_grade12_nsc_style_candidate", future_count
        candidate = repo / "deliverables/homs_best_randomized_exam_candidates_20261104_v2/HOMS_RANDOMIZED_EXAM_CANDIDATES_GRADES_01_12.zip"
        if candidate.is_file() and in_snapshot(candidate, evidence_as_of):
            return candidate, "saved_homs_grade_01_12_candidate_bundle", future_count

    selected = min(
        options,
        key=lambda item: (
            EXTENSION_RANK.get(item.suffix.lower(), 50),
            scenario_rank(item),
            len(str(item)),
            str(item),
        ),
    )
    return selected, source_class, future_count


def best_product_receipt(repo: Path, product: dict, evidence_as_of: str) -> Path | None:
    refs = [repo / item for item in product.get("current_product_specific_evidence_refs", [])]
    refs = [item for item in refs if item.is_file() and in_snapshot(item, evidence_as_of)]
    receipts = [item for item in refs if "RECEIPT" in item.name.upper()]
    if receipts:
        preferred = {
            "PROFESSIONAL_EVIDENCE_RECEIPT.JSON": 0,
            "CUSTOMER_EXECUTION_RECEIPT.JSON": 1,
            "CUSTOMER_PACKAGE_RECEIPT.JSON": 2,
        }
        return min(receipts, key=lambda item: (preferred.get(item.name.upper(), 3), scenario_rank(item), len(str(item)), str(item)))
    # HOMS Accreditation's current proof is an evidence packet rather than a receipt.
    evidence = [item for item in refs if "EVIDENCE" in item.name.upper() or "MANIFEST" in item.name.upper()]
    if evidence:
        return min(evidence, key=lambda item: (scenario_rank(item), len(str(item)), str(item)))
    return None


def readiness_verdicts(record: dict) -> dict:
    """Keep route execution separate from readiness claims."""
    route = str(record.get("route_status") or "").upper()
    execution = "PASS" if route == "PASS_FULL_PIPELINE" else ("FAIL" if route.startswith(("FAIL", "ERROR")) else "UNVERIFIED")
    quality = "PASS" if record.get("independent_professional_signoff") else "UNVERIFIED"
    acceptance_value = str(record.get("buyer_acceptance") or "").upper()
    acceptance = "PASS" if acceptance_value in {"ESTABLISHED", "PROVED", "PROVEN"} else ("FAIL" if acceptance_value in {"REJECTED", "FAILED"} else "UNVERIFIED")
    release = "PASS" if record.get("release_authorized") else "HELD"
    evidence = "TRACEABLE_UNVALIDATED" if record.get("product_evidence") and record.get("artifact_sha256") else "UNVERIFIED"
    states = {"execution": execution, "output_quality": quality, "evidence_validity": evidence, "customer_acceptance": acceptance, "release": release}
    return {"dimensions": states, "professional_readiness": "READY" if all(value == "PASS" for value in states.values()) else "NOT_ESTABLISHED",
            "interpretation": "A route PASS proves execution only. TRACEABLE_UNVALIDATED proves byte lineage where present; semantic correctness requires an independent subject-matter review."}


class LocalReferences(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key in {"src", "href", "poster"} and value:
                self.values.append(value)


def local_dependencies(repo: Path, entry: Path) -> set[Path]:
    """Resolve local HTML/CSS references without following remote URLs or symlinks out of repo."""
    found: set[Path] = set()
    pending = [entry]
    while pending:
        current = pending.pop()
        if current in found or not current.is_file():
            continue
        found.add(current)
        if current.suffix.lower() in {".html", ".htm"}:
            parser = LocalReferences()
            try:
                parser.feed(current.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            references = parser.values
        elif current.suffix.lower() == ".css":
            try:
                references = HTML_LINK_RE.findall(current.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
        else:
            references = []
        for reference in references:
            parsed = urlparse(reference)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            if parsed.path.startswith("/"):
                # Root-relative links are site routes (for example, /documents), not file assets.
                continue
            if parsed.path.startswith("deliverables/") and (repo / unquote(parsed.path)).is_file():
                target = (repo / unquote(parsed.path)).resolve()
            else:
                target = (current.parent / unquote(parsed.path)).resolve()
            try:
                target.relative_to(repo.resolve())
            except ValueError:
                continue
            if target.is_file() and target not in found:
                pending.append(target)
    return found


def copy_payload(repo: Path, source: Path, destination: Path) -> list[dict]:
    if source.suffix.lower() in {".html", ".htm"}:
        files = local_dependencies(repo, source)
    else:
        files = {source}
        # Include a matching editable source beside a selected PDF or presentation when present.
        if source.suffix.lower() == ".pdf":
            sibling = source.with_suffix(".docx")
            if sibling.is_file():
                files.add(sibling)
        if source.suffix.lower() == ".pptx":
            sibling = source.with_suffix(".pdf")
            if sibling.is_file():
                files.add(sibling)

    copied: list[tuple[Path, Path]] = []
    for item in sorted(files):
        relative = item.relative_to(repo)
        target = destination / "payload" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        copied.append((item, target))

    # Original customer review pages may link to repository-root deliverables.
    # Rewrite those anchors to the preserved payload path so the offline bundle opens correctly.
    for item, target in copied:
        if target.suffix.lower() not in {".html", ".htm"}:
            continue
        source_text = target.read_text(encoding="utf-8", errors="replace")
        def rewrite(match: re.Match[str]) -> str:
            reference = html.unescape(match.group("url"))
            parsed = urlparse(reference)
            original_target = (repo / unquote(parsed.path)).resolve()
            try:
                original_target.relative_to(repo)
            except ValueError:
                return match.group(0)
            if not original_target.is_file():
                return match.group(0)
            packaged_target = destination / "payload" / original_target.relative_to(repo)
            relative_url = Path(os.path.relpath(packaged_target, target.parent)).as_posix()
            updated = urlunparse(("", "", relative_url, "", parsed.query, parsed.fragment))
            return f"{match.group('prefix')}{match.group('quote')}{updated}{match.group('quote')}"
        source_text = ROOT_PATH_ATTR_RE.sub(rewrite, source_text)
        target.write_text(source_text, encoding="utf-8")

    result = []
    for item, target in copied:
        relative = item.relative_to(repo)
        result.append(
            {
                "path": target.relative_to(destination).as_posix(),
                "source_path": relative.as_posix(),
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
                "media_type": mimetypes.guess_type(item.name)[0] or "application/octet-stream",
            }
        )
    return result


def safe_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--qualification",
        type=Path,
        default=Path("acceptance_runs/68-product-sellability-20261027/68_PRODUCT_QUALIFICATION.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("deliverables/product_proof_portfolio_20261104"),
    )
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    qualification = args.qualification if args.qualification.is_absolute() else repo / args.qualification
    output = args.output if args.output.is_absolute() else repo / args.output
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output: {output}")
    output.mkdir(parents=True, exist_ok=True)

    snapshot = json.loads(qualification.read_text(encoding="utf-8"))
    products = snapshot.get("products", [])
    if len(products) != 68:
        raise SystemExit(f"Expected 68 catalog products, found {len(products)}")

    records = []
    for product in sorted(products, key=lambda value: value["product_id"]):
        product_id = product["product_id"]
        folder = output / "proofs" / product_id
        folder.mkdir(parents=True, exist_ok=True)
        source, source_class, future_ref_count = best_deliverable(repo, product, snapshot.get("evidence_as_of", "9999-12-31"))
        source = source.resolve()
        source.relative_to(repo)
        payload = copy_payload(repo, source, folder)
        route = product.get("latest_full_pipeline_route_execution") or {}
        receipt_path = best_product_receipt(repo, product, snapshot.get("evidence_as_of", "9999-12-31"))
        receipt_record = None
        if receipt_path:
            receipt_path = receipt_path.resolve()
            receipt_target = folder / "product_evidence_receipt" / receipt_path.name
            receipt_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(receipt_path, receipt_target)
            receipt_record = {
                "path": receipt_target.relative_to(folder).as_posix(),
                "source_path": receipt_path.relative_to(repo).as_posix(),
                "kind": "receipt" if "RECEIPT" in receipt_path.name.upper() else "evidence_record",
                "bytes": receipt_target.stat().st_size,
                "sha256": sha256(receipt_target),
            }
        primary = next((item for item in payload if item["source_path"] == source.relative_to(repo).as_posix()), payload[0])
        records.append(
            {
                "product_id": product_id,
                "name": product.get("name", product_id),
                "suite": product.get("suite", ""),
                "disposition": product.get("current_disposition", "UNSPECIFIED"),
                "pilot_candidate": bool(product.get("pilot_candidate", False)),
                "primary_artifact": primary["path"],
                "source_artifact": primary["source_path"],
                "artifact_source_class": source_class,
                "future_dated_references_excluded": future_ref_count,
                "artifact_sha256": primary["sha256"],
                "artifact_bytes": primary["bytes"],
                "payload_files": payload,
                "route_status": route.get("status", "NOT_RECORDED"),
                "product_evidence": receipt_record,
                "quality_limits": product.get("quality_limits", []),
                "independent_professional_signoff": product.get("independent_professional_signoff", False),
                "buyer_acceptance": product.get("buyer_acceptance", "NOT_ESTABLISHED"),
                "commercial_validation": product.get("commercial_validation", "UNPROVED"),
                "release_authorized": bool(product.get("qualification_grants_release_authority", False)),
            }
        )
        records[-1]["readiness_verdicts"] = readiness_verdicts(records[-1])

    # These three creative organs are tracked outside the 68-offer customer catalog.
    # Include their strongest locally recorded media proofs as a clearly separate supplement.
    creative_specs = {
        "sonoris": {
            "name": "Sonoris",
            "description": "Black-metal composition candidate with physical-performance mix, MP3 audition, and short review video.",
            "state": "HELD_FOR_REVIEW",
            "limitations": ["Human listening and visual review are required.", "Rights clearance for commercial release is unverified; publication is unauthorized."],
            "files": [
                "media/sonoris/releases/black_metal_where_pines_forget_v3/final_product_candidate/index.html",
                "media/sonoris/releases/black_metal_where_pines_forget_v3/final_product_candidate/where-the-pines-forget.mp3",
                "media/sonoris/releases/black_metal_where_pines_forget_v3/final_product_candidate/where-the-pines-forget-review.mp4",
                "media/sonoris/releases/black_metal_where_pines_forget_v3/final_product_candidate/sonoris-pictora-visual-preview.jpg",
                "media/sonoris/releases/black_metal_where_pines_forget_v3/final_product_candidate/CREATIVE_PRODUCT_RECEIPT.json",
                "media/sonoris/releases/black_metal_where_pines_forget_v3/SONORIS_LOCAL_REVIEW_RECEIPT_V4.json",
                "media/sonoris/releases/black_metal_where_pines_forget_v3/SONORIS_GOVERNED_COMPOSITION_PLAN.json",
                "media/sonoris/releases/black_metal_where_pines_forget_v3/SONORIS_PHYSICAL_PERFORMANCE_PLAN.json",
            ],
            "primary": "demo/index.html",
        },
        "pictora": {
            "name": "Pictora",
            "description": "Four local ComfyUI image-editing examples and a refined, upscaled site-matched visual, each paired with execution provenance.",
            "state": "LOCAL_REVIEW_CANDIDATE",
            "limitations": ["Human visual review is pending.", "Checkpoint and asset commercial terms remain uncleared; release is unauthorized."],
            "files": [
                "media/product_asset_packs/pictora_image_editor_v1/assets/creative_handoff.png",
                "media/product_asset_packs/pictora_image_editor_v1/pictora_jobs/creative_handoff/PICTORA_JOB_RECEIPT.json",
                "media/product_asset_packs/pictora_image_editor_v1/workflows/creative_handoff_api.json",
                "media/product_asset_packs/pictora_image_editor_v1/assets/editorial_workspace.png",
                "media/product_asset_packs/pictora_image_editor_v1/pictora_jobs/editorial_workspace/PICTORA_JOB_RECEIPT.json",
                "media/product_asset_packs/pictora_image_editor_v1/workflows/editorial_workspace_api.json",
                "media/product_asset_packs/pictora_image_editor_v1/assets/photo_finish.png",
                "media/product_asset_packs/pictora_image_editor_v1/pictora_jobs/photo_finish/PICTORA_JOB_RECEIPT.json",
                "media/product_asset_packs/pictora_image_editor_v1/workflows/photo_finish_api.json",
                "media/product_asset_packs/pictora_image_editor_v1/assets/retouch_detail.png",
                "media/product_asset_packs/pictora_image_editor_v1/pictora_jobs/retouch_detail/PICTORA_JOB_RECEIPT.json",
                "media/product_asset_packs/pictora_image_editor_v1/workflows/retouch_detail_api.json",
                "media/product_asset_packs/dio_creative_organs_site_matched_v1/assets/PICTORA_ORBITAL_IMAGE_FORGE_UPSCALED_1280x720.png",
                "media/product_asset_packs/dio_creative_organs_site_matched_v1/PICTORA_REFINED_UPSCALE_RECEIPT.json",
                "media/product_asset_packs/dio_creative_organs_site_matched_v1/ASSET_REVIEW.md",
            ],
            "primary": "assets/creative_handoff.png",
        },
        "dicere": {
            "name": "Dicere",
            "description": "Latest available V42 debut explainer render with production receipt, subtitle track, and styled caption track.",
            "state": "LOCAL_REVIEW_CANDIDATE",
            "limitations": ["Human review is required; the receipt records no publication or release authorization.", "The V42 frame sample shows the visual treatment only; full-video animation and audio still require review."],
            "files": [
                "media/dicere/debut/DICERE_DEBUT_EXPLAINER_V42.mp4",
                "media/dicere/debut/DICERE_DEBUT_EXPLAINER_V42.receipt.json",
                "media/dicere/debut/DICERE_DEBUT_EXPLAINER_V42.srt",
                "media/dicere/debut/DICERE_DEBUT_EXPLAINER_V42.ass",
            ],
            "primary": "DICERE_DEBUT_EXPLAINER_V42.mp4",
        },
    }
    creative_records = []
    for organ_id, spec in creative_specs.items():
        folder = output / "creative_organs" / organ_id
        folder.mkdir(parents=True, exist_ok=True)
        copied = []
        for source_relative in spec["files"]:
            source_path = (repo / source_relative).resolve()
            source_path.relative_to(repo)
            if not source_path.is_file():
                raise SystemExit(f"Missing required creative proof for {organ_id}: {source_relative}")
            # Keep the selected demo HTML and its media siblings together so its relative links work.
            if organ_id == "sonoris" and "/final_product_candidate/" in source_relative:
                target_relative = Path("demo") / Path(source_relative).name
            elif organ_id == "pictora" and "/assets/" in source_relative:
                target_relative = Path("assets") / Path(source_relative).name
            elif organ_id == "pictora" and "/workflows/" in source_relative:
                target_relative = Path("workflows") / Path(source_relative).name
            elif organ_id == "pictora" and "/pictora_jobs/" in source_relative:
                job_name = source_path.parent.name
                target_relative = Path("receipts") / f"{job_name}_PICTORA_JOB_RECEIPT.json"
            elif organ_id == "pictora" and "dio_creative_organs_site_matched_v1/assets/" in source_relative:
                target_relative = Path("assets") / Path(source_relative).name
            elif organ_id == "pictora" and "dio_creative_organs_site_matched_v1/" in source_relative:
                target_relative = Path("receipts") / Path(source_relative).name
            else:
                target_relative = Path(source_path.name)
            target = folder / target_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target)
            copied.append({
                "path": target.relative_to(output).as_posix(),
                "source_path": source_path.relative_to(repo).as_posix(),
                "bytes": target.stat().st_size,
                "sha256": sha256(target),
                "media_type": mimetypes.guess_type(source_path.name)[0] or "application/octet-stream",
            })
        creative_records.append({
            "organ_id": organ_id,
            "name": spec["name"],
            "description": spec["description"],
            "state": spec["state"],
            "limitations": spec["limitations"],
            "primary_artifact": f"creative_organs/{organ_id}/{spec['primary']}",
            "files": copied,
        })

    index = {
        "schema": "dio.product_proof_portfolio.v1",
        "generated_from": qualification.relative_to(repo).as_posix(),
        "qualification_snapshot_sha256": sha256(qualification),
        "source_snapshot_generated_at": snapshot.get("generated_at"),
        "evidence_as_of": snapshot.get("evidence_as_of"),
        "selection_policy": "One selected customer-facing artifact per catalog offer, paired with its current product-specific receipt or evidence record when present. Selection prefers PDF, then PPTX, DOCX, XLSX, HTML, image, ZIP, Markdown, CSV, JSON; ties prefer a reviewed-final or baseline/normal path. HOMS Exam selects the saved Grades 1-11 candidate ZIP plus the complete Grade 12 two-paper candidate ZIP. HTML-local assets are collected when referenced.",
        "important_limit": "These are review proofs and controlled examples. They do not certify professional quality, source truth, customer acceptance, commercial viability, or release authorization. Synthetic inputs remain synthetic.",
        "summary": {
            "catalog_offers": len(records),
            "product_evidence_records_included": sum(bool(record["product_evidence"]) for record in records),
            "product_receipts_included": sum(bool(record["product_evidence"] and record["product_evidence"]["kind"] == "receipt") for record in records),
            "future_dated_deliverable_refs_excluded": sum(record["future_dated_references_excluded"] for record in records),
            "independent_professional_signoffs": sum(bool(record["independent_professional_signoff"]) for record in records),
            "buyer_acceptance_established": sum(record["buyer_acceptance"] == "ESTABLISHED" for record in records),
            "release_authorized": sum(record["release_authorized"] for record in records),
            "execution_pass": sum(record["readiness_verdicts"]["dimensions"]["execution"] == "PASS" for record in records),
            "output_quality_unverified": sum(record["readiness_verdicts"]["dimensions"]["output_quality"] == "UNVERIFIED" for record in records),
            "evidence_traceable_unvalidated": sum(record["readiness_verdicts"]["dimensions"]["evidence_validity"] == "TRACEABLE_UNVALIDATED" for record in records),
            "customer_acceptance_unverified": sum(record["readiness_verdicts"]["dimensions"]["customer_acceptance"] == "UNVERIFIED" for record in records),
            "release_held": sum(record["readiness_verdicts"]["dimensions"]["release"] == "HELD" for record in records),
        },
        "products": records,
        "supplemental_creative_organs": creative_records,
    }
    (output / "PRODUCT_PROOF_INDEX.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (output / "PRODUCT_PROOF_INDEX.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = [
            "product_id", "name", "suite", "disposition", "pilot_candidate", "route_status", "artifact_source_class",
            "future_dated_references_excluded", "primary_artifact", "source_artifact", "artifact_sha256", "artifact_bytes",
            "product_evidence_path", "product_evidence_sha256", "independent_professional_signoff",
            "buyer_acceptance", "commercial_validation", "release_authorized", "execution_verdict",
            "output_quality_verdict", "evidence_validity_verdict", "customer_acceptance_verdict", "release_verdict", "professional_readiness", "quality_limits",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            receipt = record["product_evidence"] or {}
            writer.writerow({
                **{key: safe_text(record.get(key)) for key in fields if key not in {"product_evidence_path", "product_evidence_sha256", "quality_limits"}},
                "product_evidence_path": receipt.get("path", ""),
                "product_evidence_sha256": receipt.get("sha256", ""),
                "quality_limits": " | ".join(record["quality_limits"]),
                "execution_verdict": record["readiness_verdicts"]["dimensions"]["execution"],
                "output_quality_verdict": record["readiness_verdicts"]["dimensions"]["output_quality"],
                "evidence_validity_verdict": record["readiness_verdicts"]["dimensions"]["evidence_validity"],
                "customer_acceptance_verdict": record["readiness_verdicts"]["dimensions"]["customer_acceptance"],
                "release_verdict": record["readiness_verdicts"]["dimensions"]["release"],
                "professional_readiness": record["readiness_verdicts"]["professional_readiness"],
            })

    cards = []
    for record in records:
        artifact = record["primary_artifact"]
        status = "Pilot candidate · human review" if record["pilot_candidate"] else "Held execution"
        if record["artifact_source_class"] == "historical_baseline_fallback":
            status += " · historical proof"
        limits = " ".join(record["quality_limits"][:2]) or "No product-specific quality limit supplied."
        cards.append(
            f'<article class="card" data-suite="{html.escape(record["suite"])}" data-name="{html.escape(record["name"])}">'
            f'<div class="eyebrow">{html.escape(record["suite"])}</div>'
            f'<h2>{html.escape(record["name"])}</h2>'
            f'<div class="badge">{html.escape(status)}</div>'
            f'<p class="limit">{html.escape(limits)}</p>'
            f'<div class="links"><a href="proofs/{html.escape(record["product_id"])}/{html.escape(artifact)}">Open selected proof</a>'
            + (f'<a class="secondary" href="proofs/{html.escape(record["product_id"])}/{html.escape(record["product_evidence"]["path"])}">Product evidence</a>' if record["product_evidence"] else "")
            + "</div></article>"
        )
    creative_cards = []
    for organ in creative_records:
        creative_cards.append(
            f'<article class="card" data-suite="Creative organs" data-name="{html.escape(organ["name"])}">'
            f'<div class="eyebrow">Creative organ · {html.escape(organ["state"])}</div>'
            f'<h2>{html.escape(organ["name"])}</h2>'
            f'<p class="limit">{html.escape(organ["description"])} {html.escape(" ".join(organ["limitations"]))}</p>'
            f'<div class="links"><a href="{html.escape(organ["primary_artifact"])}">Open selected proof</a></div></article>'
        )
    html_doc = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DIO · Product Proof Portfolio</title><style>
:root{{--ink:#11131a;--panel:#1a1d27;--muted:#aeb4c1;--gold:#e5bd67;--line:#353947;--paper:#f4f0e7}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(ellipse at 15% 0,#2d2a22 0,transparent 38%),var(--ink);color:var(--paper);font:15px/1.55 Inter,Segoe UI,Arial,sans-serif}}
header{{padding:42px max(24px,calc((100vw - 1320px)/2));border-bottom:1px solid var(--line)}}.kicker{{color:var(--gold);text-transform:uppercase;letter-spacing:.18em;font-size:12px;font-weight:700}}
h1{{font-size:clamp(32px,5vw,58px);line-height:1.04;margin:12px 0}}.intro{{max-width:850px;color:var(--muted);font-size:17px}}.stats{{display:flex;gap:12px;flex-wrap:wrap;margin-top:26px}}.stat{{border:1px solid var(--line);background:#ffffff07;border-radius:10px;padding:10px 14px}}.stat strong{{color:var(--gold);font-size:20px;margin-right:7px}}
main{{max-width:1320px;margin:26px auto 64px;padding:0 24px}}.toolbar{{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}}input,select{{background:var(--panel);border:1px solid var(--line);color:var(--paper);border-radius:8px;padding:11px 13px;font:inherit}}input{{min-width:240px;flex:1}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:14px}}.card{{background:linear-gradient(145deg,#20232d,#171921);border:1px solid var(--line);border-radius:12px;padding:18px;display:flex;flex-direction:column;min-height:225px}}.eyebrow{{font-size:11px;color:var(--gold);letter-spacing:.12em;text-transform:uppercase}}h2{{font-size:20px;margin:8px 0 10px}}.badge{{font-size:12px;color:#f3d994}}.limit{{font-size:13px;color:var(--muted);flex:1}}.links{{display:flex;gap:14px;flex-wrap:wrap;margin-top:14px}}a{{color:var(--gold);font-weight:650;text-decoration:none}}a:hover{{text-decoration:underline}}.secondary{{color:#d2d6de}}footer{{max-width:1320px;margin:0 auto;padding:0 24px 44px;color:var(--muted);font-size:13px}}.notice{{border-left:3px solid var(--gold);padding:10px 14px;background:#e5bd670a;margin:18px 0}}.count{{color:var(--muted);margin-left:auto}}
</style></head><body><header><div class="kicker">DIO · Customer Product Catalog</div><h1>Proof Portfolio</h1><p class="intro">A curated, source-bound review surface for all 68 catalog offers, paired with product-specific evidence where available.</p><div class="stats"><div class="stat"><strong>68</strong>catalog offers</div><div class="stat"><strong>{index['summary']['product_evidence_records_included']}</strong>product evidence records</div><div class="stat"><strong>{index['summary']['independent_professional_signoffs']}</strong>professional sign-offs</div><div class="stat"><strong>{index['summary']['release_authorized']}</strong>release authorizations</div></div></header>
<main><div class="notice">These files are review evidence and controlled examples. Route completion does not establish source truth, customer acceptance, expert approval, commercial viability, or release authority. Read each product's limits in the index before relying on its sample.</div><div class="toolbar"><input id="search" type="search" placeholder="Search products or suites" aria-label="Search products"><select id="status" aria-label="Filter by review status"><option value="">All statuses</option><option value="pilot">Pilot candidates</option><option value="held">Held executions</option></select><span class="count" id="count">68 products</span></div><section class="grid" id="grid">{''.join(cards)}</section><h2>Supplemental creative-organ proofs</h2><section class="grid">{''.join(creative_cards)}</section></main>
<footer>Source snapshot: {html.escape(str(index['source_snapshot_generated_at']))} · Evidence as of {html.escape(str(index['evidence_as_of']))}. The JSON and CSV indexes include SHA-256 hashes, original workspace paths, product-evidence hashes, and quality limits.</footer>
<script>const q=document.querySelector('#search'),s=document.querySelector('#status'),cards=[...document.querySelectorAll('.card')],count=document.querySelector('#count');function filter(){{const t=q.value.toLowerCase();let n=0;cards.forEach(c=>{{const ok=(!t||(c.dataset.name+' '+c.dataset.suite).toLowerCase().includes(t))&&(!s.value||(s.value==='pilot'?c.textContent.includes('Pilot candidate'):c.textContent.includes('Held execution')));c.hidden=!ok;if(ok)n++}});count.textContent=n+' products'}}q.addEventListener('input',filter);s.addEventListener('change',filter);</script></body></html>'''
    (output / "index.html").write_text(html_doc, encoding="utf-8")

    readme = f"""# DIO Product Proof Portfolio

This package selects one strongest available customer-facing artifact for each of the 68 catalog offers and includes its product-specific receipt or evidence record when present. Open `index.html` for the review surface; `PRODUCT_PROOF_INDEX.json` and `.csv` provide exact source paths and SHA-256 hashes.

## Evidence boundary

- Snapshot generated: `{snapshot.get('generated_at')}`; evidence date: `{snapshot.get('evidence_as_of')}`. Deliverable references dated after that snapshot were excluded ({index['summary']['future_dated_deliverable_refs_excluded']} refs); products without an in-window customer deliverable use a clearly marked historical baseline artifact.
- The artifacts are controlled examples and held review material. **They are not professional certifications, customer acceptance, verified source truth, commercial validation, or release authorization.**
- The current qualification snapshot records {index['summary']['independent_professional_signoffs']}/68 independent professional sign-offs and {index['summary']['release_authorized']} release authorizations.
- Product-specific limitations are retained in each portfolio record and the index. Sonoris, Pictora and Dicere media candidates are included as a separate appendix because they are creative organs, not catalog offers.
- HOMS Exam links to randomized Grades 1–11 exam and memo candidates and a complete Grade 12 two-paper Business Studies candidate (150 marks per paper, 120 minutes per paper). All remain drafts requiring educator moderation and release authorization.

## Selection and integrity

Selection is deterministic and based on the current qualification snapshot's `customer_deliverable_refs`, with PDF preferred, followed by editable office files, HTML and other formats. HOMS Exam uses the saved Grades 1–11 candidate ZIP plus the complete Grade 12 two-paper candidate ZIP. Local HTML dependencies are copied when referenced. Every copied output and route receipt has a SHA-256 hash in the manifest. Hash verification establishes byte identity only, not content correctness.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")

    # Hash every packaged file after the indexes and documentation are complete.
    package_files = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "PACKAGE_SHA256SUMS.txt":
            package_files.append(f"{sha256(path)}  {path.relative_to(output).as_posix()}")
    (output / "PACKAGE_SHA256SUMS.txt").write_text("\n".join(package_files) + "\n", encoding="utf-8")

    zip_path = output.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                archive.write(path, (output.name + "/" + path.relative_to(output).as_posix()))
    print(json.dumps({"output": str(output), "zip": str(zip_path), "products": len(records), "product_evidence_records": index["summary"]["product_evidence_records_included"], "product_receipts": index["summary"]["product_receipts_included"], "zip_bytes": zip_path.stat().st_size}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
