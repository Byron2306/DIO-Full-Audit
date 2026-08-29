from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .product_explainer_compiler import (
    ROOT,
    ProductExplainerError,
    _as_string_list,
    _dedupe,
    _fingerprint,
    _relative_path,
    load_media_style_profile,
    resolve_product_truth,
)
from .product_explainer_branding import (
    compile_brand_render_brief,
    load_product_media_profile,
)
from .product_visual_asset_pack import load_visual_asset_pack

REQUIRED_EXPLANATION_FIELDS = (
    "what_it_is",
    "problem",
    "how_it_works",
    "why_different",
    "buyer_result",
)

_FORBIDDEN_CERTAINTY = ("guarantee", "guaranteed", "certify", "always", "eliminate")
_MARKET_CONTEXT_ALLOWLIST = {"emphasis", "audience_id", "channel", "objective", "duration_seconds"}


def _row_values(rows: list[dict[str, Any]], *keys: str) -> list[str]:
    values: list[str] = []
    for row in rows:
        for key in keys:
            values.extend(_as_string_list(row.get(key)))
    return _dedupe(values)


def _sentence_join(values: list[str]) -> str:
    clean = [value.strip().rstrip(".") for value in values if value and value.strip()]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0] + "."
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}."
    return ", ".join(clean[:-1]) + f", and {clean[-1]}."


def _contains_forbidden_certainty(text: str) -> bool:
    lowered = str(text or "").casefold()
    return any(term in lowered for term in _FORBIDDEN_CERTAINTY)


