from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import audit_product_class_readiness as readiness
from scripts.product_class_packaging_truth import truth_gate_package


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def route_config() -> dict:
    return {
        "schema": "dio.product_class_routes.v1",
        "direct_products": {},
        "aliases": {},
        "product_classes": {
            "grantproof": {
                "route_kind": "profile_extension",
                "suggested_engine": "evidex",
                "auto_promotable": False,
            }
        },
    }


def prepare_legacy_package(root: Path) -> dict:
    slug = "grantproof"
    package_dir = root / "state" / "product_class_packages" / slug
    deliverable_dir = root / "deliverables" / "product_class_packages" / slug
    site_dir = root / "sites" / "product-classes" / slug
    write_json(root / "config" / "product_class_routes.json", route_config())
    for filename in ["INTAKE_SCHEMA.json", "PROCESSING_ROUTE.json", "MAIL_TEMPLATES.json", "MARKET_COMMAND_SEED.json"]:
        write_json(package_dir / filename, {"schema": "test"})
    write_json(package_dir / "PRODUCT_PROFILE.json", {
        "schema": "dio.product_class_profile.v1",
        "product_class": "GrantProof",
        "slug": slug,
        "state": "controlled_pilot_packaged",
        "public_urls": {"product_site": "https://example.invalid/grantproof/"},
    })
    (package_dir / "GOLDEN_PROOF.md").parent.mkdir(parents=True, exist_ok=True)
    (package_dir / "GOLDEN_PROOF.md").write_text("# GrantProof Golden Proof\n\nSynthetic example.\n", encoding="utf-8")
    (package_dir / "GOLDEN_PROOF.html").write_text("<html><body><h1>GrantProof Golden Proof</h1></body></html>", encoding="utf-8")
    write_json(package_dir / "SMOKE_TEST_RECEIPT.json", {"result": "passed", "checks": []})
    write_json(package_dir / "PACKAGE_MANIFEST.json", {
        "state": "launch_controlled_pilot_package_ready",
        "site_path": f"sites/product-classes/{slug}/index.html",
        "public_url": "https://example.invalid/grantproof/",
    })
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text("<html>premature public page</html>", encoding="utf-8")
    deliverable_dir.mkdir(parents=True, exist_ok=True)
    (deliverable_dir / f"{slug}_CONTROLLED_PILOT_PACKAGE.zip").write_bytes(b"old")
    return {
        "name": "GrantProof",
        "slug": slug,
        "site_path": f"sites/product-classes/{slug}/index.html",
        "zip_path": f"deliverables/product_class_packages/{slug}/{slug}_CONTROLLED_PILOT_PACKAGE.zip",
        "result": "packaged",
    }


def test_truth_gate_demotes_legacy_package_and_removes_public_leaf(tmp_path: Path) -> None:
    result = prepare_legacy_package(tmp_path)

    corrected = truth_gate_package(
        root=tmp_path,
        package_root=tmp_path / "state" / "product_class_packages",
        deliverable_root=tmp_path / "deliverables" / "product_class_packages",
        site_root=tmp_path / "sites" / "product-classes",
        result=result,
    )

    slug = "grantproof"
    package_dir = tmp_path / "state" / "product_class_packages" / slug
    manifest = json.loads((package_dir / "PACKAGE_MANIFEST.json").read_text())
    smoke = json.loads((package_dir / "SMOKE_TEST_RECEIPT.json").read_text())
    route = json.loads((package_dir / "PROCESSING_ROUTE.json").read_text())

    assert corrected["result"] == "structural_proof_packaged"
    assert corrected["execution_proof"] is False
    assert corrected["public_launch_ready"] is False
    assert not (tmp_path / "sites" / "product-classes" / slug / "index.html").exists()
    assert manifest["state"] == "structural_proof_packaged"
    assert manifest["public_url"] is None
    assert smoke["result"] == "structural_passed"
    assert smoke["execution_proof"] is False
    assert route["state"] == "typed_route_required"
    assert route["execution_route"] == []
    assert (tmp_path / "deliverables" / "product_class_packages" / slug / f"{slug}_STRUCTURAL_PROOF_PACKAGE.zip").is_file()
    assert not (tmp_path / "deliverables" / "product_class_packages" / slug / f"{slug}_CONTROLLED_PILOT_PACKAGE.zip").exists()


def test_readiness_audit_keeps_structural_package_below_launch_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = prepare_legacy_package(tmp_path)
    package_root = tmp_path / "state" / "product_class_packages"
    deliverable_root = tmp_path / "deliverables" / "product_class_packages"
    truth_gate_package(
        root=tmp_path,
        package_root=package_root,
        deliverable_root=deliverable_root,
        site_root=tmp_path / "sites" / "product-classes",
        result=result,
    )
    monkeypatch.setattr(readiness, "ROOT", tmp_path)
    monkeypatch.setattr(readiness, "PACKAGE_ROOT", package_root)
    monkeypatch.setattr(readiness, "DELIVERABLE_ROOT", deliverable_root)

    row = {"Incarnation": "GrantProof"}
    state = readiness.classify(row, route_config())
    processing = readiness.processing_coverage(row, route_config(), state)

    assert state["tier"] == "structural_proof_packaged"
    assert state["label"] == "packaged structural proof"
    assert processing["state"] == "typed_route_required"
    assert processing["processing_ready"] is False
    assert processing["lead_promotion_ready"] is False
