from __future__ import annotations

from pathlib import Path

from products.product_explainer_branding import (
    compile_brand_render_brief,
    load_product_media_profile,
)
from products.product_explainer_compiler import ROOT, load_media_style_profile


def test_homs_media_profile_compiles_dio_cinematic_brand() -> None:
    style, style_sha = load_media_style_profile(
        "DIO_CINEMATIC_BRAND_V1",
        root=ROOT,
        require_assets=False,
    )
    product, product_sha = load_product_media_profile("homs", root=ROOT)

    brief = compile_brand_render_brief(
        style,
        product,
        product_id="HOMS",
    )

    assert style_sha.startswith("sha256:")
    assert product_sha.startswith("sha256:")
    assert brief["profile_id"] == "DIO_CINEMATIC_BRAND_V1"
    assert brief["product_id"] == "HOMS"
    assert "black glass" in brief["visual_direction"].lower()
    assert "obsidian" in brief["visual_direction"].lower()
    assert "generic blue ai glow" in [
        value.lower() for value in brief["forbidden_motifs"]
    ]
    assert brief["scene_grammar"]["proof"]["visual_mode"] == "proof"
    assert brief["scene_grammar"]["mechanism"]["visual_mode"] == "hybrid"
    assert brief["scene_grammar"]["call_to_action"]["visual_mode"] == "brand_end_card"
    assert brief["music_direction"]["inherits"] == "DIO_SONIC_IDENTITY_V1"
    assert brief["music_direction"]["variant"] == "institutional_glass"


def test_homs_media_profile_is_representation_only() -> None:
    product, _ = load_product_media_profile("HOMS", root=ROOT)

    forbidden_authority_keys = {
        "claims",
        "claim_envelope",
        "capabilities",
        "outputs",
        "product_truth",
        "semantic_truth",
        "publication_authority",
        "media_spend_authority",
    }

    assert forbidden_authority_keys.isdisjoint(product)
    assert set(product["scene_grammar"]) == {
        "problem",
        "product_definition",
        "mechanism",
        "proof",
        "differentiation",
        "result",
        "call_to_action",
    }
