import unittest

from products.sonoris_genre_compiler import compile_composition_request
from products.sonoris_physical_compiler import compile_physical_performance


class SonorisPhysicalCompilerTests(unittest.TestCase):

    def setUp(self):
        self.plan = compile_composition_request({
            "genre": "black_metal",
            "title": "Where the Pines Forget",
            "mood": "icy, eerie, relentless, then dissolving",
            "tempo_bpm": 168,
            "meter": "4/4",
            "bars": 52,
            "tonal_center": "D-minor",
        })

    def test_compiler_is_deterministic(self):
        a = compile_physical_performance(self.plan, seed=661028)
        b = compile_physical_performance(self.plan, seed=661028)

        self.assertEqual(a["sha256"], b["sha256"])
        self.assertEqual(a["roles"], b["roles"])

    def test_renderer_intent_is_not_encoded_as_bar_ranges(self):
        result = compile_physical_performance(self.plan, seed=661028)

        self.assertFalse(
            result["invariants"][
                "renderer_may_infer_gesture_from_bar_number"
            ]
        )

        self.assertFalse(
            result["invariants"][
                "song_specific_bar_range_articulation_rules"
            ]
        )

    def test_guitar_has_physical_articulation(self):
        result = compile_physical_performance(
            self.plan,
            seed=661028,
        )

        rows = result["roles"]["rhythm_guitar"]

        arts = {
            row["articulation"]
            for row in rows
        }

        # V0.4 black-metal fast surfaces are deliberately sustain-dominant.
        self.assertIn(
            "SUSTAIN_DOWN",
            arts,
        )

        self.assertIn(
            "SUSTAIN_UP",
            arts,
        )

        # Physical pick direction must still be explicit.
        strokes = {
            row["stroke"]
            for row in rows
            if row.get("stroke")
        }

        self.assertTrue(
            {"DOWN", "UP"}.issubset(strokes)
        )

        # Shape-based performance is now the primary guitar contract.
        shaped = [
            row
            for row in rows
            if row.get("pitches")
            and len(row["pitches"]) >= 2
        ]

        self.assertGreater(
            len(shaped),
            0,
        )

    def test_bass_contains_explicit_interaction(self):
        result = compile_physical_performance(self.plan, seed=661028)

        sources = {
            row["interaction_source"]
            for row in result["roles"]["bass"]
        }

        self.assertTrue(
            {"guitar", "kick+guitar"} & sources
        )

    def test_black_metal_gestures_produce_different_event_densities(self):
        result = compile_physical_performance(self.plan, seed=661028)

        sections = {
            row["gesture"]: row
            for row in result["sections"]
        }

        self.assertGreater(
            sections["PANIC"]["contract"]["density"],
            sections["COLLAPSE"]["contract"]["density"],
        )

        self.assertGreater(
            sections["SPRINT"]["contract"]["phrase_pressure"],
            sections["TRANCE"]["contract"]["phrase_pressure"],
        )


if __name__ == "__main__":
    unittest.main()

class SparseGestureTraceTests(unittest.TestCase):

    def test_collapse_and_release_keep_a_guitar_trace(self):
        from products.sonoris_genre_compiler import compile_composition_request
        from products.sonoris_physical_compiler import compile_physical_performance

        plan = compile_composition_request({
            "genre": "black_metal",
            "title": "Where the Pines Forget",
            "mood": "icy, eerie, relentless, then dissolving",
            "tempo_bpm": 168,
            "meter": "4/4",
            "bars": 52,
            "tonal_center": "D-minor",
        })

        result = compile_physical_performance(plan, seed=661028)

        counts = {
            row["gesture"]: row["event_counts"]["guitar"]
            for row in result["sections"]
        }

        self.assertGreaterEqual(counts["COLLAPSE"], 1)
        self.assertGreaterEqual(counts["RELEASE"], 1)

