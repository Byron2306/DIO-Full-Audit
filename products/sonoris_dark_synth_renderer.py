from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


DEFAULT_SR = 48000


def _midi_hz(note: float) -> float:
    return 440.0 * (
        2.0 ** (
            (float(note) - 69.0)
            / 12.0
        )
    )


def _saw(
    phase: np.ndarray,
    harmonics: int = 14,
) -> np.ndarray:
    """
    Band-limited-ish additive saw.

    Higher harmonics naturally decay faster later in the note,
    approximating the fast closing filter envelope we want.
    """
    out = np.zeros_like(
        phase,
        dtype=np.float64,
    )

    for harmonic in range(
        1,
        harmonics + 1,
    ):
        out += (
            np.sin(
                phase * harmonic
            )
            / harmonic
        )

    return (
        out
        * (2.0 / math.pi)
    )


def _square(
    phase: np.ndarray,
) -> np.ndarray:
    return np.where(
        np.sin(phase) >= 0.0,
        1.0,
        -1.0,
    )


def _pluck_envelope(
    t: np.ndarray,
    *,
    attack_s: float = 0.002,
    decay_s: float = 0.085,
) -> np.ndarray:
    attack = np.minimum(
        1.0,
        t / max(
            attack_s,
            1e-5,
        ),
    )

    decay = np.exp(
        -t
        / max(
            decay_s,
            1e-5,
        )
        * 4.0
    )

    return (
        attack
        * decay
    )


def _brightness_envelope(
    t: np.ndarray,
    harmonic: int,
    *,
    decay_s: float = 0.095,
) -> np.ndarray:
    """
    Higher harmonics disappear faster.

    This creates the audible:
        DUN!
    rather than:
        NEEEEEE
    """
    factor = (
        1.0
        + harmonic * 0.16
    )

    return np.exp(
        -t
        / decay_s
        * factor
    )


def _filtered_saw(
    freq: float,
    t: np.ndarray,
    *,
    phase_offset: float = 0.0,
) -> np.ndarray:
    phase = (
        2.0
        * math.pi
        * freq
        * t
        + phase_offset
    )

    out = np.zeros_like(t)

    for harmonic in range(
        1,
        15,
    ):
        out += (
            np.sin(
                phase * harmonic
            )
            / harmonic
            * _brightness_envelope(
                t,
                harmonic,
            )
        )

    return (
        out
        * (2.0 / math.pi)
    )


def _sidechain_gain(
    *,
    length: int,
    sample_rate: int,
    bpm: float,
    drum_events: Sequence[
        Mapping[str, Any]
    ],
    depth: float = 0.72,
    recovery_s: float = 0.18,
) -> np.ndarray:

    gain = np.ones(
        length,
        dtype=np.float64,
    )

    recovery_samples = max(
        1,
        int(
            recovery_s
            * sample_rate
        ),
    )

    for event in drum_events:
        pitch = int(
            event.get(
                "pitch",
                -1,
            )
        )

        function = str(
            event.get(
                "function",
                ""
            )
        )

        is_kick = (
            pitch in {
                35,
                36,
            }
            or "KICK"
            in function.upper()
        )

        if not is_kick:
            continue

        beat = float(
            event["beat"]
        )

        seconds = (
            beat
            * 60.0
            / bpm
        )

        start = int(
            seconds
            * sample_rate
        )

        if start >= length:
            continue

        end = min(
            length,
            start
            + recovery_samples,
        )

        count = (
            end
            - start
        )

        if count <= 0:
            continue

        x = np.linspace(
            0.0,
            1.0,
            count,
            endpoint=False,
        )

        local = (
            1.0
            - depth
            * np.exp(
                -5.0 * x
            )
        )

        gain[
            start:end
        ] = np.minimum(
            gain[
                start:end
            ],
            local,
        )

    return gain


