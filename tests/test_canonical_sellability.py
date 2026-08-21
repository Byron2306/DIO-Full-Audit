from __future__ import annotations

import copy
from pathlib import Path

from products import canonical_sellability as sellability
from products import professional_evidence_corpus as corpus
from products.portfolio_customer_surface import load_contract as load_surface_contract


def _safe_unseen_receipt() -> dict:
    return {
        "status": "PASS_FULL_PIPELINE",
        "terminal_artifact_kind": "education_deliverable",
        "vesper_web_chat_front_door_verified": True,
        "product_consumed_vesper_quarantined_bytes": True,
        "executor_rematerialized_packet": False,
        "human_review_required": True,
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "market_validation_claimed": False,
    }


def _artifact_row(path: Path) -> dict:
    return {
        "path": str(path.resolve()),
        "name": path.name,
        "suffix": path.suffix,
        "bytes": path.stat().st_size,
        "sha256": sellability._sha256(path),
    }


def _long_case_text(case: dict, *, marker: str = "") -> str:
    anchors = sellability._distinctive_anchors(case)
    body = " ".join(anchors)
    family = (
        " learner assessment curriculum exam moderation education teacher educator memo feedback "
        " review human judgement approval alignment source rubric criterion marks classroom "
    )
    return " ".join([body, marker, family * 8])


def _evaluate_education_product(tmp_path: Path, monkeypatch, *, marker_visible: bool = True, baseline_hash_valid: bool = True):
    contract = sellability.load_contract()
    base_case = copy.deepcopy(corpus.CASES["HOMS Assess"])
    unseen_case, mutation = sellability.mutate_unseen_case(base_case, "HOMS Assess", contract)

    baseline = tmp_path / "baseline.md"
    unseen = tmp_path / "unseen.md"
    baseline.write_text(_long_case_text(base_case), encoding="utf-8")
    unseen.write_text(
        _long_case_text(unseen_case, marker=mutation["marker"] if marker_visible else "MARKER-OMITTED") + " unseen distinct output",
        encoding="utf-8",
    )
    baseline_row = _artifact_row(baseline)
    if not baseline_hash_valid:
        baseline_row["sha256"] = "sha256:" + "0" * 64
    unseen_row = _artifact_row(unseen)

    def fake_unseen(**kwargs):
        return unseen_case, mutation, _safe_unseen_receipt()

    def fake_surface(*args, **kwargs):
        return {"state": "PASS", "selected": [unseen_row]}

    monkeypatch.setattr(sellability, "_run_or_reuse_unseen", fake_unseen)
    monkeypatch.setattr(sellability, "scan_customer_surface", fake_surface)

    return sellability._evaluate_product(
        incarnation="HOMS Assess",
        source={"suite": "Education & Research", "primary_family": "HOMS", "incarnation": "HOMS Assess"},
        execution_row={"all_variants_verified": True, "verified_count": 3},
        readiness_row={"production_readiness_status": "NEEDS_SELLABILITY_GRADE"},
        customer_surface_row={
            "surface_policy_id": "education_deliverable",
            "customer_surface_gate": {"selected": [baseline_row]},
        },
        product_dir=tmp_path / "product",
        contract=contract,
        surface_contract=load_surface_contract(),
        online=False,
        reuse_unseen=False,
    )


def test_contract_defines_six_families_and_100_point_grade() -> None:
    contract = sellability.load_contract()
    assert len(contract["family_policies"]) == 6
    assert sum(contract["dimensions"].values()) == 100
    assert contract["canonical_buyer_count"] == 47
    assert contract["threshold"] == 85


def test_unseen_mutation_is_deterministic_and_preserves_authority_boundary() -> None:
    contract = sellability.load_contract()
    base = copy.deepcopy(corpus.CASES["Sophia Review"])
    first, first_meta = sellability.mutate_unseen_case(base, "Sophia Review", contract)
    second, second_meta = sellability.mutate_unseen_case(base, "Sophia Review", contract)

    assert first == second
    assert first_meta == second_meta
    assert first["case_id"].endswith("-UNSEEN")
    assert first_meta["marker"].startswith("UCASE-")
    assert first_meta["marker"] in first["request"]
    assert first["authority_boundary"] == base["authority_boundary"]
    assert "baseline customer identity copied into unseen deliverable" in first["prohibited_outcomes"]


def test_family_quality_requires_multiple_semantic_signal_groups() -> None:
    contract = sellability.load_contract()
    policy = contract["family_policies"]["ai_assurance_deliverable"]
    good = sellability._family_quality(policy, "AI model control evidence assurance risk human review authority")
    weak = sellability._family_quality(policy, "model model model")

    assert good["passed"] is True
    assert good["matched_group_count"] >= 2
    assert weak["passed"] is False


def test_product_sellability_can_verify_clean_baseline_and_unseen_outputs(tmp_path: Path, monkeypatch) -> None:
    receipt = _evaluate_education_product(tmp_path, monkeypatch)

    assert receipt["sellability_status"] == "PRODUCT_SELLABILITY_VERIFIED"
    assert receipt["buyer_grade_candidate"] is True
    assert receipt["score"] >= 85
    assert receipt["critical_blockers"] == []
    assert receipt["unseen"]["generalisation_checks"]["marker_visible"] is True
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["commercial_validation"] == "UNPROVED"


def test_missing_unseen_marker_is_a_hard_stale_output_blocker(tmp_path: Path, monkeypatch) -> None:
    receipt = _evaluate_education_product(tmp_path, monkeypatch, marker_visible=False)

    assert receipt["sellability_status"] == "PRODUCT_SELLABILITY_REFUSE"
    assert "STALE_UNSEEN_ARTIFACT" in receipt["critical_blockers"]


def test_baseline_artifact_hash_drift_is_refused(tmp_path: Path, monkeypatch) -> None:
    receipt = _evaluate_education_product(tmp_path, monkeypatch, baseline_hash_valid=False)

    assert receipt["sellability_status"] == "PRODUCT_SELLABILITY_REFUSE"
    assert "BASELINE_CUSTOMER_ARTIFACT_FAILURE" in receipt["critical_blockers"]


def test_canonical_receipt_fingerprint_detects_tampering() -> None:
    receipt = {
        "schema": sellability.SCHEMA,
        "products": {"HOMS Assess": {"sellability_status": sellability.VERIFIED}},
        "authority_created": False,
        "external_effects": False,
    }
    receipt["receipt_fingerprint"] = sellability._fingerprint(receipt)
    assert sellability._verify_fingerprint(receipt, "receipt_fingerprint") is True

    receipt["products"]["HOMS Assess"]["sellability_status"] = sellability.REFUSE
    assert sellability._verify_fingerprint(receipt, "receipt_fingerprint") is False
