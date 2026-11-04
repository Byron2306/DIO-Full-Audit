from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from products.sonoris_song_engine import (
    compile_song,
)


def load_events(
    root: Path,
    job_id: str,
) -> dict:
    """
    Read the event artifact produced by compile_song().
    Support the current Sonoris job layouts.
    """
    job = root / job_id

    candidates = (
        job / "EVENTS.json",
        job / "SONORIS_EVENTS.json",
        job / "events.json",
        job / "composition_events.json",
    )

    for path in candidates:
        if path.is_file():
            return json.loads(
                path.read_text()
            )

    # Fallback: locate a JSON artifact containing the event roles.
    for path in sorted(
        job.glob("*.json")
    ):
        try:
            payload = json.loads(
                path.read_text()
            )
        except Exception:
            continue

        if not isinstance(
            payload,
            dict,
        ):
            continue

        if (
            "harmony" in payload
            and isinstance(
                payload["harmony"],
                list,
            )
        ):
            return payload

        roles = payload.get("roles")

        if (
            isinstance(roles, dict)
            and "harmony" in roles
        ):
            return roles

        events = payload.get("events")

        if (
            isinstance(events, dict)
            and "harmony" in events
        ):
            return events

    raise AssertionError(
        f"EVENT_ARTIFACT_NOT_FOUND: {job}"
    )


def compositional_fingerprint(
    events: dict,
) -> tuple:
    """Fingerprint the composed musical structure, not performance velocity."""

    roles = ("harmony", "lead", "bass", "drums", "keys", "folk")
    result = []

    for role in roles:
        rows = events.get(role, [])

        if not isinstance(rows, list):
            raise AssertionError(f"INVALID_EVENT_ROLE: {role}")

        musical_events = tuple(sorted(
            (
                round(float(row["beat"]), 4),
                round(float(row["duration"]), 4),
                int(row["pitch"]),
                str(row.get("articulation", "")),
            )
            for row in rows
        ))

        result.append((role, musical_events))

    return tuple(result)



def signature(
    root: Path,
    job_id: str,
) -> dict:
    path = (
        root
        / job_id
        / "METAL_PATTERN_SIGNATURE.json"
    )

    if not path.is_file():
        raise AssertionError(
            f"METAL_PATTERN_SIGNATURE_MISSING: {path}"
        )

    return json.loads(
        path.read_text()
    )


class SonorisMotifDNATests(
    unittest.TestCase
):

    GENRES = (
        "thrash_metal",
        "death_metal",
        "doom_metal",
        "power_metal",
        "prog_metal",
        "industrial_metal",
        "alternative_metal",
        "nu_metal",
    )

    SEEDS = (
        11,
        29,
        47,
        83,
        131,
        197,
    )

    def test_same_genre_many_seeds_generate_distinct_compositions(
        self,
    ):
        with tempfile.TemporaryDirectory(
            prefix="sonoris-motif-diversity-"
        ) as tmp:
            root = Path(tmp)

            for genre in self.GENRES:
                fingerprints = set()
                dna_hashes = set()

                for seed in self.SEEDS:
                    job = (
                        f"{genre}-{seed}"
                    )

                    compile_song(
                        {
                            "genre": genre,
                            "seed": seed,
                            "bars": 12,
                        },
                        output_root=root,
                        job_id=job,
                    )

                    events = load_events(
                        root,
                        job,
                    )

                    sig = signature(
                        root,
                        job,
                    )

                    fingerprints.add(
                        compositional_fingerprint(
                            events
                        )
                    )

                    dna = sig.get(
                        "motif_dna"
                    )

                    self.assertIsInstance(
                        dna,
                        dict,
                        (
                            genre,
                            seed,
                            sig,
                        ),
                    )

                    self.assertIn(
                        "sha256",
                        dna,
                    )

                    dna_hashes.add(
                        dna["sha256"]
                    )

                    self.assertIs(
                        sig.get(
                            "source_phrase_reuse"
                        ),
                        False,
                    )

                    self.assertEqual(
                        sig.get(
                            "composition_source"
                        ),
                        (
                            "generated_song_"
                            "specific_motif_dna"
                        ),
                    )

                self.assertEqual(
                    len(dna_hashes),
                    len(self.SEEDS),
                    (
                        genre,
                        dna_hashes,
                    ),
                )

                self.assertGreaterEqual(
                    len(fingerprints),
                    5,
                    (
                        genre,
                        len(fingerprints),
                    ),
                )

    def test_same_seed_is_compositionally_deterministic(
        self,
    ):
        with tempfile.TemporaryDirectory(
            prefix="sonoris-motif-determinism-"
        ) as tmp:
            root = Path(tmp)

            request = {
                "genre": "thrash_metal",
                "seed": 2306,
                "bars": 12,
            }

            compile_song(
                request,
                output_root=root,
                job_id="a",
            )

            compile_song(
                request,
                output_root=root,
                job_id="b",
            )

            a = load_events(
                root,
                "a",
            )

            b = load_events(
                root,
                "b",
            )

            self.assertEqual(
                compositional_fingerprint(a),
                compositional_fingerprint(b),
            )

            da = signature(
                root,
                "a",
            )

            db = signature(
                root,
                "b",
            )

            self.assertEqual(
                da[
                    "motif_dna"
                ][
                    "sha256"
                ],
                db[
                    "motif_dna"
                ][
                    "sha256"
                ],
            )


if __name__ == "__main__":
    unittest.main()
