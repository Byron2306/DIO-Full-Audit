from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass
from typing import Any


ROLES = (
    "harmony",
    "bass",
    "lead",
    "drums",
    "keys",
    "folk",
)

PULSE_DIALECTS = (
    "STALKING_OSTINATO",
    "INDUSTRIAL_CLUB",
    "DRIVING_EIGHTHS",
    "HIGH_SPEED_ASSAULT",
)

HARMONIC_DIALECTS = (
    "MINOR_PEDAL",
    "CHROMATIC_DREAD",
    "FLAT_SIX_PRESSURE",
    "TRITONE_MACHINE",
    "MINOR_THIRD_DESCENT",
)

TIMBRE_DIALECTS = (
    "DISTORTED_PWM",
    "SUB_SQUARE",
    "RESONANT_SWEEP",
    "BUZZY_SAW",
    "COLD_POLY",
    "NOISE_MACHINE",
)

ARRANGEMENT_DIALECTS = (
    "DROP",
    "ESCALATION",
    "STALK_AND_STRIKE",
    "CINEMATIC_SURGES",
    "HOOK_CYCLES",
)

BASS_FAMILIES = (
    "PULSE_8",
    "PULSE_16",
    "OCTAVE_HUNT",
    "PEDAL_CHROMATIC",
    "SYNCOPATED_STAB",
    "SUB_STALK",
    "DISTORTED_GATE",
    "FILTER_SWEEP",
)

DRUM_STATES = (
    "MACHINE_STOMP",
    "NIGHTCLUB_DRIVE",
    "INDUSTRIAL_HALF_TIME",
    "CHASE_GRID",
    "DROP_PULSE",
)

LEAD_STATES = (
    "OFF",
    "SHORT_HOOK",
    "SAW_ANTHEM",
    "OCTAVE_SIGNAL",
    "WAVETABLE_ALARM",
    "MINOR_ARP",
)

SECTION_STATES = (
    "STALK",
    "BUILD",
    "DROP",
    "HOOK",
    "SURGE",
    "BLACKOUT",
    "ASSAULT",
    "DISSOLVE",
)


@dataclass(frozen=True)
class DarkAggroBlueprint:
    schema: str
    seed: int
    bars: int
    bpm: int
    tonal_center: str
    pulse_dialect: str
    harmonic_dialect: str
    timbre_dialect: str
    arrangement_dialect: str
    bass_sequence: tuple[str, ...]
    drum_sequence: tuple[str, ...]
    lead_sequence: tuple[str, ...]
    section_sequence: tuple[str, ...]
    harmonic_span_bars: tuple[int, ...]
    lead_reveal_bar: int
    sha256: str


def _seed(seed: int, namespace: str) -> int:
    body = f"{namespace}:{seed}".encode()
    return int.from_bytes(
        hashlib.sha256(body).digest()[:8],
        "big",
    )


def _hash(payload: dict[str, Any]) -> str:
    import json

    body = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    return hashlib.sha256(body).hexdigest()


def _weighted_bpm(rng: random.Random) -> int:
    zone = rng.choices(
        ("STALK", "DRIVE", "ASSAULT"),
        weights=(0.34, 0.42, 0.24),
        k=1,
    )[0]

    if zone == "STALK":
        return rng.randint(98, 112)

    if zone == "DRIVE":
        return rng.randint(113, 128)

    return rng.randint(129, 150)


def _different_choice(
    rng: random.Random,
    values: tuple[str, ...],
    previous: str | None,
) -> str:
    candidates = tuple(
        value
        for value in values
        if value != previous
    )

    return rng.choice(candidates)


