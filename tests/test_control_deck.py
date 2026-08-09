from __future__ import annotations

import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import serve_control_deck  # noqa: E402
from scripts.build_operator_dashboard import latest_unique_jobs, run_mode, write_json  # noqa: E402


class DashboardStateTests(unittest.TestCase):
    def test_controlled_runs_are_not_labelled_live(self) -> None:
        self.assertEqual(run_mode("phase1_demo", "samples/inbox/demo_inbox.json"), "controlled")
        self.assertEqual(run_mode("client-order-104", "state/mail_ingress/INGRESS-1.json"), "live")

    def test_latest_job_instance_wins_without_removing_run_history(self) -> None:
        runs = [
            {"jobs": [{"job_id": "JOB-1", "status": "approved"}, {"job_id": "JOB-2", "status": "pending"}]},
            {"jobs": [{"job_id": "JOB-1", "status": "pending"}]},
        ]
        self.assertEqual(latest_unique_jobs(runs), [runs[0]["jobs"][0], runs[0]["jobs"][1]])

    def test_concurrent_state_writes_remain_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda value: write_json(path, {"value": value}), range(40)))
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn(payload["value"], range(40))
            self.assertFalse(list(path.parent.glob(".state.json.*.tmp")))


class ControlPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.original_policy_path = serve_control_deck.POLICY_PATH
        self.original_event_log = serve_control_deck.EVENT_LOG
        serve_control_deck.POLICY_PATH = root / "control_policy.json"
        serve_control_deck.EVENT_LOG = root / "events.jsonl"

    def tearDown(self) -> None:
        serve_control_deck.POLICY_PATH = self.original_policy_path
        serve_control_deck.EVENT_LOG = self.original_event_log
        self.temporary.cleanup()

    def test_policy_change_is_persisted_and_receipted(self) -> None:
        policy = serve_control_deck.update_policy({"automation": "running"})
        self.assertEqual(policy["automation"], "running")
        self.assertEqual(json.loads(serve_control_deck.POLICY_PATH.read_text())["automation"], "running")
        event = json.loads(serve_control_deck.EVENT_LOG.read_text().splitlines()[-1])
        self.assertEqual(event["event"], "control.policy_changed")
        self.assertEqual(event["data"]["changes"], {"automation": "running"})

    def test_unknown_or_invalid_controls_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            serve_control_deck.update_policy({"automation": "launch"})
        with self.assertRaises(ValueError):
            serve_control_deck.update_policy({"delete_everything": "yes"})

    def test_campaign_release_authority_is_held_by_default(self) -> None:
        with self.assertRaisesRegex(ValueError, "campaign_release=hold"):
            serve_control_deck.require_policy("campaign_release", "release", "Campaign publication")
        serve_control_deck.update_policy({"campaign_release": "release"})
        serve_control_deck.require_policy("campaign_release", "release", "Campaign publication")

    def test_sophia_approval_requires_explicit_confirmation(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicit operator confirmation"):
            serve_control_deck.operate_sophia({"job_id": "SOPHIA-TEST-001", "action": "approve"})

    def test_unknown_sophia_action_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown Sophia"):
            serve_control_deck.operate_sophia({"job_id": "SOPHIA-TEST-001", "action": "delete"})

    def test_vamp_approval_requires_explicit_confirmation(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicit operator confirmation"):
            serve_control_deck.operate_vamp({"job_id": "VAMP-TEST-001", "action": "approve"})

    def test_unknown_vamp_action_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown VAMP"):
            serve_control_deck.operate_vamp({"job_id": "VAMP-TEST-001", "action": "delete"})

    def test_product_approval_requires_explicit_confirmation(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicit operator confirmation"):
            serve_control_deck.operate_product({"job_id": "HOMS-TEST-001", "action": "approve-intake"})

    def test_unknown_product_action_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown HOMS or Evidex"):
            serve_control_deck.operate_product({"job_id": "HOMS-TEST-001", "action": "delete"})


class LinguaApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.original_root = serve_control_deck.ROOT
        self.original_event_log = serve_control_deck.EVENT_LOG
        serve_control_deck.ROOT = self.root
        serve_control_deck.EVENT_LOG = self.root / "telemetry" / "events.jsonl"
        object_path = self.root / "state" / "lingua" / "objects" / "LINGUA-APPROVAL-TEST.json"
        object_path.parent.mkdir(parents=True)
        object_path.write_text(json.dumps({
            "schema": "dio.lingua.semantic_object.v1",
            "object_id": "LINGUA-APPROVAL-TEST",
            "domain": "education",
            "source": {"version": "1.0", "units": [
                {"unit_id": "P1", "source_hash": "sha256:one", "source_text": "Read the source."},
                {"unit_id": "P2", "source_hash": "sha256:two", "source_text": "Answer question 2."},
            ]},
            "translations": {"Setswana": {"status": "human_review_required", "units": [
                {"unit_id": "P1", "source_hash": "sha256:one", "target_text": "Buisa motswedi.", "qa_flags": []},
                {"unit_id": "P2", "source_hash": "sha256:two", "target_text": "Araba potso 2.", "qa_flags": [{"severity": "medium", "issue": "Review terminology."}]},
            ]}},
        }), encoding="utf-8")

    def tearDown(self) -> None:
        serve_control_deck.ROOT = self.original_root
        serve_control_deck.EVENT_LOG = self.original_event_log
        self.temporary.cleanup()

    def payload(self, *, resolved: bool, approved: bool) -> dict:
        return {
            "action": "approve-language" if approved else "save-review",
            "semantic_object_id": "LINGUA-APPROVAL-TEST",
            "target_language": "Setswana",
            "reviewer": "Test Reviewer",
            "reviewer_role": "Setswana language practitioner",
            "confirmed": approved,
            "terms": [],
            "units": [
                {"unit_id": "P1", "source_hash": "sha256:one", "target_text": "Buisa motswedi.", "approved": approved, "flag_resolutions": []},
                {"unit_id": "P2", "source_hash": "sha256:two", "target_text": "Araba potso 2.", "approved": approved, "flag_resolutions": [{"index": 0, "resolution": "accepted_as_is" if resolved else "unresolved", "note": "Checked"}]},
            ],
        }

    def test_review_can_be_saved_without_promoting_semantic_authority(self) -> None:
        result = serve_control_deck.operate_lingua(self.payload(resolved=False, approved=False))
        self.assertEqual("saved", result["status"])
        review = json.loads(Path(result["review_path"]).read_text())
        self.assertEqual("in_progress", review["approval_state"])

    def test_final_approval_requires_flag_disposition(self) -> None:
        with self.assertRaisesRegex(ValueError, "Resolve every material flag"):
            serve_control_deck.operate_lingua(self.payload(resolved=False, approved=True))

    def test_resolved_language_can_be_crystallized_from_control_deck(self) -> None:
        receipt = self.root / "receipt.json"
        with patch.object(serve_control_deck, "crystallize_approval", return_value=receipt) as crystallize:
            result = serve_control_deck.operate_lingua(self.payload(resolved=True, approved=True))
        self.assertEqual("crystallized", result["status"])
        crystallize.assert_called_once()


if __name__ == "__main__":
    unittest.main()
