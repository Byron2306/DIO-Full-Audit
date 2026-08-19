from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "dashboard" / "production_semantic.js"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_custom_reel_uses_source_bound_semantic_evidence_fallback() -> None:
    source = _source()
    assert "SEMANTIC_BOUNDARY_ASSET = 'config/atlas/dio_meta_incarnation_crosswalk.csv'" in source
    assert "proof_asset: explicitProof || semanticProof || SEMANTIC_BOUNDARY_ASSET" in source
    assert "portfolio evidence boundary" in source


def test_product_presence_does_not_fallback_to_shared_catalogue() -> None:
    source = _source()
    assert "https://dioworkflows.co.za/products/" not in source
    assert "Shared catalogue fallback intentionally disabled" in source


def test_exact_standalone_product_sites_are_registered() -> None:
    source = _source()
    expected = {
        "HOMS Assess": "https://byron2306.github.io/HOMS-page/",
        "Sophia Review": "https://byron2306.github.io/Sophia-AI-page/",
        "VAMP Performance": "https://byron2306.github.io/VAMP-site/",
        "Evidex EvidenceOps": "https://byron2306.github.io/Evidex-page/",
        "Market Radar": "https://byron2306.github.io/NicheFoundry/",
    }
    for incarnation, url in expected.items():
        assert f"'{incarnation}':'{url}'" in source


def test_local_exact_surfaces_remain_available() -> None:
    source = _source()
    assert "'Document Studio Edit':'/sites/document-studio/'" in source
    assert "'Vesper Desk':VESPER_PRESENCE" in source
