#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import random
import subprocess
from pathlib import Path

import mido


SOURCE_MIDI = Path(
    "/data/byron/sonoris/rendered/glass-meridian-v002/"
    "GLASS_MERIDIAN_JAZZ_SYNTH_FUSION.mid"
)

OUT = Path("/data/byron/sonoris/rendered/glass-meridian-v005")

SF2 = Path("/usr/share/sounds/sf2/FluidR3_GM.sf2")

RHODES = Path.home() / (
    "fusion-instruments/sonoris/jlearman.jRhodes3c/"
    "jRhodes3c-looped-flac-sfz/_jRhodes-stereo-looped.sfz"
)

TENOR = Path.home() / (
    "fusion-instruments/sonoris/MTG.SoloSax/"
    "MTG Solo Saxophones/MTG Tenor Sax.sfz"
)

DRUMS = Path.home() / (
    "fusion-instruments/sonoris/virtuosity_drums/"
    "Programs/02-full-kit.sfz"
)

SEED = 20261028


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def track_name(track: mido.MidiTrack) -> str:
    for msg in track:
        if msg.type == "track_name":
            return msg.name
    return ""


def absolute_messages(track: mido.MidiTrack):
    t = 0
    rows = []
    for msg in track:
        t += msg.time
        rows.append([t, msg.copy(time=0)])
    return rows


def rebuild_track(rows):
    rows.sort(
        key=lambda r: (
            max(0, r[0]),
            0 if r[1].type in {"control_change", "program_change"} else 1,
            getattr(r[1], "note", -1),
        )
    )

    out = mido.MidiTrack()
    last = 0

    for tick, msg in rows:
        tick = max(0, int(tick))
        out.append(msg.copy(time=tick - last))
        last = tick

    return out


def meta_tracks(src: mido.MidiFile):
    result = []
    for tr in src.tracks:
        name = track_name(tr).lower()
        if not name or "meta" in name:
            result.append(copy.deepcopy(tr))
    return result


def find_track(src: mido.MidiFile, phrase: str):
    phrase = phrase.lower()
    for tr in src.tracks:
        if phrase in track_name(tr).lower():
            return tr
    raise RuntimeError(f"TRACK_NOT_FOUND: {phrase}")


def save_single_track(
    src: mido.MidiFile,
    source_track: mido.MidiTrack,
    destination: Path,
    transform=None,
):
    mf = mido.MidiFile(type=1, ticks_per_beat=src.ticks_per_beat)

    for meta in meta_tracks(src):
        mf.tracks.append(meta)

    rows = absolute_messages(source_track)

    if transform:
        rows = transform(rows, src.ticks_per_beat)

    mf.tracks.append(rebuild_track(rows))

    destination.parent.mkdir(parents=True, exist_ok=True)
    mf.save(destination)


def save_legacy_tracks(src: mido.MidiFile, destination: Path):
    """
    V5 bridge:
    - Rhodes, tenor and drums rendered separately.
    - Old GM electric bass removed.
    - Existing synth foreground is transposed DOWN ONE OCTAVE
      and becomes the provisional bass voice.
    - Flute remains temporarily on FluidR3.
    """
    mf = mido.MidiFile(type=1, ticks_per_beat=src.ticks_per_beat)

    for tr in src.tracks:
        name = track_name(tr).lower()

        # Rendered elsewhere.
        if "electric piano" in name:
            continue
        if "tenor sax" in name:
            continue
        if "drum kit" in name:
            continue

        # Retire old GM electric bass.
        if "electric bass" in name:
            continue

        cloned = copy.deepcopy(tr)

        # Turn the existing synth motif into the bass-layer voice.
        if "synth lead" in name:
            for msg in cloned:
                if msg.type in {"note_on", "note_off"} and hasattr(msg, "note"):
                    msg.note = max(0, msg.note - 12)

            # Rename truthfully.
            for msg in cloned:
                if msg.type == "track_name":
                    msg.name = "Synth bass | inherited M1/M2 pulse"
                    break

        mf.tracks.append(cloned)

    destination.parent.mkdir(parents=True, exist_ok=True)
    mf.save(destination)