def compose_dark_aggro_blueprint(
    *,
    seed: int,
    bars: int | None = None,
    tonal_center: str = "D-minor",
) -> DarkAggroBlueprint:

    rng = random.Random(
        _seed(
            seed,
            "sonoris-dark-aggro-synthwave-v1",
        )
    )

    total_bars = (
        int(bars)
        if bars is not None
        else rng.choice(
            (80, 88, 96, 104, 112, 120, 128)
        )
    )

    if total_bars < 48:
        raise ValueError(
            "DARK_AGGRO_TOO_SHORT: "
            f"bars={total_bars} minimum=48"
        )

    bpm = _weighted_bpm(rng)

    pulse = rng.choice(PULSE_DIALECTS)
    harmony = rng.choice(HARMONIC_DIALECTS)
    timbre = rng.choice(TIMBRE_DIALECTS)
    arrangement = rng.choice(
        ARRANGEMENT_DIALECTS
    )

    section_count = rng.randint(7, 10)

    section_sequence: list[str] = [
        "STALK"
    ]

    previous = "STALK"

    while len(section_sequence) < section_count - 1:
        allowed = (
            "BUILD",
            "DROP",
            "HOOK",
            "SURGE",
            "BLACKOUT",
            "ASSAULT",
        )

        next_state = _different_choice(
            rng,
            allowed,
            previous,
        )

        section_sequence.append(
            next_state
        )

        previous = next_state

    section_sequence.append(
        rng.choice(
            ("DISSOLVE", "BLACKOUT")
        )
    )

    bass_sequence: list[str] = []
    drum_sequence: list[str] = []
    lead_sequence: list[str] = []
    spans: list[int] = []

    previous_bass = None

    for index, section in enumerate(
        section_sequence
    ):
        if section == "BLACKOUT":
            bass = rng.choice(
                ("SUB_STALK", "FILTER_SWEEP")
            )

            drums = "DROP_PULSE"

        elif section == "DROP":
            bass = rng.choice(
                (
                    "DISTORTED_GATE",
                    "PULSE_16",
                    "OCTAVE_HUNT",
                )
            )

            drums = rng.choice(
                (
                    "NIGHTCLUB_DRIVE",
                    "CHASE_GRID",
                )
            )

        elif section == "ASSAULT":
            bass = rng.choice(
                (
                    "PULSE_16",
                    "PEDAL_CHROMATIC",
                    "DISTORTED_GATE",
                )
            )

            drums = "CHASE_GRID"

        else:
            bass = _different_choice(
                rng,
                BASS_FAMILIES,
                previous_bass,
            )

            if section == "STALK":
                drums = rng.choice(
                    (
                        "MACHINE_STOMP",
                        "INDUSTRIAL_HALF_TIME",
                    )
                )

            elif section == "BUILD":
                drums = rng.choice(
                    (
                        "MACHINE_STOMP",
                        "CHASE_GRID",
                        "INDUSTRIAL_HALF_TIME",
                    )
                )

            elif section == "HOOK":
                drums = rng.choice(
                    (
                        "MACHINE_STOMP",
                        "INDUSTRIAL_HALF_TIME",
                    )
                )

            elif section == "SURGE":
                drums = rng.choice(
                    (
                        "CHASE_GRID",
                        "MACHINE_STOMP",
                    )
                )

            else:
                drums = rng.choice(
                    (
                        "MACHINE_STOMP",
                        "INDUSTRIAL_HALF_TIME",
                        "CHASE_GRID",
                    )
                )

        previous_bass = bass

        bass_sequence.append(
            bass
        )

        drum_sequence.append(
            drums
        )

        if index < 2:
            lead = "OFF"

        elif section in {
            "HOOK",
            "SURGE",
            "ASSAULT",
        }:
            lead = rng.choice(
                (
                    "SHORT_HOOK",
                    "SAW_ANTHEM",
                    "OCTAVE_SIGNAL",
                    "WAVETABLE_ALARM",
                )
            )

        else:
            lead = rng.choices(
                LEAD_STATES,
                weights=(
                    0.62,
                    0.12,
                    0.06,
                    0.07,
                    0.06,
                    0.07,
                ),
                k=1,
            )[0]

        lead_sequence.append(
            lead
        )

        spans.append(
            rng.choice(
                (2, 2, 2, 4, 4, 8)
            )
        )

    reveal_fraction = rng.uniform(
        0.26,
        0.48,
    )

    reveal_bar = int(
        total_bars
        * reveal_fraction
    )

    payload = {
        "schema":
            "dio.sonoris.dark_aggro_synthwave_blueprint.v1",
        "seed": seed,
        "bars": total_bars,
        "bpm": bpm,
        "tonal_center": tonal_center,
        "pulse_dialect": pulse,
        "harmonic_dialect": harmony,
        "timbre_dialect": timbre,
        "arrangement_dialect": arrangement,
        "bass_sequence": tuple(
            bass_sequence
        ),
        "drum_sequence": tuple(
            drum_sequence
        ),
        "lead_sequence": tuple(
            lead_sequence
        ),
        "section_sequence": tuple(
            section_sequence
        ),
        "harmonic_span_bars": tuple(
            spans
        ),
        "lead_reveal_bar": reveal_bar,
    }

    digest = _hash(payload)

    return DarkAggroBlueprint(
        **payload,
        sha256=digest,
    )


