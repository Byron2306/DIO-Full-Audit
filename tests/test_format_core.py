from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.format_core.renderer import (  # noqa: E402
    _content_digest,
    _localizable,
    build_paragraph_semantic_content,
    load_profiles,
    render_semantic_asset,
    semantic_content_from_lingua_object,
    validate_semantic_content,
)


SAMPLE = ROOT / "samples" / "format_core" / "caps_natural_sciences_g7_t1.json"


class FormatCoreTests(unittest.TestCase):
    def test_profiles_cover_shared_business_and_delivery_routes(self) -> None:
        profiles = load_profiles()
        self.assertIn("caps_educator", profiles["styles"])
        self.assertIn("institutional_academic", profiles["styles"])
        self.assertEqual({"docx", "pdf", "pptx", "html", "vtt"}, set(profiles["deliveries"]["classroom_bundle"]["channels"]))

    def test_accessibility_and_structure_are_hard_gates(self) -> None:
        content = json.loads(SAMPLE.read_text(encoding="utf-8"))
        diagram = next(block for block in content["blocks"] if block["type"] == "diagram")
        diagram["alt_text"] = ""
        validation = validate_semantic_content(content)
        self.assertFalse(validation["passed"])
        self.assertTrue(any("requires alt_text" in item for item in validation["errors"]))

    def test_classroom_bundle_renders_all_channels_with_semantic_completeness(self) -> None:
        content = json.loads(SAMPLE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            receipt = render_semantic_asset(
                content,
                Path(temp),
                style_profile="caps_educator",
                delivery_profile="classroom_bundle",
                source_root=SAMPLE.parent,
            )
            self.assertEqual("rendered_review_candidate", receipt["status"])
            self.assertEqual({"docx", "pdf", "pptx", "html", "vtt"}, {item["channel"] for item in receipt["outputs"]})
            self.assertTrue(receipt["qa"]["passed"])
            self.assertTrue(all(row["missing_count"] == 0 for row in receipt["qa"]["semantic_completeness"].values()))

    def test_release_mode_rejects_candidate_translation_and_accepts_approved_lane(self) -> None:
        rows = [{"paragraph_id": "P1", "text": "Water safety"}, {"paragraph_id": "P2", "text": "Record pH after 2 minutes."}]
        translations = {"P1": {"translated": "Waterveiligheid"}, "P2": {"translated": "Teken pH na 2 minute aan."}}
        content = build_paragraph_semantic_content(
            object_id="FORMAT-LANG-001", version="1.0", title="Water safety", source_language="English",
            source_rows=rows, context={"product": "document_studio", "artifact_type": "procedure", "audience": "technicians"},
            translations=translations, target_language="Afrikaans",
        )
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "not human-approved"):
                render_semantic_asset(content, Path(temp), language="Afrikaans", channels=["html"], release_mode=True)
            content["translations"]["Afrikaans"]["status"] = "human_approved_crystallized"
            receipt = render_semantic_asset(content, Path(temp), language="Afrikaans", channels=["html"], release_mode=True)
            self.assertTrue(receipt["qa"]["passed"])
            self.assertEqual("rendered_release_candidate", receipt["status"])

    def test_exact_source_change_invalidates_only_affected_translation_block(self) -> None:
        content = json.loads(SAMPLE.read_text(encoding="utf-8"))
        blocks = content["blocks"][:2]
        content["blocks"] = blocks
        content["translations"] = {"Afrikaans": {"source_version": "1.0.0", "status": "human_approved_crystallized", "blocks": []}}
        for block in blocks:
            content["translations"]["Afrikaans"]["blocks"].append({
                "block_id": block["block_id"], "source_hash": _content_digest(_localizable(block)), "text": block["text"] + " AF",
            })
        content["blocks"][1]["text"] += " Changed."
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "stale=.*B002"):
                render_semantic_asset(content, Path(temp), language="Afrikaans", channels=["html"], release_mode=True)

    def test_approved_lingua_object_can_feed_any_product_into_format_core(self) -> None:
        lingua = json.loads((ROOT / "state" / "lingua" / "objects" / "DIO-LINGUA-WATER-001.json").read_text(encoding="utf-8"))
        content = semantic_content_from_lingua_object(lingua)
        self.assertEqual("document_studio", content["context"]["product"])
        self.assertEqual("human_approved_crystallized", content["translations"]["Afrikaans"]["status"])
        with tempfile.TemporaryDirectory() as temp:
            receipt = render_semantic_asset(content, Path(temp), language="Afrikaans", channels=["html"], release_mode=True)
            self.assertTrue(receipt["qa"]["passed"])


if __name__ == "__main__":
    unittest.main()
