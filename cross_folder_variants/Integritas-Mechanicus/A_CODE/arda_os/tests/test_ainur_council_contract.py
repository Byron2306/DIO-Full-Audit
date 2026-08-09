import unittest

from backend.services.ainur.ainur_council import AinurCouncil, AinurWitness


class _StaticWitness(AinurWitness):
    def __init__(self, name: str, domain: str, report):
        super().__init__(name, domain)
        self._report = report

    async def speak(self, context):
        return dict(self._report)


class AinurCouncilContractTest(unittest.IsolatedAsyncioTestCase):
    async def test_consult_witnesses_emits_enriched_contract(self):
        council = AinurCouncil()
        council.register_witness(
            _StaticWitness(
                "Manwë",
                "heralding",
                {
                    "judgment": "LAWFUL",
                    "testimony": "The heralding is clean.",
                    "heralding": "Routine diagnostics in fair order.",
                },
            )
        )
        council.register_witness(
            _StaticWitness(
                "Varda",
                "truth",
                {
                    "judgment": "LAWFUL",
                    "testimony": "The truth remains coherent.",
                    "findings": "No drift in the claim.",
                },
            )
        )

        advisory = await council.consult_witnesses(
            {
                "command": "uptime",
                "actor": "agent:seraph",
                "binary": "/usr/bin/uptime",
            }
        )

        self.assertEqual(advisory["overall_recommendation"], "HARMONIC")
        self.assertEqual(advisory["compat_recommendation"], "LAWFUL")
        self.assertEqual(advisory["canonical_runtime_state"], "harmonic")
        self.assertIn("collective_testimony", advisory)
        self.assertIn("resonance_summary", advisory)
        self.assertEqual(len(advisory["resonance_summary"]), 2)
        self.assertEqual(advisory["witness_sequence"], ["Manwë", "Varda"])
        self.assertIn("The heralding is clean.", advisory["collective_testimony"])
        self.assertIsNotNone(advisory["harmonic_observation"])

    async def test_empty_council_withholds_by_default(self):
        council = AinurCouncil()

        advisory = await council.consult_witnesses({"command": "/usr/bin/unknown"})

        self.assertFalse(advisory["consensus_reached"])
        self.assertEqual(advisory["action"], "WITHHOLD_EMPTY_COUNCIL")
        self.assertEqual(advisory["overall_recommendation"], "DISSONANT/WITHHELD")
        self.assertEqual(advisory["compat_recommendation"], "WITHHELD")
        self.assertEqual(advisory["canonical_runtime_state"], "muted")


if __name__ == "__main__":
    unittest.main()