def _root_pc(
    tonal_center: str,
) -> int:

    names = {
        "C": 0,
        "C#": 1,
        "D": 2,
        "D#": 3,
        "E": 4,
        "F": 5,
        "F#": 6,
        "G": 7,
        "G#": 8,
        "A": 9,
        "A#": 10,
        "B": 11,
    }

    key = (
        tonal_center
        .split("-", 1)[0]
        .upper()
        .replace("B♭", "A#")
        .replace("E♭", "D#")
    )

    if key not in names:
        raise ValueError(
            "unsupported tonal center: "
            f"{tonal_center}"
        )

    return names[key]


DARK_AGGRO_POWER_PROGRESSIONS = {
    "MINOR_PEDAL":
        (0, 0, -4, -2),

    "CHROMATIC_DREAD":
        (0, 0, -1, -4),

    "FLAT_SIX_PRESSURE":
        (0, 0, -4, -2),

    "TRITONE_MACHINE":
        (0, 0, 6, -1),

    "MINOR_THIRD_DESCENT":
        (0, 0, -3, -5),
}


HARMONIC_MOTION = {
    "MINOR_PEDAL":
        (0, 0, -5, -2),

    "CHROMATIC_DREAD":
        (0, -1, 0, -2),

    "FLAT_SIX_PRESSURE":
        (0, -4, -5, -2),

    "TRITONE_MACHINE":
        (0, 6, 0, -1),

    "MINOR_THIRD_DESCENT":
        (0, -3, -5, -2),
}



# ============================================================
# LOW TRIPLET DREAD ARPEGGIATION
#
# 12 attacks / 4-beat bar:
#
#   0, 1/3, 2/3
#   1, 4/3, 5/3
#   2, 7/3, 8/3
#   3, 10/3, 11/3
#
# This is a RIFF ENGINE, not decorative trance arpeggiation.
# ============================================================

TRIPLET_DREAD_INTERVALS = {
    "MINOR_PEDAL":
        (0, 3, 7),

    "CHROMATIC_DREAD":
        (0, 1, 6),

    "FLAT_SIX_PRESSURE":
        (0, 3, 8),

    "TRITONE_MACHINE":
        (0, 6, 1),

    "MINOR_THIRD_DESCENT":
        (0, 3, -2),
}


def _triplet_arp_active(
    section_state: str,
    *,
    local_bar: int,
    section_bars: int,
) -> bool:
    # Literal reference proof:
    # pulse continuously so we can validate the rhythm
    # and sound before restoring arrangement decisions.
    return True


