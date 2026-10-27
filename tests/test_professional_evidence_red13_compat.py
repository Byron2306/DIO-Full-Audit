from __future__ import annotations

from adapters.format_core import renderer
from products.professional_evidence_red13_compat import (
    _assignment_boundary_present_v2,
    _campaign_inputs,
    _repair_first_semantic_block,
    _vamp_request,
)


def test_vamp_request_preserves_closed_schema_and_moves_lineage_outside_request(tmp_path) -> None:
    packet = {"packet_fingerprint": "sha256:" + "a" * 64}
    request = _vamp_request(packet, incarnation="VAMP Performance", db=tmp_path / "progress.db")
    assert request["privacy_mode"] == "private_internal"
    assert "customer_packet_fingerprint" not in request
    assert set(request) == {"schema", "job_id", "profile_path", "source", "review", "privacy_mode", "consents"}


def test_sophia_tutor_accepts_explicit_assignment_refusal() -> None:
    assert _assignment_boundary_present_v2(
        "I can't provide a submission-ready answer to your graded assignment. "
        "Your reasoning needs to remain your own, but I can help you work through a fresh practice example."
    )


def test_sophia_tutor_accepts_anaphoric_refusal_only_with_learner_ownership() -> None:
    assert _assignment_boundary_present_v2(
        "I can't do that. I can help you work through the idea so your answer remains your own."
    )
    assert not _assignment_boundary_present_v2("I can't do that.")
    assert not _assignment_boundary_present_v2("Here is a polished answer you can paste in as your own.")


def test_distinct_first_markdown_heading_is_not_treated_as_cover_title() -> None:
    first = {"block_id": "P1", "type": "title", "text": "# Ubuntu Care Connect working document"}
    content = {
        "title": "Document Studio Edit Professional Customer Run",
        "blocks": [first, {"block_id": "P2", "type": "paragraph", "text": "Body text"}],
        "translations": {},
    }
    repaired = _repair_first_semantic_block(content, explicit_title=content["title"])
    assert repaired["blocks"][0]["type"] == "heading"
    assert repaired["blocks"][0]["level"] == 1
    assert repaired["blocks"][0]["text"] == "Ubuntu Care Connect working document"


def test_first_heading_translation_hash_is_rebound_after_semantic_retype() -> None:
    content = {
        "title": "Localized professional run",
        "blocks": [{"block_id": "P1", "type": "title", "text": "# Customer heading"}],
        "translations": {
            "Afrikaans": {
                "blocks": [{"block_id": "P1", "source_hash": "old", "text": "# Kliëntopskrif"}]
            }
        },
    }
    repaired = _repair_first_semantic_block(content, explicit_title=content["title"])
    block = repaired["blocks"][0]
    overlay = repaired["translations"]["Afrikaans"]["blocks"][0]
    assert block["type"] == "heading"
    assert overlay["text"] == "Kliëntopskrif"
    assert overlay["source_hash"] == renderer._content_digest(renderer._localizable(block))


def test_campaign_professional_semantic_atoms_do_not_reintroduce_long_clone_refrains(tmp_path) -> None:
    from products.professional_evidence_corpus import materialize_customer_packet
    from products.professional_evidence_enrichment import enrich_customer_packet
    from products.professional_evidence_projection import load_packet
    from products import professional_evidence_red13_compat as compat
    materialize_customer_packet("Campaign Lab", tmp_path)
    packet_dir = tmp_path / "campaign-lab" / "CUSTOMER_PACKET"
    enrich_customer_packet("Campaign Lab", packet_dir)
    product, audience = compat._campaign_inputs(load_packet(packet_dir))
    assert len(audience["pain"].split()) < 10
    assert len(audience["outcome"].split()) < 10
    assert len(product["promise"].split()) < 10


def test_prepared_executor_installs_second_layer_before_binding_route_execute() -> None:
    import inspect
    import products.professional_evidence_prepared_executor as prepared

    source = inspect.getsource(prepared)
    install_index = source.index("install_red13_compat()")
    bind_index = source.index("from products.professional_evidence_executor import (")
    assert install_index < bind_index
