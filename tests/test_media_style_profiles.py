from pathlib import Path
import json
import pytest

from products.product_explainer_compiler import ProductExplainerError, load_media_style_profile

ROOT = Path(__file__).resolve().parents[1]


def test_dio_cinematic_brand_profile_is_release_safe():
    profile, digest = load_media_style_profile(
        "DIO_CINEMATIC_BRAND_V1", root=ROOT, require_assets=False
    )
    assert digest.startswith("sha256:")
    assert profile["voice"]["profile"] == "vera_pocket_public"
    assert profile["release"]["automatic_local_render"] is True
    assert profile["release"]["automatic_external_publication"] is False
    assert profile["release"]["automatic_media_spend"] is False
    assert profile["typography"]["silent_font_fallback"] is False


def test_missing_required_brand_asset_fails_closed(tmp_path: Path):
    config = {
        "schema": "dio.media.style_profile_registry.v1",
        "profiles": {
            "BROKEN": {
                "schema": "dio.media.style_profile.v1",
                "profile_id": "BROKEN",
                "golden_reference": {"master": "missing/master.mp4", "sha256": "sha256:x"},
                "visual": {"palette": {"black": "#050607", "gold": "#d9b66f"}},
                "typography": {
                    "brand_face": "Noto Serif Display",
                    "body_face": "Noto Serif",
                    "technical_face": "DejaVu Sans",
                    "wordmark": "missing/dio-wordmark.svg",
                    "sigil": "missing/dio-sigil.webp",
                    "silent_font_fallback": False
                },
                "voice": {"role": "vesper_public", "profile": "vera_pocket_public"},
                "sound": {"sonic_identity": "DIO_SONIC_IDENTITY_V1"},
                "release": {
                    "automatic_local_render": True,
                    "automatic_external_publication": False,
                    "automatic_media_spend": False
                }
            }
        }
    }
    path = tmp_path / "config" / "media_style_profiles.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(config))
    with pytest.raises(ProductExplainerError) as exc:
        load_media_style_profile("BROKEN", root=tmp_path, require_assets=True)
    assert exc.value.code == "STYLE_ASSET_MISSING"


def test_runtime_profile_binds_actual_golden_master_hash(tmp_path: Path):
    import hashlib

    master = tmp_path / "media/master.mp4"
    wordmark = tmp_path / "media/dio-wordmark.svg"
    sigil = tmp_path / "media/dio-sigil.webp"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"golden-master")
    wordmark.write_text("<svg/>")
    sigil.write_bytes(b"sigil")
    config = {
        "schema": "dio.media.style_profile_registry.v1",
        "profiles": {
            "TEST": {
                "schema": "dio.media.style_profile.v1",
                "profile_id": "TEST",
                "golden_reference": {"master": "media/master.mp4", "sha256": "BOUND_AT_RUNTIME"},
                "visual": {"palette": {"black": "#050607", "gold": "#d9b66f"}},
                "typography": {
                    "brand_face": "Noto Serif Display",
                    "body_face": "Noto Serif",
                    "technical_face": "DejaVu Sans",
                    "wordmark": "media/dio-wordmark.svg",
                    "sigil": "media/dio-sigil.webp",
                    "silent_font_fallback": False
                },
                "voice": {"role": "vesper_public", "profile": "vera_pocket_public"},
                "sound": {"sonic_identity": "DIO_SONIC_IDENTITY_V1"},
                "release": {
                    "automatic_local_render": True,
                    "automatic_external_publication": False,
                    "automatic_media_spend": False
                }
            }
        }
    }
    path = tmp_path / "config/media_style_profiles.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(config))

    profile, _ = load_media_style_profile("TEST", root=tmp_path, require_assets=True)

    assert profile["golden_reference"]["sha256"] == "sha256:" + hashlib.sha256(b"golden-master").hexdigest()