def _triplet_dread_events(
    *,
    beat: float,
    root: int,
    harmonic_dialect: str,
    section_state: str,
    section_index: int,
    local_bar: int,
) -> list[dict[str, Any]]:
    """
    Literal dark-aggro XXX. power-pulse.

       1 e + a | 2 e + a | 3 e + a | 4 e + a
       X X X . | X X X . | X X X . | X X X .

    Four-bar phrase:

       i | i | bVI | bVII

    Every strike is the SAME power voicing within the bar.
    """

    # root passed by caller is ignored intentionally here.
    #
    # This proof version owns its four-bar harmonic phrase.
    # C minor example expressed relative to tonic:
    #
    # i, i, bVI, bVII
    bar_offsets = (
        0,
        0,
        8,
        10,
    )

    phrase_bar = (
        local_bar % 4
    )

    chord_root = (
        root
        + bar_offsets[
            phrase_bar
        ]
    )

    offsets = (
        _dark_aggro_pulse_offsets(
            phrase_cut=(
                local_bar % 4 == 3
            )
        )
    )

    rows = []

    for offset in offsets:

        # On every fourth bar, beat 4 is completely
        # removed to create the pre-drop vacuum.
        if (
            local_bar % 4 == 3
            and offset >= 3.0
        ):
            continue
        # Literal power voicing:
        #
        # root + fifth
        for interval, velocity in (
            (0, 108),
            (7, 101),
        ):
            rows.append(
                _event(
                    role="keys",
                    beat=beat + offset,
                    duration=0.145,
                    pitch=(
                        chord_root
                        + 12
                        + interval
                    ),
                    velocity=velocity,
                    gesture=section_state,
                    section=section_index,
                    function=(
                        "LITERAL_XXX_POWER_PULSE"
                    ),
                    articulation=(
                        "DISTORTED_POWER_SYNTH"
                    ),
                )
            )

    return rows

def _event(
    *,
    role: str,
    beat: float,
    duration: float,
    pitch: int,
    velocity: int,
    gesture: str,
    section: int,
    function: str,
    articulation: str | None = None,
) -> dict[str, Any]:

    row = {
        "role": role,
        "beat": round(
            beat,
            5,
        ),
        "duration": round(
            max(0.03, duration),
            5,
        ),
        "pitch": max(
            0,
            min(
                127,
                int(pitch),
            ),
        ),
        "velocity": max(
            1,
            min(
                127,
                int(velocity),
            ),
        ),
        "gesture": gesture,
        "section": section,
        "function": function,
    }

    if articulation:
        row[
            "articulation"
        ] = articulation

    return row


def _allocate_sections(
    blueprint: DarkAggroBlueprint,
) -> list[dict[str, Any]]:

    count = len(
        blueprint.section_sequence
    )

    remaining = (
        blueprint.bars
    )

    minimums = [
        8
        for _ in range(count)
    ]

    used = sum(
        minimums
    )

    extra = max(
        0,
        remaining - used,
    )

    lengths = minimums[:]

    cursor = 0

    while extra >= 4:
        index = (
            cursor
            % count
        )

        if (
            blueprint.section_sequence[
                index
            ]
            not in {
                "BLACKOUT",
                "DISSOLVE",
            }
            or lengths[index] < 12
        ):
            lengths[index] += 4
            extra -= 4

        cursor += 1

    if extra:
        lengths[-1] += extra

    sections = []
    bar = 0

    for index, (
        state,
        length,
    ) in enumerate(
        zip(
            blueprint.section_sequence,
            lengths,
        ),
        start=1,
    ):

        sections.append({
            "index": index,
            "state": state,
            "start_bar": bar,
            "end_bar": bar + length,
            "bars": length,
            "bass_family":
                blueprint.bass_sequence[
                    index - 1
                ],
            "drum_state":
                blueprint.drum_sequence[
                    index - 1
                ],
            "lead_state":
                blueprint.lead_sequence[
                    index - 1
                ],
            "harmonic_span_bars":
                blueprint.harmonic_span_bars[
                    index - 1
                ],
        })

        bar += length

    return sections



