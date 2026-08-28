from pathlib import Path
import json
import pytest

from products.product_explainer_compiler import ProductExplainerError, resolve_product_truth


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_resolver_uses_portfolio_for_identity_and_marketing_only_as_supplement(tmp_path: Path):
    portfolio = _write_json(
        tmp_path / "state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_RUNTIME.json",
        {
            "schema": "dio.meta_portfolio.runtime.v1",
            "incarnations": [
                {
                    "Incarnation": "HOMS Assess",
                    "Suite": "HOMS",
                    "Description": "Governed assessment production and review workflows",
                    "Capabilities": ["assessment generation", "rubric-bound review"],
                    "Outputs": ["assessment paper", "memorandum", "rubric"],
                }
            ],
        },
    )
    marketing = _write_json(
        tmp_path / "state/marketing_factory/CREATIVE_FAMILY_REGISTRY.json",
        {
            "schema": "dio.marketing.creative_family_registry.v1",
            "families": [
                {
                    "product": {"id": "HOMS_ASSESS", "name": "HOMS Assessment Desk"},
                    "audience": {
                        "pain": "Assessment preparation is repetitive.",
                        "outcome": "Reviewable assessment outputs.",
                    },
                    "proof_asset": "proof/homs.md",
                }
            ],
        },
    )
    proof = tmp_path / "proof/homs.md"
    proof.parent.mkdir(parents=True)
    proof.write_text("controlled HOMS proof", encoding="utf-8")

    truth = resolve_product_truth("homs", root=tmp_path)

    assert truth["canonical_name"] == "HOMS"
    assert truth["identity_source"].endswith("DIO_META_PORTFOLIO_ATLAS_RUNTIME.json")
    assert truth["identity_sha256"].startswith("sha256:")
    assert truth["capabilities"] == ["assessment generation", "rubric-bound review"]
    assert truth["outputs"] == ["assessment paper", "memorandum", "rubric"]
    assert truth["audience_observations"][0]["pain"] == "Assessment preparation is repetitive."
    assert truth["proof_assets"][0]["path"] == "proof/homs.md"
    assert {row["role"] for row in truth["source_bindings"]} == {
        "canonical_product_identity",
        "marketing_supplement",
        "proof_asset",
    }
    assert portfolio.is_file() and marketing.is_file()


def test_conflicting_canonical_sources_refuse(tmp_path: Path):
    base = tmp_path / "state/product_portfolio"
    _write_json(
        base / "DIO_META_PORTFOLIO_ATLAS_RUNTIME.json",
        {
            "incarnations": [
                {
                    "Incarnation": "HOMS Assess",
                    "Suite": "HOMS",
                    "Description": "Governed assessment production",
                }
            ]
        },
    )
    _write_json(
        base / "DIO_META_PORTFOLIO_ATLAS.json",
        {
            "incarnations": [
                {
                    "Incarnation": "HOMS Assess",
                    "Suite": "HOMS",
                    "Description": "Unrelated contradictory definition",
                }
            ]
        },
    )

    with pytest.raises(ProductExplainerError) as exc:
        resolve_product_truth("homs", root=tmp_path)

    assert exc.value.code == "PRODUCT_IDENTITY_AMBIGUOUS"
    assert len(exc.value.details["sources"]) == 2


def test_unknown_product_refuses_instead_of_using_marketing_copy(tmp_path: Path):
    _write_json(
        tmp_path / "state/marketing_factory/CREATIVE_FAMILY_REGISTRY.json",
        {
            "schema": "dio.marketing.creative_family_registry.v1",
            "families": [
                {
                    "product": {"id": "MYSTERY", "name": "Mystery AI"},
                    "audience": {"pain": "Everything hurts.", "outcome": "Everything fixed."},
                }
            ],
        },
    )

    with pytest.raises(ProductExplainerError) as exc:
        resolve_product_truth("mystery", root=tmp_path)

    assert exc.value.code == "PRODUCT_IDENTITY_UNRESOLVED"
