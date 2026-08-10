from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from commerce.mandos import MandosLedger
from scripts.manage_mandos import main


class MandosSilenceTests(unittest.TestCase):
    @staticmethod
    def write(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def base_state(self, root: Path) -> None:
        self.write(root / "state/leads/LEAD-SILENCE-1.json", {
            "lead_id": "LEAD-SILENCE-1",
            "product": "Evidex Evidence Packs",
            "offer": "bounded pilot",
        })
        self.write(root / "state/mail_intents/MAIL-SILENCE-1.json", {
            "mail_intent_id": "MAIL-SILENCE-1",
            "send_state": "sent",
            "sent_at": "2020-01-01T10:00:00+00:00",
            "updated_at": "2020-01-01T10:00:00+00:00",
            "lead_id": "LEAD-SILENCE-1",
            "conversation_id": "THREAD-SILENCE-1",
            "communicative_act": "cold_permission_request",
            "semantic_binding": {
                "semantic_object_id": "CSO-SILENCE-1",
                "communicative_act": "cold_permission_request",
            },
            "semantic_judgement": {"judgement_id": "JUDGE-SILENCE-1"},
        })

    def invoke(self, root: Path) -> dict:
        argv = [
            "manage_mandos.py", "--root", str(root), "close-silence",
            "--mail-intent-id", "MAIL-SILENCE-1",
            "--window-start", "2020-01-01T10:00:00+00:00",
            "--window-end", "2020-01-08T10:00:00+00:00",
            "--actor", "operator",
            "--reason", "seven-day bounded observation window completed",
        ]
        output = io.StringIO()
        with patch.object(sys, "argv", argv), redirect_stdout(output):
            self.assertEqual(0, main())
        return json.loads(output.getvalue())

    def test_silence_requires_explicit_closed_window_and_preserves_strategy_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.base_state(root)
            result = self.invoke(root)
            outcome = result["outcome"]
            self.assertEqual("no_reply_window_closed", outcome["outcome_type"])
            self.assertEqual("operator_confirmed", outcome["evidence"]["state"])
            self.assertEqual("Evidex Evidence Packs", outcome["strategy"]["product"])
            self.assertEqual("bounded pilot", outcome["strategy"]["offer"])
            self.assertTrue(outcome["detail"]["absence_is_operator_confirmed_not_provider_fact"])

    def test_inbound_inside_window_refuses_silence_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.base_state(root)
            self.write(root / "state/mail_ingress/IN-SILENCE-1.json", {
                "mail_ingress_id": "IN-SILENCE-1",
                "conversation_id": "THREAD-SILENCE-1",
                "received_at": "2020-01-04T12:00:00+00:00",
            })
            argv = [
                "manage_mandos.py", "--root", str(root), "close-silence",
                "--mail-intent-id", "MAIL-SILENCE-1",
                "--window-start", "2020-01-01T10:00:00+00:00",
                "--window-end", "2020-01-08T10:00:00+00:00",
                "--actor", "operator",
                "--reason", "seven-day window",
            ]
            with patch.object(sys, "argv", argv):
                with self.assertRaisesRegex(ValueError, "Silence window is false"):
                    main()
            self.assertEqual([], MandosLedger(root).outcomes())

    def test_window_cannot_begin_before_send(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.base_state(root)
            argv = [
                "manage_mandos.py", "--root", str(root), "close-silence",
                "--mail-intent-id", "MAIL-SILENCE-1",
                "--window-start", "2019-12-31T10:00:00+00:00",
                "--window-end", "2020-01-08T10:00:00+00:00",
                "--actor", "operator",
                "--reason", "invalid window",
            ]
            with patch.object(sys, "argv", argv):
                with self.assertRaisesRegex(ValueError, "cannot begin before"):
                    main()


if __name__ == "__main__":
    unittest.main()