# One clock rules the low-end.
#
# 1 e + a | 2 e + a | 3 e + a | 4 e + a
# X X X . | X X X . | X X X . | X X X .
DARK_AGGRO_MASTER_PULSE = (
    0.00, 0.25, 0.50,
    1.00, 1.25, 1.50,
    2.00, 2.25, 2.50,
    3.00, 3.25, 3.50,
)


def _dark_aggro_pulse_offsets(
    *,
    phrase_cut: bool = False,
) -> tuple[float, ...]:
    if phrase_cut:
        # Beat four becomes the pre-drop vacuum.
        return tuple(
            x
            for x in DARK_AGGRO_MASTER_PULSE
            if x < 3.0
        )

    return DARK_AGGRO_MASTER_PULSE


def _bass_offsets(
    family: str,
) -> tuple[tuple[float, int, float], ...]:

    if family == "PULSE_8":
        return tuple(
            (
                i * 0.5,
                0,
                0.34,
            )
            for i in range(8)
        )

    if family == "PULSE_16":
        return tuple(
            (
                i * 0.25,
                0,
                0.18,
            )
            for i in range(16)
        )

    if family == "OCTAVE_HUNT":
        return (
            (0.0, 0, 0.34),
            (0.5, 12, 0.30),
            (1.0, 0, 0.34),
            (1.5, 12, 0.30),
            (2.0, 0, 0.34),
            (2.5, 7, 0.30),
            (3.0, 12, 0.34),
            (3.5, 0, 0.30),
        )

    if family == "PEDAL_CHROMATIC":
        return (
            (0.0, 0, 0.28),
            (0.5, 0, 0.28),
            (1.0, 1, 0.30),
            (1.5, 0, 0.28),
            (2.0, 0, 0.28),
            (2.5, 6, 0.30),
            (3.0, 0, 0.28),
            (3.5, -1, 0.30),
        )

    if family == "SYNCOPATED_STAB":
        return (
            (0.0, 0, 0.28),
            (0.75, 0, 0.20),
            (1.5, 12, 0.26),
            (2.25, 0, 0.22),
            (3.25, 7, 0.34),
        )

    if family == "SUB_STALK":
        return (
            (0.0, 0, 0.72),
            (2.0, 0, 0.68),
        )

    if family == "DISTORTED_GATE":
        return (
            (0.0, 0, 0.18),
            (0.5, 0, 0.18),
            (1.0, 0, 0.18),
            (1.5, 1, 0.18),
            (2.0, 0, 0.18),
            (2.5, 0, 0.18),
            (3.0, 6, 0.18),
            (3.5, 0, 0.18),
        )

    # FILTER_SWEEP:
    # notes remain simple; timbre should provide development.
    return (
        (0.0, 0, 1.85),
        (2.0, 0, 1.75),
    )


