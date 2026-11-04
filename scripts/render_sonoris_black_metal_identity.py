from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SR = 48000


RIFF_ATMOSPHERE = {
    "FROST_SIGIL": (0, 3, 7),
    "FROZEN_FIELD": (0, 6, 10),
    "TRANSFIGURED_SIGIL": (0, 3, 8),
    "WAR_ASCENT": (0, 5, 8),
    "CORRUPTED_SIGIL": (0, 1, 6),
    "KNIFE": (0, 1, 7),
}


NOTE_NAMES = {
    "C": 0,
    "C#": 1,
    "DB": 1,
    "D": 2,
    "D#": 3,
    "EB": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "GB": 6,
    "G": 7,
    "G#": 8,
    "AB": 8,
    "A": 9,
    "A#": 10,
    "BB": 10,
    "B": 11,
}


def tonal_root_midi(text: str) -> int:
    name = (
        text
        .split("-", 1)[0]
        .strip()
        .upper()
    )

    pc = NOTE_NAMES.get(name)

    if pc is None:
        raise ValueError(
            f"UNSUPPORTED_TONAL_CENTER: {text}"
        )

    # D minor => D3 = MIDI 50.
    return 48 + pc


def hz(note: int) -> float:
    return (
        440.0
        * 2.0 ** ((note - 69) / 12.0)
    )


def add_choir(
    left: np.ndarray,
    right: np.ndarray,
    *,
    start_s: float,
    end_s: float,
    notes: tuple[int, ...],
    gain: float,
    attack_s: float,
    release_s: float,
) -> None:

    start = max(
        0,
        int(start_s * SR),
    )

    end = min(
        len(left),
        int(end_s * SR),
    )

    if end <= start:
        return

    t = (
        np.arange(
            end - start,
            dtype=np.float32,
        )
        / SR
    )

    envelope = np.ones_like(t)

    attack_n = min(
        len(t),
        int(attack_s * SR),
    )

    release_n = min(
        len(t),
        int(release_s * SR),
    )

    if attack_n:
        envelope[:attack_n] = np.linspace(
            0.0,
            1.0,
            attack_n,
            dtype=np.float32,
        )

    if release_n:
        envelope[-release_n:] *= np.linspace(
            1.0,
            0.0,
            release_n,
            dtype=np.float32,
        )

    l = np.zeros_like(t)
    r = np.zeros_like(t)

    for i, note in enumerate(notes):
        base = hz(note)

        # Choir colour, not a second melodic line.
        signal = np.zeros_like(t)

        for cents, weight in (
            (-6.0, 0.28),
            (0.0, 0.48),
            (6.0, 0.28),
        ):
            f = (
                base
                * 2.0 ** (
                    cents / 1200.0
                )
            )

            phase = i * 0.71

            signal += (
                weight
                * np.sin(
                    2.0
                    * math.pi
                    * f
                    * t
                    + phase
                )
            )

            signal += (
                weight
                * 0.14
                * np.sin(
                    2.0
                    * math.pi
                    * f
                    * 2.0
                    * t
                    + phase * 1.21
                )
            )

        pan = (
            -0.50
            + (
                i
                / max(
                    1,
                    len(notes) - 1,
                )
            )
            * 1.0
        )

        lg = math.sqrt(
            (1.0 - pan) / 2.0
        )

        rg = math.sqrt(
            (1.0 + pan) / 2.0
        )

        l += signal * lg
        r += signal * rg

    scale = (
        gain
        / max(
            len(notes),
            1,
        )
    )

    left[start:end] += (
        l * envelope * scale
    )

    right[start:end] += (
        r * envelope * scale
    )


