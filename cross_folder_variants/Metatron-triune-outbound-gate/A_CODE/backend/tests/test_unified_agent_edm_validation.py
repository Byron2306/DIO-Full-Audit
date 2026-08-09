"""Unit tests for EDM publish-time schema validation and quality gates."""

import ast
import sys
from pathlib import Path

ROUTERS_DIR = Path(__file__).resolve().parents[1] / "routers"


def _load_validator_from_source():
    """Extract validator code from unified_agent source without importing the full module."""
    module_path = ROUTERS_DIR / "unified_agent.py"
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    wanted_constants = {
        "EDM_MAX_RECORDS_PER_PUBLISH",
        "EDM_MIN_CANONICAL_COVERAGE",
        "EDM_MIN_ALLOWED_MIN_CONFIDENCE",
        "EDM_ALLOWED_CANDIDATE_TYPES",
    }
    wanted_functions = {
        "_normalize_edm_text",
        "_canonicalize_edm_record",
        "_validate_and_score_edm_dataset",
    }

    blocks = [
        "import json",
        "import os",
        "from typing import Any, Dict, List",
    ]

    for node in tree.body:
        if isinstance(node, ast.Assign):
            target_names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if target_names.intersection(wanted_constants):
                snippet = ast.get_source_segment(source, node)
                if snippet:
                    blocks.append(snippet)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted_functions:
            snippet = ast.get_source_segment(source, node)
            if snippet:
                blocks.append(snippet)

    namespace = {}
    exec("\n\n".join(blocks), namespace)
    return namespace["_validate_and_score_edm_dataset"]


_validate_and_score_edm_dataset = _load_validator_from_source()


def _valid_payload():
    return {
        "datasets": [
            {
                "dataset_id": "employee-pii",
                "precision": {
                    "min_confidence": 0.95,
                    "allowed_candidate_types": ["line", "delimited_bundle", "delimited_window_4"],
                },
                "records": [
                    {"record_id": "r1", "email": "alice@example.com", "name": "Alice"},
                    {"record_id": "r2", "email": "bob@example.com", "name": "Bob"},
                ],
            }
        ]
    }


def test_valid_payload_passes_schema_and_quality_gates():
    report = _validate_and_score_edm_dataset(_valid_payload())
    assert report["valid"] is True
    assert report["quality_gate_passed"] is True
    assert report["schema_errors"] == []
    assert report["quality_errors"] == []


def test_missing_datasets_list_fails_schema_validation():
    report = _validate_and_score_edm_dataset({"foo": "bar"})
    assert report["valid"] is False
    assert report["quality_gate_passed"] is False
    assert any("datasets" in err for err in report["schema_errors"])


def test_unknown_candidate_type_fails_quality_gate():
    payload = _valid_payload()
    payload["datasets"][0]["precision"]["allowed_candidate_types"] = ["line", "made_up_type"]

    report = _validate_and_score_edm_dataset(payload)
    assert report["valid"] is True
    assert report["quality_gate_passed"] is False
    assert any("unknown precision.allowed_candidate_types" in err for err in report["quality_errors"])


def test_low_canonical_coverage_fails_quality_gate():
    payload = {
        "datasets": [
            {
                "dataset_id": "low-coverage",
                "records": [
                    None,
                    "",
                    {},
                    {"record_id": "ok1", "value": "x"},
                ],
            }
        ]
    }

    report = _validate_and_score_edm_dataset(payload)
    assert report["valid"] is True
    assert report["quality_gate_passed"] is False
    assert any("canonical coverage" in err for err in report["quality_errors"])
