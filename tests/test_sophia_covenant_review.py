"""The recovery handoff must require assent to the exact reviewed covenant."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/manage_sophia_covenant.py"


@pytest.fixture(autouse=True)
def standalone_cli_backend_namespace():
    """Model the standalone CLI without inheriting other backend test imports.

    The production guard still refuses a foreign cached service. Other tests
    deliberately load unrelated backends into this shared pytest interpreter.
    """
    prior = {key: value for key, value in sys.modules.items() if key == 'backend' or key.startswith('backend.')}
    for key in prior:
        sys.modules.pop(key, None)
    try:
        yield
    finally:
        for key in list(sys.modules):
            if key == 'backend' or key.startswith('backend.'):
                sys.modules.pop(key, None)
        sys.modules.update(prior)


def helper():
    assert SCRIPT.exists(), "Missing review-bound Sophia covenant handoff"
    spec = importlib.util.spec_from_file_location("covenant_handoff", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def draft(tmp_path):
    module = helper()
    identity = tmp_path / "identity.json"
    identity.write_text(json.dumps({"payload": {"name": "Recovery Test Principal", "core_values": ["truth"], "additional_context": "Preserve this offered context"}, "record": {"principal_identity_hash": "historical-hash"}}))
    target = tmp_path / "mandos"
    review = module.build_review(identity, target)
    return module, review, identity, target


def test_review_is_read_only_and_preserves_offered_semantics(tmp_path):
    module, review, identity, target = draft(tmp_path)
    assert not target.exists()
    assert review["sealed"] is False
    assert review["principal"]["offered_identity"]["core_values"] == ["truth"]
    assert review["principal"]["current_identity"]["additional_context"] == "Preserve this offered context"
    assert review["principal"]["historical_identity_hash"] == "historical-hash"
    assert review["review_sha256"] == module.review_digest(review)
    assert review["articles"]["genesis"]
    assert review["terms"]["calibration_consent"] is False


@pytest.mark.parametrize("affirmed,digest", [(False, "correct"), (True, "wrong")])
def test_seal_refuses_missing_affirmation_or_wrong_review_hash(tmp_path, affirmed, digest):
    module, review, identity, target = draft(tmp_path)
    accepted = review["review_sha256"] if digest == "correct" else "0" * 64
    with pytest.raises(ValueError, match="affirmation|review hash"):
        module.seal_review(review, accepted, affirmed)
    assert not target.exists()


def test_seal_refuses_tampered_terms_even_with_original_acceptance_hash(tmp_path):
    module, review, identity, target = draft(tmp_path)
    accepted = review["review_sha256"]
    review["terms"]["calibration_consent"] = True
    with pytest.raises(ValueError, match="review hash"):
        module.seal_review(review, accepted, True)
    assert not target.exists()


def test_seal_refuses_identity_source_change(tmp_path):
    module, review, identity, target = draft(tmp_path)
    identity.write_text(json.dumps({"payload": {"name": "Someone Else"}}))
    with pytest.raises(ValueError, match="identity source changed"):
        module.seal_review(review, review["review_sha256"], True)
    assert not target.exists()


def test_seal_refuses_source_or_runtime_drift_before_writing(tmp_path):
    module, review, identity, target = draft(tmp_path)
    review["source_hashes"]["coronation_service.py"] = "0" * 64
    review["review_sha256"] = module.review_digest(review)
    with pytest.raises(ValueError, match="current source|review has changed"):
        module.seal_review(review, review["review_sha256"], True)
    assert not target.exists()


def test_existing_runtime_covenant_cannot_be_replaced(tmp_path):
    module, review, identity, target = draft(tmp_path)
    directory = target / "covenants/constitutional"
    directory.mkdir(parents=True)
    (directory / "existing_manifest.json").write_text('{"payload":{"state":"sealed"}}')
    with pytest.raises(ValueError, match="existing covenant"):
        module.seal_review(review, review["review_sha256"], True)


def test_historical_register_is_renamed_without_losing_its_value(tmp_path):
    module = helper()
    source = tmp_path / "identity.json"
    source.write_text(json.dumps({"payload": {"name": "Test Principal", "register": "collaborative", "encounter_mode": "socratic"}}))
    review = module.build_review(source, tmp_path / "mandos")
    assert review["principal"]["current_identity"]["identity_register"] == "collaborative"
    assert review["principal"]["current_identity"]["encounter_mode"] == "socratic"
    assert review["principal"]["field_migrations"] == {"register": "identity_register"}


def test_unknown_offered_field_cannot_be_silently_dropped(tmp_path):
    module = helper()
    source = tmp_path / "identity.json"
    source.write_text(json.dumps({"payload": {"name": "Test Principal", "unknown_preference": "preserve"}}))
    with pytest.raises(ValueError, match="explicit migration review"):
        module.build_review(source, tmp_path / "mandos")
