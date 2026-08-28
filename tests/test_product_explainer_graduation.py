from __future__ import annotations

import json
from pathlib import Path


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_ready_semantic_graduation_writes_five_custody_artifacts_without_render(tmp_path, monkeypatch):
    from scripts import run_product_explainer_graduation as runner

    manifest = {
        "product_id": "HOMS",
        "product_name": "HOMS",
        "authority": {"external_publication": "NEEDS_YOU", "media_spend": "REFUSE"},
    }
    compiled = {
        "semantic_readiness": "READY",
        "missing": [],
        "manifest": manifest,
        "manifest_sha256": "sha256:abc",
        "claim_envelope": {"allowed": [{"claim_id": "CLM-1"}], "qualified": [], "forbidden": []},
    }
    calls = {"render": 0}
    monkeypatch.setattr(runner, "compile_product_explainer", lambda *a, **k: compiled)
    monkeypatch.setattr(
        runner,
        "build_explainer_script_package",
        lambda m: {"title": "HOMS", "scenes": [{"scene_id": "scene_01"}]},
    )
    monkeypatch.setattr(runner, "semantic_challenge", lambda m, s: {"state": "PASS", "codes": []})
    monkeypatch.setattr(
        runner,
        "build_media_production_request",
        lambda c, **k: {
            "request_id": "MPR-1",
            "release": {"external_publication": "NEEDS_YOU", "media_spend": "REFUSE"},
        },
    )
    monkeypatch.setattr(
        runner,
        "build_premium_media",
        lambda **k: calls.__setitem__("render", calls["render"] + 1),
    )

    receipt = runner.run_graduation(
        product_id="homs",
        root=tmp_path,
        output_dir=tmp_path / "out",
        render=False,
    )

    assert receipt["acceptance_token"] == "DIO_PRODUCT_EXPLAINER_GRADUATION_READY"
    assert receipt["semantic_graduation"] == "PASS"
    assert receipt["render_state"] == "NOT_REQUESTED"
    assert calls["render"] == 0
    expected = {
        "PRODUCT_EXPLAINER_MANIFEST.json",
        "CLAIM_ENVELOPE.json",
        "EXPLAINER_SCRIPT_PACKAGE.json",
        "SEMANTIC_CHALLENGE.json",
        "MEDIA_PRODUCTION_REQUEST.json",
    }
    assert set(receipt["custody_artifacts"]) == expected
    assert all((tmp_path / "out" / name).is_file() for name in expected)
    assert _load(tmp_path / "out" / "GRADUATION_RECEIPT.json")["human_gate"] == "NEEDS_YOU"


def test_incomplete_truth_refuses_graduation_and_does_not_render(tmp_path, monkeypatch):
    from scripts import run_product_explainer_graduation as runner

    monkeypatch.setattr(
        runner,
        "compile_product_explainer",
        lambda *a, **k: {
            "semantic_readiness": "NEEDS_EVIDENCE",
            "missing": ["how_it_works"],
            "manifest": None,
            "manifest_sha256": None,
            "claim_envelope": {"allowed": [], "qualified": [], "forbidden": []},
        },
    )
    called = {"render": False}
    monkeypatch.setattr(
        runner,
        "build_premium_media",
        lambda **k: called.__setitem__("render", True),
    )

    receipt = runner.run_graduation(
        product_id="homs",
        root=tmp_path,
        output_dir=tmp_path / "out",
        render=True,
    )

    assert receipt["semantic_graduation"] == "REFUSE"
    assert receipt["acceptance_token"] == "DIO_PRODUCT_EXPLAINER_GRADUATION_REFUSED"
    assert receipt["missing"] == ["how_it_works"]
    assert receipt["render_state"] == "REFUSE"
    assert called["render"] is False


def test_render_is_invoked_only_when_explicitly_requested(tmp_path, monkeypatch):
    from scripts import run_product_explainer_graduation as runner

    compiled = {
        "semantic_readiness": "READY",
        "missing": [],
        "manifest": {"product_id": "HOMS", "product_name": "HOMS"},
        "manifest_sha256": "sha256:abc",
        "claim_envelope": {"allowed": [], "qualified": [], "forbidden": []},
    }
    monkeypatch.setattr(runner, "compile_product_explainer", lambda *a, **k: compiled)
    monkeypatch.setattr(
        runner,
        "build_explainer_script_package",
        lambda m: {"title": "HOMS", "scenes": [{"scene_id": "scene_01"}]},
    )
    monkeypatch.setattr(runner, "semantic_challenge", lambda m, s: {"state": "PASS", "codes": []})
    monkeypatch.setattr(
        runner,
        "build_media_production_request",
        lambda c, **k: {"request_id": "MPR-1"},
    )
    calls = []
    monkeypatch.setattr(
        runner,
        "build_premium_media",
        lambda **kwargs: calls.append(kwargs) or {"receipt": {"premium_video": "PASS"}},
    )

    receipt = runner.run_graduation(
        product_id="homs",
        root=tmp_path,
        output_dir=tmp_path / "out",
        render=True,
        provider="imported",
    )

    assert receipt["render_state"] == "PASS"
    assert len(calls) == 1
    assert calls[0]["script_package"]["title"] == "HOMS"
    assert calls[0]["production_request"]["request_id"] == "MPR-1"
    assert calls[0]["provider"] == "imported"
