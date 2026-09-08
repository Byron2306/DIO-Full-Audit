from __future__ import annotations

import hashlib
import json
from pathlib import Path

from products.canon_extension_product_grade import CANON_EXTENSIONS, evaluate_receipt_bound_extension
from products.canon_extension_proof_seal import seal_receipt_bound_extension


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_dual_bound_case(root: Path) -> tuple[dict, Path, Path, dict]:
    spec = next(row for row in CANON_EXTENSIONS if row["slug"] == "contract-desk")
    canon = root / spec["primary_artifact"]
    gamma = root / spec["proof_receipt"]
    canon.parent.mkdir(parents=True, exist_ok=True)
    canon.write_text(
        "<!doctype html><html><body><h1>Contract Desk</h1><p>Canonical product surface.</p></body></html>\n",
        encoding="utf-8",
    )
    gamma.write_text(
        json.dumps(
            {
                "schema": "fixture.gamma.receipt.v1",
                "status": "PASS",
                "artifact_sha256": _sha(canon),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    seal_receipt_bound_extension(spec=spec, root=root)
    seal = canon.parent / "CANON_EXTENSION_PROOF_RECEIPT.json"

    customer = root / "state" / "product_grade" / "canon_extensions" / "contract-desk" / "customer_delivery" / "index.html"
    customer.parent.mkdir(parents=True, exist_ok=True)
    customer.write_text(
        "<!doctype html><html><body><h1>SA-104 Northstar Services Agreement</h1><p>Controlled buyer review brief.</p></body></html>\n",
        encoding="utf-8",
    )
    native = {
        "schema": "dio.product_grade.canon_extension_native.v2",
        "status": "PRODUCT_GRADE_VERIFIED",
        "canon_artifact": spec["primary_artifact"],
        "canon_artifact_sha256": _sha(canon),
        "canon_proof_receipt": str(seal.relative_to(root)),
        "canon_proof_receipt_sha256": _sha(seal),
        "customer_artifact": str(customer.relative_to(root)),
        "customer_artifact_sha256": _sha(customer),
        "primary_artifact_sha256": _sha(customer),
        "beast_mechanical_pass": True,
        "lingua_semantic_custody": True,
        "unseen_input_generalisation": True,
        "external_effects": False,
        "authority_created": False,
        "commercial_validation": "UNPROVED",
    }
    return spec, canon, customer, native


def test_v2_native_receipt_promotes_only_with_live_dual_binding(tmp_path: Path) -> None:
    spec, _, _, native = _seed_dual_bound_case(tmp_path)

    row = evaluate_receipt_bound_extension(
        spec=spec,
        root=tmp_path,
        native_product_grade_receipt=native,
    )

    assert row["proof_status"] == "CANON_EXTENSION_PROOF_VERIFIED"
    assert row["status"] == "PRODUCT_GRADE_VERIFIED"
    assert row["critical_blockers"] == []


def test_v2_native_receipt_refuses_after_customer_artifact_tamper(tmp_path: Path) -> None:
    spec, _, customer, native = _seed_dual_bound_case(tmp_path)
    customer.write_text(customer.read_text(encoding="utf-8") + "TAMPERED\n", encoding="utf-8")

    row = evaluate_receipt_bound_extension(
        spec=spec,
        root=tmp_path,
        native_product_grade_receipt=native,
    )

    assert row["proof_status"] == "CANON_EXTENSION_PROOF_VERIFIED"
    assert row["status"] == "PRODUCT_GRADE_REFUSE"
    assert "native_product_grade_customer_artifact_mismatch" in row["critical_blockers"]
