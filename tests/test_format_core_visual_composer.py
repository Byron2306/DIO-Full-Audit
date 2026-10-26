from __future__ import annotations

import json
from pathlib import Path

from adapters.format_core.visual_composer import (
    SCHEMA,
    content_hash,
    render_svg,
    validate_composition,
    write_visual_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILES = json.loads((ROOT / "config" / "visual_profiles.json").read_text(encoding="utf-8"))


def sample_composition() -> dict:
    return {
        "schema": SCHEMA,
        "composition_id": "DIO-VISUAL-TEST-001",
        "title": "Format Core Visual Composition",
        "profile_id": "site_editorial_dark",
        "canvas": {"width": 1280, "height": 720, "background": "$paper"},
        "components": [
            {"id": "eyebrow", "kind": "badge", "x": 76, "y": 64, "width": 220, "text": "FORMAT CORE"},
            {
                "id": "headline",
                "kind": "text",
                "x": 76,
                "y": 180,
                "text": "Meaning first. Composition second.",
                "size": 54,
                "weight": "900",
                "wrap_chars": 34,
                "max_lines": 2,
                "line_gap": 62
            },
            {
                "id": "organ-flow",
                "kind": "process",
                "x": 76,
                "y": 330,
                "width": 1128,
                "steps": ["Semantic object", "Visual law", "SVG composition", "Governed artifact"]
            },
            {
                "id": "proof-cards",
                "kind": "cards",
                "x": 76,
                "y": 470,
                "width": 1128,
                "height": 180,
                "columns": 3,
                "items": [
                    {"title": "Deterministic", "body": "The same composition and profile produce the same SVG bytes."},
                    {"title": "Profile-driven", "body": "Assessment, editorial, and professional visual laws remain explicit."},
                    {"title": "Governed", "body": "Composition hashes and output hashes are captured in a receipt."}
                ]
            }
        ]
    }


def test_composition_validates() -> None:
    result = validate_composition(sample_composition(), PROFILES)
    assert result["passed"] is True
    assert result["component_count"] == 4


def test_svg_is_deterministic() -> None:
    composition = sample_composition()
    first = render_svg(composition, PROFILES)
    second = render_svg(composition, PROFILES)
    assert first == second
    assert content_hash(composition) == content_hash(json.loads(json.dumps(composition)))
    assert '<svg xmlns="http://www.w3.org/2000/svg"' in first
    assert "dio-visual-arrow" in first
    assert "Meaning first. Composition second." in first


def test_duplicate_component_ids_fail_closed() -> None:
    composition = sample_composition()
    composition["components"].append(dict(composition["components"][0]))
    result = validate_composition(composition, PROFILES)
    assert result["passed"] is False
    assert any("duplicate component id" in error for error in result["errors"])


def test_unknown_profile_fails_closed() -> None:
    composition = sample_composition()
    composition["profile_id"] = "gamma_magic_soup"
    result = validate_composition(composition, PROFILES)
    assert result["passed"] is False
    assert any("Unknown visual profile" in error for error in result["errors"])


def test_bundle_writes_svg_and_receipt_without_requiring_ffmpeg(tmp_path: Path) -> None:
    receipt = write_visual_bundle(sample_composition(), tmp_path, profiles=PROFILES, rasterize=False)
    assert receipt["state"] == "PASS"
    assert receipt["authority_created"] is False
    assert receipt["automatic_publication"] == "REFUSE"
    assert Path(receipt["svg"]).exists()
    assert Path(receipt["receipt"]).exists()
    assert receipt["png_rendered"] is False


def test_table_shape_is_validated() -> None:
    composition = sample_composition()
    composition["components"].append({
        "id": "bad-table",
        "kind": "table",
        "x": 0,
        "y": 0,
        "width": 100,
        "height": 100,
        "headers": ["A", "B"],
        "rows": [["only one"]],
    })
    result = validate_composition(composition, PROFILES)
    assert result["passed"] is False
    assert any("row width does not match headers" in error for error in result["errors"])
