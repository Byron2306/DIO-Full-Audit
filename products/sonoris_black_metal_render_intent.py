from __future__ import annotations

from copy import deepcopy
from typing import Any


INTRO_RENDERERS = {
    "IMMEDIATE_WALL": {
        "kind": "none",
    },

    "LAMENT_PRELUDE": {
        "kind": "lament_keys",
        "bars": 8,
        "hard_entry": True,
    },

    "COLD_DRONE": {
        "kind": "drone",
        "bars": 8,
        "register": "low_mid",
    },

    "FEEDBACK_RITUAL": {
        "kind": "feedback",
        "bars": 4,
        "density": "sparse",
    },

    "LONE_TREMOLO": {
        "kind": "single_guitar_tremolo",
        "bars": 4,
        "drums": False,
    },

    "CHORDAL_PROCESSION": {
        "kind": "slow_chordal_guitar",
        "bars": 8,
        "drums": False,
    },
}


ATMOSPHERE_RENDERERS = {
    "NONE": {
        "kind": "none",
    },

    "SUBLIMINAL_PAD": {
        "kind": "pad",
        "level_db": -18.0,
        "attack_s": 2.0,
        "release_s": 3.5,
    },

    "COLD_DRONE": {
        "kind": "drone",
        "level_db": -14.0,
        "attack_s": 3.5,
        "release_s": 5.0,
    },

    "CHOIR_SHADOW": {
        "kind": "choir_shadow",
        "level_db": -16.0,
        "attack_s": 2.8,
        "release_s": 4.5,
    },

    "BREATHING_KEYS": {
        "kind": "breathing_keys",
        "level_db": -15.0,
    },
}


ENDING_RENDERERS = {
    "UNRESOLVED_RELEASE": {
        "kind": "sustain_unresolved",
        "tail_s": 8.0,
    },

    "ABRUPT_EXTINCTION": {
        "kind": "hard_stop",
        "tail_s": 0.0,
    },

    "FEEDBACK_DISSOLUTION": {
        "kind": "feedback_decay",
        "tail_s": 10.0,
    },

    "FROZEN_PEDAL_DECAY": {
        "kind": "pedal_decay",
        "tail_s": 9.0,
    },

    "FINAL_ASCENT_COLLAPSE": {
        "kind": "ascending_register_then_cut",
        "tail_s": 3.0,
    },
}


def compile_black_metal_render_intent(
    governed_plan: dict[str, Any],
) -> dict[str, Any]:

    blueprint = governed_plan[
        "black_metal_blueprint"
    ]

    intro_name = blueprint["intro"]
    ending_name = blueprint["ending"]

    sections = []

    for section in governed_plan["sections"]:
        atmosphere_name = section.get(
            "atmosphere",
            "NONE",
        )

        sections.append({
            "index": section["index"],
            "start_bar": section["start_bar"],
            "end_bar": section["end_bar"],
            "section_role": section["section_role"],
            "riff_family": section.get("riff_family"),

            "atmosphere": deepcopy(
                ATMOSPHERE_RENDERERS[
                    atmosphere_name
                ]
            ),

            "atmosphere_name": atmosphere_name,

            "register_device": section.get(
                "register_device",
                "NONE",
            ),
        })

    return {
        "schema": (
            "dio.sonoris."
            "black_metal_render_intent.v1"
        ),

        "seed": governed_plan["seed"],
        "title": governed_plan["title"],
        "tempo_bpm": governed_plan["tempo_bpm"],
        "bars": governed_plan["bars"],

        "intro_name": intro_name,
        "intro": deepcopy(
            INTRO_RENDERERS[
                intro_name
            ]
        ),

        "ending_name": ending_name,
        "ending": deepcopy(
            ENDING_RENDERERS[
                ending_name
            ]
        ),

        "sections": sections,
    }