class BlackMetalMorphologyV02Tests(unittest.TestCase):

    def _compile(self):
        from products.sonoris_genre_compiler import compile_composition_request
        from products.sonoris_physical_compiler import compile_physical_performance

        plan = compile_composition_request({
            "genre": "black_metal",
            "title": "Where the Pines Forget",
            "mood": "icy, eerie, relentless, then dissolving",
            "tempo_bpm": 168,
            "meter": "4/4",
            "bars": 52,
            "tonal_center": "D-minor",
        })

        return compile_physical_performance(
            plan,
            seed=661028,
        )

    def test_fast_black_metal_gestures_are_sustain_dominant(self):
        result = self._compile()

        rows = [
            e for e in result["roles"]["rhythm_guitar"]
            if e["gesture"] in {"TRANCE", "SPRINT", "PANIC"}
        ]

        sustain = sum(
            e["articulation"].startswith("SUSTAIN")
            for e in rows
        )

        self.assertGreater(
            sustain / len(rows),
            0.95,
        )

    def test_fast_black_metal_has_dense_continuous_attack_fields(self):
        result = self._compile()

        counts = {
            row["gesture"]: row["event_counts"]["guitar"]
            for row in result["sections"]
        }

        self.assertGreater(
            counts["SPRINT"],
            100,
        )

        self.assertGreater(
            counts["PANIC"],
            100,
        )

    def test_pitch_vocabulary_is_constrained(self):
        result = self._compile()

        rows = [
            e for e in result["roles"]["rhythm_guitar"]
            if e["gesture"] == "SPRINT"
        ]

        pitch_classes = {
            e["pitch"] % 12
            for e in rows
        }

        self.assertLessEqual(
            len(pitch_classes),
            6,
        )

    def test_phrase_ids_recur_across_many_attacks(self):
        from collections import Counter

        result = self._compile()

        rows = [
            e for e in result["roles"]["rhythm_guitar"]
            if e["gesture"] in {"TRANCE", "SPRINT"}
        ]

        counts = Counter(
            e["phrase_id"]
            for e in rows
        )

        self.assertGreater(
            max(counts.values()),
            16,
        )

class BlackMetalDrumStateV02Tests(unittest.TestCase):

    def _compile(self):
        from products.sonoris_genre_compiler import compile_composition_request
        from products.sonoris_physical_compiler import compile_physical_performance

        plan = compile_composition_request({
            "genre": "black_metal",
            "title": "Where the Pines Forget",
            "mood": "icy, eerie, relentless, then dissolving",
            "tempo_bpm": 168,
            "meter": "4/4",
            "bars": 52,
            "tonal_center": "D-minor",
        })

        return compile_physical_performance(
            plan,
            seed=661028,
        )

    def test_sprint_is_sustained_blast_state(self):
        result = self._compile()

        rows = [
            e for e in result["roles"]["drums"]
            if e["gesture"] == "SPRINT"
        ]

        funcs = {
            e["function"]
            for e in rows
        }

        self.assertIn(
            "BLAST_RIDE",
            funcs,
        )

        self.assertIn(
            "BLAST_SNARE",
            funcs,
        )

        self.assertIn(
            "BLAST_KICK",
            funcs,
        )

    def test_stomp_is_not_a_blast(self):
        result = self._compile()

        rows = [
            e for e in result["roles"]["drums"]
            if e["gesture"] == "FROZEN_SUSPENSION"
        ]

        funcs = {
            e["function"]
            for e in rows
        }

        self.assertTrue(rows)

        self.assertIn(
            "FROZEN_CYMBAL",
            funcs,
        )

        self.assertIn(
            "FROZEN_KICK",
            funcs,
        )

        self.assertNotIn(
            "HALF_TIME_SNARE",
            funcs,
        )

        self.assertFalse(
            any(
                "BLAST" in f
                for f in funcs
            )
        )

    def test_collapse_is_sparse(self):
        result = self._compile()

        sections = {
            row["gesture"]: row
            for row in result["sections"]
        }

        self.assertLess(
            sections["COLLAPSE"]["event_counts"]["drums"],
            sections["SPRINT"]["event_counts"]["drums"],
        )

