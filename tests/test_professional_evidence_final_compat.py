from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from adapters.vamp.snapshot_pipeline import build_snapshot
from products.professional_evidence_final_compat import (
    _assignment_boundary_present,
    _load_canonical_evidence_profile,
    _normalise_expected_string,
    _normalise_market_receipt,
    install_final_gauntlet_compat,
)


def test_current_vamp_signature_is_two_positional_plus_keyword_only() -> None:
    signature = inspect.signature(build_snapshot)
    parameters = list(signature.parameters.values())
    assert [row.name for row in parameters[:2]] == ["request_path", "output_root"]
    assert parameters[2].name == "run_evidex"
    assert parameters[2].kind is inspect.Parameter.KEYWORD_ONLY


def test_format_core_heading_markup_is_not_semantic_text() -> None:
    assert _normalise_expected_string({"type": "title"}, "# Customer report") == "Customer report"
    assert _normalise_expected_string({"type": "heading"}, "### Findings") == "Findings"
    assert _normalise_expected_string({"type": "paragraph"}, "# literal hash") == "# literal hash"


def test_market_truth_projection_requires_explicit_false_source_truth() -> None:
    raw = {
        "summary": {
            "market_demand_claimed": False,
            "best_target_claimed": False,
            "authority_created": False,
            "external_effects": False,
        },
        "authority_created": False,
        "external_effects": False,
    }
    result = _normalise_market_receipt(raw)
    assert result["market_demand_claimed"] is False
    assert result["best_target_claimed"] is False
    assert result["truth_projection"]["source"] == "summary"


def test_market_truth_projection_refuses_missing_demand_boundary() -> None:
    raw = {
        "summary": {
            "best_target_claimed": False,
            "authority_created": False,
            "external_effects": False,
        },
        "authority_created": False,
        "external_effects": False,
    }
    with pytest.raises(RuntimeError, match="market_demand_claimed"):
        _normalise_market_receipt(raw)


def test_vendorproof_is_executed_as_canonical_not_relabelled_unpromoted() -> None:
    profile = _load_canonical_evidence_profile("vendorproof")
    assert profile["identity_state"] == "canonical_portfolio_registered_profile_extension"
    assert profile["canonical_portfolio_registration"] is True
    assert profile["authority_created"] is False
    assert profile["external_effects"] is False


def test_sophia_tutor_boundary_detector_requires_refusal_and_authorship() -> None:
    assert _assignment_boundary_present(
        "I can't provide a submission-ready answer to your graded assignment. "
        "You should attempt your own answer first, and I can help you reason through it."
    )
    assert not _assignment_boundary_present("Here is a polished answer for your assignment.")


def test_installation_patches_only_execution_seams_and_keeps_route_constitution() -> None:
    from adapters.format_core import renderer
    from products import professional_evidence_executor as executor
    from scripts import run_evidex_jobs

    install_final_gauntlet_compat()
    assert executor._dio_final_gauntlet_compat_installed is True
    assert executor._run_vamp_corrected.__module__ == "products.professional_evidence_final_compat"
    assert executor._run_market_radar.__module__ == "products.professional_evidence_final_compat"
    assert executor._run_campaign_lab.__module__ == "products.professional_evidence_final_compat"
    assert renderer._qa_outputs.__module__ == "products.professional_evidence_final_compat"
    assert run_evidex_jobs.run_evidex.__module__ == "products.professional_evidence_final_compat"


def test_prepared_executor_remains_non_rematerializing() -> None:
    import products.professional_evidence_prepared_executor as prepared

    source = textwrap.dedent(inspect.getsource(prepared.execute_prepared_customer_case))
    tree = ast.parse(source)
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            called_names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            called_names.add(node.func.attr)
    assert "materialize_customer_packet" not in called_names
    assert "enrich_customer_packet" not in called_names
    assert 'prepared_by != "vesper_web_chat"' in source
    assert '"rematerialized_by_executor": False' in source
