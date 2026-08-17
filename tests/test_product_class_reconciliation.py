from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_product_class_reconciliation import ROOT, audit_reconciliation


RECONCILIATION = ROOT / "config" / "product_class_reconciliation.json"
ROUTES = ROOT / "config" / "product_class_routes.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_reconciliation_partitions_all_38_atlas_profile_extensions() -> None:
    reconciliation = read_json(RECONCILIATION)
    routes = read_json(ROUTES)

    exact = set(reconciliation["exact_canonical_incarnations"])
    candidates = set(reconciliation["equivalence_candidates"])
    resolved = set(reconciliation["resolved_composition_bindings"])
    extensions = set(reconciliation["genuine_profile_extensions"])

    assert len(exact) == 6
    assert len(candidates) == 2
    assert len(resolved) == 2
    assert len(extensions) == 28

    partitions = [exact, candidates, resolved, extensions]
    for index, left in enumerate(partitions):
        for right in partitions[index + 1:]:
            assert not (left & right)

    assert exact | candidates | resolved | extensions == set(routes["product_classes"])


def test_exact_canonical_incarnations_are_real_executable_internal_manifests() -> None:
    result = audit_reconciliation()

    assert result["state"] == "reconciled", result["errors"]
    assert result["summary"]["exact_canonical_incarnations"] == 6
    for product_class, row in result["exact_canonical_incarnations"].items():
        assert row["manifest_exists"], product_class
        assert row["product_id_match"], product_class
        assert row["executor_bound"], product_class
        assert row["maturity"] == "internal_proof", product_class
        assert row["routable"] is True, product_class
        assert row["governable"] is True, product_class
        assert row["executable"] is True, product_class
        assert row["externally_validated"] is False, product_class
        assert row["campaign_enabled"] is False, product_class
        assert row["route_auto_promotable"] is False, product_class


def test_exact_bindings_are_the_known_canonical_products() -> None:
    reconciliation = read_json(RECONCILIATION)
    exact = reconciliation["exact_canonical_incarnations"]

    assert set(exact) == {
        "grantproof",
        "tenderproof",
        "permitproof",
        "policyproof",
        "contractproof",
        "agent_authority",
    }
    assert exact["grantproof"]["canonical_product_id"] == "dio_grantproof"
    assert exact["tenderproof"]["canonical_product_id"] == "dio_tenderproof"
    assert exact["permitproof"]["canonical_product_id"] == "dio_permitproof"
    assert exact["policyproof"]["canonical_product_id"] == "dio_policyproof"
    assert exact["contractproof"]["canonical_product_id"] == "dio_contractproof"
    assert exact["agent_authority"]["canonical_product_id"] == "dio_agentauthority"


def test_contractproof_reconciliation_preserves_vesper_inbound_ownership() -> None:
    reconciliation = read_json(RECONCILIATION)
    contractproof = reconciliation["exact_canonical_incarnations"]["contractproof"]

    assert contractproof["inbound_owner"] == "vesper"
    assert "Vesper-bound intake" in contractproof["next_gate"]


def test_equivalence_candidates_remain_review_only() -> None:
    result = audit_reconciliation()
    reconciliation = read_json(RECONCILIATION)

    assert set(reconciliation["equivalence_candidates"]) == {
        "changeproof",
        "dio_ai_assurance",
    }
    for product_class, row in result["equivalence_candidates"].items():
        assert row["manifest_exists"], product_class
        assert row["candidate_id_match"], product_class
        assert row["state"] == "equivalence_review_required", product_class
        assert row["route_auto_promotable"] is False, product_class


def test_resolved_composition_bindings_reject_aliases_but_preserve_reuse() -> None:
    result = audit_reconciliation()
    reconciliation = read_json(RECONCILIATION)

    assert set(reconciliation["resolved_composition_bindings"]) == {
        "homs_accreditation",
        "dio_regops",
    }
    assert result["summary"]["resolved_composition_bindings"] == 2

    homs = result["resolved_composition_bindings"]["homs_accreditation"]
    assert homs["canonical_product_id"] == "dio_accreditation"
    assert homs["canonical_product_exists"] is True
    assert homs["component_id_match"] is True
    assert homs["relationship"] == "composition_reuse"
    assert homs["state"] == "identity_equivalence_rejected"
    assert homs["route_auto_promotable"] is False

    regops = result["resolved_composition_bindings"]["dio_regops"]
    assert regops["canonical_product_id"] == "dio_regops"
    assert regops["canonical_product_exists"] is True
    assert regops["component_id_match"] is True
    assert regops["relationship"] == "composition_reuse"
    assert regops["state"] == "identity_equivalence_rejected"
    assert regops["route_auto_promotable"] is False


def test_reconciliation_grants_no_launch_or_auto_promotion_authority() -> None:
    reconciliation = read_json(RECONCILIATION)
    result = audit_reconciliation()

    assert reconciliation["summary"]["auto_promotable_from_reconciliation"] == 0
    assert reconciliation["summary"]["public_launch_authorized_from_reconciliation"] == 0
    assert result["summary"]["auto_promotable_from_reconciliation"] == 0
    assert result["summary"]["public_launch_authorized_from_reconciliation"] == 0
