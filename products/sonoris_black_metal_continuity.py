from __future__ import annotations

import hashlib
import random
from copy import deepcopy
from typing import Any, Mapping


TRANSITION_TYPES = (
    "CONTINUE",
    "BLEED",
    "CUT",
)

DRUM_TRANSITIONS = (
    "NONE",
    "SNARE_COLLAPSE",
    "TOM_DESCENT",
    "CYMBAL_WASH",
    "BLAST_ERUPTION",
    "KICK_RUSH",
    "SILENCE_CUT",
)

TAIL_TYPES = (
    "NONE",
    "GUITAR_FEEDBACK",
    "GUITAR_SUSTAIN",
    "KEY_DECAY",
    "ATMOSPHERE_DECAY",
)


def _rng(
    seed: int,
    boundary_index: int,
) -> random.Random:
    raw = (
        f"sonoris-bm-continuity-v1:"
        f"{seed}:{boundary_index}"
    ).encode()

    value = int.from_bytes(
        hashlib.sha256(raw).digest()[:8],
        "big",
    )

    return random.Random(value)


def _transition_type(
    *,
    rng: random.Random,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> str:

    left_role = str(
        left.get("section_role")
        or "BODY"
    )

    right_role = str(
        right.get("section_role")
        or "BODY"
    )

    if right_role == "ENDING":
        return rng.choices(
            (
                "BLEED",
                "CUT",
                "CONTINUE",
            ),
            weights=(
                0.55,
                0.25,
                0.20,
            ),
            k=1,
        )[0]

    if (
        left.get("riff_family")
        == right.get("riff_family")
    ):
        return rng.choices(
            (
                "CONTINUE",
                "BLEED",
            ),
            weights=(
                0.68,
                0.32,
            ),
            k=1,
        )[0]

    return rng.choices(
        TRANSITION_TYPES,
        weights=(
            0.34,
            0.48,
            0.18,
        ),
        k=1,
    )[0]


def _drum_transition(
    *,
    rng: random.Random,
    transition_type: str,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> str:

    # Most boundaries should NOT have a fill.
    if transition_type == "CONTINUE":
        return rng.choices(
            (
                "NONE",
                "CYMBAL_WASH",
            ),
            weights=(
                0.88,
                0.12,
            ),
            k=1,
        )[0]

    if transition_type == "CUT":
        return rng.choices(
            (
                "SILENCE_CUT",
                "SNARE_COLLAPSE",
                "NONE",
            ),
            weights=(
                0.55,
                0.25,
                0.20,
            ),
            k=1,
        )[0]

    left_drums = str(
        left.get("drum_state")
        or ""
    )

    right_drums = str(
        right.get("drum_state")
        or ""
    )

    if left_drums == right_drums:
        return rng.choices(
            (
                "NONE",
                "CYMBAL_WASH",
                "TOM_DESCENT",
            ),
            weights=(
                0.72,
                0.18,
                0.10,
            ),
            k=1,
        )[0]

    return rng.choices(
        (
            "NONE",
            "SNARE_COLLAPSE",
            "TOM_DESCENT",
            "CYMBAL_WASH",
            "BLAST_ERUPTION",
            "KICK_RUSH",
        ),
        weights=(
            0.48,
            0.11,
            0.11,
            0.10,
            0.10,
            0.10,
        ),
        k=1,
    )[0]


def _tail_type(
    *,
    rng: random.Random,
    transition_type: str,
    left: Mapping[str, Any],
) -> str:

    atmosphere = str(
        left.get("atmosphere_name")
        or left.get("atmosphere")
        or "NONE"
    )

    if transition_type == "CUT":
        return "NONE"

    # CONTINUE means texture survives, but it should not
    # automatically spray an effect tail over every boundary.
    if transition_type == "CONTINUE":
        candidates = [
            "NONE",
            "GUITAR_SUSTAIN",
        ]

        weights = [
            0.58,
            0.34,
        ]

        if atmosphere != "NONE":
            candidates.append(
                "ATMOSPHERE_DECAY"
            )

            weights.append(
                0.08
            )

        return rng.choices(
            candidates,
            weights=weights,
            k=1,
        )[0]

    # BLEED is where tails become a genuine structural device.
    candidates = [
        "GUITAR_SUSTAIN",
        "GUITAR_FEEDBACK",
        "NONE",
    ]

    weights = [
        0.42,
        0.36,
        0.10,
    ]

    if atmosphere != "NONE":
        candidates.append(
            "ATMOSPHERE_DECAY"
        )

        weights.append(
            0.20
        )

    return rng.choices(
        candidates,
        weights=weights,
        k=1,
    )[0]


def apply_black_metal_continuity(
    governed_plan: Mapping[str, Any],
) -> dict[str, Any]:

    plan = deepcopy(
        dict(governed_plan)
    )

    seed = int(
        plan["seed"]
    )

    sections = [
        dict(row)
        for row in plan["sections"]
    ]

    boundaries = []

    for index in range(
        len(sections) - 1
    ):
        left = sections[index]
        right = sections[index + 1]

        rng = _rng(
            seed,
            index,
        )

        transition_type = (
            _transition_type(
                rng=rng,
                left=left,
                right=right,
            )
        )

        drum_transition = (
            _drum_transition(
                rng=rng,
                transition_type=(
                    transition_type
                ),
                left=left,
                right=right,
            )
        )

        tail_type = _tail_type(
            rng=rng,
            transition_type=(
                transition_type
            ),
            left=left,
        )

        guitar_carry = (
            transition_type
            in {
                "CONTINUE",
                "BLEED",
            }
        )

        atmosphere_carry = (
            tail_type
            == "ATMOSPHERE_DECAY"
        )

        boundary = {
            "index":
                index + 1,

            "at_bar":
                int(
                    left["end_bar"]
                ),

            "from_section":
                int(
                    left["index"]
                ),

            "to_section":
                int(
                    right["index"]
                ),

            "transition_type":
                transition_type,

            "guitar_carry":
                guitar_carry,

            "atmosphere_carry":
                atmosphere_carry,

            "drum_transition":
                drum_transition,

            "tail_type":
                tail_type,

            # Small bounded overlap.
            # This is intent, not yet audio rendering.
            "carry_beats":
                (
                    2.0
                    if transition_type
                    == "BLEED"
                    else (
                        0.75
                        if transition_type
                        == "CONTINUE"
                        else 0.0
                    )
                ),
        }

        left[
            "transition_out"
        ] = boundary

        right[
            "transition_in"
        ] = boundary

        boundaries.append(
            boundary
        )

    plan["sections"] = sections

    plan[
        "black_metal_continuity"
    ] = {
        "schema":
            "dio.sonoris.black_metal_continuity.v1",

        "boundaries":
            boundaries,

        "laws": [
            (
                "section boundaries do not "
                "imply total silence"
            ),
            (
                "guitar texture may cross "
                "section boundaries"
            ),
            (
                "drum fills are selective, "
                "not mandatory"
            ),
            (
                "tails may occupy silence "
                "without adding new notes"
            ),
        ],
    }

    return plan