class BlackMetalGuitarShapeGrammarTests(unittest.TestCase):

    def _compile(self):
        from products.sonoris_genre_compiler import compile_composition_request
        from products.sonoris_physical_compiler import compile_physical_performance

        plan = compile_composition_request({
            "genre": "black_metal",
            "title": "Where the Pines Forget",
            "mood": "icy, eerie, relentless, then dissolving",
            "tempo_bpm": 168,
            "meter": "4/4",
            "bars": 52,
            "tonal_center": "D-minor",
        })

        return compile_physical_performance(
            plan,
            seed=661028,
        )

    def test_fast_riffs_are_shape_based_not_monophonic(self):
        result = self._compile()

        rows = [
            e
            for e in result["roles"]["rhythm_guitar"]
            if e["gesture"] in {"TRANCE", "SPRINT", "PANIC"}
        ]

        shaped = [
            e for e in rows
            if e.get("pitches")
            and len(e["pitches"]) >= 2
        ]

        self.assertGreater(
            len(shaped) / len(rows),
            0.95,
        )

    def test_trance_contains_pedal_shape_behavior(self):
        result = self._compile()

        shapes = {
            e.get("shape_type")
            for e in result["roles"]["rhythm_guitar"]
            if e["gesture"] == "TRANCE"
        }

        self.assertTrue(
            {
                "PEDAL_M3",
                "PEDAL_TT",
                "PEDAL_M2",
            } & shapes
        )

    def test_stomp_uses_heavier_voicing_than_sprint(self):
        result = self._compile()

        frozen = [
            e for e in result["roles"]["rhythm_guitar"]
            if e["gesture"] == "FROZEN_SUSPENSION"
        ]

        sprint = [
            e for e in result["roles"]["rhythm_guitar"]
            if e["gesture"] == "SPRINT"
        ]

        self.assertTrue(frozen)
        self.assertTrue(sprint)

        frozen_shapes = {
            e.get("shape_type")
            for e in frozen
        }

        self.assertTrue(
            {
                "PEDAL_TT",
                "PEDAL_P5",
                "PEDAL_M3",
                "PEDAL_M2",
            }.issubset(frozen_shapes)
        )

        self.assertTrue(
            all(
                e["articulation"].startswith("SUSTAIN")
                for e in frozen
            )
        )



class BlackMetalRiffChainV04Tests(unittest.TestCase):

    def _compile(self):
        from products.sonoris_genre_compiler import (
            compile_composition_request,
        )

        from products.sonoris_physical_compiler import (
            compile_physical_performance,
        )

        plan = compile_composition_request({
            "genre": "black_metal",
            "title": "Where the Pines Forget",
            "mood": (
                "icy, eerie, relentless, "
                "then dissolving"
            ),
            "tempo_bpm": 168,
            "meter": "4/4",
            "bars": 52,
            "tonal_center": "D-minor",
        })

        return compile_physical_performance(
            plan,
            seed=661028,
        )

    def test_v04_riff_chain_is_present(self):
        result = self._compile()

        functions = {
            e.get("function")
            for e in result["roles"]["rhythm_guitar"]
        }

        expected = {
            "FROST_SIGIL",
            "CORRUPTED_SIGIL",
            "KNIFE",
            "FROZEN_FIELD",
            "TRANSFIGURED_SIGIL",
            "WAR_ASCENT",
        }

        self.assertTrue(
            expected.issubset(functions),
            functions,
        )

    def test_stomp_source_becomes_frozen_suspension(self):
        result = self._compile()

        rows = [
            e
            for e in result["roles"]["rhythm_guitar"]
            if e["gesture"] == "FROZEN_SUSPENSION"
        ]

        self.assertTrue(rows)

        self.assertTrue(
            all(
                e["function"] == "FROZEN_FIELD"
                for e in rows
            )
        )

    def test_frozen_suspension_remains_fast(self):
        result = self._compile()

        rows = sorted(
            (
                e
                for e in result["roles"]["rhythm_guitar"]
                if e["gesture"] == "FROZEN_SUSPENSION"
            ),
            key=lambda e: e["tick"],
        )

        self.assertGreater(
            len(rows),
            32,
        )

        gaps = [
            b["tick"] - a["tick"]
            for a, b in zip(
                rows,
                rows[1:],
            )
            if b["tick"] > a["tick"]
        ]

        self.assertTrue(gaps)

        # 16th-note grid at TPQ 480 => 120 ticks.
        self.assertLessEqual(
            min(gaps),
            120,
        )

    def test_frozen_suspension_has_no_palm_mute(self):
        result = self._compile()

        rows = [
            e
            for e in result["roles"]["rhythm_guitar"]
            if e["gesture"] == "FROZEN_SUSPENSION"
        ]

        self.assertTrue(rows)

        self.assertFalse(
            any(
                "PALM_MUTE" in e["articulation"]
                for e in rows
            )
        )

    def test_opening_and_return_are_related_not_identical(self):
        result = self._compile()

        guitar = result["roles"]["rhythm_guitar"]

        opening = {
            tuple(e.get("pitches") or ())
            for e in guitar
            if e.get("function") == "FROST_SIGIL"
        }

        returning = {
            tuple(e.get("pitches") or ())
            for e in guitar
            if e.get("function") == "TRANSFIGURED_SIGIL"
        }

        self.assertTrue(opening)
        self.assertTrue(returning)

        self.assertNotEqual(
            opening,
            returning,
        )

        self.assertTrue(
            opening & returning,
            (
                "transformed return must retain "
                "some opening harmonic DNA"
            ),
        )

    def test_war_ascent_is_not_release(self):
        result = self._compile()

        war = [
            e
            for e in result["roles"]["rhythm_guitar"]
            if e.get("function") == "WAR_ASCENT"
        ]

        release = [
            e
            for e in result["roles"]["rhythm_guitar"]
            if e.get("function") == "UNRESOLVED_RELEASE"
        ]

        self.assertGreater(
            len(war),
            len(release),
        )

        self.assertGreater(
            len(war),
            32,
        )