def _drum_events(
    *,
    state: str,
    bar_beat: float,
    section: int,
    energy: float,
    local_bar: int = 0,
    section_bars: int = 8,
) -> list[dict[str, Any]]:
    """
    Dark-aggro drum machine.

    Core law:
        drums make POCKETS for the XXX. bass pulse.

    No default four-on-floor carpet.
    Hats favor offbeats.
    Phrase endings create actual silence.
    """

    rows = []

    # Last beat of every fourth bar becomes a cut-out.
    phrase_cut = (
        local_bar % 4 == 3
    )

    def hit(
        beat: float,
        note: int,
        velocity: int,
        function: str,
        duration: float = 0.07,
    ) -> None:
        # On phrase-cut bars, beat 4 is reserved for
        # the isolated snare / impact.
        if (
            phrase_cut
            and beat >= 3.0
            and function not in {
                "CUT_SNARE",
                "SUB_DROP",
            }
        ):
            return

        rows.append(
            _event(
                role="drums",
                beat=bar_beat + beat,
                duration=duration,
                pitch=note,
                velocity=int(
                    velocity * energy
                ),
                gesture=state,
                section=section,
                function=function,
            )
        )

    # --------------------------------------------------
    # KICK POCKET
    #
    # Avoid kicking on every quarter note.
    # Leave room for the synth burst.
    # --------------------------------------------------

    # Baseline darksynth machine pocket.
    #
    # The kick occupies quarter-note anchors and avoids
    # the 0.75 / 1.75 / 2.75 melodic-rest pockets.
    kicks = (
        0.0,
        2.0,
    )

    for beat in kicks:
        hit(
            beat,
            36,
            122,
            "MACHINE_KICK",
            0.08,
        )

    # --------------------------------------------------
    # SNARE
    # Main hits on 2 and 4.
    #
    # Add occasional sixteenth-note pre-shift before 2.
    # --------------------------------------------------

    hit(
        1.0,
        38,
        116,
        "GATED_SNARE",
        0.09,
    )

    if local_bar % 2 == 1:
        hit(
            0.75,
            38,
            92,
            "PRE_SNARE",
            0.055,
        )

    if not phrase_cut:
        hit(
            3.0,
            38,
            120,
            "GATED_SNARE",
            0.10,
        )

    # --------------------------------------------------
    # OFFBEAT HATS
    #
    # 1 & 2 & 3 & 4 &
    # --------------------------------------------------

    if not phrase_cut:
        for beat in (
            0.5,
            1.5,
            2.5,
            3.5,
        ):
            hit(
                beat,
                42,
                79,
                "OFFBEAT_HAT",
                0.035,
            )

    # Occasional open hat for lift.
    if (
        state in {
            "CHASE_GRID",
            "NIGHTCLUB_DRIVE",
        }
        and local_bar % 4 == 2
    ):
        hit(
            3.5,
            46,
            90,
            "OPEN_HAT",
            0.12,
        )

    # --------------------------------------------------
    # CUT-OUT FILL
    #
    # Beat 4 gets one enormous snare and then space.
    # --------------------------------------------------

    if phrase_cut:
        hit(
            3.0,
            38,
            127,
            "CUT_SNARE",
            0.12,
        )

        # Low electronic impact underneath it.
        hit(
            3.0,
            41,
            98,
            "SUB_DROP",
            0.18,
        )

    return rows


