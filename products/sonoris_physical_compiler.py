"""Sonoris physical-performance compiler.

Genre grammar does not directly prescribe notes.

The compiler transforms:

    governed composition plan
        -> gesture contracts
        -> role interaction
        -> physical performance intent
        -> instrument-realizable events

Renderers must consume this intent. They must not infer musical intent from
bar numbers, track names, or hard-coded song-specific ranges.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping
import hashlib
import json
import random


TPQ = 480


@dataclass(frozen=True)
class PhysicalEvent:
    role: str
    tick: int
    duration: int
    pitch: int
    velocity: int
    gesture: str
    articulation: str
    stroke: str | None = None
    function: str | None = None
    interaction_source: str | None = None
    phrase_id: str | None = None

    # Guitar-family events may represent a physical fretboard shape rather
    # than one isolated MIDI pitch. `pitch` remains the anchor/root for
    # compatibility; `pitches` contains the actually sounded voices.
    pitches: tuple[int, ...] | None = None

    # Describes why the voices coexist physically.
    shape_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        if row["pitches"] is not None:
            row["pitches"] = list(row["pitches"])
        return row


@dataclass(frozen=True)
class GestureContract:
    name: str

    # Composition behavior.
    density: float
    instability: float
    repetition: float
    phrase_pressure: float
    register_motion: float

    # Guitar body.
    tremolo_probability: float
    mute_probability: float
    downpick_bias: float
    sustain_probability: float

    # Rhythm section.
    kick_coupling: float
    blast_probability: float
    backbeat_probability: float
    cymbal_density: float

    # Ensemble.
    bass_lock: float
    silence_probability: float


BLACK_METAL_GESTURES: dict[str, GestureContract] = {
    "TRANCE": GestureContract(
        "TRANCE",
        density=0.72,
        instability=0.28,
        repetition=0.88,
        phrase_pressure=0.56,
        register_motion=0.22,
        tremolo_probability=0.94,
        mute_probability=0.03,
        downpick_bias=0.50,
        sustain_probability=0.94,
        kick_coupling=0.42,
        blast_probability=0.30,
        backbeat_probability=0.12,
        cymbal_density=0.78,
        bass_lock=0.66,
        silence_probability=0.02,
    ),
    "SPRINT": GestureContract(
        "SPRINT",
        density=0.95,
        instability=0.48,
        repetition=0.55,
        phrase_pressure=0.94,
        register_motion=0.38,
        tremolo_probability=0.74,
        mute_probability=0.24,
        downpick_bias=0.62,
        sustain_probability=0.38,
        kick_coupling=0.90,
        blast_probability=0.88,
        backbeat_probability=0.14,
        cymbal_density=0.88,
        bass_lock=0.86,
        silence_probability=0.01,
    ),
    "PANIC": GestureContract(
        "PANIC",
        density=0.97,
        instability=0.96,
        repetition=0.18,
        phrase_pressure=0.98,
        register_motion=0.72,
        tremolo_probability=0.68,
        mute_probability=0.10,
        downpick_bias=0.50,
        sustain_probability=0.45,
        kick_coupling=0.82,
        blast_probability=0.94,
        backbeat_probability=0.06,
        cymbal_density=0.92,
        bass_lock=0.68,
        silence_probability=0.04,
    ),
    "STOMP": GestureContract(
        "STOMP",
        density=0.42,
        instability=0.38,
        repetition=0.64,
        phrase_pressure=0.85,
        register_motion=0.22,
        tremolo_probability=0.05,
        mute_probability=0.72,
        downpick_bias=0.88,
        sustain_probability=0.42,
        kick_coupling=0.96,
        blast_probability=0.04,
        backbeat_probability=0.90,
        cymbal_density=0.48,
        bass_lock=0.96,
        silence_probability=0.08,
    ),
    "COLLAPSE": GestureContract(
        "COLLAPSE",
        density=0.14,
        instability=0.62,
        repetition=0.22,
        phrase_pressure=0.24,
        register_motion=0.18,
        tremolo_probability=0.04,
        mute_probability=0.02,
        downpick_bias=0.55,
        sustain_probability=0.98,
        kick_coupling=0.18,
        blast_probability=0.00,
        backbeat_probability=0.05,
        cymbal_density=0.28,
        bass_lock=0.40,
        silence_probability=0.42,
    ),
    "HOOK": GestureContract(
        "HOOK",
        density=0.56,
        instability=0.36,
        repetition=0.78,
        phrase_pressure=0.76,
        register_motion=0.30,
        tremolo_probability=0.20,
        mute_probability=0.20,
        downpick_bias=0.72,
        sustain_probability=0.72,
        kick_coupling=0.82,
        blast_probability=0.14,
        backbeat_probability=0.72,
        cymbal_density=0.58,
        bass_lock=0.88,
        silence_probability=0.03,
    ),
    "RELEASE": GestureContract(
        "RELEASE",
        density=0.08,
        instability=0.18,
        repetition=0.52,
        phrase_pressure=0.06,
        register_motion=0.10,
        tremolo_probability=0.00,
        mute_probability=0.00,
        downpick_bias=0.50,
        sustain_probability=1.00,
        kick_coupling=0.08,
        blast_probability=0.00,
        backbeat_probability=0.00,
        cymbal_density=0.15,
        bass_lock=0.28,
        silence_probability=0.66,
    ),
}


BLACK_METAL_INTERVAL_POOL = (
    0,   # root
    1,   # minor second
    3,   # minor third
    5,   # fourth
    6,   # tritone
    7,   # fifth
    8,   # minor sixth / augmented fifth colour
    10,  # minor seventh
    12,
)


def _seed(seed: int, *parts: object) -> int:
    raw = ":".join([str(seed), *(str(x) for x in parts)])
    return int(hashlib.sha256(raw.encode()).hexdigest()[:16], 16)


def _clamp_velocity(value: float) -> int:
    return max(1, min(127, round(value)))


def _choose_interval(
    rng: random.Random,
    *,
    previous: int,
    contract: GestureContract,
) -> int:
    """Choose movement from behavioral pressure, not a memorized riff."""

    if rng.random() < contract.repetition:
        return previous

    if rng.random() < contract.instability:
        unstable = (1, 3, 6, 8, 10)
        return rng.choice(unstable)

    stable = (0, 3, 5, 7, 12)
    return rng.choice(stable)


def _stroke(
    rng: random.Random,
    *,
    contract: GestureContract,
    ordinal: int,
    tremolo: bool,
) -> str:
    if tremolo:
        return "DOWN" if ordinal % 2 == 0 else "UP"

    return "DOWN" if rng.random() < contract.downpick_bias else "UP"


def _bm_pitch_field(
    gesture: str,
    *,
    tonal_root: int,
) -> tuple[int, ...]:
    """
    Black-metal pitch fields are deliberately narrow.

    This is not a melody scale. It is a set of gravitational tones around
    a pedal center. Repetition and pressure matter more than novelty.
    """
    fields = {
        # Root, minor second, minor third, tritone, fifth.
        "TRANCE": (0, 1, 3, 6, 7),

        # Strong root pedal with hostile neighbouring colours.
        "SPRINT": (0, 0, 0, 1, 3, 6, 7),

        # More unstable, but still magnetized to root.
        "PANIC": (0, 0, 1, 3, 6, 7, 8),

        # Heavy chordal/root gravity.
        "STOMP": (0, 0, 3, 6, 7),

        # Almost static.
        "COLLAPSE": (0, 1, 6),

        # Recognisable, repeatable identity.
        "HOOK": (0, 3, 6, 7),

        # Final tonal trace.
        "RELEASE": (0,),
    }

    return tuple(
        tonal_root + interval
        for interval in fields[gesture]
    )


def _bm_make_cell(
    gesture: str,
    *,
    tonal_root: int,
    rng: random.Random,
) -> tuple[int, ...]:
    """
    Generate a small reusable pitch cell.

    The important property is recurrence. A cell is created once and reused
    across many attacks. Black-metal pressure comes from repetition and
    transformation, not from choosing a fresh note every sixteenth.
    """
    field = _bm_pitch_field(
        gesture,
        tonal_root=tonal_root,
    )

    if gesture == "TRANCE":
        length = 4
    elif gesture in {"SPRINT", "PANIC"}:
        length = 8
    elif gesture == "HOOK":
        length = 4
    else:
        length = 2

    cell = [tonal_root]

    for _ in range(length - 1):
        if gesture == "TRANCE":
            # Mostly pedal-tone hypnosis.
            nxt = tonal_root if rng.random() < 0.64 else rng.choice(field)

        elif gesture == "SPRINT":
            # Root pressure with sparse hostile punctuation.
            nxt = tonal_root if rng.random() < 0.72 else rng.choice(field)

        elif gesture == "PANIC":
            # Instability without abandoning tonal gravity.
            nxt = tonal_root if rng.random() < 0.42 else rng.choice(field)

        elif gesture == "HOOK":
            nxt = rng.choice(field)

        else:
            nxt = tonal_root

        cell.append(nxt)

    return tuple(cell)


def _bm_transform_cell(
    cell: tuple[int, ...],
    *,
    gesture: str,
    tonal_root: int,
    rng: random.Random,
) -> tuple[int, ...]:
    """
    Phrase-level mutation.

    Mutations are intentionally conservative: one changed tone is enough
    to create development without turning repetition into prog noodling.
    """
    if len(cell) <= 1:
        return cell

    probability = {
        "TRANCE": 0.16,
        "SPRINT": 0.22,
        "PANIC": 0.38,
        "STOMP": 0.10,
        "HOOK": 0.18,
        "COLLAPSE": 0.04,
        "RELEASE": 0.00,
    }[gesture]

    if rng.random() >= probability:
        return cell

    out = list(cell)
    field = _bm_pitch_field(
        gesture,
        tonal_root=tonal_root,
    )

    index = rng.randrange(1, len(out))
    out[index] = rng.choice(field)

    return tuple(out)



def _bm_shape(
    anchor: int,
    kind: str,
) -> tuple[int, ...]:
    """
    Original black-metal fretboard primitives.

    Pedal shapes preserve the low anchor while moving only the upper voice.
    This allows extreme local picking density with extremely slow harmonic
    motion.
    """
    shapes = {
        "POWER": (0, 7),
        "OCTAVE": (0, 12),
        "TRITONE": (0, 6),
        "MINOR_DYAD": (0, 3),
        "POWER_OCTAVE": (0, 7, 12),

        # Low pedal + upper voice.
        "PEDAL_M2": (0, 13),
        "PEDAL_M3": (0, 15),
        "PEDAL_TT": (0, 18),
        "PEDAL_P5": (0, 19),
        "PEDAL_M6": (0, 20),
        "PEDAL_M3_SHARP": (0, 16),
    }

    return tuple(
        anchor + interval
        for interval in shapes[kind]
    )



BM_HARMONIC_SPANS = {
    # --------------------------------------------------------
    # FROST SIGIL — 4 bars
    #
    # D pedal:
    #   F  -> Eb -> Ab -> F
    #
    # Sorrow first, evil in the third bar.
    # --------------------------------------------------------
    "FROST_SIGIL": (
        (1, 0, "PEDAL_M3"),
        (1, 0, "PEDAL_M2"),
        (1, 0, "PEDAL_TT"),
        (1, 0, "PEDAL_M3"),
    ),

    # --------------------------------------------------------
    # CORRUPTED SIGIL — 8 bars
    #
    # D pedal:
    #   F -> Gb -> Ab -> Eb
    #
    # Two bars per harmonic state. This is intentionally
    # hypnotic rather than riff-busy.
    # --------------------------------------------------------
    "CORRUPTED_SIGIL": (
        (2, 0, "PEDAL_M3"),
        (2, 0, "PEDAL_M3_SHARP"),
        (2, 0, "PEDAL_TT"),
        (2, 0, "PEDAL_M2"),
    ),

    # --------------------------------------------------------
    # KNIFE — 8 bars
    #
    # One-bar roots:
    #   D -> Eb -> D -> Ab -> D -> F -> Eb -> D
    #
    # This is the fastest harmonic motion in the piece, but
    # even here each harmony survives an ENTIRE BAR.
    # --------------------------------------------------------
    "KNIFE": (
        (1, 0, "POWER"),
        (1, 1, "POWER"),
        (1, 0, "POWER"),
        (1, 6, "POWER"),
        (1, 0, "POWER"),
        (1, 3, "POWER"),
        (1, 1, "POWER"),
        (1, 0, "POWER"),
    ),

    # --------------------------------------------------------
    # FROZEN FIELD — 8 bars
    #
    # D pedal:
    #   Ab -> A -> F -> Eb
    #
    # Two bars per state. Surface stays fast; harmony crawls.
    # --------------------------------------------------------
    "FROZEN_FIELD": (
        (2, 0, "PEDAL_TT"),
        (2, 0, "PEDAL_P5"),
        (2, 0, "PEDAL_M3"),
        (2, 0, "PEDAL_M2"),
    ),

    # --------------------------------------------------------
    # TRANSFIGURED SIGIL — 8 bars
    #
    # D pedal:
    #   Ab -> Bb -> F -> Eb
    #
    # Related to the opening, but emotionally wider/sadder.
    # --------------------------------------------------------
    "TRANSFIGURED_SIGIL": (
        (2, 0, "PEDAL_TT"),
        (2, 0, "PEDAL_M6"),
        (2, 0, "PEDAL_M3"),
        (2, 0, "PEDAL_M2"),
    ),

    # --------------------------------------------------------
    # WAR ASCENT — 8 bars
    #
    # Roots:
    #   D -> F -> Eb -> Ab -> D -> Bb -> Ab -> Eb
    #
    # More martial, but still one complete bar per harmony.
    # --------------------------------------------------------
    "WAR_ASCENT": (
        (1, 0, "POWER_OCTAVE"),
        (1, 3, "POWER"),
        (1, 1, "POWER"),
        (1, 6, "POWER_OCTAVE"),
        (1, 0, "POWER"),
        (1, 8, "POWER"),
        (1, 6, "POWER"),
        (1, 1, "POWER"),
    ),
}



# ============================================================
# SONG-SPECIFIC BLACK-METAL HARMONIC DIALECT
#
# Family names define BEHAVIOR, not literal notes.
#
# FROZEN_FIELD still means:
#   frantic tremolo + glacial harmony
#
# KNIFE still means:
#   faster hostile harmonic motion
#
# But each song seed receives its own interval vocabulary.
# ============================================================

BM_CANONICAL_LEGACY_SEED = 661028


def _bm_song_harmonic_dialect(
    seed: int,
) -> dict:
    """
    Generate one coherent harmonic dialect for the whole song.

    The mapping is shared by every riff family in that song, so
    sections sound related without literally sharing Where-the-Pines
    pitches.

    Seed 661028 preserves the canonical breakthrough vocabulary.
    """

    if seed == BM_CANONICAL_LEGACY_SEED:
        return {
            "schema": (
                "dio.sonoris."
                "black_metal_harmonic_dialect.v1"
            ),
            "seed": seed,
            "legacy": True,

            "offset_map": {
                0: 0,
                1: 1,
                3: 3,
                6: 6,
                8: 8,
            },

            "shape_map": {
                "PEDAL_M2": "PEDAL_M2",
                "PEDAL_M3": "PEDAL_M3",
                "PEDAL_M3_SHARP":
                    "PEDAL_M3_SHARP",
                "PEDAL_TT": "PEDAL_TT",
                "PEDAL_P5": "PEDAL_P5",
                "PEDAL_M6": "PEDAL_M6",
                "POWER": "POWER",
                "POWER_OCTAVE":
                    "POWER_OCTAVE",
            },
        }

    rng = random.Random(
        _seed(
            seed,
            "bm-song-harmonic-dialect-v1",
        )
    )

    # --------------------------------------------
    # ROOT-MOTION DIALECT
    #
    # Same functional jobs, different intervals.
    # --------------------------------------------

    chromatic = rng.choice(
        (1, 2)
    )

    sorrow = rng.choice(
        (3, 5, 8, 10)
    )

    hostile = rng.choice(
        (1, 6, 10)
    )

    wide = rng.choice(
        (5, 8, 10)
    )

    # Keep important jobs from collapsing onto one pitch.
    if hostile == sorrow:
        hostile = (
            6
            if sorrow != 6
            else 1
        )

    if wide in {
        sorrow,
        hostile,
    }:
        for candidate in (
            8,
            10,
            5,
            3,
        ):
            if candidate not in {
                sorrow,
                hostile,
            }:
                wide = candidate
                break

    offset_map = {
        0: 0,
        1: chromatic,
        3: sorrow,
        6: hostile,
        8: wide,
    }

    # --------------------------------------------
    # PEDAL-VOICE DIALECT
    #
    # Each canonical emotional function receives
    # a related but seed-specific upper voice.
    # --------------------------------------------

    narrow = rng.choice(
        (
            "PEDAL_M2",
            "PEDAL_M3_SHARP",
        )
    )

    mournful = rng.choice(
        (
            "PEDAL_M3",
            "PEDAL_M6",
        )
    )

    poisoned = rng.choice(
        (
            "PEDAL_M3_SHARP",
            "PEDAL_TT",
            "PEDAL_M2",
        )
    )

    abyss = rng.choice(
        (
            "PEDAL_TT",
            "PEDAL_M3_SHARP",
            "PEDAL_M6",
        )
    )

    open_shape = rng.choice(
        (
            "PEDAL_P5",
            "PEDAL_M6",
            "PEDAL_M3",
        )
    )

    wide_shape = rng.choice(
        (
            "PEDAL_M6",
            "PEDAL_P5",
            "PEDAL_TT",
        )
    )

    shape_map = {
        "PEDAL_M2": narrow,
        "PEDAL_M3": mournful,
        "PEDAL_M3_SHARP": poisoned,
        "PEDAL_TT": abyss,
        "PEDAL_P5": open_shape,
        "PEDAL_M6": wide_shape,

        # Physical chord class stays stable.
        "POWER": "POWER",
        "POWER_OCTAVE": "POWER_OCTAVE",
    }

    return {
        "schema": (
            "dio.sonoris."
            "black_metal_harmonic_dialect.v1"
        ),
        "seed": seed,
        "legacy": False,
        "offset_map": offset_map,
        "shape_map": shape_map,
    }


def _bm_harmonic_spans_for_seed(
    family: str,
    seed: int,
) -> tuple[tuple[int, int, str], ...]:
    """
    Convert canonical family morphology into this SONG's dialect.

    Bar durations stay untouched.

    Therefore:
        harmonic pacing survives
        riff-family behavior survives
        exact pitch vocabulary changes
    """

    canonical = BM_HARMONIC_SPANS[
        family
    ]

    dialect = _bm_song_harmonic_dialect(
        seed
    )

    offset_map = dialect[
        "offset_map"
    ]

    shape_map = dialect[
        "shape_map"
    ]

    return tuple(
        (
            bars,
            offset_map.get(
                anchor_offset,
                anchor_offset,
            ),
            shape_map.get(
                shape_type,
                shape_type,
            ),
        )
        for (
            bars,
            anchor_offset,
            shape_type,
        )
        in canonical
    )


def _bm_expand_harmonic_spans(
    family: str,
    *,
    seed: int = BM_CANONICAL_LEGACY_SEED,
) -> tuple[tuple[int, int, str, int], ...]:
    """
    Expand span definitions into one entry per local bar.

    Returns:
        (span_index, anchor_offset, shape_type, bar_in_span)

    This lets all instruments see the SAME macro-harmonic clock.
    """
    spans = _bm_harmonic_spans_for_seed(
        family,
        seed,
    )

    expanded = []

    for span_index, (
        bars,
        anchor_offset,
        shape_type,
    ) in enumerate(spans):
        for bar_in_span in range(bars):
            expanded.append(
                (
                    span_index,
                    anchor_offset,
                    shape_type,
                    bar_in_span,
                )
            )

    return tuple(expanded)


def _bm_harmonic_state(
    family: str,
    local_bar: int,
    *,
    seed: int = BM_CANONICAL_LEGACY_SEED,
) -> tuple[int, int, str, int, bool]:
    """
    Return harmonic state for one bar.

    If a caller provides more bars than the canonical family length,
    cycle the complete harmonic trajectory rather than inventing notes.
    """
    expanded = _bm_expand_harmonic_spans(
        family,
        seed=seed,
    )

    if not expanded:
        raise ValueError(
            f"EMPTY_BM_HARMONIC_SPANS: {family}"
        )

    index = local_bar % len(expanded)

    (
        span_index,
        anchor_offset,
        shape_type,
        bar_in_span,
    ) = expanded[index]

    span_boundary = bar_in_span == 0

    return (
        span_index,
        anchor_offset,
        shape_type,
        bar_in_span,
        span_boundary,
    )


BM_RIFF_FAMILIES = {
    # D pedal, upper voice F → Ab → Eb → F
    "FROST_SIGIL": (
        (0, "PEDAL_M3"),
        (0, "PEDAL_TT"),
        (0, "PEDAL_M2"),
        (0, "PEDAL_M3"),
    ),

    # Same identity, poisoned:
    # F → Gb → Ab → Eb
    "CORRUPTED_SIGIL": (
        (0, "PEDAL_M3"),
        (0, "PEDAL_M3_SHARP"),
        (0, "PEDAL_TT"),
        (0, "PEDAL_M2"),
    ),

    # Moving power-field:
    # D → Eb → F → Ab
    "BLIZZARD_ASCENT": (
        (0, "POWER"),
        (1, "POWER"),
        (3, "POWER"),
        (6, "POWER"),
    ),

    # Narrow hostile chromatic chain:
    # D → Eb → D → Ab → D → F → Eb → D
    "KNIFE": (
        (0, "POWER"),
        (1, "POWER"),
        (0, "POWER"),
        (6, "POWER"),
        (0, "POWER"),
        (3, "POWER"),
        (1, "POWER"),
        (0, "POWER"),
    ),

    # Surface remains fast while harmony barely moves:
    # D pedal + Ab → A → F → Eb
    "FROZEN_FIELD": (
        (0, "PEDAL_TT"),
        (0, "PEDAL_P5"),
        (0, "PEDAL_M3"),
        (0, "PEDAL_M2"),
    ),

    # Return of opening DNA, but no literal repeat:
    # D pedal + Ab → Bb → F → Eb
    "TRANSFIGURED_SIGIL": (
        (0, "PEDAL_TT"),
        (0, "PEDAL_M6"),
        (0, "PEDAL_M3"),
        (0, "PEDAL_M2"),
    ),

    # Final martial ascent:
    # D → F → Eb → Ab → D → Bb → Ab → Eb
    "WAR_ASCENT": (
        (0, "POWER_OCTAVE"),
        (3, "POWER"),
        (1, "POWER"),
        (6, "POWER_OCTAVE"),
        (0, "POWER"),
        (8, "POWER"),
        (6, "POWER"),
        (1, "POWER"),
    ),
}


def _bm_riff_family(
    section_index: int,
    raw_gesture: str,
) -> str:
    """
    Song-specific riff-chain selection for Where the Pines Forget.

    Canonical section indices in the composition plan are ONE-BASED:

      1 TRANCE     -> FROST_SIGIL
      2 SPRINT     -> CORRUPTED_SIGIL
      3 PANIC      -> KNIFE
      4 STOMP      -> FROZEN_FIELD
      5 COLLAPSE   -> structural void
      6 TRANCE     -> TRANSFIGURED_SIGIL
      7 HOOK       -> WAR_ASCENT
      8 RELEASE    -> unresolved release

    Raw-gesture fallback keeps this compiler safe if a caller supplies
    sections without the canonical numbering.
    """
    by_index = {
        1: "FROST_SIGIL",
        2: "CORRUPTED_SIGIL",
        3: "KNIFE",
        4: "FROZEN_FIELD",
        6: "TRANSFIGURED_SIGIL",
        7: "WAR_ASCENT",
    }

    by_gesture = {
        "TRANCE": "FROST_SIGIL",
        "SPRINT": "CORRUPTED_SIGIL",
        "PANIC": "KNIFE",
        "STOMP": "FROZEN_FIELD",
        "HOOK": "WAR_ASCENT",
    }

    return by_index.get(
        section_index,
        by_gesture.get(raw_gesture, raw_gesture),
    )


def _bm_effective_gesture(
    section_index: int,
    raw_gesture: str,
) -> str:
    # STOMP no longer means slow/heavy/doom in this BM grammar.
    #
    # Do NOT infer this from section_index: PANIC is canonical index 3.
    if raw_gesture == "STOMP":
        return "FROZEN_SUSPENSION"
    return raw_gesture



def _guitar_section(
    section: Mapping[str, Any],
    *,
    tonal_root: int,
    bpm: int,
    seed: int,
) -> list[PhysicalEvent]:
    section_index = int(section["index"])
    raw_gesture = str(section["gesture"])

    gesture = str(
        section.get("execution_gesture")
        or _bm_effective_gesture(
            section_index,
            raw_gesture,
        )
    )

    family = str(
        section.get("riff_family")
        or _bm_riff_family(
            section_index,
            raw_gesture,
        )
    )

    rng = random.Random(
        _seed(
            seed,
            "bm-harmonic-span-v05",
            section_index,
            family,
        )
    )

    start_bar = int(section["start_bar"])
    bars = int(section["bars"])

    harmonic_dialect = (
        _bm_song_harmonic_dialect(
            seed
        )
    )

    # --------------------------------------------------------
    # Structural voids remain exceptional.
    # --------------------------------------------------------

    if raw_gesture == "COLLAPSE":
        # V0.5.2: ASHEN CONTINUUM
        #
        # No pause. No breakdown. No perceptual drop.
        # The right hand remains at full tremolo speed while the harmony
        # changes slowly underneath it.
        out = []

        subdivisions = 16
        step = (TPQ * 4) // subdivisions

        for local_bar in range(bars):
            bar_tick = (
                start_bar + local_bar
            ) * TPQ * 4

            # First half: D + Ab
            # Second half: D + Eb
            canonical_shape = (
                "PEDAL_TT"
                if local_bar < max(
                    1,
                    bars // 2,
                )
                else "PEDAL_M2"
            )

            shape_type = (
                harmonic_dialect[
                    "shape_map"
                ].get(
                    canonical_shape,
                    canonical_shape,
                )
            )

            voices = _bm_shape(
                tonal_root,
                shape_type,
            )

            for ordinal in range(subdivisions):
                stroke = (
                    "DOWN"
                    if ordinal % 2 == 0
                    else "UP"
                )

                accent = (
                    5 if ordinal == 0
                    else 2 if ordinal in {4, 8, 12}
                    else 0
                )

                out.append(
                    PhysicalEvent(
                        role="rhythm_guitar",
                        tick=bar_tick + ordinal * step,
                        duration=max(
                            18,
                            round(step * 0.91),
                        ),
                        pitch=tonal_root,
                        pitches=voices,
                        velocity=_clamp_velocity(
                            85
                            + accent
                            + rng.uniform(-2, 2)
                        ),
                        gesture="ASHEN_CONTINUUM",
                        articulation=f"SUSTAIN_{stroke}",
                        stroke=stroke,
                        function="ASHEN_CONTINUUM",
                        phrase_id=(
                            f"ASHEN_CONTINUUM-"
                            f"{section_index}-"
                            f"{local_bar // 2}"
                        ),
                        shape_type=shape_type,
                    )
                )

        return out

    if raw_gesture == "RELEASE":
        return [
            PhysicalEvent(
                role="rhythm_guitar",
                tick=start_bar * TPQ * 4,
                duration=max(
                    TPQ * 2,
                    bars * TPQ * 4 - TPQ // 2,
                ),
                pitch=tonal_root,
                pitches=_bm_shape(
                    tonal_root,
                    harmonic_dialect[
                        "shape_map"
                    ].get(
                        "PEDAL_M2",
                        "PEDAL_M2",
                    ),
                ),
                shape_type=(
                    harmonic_dialect[
                        "shape_map"
                    ].get(
                        "PEDAL_M2",
                        "PEDAL_M2",
                    )
                ),
                velocity=58,
                gesture="RELEASE",
                articulation="SUSTAIN_DOWN",
                stroke="DOWN",
                function="UNRESOLVED_RELEASE",
                phrase_id=f"RELEASE-{section_index}",
            )
        ]

    if family not in BM_HARMONIC_SPANS:
        raise RuntimeError(
            f"BM_V05_HARMONIC_FAMILY_MISSING: {family}"
        )

    subdivisions = 16
    step = (TPQ * 4) // subdivisions

    out: list[PhysicalEvent] = []

    for local_bar in range(bars):
        absolute_bar = start_bar + local_bar
        bar_tick = absolute_bar * TPQ * 4

        (
            span_index,
            anchor_offset,
            shape_type,
            bar_in_span,
            span_boundary,
        ) = _bm_harmonic_state(
            family,
            local_bar,
            seed=seed,
        )

        anchor = tonal_root + anchor_offset

        register_device = _governed_register_device(
            section
        )

        # ----------------------------------------------------
        # GOVERNED REGISTER REALIZATION
        # ----------------------------------------------------

        if register_device == "REGISTER_REVELATION":
            # Sudden vertical opening in second half.
            if local_bar >= max(1, bars // 2):
                anchor += 12

        elif register_device == "LOW_TO_HIGH_RETURN":
            # First quarter low, middle returns low, final quarter opens.
            quarter = max(1, bars // 4)

            if local_bar >= bars - quarter:
                anchor += 12

        elif register_device == "OCTAVE_SHADOW":
            # Every second bar shadows the same harmony an octave higher.
            if local_bar % 2 == 1:
                anchor += 12

        elif register_device == "NONE":
            # Preserve the proven Where-the-Pines behavior for WAR_ASCENT
            # only when no governed register device is explicitly present.
            if (
                family == "WAR_ASCENT"
                and local_bar >= max(1, bars // 2)
            ):
                anchor += 12

        else:
            raise RuntimeError(
                f"UNKNOWN_REGISTER_DEVICE: {register_device}"
            )

        voices = _bm_shape(
            anchor,
            shape_type,
        )

        phrase_id = (
            f"{family}-"
            f"section{section_index}-"
            f"span{span_index}"
        )

        # ----------------------------------------------------
        # CRITICAL V0.5 LAW:
        #
        # The SAME harmonic shape survives every tremolo attack
        # in this whole bar.
        #
        # Right hand = frantic.
        # Harmony = glacial.
        # ----------------------------------------------------

        for ordinal in range(subdivisions):
            stroke = (
                "DOWN"
                if ordinal % 2 == 0
                else "UP"
            )

            articulation = f"SUSTAIN_{stroke}"

            if gesture == "FROZEN_SUSPENSION":
                base_velocity = 79
            elif family == "KNIFE":
                base_velocity = 100
            elif family == "WAR_ASCENT":
                base_velocity = 98
            elif family == "CORRUPTED_SIGIL":
                base_velocity = 94
            else:
                base_velocity = 87

            # Accents follow beats, never harmonic micro-changes.
            if ordinal == 0:
                accent = 6
            elif ordinal in {4, 8, 12}:
                accent = 2
            else:
                accent = 0

            # Slightly announce a genuine harmonic-span boundary,
            # but never enough to sound like a prog accent.
            if (
                span_boundary
                and local_bar > 0
                and ordinal == 0
            ):
                accent += 2

            velocity = _clamp_velocity(
                base_velocity
                + accent
                + rng.uniform(-2.5, 2.5)
            )

            duration = max(
                18,
                round(step * 0.90),
            )

            out.append(
                PhysicalEvent(
                    role="rhythm_guitar",
                    tick=bar_tick + ordinal * step,
                    duration=duration,
                    pitch=anchor,
                    pitches=voices,
                    velocity=velocity,
                    gesture=gesture,
                    articulation=articulation,
                    stroke=stroke,
                    function=family,
                    phrase_id=phrase_id,
                    shape_type=shape_type,
                )
            )

    return out


def _governed_drum_state(
    section: Mapping[str, Any],
    family: str,
) -> str:
    """
    Governed plan wins.

    Legacy family-derived behavior remains only as fallback for old plans.
    """
    explicit = section.get("drum_state")

    if explicit:
        return str(explicit)

    fallback = {
        "FROST_SIGIL": "FROST_BLAST",
        "CORRUPTED_SIGIL": "FULL_BLAST",
        "KNIFE": "DOUBLE_KICK_STORM",
        "FROZEN_FIELD": "WITHDRAWN_BLAST",
        "TRANSFIGURED_SIGIL": "FROST_BLAST",
        "WAR_ASCENT": "MARTIAL_BLAST",
    }

    return fallback.get(
        family,
        "FROST_BLAST",
    )


def _governed_register_device(
    section: Mapping[str, Any],
) -> str:
    return str(
        section.get(
            "register_device",
            "NONE",
        )
    )



def _drum_section(
    section: Mapping[str, Any],
    *,
    guitar: list[PhysicalEvent],
    seed: int,
) -> list[PhysicalEvent]:
    section_index = int(section["index"])
    raw_gesture = str(section["gesture"])

    gesture = str(
        section.get("execution_gesture")
        or _bm_effective_gesture(
            section_index,
            raw_gesture,
        )
    )

    family = str(
        section.get("riff_family")
        or _bm_riff_family(
            section_index,
            raw_gesture,
        )
    )

    drum_state = _governed_drum_state(
        section,
        family,
    )

    rng = random.Random(
        _seed(
            seed,
            "governed-drums-v1",
            section_index,
            family,
            drum_state,
        )
    )

    start_bar = int(section["start_bar"])
    bars = int(section["bars"])

    out: list[PhysicalEvent] = []

    def hit(
        tick: int,
        note: int,
        velocity: int,
        function: str,
        *,
        duration: int = TPQ // 10,
        interaction_source: str | None = None,
    ) -> None:
        out.append(
            PhysicalEvent(
                role="drums",
                tick=tick,
                duration=duration,
                pitch=note,
                velocity=max(
                    1,
                    min(
                        127,
                        velocity + rng.randint(-3, 3),
                    ),
                ),
                gesture=gesture,
                articulation="STRIKE",
                function=function,
                interaction_source=interaction_source,
            )
        )

    for local_bar in range(bars):
        t = (start_bar + local_bar) * TPQ * 4

        # ====================================================
        # FROST BLAST
        # ====================================================

        if drum_state == "FROST_BLAST":
            for sub in range(16):
                tick = t + sub * (TPQ // 4)

                if sub % 2 == 0:
                    hit(
                        tick,
                        51,
                        84,
                        "FROST_RIDE",
                    )

                    hit(
                        tick,
                        36,
                        91,
                        "FROST_KICK",
                        interaction_source=family,
                    )
                else:
                    hit(
                        tick,
                        38,
                        87,
                        "FROST_SNARE",
                    )

        # ====================================================
        # FULL BLAST
        # ====================================================

        elif drum_state == "FULL_BLAST":
            for sub in range(16):
                tick = t + sub * (TPQ // 4)

                if sub % 2 == 0:
                    hit(
                        tick,
                        51,
                        91,
                        "BLAST_RIDE",
                    )

                    hit(
                        tick,
                        36,
                        99,
                        "BLAST_KICK",
                        interaction_source=family,
                    )
                else:
                    hit(
                        tick,
                        38,
                        96,
                        "BLAST_SNARE",
                    )

        # ====================================================
        # DOUBLE KICK STORM
        # ====================================================

        elif drum_state == "DOUBLE_KICK_STORM":
            for sub in range(16):
                tick = t + sub * (TPQ // 4)

                if sub % 2 == 0:
                    hit(
                        tick,
                        51,
                        90,
                        "STORM_RIDE",
                    )
                else:
                    hit(
                        tick,
                        38,
                        96,
                        "STORM_SNARE",
                    )

                hit(
                    tick,
                    36,
                    101,
                    "STORM_KICK",
                    interaction_source=family,
                )

        # ====================================================
        # WITHDRAWN BLAST
        #
        # Still black-metal motion. Not doom. Not silence.
        # ====================================================

        elif drum_state == "WITHDRAWN_BLAST":
            harmonic_span_bars = int(
                section.get(
                    "harmonic_span_bars",
                    2,
                )
            )

            if harmonic_span_bars <= 0:
                raise RuntimeError(
                    "INVALID_HARMONIC_SPAN_BARS: "
                    f"{harmonic_span_bars}"
                )

            for eighth in range(8):
                tick = t + eighth * (TPQ // 2)

                # Preserve the V0.5 macro-harmonic boundary event.
                #
                # The drummer remains withdrawn, but the first cymbal
                # attack of each NEW harmonic span becomes a crash.
                is_boundary = (
                    local_bar > 0
                    and local_bar % harmonic_span_bars == 0
                    and eighth == 0
                )

                if is_boundary:
                    hit(
                        tick,
                        49,
                        78,
                        "FROZEN_BOUNDARY_CRASH",
                    )
                else:
                    hit(
                        tick,
                        51,
                        70 if eighth % 2 else 76,
                        "WITHDRAWN_RIDE",
                    )

                if eighth in {0, 4}:
                    hit(
                        tick,
                        36,
                        74,
                        "WITHDRAWN_KICK",
                        interaction_source=family,
                    )

            if local_bar % 2 == 1:
                hit(
                    t + TPQ * 3,
                    38,
                    72,
                    "DISTANT_SNARE",
                )

        # ====================================================
        # MARTIAL BLAST
        # ====================================================

        elif drum_state == "MARTIAL_BLAST":
            for sub in range(16):
                tick = t + sub * (TPQ // 4)

                if sub % 2 == 0:
                    hit(
                        tick,
                        51,
                        91,
                        "MARTIAL_RIDE",
                    )

                    hit(
                        tick,
                        36,
                        101,
                        "MARTIAL_KICK",
                        interaction_source=family,
                    )
                else:
                    hit(
                        tick,
                        38,
                        95,
                        "MARTIAL_SNARE",
                    )

            if (
                local_bar > 0
                and local_bar % 2 == 0
            ):
                hit(
                    t,
                    49,
                    96,
                    "MARTIAL_PHRASE_CRASH",
                )

        # ====================================================
        # ASHEN CONTINUUM
        # ====================================================

        elif drum_state == "ASHEN_CONTINUUM":
            for sub in range(16):
                tick = t + sub * (TPQ // 4)

                if sub % 2 == 0:
                    hit(
                        tick,
                        51,
                        80,
                        "ASHEN_RIDE",
                    )

                    hit(
                        tick,
                        36,
                        84,
                        "ASHEN_KICK",
                        interaction_source=family,
                    )
                else:
                    hit(
                        tick,
                        38,
                        80,
                        "ASHEN_SNARE",
                    )

        else:
            raise RuntimeError(
                f"UNKNOWN_GOVERNED_DRUM_STATE: {drum_state}"
            )

        # One section-boundary crash only.
        if (
            local_bar == bars - 1
            and raw_gesture != "RELEASE"
        ):
            hit(
                t + TPQ * 3 + TPQ // 2,
                49,
                88,
                "SECTION_EXIT_CRASH",
                duration=TPQ // 3,
            )

    return out

def _bass_section(
    section: Mapping[str, Any],
    *,
    guitar: list[PhysicalEvent],
    drums: list[PhysicalEvent],
    tonal_root: int,
    seed: int,
) -> list[PhysicalEvent]:
    gesture = str(section["gesture"])
    contract = BLACK_METAL_GESTURES[gesture]
    rng = random.Random(_seed(seed, "bass", section["index"], gesture))

    start_tick = int(section["start_bar"]) * TPQ * 4
    end_tick = int(section["end_bar"]) * TPQ * 4

    guitar_events = [
        event
        for event in guitar
        if start_tick <= event.tick < end_tick
    ]

    kick_ticks = {
        event.tick
        for event in drums
        if start_tick <= event.tick < end_tick
        and event.function in {"KICK", "DOUBLE_KICK"}
    }

    # Bass responds to guitar phrase anchors and kick landmarks.
    anchors: dict[int, PhysicalEvent] = {}

    for event in guitar_events:
        quantized = (event.tick // (TPQ // 2)) * (TPQ // 2)

        if quantized not in anchors or event.velocity > anchors[quantized].velocity:
            anchors[quantized] = event

    out: list[PhysicalEvent] = []

    for tick, guitar_event in sorted(anchors.items()):
        locked = tick in kick_ticks or rng.random() < contract.bass_lock

        if not locked and rng.random() > 0.35:
            continue

        pitch = max(28, min(50, guitar_event.pitch - 12))

        # At unstable gestures bass may answer chromatically rather than
        # doubling the guitar verbatim.
        if contract.instability > 0.75 and rng.random() < 0.28:
            pitch += rng.choice((-1, 1, 6))

        articulation = (
            "VICIOUS"
            if contract.phrase_pressure > 0.75
            else "DIRTY"
        )

        duration = (
            TPQ // 2
            if articulation == "VICIOUS"
            else TPQ
        )

        out.append(
            PhysicalEvent(
                role="bass",
                tick=tick,
                duration=duration,
                pitch=pitch,
                velocity=_clamp_velocity(
                    69 + contract.phrase_pressure * 30 + rng.uniform(-6, 6)
                ),
                gesture=gesture,
                articulation=articulation,
                function="LOCK" if locked else "COUNTER",
                interaction_source=(
                    "kick+guitar"
                    if tick in kick_ticks
                    else "guitar"
                ),
            )
        )

    # Collapse/release are allowed to become almost static.
    if not out and gesture in {"COLLAPSE", "RELEASE"}:
        out.append(
            PhysicalEvent(
                "bass",
                start_tick,
                max(TPQ, end_tick - start_tick - 30),
                tonal_root - 12,
                62,
                gesture,
                "DIRTY",
                function="DRONE",
            )
        )

    return out


def compile_physical_performance(
    plan: Mapping[str, Any],
    *,
    seed: int = 20261028,
) -> dict[str, Any]:
    primary = plan["grammar"]["primary"]["key"]

    if primary != "black_metal":
        raise ValueError(
            "physical compiler v0.1 currently admits black_metal only"
        )

    tonal_root = 38  # D2 guitar reference register for first acceptance specimen.
    bpm = int(plan["musical_frame"]["tempo_bpm"])

    guitar: list[PhysicalEvent] = []
    drums: list[PhysicalEvent] = []
    bass: list[PhysicalEvent] = []

    section_receipts: list[dict[str, Any]] = []

    for section in plan["sections"]:
        g = _guitar_section(
            section,
            tonal_root=tonal_root,
            bpm=bpm,
            seed=seed,
        )

        d = _drum_section(
            section,
            guitar=g,
            seed=seed,
        )

        b = _bass_section(
            section,
            guitar=g,
            drums=d,
            tonal_root=tonal_root,
            seed=seed,
        )

        guitar.extend(g)
        drums.extend(d)
        bass.extend(b)

        section_receipts.append(
            {
                "section": section["section"],
                "gesture": section["gesture"],
                "contract": asdict(
                    BLACK_METAL_GESTURES[section["gesture"]]
                ),
                "event_counts": {
                    "guitar": len(g),
                    "bass": len(b),
                    "drums": len(d),
                },
            }
        )

    payload = {
        "schema": "dio.sonoris.physical_performance_plan.v1",
        "compiler_version": "0.1.0",
        "genre": primary,
        "seed": seed,
        "tempo_bpm": bpm,
        "ticks_per_beat": TPQ,
        "performance_model": (
            "behavior->interaction->physical intent->instrument realization"
        ),
        "sections": section_receipts,
        "roles": {
            "rhythm_guitar": [event.to_dict() for event in guitar],
            "bass": [event.to_dict() for event in bass],
            "drums": [event.to_dict() for event in drums],
        },
        "invariants": {
            "song_specific_bar_range_articulation_rules": False,
            "renderer_may_infer_gesture_from_bar_number": False,
            "physical_articulation_is_explicit": True,
            "role_interaction_is_explicit": True,
        },
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    payload["sha256"] = hashlib.sha256(canonical).hexdigest()

    return payload


# ============================================================
# BLACK METAL CONTINUITY REALIZATION V1
#
# Initial audible law:
#
#   GUITAR_SUSTAIN
#
# Everything else remains untouched until this behavior has
# survived listening review.
# ============================================================

_compile_physical_performance_pre_continuity = (
    compile_physical_performance
)


def _apply_black_metal_guitar_continuity(
    physical,
    governed,
):
    import copy

    result = copy.deepcopy(physical)

    continuity = governed.get(
        "black_metal_continuity"
    )

    if not continuity:
        return result

    guitar = (
        result.get("roles", {})
        .get("rhythm_guitar", [])
    )

    if not guitar:
        return result

    TPQ_LOCAL = 480
    BAR_TICKS_LOCAL = (
        TPQ_LOCAL * 4
    )

    # Discover the duration field from the real physical schema.
    sample = guitar[0]

    duration_field = None

    for candidate in (
        "duration_ticks",
        "duration",
        "length_ticks",
        "length",
    ):
        if candidate in sample:
            duration_field = candidate
            break

    if duration_field is None:
        raise RuntimeError(
            "BM_CONTINUITY_UNKNOWN_GUITAR_DURATION_FIELD:"
            + ",".join(
                sorted(sample.keys())
            )
        )

    realized = []

    for boundary in continuity.get(
        "boundaries",
        []
    ):
        if (
            boundary.get("tail_type")
            != "GUITAR_SUSTAIN"
        ):
            continue

        boundary_tick = (
            int(boundary["at_bar"])
            * BAR_TICKS_LOCAL
        )

        carry_ticks = int(
            float(
                boundary.get(
                    "carry_beats",
                    0.0,
                )
            )
            * TPQ_LOCAL
        )

        if carry_ticks <= 0:
            continue

        candidates = [
            event
            for event in guitar
            if int(
                event.get(
                    "tick",
                    -1,
                )
            ) < boundary_tick
        ]

        if not candidates:
            continue

        latest_tick = max(
            int(event["tick"])
            for event in candidates
        )

        # Extend every note belonging to the final physical
        # attack/chord, not merely one pitch of the voicing.
        final_attack = [
            event
            for event in candidates
            if int(event["tick"])
            == latest_tick
        ]

        for event in final_attack:
            original = int(
                event[duration_field]
            )

            minimum_needed = (
                boundary_tick
                + carry_ticks
                - int(event["tick"])
            )

            event[duration_field] = max(
                original,
                minimum_needed,
            )

            event[
                "continuity_tail"
            ] = "GUITAR_SUSTAIN"

            event[
                "continuity_boundary_bar"
            ] = int(
                boundary["at_bar"]
            )

        realized.append({
            "at_bar":
                int(boundary["at_bar"]),
            "tail_type":
                "GUITAR_SUSTAIN",
            "carry_beats":
                float(
                    boundary["carry_beats"]
                ),
            "attack_tick":
                latest_tick,
            "notes_extended":
                len(final_attack),
        })

    result[
        "black_metal_continuity_realization"
    ] = {
        "schema":
            "dio.sonoris.black_metal_continuity_realization.v1",
        "guitar_sustain":
            realized,
    }

    return result


def compile_physical_performance(
    governed_plan,
    *,
    seed,
):
    physical = (
        _compile_physical_performance_pre_continuity(
            governed_plan,
            seed=seed,
        )
    )

    return (
        _apply_black_metal_guitar_continuity(
            physical,
            governed_plan,
        )
    )
