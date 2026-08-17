from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any


ROUTE_CONFIG_NAME = "config/product_class_routes.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def route_key(value: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def route_contract(root: Path, product_class: str) -> dict[str, Any]:
    config = load_json(root / ROUTE_CONFIG_NAME)
    key = route_key(product_class)
    key = str((config.get("aliases") or {}).get(key, key))
    direct = (config.get("direct_products") or {}).get(key)
    if direct:
        return {"key": key, "registered_as": "direct_product", **direct}
    product = (config.get("product_classes") or {}).get(key)
    if product:
        return {"key": key, "registered_as": "product_class", **product}
    return {
        "key": key,
        "registered_as": "unregistered",
        "route_kind": "missing",
        "auto_promotable": False,
        "suggested_engine": None,
    }


def _mark_demo_file(path: Path, product_class: str) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".md":
        marker = (
            f"# {product_class} Structural Demonstration\n\n"
            "> **Evidence boundary:** this is a synthetic/profile demonstration. It is not an execution receipt, buyer proof, certification, or evidence that the typed fulfilment route has run.\n\n"
        )
        if "Evidence boundary:" not in text:
            text = marker + text.replace(f"# {product_class} Golden Proof\n", "", 1)
    elif path.suffix.lower() == ".html":
        banner = (
            '<div style="padding:14px 18px;background:#fff3cd;border:1px solid #e5c07b;color:#5f4300;font-weight:700;">'
            "STRUCTURAL DEMONSTRATION ONLY. This is not an execution receipt or proof that the typed fulfilment route has run."
            "</div>"
        )
        if "STRUCTURAL DEMONSTRATION ONLY" not in text:
            text = text.replace("<body>", f"<body>\n{banner}", 1)
            text = text.replace(f"<title>{product_class} Golden Proof</title>", f"<title>{product_class} Structural Demonstration</title>")
            text = text.replace(f"<h1>{product_class} Golden Proof</h1>", f"<h1>{product_class} Structural Demonstration</h1>")
    path.write_text(text, encoding="utf-8")


def truth_gate_package(
    *,
    root: Path,
    package_root: Path,
    deliverable_root: Path,
    site_root: Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    slug = str(result["slug"])
    package_dir = package_root / slug
    site_path = site_root / slug / "index.html"
    profile_path = package_dir / "PRODUCT_PROFILE.json"
    smoke_path = package_dir / "SMOKE_TEST_RECEIPT.json"
    route_path = package_dir / "PROCESSING_ROUTE.json"
    manifest_path = package_dir / "PACKAGE_MANIFEST.json"
    product_class = str(result.get("name") or result.get("product_class") or slug)
    contract = route_contract(root, product_class)

    if profile_path.is_file():
        profile = load_json(profile_path)
        profile.update({
            "state": "structural_proof_packaged",
            "commercial_posture": "execution_proof_required",
            "route_contract": contract,
            "public_offer_state": "held_until_typed_route_execution_proof",
        })
        profile["truth_boundary"] = (
            "This package proves a typed profile, intake shape, example outputs and authority boundary. "
            "It does not prove that the product-class fulfilment route has executed successfully."
        )
        public_urls = profile.setdefault("public_urls", {})
        public_urls["product_site"] = None
        write_json(profile_path, profile)

    write_json(route_path, {
        "schema": "dio.processing_route.v2",
        "product_class": product_class,
        "state": "typed_route_required",
        "route_contract": contract,
        "auto_promotable": False,
        "execution_route": [],
        "suggested_engine": contract.get("suggested_engine") or contract.get("engine"),
        "required_before_execution": [
            "typed product profile approved",
            "source/authority contract approved",
            "processor adapter selected",
            "controlled execution fixture accepted",
        ],
        "required_before_public_launch": [
            "successful controlled execution receipt",
            "reviewed output artifact",
            "public-safe proof artifact",
            "operator launch approval",
        ],
        "truth_boundary": "Named processors are architectural candidates, not evidence that this route is currently executable.",
    })

    checks = []
    for filename in (
        "PRODUCT_PROFILE.json",
        "INTAKE_SCHEMA.json",
        "PROCESSING_ROUTE.json",
        "MAIL_TEMPLATES.json",
        "MARKET_COMMAND_SEED.json",
        "GOLDEN_PROOF.md",
        "PACKAGE_MANIFEST.json",
    ):
        checks.append({"check": f"structural:{filename}", "passed": (package_dir / filename).exists()})
    checks.extend([
        {"check": "typed_execution_receipt", "passed": False, "required_for": "execution_proof"},
        {"check": "public_safe_proof", "passed": False, "required_for": "public_launch"},
        {"check": "public_product_page", "passed": False, "required_for": "public_launch"},
    ])
    write_json(smoke_path, {
        "schema": "dio.product_class_structural_smoke_receipt.v2",
        "product_class": product_class,
        "slug": slug,
        "result": "structural_passed" if all(item["passed"] for item in checks if str(item["check"]).startswith("structural:")) else "structural_failed",
        "evidence_level": "structural_proof",
        "execution_proof": False,
        "public_launch_ready": False,
        "checks": checks,
        "route_contract": contract,
    })

    _mark_demo_file(package_dir / "GOLDEN_PROOF.md", product_class)
    _mark_demo_file(package_dir / "GOLDEN_PROOF.html", product_class)

    manifest = load_json(manifest_path) if manifest_path.is_file() else {}
    manifest.update({
        "schema": "dio.product_class_package_manifest.v2",
        "product_class": product_class,
        "slug": slug,
        "state": "structural_proof_packaged",
        "evidence_level": "structural_proof",
        "execution_proof": False,
        "public_launch_ready": False,
        "site_path": None,
        "public_url": None,
        "route_contract": contract,
        "required_operator_posture": "Do not market as execution-ready. Approve a typed route and successful execution proof first.",
    })
    write_json(manifest_path, manifest)

    if site_path.exists():
        site_path.unlink()
        try:
            site_path.parent.rmdir()
        except OSError:
            pass

    deliverable_dir = deliverable_root / slug
    zip_path = deliverable_dir / f"{slug}_CONTROLLED_PILOT_PACKAGE.zip"
    if zip_path.exists():
        zip_path.unlink()
    deliverable_dir.mkdir(parents=True, exist_ok=True)
    structural_zip = deliverable_dir / f"{slug}_STRUCTURAL_PROOF_PACKAGE.zip"
    with zipfile.ZipFile(structural_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package_dir.iterdir()):
            if path.is_file():
                archive.write(path, arcname=f"{slug}/{path.name}")
    manifest = load_json(manifest_path)
    manifest["deliverable_zip"] = str(structural_zip.relative_to(root))
    manifest["deliverable_zip_exists"] = structural_zip.exists()
    write_json(manifest_path, manifest)

    result.update({
        "site_path": "",
        "zip_path": str(structural_zip.relative_to(root)),
        "result": "structural_proof_packaged",
        "evidence_level": "structural_proof",
        "execution_proof": False,
        "public_launch_ready": False,
        "route_contract": contract,
    })
    return result
