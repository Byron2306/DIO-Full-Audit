from __future__ import annotations

from pathlib import Path

from products.portfolio_customer_surface import (
    READY,
    build_review_portal,
    evaluate_canonical_surface,
    evaluate_site_surface,
    inspect_artifact,
    load_contract,
    load_crosswalk,
    resolve_family_policy,
    resolve_wave,
    scan_customer_surface,
    slug,
)


def _write(path: Path, text: str, repeat: int = 1) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text * repeat, encoding="utf-8")
    return path


def test_contract_exposes_alpha_canonical53_and_full57() -> None:
    contract = load_contract()
    crosswalk = load_crosswalk()
    alpha = resolve_wave(contract, crosswalk, "alpha")
    canonical = resolve_wave(contract, crosswalk, "canonical53")
    full = resolve_wave(contract, crosswalk, "full57")

    assert len(alpha["canonical"]) == 7
    assert alpha["studios"] == ["site_studio"]
    assert len(canonical["canonical"]) == 53
    assert canonical["studios"] == []
    assert len(full["canonical"]) == 53
    assert len(full["studios"]) == 4
    assert len(full["canonical"]) + len(full["studios"]) == 57


def test_family_policy_routes_meaningful_product_families() -> None:
    contract = load_contract()
    assert resolve_family_policy(contract, {"primary_family": "HOMS", "suite": "Education & Research"})["policy_id"] == "education_deliverable"
    assert resolve_family_policy(contract, {"primary_family": "Sophia", "suite": "Education & Research"})["policy_id"] == "academic_review_deliverable"
    assert resolve_family_policy(contract, {"primary_family": "NicheFoundry + Hivenance", "suite": "Demand & Presence"})["policy_id"] == "market_deliverable"
    assert resolve_family_policy(contract, {"primary_family": "BEAST + META", "suite": "AI & Digital Trust"})["policy_id"] == "ai_assurance_deliverable"


def test_customer_surface_gate_rejects_internal_machinery_and_prefers_customer_output(tmp_path: Path) -> None:
    contract = load_contract()
    gate = contract["artifact_gate"]
    policy = contract["default_surface_policy"]
    root = tmp_path / "EXECUTION"
    _write(root / "PROFESSIONAL_EVIDENCE_RECEIPT.md", "receipt internals only\n", 30)
    _write(root / "CUSTOMER_REQUEST.md", "request internals only\n", 30)
    customer = _write(
        root / "customer-ready-report.html",
        "<html><body><h1>Customer report</h1><p>This is a substantial professional deliverable with evidence, findings, limitations and a clear review boundary.</p></body></html>",
        8,
    )
    _write(root / "supporting-notes.md", "Useful customer-facing supporting explanation with enough substantive content to inspect.\n", 10)

    result = scan_customer_surface(root, gate=gate, policy=policy, terminal_artifact_kind="professional report")
    assert result["state"] == "PASS"
    assert result["selected"][0]["path"] == str(customer.resolve())
    refused_names = {Path(row["path"]).name for row in result["refused_sample"]}
    assert "PROFESSIONAL_EVIDENCE_RECEIPT.md" in refused_names
    assert "CUSTOMER_REQUEST.md" in refused_names


def test_canonical_surface_requires_three_tier_pipeline_and_buyer_artifact(tmp_path: Path) -> None:
    contract = load_contract()
    incarnation = "HOMS Exam"
    execution = tmp_path / "normal" / slug(incarnation) / "EXECUTION"
    _write(
        execution / "review-ready-exam.html",
        "<html><body><h1>Grade 12 examination</h1><p>Questions, source material, memorandum and educator review boundary are presented for customer use.</p></body></html>",
        8,
    )
    tier = {
        "verified_count": 3,
        "all_variants_verified": True,
        "variants": {
            "normal": {"passed": True, "terminal_artifact_kind": "review_ready_exam_and_memo"},
            "messy": {"passed": True},
            "adversarial": {"passed": True},
        },
    }
    source = {"incarnation": incarnation, "suite": "Education & Research", "primary_family": "HOMS", "source_maturity": "Internal proof", "execution_truth_class": "PORTFOLIO_INTERNAL_PROOF"}
    row = evaluate_canonical_surface(incarnation=incarnation, source=source, multitier_row=tier, canonical_root=tmp_path, contract=contract)
    assert row["engineering_surface_status"] == READY
    assert row["human_buyer_review"] == "PENDING"
    assert row["customer_grade_claimed"] is False
    assert row["commercial_validation"] == "UNPROVED"


def test_site_surface_requires_real_customer_pack_not_just_html(tmp_path: Path) -> None:
    contract = load_contract()
    site = tmp_path / "FULL_GRADE_SITE"
    _write(
        site / "index.html",
        "<html><body><h1>Karoo Research Advisory</h1><p>Evidence-led research consulting with services, proof, human authority and controlled intake.</p></body></html>",
        8,
    )
    good = {
        "customer_visual_pack_state": "READY_NEEDS_YOU",
        "format_core_visual_compositor": "PASS",
        "visual_projection_authority": "DIO_FORMAT_CORE",
        "role_geometry_selection": "REFUSE",
        "role_material_selection": "REFUSE",
        "remote_runtime_asset_fetch": "REFUSE",
        "mixed_media_scene_count": 5,
        "material_kind_counts": {"curated_photo": 3, "artifact_render": 2, "native_renderer": 3},
    }
    row = evaluate_site_surface(site_root=site, production_summary=good, contract=contract)
    assert row["engineering_surface_status"] == READY
    assert row["customer_visual_pack_pass"] is True

    bad = {**good, "customer_visual_pack_state": "REFUSE"}
    refused = evaluate_site_surface(site_root=site, production_summary=bad, contract=contract)
    assert refused["engineering_surface_status"] != READY


def test_review_portal_packages_copies_without_mutating_original(tmp_path: Path) -> None:
    contract = load_contract()
    original = _write(
        tmp_path / "original" / "buyer-output.html",
        "<html><body><h1>Buyer output</h1><p>A substantial customer-facing artifact used for blind review.</p></body></html>",
        10,
    )
    candidate = inspect_artifact(original, gate=contract["artifact_gate"], policy=contract["default_surface_policy"], terminal_artifact_kind="buyer output")
    before = original.read_bytes()
    rows = [
        {
            "surface_id": "demo",
            "surface_name": "Demo Product",
            "surface_origin": "test",
            "surface_label": "customer artifact",
            "engineering_surface_status": READY,
            "human_buyer_review": "PENDING",
            "buyer_review_dimensions": ["buyer-job fidelity", "professional presentation", "would use"],
            "customer_surface_gate": {"state": "PASS", "selected": [candidate]},
        }
    ]
    receipt = build_review_portal(rows, tmp_path / "review", contract)
    portal = Path(receipt["portal"])
    assert portal.is_file()
    assert "Would you actually hand this to the customer?" in portal.read_text(encoding="utf-8")
    assert receipt["engineering_ready_count"] == 1
    assert receipt["customer_grade_claimed"] is False
    assert original.read_bytes() == before
    copied = receipt["packaged"][0]["assets"]
    assert len(copied) == 1
    assert (portal.parent / copied[0]["review_path"]).is_file()
