from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from adapters.format_core.site_visual_compositor import render_site_visual_assets
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


def _escape_attr(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _figure(asset: dict[str, Any], *, class_name: str = "dio-svg-scene") -> str:
    material_kind = str(asset.get("selected_material_kind") or "native_renderer").replace("_", " ")
    return (
        f'<figure class="{class_name}" data-dio-role="{asset["role"]}" data-dio-material="{_escape_attr(material_kind)}">'
        f'<img src="assets/svg/{asset["path"]}" alt="{_escape_attr(str(asset.get("alt_text") or asset["role"]))}" loading="lazy">'
        f'<figcaption>Governed Format Core composition · {material_kind} · Site Studio semantics</figcaption>'
        '</figure>'
    )


def _inject_svg_assets(*, package_dir: Path, compositor: dict[str, Any]) -> dict[str, Any]:
    assets = {str(row["role"]): row for row in compositor.get("assets") or []}
    required = {"site_hook", "service_1", "service_2", "service_3", "method", "proof", "human_authority", "cta"}
    if set(assets) != required:
        raise SiteFullGradeV3Error(f"Format Core visual roles do not match website contract: {sorted(assets)}")

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
/* DIO Format Core governed visual scene layer. */
.dio-svg-hero,.dio-svg-scene,.dio-svg-cta{width:min(1180px,calc(100% - 40px));margin:34px auto 0;position:relative;overflow:hidden;background:#0b1118;border:1px solid #ffffff20;border-radius:16px}
.dio-svg-hero{margin-top:48px}.dio-svg-scene{margin-bottom:42px}.dio-svg-cta{margin:72px auto}
.dio-svg-hero img,.dio-svg-scene img,.dio-svg-cta img{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.dio-svg-hero figcaption,.dio-svg-scene figcaption,.dio-svg-cta figcaption{position:absolute;left:14px;bottom:12px;padding:7px 10px;background:#071014e8;color:#d9e5e4;font:800 .62rem/1.2 ui-sans-serif,system-ui,sans-serif;letter-spacing:.09em;text-transform:uppercase;border-left:3px solid #5fd1d8}
.split-band>.dio-svg-scene,.proof-band>.dio-svg-scene{border-color:#18202430}
@media(max-width:820px){.dio-svg-hero,.dio-svg-scene,.dio-svg-cta{width:min(100% - 24px,1180px);margin-top:24px}.dio-svg-hero figcaption,.dio-svg-scene figcaption,.dio-svg-cta figcaption{position:static;background:#091216;padding:9px 10px}.dio-svg-hero img,.dio-svg-scene img,.dio-svg-cta img{aspect-ratio:4/3}}
"""
    index_path.write_text(html, encoding="utf-8")
    css_path.write_text(css, encoding="utf-8")

    embedded = [f'assets/svg/{row["path"]}' in html for row in compositor.get("assets") or []]
    return {
        "schema": "dio.site_studio.format_core_visual_embedding_qa.v2",
        "passed": all(embedded) and html.count("data-dio-role=") == 8,
        "all_visual_assets_embedded": all(embedded),
        "embedded_role_count": html.count("data-dio-role="),
        "visual_projection_authority": "DIO_FORMAT_CORE",
        "site_semantic_authority": "DIO_SITE_STUDIO",
        "external_material_authority": "REFUSE",
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
            "deterministic_format_core_scene_assets": compositor.get("scene_count") == 8,
            "visual_assets_embedded": embedding_qa.get("passed") is True,
            "format_core_owns_visual_geometry": all(row.get("geometry_authority") == "DIO_FORMAT_CORE" for row in compositor.get("assets") or []),
            "format_core_owns_visual_text_projection": all(row.get("text_authority") == "DIO_FORMAT_CORE" for row in compositor.get("assets") or []),
            "site_studio_owns_semantics": compositor.get("site_semantic_authority") == "DIO_SITE_STUDIO",
            "format_core_visual_composition_pass": compositor.get("format_core_visual_composition") == "PASS",
            "visual_material_resolution_pass": compositor.get("visual_material_resolution_state") == "PASS",
            "visual_materials_commercially_allowed": compositor.get("all_selected_materials_commercially_allowed") is True,
            "visual_materials_approved": compositor.get("all_selected_materials_approved") is True,
            "external_material_authority_refused": compositor.get("external_material_authority") == "REFUSE",
            "remote_runtime_asset_fetch_refused": compositor.get("remote_runtime_asset_fetch") == "REFUSE",
            "role_material_selection_refused": compositor.get("role_material_selection") == "REFUSE",
            "gamma_layout_authority_refused": compositor.get("gamma_layout_authority") == "REFUSE",
            "gamma_text_authority_refused": compositor.get("gamma_text_authority") == "REFUSE",
        }
    )
    visual_qa["schema"] = "dio.site_studio_full_grade_visual_qa.v4"
    visual_qa["checks"] = checks
    visual_qa["passed"] = all(checks.values())
    visual_qa["visual_scene_asset_count"] = compositor.get("scene_count")
    visual_qa["format_core_visual_profile_id"] = compositor.get("profile_id")
    visual_qa["format_core_visual_profile_hash"] = compositor.get("profile_hash")
    visual_qa["format_core_compositor_fingerprint"] = compositor.get("compositor_fingerprint")
    visual_qa["material_kind_counts"] = compositor.get("material_kind_counts")
    visual_qa["mixed_media_scene_count"] = compositor.get("mixed_media_scene_count")
    _write_json(visual_qa_path, visual_qa)
    if not visual_qa["passed"]:
        raise SiteFullGradeV3Error(
            "Format Core-enhanced Site visual QA refused: " + ", ".join(key for key, passed in checks.items() if not passed)
        )

    manifest_path = proof_dir / "SITE_PROOF_MANIFEST.json"
    manifest = _load(manifest_path)
    artifact_rows = []
    for path in sorted(p for p in package_dir.rglob("*") if p.is_file() and p.name != "SITE_PROOF_MANIFEST.json"):
        artifact_rows.append({"path": str(path.relative_to(package_dir)), "sha256": _sha(path), "bytes": path.stat().st_size})
    manifest["schema"] = "dio.site_studio.full_grade_proof_manifest.v5"
    manifest["artifacts"] = artifact_rows
    manifest["format_core_visual_compositor"] = "PASS"
    manifest["format_core_visual_profile_id"] = compositor.get("profile_id")
    manifest["format_core_visual_profile_hash"] = compositor.get("profile_hash")
    manifest["format_core_compositor_fingerprint"] = compositor.get("compositor_fingerprint")
    manifest["visual_material_registry_schema"] = compositor.get("visual_material_registry_schema")
    manifest["material_kind_counts"] = compositor.get("material_kind_counts")
    manifest["mixed_media_scene_count"] = compositor.get("mixed_media_scene_count")
    manifest["all_selected_materials_commercially_allowed"] = compositor.get("all_selected_materials_commercially_allowed")
    manifest["all_selected_materials_approved"] = compositor.get("all_selected_materials_approved")
    manifest["external_material_authority"] = "REFUSE"
    manifest["site_semantic_authority"] = "DIO_SITE_STUDIO"
    manifest["visual_projection_authority"] = "DIO_FORMAT_CORE"
    manifest["document_studio_svg_compositor"] = "RETIRED_TO_FORMAT_CORE"
    manifest["gamma_visual_role"] = "OPTIONAL_IMAGE_MATERIAL_ONLY"
    manifest["gamma_layout_authority"] = "REFUSE"
    manifest["gamma_text_authority"] = "REFUSE"
    manifest.pop("proof_fingerprint", None)
    manifest["proof_fingerprint"] = _fingerprint(manifest)
    _write_json(manifest_path, manifest)

    receipt_path = output_dir / "SITE_STUDIO_FULL_GRADE_RECEIPT.json"
    receipt = _load(receipt_path)
    receipt["schema"] = "dio.site_studio.full_grade_receipt.v5"
    receipt["format_core_visual_compositor"] = "PASS"
    receipt["format_core_visual_profile_id"] = compositor.get("profile_id")
    receipt["format_core_visual_profile_hash"] = compositor.get("profile_hash")
    receipt["format_core_compositor_fingerprint"] = compositor.get("compositor_fingerprint")
    receipt["visual_material_registry_schema"] = compositor.get("visual_material_registry_schema")
    receipt["material_kind_counts"] = compositor.get("material_kind_counts")
    receipt["mixed_media_scene_count"] = compositor.get("mixed_media_scene_count")
    receipt["all_selected_materials_commercially_allowed"] = compositor.get("all_selected_materials_commercially_allowed")
    receipt["all_selected_materials_approved"] = compositor.get("all_selected_materials_approved")
    receipt["external_material_authority"] = "REFUSE"
    receipt["site_semantic_authority"] = "DIO_SITE_STUDIO"
    receipt["visual_projection_authority"] = "DIO_FORMAT_CORE"
    receipt["document_studio_svg_compositor"] = "RETIRED_TO_FORMAT_CORE"
    receipt["gamma_visual_role"] = "OPTIONAL_IMAGE_MATERIAL_ONLY"
    receipt["gamma_layout_authority"] = "REFUSE"
    receipt["gamma_text_authority"] = "REFUSE"
    receipt["proof_fingerprint"] = manifest["proof_fingerprint"]
    receipt.pop("full_grade_fingerprint", None)
    receipt["full_grade_fingerprint"] = _fingerprint(receipt)
    _write_json(receipt_path, receipt)
    return receipt


def run_site_full_grade_v3(*, manifest_path: Path, output_dir: Path, root: Path) -> dict[str, Any]:
    """Run Site Studio full grade with Format Core as semantic visual and material projection organ."""
    output_dir = output_dir.resolve()
    run_site_full_grade_v2(manifest_path=manifest_path, output_dir=output_dir, root=root)

    package_dir = output_dir / "customer" / "FULL_GRADE_SITE"
    proof_dir = package_dir / "proof"
    story = _load(proof_dir / "SITE_STORY_ARCHITECTURE.json")
    art = _load(proof_dir / "DOCUMENT_STUDIO_SITE_ART_DIRECTION.json")
    svg_dir = package_dir / "assets" / "svg"
    compositor = render_site_visual_assets(story=story, art=art, output_dir=svg_dir, material_root=root)
    _write_json(proof_dir / "FORMAT_CORE_SITE_VISUAL_COMPOSITOR_RECEIPT.json", compositor)
    embedding_qa = _inject_svg_assets(package_dir=package_dir, compositor=compositor)
    _write_json(proof_dir / "SITE_FORMAT_CORE_VISUAL_EMBEDDING_QA.json", embedding_qa)
    if not embedding_qa["passed"]:
        raise SiteFullGradeV3Error("Site Format Core visual embedding QA refused the generated website")
    return _refresh_full_grade_proof(output_dir=output_dir, compositor=compositor, embedding_qa=embedding_qa)
