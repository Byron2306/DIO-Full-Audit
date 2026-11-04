import unittest

from products.sonoris_dark_aggro_synthwave import (
    compose_dark_aggro_blueprint,
    compile_dark_aggro_events,
)


class DarkAggroSynthwaveTests(
    unittest.TestCase
):

    def test_same_seed_is_deterministic(
        self,
    ):
        a = compile_dark_aggro_events(
            seed=2306,
            bars=96,
        )

        b = compile_dark_aggro_events(
            seed=2306,
            bars=96,
        )

        self.assertEqual(
            a,
            b,
        )

    def test_tempo_covers_dark_aggro_range(
        self,
    ):
        bpms = {
            compose_dark_aggro_blueprint(
                seed=seed
            ).bpm
            for seed in range(80)
        }

        self.assertTrue(
            min(bpms) >= 98
        )

        self.assertTrue(
            max(bpms) <= 150
        )

        self.assertTrue(
            any(
                bpm <= 112
                for bpm in bpms
            )
        )

        self.assertTrue(
            any(
                113 <= bpm <= 128
                for bpm in bpms
            )
        )

        self.assertTrue(
            any(
                bpm >= 129
                for bpm in bpms
            )
        )

    def test_many_seeds_produce_many_dialects(
        self,
    ):
        signatures = set()

        for seed in range(40):
            b = (
                compose_dark_aggro_blueprint(
                    seed=seed
                )
            )

            signatures.add(
                (
                    b.pulse_dialect,
                    b.harmonic_dialect,
                    b.timbre_dialect,
                    b.arrangement_dialect,
                    b.bass_sequence,
                    b.drum_sequence,
                    b.lead_sequence,
                )
            )

        self.assertGreaterEqual(
            len(signatures),
            32,
        )

    def test_bass_is_primary_event_role(
        self,
    ):
        d = compile_dark_aggro_events(
            seed=2306,
            bars=96,
        )

        counts = d[
            "event_counts"
        ]

        self.assertGreater(
            counts["bass"],
            counts["harmony"],
        )

    def test_no_guitar_semantics_are_required(
        self,
    ):
        d = compile_dark_aggro_events(
            seed=2306,
            bars=96,
        )

        all_functions = {
            e["function"]
            for role in (
                "harmony",
                "bass",
                "lead",
            )
            for e in d[
                "events"
            ][role]
        }

        for value in all_functions:
            self.assertNotIn(
                "GUITAR",
                value,
            )

    def test_lead_can_remain_absent_early(
        self,
    ):
        d = compile_dark_aggro_events(
            seed=2306,
            bars=96,
        )

        reveal = d[
            "blueprint"
        ][
            "lead_reveal_bar"
        ]

        early_leads = [
            e
            for e in d[
                "events"
            ][
                "lead"
            ]
            if e["beat"]
            < reveal * 4
        ]

        self.assertEqual(
            early_leads,
            [],
        )

    def test_harmony_moves_slower_than_bass(
        self,
    ):
        d = compile_dark_aggro_events(
            seed=404,
            bars=96,
        )

        bass = d[
            "events"
        ][
            "bass"
        ]

        harmony = d[
            "events"
        ][
            "harmony"
        ]

        self.assertGreater(
            len(bass),
            len(harmony) * 2,
        )

    def test_drums_are_machine_states(
        self,
    ):
        d = compile_dark_aggro_events(
            seed=666,
            bars=96,
        )

        allowed = {
            "MACHINE_STOMP",
            "NIGHTCLUB_DRIVE",
            "INDUSTRIAL_HALF_TIME",
            "CHASE_GRID",
            "DROP_PULSE",
        }

        states = {
            e["gesture"]
            for e in d[
                "events"
            ][
                "drums"
            ]
        }

        self.assertTrue(
            states <= allowed
        )

        self.assertGreaterEqual(
            len(states),
            2,
        )

    def test_bass_has_multiple_riff_families(
        self,
    ):
        d = compile_dark_aggro_events(
            seed=1993,
            bars=96,
        )

        families = {
            e["function"]
            for e in d[
                "events"
            ][
                "bass"
            ]
        }

        self.assertGreaterEqual(
            len(families),
            3,
        )

    def test_sections_include_contrast(
        self,
    ):
        d = compile_dark_aggro_events(
            seed=8888,
            bars=96,
        )

        states = {
            s["state"]
            for s in d[
                "sections"
            ]
        }

        self.assertIn(
            "STALK",
            states,
        )

        self.assertTrue(
            states
            & {
                "DROP",
                "SURGE",
                "ASSAULT",
                "HOOK",
            }
        )

    def test_short_form_refuses(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            compile_dark_aggro_events(
                seed=1,
                bars=32,
            )


if __name__ == "__main__":
    unittest.main()
