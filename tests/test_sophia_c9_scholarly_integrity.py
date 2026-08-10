from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.sophia.product_integrity import (  # noqa: E402
    build_scholarly_risk_register,
    build_verification_queue,
    compare_revision_packs,
    enrich_review_pack,
)


def claim_payload(label: str = "background only", entailment: str = "partial_or_contextual_only") -> dict:
    return {
        "schema": "dio.sophia_claim_source_ledger.v1",
        "claims": [
            {
                "claim_record": {
                    "claim": "Structured feedback causes measurable improvement in academic writing outcomes.",
                    "claim_type": "causal",
                    "evidence_standard": "Needs design capable of causal inference; otherwise downgrade the claim.",
                    "evidence_risk": "high",
                },
                "source_map": {
                    "results": [
                        {
                            "source_name": "Doctoral Writing and Feedback Review",
                            "support_label": label,
                            "entailment_status": entailment,
                            "entailment_score": 0.31 if label == "background only" else 0.91,
                            "quality_score": 0.86,
                            "relevance": 0.76,
                            "source_quality_rubric": {
                                "score": 0.81,
                                "band": "usable",
                                "integrity_rule": "A source lead is not proof until its exact span supports the claim.",
                            },
                            "exact_span": "The review discusses writing, feedback, doctoral identity and academic development.",
                            "authors": ["Kelsey Inouye", "Lynn McAlpine"],
                            "year": "2019",
                            "doi": "10.28945/4168",
                            "url": "https://doi.org/10.28945/4168",
                            "apa_candidate": "Inouye, K., & McAlpine, L. (2019). Doctoral writing and feedback.",
                            "metadata_status": "doi metadata present",
                            "provenance_status": "scholarly_index",
                            "page_status": "no page number visible; do not invent one",
                            "page_locator": "",
                            "entailment_warnings": ["causal scope is not visible in the source span"] if label == "background only" else [],
                            "semantic_score": 0.45,
                            "source_type": "OpenAlex",
                        }
                    ]
                },
            }
        ],
    }


def reference_audit(actionable: int = 1) -> dict:
    missing = [{"key": "ghost:2024", "author": "Ghost", "year": "2024", "form": "parenthetical"}] if actionable else []
    return {
        "schema": "dio.sophia_reference_audit.v1",
        "citation_style": "APA 7 diagnostic",
        "in_text_citations": missing,
        "reference_entries": [],
        "missing_from_reference_list": missing,
        "reference_list_entries_not_cited": [],
        "duplicate_entries": [],
        "duplicate_dois": [],
        "actionable_issue_count": actionable,
        "status": "needs_revision" if actionable else "clean_first_pass",
        "limits": [],
    }


def literature_payload() -> dict:
    return {
        "schema": "dio.sophia_literature_map.v1",
        "queries": ["feedback academic writing"],
        "external_retrieval_approved": True,
        "retrieval_runs": [],
        "deduplicated_sources": [
            {
                "title": "Doctoral Writing and Feedback Review",
                "url": "https://doi.org/10.28945/4168",
                "year": "2019",
                "authors": ["Kelsey Inouye", "Lynn McAlpine"],
                "summary": "A review of doctoral writing, feedback and identity.",
                "source": "OpenAlex",
                "quality_score": 0.86,
                "relevance_score": 0.76,
            }
        ],
    }


def commentary() -> dict:
    return {
        "status": "completed",
        "source": "reasoned_integrity_lane",
        "provider": "gemini",
        "provider_status": "ok",
        "model": "gemini-test",
        "repair_applied": True,
        "repair_steps": ["source_scope_repair"],
        "mandos_judgment": {"passed": True},
        "article_conformity": {"summary": {"all_passed": True}},
        "validation": {
            "passed": True,
            "checks": {
                "provider_is_gemini": True,
                "provider_completed": True,
                "reasoned_lane_used": True,
                "mandos_passed": True,
                "genesis_articles_passed": True,
                "document_anchor_present": True,
                "no_unknown_anchors": True,
                "no_unknown_citations": True,
                "no_unknown_dois": True,
            },
        },
        "commentary": "Major revision [C1]: the causal claim exceeds the evidence currently visible in the mapped source.",
    }


