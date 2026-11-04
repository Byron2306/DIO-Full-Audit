from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


POLLY_ROOT = Path(
    "/home/byron/polly-grunge-rocker"
)

TPQ_FALLBACK = 480


def _load_host():
    if not POLLY_ROOT.is_dir():
        raise RuntimeError(
            f"SONORIS_THRASH_POLLY_ROOT_MISSING: "
            f"{POLLY_ROOT}"
        )

    root = str(POLLY_ROOT)

    if root not in sys.path:
        sys.path.insert(
            0,
            root,
        )

    from fusion_lab.chainsaw_diplomacy import (
        build_chainsaw_diplomacy,
    )

    return build_chainsaw_diplomacy()


def _get(
    obj,
    *names,
    default=None,
):
    for name in names:
        if hasattr(obj, name):
            return getattr(
                obj,
                name,
            )

        if isinstance(obj, dict):
            if name in obj:
                return obj[name]

    return default


def _role_for_track(
    name: str,
) -> str | None:
    value = name.upper()

    if (
        "RHYTHM"
        in value
        or value
        == "GUITAR"
        or value
        == "RHYTHM_GUITAR"
    ):
        return "harmony"

    if "BASS" in value:
        return "bass"

    if "DRUM" in value:
        return "drums"

    if "LEAD" in value:
        return "lead"

    return None


def _section_index(
    beat: float,
    sections,
) -> int:
    cursor = 0.0

    for index, section in enumerate(
        sections
    ):
        bars = int(
            _get(
                section,
                "bars",
                default=0,
            )
            or 0
        )

        end = (
            cursor
            + bars * 4
        )

        if beat < end:
            return index

        cursor = end

    return max(
        0,
        len(sections) - 1,
    )


def compile_thrash_specialist(
    *,
    seed: int,
) -> dict[str, Any]:
    """
    Adapt the proven Chainsaw Diplomacy host into the
    canonical Sonoris event schema.

    Chainsaw owns thrash composition/performance grammar.
    Sonoris owns orchestration, rendering, receipts and UI.
    """

    host = _load_host()

    tpq = int(
        _get(
            host,
            "tpq",
            "ticks_per_quarter",
            default=TPQ_FALLBACK,
        )
        or TPQ_FALLBACK
    )

    sections = list(
        _get(
            host,
            "sections",
            default=[],
        )
        or []
    )

    tracks = (
        _get(
            host,
            "tracks",
            default={},
        )
        or {}
    )

    out = {
        "harmony": [],
        "bass": [],
        "lead": [],
        "drums": [],
        "keys": [],
        "folk": [],
    }

    track_items = (
        tracks.items()
        if hasattr(
            tracks,
            "items",
        )
        else []
    )

    for track_name, track in track_items:
        role = _role_for_track(
            str(track_name)
        )

        if role is None:
            continue

        events = list(
            _get(
                track,
                "events",
                default=[],
            )
            or []
        )

        for event in events:
            start_tick = int(
                _get(
                    event,
                    "start_tick",
                    "start",
                    default=0,
                )
                or 0
            )

            duration_ticks = int(
                _get(
                    event,
                    "duration_ticks",
                    "duration",
                    default=1,
                )
                or 1
            )

            pitch = int(
                _get(
                    event,
                    "midi_note",
                    "note",
                    default=60,
                )
            )

            velocity = int(
                _get(
                    event,
                    "velocity",
                    default=100,
                )
            )

            technique = str(
                _get(
                    event,
                    "technique",
                    "articulation",
                    default="THRASH",
                )
            )

            # Translate the richer Chainsaw performance
            # vocabulary into the canonical Sonoris renderer
            # articulation classes.
            #
            # Preserve technique separately so none of the
            # specialist information is lost.
            upper_technique = (
                technique.upper()
            )

            if (
                role == "harmony"
                and "PALM_MUTE"
                in upper_technique
            ):
                render_articulation = "mute"

            elif (
                role == "harmony"
                and upper_technique
                in {
                    "CLEAN",
                    "CLEAN_PICK",
                    "CLEAN_CHORD",
                }
            ):
                render_articulation = "clean"

            else:
                render_articulation = "sustain"

            phrase_role = str(
                _get(
                    event,
                    "phrase_role",
                    default="THRASH_RIFF",
                )
            )

            beat = (
                start_tick
                / tpq
            )

            duration = max(
                0.03,
                duration_ticks
                / tpq,
            )

            out[role].append(
                {
                    "role":
                        role,

                    "beat":
                        beat,

                    "duration":
                        duration,

                    "pitch":
                        pitch,

                    "velocity":
                        max(
                            1,
                            min(
                                127,
                                velocity,
                            ),
                        ),

                    "gesture":
                        technique,

                    "physical_articulation":
                        technique,

                    # Renderer-facing articulation class.
                    "articulation":
                        render_articulation,

                    "phrase_role":
                        phrase_role,

                    "section":
                        _section_index(
                            beat,
                            sections,
                        ),

                    "specialist":
                        "CHAINSAW_DIPLOMACY",
                }
            )

    counts = {
        role: len(rows)
        for role, rows
        in out.items()
    }

    if not out["harmony"]:
        raise RuntimeError(
            "SONORIS_THRASH_SPECIALIST_NO_GUITAR"
        )

    if not out["drums"]:
        raise RuntimeError(
            "SONORIS_THRASH_SPECIALIST_NO_DRUMS"
        )

    bars = sum(
        int(
            _get(
                section,
                "bars",
                default=0,
            )
            or 0
        )
        for section in sections
    )

    return {
        "schema":
            "dio.sonoris.thrash_specialist.v1",

        "engine":
            "CHAINSAW_DIPLOMACY",

        "seed":
            seed,

        "tempo_bpm":
            int(
                _get(
                    host,
                    "bpm",
                    "tempo_bpm",
                    default=192,
                )
                or 192
            ),

        "meter":
            "4/4",

        "bars":
            bars or 64,

        "events":
            out,

        "event_counts":
            counts,
    }
