from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from random import Random
from typing import Any

from products.sonoris_black_metal_genome import (
    BlackMetalBlueprint,
    compose_black_metal_blueprint,
)
from products.sonoris_genre_compiler import (
    compile_composition_request,
)


# ============================================================
# GENOME -> GOVERNED PLAN
#
# Genome:
#   decides WHAT kind of song this is.
#
# Governed compiler:
#   places those decisions in time.
#
# Physical compiler:
#   performs those decisions.
# ============================================================


FAMILY_GESTURES = {
    "FROST_SIGIL": (
        "TRANCE",
        "TRANCE",
    ),
    "CORRUPTED_SIGIL": (
        "SPRINT",
        "SPRINT",
    ),
    "KNIFE": (
        "PANIC",
        "PANIC",
    ),
    "FROZEN_FIELD": (
        "STOMP",
        "FROZEN_SUSPENSION",
    ),
    "TRANSFIGURED_SIGIL": (
        "TRANCE",
        "TRANCE",
    ),
    "WAR_ASCENT": (
        "HOOK",
        "HOOK",
    ),
}


INTRO_FAMILY = {
    "IMMEDIATE_WALL": None,
    "LAMENT_PRELUDE": "FROST_SIGIL",
    "COLD_DRONE": "FROZEN_FIELD",
    "FEEDBACK_RITUAL": "TRANSFIGURED_SIGIL",
    "LONE_TREMOLO": "FROST_SIGIL",
    "CHORDAL_PROCESSION": "TRANSFIGURED_SIGIL",
}


INTRO_BARS = {
    "IMMEDIATE_WALL": 0,
    "LAMENT_PRELUDE": 8,
    "COLD_DRONE": 8,
    "FEEDBACK_RITUAL": 4,
    "LONE_TREMOLO": 4,
    "CHORDAL_PROCESSION": 8,
}


INTRO_ATMOSPHERE = {
    "IMMEDIATE_WALL": "NONE",
    "LAMENT_PRELUDE": "BREATHING_KEYS",
    "COLD_DRONE": "COLD_DRONE",
    "FEEDBACK_RITUAL": "NONE",
    "LONE_TREMOLO": "NONE",
    "CHORDAL_PROCESSION": "SUBLIMINAL_PAD",
}


ENDING_BARS = 4


