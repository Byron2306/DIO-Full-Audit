from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GoldenEyeControlDeckTests(unittest.TestCase):
    def test_goldeneye_surface_keeps_governed_control_api(self) -> None:
        html = (ROOT / "dashboard" / "goldeneye.html").read_text(encoding="utf-8")
        for required in (
            "DIO GOLDENEYE",
            "NEEDS BYRON NOW",
            "MANDOS // COMMERCIAL MEMORY",
            "BLACKOUT",
            "/api/control/state",
            "/api/control/policy",
            "/api/control/product/action",
            "/api/control/transaction/action",
            "/dashboard/index.html",
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