def receipt(word_count: int = 130) -> dict:
    return {
        "schema": "dio.sophia_review_receipt.v1",
        "source": {"word_count": word_count},
        "metrics": {"reference_findings": 1},
    }


class SophiaC9Tests(unittest.TestCase):
    def test_high_risk_causal_claim_with_background_source_is_not_promoted(self) -> None:
        register = build_scholarly_risk_register(claim_payload(), reference_audit(0))
        claim = register["risks"][0]
        self.assertEqual(claim["support_state"], "background_only")
        self.assertEqual(claim["severity"], "high")
        self.assertIn("candidate_is_background_not_direct_support", claim["problems"])
        self.assertIn("not findings of misconduct", register["boundary"])

    def test_direct_support_can_be_support_ready_but_still_requires_verification(self) -> None:
        payload = claim_payload("supports", "entails")
        register = build_scholarly_risk_register(payload, reference_audit(0))
        self.assertEqual(register["risks"][0]["support_state"], "support_ready")
        queue = build_verification_queue(payload, reference_audit(0))
        self.assertTrue(queue["items"][0]["verification_required"])
        self.assertIn("No queue item is promoted", queue["release_rule"])

    def test_reference_gap_enters_risk_register(self) -> None:
        register = build_scholarly_risk_register(claim_payload("supports", "entails"), reference_audit(1))
        self.assertTrue(any(row["kind"] == "reference_integrity" for row in register["risks"]))
        self.assertTrue(any("cited_in_text_but_missing_from_reference_list" in row.get("problems", []) for row in register["risks"]))

    def test_real_vendored_speculum_engine_enriches_commercial_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "pack"
            output.mkdir()
            manuscript = root / "manuscript.txt"
            manuscript.write_text(
                "Structured feedback can help writers notice weaknesses in a draft. "
                "However, causal improvement claims require research designs capable of causal inference. "
                "The author therefore treats source fit, warrant and limitations as separate scholarly decisions.\n" * 3,
                encoding="utf-8",
            )
            (output / "CLAIM_SOURCE_LEDGER.json").write_text(json.dumps(claim_payload(), indent=2), encoding="utf-8")
            (output / "REFERENCE_AUDIT.json").write_text(json.dumps(reference_audit(1), indent=2), encoding="utf-8")
            (output / "LITERATURE_MAP.json").write_text(json.dumps(literature_payload(), indent=2), encoding="utf-8")
            (output / "REVIEWER_COMMENTARY.json").write_text(json.dumps(commentary(), indent=2), encoding="utf-8")
            (output / "SOPHIA_REVIEW_RECEIPT.json").write_text(json.dumps(receipt(), indent=2), encoding="utf-8")

            result = enrich_review_pack(
                job_id="SOPHIA-C9-CI-001",
                output_dir=output,
                manuscript_path=manuscript,
                sophia_root=root / "deliberately-missing-sophia-root",
            )
            self.assertEqual(result["state"], "integrity_pack_ready")
            self.assertEqual(len(result["speculum_integrity_record_hash"]), 64)
            for name in (
                "SCHOLARLY_RISK_REGISTER.json",
                "SOURCE_VERIFICATION_QUEUE.json",
                "SOPHIA_INTEGRITY_RECORD.json",
                "AUTHORSHIP_PRESERVATION_INDEX.json",
                "INTEGRITY_PASSPORT.json",
                "SOPHIA-C9-CI-001_SOPHIA_REVIEW_PACK.zip",
            ):
                self.assertTrue((output / name).is_file(), name)
            index = json.loads((output / "AUTHORSHIP_PRESERVATION_INDEX.json").read_text(encoding="utf-8"))
            self.assertEqual(index.get("validation_status"), "engineering_metric_unvalidated")
            passport = json.loads((output / "INTEGRITY_PASSPORT.json").read_text(encoding="utf-8"))
            self.assertFalse(passport["authority"]["misconduct_finding_authority"])
            self.assertFalse(passport["authority"]["automatic_source_promotion"])
            self.assertIn("not a forensic", passport["authorship_preservation"]["boundary"])

    def test_revision_comparison_rewards_risk_reduction_without_authorship_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_dir = root / "old"
            new_dir = root / "new"
            old_dir.mkdir(); new_dir.mkdir()
            old_doc = root / "old.txt"; new_doc = root / "new.txt"
            old_doc.write_text("old draft", encoding="utf-8")
            new_doc.write_text("new draft", encoding="utf-8")
            old_risk = {"open_risk_count": 4}; new_risk = {"open_risk_count": 2}
            old_ref = reference_audit(3); new_ref = reference_audit(1)
            old_claim = claim_payload(); new_claim = claim_payload()
            for directory, risk, ref, claims in (
                (old_dir, old_risk, old_ref, old_claim),
                (new_dir, new_risk, new_ref, new_claim),
            ):
                (directory / "SCHOLARLY_RISK_REGISTER.json").write_text(json.dumps(risk), encoding="utf-8")
                (directory / "REFERENCE_AUDIT.json").write_text(json.dumps(ref), encoding="utf-8")
                (directory / "CLAIM_SOURCE_LEDGER.json").write_text(json.dumps(claims), encoding="utf-8")
            report = compare_revision_packs(
                original_dir=old_dir,
                revised_dir=new_dir,
                original_document=old_doc,
                revised_document=new_doc,
            )
            self.assertEqual(report["movement"], "improved")
            self.assertEqual(report["delta"]["open_scholarly_risks"], -2)
            self.assertIn("does not forensically determine", report["authorship_boundary"])

    def test_new_high_risk_claim_prevents_false_improvement_story(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_dir = root / "old"; new_dir = root / "new"
            old_dir.mkdir(); new_dir.mkdir()
            old_doc = root / "old.txt"; new_doc = root / "new.txt"
            old_doc.write_text("old", encoding="utf-8"); new_doc.write_text("new", encoding="utf-8")
            new_claims = claim_payload()
            new_claims["claims"].append({
                "claim_record": {
                    "claim": "The intervention definitively causes institution-wide retention gains.",
                    "claim_type": "causal",
                    "evidence_risk": "high",
                    "evidence_standard": "causal inference required",
                },
                "source_map": {"results": []},
            })
            for directory, claims in ((old_dir, claim_payload()), (new_dir, new_claims)):
                (directory / "SCHOLARLY_RISK_REGISTER.json").write_text(json.dumps({"open_risk_count": 2}), encoding="utf-8")
                (directory / "REFERENCE_AUDIT.json").write_text(json.dumps(reference_audit(1)), encoding="utf-8")
                (directory / "CLAIM_SOURCE_LEDGER.json").write_text(json.dumps(claims), encoding="utf-8")
            report = compare_revision_packs(
                original_dir=old_dir,
                revised_dir=new_dir,
                original_document=old_doc,
                revised_document=new_doc,
            )
            self.assertEqual(report["movement"], "new_or_shifted_risk")
            self.assertEqual(len(report["new_high_risk_claims"]), 1)

    def test_public_product_surface_exposes_integrity_not_detector_claims(self) -> None:
        source = (ROOT / "sites" / "sophia" / "index.html").read_text(encoding="utf-8")
        for phrase in (
            "Integrity you can inspect.",
            "Not proofreading. Scholarly integrity work.",
            "Ten artifacts. One evidence trail.",
            "The author revises. Sophia checks the movement.",
            "No detector cosplay.",
            "No plagiarism verdict from similarity.",
            "No “AI-written” verdict.",
        ):
            self.assertIn(phrase, source)

    def test_service_contract_matches_product_surface(self) -> None:
        config = json.loads((ROOT / "config" / "sophia_service.json").read_text(encoding="utf-8"))
        self.assertEqual(config["limits"]["included_revision_rounds"], 1)
        self.assertEqual(len(config["deliverables"]), 10)
        self.assertFalse(config["integrity_contract"]["misconduct_detection_authority"])
        self.assertFalse(config["integrity_contract"]["authorship_preservation_index_is_forensic_detector"])
        self.assertTrue(any(row["code"] == "SOPHIA_SUPERVISOR_REVIEW" for row in config["future_scoped_offers"]))


if __name__ == "__main__":
    unittest.main()
