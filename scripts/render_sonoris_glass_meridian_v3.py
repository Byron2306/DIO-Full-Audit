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

OUT = Path("/data/byron/sonoris/rendered/glass-meridian-v003")

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
    Keep bass, synth and flute temporarily on FluidR3.
    Rhodes, tenor and drums are removed because V3 renders them separately.
    """
    reject = (
        "electric piano",
        "tenor sax",
        "drum kit",
    )

    mf = mido.MidiFile(type=1, ticks_per_beat=src.ticks_per_beat)

    for tr in src.tracks:
        name = track_name(tr).lower()

        if any(x in name for x in reject):
            continue

        mf.tracks.append(copy.deepcopy(tr))

    destination.parent.mkdir(parents=True, exist_ok=True)
    mf.save(destination)


def rhodes_performance(rows, tpq):
    """
    Human comping:
    - slight upward chord rake
    - velocity asymmetry inside chords
    - tiny phrase-level timing drift
    """
    rng = random.Random(SEED + 101)

    note_ons = {}

    for i, (tick, msg) in enumerate(rows):
        if msg.type == "note_on" and msg.velocity > 0:
            note_ons.setdefault(tick, []).append(i)

    for tick, indices in note_ons.items():
        indices.sort(key=lambda i: rows[i][1].note)

        phrase_bias = rng.randint(-3, 3)

        for rank, idx in enumerate(indices):
            _, msg = rows[idx]

            rake = rank * 4
            rows[idx][0] += phrase_bias + rake

            base = msg.velocity
            accent = (-4, 0, 3, 6, 2)[rank % 5]
            msg.velocity = max(35, min(118, base + accent))

    return rows


def tenor_performance(rows, tpq):
    """
    Give the MTG tenor phrase-level control information.

    CC11 = expression/breath.
    CC1  = delayed vibrato.
    CC64 = legato engagement between phrase notes.
    """
    out = list(rows)

    note_events = [
        (tick, msg)
        for tick, msg in rows
        if msg.type == "note_on" and msg.velocity > 0
    ]

    for n, (tick, msg) in enumerate(note_events):
        ch = msg.channel

        # Breath attack begins slightly under full expression.
        out.append([
            max(0, tick - 8),
            mido.Message(
                "control_change",
                channel=ch,
                control=11,
                value=74 + (n % 3) * 5,
                time=0,
            ),
        ])

        # Phrase swells after the attack.
        out.append([
            tick + max(20, tpq // 6),
            mido.Message(
                "control_change",
                channel=ch,
                control=11,
                value=min(118, 96 + (n % 4) * 4),
                time=0,
            ),
        ])

        # Delayed vibrato, never at the exact attack.
        out.append([
            tick + max(40, tpq // 3),
            mido.Message(
                "control_change",
                channel=ch,
                control=1,
                value=24 + (n % 4) * 9,
                time=0,
            ),
        ])

        # Legato pedal for interior phrase notes.
        if n > 0:
            out.append([
                max(0, tick - 6),
                mido.Message(
                    "control_change",
                    channel=ch,
                    control=64,
                    value=127,
                    time=0,
                ),
            ])

    if note_events:
        end_tick = max(t for t, _ in rows) + 8
        ch = note_events[-1][1].channel

        out.append([
            end_tick,
            mido.Message(
                "control_change",
                channel=ch,
                control=64,
                value=0,
                time=0,
            ),
        ])

        out.append([
            end_tick,
            mido.Message(
                "control_change",
                channel=ch,
                control=1,
                value=0,
                time=0,
            ),
        ])

    return out


def drum_performance(rows, tpq):
    """
    Preserve authored groove but stop the kit behaving like a drum grid.
    """
    rng = random.Random(SEED + 303)

    for tick, msg in rows:
        if msg.type != "note_on" or msg.velocity <= 0:
            continue

        note = msg.note

        # Kick/snare remain relatively tight.
        if note in {36, 38}:
            jitter = rng.randint(-4, 4)

        # Cymbals breathe more.
        elif note in {42, 44, 46, 49, 51, 53, 55, 57, 59}:
            jitter = rng.randint(-8, 8)

        else:
            jitter = rng.randint(-6, 6)

        tick += jitter

        # Natural dynamic hierarchy.
        if note == 38:
            msg.velocity = max(
                45,
                min(121, msg.velocity + rng.randint(-5, 7)),
            )

        elif note == 36:
            msg.velocity = max(
                42,
                min(117, msg.velocity + rng.randint(-4, 6)),
            )

        else:
            msg.velocity = max(
                28,
                min(110, msg.velocity + rng.randint(-8, 8)),
            )

        # Mutate the original row in place.
        for row in rows:
            if row[1] is msg:
                row[0] = max(0, tick)
                break

    return rows


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
        "schema": "dio.sonoris.performance_realization.v3",
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
                    "electric_bass",
                    "synth_lead",
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
