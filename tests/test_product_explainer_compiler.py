from pathlib import Path
import json
import pytest

from products.product_explainer_compiler import (
    ProductExplainerError,
    build_claim_envelope,
    build_explainer_script_package,
    build_media_production_request,
    compile_product_explainer,
    resolve_product_truth,
    semantic_challenge,
)


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


def build_minimal_portfolio_fixture(tmp_path: Path, description: str = "") -> Path:
    _write_json(
        tmp_path / "state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_RUNTIME.json",
        {
            "schema": "dio.meta_portfolio.runtime.v1",
            "incarnations": [
                {
                    "Incarnation": "HOMS Assess",
                    "Suite": "HOMS",
                    "Description": description,
                    "Capabilities": [],
                    "Outputs": [],
                }
            ],
        },
    )
    return tmp_path


def build_complete_homs_fixture(tmp_path: Path) -> Path:
    _write_json(
        tmp_path / "state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_RUNTIME.json",
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
    _write_json(
        tmp_path / "state/marketing_factory/CREATIVE_FAMILY_REGISTRY.json",
        {
            "schema": "dio.marketing.creative_family_registry.v1",
            "families": [
                {
                    "family_id": "HOMS_ASSESS--teachers_lecturers",
                    "product": {"id": "HOMS_ASSESS", "name": "HOMS Assessment Desk"},
                    "audience": {
                        "id": "teachers_lecturers",
                        "name": "Teachers and lecturers",
                        "pain": "Marking, feedback and paper preparation consume evenings and weekends.",
                        "outcome": "Structured drafts and learner feedback ready for educator review.",
                    },
                    "proof_asset": "proof/homs.md",
                }
            ],
        },
    )
    proof = tmp_path / "proof/homs.md"
    proof.parent.mkdir(parents=True)
    proof.write_text("HOMS controlled assessment production proof", encoding="utf-8")
    return tmp_path


def test_missing_required_truth_returns_needs_evidence(tmp_path: Path):
    root = build_minimal_portfolio_fixture(tmp_path, description="")
    result = compile_product_explainer("homs", root=root)
    assert result["semantic_readiness"] == "NEEDS_EVIDENCE"
    assert "what_it_is" in result["missing"]
    assert "how_it_works" in result["missing"]
    assert "buyer_result" in result["missing"]
    assert result["manifest_path"] is None


def test_market_context_cannot_mutate_product_definition(tmp_path: Path):
    root = build_complete_homs_fixture(tmp_path)
    baseline = compile_product_explainer("homs", root=root)
    marketed = compile_product_explainer(
        "homs",
        root=root,
        market_context={
            "emphasis": ["speed"],
            "audience_id": "teachers_lecturers",
            "product_definition": "guaranteed automatic compliance",
            "claims": ["guaranteed results"],
        },
    )
    assert marketed["semantic_readiness"] == "READY"
    assert marketed["manifest"]["explanation"]["what_it_is"] == baseline["manifest"]["explanation"]["what_it_is"]
    assert marketed["manifest"]["market_context"]["emphasis"] == ["speed"]
    assert marketed["manifest"]["market_context"]["audience_id"] == "teachers_lecturers"
    assert "product_definition" not in marketed["manifest"]["market_context"]
    assert "claims" not in marketed["manifest"]["market_context"]


def test_release_authority_stays_human(tmp_path: Path):
    result = compile_product_explainer("homs", root=build_complete_homs_fixture(tmp_path))
    authority = result["manifest"]["authority"]
    assert authority["human_release_required"] is True
    assert authority["external_publication"] == "NEEDS_YOU"
    assert authority["media_spend"] == "REFUSE"
    assert authority["market_may_change_product_truth"] is False


def test_marketing_outcome_is_qualified_not_supported(tmp_path: Path):
    truth = resolve_product_truth("homs", root=build_complete_homs_fixture(tmp_path))
    envelope = build_claim_envelope(truth)
    qualified = [row["text"] for row in envelope["qualified"]]
    supported = [row["text"] for row in envelope["allowed"]]
    assert "Structured drafts and learner feedback ready for educator review." in qualified
    assert "Structured drafts and learner feedback ready for educator review." not in supported


def test_source_change_changes_manifest_fingerprint(tmp_path: Path):
    root = build_complete_homs_fixture(tmp_path)
    first = compile_product_explainer("homs", root=root)
    portfolio = root / "state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_RUNTIME.json"
    data = json.loads(portfolio.read_text())
    data["incarnations"][0]["Outputs"].append("review summary")
    portfolio.write_text(json.dumps(data), encoding="utf-8")
    second = compile_product_explainer("homs", root=root)
    assert first["manifest_sha256"] != second["manifest_sha256"]
    assert first["manifest"]["source_binding"] != second["manifest"]["source_binding"]


def install_test_brand_profile(root: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "config/media_style_profiles.json"
    target = root / "config/media_style_profiles.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    master = root / "media/golden_references/dio_launch_cinematic_v1/master/DIO_LAUNCH_TRAILER_MASTER_V1.mp4"
    wordmark = root / "media/golden_references/dio_launch_cinematic_v1/brand/dio-wordmark.svg"
    sigil = root / "media/golden_references/dio_launch_cinematic_v1/brand/dio-sigil.webp"
    master.parent.mkdir(parents=True, exist_ok=True)
    wordmark.parent.mkdir(parents=True, exist_ok=True)
    master.write_bytes(b"test-golden-master")
    wordmark.write_text("<svg/>", encoding="utf-8")
    sigil.write_bytes(b"test-sigil")


def test_media_request_binds_explainer_style_and_voice(tmp_path: Path):
    root = build_complete_homs_fixture(tmp_path)
    install_test_brand_profile(root)
    compiled = compile_product_explainer("homs", root=root)
    request = build_media_production_request(compiled, root=root)
    assert request["schema"] == "dio.media.production_request.v2"
    assert request["explainer_manifest"]["sha256"] == compiled["manifest_sha256"]
    assert request["style_profile"]["sha256"].startswith("sha256:")
    assert request["voice"] == {
        "role": "vesper_public",
        "profile": "vera_pocket_public",
        "render_mode": "presence_core_imported_audio",
        "pronunciation": {"DIO": "Dio"},
    }
    assert request["release"] == {
        "local_render": "ALLOW",
        "external_publication": "NEEDS_YOU",
        "media_spend": "REFUSE",
    }


def test_script_package_explains_before_it_sells(tmp_path: Path):
    compiled = compile_product_explainer("homs", root=build_complete_homs_fixture(tmp_path))
    script = build_explainer_script_package(compiled["manifest"])
    beats = [scene["story_beat"] for scene in script["scenes"]]
    assert beats == [
        "problem",
        "product_definition",
        "mechanism",
        "proof",
        "differentiation",
        "result",
        "call_to_action",
    ]
    assert [scene["target_duration_seconds"] for scene in script["scenes"]] == [7, 7, 11, 11, 9, 7, 3]
    assert sum(scene["target_duration_seconds"] for scene in script["scenes"]) == 55
    assert all(scene["source_ids"] for scene in script["scenes"][:-1])
    assert all("asset_preference" in scene for scene in script["scenes"])


def test_semantic_challenge_accepts_compiler_script(tmp_path: Path):
    compiled = compile_product_explainer("homs", root=build_complete_homs_fixture(tmp_path))
    script = build_explainer_script_package(compiled["manifest"])
    report = semantic_challenge(compiled["manifest"], script)
    assert report["state"] == "PASS"
    assert report["codes"] == []


def test_semantic_challenge_refuses_strengthened_claim(tmp_path: Path):
    compiled = compile_product_explainer("homs", root=build_complete_homs_fixture(tmp_path))
    script = build_explainer_script_package(compiled["manifest"])
    script["scenes"][2]["narration"] = "HOMS guarantees compliant assessments every time."
    report = semantic_challenge(compiled["manifest"], script)
    assert report["state"] == "REFUSE"
    assert "CLAIM_EXCEEDS_EVIDENCE" in report["codes"]


def test_semantic_challenge_refuses_generated_asset_presented_as_evidence(tmp_path: Path):
    compiled = compile_product_explainer("homs", root=build_complete_homs_fixture(tmp_path))
    script = build_explainer_script_package(compiled["manifest"])
    script["scenes"][3]["asset_provenance"] = "generated"
    script["scenes"][3]["asset_representation"] = "evidence"
    report = semantic_challenge(compiled["manifest"], script)
    assert report["state"] == "REFUSE"
    assert "GENERATED_ASSET_MISREPRESENTED_AS_EVIDENCE" in report["codes"]
