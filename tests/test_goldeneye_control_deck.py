from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GoldenEyeControlDeckTests(unittest.TestCase):
    def test_goldeneye_surface_keeps_governed_control_api(self) -> None:
        html = (ROOT / "dashboard" / "goldeneye.html").read_text(encoding="utf-8")
        for required in (
            "DIO // GOLDENEYE",
            "Needs Byron Now",
            "Hypothesis Board",
            "Campaign War Room",
            "Registry Command",
            "Lead Spine",
            "Experiment Command",
            "Economics & Attribution Truth",
            "Gaps & Contradictions",
            "Mandos Outcome Memory",
            "BLACKOUT",
            "data:image/webp;base64,",
            "/api/control/state",
            "/api/control/policy",
            "/api/control/market-campaign/action",
            "/api/control/market-command/action",
            "/api/control/creative-factory/action",
            "/api/control/lead/action",
            "/dashboard/index.html",
        ):
            self.assertIn(required, html)

    def test_goldeneye_exposes_full_commercial_lineage_and_integrity_watch(self) -> None:
        html = (ROOT / "dashboard" / "goldeneye.html").read_text(encoding="utf-8")
        for required in (
            "registry → hypothesis → campaign → creative → lead → transaction → outcome",
            "Qualified lead has no canonical transaction",
            "Paid order lacks fulfilment job id",
            "Lead has no resolvable campaign lineage",
            "Market Command experiment has no Wave4 hypothesis link",
            "measurement-ledger economics and direct-event economics",
            "Authority gained",
            "observation only",
        ):
            self.assertIn(required, html)

    def test_goldeneye_wrapper_is_valid_python_and_localhost_bound(self) -> None:
        path = ROOT / "scripts" / "serve_goldeneye.py"
        source = path.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('self.path = "/dashboard/goldeneye.html"', source)
        self.assertIn('args.host not in {"127.0.0.1", "localhost", "::1"}', source)
        self.assertIn("ControlDeckHandler", source)

    def test_systemd_entrypoint_uses_goldeneye(self) -> None:
        service = (ROOT / "deploy" / "systemd" / "dio-control-deck.service").read_text(encoding="utf-8")
        self.assertIn("scripts/serve_goldeneye.py", service)
        self.assertIn("--host 127.0.0.1 --port 8765", service)


if __name__ == "__main__":
    unittest.main()