def write_wav(
    path: Path,
    left: np.ndarray,
    right: np.ndarray,
) -> None:

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

    if peak > 0.92:
        scale = 0.92 / peak
        left *= scale
        right *= scale

    stereo = np.stack(
        (left, right),
        axis=1,
    )

    pcm = (
        np.clip(
            stereo,
            -1.0,
            1.0,
        )
        * 32767.0
    ).astype("<i2")

    with wave.open(
        str(path),
        "wb",
    ) as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SR)
        wav.writeframes(
            pcm.tobytes()
        )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--seed",
        required=True,
        type=int,
    )

    args = parser.parse_args()

    seed_dir = (
        ROOT
        / "media/sonoris/generated/"
        / "black_metal"
        / f"seed-{args.seed}"
    )

    governed_path = (
        seed_dir
        / "SONORIS_GOVERNED_COMPOSITION_PLAN.json"
    )

    intent_path = (
        seed_dir
        / "SONORIS_BLACK_METAL_RENDER_INTENT.json"
    )

    base_path = (
        seed_dir
        / "WHERE_THE_PINES_FORGET_PHYSICAL_V3.wav"
    )

    physical_dir = (
        seed_dir
        / "physical_render"
    )

    for path in (
        governed_path,
        intent_path,
        base_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(
                f"REQUIRED_INPUT_MISSING: {path}"
            )

    governed = json.loads(
        governed_path.read_text()
    )

    intent = json.loads(
        intent_path.read_text()
    )

    bpm = float(
        governed["tempo_bpm"]
    )

    bar_s = (
        4.0
        * 60.0
        / bpm
    )

    root = tonal_root_midi(
        governed["tonal_center"]
    )

    ending_tail = float(
        intent["ending"].get(
            "tail_s",
            0.0,
        )
    )

    total_seconds = (
        governed["bars"]
        * bar_s
        + ending_tail
        + 1.0
    )

    n = int(
        total_seconds * SR
    )

    left = np.zeros(
        n,
        dtype=np.float32,
    )

    right = np.zeros(
        n,
        dtype=np.float32,
    )

    # ========================================================
    # ATMOSPHERE STEM
    # ========================================================

    for section in intent["sections"]:
        atmos = section["atmosphere"]

        if atmos["kind"] == "none":
            continue

        family = (
            section.get("riff_family")
            or "FROST_SIGIL"
        )

        intervals = RIFF_ATMOSPHERE.get(
            family,
            (0, 3, 7),
        )

        # Keep it above the distorted guitar fundamentals.
        notes = tuple(
            root + 12 + interval
            for interval
            in intervals
        )

        start_s = (
            section["start_bar"]
            * bar_s
        )

        end_s = (
            section["end_bar"]
            * bar_s
        )

        if atmos["kind"] == "choir_shadow":
            level_db = float(
                atmos["level_db"]
            )

            gain = (
                10.0
                ** (
                    level_db
                    / 20.0
                )
            )

            add_choir(
                left,
                right,
                start_s=start_s,
                end_s=end_s
                + float(
                    atmos["release_s"]
                ),
                notes=notes,
                gain=gain,
                attack_s=float(
                    atmos["attack_s"]
                ),
                release_s=float(
                    atmos["release_s"]
                ),
            )

    atmosphere_path = (
        seed_dir
        / "identity_atmosphere_dry.wav"
    )

    write_wav(
        atmosphere_path,
        left,
        right,
    )

    atmosphere_frost = (
        seed_dir
        / "identity_atmosphere_frost.wav"
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(atmosphere_path),
            "-af",
            (
                "highpass=f=110,"
                "lowpass=f=5200,"
                "aecho=0.90:0.55:"
                "431|887|1361:"
                "0.18|0.09|0.04,"
                "volume=-1.5dB"
            ),
            "-c:a",
            "pcm_s16le",
            str(atmosphere_frost),
        ],
        check=True,
    )

    # ========================================================
    # INTRO REALIZATION
    # ========================================================

    intro = intent["intro"]
    intro_bars = int(
        intro.get(
            "bars",
            0,
        )
    )

    intro_s = (
        intro_bars
        * bar_s
    )

    intro_path = (
        seed_dir
        / "identity_intro.wav"
    )

    if (
        intro["kind"] == "feedback"
        and intro_bars
    ):
        gtr_l = (
            physical_dir
            / "gtrL_amp.wav"
        )

        gtr_r = (
            physical_dir
            / "gtrR_amp.wav"
        )

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(gtr_l),
                "-i",
                str(gtr_r),
                "-filter_complex",
                (
                    f"[0:a]atrim=0:{intro_s},"
                    "asetpts=PTS-STARTPTS,"
                    "volume=-8dB,"
                    "lowpass=f=6200,"
                    "aecho=0.90:0.68:"
                    "241|613|1019:"
                    "0.31|0.17|0.08[gl];"
                    f"[1:a]atrim=0:{intro_s},"
                    "asetpts=PTS-STARTPTS,"
                    "volume=-8dB,"
                    "lowpass=f=5900,"
                    "aecho=0.90:0.70:"
                    "307|701|1123:"
                    "0.30|0.16|0.08[gr];"
                    "[gl][gr]"
                    "amix=inputs=2:"
                    "normalize=0,"
                    "alimiter=limit=0.88[out]"
                ),
                "-map",
                "[out]",
                "-c:a",
                "pcm_s16le",
                str(intro_path),
            ],
            check=True,
        )

    else:
        # For now preserve existing base intro for unsupported
        # archetypes. They will get dedicated renderers next.
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(base_path),
                "-t",
                str(intro_s),
                "-c:a",
                "pcm_s16le",
                str(intro_path),
            ],
            check=True,
        )

    # ========================================================
    # BODY
    #
    # Remove the old generic intro from the full mix and splice
    # our governed intro in its place.
    # ========================================================

    body_path = (
        seed_dir
        / "identity_body.wav"
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(base_path),
            "-ss",
            str(intro_s),
            "-c:a",
            "pcm_s16le",
            str(body_path),
        ],
        check=True,
    )

    identity_core = (
        seed_dir
        / "identity_core.wav"
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(intro_path),
            "-i",
            str(body_path),
            "-filter_complex",
            (
                "[0:a][1:a]"
                "concat=n=2:v=0:a=1[out]"
            ),
            "-map",
            "[out]",
            "-c:a",
            "pcm_s16le",
            str(identity_core),
        ],
        check=True,
    )

    # ========================================================
    # FINAL ATMOSPHERIC MIX
    # ========================================================

    final_path = (
        seed_dir
        / (
            governed["title"]
            .upper()
            .replace(" ", "_")
            + "_IDENTITY_V1.wav"
        )
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(identity_core),
            "-i",
            str(atmosphere_frost),
            "-filter_complex",
            (
                "[0:a]volume=0.98[band];"
                "[1:a]volume=1.0[atmos];"
                "[band][atmos]"
                "amix=inputs=2:"
                "duration=longest:"
                "normalize=0,"
                "alimiter=limit=0.94[out]"
            ),
            "-map",
            "[out]",
            "-c:a",
            "pcm_s16le",
            str(final_path),
        ],
        check=True,
    )

    print(
        json.dumps(
            {
                "state": (
                    "BLACK_METAL_IDENTITY_RENDER_COMPLETE"
                ),
                "seed": args.seed,
                "title": governed["title"],
                "intro": intent["intro_name"],
                "ending": intent["ending_name"],
                "output": str(final_path),
                "atmosphere": str(
                    atmosphere_frost
                ),
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
