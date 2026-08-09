from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.document_studio import pipeline  # noqa: E402
from adapters.lingua.lifecycle import register_product_source, update_semantic_object  # noqa: E402
from scripts.build_operator_dashboard import build_dashboard_state, render_dashboard  # noqa: E402


PACK = ROOT / "deliverables" / "document_studio" / "DIO-DOC-GOLDEN-001"
MULTILINGUAL_PACKS = {
    "isiZulu": ROOT / "deliverables" / "document_studio" / "DIO-DOC-ISIZULU-001",
    "Sesotho": ROOT / "deliverables" / "document_studio" / "DIO-DOC-SESOTHO-001",
    "Setswana": ROOT / "deliverables" / "document_studio" / "DIO-DOC-SETSWANA-001",
}


class DocumentStudioContractTests(unittest.TestCase):
    def test_south_african_language_profiles_and_aliases_are_canonical(self) -> None:
        registry = pipeline.load_language_registry()
        self.assertEqual("isiZulu", pipeline.canonical_language("Zulu", registry))
        self.assertEqual("Sesotho", pipeline.canonical_language("sotho", registry))
        self.assertEqual("Setswana", pipeline.canonical_language("setstwana", registry))
        for language in ("Afrikaans", "isiZulu", "Sesotho", "Setswana"):
            self.assertIn(language, registry["languages"])
            self.assertIn("reviewer_requirement", registry["languages"][language])

    def test_translation_requires_a_distinct_target_and_human_reviewer(self) -> None:
        request = {
            "service": "translation",
            "source_language": "English",
            "target_language": "isiZulu",
            "human_language_review_required": False,
        }
        with self.assertRaisesRegex(ValueError, "target-language reviewer"):
            pipeline.normalize_language_request(request)
        request["human_language_review_required"] = True
        request["target_language"] = "English"
        with self.assertRaisesRegex(ValueError, "must differ"):
            pipeline.normalize_language_request(request)

    def test_validator_rejects_a_dropped_operational_number(self) -> None:
        request = {"service": "edit_and_translate", "protected_tokens": ["pH"], "preferred_terms": []}
        paragraphs = [{"paragraph_id": "P1", "text": "Record pH after 2 minutes."}]
        result = {
            "edits": [{"paragraph_id": "P1", "revised": "Record pH after 2 minutes."}],
            "translations": [{"paragraph_id": "P1", "translated": "Teken pH aan."}],
        }
        validation = pipeline.validate_result(request, paragraphs, result)
        self.assertFalse(validation["passed"])
        self.assertIn("P1 translation dropped numbers: 2", validation["errors"])

    def test_golden_pack_is_complete_and_human_gated(self) -> None:
        qa = json.loads((PACK / "DOCUMENT_STUDIO_QA.json").read_text(encoding="utf-8"))
        receipt = json.loads((PACK / "DOCUMENT_STUDIO_RECEIPT.json").read_text(encoding="utf-8"))
        self.assertTrue(qa["passed"])
        self.assertEqual(7, qa["automated_validation"]["translation_rows"])
        self.assertGreaterEqual(qa["translation_review_overrides"]["applied_count"], 1)
        self.assertIn(qa["human_gates"]["target_language_reviewer_approval"], {"pending", "approved"})
        self.assertFalse(receipt["release"]["delivery_released"])
        self.assertFalse(receipt["release"]["certified_translation"])
        self.assertTrue((PACK / "pdf" / "REDLINE_REVIEW_COPY.pdf").is_file())
        self.assertTrue((PACK / "pdf" / "BILINGUAL_REVIEW_COPY.pdf").is_file())
        self.assertTrue((PACK / "DOCUMENT_STUDIO_PROOF.png").is_file())

    def test_multilingual_nim_candidates_are_complete_and_release_blocked(self) -> None:
        for language, pack in MULTILINGUAL_PACKS.items():
            with self.subTest(language=language):
                qa = json.loads((pack / "DOCUMENT_STUDIO_QA.json").read_text(encoding="utf-8"))
                receipt = json.loads((pack / "DOCUMENT_STUDIO_RECEIPT.json").read_text(encoding="utf-8"))
                self.assertTrue(qa["automated_integrity_passed"])
                self.assertIsInstance(qa["linguistic_quality_approved"], bool)
                expected_readiness = "linguistic_approved_pending_remaining_review" if qa["linguistic_quality_approved"] else "blocked_pending_human_approval"
                self.assertEqual(expected_readiness, qa["release_readiness"])
                self.assertEqual(language, qa["language_controls"]["target_language"])
                self.assertEqual("deepseek-ai/deepseek-v4-flash-0731", qa["language_controls"]["automated_critic"]["model"])
                self.assertEqual("nvidia_nim", receipt["processing"]["provider"])
                self.assertFalse(receipt["release"]["delivery_released"])
                self.assertEqual(qa["linguistic_quality_approved"], receipt["release"]["linguistic_quality_approved"])
                learning = json.loads((pack / "BEAST_LEARNING_RECEIPT.json").read_text(encoding="utf-8"))
                self.assertFalse(learning["semantic_translation_truth_promoted"])
                self.assertFalse(learning["human_intervention_required"])
                self.assertTrue(learning["chain"]["valid"])
                self.assertTrue((pack / f"{pack.name}_DOCUMENT_STUDIO_REVIEW_PACK.zip").is_file())

    def test_lingua_object_unifies_languages_and_beast_does_not_auto_approve_meaning(self) -> None:
        semantic_object = json.loads((ROOT / "state" / "lingua" / "objects" / "DIO-LINGUA-WATER-001.json").read_text(encoding="utf-8"))
        self.assertEqual({"Afrikaans", "isiZulu", "Sesotho", "Setswana"}, set(semantic_object["translations"]))
        self.assertEqual(7, len(semantic_object["source"]["units"]))
        self.assertTrue(all(lane["status"] in {"human_review_required", "human_approved_crystallized"} for lane in semantic_object["translations"].values()))
        credits = [json.loads(path.read_text(encoding="utf-8")) for path in (ROOT / "state" / "lingua" / "beast_credits").glob("scc_*.json")]
        self.assertTrue(any(row["task_class"] == "dio_lingua_deterministic_guard" for row in credits))
        self.assertTrue(any(row["task_class"] == "dio_lingua_risk_pattern" for row in credits))
        semantic_credits = [row for row in credits if row["task_class"] in {"dio_lingua_translation_unit", "dio_lingua_approved_term"}]
        self.assertTrue(all((row.get("metadata") or {}).get("reviewer") for row in semantic_credits))
        self.assertFalse(semantic_object["authority"]["machine_drafts_reusable"])

    def test_control_deck_projects_automatic_beast_learning_and_grouped_semantic_review(self) -> None:
        state = build_dashboard_state()
        lingua = state["lingua"]
        self.assertEqual("active", lingua["automatic_learning"])
        self.assertGreaterEqual(lingua["automatic_guard_credits"], 4)
        self.assertGreaterEqual(lingua["automatic_risk_credits"], 1)
        self.assertGreaterEqual(lingua["approved_semantic_credits"], 0)
        self.assertTrue(lingua["chain"]["valid"])
        water_object = next(item for item in lingua["objects"] if item["object_id"] == "DIO-LINGUA-WATER-001")
        self.assertEqual(4, water_object["language_count"])
        self.assertGreaterEqual(lingua["product_count"], 5)
        self.assertEqual("operational", json.loads((ROOT / "state" / "lingua" / "BEAST_ORGANS_STATUS.json").read_text())["status"])
        beast_system = next(item for item in state["systems"] if item["id"] == "beast_lingua")
        self.assertEqual("active", beast_system["state"])
        pending_objects = sum(any(lane["status"] == "human_review_required" for lane in item["languages"]) for item in lingua["objects"])
        lingua_attention = [item for item in state["attention"] if item["kind"] == "lingua"]
        self.assertEqual(pending_objects, len(lingua_attention))
        self.assertTrue(all("BEAST guard learning active" in item["detail"] for item in lingua_attention))

        dashboard = render_dashboard(state)
        self.assertIn("Lingua QA", dashboard)
        self.assertIn("Automatic learning", dashboard)
        self.assertIn("Only human-approved meaning is reusable", dashboard)
        self.assertIn("Inspect approval", dashboard)

    def test_only_changed_source_unit_stales_existing_languages(self) -> None:
        request = {
            "source_language": "English",
            "target_language": "isiZulu",
            "document_domain": "Education",
        }
        source_v1 = [{"paragraph_id": "P1", "text": "Title"}, {"paragraph_id": "P2", "text": "Force is measured in N."}]
        translations = {
            "P1": {"translated": "Isihloko"},
            "P2": {"translated": "Amandla alinganiswa nge-N."},
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            update_semantic_object(
                state_root=root,
                object_id="LESSON-TEST-001",
                source_version="1.0",
                request=request,
                source_rows=source_v1,
                translations=translations,
                provider={"provider": "test", "model": "test"},
                qa_flags=[],
            )
            request["target_language"] = "Sesotho"
            source_v2 = [{"paragraph_id": "P1", "text": "Title"}, {"paragraph_id": "P2", "text": "Force is measured in newtons (N)."}]
            _obj, receipt = update_semantic_object(
                state_root=root,
                object_id="LESSON-TEST-001",
                source_version="1.1",
                request=request,
                source_rows=source_v2,
                translations={"P1": {"translated": "Sehlooho"}, "P2": {"translated": "Matla a lekanngwa ka N."}},
                provider={"provider": "test", "model": "test"},
                qa_flags=[],
            )
            self.assertEqual(["P2"], receipt["changed_units"])
            self.assertEqual(["P2"], receipt["stale_translation_units"]["isiZulu"])

    def test_product_registration_preserves_other_lanes_and_stales_only_changed_units(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            semantic, _receipt = register_product_source(
                state_root=root,
                object_id="VAMP-LINGUA-TEST",
                source_version="1.0",
                source_language="English",
                source_rows=[{"paragraph_id": "P1", "text": "Review title"}, {"paragraph_id": "P2", "text": "Evidence is complete."}],
                origin={"product": "vamp", "artifact_type": "review_snapshot", "artifact_id": "VAMP-1"},
                domain="performance review",
            )
            semantic["translations"] = {
                "Setswana": {
                    "status": "human_review_required",
                    "units": [
                        {"unit_id": "P1", "source_hash": semantic["source"]["units"][0]["source_hash"], "target_text": "Setlhogo"},
                        {"unit_id": "P2", "source_hash": semantic["source"]["units"][1]["source_hash"], "target_text": "Bosupi bo feletse."},
                    ],
                }
            }
            (root / "objects" / "VAMP-LINGUA-TEST.json").write_text(json.dumps(semantic), encoding="utf-8")
            updated, receipt = register_product_source(
                state_root=root,
                object_id="VAMP-LINGUA-TEST",
                source_version="1.1",
                source_language="English",
                source_rows=[{"paragraph_id": "P1", "text": "Review title"}, {"paragraph_id": "P2", "text": "Evidence is partly complete."}],
                origin={"product": "vamp", "artifact_type": "review_snapshot", "artifact_id": "VAMP-1"},
                domain="performance review",
            )
            self.assertEqual(["P2"], receipt["stale_translation_units"]["Setswana"])
            self.assertEqual("stale_source_changed", updated["translations"]["Setswana"]["units"][1]["status"])

    def test_public_site_uses_the_universal_intake(self) -> None:
        site = (ROOT / "sites" / "document-studio" / "index.html").read_text(encoding="utf-8")
        schema = json.loads((ROOT / "schemas" / "public_intake.schema.json").read_text(encoding="utf-8"))
        self.assertIn('product:"document_studio"', site)
        self.assertIn("window.DIOPublicIntake.submit", site)
        self.assertIn("REDLINE_REVIEW_COPY.pdf", site)
        self.assertIn("isiZulu", site)
        self.assertIn("Sesotho", site)
        self.assertIn("Setswana", site)
        self.assertIn("DIO Lingua + BEAST", site)
        self.assertIn('value="lingua_lifecycle"', site)
        self.assertIn("document_studio", schema["properties"]["product"]["enum"])

    def test_lingua_output_request_is_available_across_primary_product_sites(self) -> None:
        for product in ("homs", "sophia", "evidex", "vamp"):
            with self.subTest(product=product):
                site = (ROOT / "sites" / product / "index.html").read_text(encoding="utf-8")
                self.assertIn('name="output_language"', site)
                for language in ("Afrikaans", "isiZulu", "Sesotho", "Setswana"):
                    self.assertIn(language, site)
                self.assertIn("proficient_review_required", site)


if __name__ == "__main__":
    unittest.main()
