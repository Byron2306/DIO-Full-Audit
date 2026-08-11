from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


REQUIRED_BEFORE_DEIFICATION = {
    "dio_core",
    "vesper_presence",
    "sophia_integritas",
    "valinor",
    "beast",
    "metatron",
    "arda",
    "seraph",
    "phoenix",
    "evidex",
    "vamp",
    "homs",
    "outlook_triage",
    "microsoft_graph",
    "nichefoundry",
    "document_studio",
    "lingua",
    "format_core",
    "legalis",
    "market_command",
    "commerce_autorelease",
    "dio_product_platform",
    "dio_workflows_site",
}


def _registry() -> dict:
    return json.loads(Path("config/dio_fusion_registry.json").read_text(encoding="utf-8"))


def test_fusion_registry_validates_against_schema() -> None:
    schema = json.loads(Path("schemas/dio_fusion_registry.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(_registry())


def test_every_mandatory_system_is_explicitly_in_the_fusion_set() -> None:
    registry = _registry()
    systems = {row["system_id"]: row for row in registry["systems"]}
    assert REQUIRED_BEFORE_DEIFICATION <= set(systems)
    assert {key for key, row in systems.items() if row["must_participate_before_deification"]} == REQUIRED_BEFORE_DEIFICATION
    assert all(systems[key]["authority_boundary"] for key in REQUIRED_BEFORE_DEIFICATION)
    assert all(systems[key]["sources"] for key in REQUIRED_BEFORE_DEIFICATION)


def test_outlook_is_an_executor_not_an_autonomous_authority() -> None:
    row = next(item for item in _registry()["systems"] if item["system_id"] == "outlook_triage")
    assert row["disposition"] == "capability_executor"
    bounded = " ".join(row["bounded"]).lower()
    assert "send" in bounded and "reply" in bounded and "form filling" in bounded
    assert "human approval" in row["authority_boundary"].lower()
    assert "valinor" in row["authority_boundary"].lower()


def test_seraph_current_candidate_and_no_execution_authority_are_recorded() -> None:
    row = next(item for item in _registry()["systems"] if item["system_id"] == "seraph")
    refs = {source["ref"]: source for source in row["sources"]}
    assert "Byron2306/Seraph-AI-12" in refs
    assert refs["Byron2306/Seraph-AI-12"]["sha"] == "510816f60ff0ddd2600e8f8de85d138e87b603bd"
    assert "cannot authorize release" in " ".join(row["bounded"]).lower()
    assert "valinor" in row["authority_boundary"].lower()


def test_legacy_presence_is_explicitly_retired_not_fused_as_parallel_authority() -> None:
    row = next(item for item in _registry()["systems"] if item["system_id"] == "legacy_presence_repos")
    assert row["disposition"] == "legacy_retire"
    assert row["must_participate_before_deification"] is False
    refs = {source["ref"] for source in row["sources"]}
    assert {"Byron2306/Lilith", "Byron2306/L1l1th", "Byron2306/lilith_minimal"} <= refs


def test_websites_and_variants_are_not_runtime_organs() -> None:
    systems = {row["system_id"]: row for row in _registry()["systems"]}
    assert systems["product_marketing_sites"]["disposition"] == "surface"
    assert systems["noedge_multi_hymark"]["disposition"] == "reference_only"
    assert systems["seraph_mitre"]["disposition"] == "reference_only"
    assert systems["legacy_vamp_variants"]["disposition"] == "reference_only"
