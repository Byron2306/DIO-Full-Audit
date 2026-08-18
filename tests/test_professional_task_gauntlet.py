from __future__ import annotations

import json
from pathlib import Path

from products.professional_task_gauntlet import build_task_manifest
from products.professional_task_packets import (
    BASE_MANIFESTS,
    TIERS,
    load_case,
    load_portfolio,
    materialize_case_packet,
)

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