def build_claim_envelope(truth: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    canonical_sources = [
        row["path"]
        for row in truth.get("source_bindings") or []
        if row.get("role") == "canonical_product_identity"
    ]
    proof_sources = [
        row["path"]
        for row in truth.get("source_bindings") or []
        if row.get("role") == "proof_asset"
    ]
    allowed: list[dict[str, Any]] = []
    qualified: list[dict[str, Any]] = []
    forbidden: list[dict[str, Any]] = []

    description = str(truth.get("description") or "").strip()
    if description:
        allowed.append(
            {
                "text": f"{truth.get('canonical_name')}: {description}",
                "class": "DESCRIPTIVE",
                "source_paths": canonical_sources,
                "reason": "canonical product definition",
            }
        )

    for capability in truth.get("capabilities") or []:
        allowed.append(
            {
                "text": str(capability),
                "class": "DESCRIPTIVE",
                "source_paths": canonical_sources,
                "reason": "canonical capability",
            }
        )
    for output in truth.get("outputs") or []:
        allowed.append(
            {
                "text": str(output),
                "class": "DESCRIPTIVE",
                "source_paths": canonical_sources,
                "reason": "canonical output",
            }
        )

    explicit_claims = _row_values(truth.get("portfolio_rows") or [], "Claims", "claims")
    for claim in explicit_claims:
        target = forbidden if _contains_forbidden_certainty(claim) else allowed
        target.append(
            {
                "text": claim,
                "class": "FORBIDDEN" if target is forbidden else ("SUPPORTED" if proof_sources else "DESCRIPTIVE"),
                "source_paths": [*canonical_sources, *proof_sources],
                "reason": "explicit canonical claim" if target is allowed else "unsupported certainty requires explicit evidence classification",
            }
        )

    for problem in _row_values(truth.get("portfolio_rows") or [], "Problem", "problem", "Problems", "problems"):
        allowed.append(
            {
                "text": problem,
                "class": "DESCRIPTIVE",
                "source_paths": canonical_sources,
                "reason": "canonical problem definition",
            }
        )
    for differentiator in _row_values(
        truth.get("portfolio_rows") or [],
        "Differentiators",
        "differentiators",
        "Why Different",
        "why_different",
    ):
        allowed.append(
            {
                "text": differentiator,
                "class": "DESCRIPTIVE",
                "source_paths": canonical_sources,
                "reason": "canonical differentiator",
            }
        )

    for observation in truth.get("audience_observations") or []:
        outcome = str(observation.get("outcome") or "").strip()
        if not outcome:
            continue
        target = forbidden if _contains_forbidden_certainty(outcome) else qualified
        target.append(
            {
                "text": outcome,
                "class": "FORBIDDEN" if target is forbidden else "QUALIFIED",
                "source_paths": [
                    row["path"]
                    for row in truth.get("source_bindings") or []
                    if row.get("role") == "marketing_supplement"
                ],
                "reason": (
                    "marketing outcome contains certainty beyond bound outcome evidence"
                    if target is forbidden
                    else "marketing outcome observation is not direct outcome proof"
                ),
            }
        )

    for bucket_name, rows in (("allowed", allowed), ("qualified", qualified), ("forbidden", forbidden)):
        for row in rows:
            raw = f"{bucket_name}|{row.get('class')}|{row.get('text')}".encode("utf-8")
            row["claim_id"] = "CLM-" + hashlib.sha256(raw).hexdigest()[:12].upper()

    return {"allowed": allowed, "qualified": qualified, "forbidden": forbidden}


def _build_explanation(truth: dict[str, Any]) -> dict[str, str]:
    rows = truth.get("portfolio_rows") or []
    canonical_problem = _row_values(rows, "Problem", "problem", "Problems", "problems")
    differentiators = _row_values(rows, "Differentiators", "differentiators", "Why Different", "why_different")
    observed_pains = _dedupe(
        [str(row.get("pain") or "").strip() for row in truth.get("audience_observations") or [] if row.get("pain")]
    )

    description = str(truth.get("description") or "").strip()
    what_it_is = f"{truth.get('canonical_name')} is {description.rstrip('.').lower()}." if description else ""
    problem_values = canonical_problem or observed_pains
    problem = _sentence_join(problem_values)
    if problem and not canonical_problem:
        problem = "Observed audience pain: " + problem[0].lower() + problem[1:]

    capabilities = [str(value) for value in truth.get("capabilities") or []]
    how_it_works = "It works by " + _sentence_join(capabilities)[0].lower() + _sentence_join(capabilities)[1:] if capabilities else ""

    why_different = "Its distinguishing design is " + _sentence_join(differentiators)[0].lower() + _sentence_join(differentiators)[1:] if differentiators else ""

    outputs = [str(value) for value in truth.get("outputs") or []]
    buyer_result = "Users receive " + _sentence_join(outputs)[0].lower() + _sentence_join(outputs)[1:] if outputs else ""

    return {
        "what_it_is": what_it_is,
        "problem": problem,
        "how_it_works": how_it_works,
        "why_different": why_different,
        "buyer_result": buyer_result,
    }


def _safe_market_context(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    return {
        key: json.loads(json.dumps(item))
        for key, item in value.items()
        if key in _MARKET_CONTEXT_ALLOWLIST
    }


def compile_product_explainer(
    product_id: str,
    *,
    root: Path = ROOT,
    output_dir: Path | None = None,
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(root)
    truth = resolve_product_truth(product_id, root=root)
    explanation = _build_explanation(truth)
    missing = [field for field in REQUIRED_EXPLANATION_FIELDS if not explanation.get(field)]
    envelope = build_claim_envelope(truth)

    if missing:
        return {
            "semantic_readiness": "NEEDS_EVIDENCE",
            "missing": missing,
            "truth": truth,
            "claim_envelope": envelope,
            "manifest": None,
            "manifest_path": None,
            "manifest_sha256": None,
        }

    source_binding = {
        "sources": truth["source_bindings"],
        "fingerprint": _fingerprint(truth["source_bindings"]),
    }
    manifest: dict[str, Any] = {
        "schema": "dio.product_explainer.v1",
        "product_id": truth["product_id"],
        "product_name": truth["canonical_name"],
        "source_binding": source_binding,
        "explanation": explanation,
        "outputs": list(truth.get("outputs") or []),
        "proof_points": [row for row in truth.get("proof_assets") or [] if row.get("exists")],
        "claims": envelope,
        "canonical_story": [
            "problem",
            "product_definition",
            "mechanism",
            "proof",
            "differentiation",
            "result",
            "call_to_action",
        ],
        "target_seconds": 55,
        "market_context": _safe_market_context(market_context),
        "authority": {
            "semantic_truth_source": "product_registry",
            "market_may_change_product_truth": False,
            "human_release_required": True,
            "external_publication": "NEEDS_YOU",
            "media_spend": "REFUSE",
        },
    }

    destination = Path(output_dir) if output_dir is not None else root / "state" / "product_explainers" / truth["product_id"]
    destination.mkdir(parents=True, exist_ok=True)
    manifest_path = destination / "PRODUCT_EXPLAINER_MANIFEST.json"
    serialized = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    manifest_path.write_text(serialized, encoding="utf-8")
    manifest_sha256 = "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    return {
        "semantic_readiness": "READY",
        "missing": [],
        "truth": truth,
        "claim_envelope": envelope,
        "manifest": manifest,
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha256,
    }

ASSET_PREFERENCE = [
    "real_product_output",
    "real_product_ui",
    "real_evidence_or_diagram",
    "dio_generated_explanatory_diagram",
    "generated_cinematic_metaphor",
]


def build_media_production_request(
    explainer_result: dict[str, Any],
    *,
    root: Path = ROOT,
    style_profile_id: str = "DIO_CINEMATIC_BRAND_V1",
) -> dict[str, Any]:
    if explainer_result.get("semantic_readiness") != "READY" or not explainer_result.get("manifest"):
        raise ProductExplainerError(
            "EXPLAINER_SEMANTIC_READINESS_NEEDS_EVIDENCE",
            "media production requires a semantically ready product explainer",
            {"missing": explainer_result.get("missing") or []},
        )
    root = Path(root)
    profile, profile_sha = load_media_style_profile(style_profile_id, root=root, require_assets=True)
    manifest = explainer_result["manifest"]
    product_profile, product_profile_sha = load_product_media_profile(
        str(manifest["product_id"]),
        root=root,
    )
    brand_render_brief = compile_brand_render_brief(
        profile,
        product_profile,
        product_id=str(manifest["product_id"]),
    )

    visual_asset_pack_binding: dict[str, str] | None = None
    visual_asset_profile = product_profile.get("visual_asset_pack") or {}
    if visual_asset_profile:
        if not isinstance(visual_asset_profile, dict):
            raise ProductExplainerError(
                "VISUAL_ASSET_PACK_INVALID",
                "product media visual asset pack binding must be an object",
            )
        pack_id = str(visual_asset_profile.get("pack_id") or "").strip().upper()
        if not pack_id or visual_asset_profile.get("fallback") != "REFUSE":
            raise ProductExplainerError(
                "VISUAL_ASSET_PACK_INVALID",
                "product media visual asset pack binding is incomplete",
            )
        pack, pack_sha = load_visual_asset_pack(pack_id, root=root)
        if str(pack.get("product_id") or "").strip().upper() != str(manifest["product_id"]).strip().upper():
            raise ProductExplainerError(
                "VISUAL_ASSET_PACK_INVALID",
                "visual asset pack product id does not match explainer product",
            )
        visual_asset_pack_binding = {
            "id": str(pack["pack_id"]),
            "sha256": pack_sha,
            "fallback": "REFUSE",
        }

    manifest_path = Path(str(explainer_result["manifest_path"]))
    manifest_ref = _relative_path(manifest_path, root) if manifest_path.is_absolute() else str(manifest_path)
    seed = {
        "product_id": manifest["product_id"],
        "explainer_sha256": explainer_result["manifest_sha256"],
        "style_profile_sha256": profile_sha,
        "product_media_profile_sha256": product_profile_sha,
    }
    if visual_asset_pack_binding is not None:
        seed["visual_asset_pack_sha256"] = visual_asset_pack_binding["sha256"]
    request_id = "MPR-" + _fingerprint(seed).split(":", 1)[1][:12].upper()
    voice = profile.get("voice") or {}
    request: dict[str, Any] = {
        "schema": "dio.media.production_request.v2",
        "request_id": request_id,
        "product_id": manifest["product_id"],
        "explainer_manifest": {
            "path": manifest_ref,
            "sha256": explainer_result["manifest_sha256"],
        },
        "style_profile": {"id": style_profile_id, "sha256": profile_sha},
        "product_media_profile": {
            "id": str(product_profile.get("profile_id") or manifest["product_id"]).upper(),
            "sha256": product_profile_sha,
        },
        "brand_render_brief": brand_render_brief,
        "production": {
            "kind": "canonical_product_explainer",
            "target_seconds": int(manifest.get("target_seconds") or 55),
            "aspect_ratio": "16:9",
            "resolution": "1920x1080",
            "voice_required": True,
            "captions": True,
        },
        "voice": {
            "role": voice.get("role"),
            "profile": voice.get("profile"),
            "render_mode": voice.get("render_mode"),
            "pronunciation": dict(voice.get("pronunciation") or {}),
        },
        "sound": {
            "music_origin": "dio_product_score",
            "sonic_identity": brand_render_brief["music_direction"]["inherits"],
            "music_direction": brand_render_brief["music_direction"],
            "score_recipe": dict((product_profile.get("score") or {}).get("recipe") or {}),
            "source_path": (product_profile.get("score") or {}).get("source_path"),
        },
        "assets": {
            "proof_assets": list(manifest.get("proof_points") or []),
            "product_screens": [],
            "generated_visuals": [],
        },
        "release": {
            "local_render": "ALLOW",
            "external_publication": "NEEDS_YOU",
            "media_spend": "REFUSE",
        },
    }
    if visual_asset_pack_binding is not None:
        request["visual_asset_pack"] = visual_asset_pack_binding
    return request


def _manifest_source_ids(manifest: dict[str, Any]) -> list[str]:
    return [
        str(row.get("path"))
        for row in ((manifest.get("source_binding") or {}).get("sources") or [])
        if row.get("path")
    ]


def _claims_by_reason(manifest: dict[str, Any], *reasons: str) -> list[str]:
    wanted = set(reasons)
    return [
        str(row.get("claim_id"))
        for row in ((manifest.get("claims") or {}).get("allowed") or [])
        if row.get("claim_id") and row.get("reason") in wanted
    ]


def build_explainer_script_package(manifest: dict[str, Any]) -> dict[str, Any]:
    explanation = manifest.get("explanation") or {}
    product_name = str(manifest.get("product_name") or manifest.get("product_id") or "Product")
    sources = _manifest_source_ids(manifest)
    proof_points = manifest.get("proof_points") or []
    outputs = [str(value) for value in manifest.get("outputs") or []]
    proof_narration = (
        "A bound proof package preserves reviewable evidence for the product's current outputs."
        if proof_points
        else "The explainer has no bound proof asset and must not imply observed proof."
    )
    proof_anchor = "BOUND PRODUCT EVIDENCE" if proof_points else "PROOF REQUIRED"
    definitions = [
        (
            "problem",
            "The problem",
            str(explanation.get("problem") or ""),
            "THE WORK IS FRAGMENTED",
            7,
            _claims_by_reason(manifest, "canonical problem definition"),
        ),
        (
            "product_definition",
            f"What {product_name} is",
            str(explanation.get("what_it_is") or ""),
            f"{product_name.upper()} • PRODUCT DEFINITION",
            7,
            _claims_by_reason(manifest, "canonical product definition"),
        ),
        (
            "mechanism",
            "How it works",
            str(explanation.get("how_it_works") or ""),
            "INPUT → GOVERNED WORK → REVIEWABLE OUTPUT",
            11,
            _claims_by_reason(manifest, "canonical capability"),
        ),
        (
            "proof",
            "Show the product",
            proof_narration,
            proof_anchor,
            11,
            _claims_by_reason(manifest, "canonical output"),
        ),
        (
            "differentiation",
            "Why it is different",
            str(explanation.get("why_different") or ""),
            "SOURCE-BOUND • REVIEWABLE • GOVERNED",
            9,
            _claims_by_reason(manifest, "canonical differentiator"),
        ),
        (
            "result",
            "What the user gets",
            str(explanation.get("buyer_result") or ""),
            " → ".join(outputs[:3]).upper() if outputs else "REVIEWABLE OUTPUT",
            7,
            _claims_by_reason(manifest, "canonical output"),
        ),
        (
            "call_to_action",
            "Next action",
            f"See how {product_name} fits your workflow.",
            f"EXPLORE {product_name.upper()}",
            3,
            [],
        ),
    ]
    scenes = []
    for index, (beat, title, narration, anchor, duration, claim_ids) in enumerate(definitions, 1):
        scenes.append(
            {
                "scene_id": f"scene_{index:02d}_{beat}",
                "story_beat": beat,
                "title": title,
                "narration": narration,
                "screen_anchor": anchor,
                "target_duration_seconds": duration,
                "claim_ids": claim_ids,
                "source_ids": sources if beat != "call_to_action" else [],
                "asset_preference": list(ASSET_PREFERENCE),
                "asset_provenance": "unresolved",
                "asset_representation": "planned",
            }
        )
    return {
        "schema": "dio.product_explainer.script_package.v1",
        "product_id": manifest.get("product_id"),
        "title": product_name,
        "target_seconds": sum(scene["target_duration_seconds"] for scene in scenes),
        "story_grammar": list(manifest.get("canonical_story") or []),
        "scenes": scenes,
    }


def semantic_challenge(
    manifest: dict[str, Any],
    script_package: dict[str, Any],
) -> dict[str, Any]:
    codes: list[str] = []
    findings: list[dict[str, Any]] = []
    allowed_claims = [str(row.get("text") or "") for row in ((manifest.get("claims") or {}).get("allowed") or [])]
    allowed_certainty = {
        term
        for term in _FORBIDDEN_CERTAINTY
        if any(term in claim.casefold() for claim in allowed_claims)
    }
    unsupported_cta_markers = (
        "available now",
        "buy now",
        "certified",
        "customers",
        "guaranteed",
        "$",
        "€",
        "£",
    )
    for scene in script_package.get("scenes") or []:
        narration = str(scene.get("narration") or "")
        anchor = str(scene.get("screen_anchor") or "")
        combined = f"{narration} {anchor}".casefold()
        certainty = [
            term
            for term in _FORBIDDEN_CERTAINTY
            if term in combined and term not in allowed_certainty
        ]
        if certainty:
            if "CLAIM_EXCEEDS_EVIDENCE" not in codes:
                codes.append("CLAIM_EXCEEDS_EVIDENCE")
            findings.append(
                {
                    "scene_id": scene.get("scene_id"),
                    "code": "CLAIM_EXCEEDS_EVIDENCE",
                    "terms": certainty,
                }
            )
        if (
            scene.get("asset_provenance") == "generated"
            and scene.get("asset_representation") == "evidence"
        ):
            if "GENERATED_ASSET_MISREPRESENTED_AS_EVIDENCE" not in codes:
                codes.append("GENERATED_ASSET_MISREPRESENTED_AS_EVIDENCE")
            findings.append(
                {
                    "scene_id": scene.get("scene_id"),
                    "code": "GENERATED_ASSET_MISREPRESENTED_AS_EVIDENCE",
                }
            )
        if scene.get("story_beat") == "call_to_action":
            bad_markers = [marker for marker in unsupported_cta_markers if marker in combined]
            if bad_markers:
                if "CTA_EXCEEDS_COMMERCIAL_TRUTH" not in codes:
                    codes.append("CTA_EXCEEDS_COMMERCIAL_TRUTH")
                findings.append(
                    {
                        "scene_id": scene.get("scene_id"),
                        "code": "CTA_EXCEEDS_COMMERCIAL_TRUTH",
                        "markers": bad_markers,
                    }
                )
    return {
        "schema": "dio.product_explainer.semantic_challenge.v1",
        "state": "PASS" if not codes else "REFUSE",
        "codes": codes,
        "findings": findings,
        "market_may_change_product_truth": False,
        "automated_publication_authority_created": False,
    }
