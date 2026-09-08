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
from products.canon_extension_native_profiles import native_profile
from products.canon_extension_product_grade import CANON_EXTENSIONS
from products.canon_extension_proof_seal import CanonExtensionProofSealError, seal_receipt_bound_extension


REPO_ROOT = Path(__file__).resolve().parents[1]
ANCHOR_REL = Path("evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_anchor(root: Path) -> Path:
    source = REPO_ROOT / ANCHOR_REL
    target = root / ANCHOR_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    return target


def _targets() -> list[dict]:
    return [row for row in CANON_EXTENSIONS if row["proof_kind"] == "receipt_bound"]


def _generated_hashes(root: Path) -> dict[str, tuple[str, str]]:
    rows: dict[str, tuple[str, str]] = {}
    for spec in _targets():
        artifact = root / spec["primary_artifact"]
        receipt = artifact.parent / MATERIALIZATION_FILENAME
        rows[spec["slug"]] = (_sha(artifact), _sha(receipt))
    return rows


def test_materializes_exactly_11_receipt_bound_canon_extensions(tmp_path: Path) -> None:
    anchor = _seed_anchor(tmp_path)

    batch = materialize_receipt_bound_extensions(root=tmp_path)

    assert batch["acceptance_token"] == MATERIALIZED_TOKEN
    assert batch["target_count"] == 11
    assert batch["materialized_count"] == 11
    assert batch["refuse_count"] == 0
    assert batch["authority_created"] is False
    assert batch["external_effects"] is False
    assert batch["commercial_validation"] == "UNPROVED"

    for spec in _targets():
        artifact = tmp_path / spec["primary_artifact"]
        receipt_path = artifact.parent / MATERIALIZATION_FILENAME
        assert artifact.is_file()
        assert receipt_path.is_file()

        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["schema"] == "dio.canon_extension.materialization_receipt.v1"
        assert receipt["status"] == "PASS"
        assert receipt["canon_id"] == spec["canon_id"]
        assert receipt["slug"] == spec["slug"]
        assert receipt["primary_artifact"] == spec["primary_artifact"]
        assert receipt["primary_artifact_sha256"] == _sha(artifact)
        assert receipt["historical_anchor"] == ANCHOR_REL.as_posix()
        assert receipt["historical_anchor_sha256"] == _sha(anchor)
        assert receipt["profile_fingerprint"].startswith("sha256:")
        assert receipt["authority_created"] is False
        assert receipt["external_effects"] is False
        assert receipt["commercial_validation"] == "UNPROVED"
        assert receipt["receipt_fingerprint"].startswith("sha256:")


def test_materialization_is_byte_deterministic(tmp_path: Path) -> None:
    _seed_anchor(tmp_path)

    first = materialize_receipt_bound_extensions(root=tmp_path)
    assert first["acceptance_token"] == MATERIALIZED_TOKEN
    first_hashes = _generated_hashes(tmp_path)

    second = materialize_receipt_bound_extensions(root=tmp_path)
    assert second["acceptance_token"] == MATERIALIZED_TOKEN
    second_hashes = _generated_hashes(tmp_path)

    assert first_hashes == second_hashes


def test_materialization_receipt_binds_exact_native_profile(tmp_path: Path) -> None:
    _seed_anchor(tmp_path)
    batch = materialize_receipt_bound_extensions(root=tmp_path)
    assert batch["acceptance_token"] == MATERIALIZED_TOKEN

    for spec in _targets():
        receipt_path = tmp_path / spec["primary_artifact"]
        receipt = json.loads((receipt_path.parent / MATERIALIZATION_FILENAME).read_text(encoding="utf-8"))
        profile = native_profile(spec["slug"])
        canonical = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        expected = "sha256:" + hashlib.sha256(canonical).hexdigest()
        assert receipt["profile_fingerprint"] == expected


def test_sealer_refuses_after_materialized_artifact_tamper(tmp_path: Path) -> None:
    _seed_anchor(tmp_path)
    batch = materialize_receipt_bound_extensions(root=tmp_path)
    assert batch["acceptance_token"] == MATERIALIZED_TOKEN

    spec = next(row for row in CANON_EXTENSIONS if row["slug"] == "contract-desk")
    materialized_spec = dict(spec)
    materialized_spec["proof_receipt"] = str(
        Path(spec["primary_artifact"]).parent / MATERIALIZATION_FILENAME
    )

    seal = seal_receipt_bound_extension(spec=materialized_spec, root=tmp_path)
    assert seal["status"] == "PASS"

    artifact = tmp_path / spec["primary_artifact"]
    artifact.write_text(artifact.read_text(encoding="utf-8") + "\nTAMPERED\n", encoding="utf-8")

    with pytest.raises(CanonExtensionProofSealError, match="does not bind current artifact sha256"):
        seal_receipt_bound_extension(spec=materialized_spec, root=tmp_path)