def _sha256(payload: dict[str, Any]) -> str:
    clean = deepcopy(payload)
    clean.pop("sha256", None)

    body = json.dumps(
        clean,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(body).hexdigest()


def _gesture_contracts(
    *,
    tonal_center: str,
    mood: str,
    bpm: int,
) -> dict[str, dict[str, Any]]:
    """
    Ask the existing genre compiler for canonical black-metal contracts.

    This preserves Sonoris' established gesture semantics instead of
    re-defining them inside the genome bridge.
    """
    specimen = compile_composition_request({
        "genre": "black_metal",
        "title": "contract-source",
        "mood": mood,
        "tempo_bpm": bpm,
        "meter": "4/4",
        "bars": 52,
        "tonal_center": tonal_center,
    })

    contracts: dict[str, dict[str, Any]] = {}

    for section in specimen["sections"]:
        gesture = str(
            section["gesture"]
        )

        contract = deepcopy(
            section.get(
                "contract",
                {},
            )
        )

        if contract:
            contracts[gesture] = contract

    return contracts


def _allocate_body_bars(
    blueprint: BlackMetalBlueprint,
    *,
    body_bars: int,
) -> tuple[int, ...]:
    """
    Allocate complete four-bar phrases across the genome's riff chain.

    Every section gets at least four bars.

    Remaining time is distributed deterministically in four-bar chunks.
    A harmonic span of two bars therefore always divides a section
    cleanly.

    This controls FORM without inventing new riff-family decisions.
    """
    count = len(
        blueprint.riff_sequence
    )

    minimum = count * 4

    if body_bars < minimum:
        raise ValueError(
            "BLACK_METAL_BODY_TOO_SHORT: "
            f"body_bars={body_bars} "
            f"minimum={minimum}"
        )

    if body_bars % 4:
        raise ValueError(
            f"BLACK_METAL_BODY_NOT_FOUR_BAR_ALIGNED: {body_bars}"
        )

    bars = [4] * count

    remaining = (
        body_bars
        - minimum
    )

    chunks = remaining // 4

    rng = Random(
        blueprint.seed
        ^ 0xB10C
    )

    # Bias expansion toward sections whose harmonic grammar already
    # prefers two-bar spans, without making it deterministic by family.
    weights = [
        2.0
        if span == 2
        else 1.0
        for span
        in blueprint.harmonic_span_bars
    ]

    while chunks:
        candidates = [
            i
            for i, value
            in enumerate(bars)
            if value < 16
        ]

        if not candidates:
            raise RuntimeError(
                "BLACK_METAL_BAR_ALLOCATION_EXHAUSTED"
            )

        candidate_weights = [
            weights[i]
            for i in candidates
        ]

        selected = rng.choices(
            candidates,
            weights=candidate_weights,
            k=1,
        )[0]

        bars[selected] += 4
        chunks -= 1

    return tuple(bars)


def _section(
    *,
    index: int,
    name: str,
    raw_gesture: str,
    execution_gesture: str,
    bars: int,
    start_bar: int,
    contract: dict[str, Any],
    riff_family: str | None,
    drum_state: str,
    harmonic_span_bars: int,
    atmosphere: str,
    register_device: str,
    section_role: str,
    intro_archetype: str | None = None,
    ending_archetype: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "index": index,
        "section": name,
        "section_role": section_role,

        "gesture": raw_gesture,
        "execution_gesture": execution_gesture,

        "bars": bars,
        "start_bar": start_bar,
        "end_bar": start_bar + bars,

        "contract": deepcopy(
            contract
        ),

        "riff_family": riff_family,
        "drum_state": drum_state,
        "harmonic_span_bars": harmonic_span_bars,

        "atmosphere": atmosphere,
        "register_device": register_device,
    }

    if intro_archetype is not None:
        row["intro_archetype"] = (
            intro_archetype
        )

    if ending_archetype is not None:
        row["ending_archetype"] = (
            ending_archetype
        )

    return row


def compile_black_metal_governed_plan(
    *,
    seed: int,
    title: str | None = None,
    tonal_center: str = "D-minor",
    bars: int | None = None,
    mood: str = "icy, sorrowful, hostile, atmospheric",
    bpm: int = 168,
) -> dict[str, Any]:

    blueprint = (
        compose_black_metal_blueprint(
            seed=seed,
            tonal_center=tonal_center,
            requested_bars=bars,
            mood=mood,
        )
    )

    title = (
        title
        or f"Black Metal Seed {seed}"
    )

    contracts = _gesture_contracts(
        tonal_center=tonal_center,
        mood=mood,
        bpm=bpm,
    )

    intro_bars = INTRO_BARS[
        blueprint.intro
    ]

    ending_bars = ENDING_BARS

    body_bars = (
        blueprint.bars
        - intro_bars
        - ending_bars
    )

    body_allocations = (
        _allocate_body_bars(
            blueprint,
            body_bars=body_bars,
        )
    )

    sections: list[
        dict[str, Any]
    ] = []

    cursor = 0
    section_index = 1

    # ========================================================
    # INTRO
    #
    # The physical family gives the current renderer something valid
    # to perform.
    #
    # intro_archetype remains explicit so specialized intro rendering
    # can later replace that realization without changing composition.
    # ========================================================

    intro_family = INTRO_FAMILY[
        blueprint.intro
    ]

    if intro_bars:
        assert intro_family is not None

        (
            intro_raw,
            intro_execution,
        ) = FAMILY_GESTURES[
            intro_family
        ]

        sections.append(
            _section(
                index=section_index,
                name=(
                    f"Intro: "
                    f"{blueprint.intro}"
                ),
                raw_gesture=intro_raw,
                execution_gesture=(
                    intro_execution
                ),
                bars=intro_bars,
                start_bar=cursor,
                contract=contracts.get(
                    intro_raw,
                    {},
                ),
                riff_family=intro_family,
                drum_state=(
                    "WITHDRAWN_BLAST"
                    if blueprint.intro
                    in {
                        "LAMENT_PRELUDE",
                        "COLD_DRONE",
                    }
                    else "FROST_BLAST"
                ),
                harmonic_span_bars=2,
                atmosphere=(
                    INTRO_ATMOSPHERE[
                        blueprint.intro
                    ]
                ),
                register_device="NONE",
                section_role="INTRO",
                intro_archetype=(
                    blueprint.intro
                ),
            )
        )

        cursor += intro_bars
        section_index += 1

    # ========================================================
    # BODY
    # ========================================================

    for ordinal, (
        family,
        drum_state,
        harmonic_span,
        section_bars,
    ) in enumerate(
        zip(
            blueprint.riff_sequence,
            blueprint.drum_sequence,
            blueprint.harmonic_span_bars,
            body_allocations,
        ),
        start=1,
    ):
        (
            raw_gesture,
            execution_gesture,
        ) = FAMILY_GESTURES[
            family
        ]

        register_device = "NONE"

        # Apply the song-level register device late rather than everywhere.
        if (
            blueprint.register_device
            != "NONE"
            and ordinal
            >= max(
                1,
                len(
                    blueprint.riff_sequence
                )
                - 1,
            )
        ):
            register_device = (
                blueprint.register_device
            )

        atmosphere = "NONE"

        # Atmosphere is a song-level identity but need not occupy
        # every section.
        if blueprint.atmosphere != "NONE":
            if family in {
                "FROST_SIGIL",
                "FROZEN_FIELD",
                "TRANSFIGURED_SIGIL",
                "WAR_ASCENT",
            }:
                atmosphere = (
                    blueprint.atmosphere
                )

        sections.append(
            _section(
                index=section_index,
                name=(
                    f"{family} {ordinal}"
                ),
                raw_gesture=raw_gesture,
                execution_gesture=(
                    execution_gesture
                ),
                bars=section_bars,
                start_bar=cursor,
                contract=contracts.get(
                    raw_gesture,
                    {},
                ),
                riff_family=family,
                drum_state=drum_state,
                harmonic_span_bars=(
                    harmonic_span
                ),
                atmosphere=atmosphere,
                register_device=(
                    register_device
                ),
                section_role="BODY",
            )
        )

        cursor += section_bars
        section_index += 1

    # ========================================================
    # ENDING
    # ========================================================

    sections.append(
        _section(
            index=section_index,
            name=(
                f"Ending: "
                f"{blueprint.ending}"
            ),
            raw_gesture="RELEASE",
            execution_gesture="RELEASE",
            bars=ending_bars,
            start_bar=cursor,
            contract=contracts.get(
                "RELEASE",
                {},
            ),
            riff_family=None,
            drum_state="WITHDRAWN_BLAST",
            harmonic_span_bars=2,
            atmosphere=(
                blueprint.atmosphere
                if blueprint.atmosphere
                != "NONE"
                else "NONE"
            ),
            register_device="NONE",
            section_role="ENDING",
            ending_archetype=(
                blueprint.ending
            ),
        )
    )

    cursor += ending_bars

    if cursor != blueprint.bars:
        raise RuntimeError(
            "BLACK_METAL_BAR_CUSTODY_FAILURE: "
            f"expected={blueprint.bars} "
            f"actual={cursor}"
        )

    # Start from the established governed-plan schema.
    base = compile_composition_request({
        "genre": "black_metal",
        "title": title,
        "mood": mood,
        "tempo_bpm": bpm,
        "meter": "4/4",
        "bars": blueprint.bars,
        "tonal_center": tonal_center,
    })

    plan = deepcopy(base)

    plan["schema"] = (
        "dio.sonoris."
        "black_metal_governed.v1"
    )

    plan["title"] = title
    plan["genre"] = "black_metal"
    plan["bars"] = blueprint.bars
    plan["tempo_bpm"] = bpm
    plan["meter"] = "4/4"
    plan["tonal_center"] = tonal_center
    plan["mood"] = mood

    plan["seed"] = seed

    plan["sections"] = (
        sections
    )

    plan[
        "black_metal_blueprint"
    ] = blueprint.as_dict()

    plan[
        "composition_contract"
    ] = {
        "genre_laws": [
            "tremolo_speed_independent_of_harmonic_speed",
            "macro_scale_harmonic_motion",
            "minor_semitone_tritone_gravity",
            "repetition_before_mutation",
            "recognizable_dna_through_transformation",
            "drum_states_need_not_follow_every_harmonic_change",
            "contrast_need_not_mean_silence",
            "register_transformation_allowed",
            "atmosphere_optional",
            "keys_optional",
            "intro_optional",
            "non_verse_chorus_form_allowed",
            "resolution_optional",
        ],
        "golden_fixture_is_template": False,
    }

    plan["sha256"] = (
        _sha256(plan)
    )

    return plan
