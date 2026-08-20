from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from adapters.document_studio.site_svg_compositor import render_site_svg_assets
from products.site_full_grade_bridge_v2 import (
    _website_projection,
    _website_semantic_qa,
    _website_story,
    run_site_full_grade_v2,
)
from products.studio_full_grade_convergence import _fingerprint, _sha, _write_json


class SiteFullGradeV3Error(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SiteFullGradeV3Error(f"invalid or missing JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SiteFullGradeV3Error(f"expected object: {path}")
    return value


def _figure(asset: dict[str, Any], *, class_name: str = "dio-svg-scene") -> str:
    return (
        f'<figure class="{class_name}" data-dio-role="{asset["role"]}">'
        f'<img src="assets/svg/{asset["path"]}" alt="{_escape_attr(str(asset.get("alt_text") or asset["role"]))}" loading="lazy">'
        '<figcaption>Deterministic Document Studio SVG · DIO owns text and geometry</figcaption>'
        '</figure>'
    )


def _escape_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _inject_svg_assets(*, package_dir: Path, compositor: dict[str, Any]) -> dict[str, Any]:
    assets = {str(row["role"]): row for row in compositor.get("assets") or []}
    required = {
        "site_hook",
        "service_1",
        "service_2",
        "service_3",
        "method",
        "proof",
        "human_authority",
        "cta",
    }
    if set(assets) != required:
        raise SiteFullGradeV3Error(f"SVG compositor roles do not match website contract: {sorted(assets)}")

    index_path = package_dir / "index.html"
    css_path = package_dir / "styles.css"
    html = index_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8")

    hero = _figure(assets["site_hook"], class_name="dio-svg-hero")
    marker = '<ul class="story-strip">'
    if marker not in html:
        raise SiteFullGradeV3Error("Site HTML no longer exposes the story-strip injection seam")
    html = html.replace(marker, hero + marker, 1)

    scene_roles = iter(["service_1", "service_2", "service_3", "method", "proof", "human_authority"])

    def inject_scene(match: re.Match[str]) -> str:
        try:
            role = next(scene_roles)
        except StopIteration:
            return match.group(0)
        return match.group(0) + _figure(assets[role])

    html, scene_count = re.subn(r'(<section class="scene [^"]+">)', inject_scene, html)
    if scene_count < 6:
        raise SiteFullGradeV3Error(f"Site HTML exposed only {scene_count} scene sections; six are required")

    intake_marker = '<section class="intake"'
    if intake_marker not in html:
        raise SiteFullGradeV3Error("Site HTML no longer exposes the intake injection seam")
    html = html.replace(intake_marker, _figure(assets["cta"], class_name="dio-svg-cta") + intake_marker, 1)

    css += """
/* DIO deterministic SVG scene layer, generalized from the HOMS vector-composition pattern. */
.dio-svg-hero,.dio-svg-scene,.dio-svg-cta{width:min(1180px,calc(100% - 40px));margin:34px auto 0;position:relative;overflow:hidden;background:#0b1115;border:1px solid #ffffff20}
.dio-svg-hero{margin-top:48px}.dio-svg-scene{margin-bottom:42px}.dio-svg-cta{margin:72px auto}
.dio-svg-hero img,.dio-svg-scene img,.dio-svg-cta img{display:block;width:100%;height:auto;aspect-ratio:16/10;object-fit:cover}
.dio-svg-hero figcaption,.dio-svg-scene figcaption,.dio-svg-cta figcaption{position:absolute;left:14px;bottom:12px;padding:7px 10px;background:#071014d9;color:#d9e5e4;font:800 .62rem/1.2 ui-sans-serif,system-ui,sans-serif;letter-spacing:.09em;text-transform:uppercase;border-left:3px solid #22d3c5}
.split-band>.dio-svg-scene,.proof-band>.dio-svg-scene{border-color:#18202430}
@media(max-width:820px){.dio-svg-hero,.dio-svg-scene,.dio-svg-cta{width:min(100% - 24px,1180px);margin-top:24px}.dio-svg-hero figcaption,.dio-svg-scene figcaption,.dio-svg-cta figcaption{position:static;background:#091216;padding:9px 10px}.dio-svg-hero img,.dio-svg-scene img,.dio-svg-cta img{aspect-ratio:4/3}}
"""
    index_path.write_text(html, encoding="utf-8")
    css_path.write_text(css, encoding="utf-8")

    embedded = [f'assets/svg/{row["path"]}' in html for row in compositor.get("assets") or []]
    return {
        "schema": "dio.site_studio.svg_embedding_qa.v1",
        "passed": all(embedded) and html.count("data-dio-role=") == 8,
        "all_svg_assets_embedded": all(embedded),
        "embedded_role_count": html.count("data-dio-role="),
        "gamma_layout_authority": "REFUSE",
        "gamma_text_authority": "REFUSE",
        "human_visual_release": "NEEDS_YOU",
    }


def _refresh_full_grade_proof(*, output_dir: Path, compositor: dict[str, Any], embedding_qa: dict[str, Any]) -> dict[str, Any]:
    package_dir = output_dir / "customer" / "FULL_GRADE_SITE"
    proof_dir = package_dir / "proof"
    visual_qa_path = proof_dir / "SITE_VISUAL_QA.json"
    visual_qa = _load(visual_qa_path)
    checks = dict(visual_qa.get("checks") or {})
    checks.update(
        {
            "deterministic_svg_scene_assets": compositor.get("scene_count") == 8,
            "svg_assets_embedded": embedding_qa.get("passed") is True,
            "document_studio_owns_svg_geometry": all(
                row.get("geometry_authority") == "DIO_DOCUMENT_STUDIO" for row in compositor.get("assets") or []
            ),
            "document_studio_owns_svg_text": all(
                row.get("text_authority") == "DIO_DOCUMENT_STUDIO" for row in compositor.get("assets") or []
            ),
            "gamma_layout_authority_refused": compositor.get("gamma_layout_authority") == "REFUSE",
            "gamma_text_authority_refused": compositor.get("gamma_text_authority") == "REFUSE",
        }
    )
    visual_qa["schema"] = "dio.site_studio_full_grade_visual_qa.v2"
    visual_qa["checks"] = checks
    visual_qa["passed"] = all(checks.values())
    visual_qa["svg_scene_asset_count"] = compositor.get("scene_count")
    visual_qa["svg_compositor_fingerprint"] = compositor.get("compositor_fingerprint")
    _write_json(visual_qa_path, visual_qa)
    if not visual_qa["passed"]:
        raise SiteFullGradeV3Error(
            "SVG-enhanced Site visual QA refused: "
            + ", ".join(key for key, passed in checks.items() if not passed)
        )

    manifest_path = proof_dir / "SITE_PROOF_MANIFEST.json"
    manifest = _load(manifest_path)
    artifact_rows = []
    for path in sorted(p for p in package_dir.rglob("*") if p.is_file() and p.name != "SITE_PROOF_MANIFEST.json"):
        artifact_rows.append(
            {
                "path": str(path.relative_to(package_dir)),
                "sha256": _sha(path),
                "bytes": path.stat().st_size,
            }
        )
    manifest["schema"] = "dio.site_studio.full_grade_proof_manifest.v3"
    manifest["artifacts"] = artifact_rows
    manifest["document_studio_svg_compositor"] = "PASS"
    manifest["svg_scene_asset_count"] = compositor.get("scene_count")
    manifest["svg_compositor_fingerprint"] = compositor.get("compositor_fingerprint")
    manifest["gamma_visual_role"] = "OPTIONAL_IMAGE_MATERIAL_ONLY"
    manifest["gamma_layout_authority"] = "REFUSE"
    manifest["gamma_text_authority"] = "REFUSE"
    manifest.pop("proof_fingerprint", None)
    manifest["proof_fingerprint"] = _fingerprint(manifest)
    _write_json(manifest_path, manifest)

    receipt_path = output_dir / "SITE_STUDIO_FULL_GRADE_RECEIPT.json"
    receipt = _load(receipt_path)
    receipt["schema"] = "dio.site_studio.full_grade_receipt.v3"
    receipt["document_studio_svg_compositor"] = "PASS"
    receipt["svg_scene_asset_count"] = compositor.get("scene_count")
    receipt["svg_compositor_fingerprint"] = compositor.get("compositor_fingerprint")
    receipt["gamma_visual_role"] = "OPTIONAL_IMAGE_MATERIAL_ONLY"
    receipt["gamma_layout_authority"] = "REFUSE"
    receipt["gamma_text_authority"] = "REFUSE"
    receipt["proof_fingerprint"] = manifest["proof_fingerprint"]
    receipt.pop("full_grade_fingerprint", None)
    receipt["full_grade_fingerprint"] = _fingerprint(receipt)
    _write_json(receipt_path, receipt)
    return receipt


def run_site_full_grade_v3(*, manifest_path: Path, output_dir: Path, root: Path) -> dict[str, Any]:
    """Run Site Studio v2, then bind deterministic HOMS-derived SVG composition into the canonical artifact."""
    output_dir = output_dir.resolve()
    run_site_full_grade_v2(manifest_path=manifest_path, output_dir=output_dir, root=root)

    package_dir = output_dir / "customer" / "FULL_GRADE_SITE"
    proof_dir = package_dir / "proof"
    story = _load(proof_dir / "SITE_STORY_ARCHITECTURE.json")
    art = _load(proof_dir / "DOCUMENT_STUDIO_SITE_ART_DIRECTION.json")
    svg_dir = package_dir / "assets" / "svg"
    compositor = render_site_svg_assets(story=story, art=art, output_dir=svg_dir)
    _write_json(proof_dir / "DOCUMENT_STUDIO_SVG_COMPOSITOR_RECEIPT.json", compositor)
    embedding_qa = _inject_svg_assets(package_dir=package_dir, compositor=compositor)
    _write_json(proof_dir / "SITE_SVG_EMBEDDING_QA.json", embedding_qa)
    if not embedding_qa["passed"]:
        raise SiteFullGradeV3Error("Site SVG embedding QA refused the generated website")
    return _refresh_full_grade_proof(output_dir=output_dir, compositor=compositor, embedding_qa=embedding_qa)


__all__ = [
    "SiteFullGradeV3Error",
    "run_site_full_grade_v3",
    "_website_projection",
    "_website_semantic_qa",
    "_website_story",
]
