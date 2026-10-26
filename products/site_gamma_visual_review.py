from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VISUAL_PLATE_MODE = "visual_plate_only"


class SiteGammaVisualReviewError(RuntimeError):
    pass


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SiteGammaVisualReviewError(f"invalid or missing JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SiteGammaVisualReviewError(f"expected object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_site_gamma_request(*, site_root: Path, gamma_output_dir: Path) -> dict[str, Any]:
    package = site_root / "customer" / "FULL_GRADE_SITE"
    proof = package / "proof"
    law = _load(proof / "LINGUA_SEMANTIC_LAW.json")
    projection = _load(proof / "LINGUA_SITE_PROJECTION.json")
    story = _load(proof / "SITE_STORY_ARCHITECTURE.json")
    art = _load(proof / "DOCUMENT_STUDIO_SITE_ART_DIRECTION.json")

    if story.get("surface") != "website":
        raise SiteGammaVisualReviewError("Gamma Site review requires the native website story surface")
    if story.get("semantic_law_hash") != law.get("semantic_law_hash"):
        raise SiteGammaVisualReviewError("website story is not bound to the current semantic law")
    if story.get("projection_hash") != projection.get("projection_hash"):
        raise SiteGammaVisualReviewError("website story is not bound to the current projection")
    if art.get("source_story_hash") != story.get("story_hash"):
        raise SiteGammaVisualReviewError("Document Studio art direction is not bound to the website story")

    scenes = list(art.get("scenes") or [])
    if len(scenes) < 3:
        raise SiteGammaVisualReviewError("Site art direction exposes too few scenes for Gamma review")
    if any(not str(scene.get("visual_subject") or "").strip() for scene in scenes):
        raise SiteGammaVisualReviewError("Site art direction contains an empty visual subject")

    blocks = []
    for scene in scenes:
        subject = " ".join(str(scene.get("visual_subject") or "").split())
        blocks.append(subject)

    direction = dict(story.get("creative_direction") or {})
    payload = {
        "schema": "dio.gamma.campaign_story_request.v1",
        "family_id": str(story.get("family_id") or "site:site_studio"),
        "surface": "website",
        "output_mode": VISUAL_PLATE_MODE,
        "intended_consumer": "document_studio_site_compositor",
        "title": "DIO Site Studio source-visual candidates",
        "story_hash": story["story_hash"],
        "semantic_law_hash": law["semantic_law_hash"],
        "projection_hash": projection["projection_hash"],
        "art_direction_hash": art["art_direction_hash"],
        "num_cards": len(scenes),
        "input_text": "\n\n---\n\n".join(blocks),
        "creative_direction": {
            "audience_archetype": direction.get("audience_archetype"),
            "tone": direction.get("tone") or [],
            "pacing": direction.get("pacing"),
            "visual_grammar": direction.get("visual_grammar"),
            "motion_grammar": direction.get("motion_grammar"),
            "surface": "website",
            "document_studio_art_language": art.get("art_language") or {},
            "scene_directions": scenes,
            "anti_patterns": art.get("anti_patterns") or [],
            "format_core_profile": art.get("format_core_profile"),
            "format_core_profile_hash": art.get("format_core_profile_hash"),
            "beast_visual_memory": art.get("beast_visual_memory") or {},
        },
        "visual_plate_contract": {
            "gamma_role": "source_visual_candidate_generator_only",
            "typography_authority": "REFUSE",
            "layout_authority": "REFUSE",
            "page_composition_authority": "REFUSE",
            "visible_text": "REFUSE",
            "headings": "REFUSE",
            "captions": "REFUSE",
            "logos_and_brand_marks": "REFUSE",
            "presentation_chrome": "REFUSE",
            "white_or_pale_slide_canvas": "REFUSE",
            "card_inside_card": "REFUSE",
            "full_bleed_visual_plate_requested": True,
            "document_studio_owns_visible_copy": True,
            "document_studio_owns_layout": True,
        },
        "semantic_guardrails": story.get("semantic_guardrails") or {},
        "output_dir": str(gamma_output_dir.resolve()),
        "release": {
            "state": "held",
            "visual_review_required": True,
            "operator_approval_required": True,
        },
        "visual_source_policy": {
            "canonical_site": "customer/FULL_GRADE_SITE",
            "gamma": "synthetic_source_visual_candidate_only",
            "automatic_selection": False,
            "human_visual_review_required": True,
            "pixel_text_free_verification": "HUMAN_REVIEW_REQUIRED",
        },
    }
    payload["request_hash"] = _fingerprint(payload)
    return payload


def validate_gamma_candidate(*, request: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    cards = list(receipt.get("cards") or [])
    contract = request.get("visual_plate_contract") or {}
    generated = receipt.get("generation_contract") or {}
    governance = receipt.get("governance") or {}
    checks = {
        "state_ready": receipt.get("state") == "ready",
        "request_hash_bound": receipt.get("request_hash") == request.get("request_hash"),
        "semantic_law_bound": receipt.get("semantic_law_hash") == request.get("semantic_law_hash"),
        "projection_bound": receipt.get("projection_hash") == request.get("projection_hash"),
        "art_direction_bound": receipt.get("art_direction_hash") == request.get("art_direction_hash"),
        "scene_count_exact": len(cards) == int(request.get("num_cards") or 0),
        "all_cards_exist": bool(cards) and all(Path(str(row.get("path") or "")).is_file() for row in cards),
        "all_cards_synthetic": bool(cards) and all(row.get("synthetic") is True for row in cards),
        "all_cards_require_review": bool(cards) and all(
            row.get("publication_status") == "visual_review_required" for row in cards
        ),
        "visual_plate_mode": request.get("output_mode") == VISUAL_PLATE_MODE,
        "document_studio_is_consumer": request.get("intended_consumer") == "document_studio_site_compositor",
        "typography_authority_refused": contract.get("typography_authority") == "REFUSE",
        "layout_authority_refused": contract.get("layout_authority") == "REFUSE",
        "visible_text_refused": contract.get("visible_text") == "REFUSE",
        "document_studio_owns_visible_copy": contract.get("document_studio_owns_visible_copy") is True,
        "document_studio_owns_layout": contract.get("document_studio_owns_layout") is True,
        "gamma_execution_visual_plate_mode": generated.get("output_mode") == VISUAL_PLATE_MODE,
        "gamma_text_mode_not_preserve": generated.get("text_mode") != "preserve",
        "gamma_theme_not_applied": generated.get("theme_applied") is False,
        "publication_held": governance.get("publication") == "held_for_operator_approval",
        "authority_not_created": governance.get("authority_created") is False,
        "optional_candidate_only": governance.get("optional_visual_candidate") is True,
    }
    passed = all(checks.values())
    return {
        "schema": "dio.site_studio.gamma_visual_candidate_qa.v2",
        "checks": checks,
        "passed": passed,
        "candidate_state": "READY_NEEDS_YOU" if passed else "REFUSE",
        "transport_and_request_policy_qa": "PASS" if passed else "REFUSE",
        "pixel_text_free_verified": False,
        "pixel_visual_quality": "HUMAN_REVIEW_REQUIRED",
        "human_visual_release": "NEEDS_YOU",
        "automatic_promotion": "REFUSE",
    }


def _inject_gamma_review_site(
    *, canonical_site: Path, review_site: Path, receipt: dict[str, Any], art: dict[str, Any]
) -> Path:
    if review_site.exists():
        shutil.rmtree(review_site)
    shutil.copytree(canonical_site, review_site)
    assets = review_site / "assets" / "gamma"
    assets.mkdir(parents=True, exist_ok=True)

    scenes = list(art.get("scenes") or [])
    copied: list[Path] = []
    for index, card in enumerate(receipt.get("cards") or [], 1):
        source = Path(str(card["path"])).resolve()
        target = assets / f"{index:02d}.png"
        shutil.copyfile(source, target)
        copied.append(target)

    index_path = review_site / "index.html"
    page = index_path.read_text(encoding="utf-8")
    banner = (
        '<div class="gamma-review-banner">GAMMA SOURCE-VISUAL CANDIDATES · '
        'TYPOGRAPHY & LAYOUT OWNED BY DIO · HUMAN VISUAL REVIEW REQUIRED · NOT PUBLISHED</div>'
    )
    page = page.replace("<body>", "<body>" + banner, 1)

    hero_alt = str((scenes[0] if scenes else {}).get("visual_subject") or "Synthetic source visual candidate")
    hero = (
        f'<figure class="gamma-hero-visual"><img src="assets/gamma/01.png" alt="{_escape_attr(hero_alt)}">'
        '<figcaption>Source visual 01 · Gamma synthetic candidate · DIO composition retained</figcaption></figure>'
    )
    page = page.replace("</header>", hero + "</header>", 1)

    scene_iter = iter(range(2, min(len(copied), 7) + 1))

    def repl(match: re.Match[str]) -> str:
        try:
            card_index = next(scene_iter)
        except StopIteration:
            return match.group(0)
        scene = scenes[card_index - 1] if card_index - 1 < len(scenes) else {}
        alt = _escape_attr(str(scene.get("visual_subject") or "Synthetic source visual candidate"))
        media = (
            f'<figure class="gamma-scene-visual"><img src="assets/gamma/{card_index:02d}.png" alt="{alt}">'
            f'<figcaption>Source visual {card_index:02d} · synthetic · human review required</figcaption></figure>'
        )
        return match.group(0) + media

    page = re.sub(r'(<section class="scene [^"]+">)', repl, page)

    if len(copied) >= 8:
        scene = scenes[7] if len(scenes) > 7 else {}
        alt = _escape_attr(str(scene.get("visual_subject") or "Synthetic CTA source visual candidate"))
        cta_media = (
            f'<figure class="gamma-cta-visual"><img src="assets/gamma/08.png" alt="{alt}">'
            '<figcaption>Source visual 08 · synthetic · human review required</figcaption></figure>'
        )
        page = page.replace('<section class="intake"', cta_media + '<section class="intake"', 1)

    index_path.write_text(page, encoding="utf-8")
    css_path = review_site / "styles.css"
    css = css_path.read_text(encoding="utf-8")
    css += """
.gamma-review-banner{position:sticky;top:0;z-index:99;padding:10px 18px;background:#eab464;color:#12191d;font:900 .68rem/1.2 ui-sans-serif,system-ui,sans-serif;letter-spacing:.12em;text-align:center}
.gamma-hero-visual,.gamma-scene-visual,.gamma-cta-visual{width:min(1180px,calc(100% - 40px));margin:36px auto 0;position:relative;overflow:hidden;border:1px solid #ffffff24;background:#0b1115}
.gamma-hero-visual{margin-top:54px}.gamma-scene-visual{margin-bottom:42px}.gamma-cta-visual{margin:70px auto}
.gamma-hero-visual img,.gamma-scene-visual img,.gamma-cta-visual img{display:block;width:100%;aspect-ratio:16/9;object-fit:cover}
.gamma-hero-visual figcaption,.gamma-scene-visual figcaption,.gamma-cta-visual figcaption{position:absolute;right:10px;bottom:10px;padding:7px 9px;background:#081014dd;color:#fff;font:800 .62rem/1.2 ui-sans-serif,system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase}
.split-band .gamma-scene-visual,.proof-band .gamma-scene-visual{border-color:#1113}
@media(max-width:820px){.gamma-hero-visual,.gamma-scene-visual,.gamma-cta-visual{width:min(100% - 24px,1180px);margin-top:24px}.gamma-hero-visual img,.gamma-scene-visual img,.gamma-cta-visual img{aspect-ratio:4/3}}
"""
    css_path.write_text(css, encoding="utf-8")
    return index_path


def _escape_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def run_site_gamma_visual_review(*, site_root: Path, generate: bool, root: Path = ROOT) -> dict[str, Any]:
    site_root = site_root.expanduser().resolve()
    canonical_site = site_root / "customer" / "FULL_GRADE_SITE"
    if not (canonical_site / "index.html").is_file():
        raise SiteGammaVisualReviewError(
            f"full-grade Site Studio artifact missing: {canonical_site / 'index.html'}"
        )

    proof = canonical_site / "proof"
    canonical_receipt = _load(site_root / "SITE_STUDIO_FULL_GRADE_RECEIPT.json")
    if canonical_receipt.get("full_grade_state") != "PASS":
        raise SiteGammaVisualReviewError("Gamma review requires an already-passed full-grade Site Studio run")

    gamma_root = site_root / "gamma_visual_candidate"
    request = build_site_gamma_request(site_root=site_root, gamma_output_dir=gamma_root / "generation")
    request_path = gamma_root / "GAMMA_SITE_VISUAL_REQUEST.json"
    _write_json(request_path, request)

    if not generate:
        return {
            "schema": "dio.site_studio.gamma_visual_review_receipt.v2",
            "state": "REQUEST_READY_NOT_GENERATED",
            "request": str(request_path),
            "gamma_external_call_executed": False,
            "gamma_output_mode": VISUAL_PLATE_MODE,
            "typography_authority": "REFUSE",
            "layout_authority": "REFUSE",
            "canonical_site_unchanged": True,
            "human_visual_release": "NEEDS_YOU",
            "publication": "REFUSE",
            "authority_created": False,
        }

    completed = subprocess.run(
        ["node", str(root / "scripts" / "run_gamma_art_directed_story.js"), str(request_path)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if completed.returncode != 0:
        raise SiteGammaVisualReviewError(
            "Gamma Site visual generation failed: "
            + (completed.stderr or completed.stdout or "unknown error")[-3000:]
        )

    receipt_path = gamma_root / "generation" / "GAMMA_STORY_RECEIPT.json"
    gamma_receipt = _load(receipt_path)
    qa = validate_gamma_candidate(request=request, receipt=gamma_receipt)
    _write_json(gamma_root / "GAMMA_SITE_VISUAL_QA.json", qa)
    if not qa["passed"]:
        raise SiteGammaVisualReviewError(
            "Gamma source-visual candidate QA refused: "
            + ", ".join(key for key, passed in qa["checks"].items() if not passed)
        )

    art = _load(proof / "DOCUMENT_STUDIO_SITE_ART_DIRECTION.json")
    review_site = site_root / "customer" / "GAMMA_REVIEW_SITE"
    review_entrypoint = _inject_gamma_review_site(
        canonical_site=canonical_site,
        review_site=review_site,
        receipt=gamma_receipt,
        art=art,
    )

    review_receipt = {
        "schema": "dio.site_studio.gamma_visual_review_receipt.v2",
        "state": "READY_NEEDS_YOU",
        "canonical_full_grade_fingerprint": canonical_receipt.get("full_grade_fingerprint"),
        "semantic_law_hash": request.get("semantic_law_hash"),
        "projection_hash": request.get("projection_hash"),
        "story_hash": request.get("story_hash"),
        "art_direction_hash": request.get("art_direction_hash"),
        "gamma_request_hash": request.get("request_hash"),
        "gamma_generation_id": gamma_receipt.get("generation_id"),
        "gamma_card_count": len(gamma_receipt.get("cards") or []),
        "gamma_output_mode": VISUAL_PLATE_MODE,
        "gamma_transport_and_request_policy_qa": "PASS",
        "pixel_text_free_verified": False,
        "pixel_visual_quality": "HUMAN_REVIEW_REQUIRED",
        "typography_authority": "REFUSE",
        "layout_authority": "REFUSE",
        "document_studio_composition_authority": "REQUIRED",
        "review_site": str(review_entrypoint.relative_to(site_root)),
        "canonical_site_unchanged": True,
        "automatic_selection": "REFUSE",
        "human_visual_release": "NEEDS_YOU",
        "publication": "REFUSE",
        "authority_created": False,
    }
    review_receipt["review_fingerprint"] = _fingerprint(review_receipt)
    _write_json(gamma_root / "GAMMA_SITE_VISUAL_REVIEW_RECEIPT.json", review_receipt)
    return review_receipt


__all__ = [
    "SiteGammaVisualReviewError",
    "VISUAL_PLATE_MODE",
    "build_site_gamma_request",
    "validate_gamma_candidate",
    "run_site_gamma_visual_review",
]
