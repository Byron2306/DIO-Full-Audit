from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any, Mapping


# ============================================================
# SONORIS MOTIF DNA
#
# A genre supplies constraints.
# A song seed creates its own musical vocabulary.
#
# Nothing here stores or reproduces source-song phrases.
# ============================================================


@dataclass(frozen=True)
class MotifCell:
    onsets: tuple[float, ...]
    degrees: tuple[int, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "onsets": list(self.onsets),
            "degrees": list(self.degrees),
        }


@dataclass(frozen=True)
class SongMotifDNA:
    schema: str

    genre: str
    seed: int

    harmonic_route: tuple[int, ...]
    primary: MotifCell
    secondary: MotifCell
    turnaround: MotifCell

    lead_pool: tuple[int, ...]

    density: float
    rest_probability: float
    pedal_probability: float
    chromatic_probability: float
    dissonance_probability: float
    mutation_strength: float

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "schema": self.schema,
            "genre": self.genre,
            "seed": self.seed,
            "harmonic_route": list(
                self.harmonic_route
            ),
            "primary": self.primary.as_dict(),
            "secondary": self.secondary.as_dict(),
            "turnaround": self.turnaround.as_dict(),
            "lead_pool": list(
                self.lead_pool
            ),
            "density": self.density,
            "rest_probability": self.rest_probability,
            "pedal_probability": self.pedal_probability,
            "chromatic_probability": self.chromatic_probability,
            "dissonance_probability": self.dissonance_probability,
            "mutation_strength": self.mutation_strength,
        }

        body = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

        payload["sha256"] = hashlib.sha256(
            body
        ).hexdigest()

        return payload


GENRE_BEHAVIOR = {
    "thrash_metal": {
        "grid": (0.25, 0.5),
        "attacks": (6, 8, 10, 12),
        "interval_pool": (
            0, 0, 0, 0,
            -1, 1,
            2, 3,
            5, 6,
        ),
        "harmonic_pool": (
            0, -1, 1, -2, 2, -5, 5, 6,
        ),
        "pedal_probability": 0.58,
        "chromatic_probability": 0.28,
        "dissonance_probability": 0.18,
        "rest_probability": 0.12,
        "mutation_strength": 0.28,
        "lead_pool": (
            0, 3, 5, 6, 7, 10,
        ),
    },

    "death_metal": {
        "grid": (0.25, 0.5),
        "attacks": (8, 10, 12, 16),
        "interval_pool": (
            0, 0,
            -1, 1,
            3, 5, 6,
            10, 11,
        ),
        "harmonic_pool": (
            0, 1, -1, 3, 6, -5,
        ),
        "pedal_probability": 0.38,
        "chromatic_probability": 0.42,
        "dissonance_probability": 0.38,
        "rest_probability": 0.08,
        "mutation_strength": 0.42,
        "lead_pool": (
            0, 1, 3, 5, 6, 7, 10,
        ),
    },

    "power_metal": {
        "grid": (0.25, 0.5),
        "attacks": (8, 10, 12),
        "interval_pool": (
            0, 0,
            2, 3, 5, 7, 9, 10,
        ),
        "harmonic_pool": (
            0, 3, 5, 7, -2,
        ),
        "pedal_probability": 0.32,
        "chromatic_probability": 0.06,
        "dissonance_probability": 0.04,
        "rest_probability": 0.06,
        "mutation_strength": 0.20,
        "lead_pool": (
            0, 2, 3, 5, 7, 9, 10,
        ),
    },

    "doom_metal": {
        "grid": (0.5, 1.0),
        "attacks": (2, 3, 4),
        "interval_pool": (
            0, 0,
            -1, -2,
            3, 5, 6, 10,
        ),
        "harmonic_pool": (
            0, -1, -2, -5, 3, 6,
        ),
        "pedal_probability": 0.22,
        "chromatic_probability": 0.16,
        "dissonance_probability": 0.34,
        "rest_probability": 0.34,
        "mutation_strength": 0.18,
        "lead_pool": (
            0, 3, 5, 6, 7, 10,
        ),
    },

    "glam_metal": {
        "grid": (0.5, 0.75),
        "attacks": (5, 6, 8),
        "interval_pool": (
            0, 0,
            2, 4, 5, 7, 9,
        ),
        "harmonic_pool": (
            0, 5, 7, 2, 9,
        ),
        "pedal_probability": 0.26,
        "chromatic_probability": 0.04,
        "dissonance_probability": 0.02,
        "rest_probability": 0.12,
        "mutation_strength": 0.18,
        "lead_pool": (
            0, 2, 4, 5, 7, 9,
        ),
    },

    "folk_metal": {
        "grid": (0.5, 0.75),
        "attacks": (5, 6, 8),
        "interval_pool": (
            0, 0,
            2, 3, 5, 7, 10,
        ),
        "harmonic_pool": (
            0, 5, -2, 7, 3,
        ),
        "pedal_probability": 0.42,
        "chromatic_probability": 0.06,
        "dissonance_probability": 0.04,
        "rest_probability": 0.10,
        "mutation_strength": 0.22,
        "lead_pool": (
            0, 2, 3, 5, 7, 10,
        ),
    },

    "prog_metal": {
        "grid": (0.25, 0.5, 0.75),
        "attacks": (5, 7, 9, 11),
        "interval_pool": (
            0, 2, 3, 5, 6, 7, 10,
        ),
        "harmonic_pool": (
            0, 3, 5, 6, -2, 1,
        ),
        "pedal_probability": 0.24,
        "chromatic_probability": 0.14,
        "dissonance_probability": 0.28,
        "rest_probability": 0.16,
        "mutation_strength": 0.46,
        "lead_pool": (
            0, 2, 3, 5, 6, 7, 10,
        ),
    },

    "industrial_metal": {
        "grid": (0.5, 1.0),
        "attacks": (4, 5, 6, 8),
        "interval_pool": (
            0, 0, 0, 0,
            1, 6,
        ),
        "harmonic_pool": (
            0, 0, 1, 6,
        ),
        "pedal_probability": 0.70,
        "chromatic_probability": 0.14,
        "dissonance_probability": 0.20,
        "rest_probability": 0.18,
        "mutation_strength": 0.12,
        "lead_pool": (
            0, 1, 6, 7,
        ),
    },

    "alternative_metal": {
        "grid": (0.5, 0.75, 1.0),
        "attacks": (4, 5, 6),
        "interval_pool": (
            0, 0,
            3, 5, 6, 7, 10,
        ),
        "harmonic_pool": (
            0, 3, 5, 6, -2,
        ),
        "pedal_probability": 0.28,
        "chromatic_probability": 0.08,
        "dissonance_probability": 0.16,
        "rest_probability": 0.24,
        "mutation_strength": 0.28,
        "lead_pool": (
            0, 3, 5, 7, 10,
        ),
    },

    "nu_metal": {
        "grid": (0.5, 0.75, 1.0),
        "attacks": (4, 5, 6),
        "interval_pool": (
            0, 0, 0,
            1, 5, 6,
        ),
        "harmonic_pool": (
            0, 1, 6, 5,
        ),
        "pedal_probability": 0.64,
        "chromatic_probability": 0.16,
        "dissonance_probability": 0.18,
        "rest_probability": 0.28,
        "mutation_strength": 0.20,
        "lead_pool": (
            0, 1, 3, 5, 6,
        ),
    },
}


