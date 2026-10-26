from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from products.customer_artifact_bridge import (
    compose_customer_artifact_bridge,
    verify_customer_artifact_bridge,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = ROOT / "config" / "studio_harvest"
MANIFESTS = (
    "site_studio.json",
    "professional_correspondence_studio.json",
    "finance_readiness_studio.json",
    "article_publication_studio.json",
)


def _load(name: str) -> dict:
    return json.loads((MANIFEST_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("filename", MANIFESTS)
def test_customer_artifact_bridge_is_deterministic_and_verified(tmp_path: Path, filename: str) -> None:
    manifest = _load(filename)
    first = compose_customer_artifact_bridge(manifest=manifest, output_dir=tmp_path / "first")
    second = compose_customer_artifact_bridge(manifest=manifest, output_dir=tmp_path / "second")

    assert verify_customer_artifact_bridge(tmp_path / "first")["passed"] is True
    assert verify_customer_artifact_bridge(tmp_path / "second")["passed"] is True
    assert first["semantic_input_hash"] == second["semantic_input_hash"]
    assert first["semantic_visual_hash"] == second["semantic_visual_hash"]
    assert first["visual_svg_hash"] == second["visual_svg_hash"]
    assert first["authority_created"] is False
    assert first["external_effects"] is False
    assert first["automatic_publication"] == "REFUSE"


def test_customer_semantics_change_the_rendered_visual(tmp_path: Path) -> None:
    manifest = _load("finance_readiness_studio.json")
    changed = copy.deepcopy(manifest)
    changed["artifact_contract"]["venture"] = {
        "name": "Mhlabeni Solar Services",
        "business_model": "Installation and maintenance services for small commercial solar systems.",
        "funding_need": "R500,000 vehicle, tools and working-capital facility",
        "use_of_funds": ["service vehicle", "installation tools", "working capital"],
    }

    baseline = compose_customer_artifact_bridge(manifest=manifest, output_dir=tmp_path / "baseline")
    unseen = compose_customer_artifact_bridge(manifest=changed, output_dir=tmp_path / "unseen")

    assert baseline["semantic_input_hash"] != unseen["semantic_input_hash"]
    assert baseline["semantic_visual_hash"] != unseen["semantic_visual_hash"]
    assert baseline["visual_svg_hash"] != unseen["visual_svg_hash"]


def test_bridge_verifier_refuses_tampered_visual(tmp_path: Path) -> None:
    manifest = _load("site_studio.json")
    receipt = compose_customer_artifact_bridge(manifest=manifest, output_dir=tmp_path)
    svg = tmp_path / receipt["visual_svg"]
    svg.write_text(svg.read_text(encoding="utf-8") + "<!-- tampered -->\n", encoding="utf-8")

    verification = verify_customer_artifact_bridge(tmp_path)
    assert verification["passed"] is False
    assert any("visual_svg hash mismatch" in error for error in verification["errors"])
