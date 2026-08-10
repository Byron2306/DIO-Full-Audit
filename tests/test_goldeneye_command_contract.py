from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "dashboard" / "goldeneye-command.html").read_text(encoding="utf-8")
JS = (ROOT / "dashboard" / "goldeneye-command.js").read_text(encoding="utf-8")
HARDENING = (ROOT / "dashboard" / "goldeneye-command-hardening.js").read_text(encoding="utf-8")
SERVER = (ROOT / "scripts" / "serve_goldeneye.py").read_text(encoding="utf-8")
MANDOS = (ROOT / "commerce" / "mandos.py").read_text(encoding="utf-8")
COCKPIT = HTML + "\n" + JS + "\n" + HARDENING


class GoldenEyeCommandContractTests(unittest.TestCase):
    def test_command_cockpit_is_goldeneye_root(self) -> None:
        self.assertIn('self.path = "/dashboard/goldeneye-command.html"', SERVER)
        self.assertIn('/dashboard/goldeneye.html', SERVER)

    def test_original_dio_emblem_is_visible_in_command_cockpit(self) -> None:
        self.assertGreaterEqual(HTML.count('/dashboard/assets/dio-logo-cockpit.svg'), 2)
        self.assertIn('DIO GoldenEye emblem', HTML)

    def test_home_has_exact_five_operator_surfaces(self) -> None:
        for label in (
            "Needs me now",
            "Customers waiting",
            "Money & pipeline",
            "Ready to ship / release",
            "Risk & memory",
        ):
            self.assertIn(label, HTML)

    def test_needs_me_cards_expose_full_decision_contract(self) -> None:
        for label in (
            "Customer",
            "Product",
            "Elapsed",
            "Money involved",
            "Evidence",
            "Uncertainty",
            "Why DIO stopped",
            "Authorised action",
        ):
            self.assertIn(label, JS)
        self.assertIn("No monetary amount bound", JS)
        self.assertIn("No explicit uncertainty metric surfaced", JS)
        self.assertIn("no action authority surfaced", JS)

    def test_unified_case_dossier_has_all_required_stages(self) -> None:
        self.assertIn("Commercial Case Dossier", HTML)
        for stage in (
            "Conversation Context",
            "CSO",
            "Transaction",
            "Quote / payment",
            "Fulfilment",
            "Delivery",
            "Mandos outcomes",
        ):
            self.assertIn(stage, COCKPIT)
        self.assertIn("semantic_object_id", JS)
        self.assertIn("commercial_semantic_object_sha256", JS)
        self.assertIn("Legacy or pre-semantic case. GoldenEye does not invent a CSO.", JS)
        self.assertIn("No Mandos outcome is bound to this case yet. Absence is not interpreted as success or failure.", JS)

    def test_mandos_reads_real_c6_outcomes_patterns_and_decisions(self) -> None:
        self.assertIn("/state/mandos/JOURNAL.jsonl", JS)
        self.assertIn("/state/mandos/outcomes/", JS)
        self.assertIn("/state/mandos/patterns/", HARDENING)
        self.assertIn("/state/mandos/decisions/", HARDENING)
        self.assertIn("canonical C6 state", HARDENING)
        self.assertIn('return self.state_root / "patterns"', MANDOS)
        self.assertIn('return self.state_root / "decisions"', MANDOS)
        self.assertIn("operator_confirmed", JS)
        self.assertIn("repeated_observation", JS)
        self.assertIn("corroborated_pattern", JS)
        self.assertIn("candidate_strategy", JS)
        self.assertIn("adversarial_validated", JS)
        self.assertIn("reusable_crystal", JS)

    def test_mandos_surfaces_complete_requested_taxonomy(self) -> None:
        for label in (
            "Recent outcomes",
            "Repeated patterns",
            "Active negative capabilities",
            "Contested patterns",
            "Candidate strategies",
            "Promoted crystals",
            "Revocations",
        ):
            self.assertIn(label, HTML)

    def test_positive_memory_never_looks_like_execution_permission(self) -> None:
        self.assertIn("positive memory never grants execution permission", HTML)
        self.assertIn("strategy-hypothesis reuse only", HTML)
        self.assertIn("EXECUTION AUTHORITY = 0", JS)
        self.assertIn("Execution authority gained", JS)
        self.assertNotIn("/api/control/mandos/action", COCKPIT)

    def test_technical_surfaces_are_demoted_to_advanced(self) -> None:
        self.assertIn("Advanced / Organs", HTML)
        self.assertIn('/dashboard/goldeneye.html', HTML)
        self.assertIn('/dashboard/index.html', HTML)
        self.assertIn('http://127.0.0.1:8770/', HTML)


if __name__ == "__main__":
    unittest.main()