def compile_dark_aggro_events(
    *,
    seed: int,
    bars: int | None = None,
    tonal_center: str = "D-minor",
) -> dict[str, Any]:

    blueprint = (
        compose_dark_aggro_blueprint(
            seed=seed,
            bars=bars,
            tonal_center=tonal_center,
        )
    )

    sections = _allocate_sections(
        blueprint
    )

    result: dict[
        str,
        list[dict[str, Any]]
    ] = {
        role: []
        for role in ROLES
    }

    key_pc = _root_pc(
        blueprint.tonal_center
    )

    bass_base = (
        24
        + key_pc
    )

    pad_base = (
        48
        + key_pc
    )

    lead_base = (
        60
        + key_pc
    )

    progression = (
        DARK_AGGRO_POWER_PROGRESSIONS[
            blueprint.harmonic_dialect
        ]
    )

    rng = random.Random(
        _seed(
            seed,
            "dark-aggro-events-v1",
        )
    )

    for section in sections:
        index = int(
            section["index"]
        )

        section_state = str(
            section["state"]
        )

        bass_family = str(
            section["bass_family"]
        )

        drum_state = str(
            section["drum_state"]
        )

        lead_state = str(
            section["lead_state"]
        )

        harmonic_span = int(
            section[
                "harmonic_span_bars"
            ]
        )

        energy = {
            "STALK": 0.72,
            "BUILD": 0.82,
            "DROP": 1.0,
            "HOOK": 0.90,
            "SURGE": 0.96,
            "BLACKOUT": 0.48,
            "ASSAULT": 1.0,
            "DISSOLVE": 0.55,
        }[
            section_state
        ]

        for bar in range(
            int(
                section["start_bar"]
            ),
            int(
                section["end_bar"]
            ),
        ):
            beat = (
                bar
                * 4.0
            )

            # Dark Aggro pulse progression:
            #
            # four-bar macro phrase such as
            #
            #   i | i | bVI | bVII
            #
            # while the 3+1 sixteenth pulse repeats
            # inside each bar.
            harmony_step = (
                bar % 4
            )

            root_offset = progression[
                harmony_step
                % len(progression)
            ]

            root = (
                bass_base
                + root_offset
            )

            # ----------------------------------------
            # SYNTH BASS IS THE PRIMARY RIFF ENGINE.
            # ----------------------------------------

            local_bar = (
                bar
                - int(
                    section["start_bar"]
                )
            )

            phrase_cut = (
                local_bar % 4 == 3
            )

            bass_pattern = [
                (
                    offset,
                    0,
                    0.16,
                )
                for offset
                in _dark_aggro_pulse_offsets(
                    phrase_cut=phrase_cut,
                )
            ]

            for (
                offset,
                interval,
                duration,
            ) in bass_pattern:

                # Four-bar cut-out:
                # silence the bass on beat 4.
                if (
                    local_bar % 4 == 3
                    and offset >= 3.0
                ):
                    continue

                velocity = int(
                    (
                        104
                        + rng.randint(
                            -5,
                            5,
                        )
                    )
                    * energy
                )

                result[
                    "bass"
                ].append(
                    _event(
                        role="bass",
                        beat=beat + offset,
                        duration=duration,
                        pitch=root + interval,
                        velocity=velocity,
                        gesture=section_state,
                        section=index,
                        function=bass_family,
                        articulation=(
                            "SYNTH_PULSE"
                        ),
                    )
                )

            # ----------------------------------------
            # HARMONY IS SLOW AND SECONDARY.
            # It never competes with the bass grid.
            # ----------------------------------------

            if (
                bar
                % harmonic_span
                == 0
            ):
                pad_root = (
                    pad_base
                    + root_offset
                )

                pad_duration = (
                    harmonic_span
                    * 4.0
                    - 0.20
                )

                for interval in (
                    0,
                    3,
                    7,
                ):
                    result[
                        "harmony"
                    ].append(
                        _event(
                            role="harmony",
                            beat=beat,
                            duration=pad_duration,
                            pitch=(
                                pad_root
                                + interval
                            ),
                            velocity=int(
                                64
                                * energy
                            ),
                            gesture=section_state,
                            section=index,
                            function=(
                                "DARK_POLY_BED"
                            ),
                            articulation=(
                                "SYNTH_SUSTAIN"
                            ),
                        )
                    )

            # ----------------------------------------
            # LOW TRIPLET DREAD ARP
            #
            # Unlike the pad, this is rhythmic.
            # Unlike the bass, it articulates the upper
            # tension of the same harmonic root.
            # ----------------------------------------

            local_bar = (
                bar
                - int(
                    section["start_bar"]
                )
            )

            if _triplet_arp_active(
                section_state,
                local_bar=local_bar,
                section_bars=int(
                    section["bars"]
                ),
            ):
                result[
                    "keys"
                ].extend(
                    _triplet_dread_events(
                        beat=beat,
                        root=root,
                        harmonic_dialect=(
                            blueprint
                            .harmonic_dialect
                        ),
                        section_state=(
                            section_state
                        ),
                        section_index=index,
                        local_bar=local_bar,
                    )
                )

            # ----------------------------------------
            # ELECTRONIC DRUM MACHINE.
            # ----------------------------------------

            result[
                "drums"
            ].extend(
                _drum_events(
                    state=drum_state,
                    bar_beat=beat,
                    section=index,
                    energy=energy,
                    local_bar=local_bar,
                    section_bars=int(
                        section["bars"]
                    ),
                )
            )

            # ----------------------------------------
            # LEAD IS OPTIONAL AND ARRIVES LATE.
            # ----------------------------------------

            if (
                lead_state != "OFF"
                and bar
                >= blueprint.lead_reveal_bar
            ):
                local = (
                    bar
                    - int(
                        section[
                            "start_bar"
                        ]
                    )
                )

                if (
                    lead_state
                    == "SHORT_HOOK"
                    and local % 4 == 0
                ):
                    for offset, interval in (
                        (0.0, 0),
                        (0.75, 3),
                        (1.5, 6),
                        (2.5, 3),
                    ):
                        result[
                            "lead"
                        ].append(
                            _event(
                                role="lead",
                                beat=beat + offset,
                                duration=0.48,
                                pitch=(
                                    lead_base
                                    + root_offset
                                    + interval
                                ),
                                velocity=96,
                                gesture=section_state,
                                section=index,
                                function=lead_state,
                                articulation=(
                                    "SYNTH_LEAD"
                                ),
                            )
                        )

                elif (
                    lead_state
                    == "SAW_ANTHEM"
                    and local % 2 == 0
                ):
                    result[
                        "lead"
                    ].append(
                        _event(
                            role="lead",
                            beat=beat,
                            duration=3.65,
                            pitch=(
                                lead_base
                                + root_offset
                                + 12
                            ),
                            velocity=100,
                            gesture=section_state,
                            section=index,
                            function=lead_state,
                            articulation=(
                                "SYNTH_LEAD"
                            ),
                        )
                    )

                elif (
                    lead_state
                    == "OCTAVE_SIGNAL"
                ):
                    for offset, interval in (
                        (0.0, 0),
                        (2.0, 12),
                    ):
                        result[
                            "lead"
                        ].append(
                            _event(
                                role="lead",
                                beat=beat + offset,
                                duration=1.25,
                                pitch=(
                                    lead_base
                                    + root_offset
                                    + interval
                                ),
                                velocity=94,
                                gesture=section_state,
                                section=index,
                                function=lead_state,
                                articulation=(
                                    "SYNTH_LEAD"
                                ),
                            )
                        )

                elif (
                    lead_state
                    == "WAVETABLE_ALARM"
                ):
                    for offset, interval in (
                        (0.0, 6),
                        (1.0, 5),
                        (2.0, 6),
                        (3.0, 1),
                    ):
                        result[
                            "lead"
                        ].append(
                            _event(
                                role="lead",
                                beat=beat + offset,
                                duration=0.55,
                                pitch=(
                                    lead_base
                                    + root_offset
                                    + interval
                                ),
                                velocity=101,
                                gesture=section_state,
                                section=index,
                                function=lead_state,
                                articulation=(
                                    "SYNTH_LEAD"
                                ),
                            )
                        )

                elif (
                    lead_state
                    == "MINOR_ARP"
                ):
                    for i, interval in enumerate(
                        (
                            0,
                            3,
                            7,
                            12,
                            7,
                            3,
                            0,
                            3,
                        )
                    ):
                        result[
                            "lead"
                        ].append(
                            _event(
                                role="lead",
                                beat=(
                                    beat
                                    + i * 0.5
                                ),
                                duration=0.28,
                                pitch=(
                                    lead_base
                                    + root_offset
                                    + interval
                                ),
                                velocity=88,
                                gesture=section_state,
                                section=index,
                                function=lead_state,
                                articulation=(
                                    "SYNTH_LEAD"
                                ),
                            )
                        )

    return {
        "schema":
            "dio.sonoris.dark_aggro_synthwave_physical.v1",

        "blueprint":
            asdict(
                blueprint
            ),

        "sections":
            sections,

        "events":
            result,

        "event_counts": {
            role: len(rows)
            for role, rows
            in result.items()
        },
    }
