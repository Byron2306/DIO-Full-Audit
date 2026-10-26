from __future__ import annotations

import copy
from pathlib import Path

import pytest

from products.compiler import (
    CompilerError,
    bind_profiles,
    compile_manifest,
    load_capability_catalog,
    load_json,
    load_meta_capabilities,
    load_profile_index,
    load_work_patterns,
    validate_manifest_schema,
    validate_pattern_meta_composition,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "products" / "manifests" / "contractproof.json"


def test_contractproof_compilation_is_deterministic_and_never_autonomously_authoritative() -> None:
    first = compile_manifest(ROOT, MANIFEST)
    second = compile_manifest(ROOT, MANIFEST)
    assert first["composition_fingerprint"] == second["composition_fingerprint"]
    assert first["compilation_fingerprint"] == second["compilation_fingerprint"]
    assert first["compiler_provenance"]["source_ref"] == "products/compiler.py"
    assert first["compiler_provenance"]["source_sha256"].startswith("sha256:")
    assert first["gates"]["composition"]["state"] == "ALLOW"
    assert first["gates"]["planning"]["state"] in {"ALLOW", "NEEDS_IMPLEMENTATION"}
    assert first["gates"]["execution"]["state"] in {"REFUSE", "NEEDS_YOU"}
    assert first["gates"]["execution"]["state"] != "ALLOW"
    assert first["gates"]["human_review"]["state"] == "NEEDS_YOU"
    assert first["gates"]["external_release"]["state"] == "REFUSE"


def test_manifest_cannot_wire_organs_directly() -> None:
    manifest = load_json(MANIFEST)
    manifest["organs"] = ["Evidex"]
    with pytest.raises(CompilerError, match="Additional properties are not allowed"):
        validate_manifest_schema(ROOT, manifest)


def test_work_pattern_meta_dependencies_are_mandatory() -> None:
    manifest = load_json(MANIFEST)
    manifest["meta_capabilities"] = ["meta_evidence", "meta_assurance", "meta_room"]
    patterns, _ = load_work_patterns(ROOT)
    meta, _ = load_meta_capabilities(ROOT)
    with pytest.raises(CompilerError, match="META composition incomplete"):
        validate_pattern_meta_composition(manifest, patterns, meta)


def test_profile_hash_tamper_is_refused() -> None:
    manifest = copy.deepcopy(load_json(MANIFEST))
    manifest["profiles"]["framework"][0]["content_hash"] = "sha256:" + ("0" * 64)
    index = load_profile_index(ROOT)
    with pytest.raises(CompilerError, match="profile content hash mismatch"):
        bind_profiles(ROOT, manifest, index)


def test_capitalroom_is_never_assumed_generic_for_contractproof() -> None:
    compiled = compile_manifest(ROOT, MANIFEST)
    capabilities = {row["capability_id"]: row for row in compiled["capability_plan"]}
    catalog, _ = load_capability_catalog(ROOT)
    capitalroom = next(row for row in catalog["proof.room.compile"]["providers"] if row["provider_id"] == "capitalroom_proof_room")
    assert "dio_contractproof" not in capitalroom["product_scope"]
    room = capabilities["proof.room.compile"]
    if room["resolution_state"] == "RESOLVED":
        assert room["provider"]["provider_id"] != "capitalroom_proof_room"
    else:
        assert room["resolution_state"] == "UNAVAILABLE"
        assert "no earned provider declares applicability" in room["reason"]


def test_capability_frontier_is_truthful_as_later_phases_earn_providers() -> None:
    compiled = compile_manifest(ROOT, MANIFEST)
    capabilities = {row["capability_id"]: row for row in compiled["capability_plan"]}
    catalog, _ = load_capability_catalog(ROOT)
    tracked = (
        "obligation.extract",
        "obligation.normalize",
        "obligation.deadlines",
        "obligation.evaluate",
        "product.executor.contractproof",
    )
    for capability_id in tracked:
        expected = "RESOLVED" if catalog[capability_id]["status"] == "available" else "PLANNED"
        assert capabilities[capability_id]["resolution_state"] == expected


def test_earned_generic_capabilities_resolve() -> None:
    compiled = compile_manifest(ROOT, MANIFEST)
    capabilities = {row["capability_id"]: row for row in compiled["capability_plan"]}
    for capability_id in ("case.materialize", "evidence.provenance", "evidence.link"):
        assert capabilities[capability_id]["resolution_state"] == "RESOLVED"
        assert capabilities[capability_id]["provider"] is not None