class BlackMetalHarmonicSpanV05Tests(unittest.TestCase):

    def _compile(self):
        from products.sonoris_genre_compiler import (
            compile_composition_request,
        )

        from products.sonoris_physical_compiler import (
            compile_physical_performance,
        )

        plan = compile_composition_request({
            "genre": "black_metal",
            "title": "Where the Pines Forget",
            "mood": "icy, eerie, relentless, then dissolving",
            "tempo_bpm": 168,
            "meter": "4/4",
            "bars": 52,
            "tonal_center": "D-minor",
        })

        return compile_physical_performance(
            plan,
            seed=661028,
        )

    def test_corrupted_sigil_harmony_survives_two_bars(self):
        result = self._compile()

        rows = sorted(
            (
                e
                for e in result["roles"]["rhythm_guitar"]
                if e.get("function") == "CORRUPTED_SIGIL"
            ),
            key=lambda e: e["tick"],
        )

        self.assertTrue(rows)

        # 2 bars x 16 attacks = first 32 attacks must share shape.
        first = {
            tuple(e["pitches"])
            for e in rows[:32]
        }

        self.assertEqual(
            len(first),
            1,
        )

    def test_frozen_field_changes_only_every_two_bars(self):
        result = self._compile()

        rows = sorted(
            (
                e
                for e in result["roles"]["rhythm_guitar"]
                if e.get("function") == "FROZEN_FIELD"
            ),
            key=lambda e: e["tick"],
        )

        self.assertEqual(
            len(rows),
            8 * 16,
        )

        bar_shapes = []

        for bar in range(8):
            chunk = rows[
                bar * 16:
                (bar + 1) * 16
            ]

            shapes = {
                tuple(e["pitches"])
                for e in chunk
            }

            self.assertEqual(
                len(shapes),
                1,
            )

            bar_shapes.append(
                next(iter(shapes))
            )

        self.assertEqual(
            bar_shapes[0],
            bar_shapes[1],
        )

        self.assertEqual(
            bar_shapes[2],
            bar_shapes[3],
        )

        self.assertEqual(
            bar_shapes[4],
            bar_shapes[5],
        )

        self.assertEqual(
            bar_shapes[6],
            bar_shapes[7],
        )

        self.assertNotEqual(
            bar_shapes[0],
            bar_shapes[2],
        )

    def test_knife_harmony_changes_at_bar_scale_not_attack_scale(self):
        result = self._compile()

        rows = sorted(
            (
                e
                for e in result["roles"]["rhythm_guitar"]
                if e.get("function") == "KNIFE"
            ),
            key=lambda e: e["tick"],
        )

        for bar in range(8):
            chunk = rows[
                bar * 16:
                (bar + 1) * 16
            ]

            self.assertEqual(
                len({
                    tuple(e["pitches"])
                    for e in chunk
                }),
                1,
            )

    def test_drums_do_not_fill_every_harmonic_change(self):
        result = self._compile()

        rows = [
            e
            for e in result["roles"]["drums"]
            if e.get("gesture") == "PANIC"
        ]

        funcs = [
            e["function"]
            for e in rows
        ]

        # KNIFE harmony changes every bar.
        # Drum phrase punctuation only every two bars.
        crashes = funcs.count(
            "KNIFE_PHRASE_CRASH"
        )

        self.assertLessEqual(
            crashes,
            4,
        )

    def test_frozen_drums_follow_macro_span_clock(self):
        result = self._compile()

        rows = [
            e
            for e in result["roles"]["drums"]
            if e.get("gesture") == "FROZEN_SUSPENSION"
        ]

        funcs = [
            e["function"]
            for e in rows
        ]

        # Three internal boundaries between four 2-bar spans.
        self.assertEqual(
            funcs.count("FROZEN_BOUNDARY_CRASH"),
            3,
        )
