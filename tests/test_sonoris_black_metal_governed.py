import unittest

from products.sonoris_black_metal_governed import (
    compile_black_metal_governed_plan,
)
from products.sonoris_physical_compiler import (
    compile_physical_performance,
)


class SonorisBlackMetalGovernedTests(
    unittest.TestCase
):

    def test_deterministic(self):
        a = compile_black_metal_governed_plan(
            seed=1993,
        )

        b = compile_black_metal_governed_plan(
            seed=1993,
        )

        self.assertEqual(a, b)

    def test_bar_custody(self):
        for seed in (
            2306,
            666,
            1993,
            404,
            1207,
            8888,
        ):
            plan = (
                compile_black_metal_governed_plan(
                    seed=seed,
                )
            )

            self.assertEqual(
                plan["sections"][0][
                    "start_bar"
                ],
                0,
            )

            cursor = 0

            for section in plan[
                "sections"
            ]:
                self.assertEqual(
                    section["start_bar"],
                    cursor,
                )

                self.assertEqual(
                    section["end_bar"]
                    - section["start_bar"],
                    section["bars"],
                )

                cursor = section[
                    "end_bar"
                ]

            self.assertEqual(
                cursor,
                plan["bars"],
            )

    def test_body_contains_genome_decisions(self):
        plan = compile_black_metal_governed_plan(
            seed=2306,
        )

        blueprint = plan[
            "black_metal_blueprint"
        ]

        body = [
            section
            for section
            in plan["sections"]
            if section["section_role"]
            == "BODY"
        ]

        self.assertEqual(
            [
                section["riff_family"]
                for section in body
            ],
            blueprint[
                "riff_sequence"
            ],
        )

        self.assertEqual(
            [
                section["drum_state"]
                for section in body
            ],
            blueprint[
                "drum_sequence"
            ],
        )

        self.assertEqual(
            [
                section[
                    "harmonic_span_bars"
                ]
                for section in body
            ],
            blueprint[
                "harmonic_span_bars"
            ],
        )

    def test_different_seeds_have_different_plans(self):
        signatures = set()

        for seed in (
            2306,
            666,
            1993,
            404,
            1207,
            8888,
        ):
            plan = (
                compile_black_metal_governed_plan(
                    seed=seed,
                )
            )

            signatures.add(
                tuple(
                    (
                        section.get(
                            "intro_archetype"
                        ),
                        section.get(
                            "riff_family"
                        ),
                        section.get(
                            "drum_state"
                        ),
                        section[
                            "bars"
                        ],
                        section.get(
                            "ending_archetype"
                        ),
                    )
                    for section
                    in plan["sections"]
                )
            )

        self.assertEqual(
            len(signatures),
            6,
        )

    def test_physical_compiler_accepts_governed_plan(self):
        plan = compile_black_metal_governed_plan(
            seed=404,
        )

        physical = (
            compile_physical_performance(
                plan,
                seed=404,
            )
        )

        self.assertTrue(
            physical[
                "roles"
            ][
                "rhythm_guitar"
            ]
        )

        self.assertTrue(
            physical[
                "roles"
            ][
                "bass"
            ]
        )

        self.assertTrue(
            physical[
                "roles"
            ][
                "drums"
            ]
        )

    def test_plan_driven_riff_families_reach_physical_layer(self):
        plan = compile_black_metal_governed_plan(
            seed=666,
        )

        physical = (
            compile_physical_performance(
                plan,
                seed=666,
            )
        )

        expected = {
            section[
                "riff_family"
            ]
            for section
            in plan["sections"]
            if section[
                "section_role"
            ] == "BODY"
        }

        realized = {
            event.get(
                "function"
            )
            for event
            in physical[
                "roles"
            ][
                "rhythm_guitar"
            ]
        }

        self.assertTrue(
            expected.issubset(
                realized
            ),
            (
                expected,
                realized,
            ),
        )


if __name__ == "__main__":
    unittest.main()


class SonorisBlackMetalGovernedRealizationTests(
    unittest.TestCase
):

    def test_governed_drum_states_change_realized_drums(self):
        plan = compile_black_metal_governed_plan(
            seed=1993,
        )

        physical = compile_physical_performance(
            plan,
            seed=1993,
        )

        drums = physical["roles"]["drums"]

        expected_markers = {
            "WITHDRAWN_BLAST": "WITHDRAWN_RIDE",
            "MARTIAL_BLAST": "MARTIAL_RIDE",
            "FULL_BLAST": "BLAST_RIDE",
            "DOUBLE_KICK_STORM": "STORM_KICK",
            "FROST_BLAST": "FROST_RIDE",
            "ASHEN_CONTINUUM": "ASHEN_RIDE",
        }

        observed = {
            e["function"]
            for e in drums
        }

        used_states = {
            s["drum_state"]
            for s in plan["sections"]
        }

        for state in used_states:
            marker = expected_markers[state]

            self.assertIn(
                marker,
                observed,
                (
                    state,
                    marker,
                    observed,
                ),
            )

    def test_register_revelation_moves_pitch_range_up(self):
        plan = compile_black_metal_governed_plan(
            seed=666,
        )

        target = None

        for section in reversed(
            plan["sections"]
        ):
            if (
                section["section_role"] == "BODY"
                and section["register_device"]
                == "REGISTER_REVELATION"
            ):
                target = section
                break

        self.assertIsNotNone(target)

        physical = compile_physical_performance(
            plan,
            seed=666,
        )

        lo = target["start_bar"] * 4 * 480
        hi = target["end_bar"] * 4 * 480

        rows = sorted(
            (
                e
                for e
                in physical["roles"]["rhythm_guitar"]
                if lo <= e["tick"] < hi
            ),
            key=lambda e: e["tick"],
        )

        self.assertTrue(rows)

        half = len(rows) // 2

        low_half = rows[:half]
        high_half = rows[half:]

        self.assertGreater(
            min(
                e["pitch"]
                for e in high_half
            ),
            min(
                e["pitch"]
                for e in low_half
            ),
        )
