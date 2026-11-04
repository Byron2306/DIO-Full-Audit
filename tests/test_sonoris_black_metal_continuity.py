import unittest

from products.sonoris_black_metal_governed import (
    compile_black_metal_governed_plan,
)

from products.sonoris_black_metal_continuity import (
    apply_black_metal_continuity,
)


class BlackMetalContinuityTests(
    unittest.TestCase
):

    def _fixture(
        self,
        seed=2306,
    ):
        """
        Minimal valid governed-plan shape for continuity tests.

        Continuity owns boundary relationships only.
        It must not depend on genome bar allocation succeeding.
        """
        return {
            "seed": seed,
            "title": "Continuity Fixture",
            "bars": 40,
            "sections": [
                {
                    "index": 1,
                    "start_bar": 0,
                    "end_bar": 8,
                    "section_role": "INTRO",
                    "riff_family": "FROZEN_FIELD",
                    "drum_state": "FROST_BLAST",
                    "atmosphere_name": "COLD_DRONE",
                },
                {
                    "index": 2,
                    "start_bar": 8,
                    "end_bar": 20,
                    "section_role": "BODY",
                    "riff_family": "FROZEN_FIELD",
                    "drum_state": "WITHDRAWN_BLAST",
                    "atmosphere_name": "COLD_DRONE",
                },
                {
                    "index": 3,
                    "start_bar": 20,
                    "end_bar": 32,
                    "section_role": "BODY",
                    "riff_family": "WAR_ASCENT",
                    "drum_state": "FULL_BLAST",
                    "atmosphere_name": "CHOIR_SHADOW",
                },
                {
                    "index": 4,
                    "start_bar": 32,
                    "end_bar": 36,
                    "section_role": "BODY",
                    "riff_family": "KNIFE",
                    "drum_state": "DOUBLE_KICK_STORM",
                    "atmosphere_name": "NONE",
                },
                {
                    "index": 5,
                    "start_bar": 36,
                    "end_bar": 40,
                    "section_role": "ENDING",
                    "riff_family": None,
                    "drum_state": "WITHDRAWN_BLAST",
                    "atmosphere_name": "CHOIR_SHADOW",
                },
            ],
        }

    def _compile(
        self,
        seed=2306,
    ):
        return (
            apply_black_metal_continuity(
                self._fixture(seed)
            )
        )

    def test_deterministic(
        self,
    ):
        self.assertEqual(
            self._compile(2306),
            self._compile(2306),
        )

    def test_every_boundary_is_described(
        self,
    ):
        d = self._compile()

        sections = d["sections"]

        boundaries = d[
            "black_metal_continuity"
        ][
            "boundaries"
        ]

        self.assertEqual(
            len(boundaries),
            len(sections) - 1,
        )

    def test_boundary_bars_match_sections(
        self,
    ):
        d = self._compile()

        sections = d["sections"]

        boundaries = d[
            "black_metal_continuity"
        ][
            "boundaries"
        ]

        for i, boundary in enumerate(
            boundaries
        ):
            self.assertEqual(
                boundary["at_bar"],
                sections[i]["end_bar"],
            )

            self.assertEqual(
                boundary["at_bar"],
                sections[i + 1][
                    "start_bar"
                ],
            )

    def test_not_every_boundary_has_fill(
        self,
    ):
        rows = []

        for seed in range(30):
            d = self._compile(seed)

            rows.extend(
                d[
                    "black_metal_continuity"
                ][
                    "boundaries"
                ]
            )

        self.assertTrue(
            any(
                row["drum_transition"]
                == "NONE"
                for row in rows
            )
        )

        self.assertTrue(
            any(
                row["drum_transition"]
                != "NONE"
                for row in rows
            )
        )

    def test_bleed_exists_across_seed_set(
        self,
    ):
        types = set()

        for seed in range(30):
            d = self._compile(seed)

            types.update(
                row["transition_type"]
                for row
                in d[
                    "black_metal_continuity"
                ][
                    "boundaries"
                ]
            )

        self.assertIn(
            "BLEED",
            types,
        )

        self.assertIn(
            "CONTINUE",
            types,
        )

        self.assertIn(
            "CUT",
            types,
        )

    def test_cut_has_no_carry(
        self,
    ):
        for seed in range(40):
            d = self._compile(seed)

            for row in d[
                "black_metal_continuity"
            ][
                "boundaries"
            ]:
                if (
                    row[
                        "transition_type"
                    ]
                    == "CUT"
                ):
                    self.assertFalse(
                        row[
                            "guitar_carry"
                        ]
                    )

                    self.assertEqual(
                        row[
                            "carry_beats"
                        ],
                        0.0,
                    )

    def test_transition_metadata_reaches_sections(
        self,
    ):
        d = self._compile()

        sections = d["sections"]

        self.assertIn(
            "transition_out",
            sections[0],
        )

        self.assertIn(
            "transition_in",
            sections[1],
        )

    def test_accepts_real_governed_black_metal_plan(
        self,
    ):
        governed = (
            compile_black_metal_governed_plan(
                seed=1993,
                title="Thrones Beneath Snow",
            )
        )

        d = apply_black_metal_continuity(
            governed
        )

        boundaries = d[
            "black_metal_continuity"
        ][
            "boundaries"
        ]

        self.assertEqual(
            len(boundaries),
            len(governed["sections"]) - 1,
        )

        self.assertEqual(
            boundaries[0]["at_bar"],
            governed["sections"][0][
                "end_bar"
            ],
        )


    def test_atmosphere_decay_implies_atmosphere_carry(
        self,
    ):
        for seed in range(100):
            d = self._compile(seed)

            for row in d[
                "black_metal_continuity"
            ][
                "boundaries"
            ]:
                if (
                    row["tail_type"]
                    == "ATMOSPHERE_DECAY"
                ):
                    self.assertTrue(
                        row[
                            "atmosphere_carry"
                        ]
                    )

    def test_continue_does_not_always_emit_tail(
        self,
    ):
        rows = []

        for seed in range(100):
            d = self._compile(seed)

            rows.extend(
                row
                for row in d[
                    "black_metal_continuity"
                ][
                    "boundaries"
                ]
                if (
                    row[
                        "transition_type"
                    ]
                    == "CONTINUE"
                )
            )

        self.assertTrue(
            any(
                row["tail_type"]
                == "NONE"
                for row in rows
            )
        )



if __name__ == "__main__":
    unittest.main()