def rhodes_performance(rows, tpq):
    """
    Rhodes realism:
    - deliberate velocity-layer crossing
    - separate left/right-hand onset tendencies
    - chord rake
    - non-uniform releases
    """
    rng = random.Random(SEED + 101)

    note_ons = {}
    note_offs = []

    for i, (tick, msg) in enumerate(rows):
        if msg.type == "note_on" and msg.velocity > 0:
            note_ons.setdefault(tick, []).append(i)
        elif msg.type in {"note_off", "note_on"} and getattr(msg, "velocity", 0) == 0:
            note_offs.append(i)

    layer_targets = [44, 64, 84, 104, 116]

    for chord_index, (tick, indices) in enumerate(sorted(note_ons.items())):
        indices.sort(key=lambda i: rows[i][1].note)

        phrase_drift = rng.randint(-5, 5)

        for rank, idx in enumerate(indices):
            msg = rows[idx][1]
            pitch = msg.note

            # Left hand slightly ahead, right hand slightly raked.
            hand_bias = -5 if pitch < 55 else 0
            rake = rank * rng.randint(2, 5)

            rows[idx][0] = max(
                0,
                rows[idx][0] + phrase_drift + hand_bias + rake
            )

            # Cross actual sample velocity layers deliberately.
            target = layer_targets[
                (chord_index + rank + (1 if pitch > 65 else 0))
                % len(layer_targets)
            ]

            # Avoid making every chord equally aggressive.
            if chord_index % 4 == 3:
                target += 8
            elif chord_index % 4 == 0:
                target -= 5

            msg.velocity = max(30, min(120, target + rng.randint(-3, 3)))

    # Avoid synchronized note-off guillotine.
    for idx in note_offs:
        rows[idx][0] += rng.randint(-8, 18)

    return rows


def tenor_performance(rows, tpq):
    """
    Renderer-aware MTG Tenor performance.

    MTG contract:
      CC1  vibrato depth
      CC3  vibrato rate
      CC11 expression
      CC64 legato
      CC71 attack
      CC72 release
      CC80 noise
      CC98 offset
      CC99 velocity tracking
    """
    rng = random.Random(SEED + 202)

    out = list(rows)

    ons = [
        (tick, msg)
        for tick, msg in rows
        if msg.type == "note_on" and msg.velocity > 0
    ]

    if not ons:
        return out

    # Build phrases from gaps.
    phrases = []
    current = []

    previous_tick = None

    for tick, msg in ons:
        if previous_tick is not None and tick - previous_tick > tpq * 2:
            if current:
                phrases.append(current)
            current = []

        current.append((tick, msg))
        previous_tick = tick

    if current:
        phrases.append(current)

    for phrase_index, phrase in enumerate(phrases):
        first_tick = phrase[0][0]
        last_tick = phrase[-1][0]
        ch = phrase[0][1].channel

        # Phrase identity.
        attack = 38 + rng.randint(-7, 8)
        release = 35 + rng.randint(-8, 12)
        noise = 10 + rng.randint(0, 15)
        veltrack = 88 + rng.randint(-8, 10)
        vib_rate = 42 + rng.randint(-9, 10)

        out.extend([
            [
                max(0, first_tick - 15),
                mido.Message(
                    "control_change",
                    channel=ch,
                    control=71,
                    value=max(15, min(90, attack)),
                    time=0,
                ),
            ],
            [
                max(0, first_tick - 15),
                mido.Message(
                    "control_change",
                    channel=ch,
                    control=72,
                    value=max(15, min(90, release)),
                    time=0,
                ),
            ],
            [
                max(0, first_tick - 12),
                mido.Message(
                    "control_change",
                    channel=ch,
                    control=80,
                    value=max(0, min(45, noise)),
                    time=0,
                ),
            ],
            [
                max(0, first_tick - 10),
                mido.Message(
                    "control_change",
                    channel=ch,
                    control=99,
                    value=max(60, min(115, veltrack)),
                    time=0,
                ),
            ],
            [
                max(0, first_tick - 8),
                mido.Message(
                    "control_change",
                    channel=ch,
                    control=3,
                    value=max(20, min(80, vib_rate)),
                    time=0,
                ),
            ],
            [
                max(0, first_tick - 5),
                mido.Message(
                    "control_change",
                    channel=ch,
                    control=11,
                    value=68 + rng.randint(-4, 6),
                    time=0,
                ),
            ],
        ])

        for note_index, (tick, msg) in enumerate(phrase):
            interior = 0 < note_index < len(phrase) - 1

            # Do not vibrato every note.
            longish = note_index % 3 == 1 or note_index == len(phrase) - 1

            if interior:
                out.append([
                    max(0, tick - 8),
                    mido.Message(
                        "control_change",
                        channel=ch,
                        control=64,
                        value=127,
                        time=0,
                    ),
                ])
            else:
                out.append([
                    max(0, tick - 8),
                    mido.Message(
                        "control_change",
                        channel=ch,
                        control=64,
                        value=0,
                        time=0,
                    ),
                ])

            # Phrase swell.
            out.append([
                tick + tpq // 5,
                mido.Message(
                    "control_change",
                    channel=ch,
                    control=11,
                    value=min(118, 88 + note_index * 4 + rng.randint(-4, 5)),
                    time=0,
                ),
            ])

            if longish:
                out.append([
                    tick + tpq // 2,
                    mido.Message(
                        "control_change",
                        channel=ch,
                        control=1,
                        value=28 + rng.randint(0, 26),
                        time=0,
                    ),
                ])
            else:
                out.append([
                    tick,
                    mido.Message(
                        "control_change",
                        channel=ch,
                        control=1,
                        value=0,
                        time=0,
                    ),
                ])

        # Phrase release.
        out.extend([
            [
                last_tick + tpq // 2,
                mido.Message(
                    "control_change",
                    channel=ch,
                    control=64,
                    value=0,
                    time=0,
                ),
            ],
            [
                last_tick + tpq // 2,
                mido.Message(
                    "control_change",
                    channel=ch,
                    control=1,
                    value=0,
                    time=0,
                ),
            ],
            [
                last_tick + tpq // 2,
                mido.Message(
                    "control_change",
                    channel=ch,
                    control=11,
                    value=60,
                    time=0,
                ),
            ],
        ])

    return out


