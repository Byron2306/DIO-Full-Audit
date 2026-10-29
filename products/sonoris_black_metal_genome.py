from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Any


# ============================================================
# SONORIS BLACK METAL GENOME v1
#
# These are compositional possibilities.
# They are NOT a fixed song sequence.
# ============================================================


INTRO_ARCHETYPES = (
    "IMMEDIATE_WALL",
    "LAMENT_PRELUDE",
    "COLD_DRONE",
    "FEEDBACK_RITUAL",
    "LONE_TREMOLO",
    "CHORDAL_PROCESSION",
)

ENDING_ARCHETYPES = (
    "UNRESOLVED_RELEASE",
    "ABRUPT_EXTINCTION",
    "FEEDBACK_DISSOLUTION",
    "FROZEN_PEDAL_DECAY",
    "FINAL_ASCENT_COLLAPSE",
)

ATMOSPHERE_MODES = (
    "NONE",
    "SUBLIMINAL_PAD",
    "BREATHING_KEYS",
    "COLD_DRONE",
    "CHOIR_SHADOW",
)

REGISTER_DEVICES = (
    "NONE",
    "REGISTER_REVELATION",
    "OCTAVE_SHADOW",
    "LOW_TO_HIGH_RETURN",
)

RIFF_FAMILIES = (
    "FROST_SIGIL",
    "CORRUPTED_SIGIL",
    "KNIFE",
    "FROZEN_FIELD",
    "TRANSFIGURED_SIGIL",
    "WAR_ASCENT",
)

DRUM_STATES = (
    "FROST_BLAST",
    "FULL_BLAST",
    "DOUBLE_KICK_STORM",
    "WITHDRAWN_BLAST",
    "MARTIAL_BLAST",
    "ASHEN_CONTINUUM",
)


@dataclass(frozen=True)
class BlackMetalBlueprint:
    seed: int
    bars: int
    tonal_center: str

    intro: str
    ending: str
    atmosphere: str
    register_device: str

    riff_sequence: tuple[str, ...]
    drum_sequence: tuple[str, ...]

    harmonic_span_bars: tuple[int, ...]

    lament_intro: bool
    keys_present: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "bars": self.bars,
            "tonal_center": self.tonal_center,
            "intro": self.intro,
            "ending": self.ending,
            "atmosphere": self.atmosphere,
            "register_device": self.register_device,
            "riff_sequence": list(self.riff_sequence),
            "drum_sequence": list(self.drum_sequence),
            "harmonic_span_bars": list(
                self.harmonic_span_bars
            ),
            "lament_intro": self.lament_intro,
            "keys_present": self.keys_present,
        }


def _weighted(
    rng: Random,
    values: tuple[str, ...],
    weights: tuple[int, ...],
) -> str:
    return rng.choices(
        values,
        weights=weights,
        k=1,
    )[0]


def compose_black_metal_blueprint(
    *,
    seed: int,
    tonal_center: str = "D-minor",
    requested_bars: int | None = None,
    mood: str = "",
) -> BlackMetalBlueprint:

    rng = Random(seed)

    bars = requested_bars or rng.choice(
        (88, 96, 104, 112, 120, 128, 136)
    )

    intro = _weighted(
        rng,
        INTRO_ARCHETYPES,
        (18, 18, 12, 10, 18, 10),
    )

    atmosphere = _weighted(
        rng,
        ATMOSPHERE_MODES,
        (18, 24, 18, 22, 10),
    )

    ending = rng.choice(
        ENDING_ARCHETYPES
    )

    register_device = _weighted(
        rng,
        REGISTER_DEVICES,
        (38, 25, 18, 19),
    )

    # --------------------------------------------------------
    # Choose a RIFF CHAIN, not a verse/chorus sequence.
    #
    # Minimum four distinct families.
    # No fixed canonical order.
    # --------------------------------------------------------

    available = list(RIFF_FAMILIES)
    rng.shuffle(available)

    family_count = rng.randint(4, 6)

    core = available[:family_count]

    sequence: list[str] = []

    # First exposition.
    sequence.extend(core)

    # Mutation / return phase.
    return_count = rng.randint(
        2,
        min(4, len(core)),
    )

    returns = rng.sample(
        core,
        return_count,
    )

    rng.shuffle(returns)

    sequence.extend(returns)

    # Optional late escalation.
    if (
        "WAR_ASCENT" not in sequence[-2:]
        and rng.random() < 0.65
    ):
        sequence.append("WAR_ASCENT")

    # Do not permit identical adjacent riff families.
    compact: list[str] = []

    for family in sequence:
        if not compact or compact[-1] != family:
            compact.append(family)

    # --------------------------------------------------------
    # Harmonic changes remain much slower than picking.
    # 1–2 bars per harmonic state.
    # --------------------------------------------------------

    spans = tuple(
        rng.choices(
            (1, 2),
            weights=(35, 65),
            k=len(compact),
        )
    )

    # --------------------------------------------------------
    # Drum states correlate with macro tension,
    # but DO NOT change every time the harmony changes.
    # --------------------------------------------------------

    drums: list[str] = []

    for index, family in enumerate(compact):
        if family == "KNIFE":
            state = "DOUBLE_KICK_STORM"

        elif family == "FROZEN_FIELD":
            state = "WITHDRAWN_BLAST"

        elif family == "WAR_ASCENT":
            state = "MARTIAL_BLAST"

        elif family == "CORRUPTED_SIGIL":
            state = "FULL_BLAST"

        else:
            state = rng.choice(
                (
                    "FROST_BLAST",
                    "FULL_BLAST",
                    "ASHEN_CONTINUUM",
                )
            )

        # Allow a drum state to survive across a riff boundary.
        if (
            drums
            and rng.random() < 0.30
        ):
            state = drums[-1]

        drums.append(state)

    lament_intro = (
        intro == "LAMENT_PRELUDE"
    )

    keys_present = (
        lament_intro
        or atmosphere
        in {
            "BREATHING_KEYS",
            "SUBLIMINAL_PAD",
            "CHOIR_SHADOW",
        }
    )

    return BlackMetalBlueprint(
        seed=seed,
        bars=bars,
        tonal_center=tonal_center,
        intro=intro,
        ending=ending,
        atmosphere=atmosphere,
        register_device=register_device,
        riff_sequence=tuple(compact),
        drum_sequence=tuple(drums),
        harmonic_span_bars=spans,
        lament_intro=lament_intro,
        keys_present=keys_present,
    )
