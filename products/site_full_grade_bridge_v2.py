from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.document_studio.art_direction import build_art_direction
from lingua.product_projection import build_projection_plan
from lingua.semantic_law import build_semantic_law, validate_projection
from presence_core.studio_release import prepare_studio_release
from scripts.beast_visual_memory import resolve_visual_memory

from products.studio_full_grade_convergence import (
    ROOT,
    StudioFullGradeError,
    _apply_visual_memory,
    _base_native_closure,
    _fingerprint,
    _load,
    _render_site,
    _sha,
    _site_product_audience,
    _site_visual_qa,
    _write_json,
)


def _website_projection(
    *,
    law: dict[str, Any],
    base_projection: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Add a website-native LINGUA surface without pretending a video arc is a site map."""
    projection = json.loads(json.dumps(base_projection))
    landscape = dict((projection.get("surfaces") or {}).get("landscape_explainer") or {})
    declared_services = [str(row.get("title") or "") for row in manifest["artifact_contract"].get("sections") or []]
    website = {
        "schema": "dio.lingua.website_surface.v1",
        "arc_family": "problem_to_method_to_proof_to_human_action",
        "roles": [
            "site_hook",
            *[f"service_{index + 1}" for index in range(len(declared_services))],
            "method",
            "proof",
            "human_authority",
            "cta",
        ],
        "service_labels": declared_services,
        "tone": list(landscape.get("tone") or []),
        "pacing": "progressive_scroll",
        "visual_grammar": str(landscape.get("visual_grammar") or "clean_professional_editorial"),
        "motion_grammar": "scroll_depth_editorial_transitions",
        "content_density": "progressive_disclosure",
        "proof_treatment": "embedded_inspectable_provenance",
        "navigation_model": "single_page_editorial_sequence",
        "authority_model": "human_release_visible",
        "source_semantic_law_hash": law["semantic_law_hash"],
    }
    projection.setdefault("surfaces", {})["website"] = website
    projection.setdefault("channel_projections", {})["WEBSITE"] = {
        "tone": "credible_editorial",
        "cta_style": "bounded_professional_next_step",
        "density": "progressive",
        "format": "responsive_proof_carrying_site",
        "surface": "website",
    }
    projection["website_projection_is_campaign_reuse"] = False
    projection.pop("projection_hash", None)
    projection["projection_hash"] = _fingerprint(projection)
    return projection


def _website_story(
    *,
    law: dict[str, Any],
    projection: dict[str, Any],
    manifest: dict[str, Any],
    product: dict[str, Any],
    audience: dict[str, Any],
) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    brand = contract["brand"]
    positioning = contract["positioning"]
    declared = list(contract.get("sections") or [])
    website = dict((projection.get("surfaces") or {}).get("website") or {})

    scenes: list[dict[str, Any]] = [
        {
            "scene_id": "web_01_hook",
            "role": "site_hook",
            "semantic_focus": "problem_and_category",
            "screen_text": str(brand["headline"]),
            "narration": str(positioning["buyer_problem"]),
            "visual": "Open on the actual professional decision context, with research material visible as working evidence rather than decorative interface chrome.",
        }
    ]
    visual_prompts = [
        "Show the framing of a difficult question through real notes, source material and an active working surface.",
        "Show source fragments being compared and synthesised into an inspectable evidence trail, with no fake dashboard treatment.",
        "Show the handoff from evidence to a human decision artifact, with the reviewer or client visibly retaining judgment.",
    ]
    for index, row in enumerate(declared):
        scenes.append(
            {
                "scene_id": f"web_{index + 2:02d}_service",
                "role": f"service_{index + 1}",
                "semantic_focus": f"service_{index + 1}",
                "screen_text": str(row["title"]),
                "narration": str(row["body"]),
                "visual": visual_prompts[index % len(visual_prompts)],
            }
        )
    scenes.extend(
        [
            {
                "scene_id": "web_method",
                "role": "method",
                "semantic_focus": "method",
                "screen_text": "From question to reviewable handoff",
                "narration": "The work begins with the decision context, binds supplied material, exposes uncertainty and prepares an inspectable handoff for professional review.",
                "visual": "Use a spatial process composition built from the real work objects, moving from question to evidence to reviewed handoff without turning the process into a SaaS diagram.",
            },
            {
                "scene_id": "web_proof",
                "role": "proof",
                "semantic_focus": "proof",
                "screen_text": "Inspect the trail behind the claim",
                "narration": str(product["proof"]),
                "visual": "Make the proof object the protagonist: semantic law, source lineage, visual QA or provenance record shown as a tangible inspectable artifact.",
            },
            {
                "scene_id": "web_authority",
                "role": "human_authority",
                "semantic_focus": "authority",
                "screen_text": "Professional judgment stays human",
                "narration": "The site may explain evidence-bound work, but it cannot invent clients, outcomes, approval, publication authority or professional judgment.",
                "visual": "End the evidence sequence on a real human review moment where authority is visibly exercised rather than hidden in disclaimer text.",
            },
            {
                "scene_id": "web_cta",
                "role": "cta",
                "semantic_focus": "bounded_next_step",
                "screen_text": "Start with the decision context",
                "narration": str(product["cta"]),
                "visual": "Resolve on one calm, concrete next action with generous negative space and no urgency theatre.",
            },
        ]
    )

    roles = [str(row["role"]) for row in scenes]
    focuses = [str(row["semantic_focus"]) for row in scenes]
    screen_texts = [" ".join(str(row["screen_text"]).casefold().split()) for row in scenes]
    if len(set(roles)) != len(roles):
        raise StudioFullGradeError("LINGUA website projection produced duplicate semantic roles")
    if len(set(focuses)) < len(focuses) - 1:
        raise StudioFullGradeError("LINGUA website projection collapsed distinct sections into duplicate semantic focuses")
    if len(set(screen_texts)) != len(screen_texts):
        raise StudioFullGradeError("LINGUA website projection repeated visible section copy")

    story_core = {
        "schema": "dio.lingua.website_story.v1",
        "family_id": f"site:{manifest['studio_id']}",
        "surface": "website",
        "title": str(brand["title"]),
        "semantic_law_hash": law["semantic_law_hash"],
        "projection_hash": projection["projection_hash"],
        "arc_family": website["arc_family"],
        "creative_direction": {
            "audience_archetype": str(projection.get("audience_archetype") or "general_professional"),
            "tone": list(website.get("tone") or []),
            "pacing": website["pacing"],
            "visual_grammar": website["visual_grammar"],
            "motion_grammar": website["motion_grammar"],
            "surface": "website",
        },
        "semantic_guardrails": {
            "prohibitions": list((law.get("prohibition") or {}).get("rules") or []),
            "preserves": list(projection.get("preserves") or []),
            "campaign_story_reuse": "REFUSE",
            "publication": "held",
            "spend": "disabled",
        },
        "storyline_strategy": {
            "mode": "website_semantic_section_allocation",
            "campaign_surface_reused": False,
            "progression": ["problem", "services", "method", "proof", "authority", "bounded_action"],
            "service_count": len(declared),
        },
        "scenes": scenes,
    }
    return {**story_core, "story_hash": _fingerprint(story_core)}


def _website_semantic_qa(*, projection: dict[str, Any], story: dict[str, Any]) -> dict[str, Any]:
    scenes = list(story.get("scenes") or [])
    roles = [str(row.get("role") or "") for row in scenes]
    focuses = [str(row.get("semantic_focus") or "") for row in scenes]
    checks = {
        "website_surface_present": bool((projection.get("surfaces") or {}).get("website")),
        "campaign_story_reuse_refused": projection.get("website_projection_is_campaign_reuse") is False,
        "site_story_surface_is_website": story.get("surface") == "website",
        "semantic_roles_unique": len(set(roles)) == len(roles),
        "semantic_focus_diverse": len(set(focuses)) >= max(5, len(focuses) - 1),
        "proof_role_present": "proof" in roles,
        "human_authority_role_present": "human_authority" in roles,
        "bounded_cta_role_present": "cta" in roles,
    }
    return {
        "schema": "dio.site_studio.website_semantic_qa.v1",
        "checks": checks,
        "passed": all(checks.values()),
        "roles": roles,
        "semantic_focuses": focuses,
    }


def run_site_full_grade_v2(*, manifest_path: Path, output_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = manifest_path if manifest_path.is_absolute() else root / manifest_path
    manifest = _load(manifest_path.resolve())
    if manifest.get("artifact_contract", {}).get("kind") != "site":
        raise StudioFullGradeError("Site full-grade runner requires a site Studio manifest")

    output_dir = output_dir.resolve()
    base = _base_native_closure(manifest_path, output_dir / "base", root)
    product, audience = _site_product_audience(manifest)
    law = build_semantic_law(product, audience)
    base_projection = build_projection_plan(
        law,
        product,
        audience,
        {"WEBSITE": {"format": "responsive_proof_carrying_site"}},
    )
    projection = _website_projection(
        law=law,
        base_projection=base_projection,
        manifest=manifest,
    )
    projection_errors = validate_projection(law, projection)
    if projection_errors:
        raise StudioFullGradeError("LINGUA Site projection refused: " + "; ".join(projection_errors))

    story = _website_story(
        law=law,
        projection=projection,
        manifest=manifest,
        product=product,
        audience=audience,
    )
    semantic_qa = _website_semantic_qa(projection=projection, story=story)
    if not semantic_qa["passed"]:
        raise StudioFullGradeError(
            "LINGUA website semantic QA refused: "
            + ", ".join(key for key, passed in semantic_qa["checks"].items() if not passed)
        )

    surface = projection["surfaces"]["website"]
    memory = resolve_visual_memory(
        audience_archetype=str(projection.get("audience_archetype") or "general_professional"),
        surface="website",
        visual_grammar=str(surface.get("visual_grammar") or ""),
    )
    art = _apply_visual_memory(build_art_direction(story, beast_memory=memory), memory)

    package_dir = output_dir / "customer" / "FULL_GRADE_SITE"
    proof_dir = package_dir / "proof"
    _write_json(proof_dir / "LINGUA_SEMANTIC_LAW.json", law)
    _write_json(proof_dir / "LINGUA_SITE_PROJECTION.json", projection)
    _write_json(proof_dir / "LINGUA_WEBSITE_SEMANTIC_QA.json", semantic_qa)
    _write_json(proof_dir / "SITE_STORY_ARCHITECTURE.json", story)
    _write_json(proof_dir / "DOCUMENT_STUDIO_SITE_ART_DIRECTION.json", art)
    _write_json(proof_dir / "BEAST_SITE_VISUAL_MEMORY.json", memory)

    index_path, page, css = _render_site(
        manifest,
        law=law,
        projection=projection,
        story=story,
        art=art,
        package_dir=package_dir,
    )
    visual_qa = _site_visual_qa(
        law=law,
        projection=projection,
        art=art,
        html_text=page,
        css_text=css,
    )
    visual_qa.setdefault("checks", {})["website_semantic_qa"] = semantic_qa["passed"]
    visual_qa["passed"] = all(visual_qa["checks"].values())
    _write_json(proof_dir / "SITE_VISUAL_QA.json", visual_qa)
    if not visual_qa["passed"]:
        raise StudioFullGradeError(
            "Site full-grade visual QA refused: "
            + ", ".join(key for key, passed in visual_qa["checks"].items() if not passed)
        )

    artifact_rows = []
    for path in sorted(p for p in package_dir.rglob("*") if p.is_file() and p.name != "SITE_PROOF_MANIFEST.json"):
        artifact_rows.append(
            {
                "path": str(path.relative_to(package_dir)),
                "sha256": _sha(path),
                "bytes": path.stat().st_size,
            }
        )
    proof_manifest = {
        "schema": "dio.site_studio.full_grade_proof_manifest.v2",
        "studio_id": manifest["studio_id"],
        "semantic_law_hash": law["semantic_law_hash"],
        "projection_hash": projection["projection_hash"],
        "story_hash": story["story_hash"],
        "art_direction_hash": art["art_direction_hash"],
        "beast_visual_memory_state": memory.get("state"),
        "website_semantic_qa": "PASS",
        "visual_qa": "PASS",
        "campaign_story_reuse": "REFUSE",
        "base_native_closure_fingerprint": base["receipt"]["native_closure_fingerprint"],
        "artifacts": artifact_rows,
        "human_gate": "NEEDS_YOU",
        "external_publication": "REFUSE",
        "authority_created": False,
    }
    proof_manifest["proof_fingerprint"] = _fingerprint(proof_manifest)
    _write_json(proof_dir / "SITE_PROOF_MANIFEST.json", proof_manifest)

    release = prepare_studio_release(
        studio_id=manifest["studio_id"],
        entrypoint=str(index_path.relative_to(output_dir)),
    )
    _write_json(output_dir / "presence" / "PRESENCE_FULL_GRADE_SITE_RELEASE.json", release)

    receipt = {
        "schema": "dio.site_studio.full_grade_receipt.v2",
        "studio_id": manifest["studio_id"],
        "base_native_closure": "PASS",
        "lingua_semantic_projection": "PASS",
        "lingua_website_surface": "PASS",
        "campaign_story_reuse": "REFUSE",
        "document_studio_art_direction": "PASS",
        "beast_visual_memory": "RESOLVED",
        "beast_visual_memory_state": memory.get("state"),
        "site_semantic_qa": "PASS",
        "site_visual_qa": "PASS",
        "proof_carrying_customer_site": "PASS",
        "customer_artifact": str(index_path.relative_to(output_dir)),
        "proof_fingerprint": proof_manifest["proof_fingerprint"],
        "human_gate": "NEEDS_YOU",
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "authority_created": False,
        "full_grade_state": "PASS",
    }
    receipt["full_grade_fingerprint"] = _fingerprint(receipt)
    _write_json(output_dir / "SITE_STUDIO_FULL_GRADE_RECEIPT.json", receipt)
    return receipt


__all__ = ["run_site_full_grade_v2"]
