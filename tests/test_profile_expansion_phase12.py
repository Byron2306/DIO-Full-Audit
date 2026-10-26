from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from products.compiler import CompilerError, bind_profiles, compile_manifest, load_profile_index
from products.obligationfamily.runner import FAMILY_DEFINITIONS, run_family_proof
from products.profile_expansion import ACCEPTANCE_TOKEN, PROFILE_CLASSES, run_profile_expansion

ROOT = Path(__file__).resolve().parents[1]


def test_policyproof_is_a_canonical_six_axis_profile_incarnation() -> None:
    compiled = compile_manifest(ROOT, ROOT / "config/products/manifests/policyproof.json")
    assert compiled["product_id"] == "dio_policyproof"
    assert {row["profile_class"] for row in compiled["profile_bindings"]} == PROFILE_CLASSES
    assert "framework.policy_assurance" in {row["profile_id"] for row in compiled["profile_bindings"]}
    assert compiled["gates"]["execution"]["state"] == "NEEDS_YOU"
    assert compiled["gates"]["external_release"]["state"] == "REFUSE"
    assert FAMILY_DEFINITIONS["dio_policyproof"]["source_type"] == "policy"


def test_profile_reference_tampering_refuses_before_compilation() -> None:
    manifest = json.loads((ROOT / "config/products/manifests/policyproof.json").read_text())
    manifest["profiles"]["framework"][0]["content_hash"] = "sha256:" + "f" * 64
    with pytest.raises(CompilerError, match="profile content hash mismatch"):
        bind_profiles(ROOT, manifest, load_profile_index(ROOT))


def test_cross_profile_source_type_refuses(tmp_path: Path) -> None:
    tender = json.loads((ROOT / "config/products/golden/tenderproof/reference_source.json").read_text())
    with pytest.raises(ValueError, match="source_type=policy"):
        run_family_proof("dio_policyproof", tender, [], output_dir=tmp_path,
                         operator_id="human.phase12_test", now="2026-08-12T12:00:00+00:00")


def test_phase12_full_gauntlet(tmp_path: Path) -> None:
    receipt = run_profile_expansion(output_dir=tmp_path / "phase12")
    assert receipt["acceptance_token"] == ACCEPTANCE_TOKEN
    assert receipt["incarnation_count"] == 5
    assert receipt["new_incarnation"] == "dio_policyproof"
    assert receipt["phase7_regression"] == "PASS"
    assert receipt["profile_source_custody"] == "PASS"
    assert receipt["source_type_isolation"] == "PASS"
    assert receipt["deterministic_execution"] == "PASS"
    assert receipt["external_release"] == "REFUSE"
    assert receipt["authority_created"] is False
    assert len({row["composition_fingerprint"] for row in receipt["incarnations"]}) == 5
