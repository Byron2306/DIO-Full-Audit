import unittest

from products.sonoris_physical_compiler import (
    BM_HARMONIC_SPANS,
    _bm_harmonic_spans_for_seed,
    _bm_song_harmonic_dialect,
)


class BlackMetalHarmonicDialectTests(
    unittest.TestCase
):

    def test_same_seed_is_deterministic(self):
        a = _bm_song_harmonic_dialect(
            1993
        )

        b = _bm_song_harmonic_dialect(
            1993
        )

        self.assertEqual(
            a,
            b,
        )

    def test_three_song_seeds_have_distinct_dialects(
        self,
    ):
        rows = {
            seed: (
                tuple(
                    sorted(
                        _bm_song_harmonic_dialect(
                            seed
                        )[
                            "offset_map"
                        ].items()
                    )
                ),
                tuple(
                    sorted(
                        _bm_song_harmonic_dialect(
                            seed
                        )[
                            "shape_map"
                        ].items()
                    )
                ),
            )
            for seed in (
                404,
                1993,
                8888,
            )
        }

        self.assertEqual(
            len(
                set(
                    rows.values()
                )
            ),
            3,
        )

    def test_legacy_breakthrough_seed_is_preserved(
        self,
    ):
        for family in (
            "FROST_SIGIL",
            "CORRUPTED_SIGIL",
            "KNIFE",
            "FROZEN_FIELD",
            "TRANSFIGURED_SIGIL",
            "WAR_ASCENT",
        ):
            self.assertEqual(
                _bm_harmonic_spans_for_seed(
                    family,
                    661028,
                ),
                BM_HARMONIC_SPANS[
                    family
                ],
            )

    def test_family_harmonic_pacing_is_preserved(
        self,
    ):
        for seed in (
            404,
            1993,
            8888,
        ):
            for family, canonical in (
                BM_HARMONIC_SPANS.items()
            ):
                generated = (
                    _bm_harmonic_spans_for_seed(
                        family,
                        seed,
                    )
                )

                self.assertEqual(
                    tuple(
                        row[0]
                        for row
                        in generated
                    ),
                    tuple(
                        row[0]
                        for row
                        in canonical
                    ),
                )

    def test_song_seed_changes_actual_harmonic_content(
        self,
    ):
        signatures = {
            tuple(
                _bm_harmonic_spans_for_seed(
                    "FROZEN_FIELD",
                    seed,
                )
            )
            for seed in (
                404,
                1993,
                8888,
            )
        }

        self.assertGreaterEqual(
            len(signatures),
            2,
        )


if __name__ == "__main__":
    unittest.main()