def _weighted_degree(
    rng: random.Random,
    config: Mapping[str, Any],
) -> int:
    if (
        rng.random()
        < float(
            config["pedal_probability"]
        )
    ):
        return 0

    pool = tuple(
        int(x)
        for x
        in config["interval_pool"]
    )

    return rng.choice(pool)


def _make_cell(
    rng: random.Random,
    config: Mapping[str, Any],
    *,
    beats_per_bar: float,
    attack_bias: int = 0,
) -> MotifCell:

    attack_count = max(
        2,
        rng.choice(
            tuple(config["attacks"])
        )
        + attack_bias,
    )

    grid = min(
        float(x)
        for x
        in config["grid"]
    )

    slots = [
        round(i * grid, 5)
        for i
        in range(
            int(
                beats_per_bar / grid
            )
        )
    ]

    rng.shuffle(slots)

    chosen = sorted(
        slots[
            : min(
                attack_count,
                len(slots),
            )
        ]
    )

    if 0.0 not in chosen:
        chosen[0] = 0.0
        chosen.sort()

    degrees: list[int] = []

    previous = 0

    for _ in chosen:
        degree = _weighted_degree(
            rng,
            config,
        )

        # Phrase continuity:
        # sometimes move locally from the previous pitch instead
        # of jumping to an unrelated interval.
        if (
            degrees
            and rng.random() < 0.42
        ):
            motion = rng.choice(
                (-2, -1, 0, 1, 2)
            )

            candidate = previous + motion

            if -7 <= candidate <= 12:
                degree = candidate

        degrees.append(degree)
        previous = degree

    # Avoid completely static cells.
    if len(set(degrees)) == 1:
        degrees[-1] = rng.choice(
            [
                x
                for x
                in config["interval_pool"]
                if x != degrees[0]
            ]
        )

    return MotifCell(
        onsets=tuple(chosen),
        degrees=tuple(degrees),
    )