def render_dark_aggro_triple_saw(
    path: Path,
    events: Sequence[
        Mapping[str, Any]
    ],
    *,
    bpm: float,
    drum_events: Sequence[
        Mapping[str, Any]
    ] = (),
    sample_rate: int = DEFAULT_SR,
    detune_cents: float = 7.0,
    sub_level: float = 0.34,
    drive: float = 2.35,
    tail_s: float = 0.35,
) -> Path:

    path = Path(path)

    if not events:
        raise ValueError(
            "DARK_SYNTH_NO_EVENTS"
        )

    max_beat = max(
        float(e["beat"])
        + float(
            e.get(
                "duration",
                0.25,
            )
        )
        for e in events
    )

    duration_s = (
        max_beat
        * 60.0
        / bpm
        + tail_s
    )

    length = int(
        math.ceil(
            duration_s
            * sample_rate
        )
    )

    left = np.zeros(
        length,
        dtype=np.float64,
    )

    right = np.zeros(
        length,
        dtype=np.float64,
    )

    detune_ratio = (
        2.0
        ** (
            detune_cents
            / 1200.0
        )
    )

    for event in events:
        start_beat = float(
            event["beat"]
        )

        # A 16th note at this BPM is 0.25 beats.
        # Keep the synth short enough to preserve the XXX. gate.
        event_beats = min(
            0.225,
            float(
                event.get(
                    "duration",
                    0.225,
                )
            ),
        )

        start_s = (
            start_beat
            * 60.0
            / bpm
        )

        note_s = (
            event_beats
            * 60.0
            / bpm
        )

        start = int(
            start_s
            * sample_rate
        )

        count = max(
            1,
            int(
                note_s
                * sample_rate
            ),
        )

        end = min(
            length,
            start + count,
        )

        count = (
            end
            - start
        )

        if count <= 0:
            continue

        t = (
            np.arange(
                count,
                dtype=np.float64,
            )
            / sample_rate
        )

        note = int(
            event["pitch"]
        )

        freq = _midi_hz(
            note
        )

        velocity = (
            float(
                event.get(
                    "velocity",
                    100,
                )
            )
            / 127.0
        )

        amp = _pluck_envelope(
            t,
            attack_s=0.002,
            decay_s=0.19,
        )

        saw_a = _filtered_saw(
            freq,
            t,
        )

        saw_b = _filtered_saw(
            freq * detune_ratio,
            t,
            phase_offset=0.17,
        )

        sub_phase = (
            2.0
            * math.pi
            * (
                freq / 2.0
            )
            * t
        )

        sub = (
            _square(
                sub_phase
            )
            * sub_level
        )

        # Slightly asymmetric stereo oscillator balance.
        l = (
            (
                saw_a * 0.68
                + saw_b * 0.42
                + sub
            )
            * amp
            * velocity
        )

        r = (
            (
                saw_a * 0.42
                + saw_b * 0.68
                + sub
            )
            * amp
            * velocity
        )

        # Saturation BEFORE sidechain.
        l = np.tanh(
            l * drive
        )

        r = np.tanh(
            r * drive
        )

        left[
            start:end
        ] += l

        right[
            start:end
        ] += r

    sidechain = _sidechain_gain(
        length=length,
        sample_rate=sample_rate,
        bpm=bpm,
        drum_events=drum_events,
        depth=0.0,
    )

    left *= sidechain
    right *= sidechain

    # Gentle final clip.
    left = np.tanh(
        left * 1.15
    )

    right = np.tanh(
        right * 1.15
    )

    peak = max(
        float(
            np.max(
                np.abs(left)
            )
        ),
        float(
            np.max(
                np.abs(right)
            )
        ),
        1e-9,
    )

    if peak > 0.94:
        scale = (
            0.94 / peak
        )

        left *= scale
        right *= scale

    stereo = np.column_stack(
        (
            left,
            right,
        )
    )

    pcm = (
        np.clip(
            stereo,
            -1.0,
            1.0,
        )
        * 32767.0
    ).astype(
        np.int16
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with wave.open(
        str(path),
        "wb",
    ) as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(
            sample_rate
        )
        wav.writeframes(
            pcm.tobytes()
        )

    return path