def drum_performance(rows, tpq):
    """
    Jazz/fusion drummer realization using Virtuosity's real map.

    Virtuosity:
      38 center snare
      40 rimshot
      42 closed hat
      46 open hat
      49 crash
      51 ride
      53 ride bell
      88 cross-stick
      90 half-open hat
      92 splash hat
      94 three-quarter hat
      95 snare flam
    """
    rng = random.Random(SEED + 303)

    new_rows = []

    for tick, msg in rows:
        if msg.type != "note_on" or msg.velocity <= 0:
            new_rows.append([tick, msg])
            continue

        msg = msg.copy()
        note = msg.note

        # Phrase-aware articulation remapping.
        beat = (tick // tpq) % 4
        bar = tick // (tpq * 4)

        # Snare center becomes more varied.
        if note == 38:
            choice = rng.random()

            if bar % 8 == 7 and beat == 3:
                msg.note = 95        # flam into transition
            elif choice < 0.08:
                msg.note = 40        # rimshot
            elif choice < 0.16:
                msg.note = 88        # cross-stick
            else:
                msg.note = 38

        # Cymbal language.
        elif note == 51:
            if bar % 4 == 3 and beat == 2:
                msg.note = 53        # ride bell accent
            else:
                msg.note = 51

        elif note == 42:
            choice = rng.random()
            if choice < 0.08:
                msg.note = 46        # open
            elif choice < 0.16:
                msg.note = 90        # half open
            elif choice < 0.22:
                msg.note = 94        # 3/4
            else:
                msg.note = 42

        # Timing depends on limb/role.
        if msg.note in {36, 38, 40, 88, 95}:
            jitter = rng.randint(-5, 5)
        elif msg.note in {42, 46, 49, 51, 53, 90, 92, 94}:
            jitter = rng.randint(-10, 10)
        else:
            jitter = rng.randint(-7, 7)

        new_tick = max(0, tick + jitter)

        # Dynamic hierarchy.
        if msg.note == 36:
            msg.velocity = max(48, min(118, msg.velocity + rng.randint(-6, 7)))
        elif msg.note in {38, 40, 95}:
            msg.velocity = max(55, min(122, msg.velocity + rng.randint(-6, 10)))
        elif msg.note == 88:
            msg.velocity = max(35, min(85, msg.velocity + rng.randint(-8, 4)))
        else:
            msg.velocity = max(24, min(110, msg.velocity + rng.randint(-10, 9)))

        new_rows.append([new_tick, msg])

        # Ghost notes around selected backbeats.
        if msg.note in {38, 40} and rng.random() < 0.28:
            ghost = msg.copy(
                note=38,
                velocity=rng.randint(25, 42),
            )

            ghost_tick = max(
                0,
                new_tick - tpq // 4 + rng.randint(-6, 6),
            )

            new_rows.append([ghost_tick, ghost])

    # Set kit mic character.
    # Less close-mic brutality, more overhead and room.
    ch = 9

    new_rows.extend([
        [0, mido.Message("control_change", channel=ch, control=101, value=100, time=0)],
        [0, mido.Message("control_change", channel=ch, control=103, value=105, time=0)],
        [0, mido.Message("control_change", channel=ch, control=105, value=118, time=0)],
        [0, mido.Message("control_change", channel=ch, control=107, value=30, time=0)],
        [0, mido.Message("control_change", channel=ch, control=109, value=32, time=0)],
        [0, mido.Message("control_change", channel=ch, control=111, value=10, time=0)],
        [0, mido.Message("control_change", channel=ch, control=113, value=0, time=0)],
    ])

    return new_rows

def run(cmd):
    print("+", " ".join(map(str, cmd)))
    subprocess.run(
        [str(x) for x in cmd],
        check=True,
    )


def render_sfizz(sfz, midi, wav):
    run([
        "sfizz_render",
        "--sfz", sfz,
        "--midi", midi,
        "--wav", wav,
        "--samplerate", "48000",
    ])


def main():
    for required in (SOURCE_MIDI, SF2, RHODES, TENOR, DRUMS):
        if not required.is_file():
            raise SystemExit(f"MISSING_REQUIRED_ASSET: {required}")

    OUT.mkdir(parents=True, exist_ok=True)
    midi_dir = OUT / "midi"
    stem_dir = OUT / "stems"

    midi_dir.mkdir(exist_ok=True)
    stem_dir.mkdir(exist_ok=True)

    src = mido.MidiFile(SOURCE_MIDI)

    print("=== TRACKS ===")
    for i, tr in enumerate(src.tracks):
        print(i, track_name(tr))

    rhodes_midi = midi_dir / "rhodes.mid"
    tenor_midi = midi_dir / "tenor.mid"
    drums_midi = midi_dir / "drums.mid"
    legacy_midi = midi_dir / "legacy_remaining.mid"

    save_single_track(
        src,
        find_track(src, "Electric piano"),
        rhodes_midi,
        rhodes_performance,
    )

    save_single_track(
        src,
        find_track(src, "Tenor sax"),
        tenor_midi,
        tenor_performance,
    )

    save_single_track(
        src,
        find_track(src, "Drum kit"),
        drums_midi,
        drum_performance,
    )

    save_legacy_tracks(src, legacy_midi)

    rhodes_wav = stem_dir / "rhodes.wav"
    tenor_wav = stem_dir / "tenor.wav"
    drums_wav = stem_dir / "drums.wav"
    legacy_wav = stem_dir / "legacy_remaining.wav"

    render_sfizz(RHODES, rhodes_midi, rhodes_wav)
    render_sfizz(TENOR, tenor_midi, tenor_wav)
    render_sfizz(DRUMS, drums_midi, drums_wav)

    run([
        "fluidsynth",
        "-ni",
        "-g", "0.65",
        "-r", "48000",
        SF2,
        legacy_midi,
        "-F", legacy_wav,
        "-O", "s16",
    ])

    final_wav = OUT / "GLASS_MERIDIAN_V3.wav"

    # This is deliberately conservative.
    # First priority is to hear the new sources clearly and safely.
    run([
        "ffmpeg", "-y",
        "-i", rhodes_wav,
        "-i", tenor_wav,
        "-i", drums_wav,
        "-i", legacy_wav,
        "-filter_complex",
        (
            "[0:a]volume=0.90[r];"
            "[1:a]volume=0.90[t];"
            "[2:a]volume=1.10[d];"
            "[3:a]volume=0.68[l];"
            "[r][t][d][l]"
            "amix=inputs=4:normalize=0,"
            "alimiter=limit=0.93[out]"
        ),
        "-map", "[out]",
        "-ar", "48000",
        "-c:a", "pcm_s24le",
        final_wav,
    ])

    preview = OUT / "GLASS_MERIDIAN_V3_AUDITION.mp3"

    run([
        "ffmpeg", "-y",
        "-i", final_wav,
        "-af", "loudnorm=I=-16:LRA=11:TP=-1.5",
        "-c:a", "libmp3lame",
        "-b:a", "256k",
        preview,
    ])

    receipt = {
        "schema": "dio.sonoris.performance_realization.v5",
        "composition_source": str(SOURCE_MIDI),
        "composition_source_sha256": sha256(SOURCE_MIDI),
        "composition_changed": False,
        "seed": SEED,
        "realization": {
            "electric_piano": {
                "source": str(RHODES),
                "sha256": sha256(RHODES),
                "behavior": [
                    "velocity_asymmetry",
                    "chord_rake",
                    "phrase_timing_drift",
                ],
            },
            "tenor_saxophone": {
                "source": str(TENOR),
                "sha256": sha256(TENOR),
                "behavior": [
                    "expression_cc11",
                    "delayed_vibrato_cc1",
                    "legato_cc64",
                ],
            },
            "drums": {
                "source": str(DRUMS),
                "sha256": sha256(DRUMS),
                "behavior": [
                    "instrument_specific_microtiming",
                    "dynamic_variation",
                    "cymbal_breath",
                ],
            },
            "legacy_remaining": {
                "engine": "FluidSynth",
                "source": str(SF2),
                "contains": [
                    "synth_bass_transposed_minus_12",
                    "flute",
                ],
                "status": "temporary_v3_bridge",
            },
        },
        "outputs": {
            "wav": str(final_wav),
            "mp3": str(preview),
        },
    }

    receipt_path = OUT / "GLASS_MERIDIAN_V3_RECEIPT.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2) + "\n"
    )

    print()
    print("=========================================")
    print("SONORIS GLASS MERIDIAN V3 READY")
    print("=========================================")
    print(final_wav)
    print(preview)
    print(receipt_path)


if __name__ == "__main__":
    main()