def _mutate_cell(
    rng: random.Random,
    source: MotifCell,
    config: Mapping[str, Any],
    *,
    beats_per_bar: float,
) -> MotifCell:

    onsets = list(source.onsets)
    degrees = list(source.degrees)

    strength = float(
        config["mutation_strength"]
    )

    for i in range(len(degrees)):
        if rng.random() < strength:
            if rng.random() < 0.55:
                degrees[i] += rng.choice(
                    (-2, -1, 1, 2)
                )
            else:
                degrees[i] = _weighted_degree(
                    rng,
                    config,
                )

    # Occasionally remove one attack.
    if (
        len(onsets) > 3
        and rng.random()
        < float(
            config["rest_probability"]
        )
    ):
        index = rng.randrange(
            1,
            len(onsets),
        )

        onsets.pop(index)
        degrees.pop(index)

    # Occasionally insert a new grid attack.
    if rng.random() < strength:
        grid = min(
            float(x)
            for x
            in config["grid"]
        )

        candidates = [
            round(i * grid, 5)
            for i
            in range(
                int(
                    beats_per_bar / grid
                )
            )
            if round(
                i * grid,
                5,
            )
            not in onsets
        ]

        if candidates:
            new_onset = rng.choice(
                candidates
            )

            onsets.append(
                new_onset
            )

            degrees.append(
                _weighted_degree(
                    rng,
                    config,
                )
            )

            pairs = sorted(
                zip(
                    onsets,
                    degrees,
                )
            )

            onsets = [
                pair[0]
                for pair in pairs
            ]

            degrees = [
                pair[1]
                for pair in pairs
            ]

    return MotifCell(
        onsets=tuple(onsets),
        degrees=tuple(degrees),
    )


def generate_song_motif_dna(
    *,
    genre: str,
    seed: int,
    beats_per_bar: float,
) -> SongMotifDNA:

    if genre not in GENRE_BEHAVIOR:
        raise ValueError(
            f"no motif grammar for {genre}"
        )

    config = GENRE_BEHAVIOR[
        genre
    ]

    rng = random.Random(
        f"sonoris-motif-dna:{genre}:{seed}"
    )

    primary = _make_cell(
        rng,
        config,
        beats_per_bar=beats_per_bar,
    )

    secondary = _mutate_cell(
        rng,
        primary,
        config,
        beats_per_bar=beats_per_bar,
    )

    turnaround = _make_cell(
        rng,
        config,
        beats_per_bar=beats_per_bar,
        attack_bias=-1,
    )

    harmonic_count = rng.choice(
        (3, 4, 5)
    )

    harmonic_route = [0]

    pool = tuple(
        int(x)
        for x
        in config["harmonic_pool"]
        if int(x) != 0
    )

    while len(
        harmonic_route
    ) < harmonic_count:
        candidate = rng.choice(
            pool
        )

        if (
            candidate
            != harmonic_route[-1]
        ):
            harmonic_route.append(
                candidate
            )

    return SongMotifDNA(
        schema=(
            "dio.sonoris."
            "song_motif_dna.v1"
        ),
        genre=genre,
        seed=seed,
        harmonic_route=tuple(
            harmonic_route
        ),
        primary=primary,
        secondary=secondary,
        turnaround=turnaround,
        lead_pool=tuple(
            config["lead_pool"]
        ),
        density=(
            len(primary.onsets)
            / max(
                1,
                beats_per_bar
                / min(
                    config["grid"]
                ),
            )
        ),
        rest_probability=float(
            config["rest_probability"]
        ),
        pedal_probability=float(
            config["pedal_probability"]
        ),
        chromatic_probability=float(
            config["chromatic_probability"]
        ),
        dissonance_probability=float(
            config[
                "dissonance_probability"
            ]
        ),
        mutation_strength=float(
            config["mutation_strength"]
        ),
    )


def select_song_cell(
    dna: SongMotifDNA,
    *,
    section_index: int,
    bar_in_section: int,
    variant: str,
) -> MotifCell:

    # Stable internal identity:
    # the same song keeps returning to related material.
    phase = (
        section_index
        + bar_in_section // 2
    ) % 4

    if phase in {0, 3}:
        cell = dna.primary
    elif phase == 1:
        cell = dna.secondary
    else:
        cell = dna.turnaround

    # Song-type changes how often material is exposed,
    # not which source riff it copies.
    if variant == "space":
        onsets = cell.onsets[::2]
        degrees = cell.degrees[::2]

        if not onsets:
            return MotifCell(
                (0.0,),
                (0,),
            )

        return MotifCell(
            tuple(onsets),
            tuple(degrees),
        )

    if (
        variant == "fracture"
        and len(cell.onsets) > 2
        and bar_in_section % 4 == 3
    ):
        return MotifCell(
            cell.onsets[1:],
            cell.degrees[1:],
        )

    return cell
