
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from presence_core.commercial_cognition import (
    _document_edit_job,
    _document_operation_override,
)
from presence_core.engine import _document_quote_scope_reply
from presence_core.vesper_journey_runtime import build_vesper_journey_view
from presence_core.journey_core import available_actions
from presence_core.customer_cases import create_or_attach_case, load_case, update_case
from presence_core.intake_scope_quote import assess_scope, open_intake, prepare_quote, record_intake_inputs
from presence_core.journey_core import transition_case

class TestDocumentEditJob(unittest.TestCase):
    def test_original_customer_problem(self):
        self.assertTrue(_document_edit_job(
            "Several reports are inconsistent. The headings are messy "
            "and I need them professionally formatted."
        ))

    def test_twelve_report_batch(self):
        self.assertTrue(_document_edit_job(
            "Twelve Word reports need consistent headings, typography, "
            "tables, margins, branding, headers and footers."
        ))

    def test_negated_localize(self):
        self.assertTrue(_document_edit_job(
            "I do not need Document Studio Localize or translation. "
            "My English reports need consistent headings and page layouts."
        ))

    def test_real_translation(self):
        self.assertFalse(_document_edit_job(
            "Translate these reports into Afrikaans and format the pages."
        ))

    def test_unrelated(self):
        self.assertFalse(_document_edit_job(
            "Create a Grade 12 examination and marking memorandum."
        ))

    def test_translation_operation_is_distinct(self):
        self.assertEqual(
            _document_operation_override(
                "Translate these reports into Afrikaans and format the pages."
            ),
            "Document Studio Localize",
        )

    def test_publication_operation_is_distinct(self):
        self.assertEqual(
            _document_operation_override(
                "Format these reports for publication on our website."
            ),
            "Document Studio Publish",
        )

    def test_existing_localize_hint_yields_to_formatting_job(self):
        from pathlib import Path
        from presence_core.commercial_cognition import resolve_commercial_cognition

        result = resolve_commercial_cognition(
            Path(__file__).resolve().parents[1],
            "All 12 reports are already in English. I need professional editing and "
            "consistent visual formatting: headings, typography, tables, branding and "
            "page layouts, while preserving factual content. Please reassess Document "
            "Studio Edit versus Document Studio Publish. Do not apply the Document "
            "Studio Localize pricing band.",
            incarnation_hint="Document Studio Localize",
        )
        self.assertEqual(result["product"]["name"], "Document Studio Edit")

    def test_quote_request_answers_process_and_authority(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "intakes").mkdir()
            (root / "intakes" / "PRES-1234567890AB.json").write_text(json.dumps({
                "intake_id": "PRES-1234567890AB",
                "conversation_id": "CONV-TEST-1",
            }))
            reply = _document_quote_scope_reply(
                "Document Studio Edit",
                {"case_id": "CASE-TEST-1", "stage": "NEW_LEAD", "attachments": []},
                "Continue with intake PRES-1234567890AB and prepare a bounded quotation.",
                presence_root=root,
                conversation_id="CONV-TEST-1",
            )
        self.assertIn("sample", reply)
        self.assertIn("approval steps", reply)
        self.assertIn("no quote has been issued", reply)
        self.assertIn("not authorised", reply)
        self.assertIn("PRES-1234567890AB", reply)
        self.assertIn("CASE-TEST-1", reply)

    def test_journey_keeps_customer_and_job_references_visible(self):
        case = {
            "schema": "dio.customer_case.v1",
            "case_id": "CASE-EXAMPLE",
            "product_id": "Document Studio Edit",
            "stage": "FILES_RECEIVED_QUARANTINED",
            "customer_id": None,
            "customer_identity": {"state": "unverified"},
            "contact_email": "customer@example.test",
            "fulfilment": {},
        }
        view = build_vesper_journey_view(case)
        self.assertEqual(view["case_id"], "CASE-EXAMPLE")
        self.assertEqual(view["facts"]["communication"]["contact_email"], "customer@example.test")
        self.assertEqual(view["facts"]["communication"]["customer_identity_state"], "unverified")
        self.assertIn("OPEN_INTAKE", available_actions(case))
        self.assertIn("RECORD_INTAKE_INPUTS", available_actions(case))

    def test_job_id_is_projected_after_fulfilment_starts(self):
        view = build_vesper_journey_view({
            "schema": "dio.customer_case.v1",
            "case_id": "CASE-EXAMPLE",
            "product_id": "Document Studio Edit",
            "stage": "REVIEW_READY",
            "customer_identity": {"state": "unverified"},
            "fulfilment": {"job_id": "DOC-EXAMPLE", "state": "review_ready"},
        })
        self.assertEqual(view["facts"]["fulfilment"]["job_id"], "DOC-EXAMPLE")

    def test_uploaded_document_quote_goes_to_operator_with_bound_scope(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as td:
            state = Path(td) / "presence"
            case = create_or_attach_case(
                state,
                conversation_id="CONV-DOC-QUOTE-1",
                channel="webchat",
                external_user_id="VWC-DOC-QUOTE-1",
                product_id="Document Studio Edit",
            )
            open_intake(root, state, case["case_id"])
            case = load_case(state, case["case_id"])
            case = update_case(state, case, patch={"attachments": [{
                "attachment_id": "ATT-SAMPLE-1",
                "original_file_name": "sample-report.docx",
                "sha256": "a" * 64,
                "state": "quarantined",
            "safe_to_parse": False,
            }]})
            transition_case(state, case["case_id"], "FILES_RECEIVED_QUARANTINED", evidence_ref="test-upload")
            record_intake_inputs(root, state, case["case_id"], {
                "requested_outcome": "12 English reports; preserve factual wording; consistent branding and layout; maximum 180 pages.",
                "buyer_class": "C2",
                "scope_quantity": 180,
            })
            scope = assess_scope(root, state, case["case_id"])
            self.assertEqual(scope["state"], "SUFFICIENT")
            quote = prepare_quote(root, state, case["case_id"])
            self.assertEqual(quote["decision"], "NEEDS_YOU")
            self.assertIsNone(quote["quote"])
            self.assertEqual(quote["quote_request"]["scope_quantity"], 180)
            self.assertEqual(quote["quote_request"]["source_attachments"][0]["attachment_id"], "ATT-SAMPLE-1")
            self.assertEqual(load_case(state, case["case_id"])["stage"], "NEEDS_YOU")

if __name__ == "__main__":
    unittest.main()

class TestDocumentEditConversationRouting(unittest.TestCase):
    def test_greeting_prefix_does_not_hide_recommendation(self):
        from presence_core.router import route_message
        root = Path(__file__).resolve().parents[1]
        decision = route_message(
            "Hello Vesper. I manage a small consulting organisation, and we have reports that need professional formatting.",
            "public",
            root / "config/routes.json",
        )
        # The engine's operation override upgrades this generic route to Edit.
        self.assertNotEqual(decision.intent, "general_info")
        self.assertEqual(_document_operation_override(
            "Hello Vesper. Our reports look inconsistent and need professional formatting."
        ), "Document Studio Edit")

    def test_quotation_wording_is_recognized(self):
        from presence_core.router import route_message
        root = Path(__file__).resolve().parents[1]
        decision = route_message(
            "Please prepare a bounded quotation for formatting my reports.",
            "public",
            root / "config/routes.json",
        )
        self.assertEqual(decision.intent, "pricing_info")

    def test_quote_followup_states_no_quote_details_exist_yet(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "intakes").mkdir()
            (root / "intakes" / "PRES-1234567890AB.json").write_text(json.dumps({
                "intake_id": "PRES-1234567890AB",
                "conversation_id": "CONV-TEST-2",
            }))
            reply = _document_quote_scope_reply(
                "Document Studio Edit",
                {"case_id": "CASE-TEST-2", "stage": "NEW_LEAD", "attachments": []},
                "Show me the quotation details and how the batch will be handled securely.",
                presence_root=root,
                conversation_id="CONV-TEST-2",
            )
        for phrase in ("no quotation has been issued", "no quote reference", "price, validity", "validity period", "turnaround estimate", "quarantine", "PRES-1234567890AB"):
            self.assertIn(phrase.casefold(), reply.casefold())
        self.assertNotIn("Localize pricing", reply)
