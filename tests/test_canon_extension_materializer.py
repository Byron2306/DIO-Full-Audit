from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from products.canon_extension_materializer import (
    MATERIALIZATION_FILENAME,
    MATERIALIZED_TOKEN,
    materialize_receipt_bound_extensions,
)
from products.canon_extension_product_grade import CANON_EXTENSIONS
from products.canon_extension_proof_seal import CanonExtensionProofSealError, seal_receipt_bound_extension


ROOT = Path(__file__).resolve().parents[1]
ANCHOR_REL = Path("evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_anchor(root: Path) -> Path:
    source = ROOT / ANCHOR_REL
    target = root / ANCHOR_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    return target


def _receipt_bound_specs() -> list[dict]:
    return [row for row in CANON_EXTENSIONS if row["proof_kind"] == "receipt_bound"]


def _materialized_spec(slug: str) -> dict:
    spec = dict(next(row for row in _receipt_bound_specs() if row["slug"] == slug))
    spec["proof_receipt"] = str(Path(spec["primary_artifact"]).parent / MATERIALIZATION_FILENAME)
    return spec


def test_materializes_exactly_11_receipt_bound_extensions(tmp_path: Path) -> None:
    anchor = _seed_anchor(tmp_path)
    batch = materialize_receipt_bound_extensions(root=tmp_path)

    assert batch["acceptance_token"] == MATERIALIZED_TOKEN
    assert batch["target_count"] == 11
    assert batch["materialized_count"] == 11
    assert batch["refuse_count"] == 0
    assert batch["authority_created"] is False
    assert batch["external_effects"] is False
    assert batch["commercial_validation"] == "UNPROVED"

    specs = _receipt_bound_specs()
    assert len(specs) == 11
    anchor_sha = _sha(anchor)

    for spec in specs:
        site = tmp_path / spec["primary_artifact"]
        receipt_path = site.parent / MATERIALIZATION_FILENAME
        assert site.is_file()
        assert receipt_path.is_file()

        row = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert row["schema"] == "dio.canon_extension.materialization_receipt.v1"
        assert row["status"] == "PASS"
        assert row["canon_id"] == spec["canon_id"]
        assert row["name"] == spec["name"]
        assert row["slug"] == spec["slug"]
        assert row["primary_artifact"] == spec["primary_artifact"]
        assert row["primary_artifact_sha256"] == _sha(site)
        assert row["historical_anchor"] == str(ANCHOR_REL)
        assert row["historical_anchor_sha256"] == anchor_sha
        assert str(row["profile_fingerprint"]).startswith("sha256:")
        assert str(row["receipt_fingerprint"]).startswith("sha256:")
        assert row["authority_created"] is False
        assert row["external_effects"] is False
        assert row["commercial_validation"] == "UNPROVED"


def test_materialization_is_byte_deterministic(tmp_path: Path) -> None:
    _seed_anchor(tmp_path)
    first = materialize_receipt_bound_extensions(root=tmp_path)
    assert first["acceptance_token"] == MATERIALIZED_TOKEN

    first_hashes: dict[str, tuple[str, str]] = {}
    for spec in _receipt_bound_specs():
        site = tmp_path / spec["primary_artifact"]
        receipt_path = site.parent / MATERIALIZATION_FILENAME
        first_hashes[spec["slug"]] = (_sha(site), _sha(receipt_path))

    second = materialize_receipt_bound_extensions(root=tmp_path)
    assert second["acceptance_token"] == MATERIALIZED_TOKEN

    second_hashes = {
        spec["slug"]: (
            _sha(tmp_path / spec["primary_artifact"]),
            _sha((tmp_path / spec["primary_artifact"]).parent / MATERIALIZATION_FILENAME),
        )
        for spec in _receipt_bound_specs()
    }

    assert second_hashes == first_hashes


def test_materialization_never_emits_gamma_receipts(tmp_path: Path) -> None:
    _seed_anchor(tmp_path)
    batch = materialize_receipt_bound_extensions(root=tmp_path)
    assert batch["acceptance_token"] == MATERIALIZED_TOKEN
    assert list(tmp_path.rglob("GAMMA_RECEIPT.json")) == []


def test_sealer_refuses_when_materialized_artifact_no_longer_matches_source_receipt(tmp_path: Path) -> None:
    _seed_anchor(tmp_path)
    batch = materialize_receipt_bound_extensions(root=tmp_path)
    assert batch["acceptance_token"] == MATERIALIZED_TOKEN

    spec = _materialized_spec("contract-desk")
    first = seal_receipt_bound_extension(spec=spec, root=tmp_path)
    assert first["status"] == "PASS"

    artifact = tmp_path / spec["primary_artifact"]
    artifact.write_text(artifact.read_text(encoding="utf-8") + "\nTAMPERED\n", encoding="utf-8")

    with pytest.raises(CanonExtensionProofSealError, match="bind current artifact sha256"):
        seal_receipt_bound_extension(spec=spec, root=tmp_path)
