from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "dashboard" / "goldeneye-command.html").read_text(encoding="utf-8")
JS = (ROOT / "dashboard" / "goldeneye-command.js").read_text(encoding="utf-8")
SERVER = (ROOT / "scripts" / "serve_goldeneye.py").read_text(encoding="utf-8")
COCKPIT = HTML + "\n" + JS


class GoldenEyeCommandContractTests(unittest.TestCase):
    def test_command_cockpit_is_goldeneye_root(self) -> None:
        self.assertIn('self.path = "/dashboard/goldeneye-command.html"', SERVER)
        self.assertIn('/dashboard/goldeneye.html', SERVER)

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
        # The chain nodes are rendered dynamically by goldeneye-command.js, while
        # the dossier contract also appears in the static HTML. Validate the
        # complete browser source rather than pretending generated stages are
        # literal static markup.
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

    def test_mandos_reads_real_c6_outcomes_and_decisions(self) -> None:
        self.assertIn("/state/mandos/JOURNAL.jsonl", JS)
        self.assertIn("/state/mandos/outcomes/", JS)
        self.assertIn("/state/mandos/decisions/", JS)
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
        self.assertNotIn("/api/control/mandos/action", JS)

    def test_technical_surfaces_are_demoted_to_advanced(self) -> None:
        self.assertIn("Advanced / Organs", HTML)
        self.assertIn('/dashboard/goldeneye.html', HTML)
        self.assertIn('/dashboard/index.html', HTML)
        self.assertIn('http://127.0.0.1:8770/', HTML)


if __name__ == "__main__":
    unittest.main()
