from __future__ import annotations

import json
from pathlib import Path

from products.product_explainer_pipeline import (
    build_media_production_request,
    compile_product_explainer,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _install_homs_truth(root: Path) -> None:
    _write_json(
        root / "state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_RUNTIME.json",
        {
            "schema": "dio.meta_portfolio.runtime.v1",
            "incarnations": [
                {
                    "Incarnation": "HOMS Assess",
                    "Suite": "HOMS",
                    "Description": "Governed assessment production and review workflows",
                    "Problem": "Assessment production and review are fragmented across source material and manual steps.",
                    "Capabilities": [
                        "bind curriculum and assessment inputs",
                        "generate reviewable assessment drafts",
                        "preserve human approval before final use",
                    ],
                    "Outputs": ["assessment paper", "memorandum", "rubric"],
                    "Differentiators": [
                        "source-bound assessment generation",
                        "explicit human review authority",
                    ],
                }
            ],
        },
    )


def _install_media_profiles(root: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    for name in ("media_style_profiles.json", "product_media_profiles.json"):
        (config_dir / name).write_text(
            (repo_root / "config" / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    master = root / "media/golden_references/dio_launch_cinematic_v1/master/DIO_LAUNCH_TRAILER_MASTER_V1.mp4"
    wordmark = root / "media/golden_references/dio_launch_cinematic_v1/brand/dio-wordmark.svg"
    sigil = root / "media/golden_references/dio_launch_cinematic_v1/brand/dio-sigil.webp"
    master.parent.mkdir(parents=True, exist_ok=True)
    wordmark.parent.mkdir(parents=True, exist_ok=True)
    master.write_bytes(b"test-golden-master")
    wordmark.write_text("<svg/>", encoding="utf-8")
    sigil.write_bytes(b"test-sigil")


def test_media_request_carries_resolved_brand_and_product_score(tmp_path: Path) -> None:
    _install_homs_truth(tmp_path)
    _install_media_profiles(tmp_path)

    compiled = compile_product_explainer("homs", root=tmp_path)
    request = build_media_production_request(compiled, root=tmp_path)

    assert request["brand_render_brief"]["profile_id"] == "DIO_CINEMATIC_BRAND_V1"
    assert request["brand_render_brief"]["product_id"] == "HOMS"
    assert "black glass" in request["brand_render_brief"]["visual_direction"].lower()
    assert request["product_media_profile"]["id"] == "HOMS"
    assert request["product_media_profile"]["sha256"].startswith("sha256:")
    assert request["sound"]["music_origin"] == "dio_product_score"
    assert request["sound"]["sonic_identity"] == "DIO_SONIC_IDENTITY_V1"
    assert request["sound"]["music_direction"]["variant"] == "institutional_glass"
    assert request["release"] == {
        "local_render": "ALLOW",
        "external_publication": "NEEDS_YOU",
        "media_spend": "REFUSE",
    }
