from __future__ import annotations

import json
from pathlib import Path

from adapters.lingua.communicator import plain_text_from_html
from presence_core.router import route_message
from products.professional_task_gauntlet import build_task_manifest
from products.professional_task_packets import (
    BASE_MANIFESTS,
    TIERS,
    load_case,
    load_portfolio,
    materialize_case_packet,
)
from products.studio_customer_delivery import render_customer_delivery

ROOT = Path(__file__).resolve().parents[1]


def test_professional_task_portfolio_has_twelve_balanced_cases():
    portfolio = load_portfolio(root=ROOT)
    assert portfolio["case_count"] == 12
    assert set(portfolio["studios"]) == set(BASE_MANIFESTS)
    ids = []
    for studio_id, tiers in portfolio["studios"].items():
        assert set(tiers) == set(TIERS)
        ids.extend(tiers.values())
    assert len(ids) == 12
    assert len(set(ids)) == 12


def test_professional_task_cases_have_no_desired_final_copy():
    portfolio = load_portfolio(root=ROOT)
    for tiers in portfolio["studios"].values():
        for case_id in tiers.values():
            case = load_case(case_id, root=ROOT)
            serialized = json.dumps(case, sort_keys=True).casefold()
            assert '"final_copy"' not in serialized
            assert '"golden_output"' not in serialized
            assert case["source_documents"]
            assert case["expected_facts"]
            assert case["authority_boundary"]["human_gate"] == "NEEDS_YOU"


def test_examiner_truth_is_withheld_from_studio_manifest():
    portfolio = load_portfolio(root=ROOT)
    for tiers in portfolio["studios"].values():
        for case_id in tiers.values():
            case = load_case(case_id, root=ROOT)
            manifest = build_task_manifest(case, root=ROOT)
            task_input = manifest["professional_task_input"]
            assert "expected_facts" not in task_input
            assert "prohibited_inventions" not in task_input
            assert "acceptance_rubric" not in task_input
            assert task_input["case_id"] == case_id
            assert manifest["job"]["source_request"] == case["job"]["request"]
            assert case["job"]["request"] in manifest["job"]["request"]


def test_all_projected_professional_tasks_enter_expected_vesper_intake_route():
    portfolio = load_portfolio(root=ROOT)
    routes = ROOT / "config" / "routes.json"
    for studio_id, tiers in portfolio["studios"].items():
        for case_id in tiers.values():
            case = load_case(case_id, root=ROOT)
            manifest = build_task_manifest(case, root=ROOT)
            decision = route_message(manifest["job"]["request"], "public", routes).as_dict()
            assert decision["intent"] == "intake_request", (case_id, decision)
            assert decision["product"] == studio_id, (case_id, decision)
            assert decision["source"] == "deterministic", (case_id, decision)


def test_site_professional_delivery_preserves_supported_case_facts_and_rejects_poison(tmp_path: Path):
    portfolio = load_portfolio(root=ROOT)
    for case_id in portfolio["studios"]["site_studio"].values():
        case = load_case(case_id, root=ROOT)
        manifest = build_task_manifest(case, root=ROOT)
        out = tmp_path / case_id
        receipt = render_customer_delivery(manifest=manifest, output_dir=out)
        primary = out / receipt["primary_artifact"]
        text = plain_text_from_html(primary.read_text(encoding="utf-8")).casefold()

        for expected in case["expected_facts"]:
            assert any(str(value).casefold() in text for value in expected["any_of"]), (case_id, expected)
        for prohibited in case["prohibited_inventions"]:
            assert not any(str(value).casefold() in text for value in prohibited["patterns"]), (case_id, prohibited)
        poison = case.get("poisoned_instruction")
        if poison:
            assert not any(str(value).casefold() in text for value in poison["must_not_assert"]), case_id
            assert any(str(value).casefold() in text for value in poison["safe_alternative_terms"]), case_id

        assert "professional_task_input.source_documents" in receipt["input_fields_used"]
        assert receipt["external_effects"] is False
        assert receipt["authority_created"] is False


def test_packet_materialisation_uses_professional_exam_layout(tmp_path: Path):
    case = load_case("correspondence_adversarial_executive_instruction", root=ROOT)
    packet = materialize_case_packet(case, output_dir=tmp_path)
    assert (packet / "JOB.md").is_file()
    assert (packet / "SOURCES").is_dir()
    assert len(list((packet / "SOURCES").iterdir())) == len(case["source_documents"])
    assert (packet / "CONSTRAINTS.json").is_file()
    assert (packet / "EXPECTED_FACTS.json").is_file()
    assert (packet / "PROHIBITED_INVENTIONS.json").is_file()
    assert (packet / "AUTHORITY_BOUNDARY.json").is_file()
    assert (packet / "ACCEPTANCE_RUBRIC.json").is_file()
