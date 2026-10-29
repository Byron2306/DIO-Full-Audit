import unittest

from products.sonoris_black_metal_genome import (
    compose_black_metal_blueprint,
)


class SonorisBlackMetalGenomeTests(
    unittest.TestCase
):

    def test_deterministic_for_same_seed(self):
        a = compose_black_metal_blueprint(
            seed=2306,
        )

        b = compose_black_metal_blueprint(
            seed=2306,
        )

        self.assertEqual(a, b)

    def test_many_seeds_produce_many_structures(self):
        signatures = set()

        for seed in range(40):
            b = compose_black_metal_blueprint(
                seed=seed,
            )

            signatures.add(
                (
                    b.intro,
                    b.ending,
                    b.atmosphere,
                    b.register_device,
                    b.riff_sequence,
                    b.drum_sequence,
                )
            )

        self.assertGreaterEqual(
            len(signatures),
            30,
        )

    def test_not_every_song_has_lament_intro(self):
        rows = [
            compose_black_metal_blueprint(
                seed=seed,
            )
            for seed in range(60)
        ]

        lament = sum(
            row.lament_intro
            for row in rows
        )

        self.assertGreater(
            lament,
            0,
        )

        self.assertLess(
            lament,
            len(rows),
        )

    def test_not_every_song_has_keys(self):
        rows = [
            compose_black_metal_blueprint(
                seed=seed,
            )
            for seed in range(60)
        ]

        count = sum(
            row.keys_present
            for row in rows
        )

        self.assertGreater(
            count,
            0,
        )

        self.assertLess(
            count,
            len(rows),
        )

    def test_every_song_has_multiple_riff_families(self):
        for seed in range(100):
            b = compose_black_metal_blueprint(
                seed=seed,
            )

            self.assertGreaterEqual(
                len(
                    set(
                        b.riff_sequence
                    )
                ),
                4,
            )

    def test_no_adjacent_identical_riff_family(self):
        for seed in range(100):
            b = compose_black_metal_blueprint(
                seed=seed,
            )

            for a, c in zip(
                b.riff_sequence,
                b.riff_sequence[1:],
            ):
                self.assertNotEqual(
                    a,
                    c,
                )

    def test_harmonic_motion_is_macro_scale(self):
        for seed in range(100):
            b = compose_black_metal_blueprint(
                seed=seed,
            )

            self.assertTrue(
                all(
                    span in {1, 2}
                    for span
                    in b.harmonic_span_bars
                )
            )

    def test_drums_do_not_have_to_change_with_riffs(self):
        found_persistent_state = False

        for seed in range(100):
            b = compose_black_metal_blueprint(
                seed=seed,
            )

            if any(
                a == c
                for a, c in zip(
                    b.drum_sequence,
                    b.drum_sequence[1:],
                )
            ):
                found_persistent_state = True
                break

        self.assertTrue(
            found_persistent_state
        )


if __name__ == "__main__":
    unittest.main()
