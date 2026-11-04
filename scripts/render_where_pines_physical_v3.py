from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
import json
import random
import re
import subprocess

import mido


ROOT = Path(__file__).resolve().parents[1]

OUT = ROOT / "media/sonoris/releases/black_metal_where_pines_forget_v3"
PLAN = OUT / "SONORIS_PHYSICAL_PERFORMANCE_PLAN.json"

TPQ = 480
SR = 48000

GUITAR_ROOT = Path(
    "/home/byron/fusion-instruments/guitar/Metal-GTX/"
    "UI_METAL-GTX/Programs/Individual Patchs/SFIZZ_CLEAN/"
    "METAL-GTX_Full"
)

BASS_ROOT = Path(
    "/home/byron/fusion-instruments/bass/Growlybass/Growlybass"
)

DRUM_SFZ = Path(
    "/home/byron/fusion-instruments/sonoris/"
    "virtuosity_drums/Programs/02-full-kit.sfz"
)

ARTICULATION_SFZ = {
    "SUSTAIN_DOWN": GUITAR_ROOT / "Sus_Down.sfz",
    "SUSTAIN_UP": GUITAR_ROOT / "Sus_Up.sfz",
    "PALM_MUTE_DOWN": GUITAR_ROOT / "Mute_Down.sfz",
    "PALM_MUTE_UP": GUITAR_ROOT / "Mute_Up.sfz",
}

# Virtuosity full-kit microphone perspective.
#
# Black-metal Frost profile:
# close enough to retain physical attack,
# but overwhelmingly overhead/room oriented.
VIRTUOSITY_FROST_CC = {
    101: 112,  # kick mic
    102: 72,   # kick bleed
    103: 108,  # snare mic
    104: 80,   # snare bleed
    105: 120,  # overhead volume
    106: 110,  # overhead width
    107: 38,   # mid mic
    108: 96,   # mid width
    109: 84,   # room mic
    110: 127,  # room width
    111: 48,   # vintage / lofi mic
    113: 0,    # epic layer OFF
}

BASS_SFZ = {
    "DIRTY": BASS_ROOT / "growlybass_dirty.sfz",
    "VICIOUS": BASS_ROOT / "growlybass_vicious.sfz",
}


def run(cmd):
    subprocess.run(cmd, check=True)


def abs_sfz(
    source: Path,
    target: Path,
    *,
    default_path: str | None = None,
):
    text = source.read_text(
        encoding="utf-8",
        errors="replace",
    ).replace("\\", "/")

    if default_path:
        text = re.sub(
            r"(?m)^\s*default_path\s*=.*$",
            f"default_path={default_path.rstrip('/')}/",
            text,
        )

    def sample(match):
        name = match.group(1).strip()
        return "sample=" + str(
            (source.parent / name).resolve()
        )

    text = re.sub(
        r"(?m)^\s*sample\s*=\s*(.+?)\s*$",
        sample,
        text,
    )

    target.write_text(text)


def write_events(
    events,
    path: Path,
    *,
    controllers: dict[int, int] | None = None,
):
    rows = []

    # Production/mic controls are written at tick zero.
    if controllers:
        for cc, value in sorted(controllers.items()):
            rows.append((
                0,
                -10,
                mido.Message(
                    "control_change",
                    control=int(cc),
                    value=max(0, min(127, int(value))),
                    channel=0,
                ),
            ))

    for event in events:
        tick = int(event["tick"])
        duration = max(1, int(event["duration"]))
        velocity = int(event["velocity"])

        pitches = event.get("pitches") or [event["pitch"]]

        for raw_pitch in pitches:
            pitch = int(raw_pitch)

            rows.append((
                tick,
                1,
                mido.Message(
                    "note_on",
                    note=pitch,
                    velocity=velocity,
                    channel=0,
                ),
            ))

            rows.append((
                tick + duration,
                0,
                mido.Message(
                    "note_off",
                    note=pitch,
                    velocity=0,
                    channel=0,
                ),
            ))

    rows.sort(
        key=lambda row: (
            row[0],
            row[1],
            getattr(row[2], "note", -1),
        )
    )

    midi = mido.MidiFile(
        type=0,
        ticks_per_beat=TPQ,
    )

    track = mido.MidiTrack()
    midi.tracks.append(track)

    track.append(
        mido.MetaMessage(
            "set_tempo",
            tempo=mido.bpm2tempo(168),
            time=0,
        )
    )

    last = 0

    for tick, _, msg in rows:
        msg.time = max(0, tick - last)
        last = tick
        track.append(msg)

    track.append(
        mido.MetaMessage(
            "end_of_track",
            time=1,
        )
    )

    midi.save(path)

def render_sfz(sfz: Path, midi: Path, wav: Path):
    run([
        "sfizz_render",
        "--sfz", str(sfz),
        "--midi", str(midi),
        "--wav", str(wav),
        "--samplerate", str(SR),
    ])


def performer_take(events, seed: int, side: str):
    """
    Realize compiled guitar shape intent as a physical performance.

    One compiler event may contain multiple simultaneously intended voices.
    Those voices become individual MIDI note events here, with rake direction
    determined by the physical pick stroke.

    Same musical intent.
    Different human L/R execution.
    """
    rng = random.Random(seed)

    take_bias = -2 if side == "L" else 2

    realized = []

    for event in events:
        row = dict(event)

        voices = tuple(
            row.get("pitches")
            or [row["pitch"]]
        )

        stroke = row.get("stroke") or "DOWN"
        gesture = row["gesture"]

        # Actual string-travel model.
        #
        # Fast tremolo shapes remain almost simultaneous.
        # Heavy/stomp/hook shapes expose more pick travel.
        rake_span = {
            "TRANCE": 2,
            "SPRINT": 1,
            "PANIC": 1,
            "STOMP": 5,
            "HOOK": 3,
            "COLLAPSE": 4,
            "RELEASE": 4,
        }.get(gesture, 2)

        ordered = sorted(
            voices,
            reverse=(stroke == "UP"),
        )

        # Shared hand timing. All voices belong to one physical attack.
        attack_jitter = rng.randint(-2, 2)

        for voice_index, pitch in enumerate(ordered):
            out = dict(row)

            rake = round(
                voice_index * rake_span /
                max(1, len(ordered) - 1)
            )

            out["pitch"] = int(pitch)

            # Renderer receives monophonic realized voices after this point.
            out["pitches"] = None

            out["tick"] = max(
                0,
                int(row["tick"])
                + take_bias
                + attack_jitter
                + rake
            )

            # Do not make all strings identical in force.
            #
            # DOWN: low strings tend to take slightly more energy.
            # UP: high strings receive the stronger initial contact.
            contact_falloff = voice_index * 2

            out["velocity"] = max(
                1,
                min(
                    127,
                    int(row["velocity"])
                    + rng.randint(-4, 4)
                    - contact_falloff
                )
            )

            duration_scale = rng.uniform(
                0.95,
                1.04,
            )

            if "PALM_MUTE" in row["articulation"]:
                duration_scale *= rng.uniform(
                    0.86,
                    0.95,
                )

            out["duration"] = max(
                1,
                round(
                    int(row["duration"])
                    * duration_scale
                )
            )

            realized.append(out)

    return realized

def group_by_articulation(events):
    grouped = defaultdict(list)

    for event in events:
        grouped[event["articulation"]].append(event)

    return grouped


def render_guitar_performer(
    events,
    *,
    tag: str,
    seed: int,
    side: str,
    work: Path,
):
    take = performer_take(
        events,
        seed,
        side,
    )

    grouped = group_by_articulation(take)

    rendered = []

    for articulation, sfz in ARTICULATION_SFZ.items():
        subset = grouped.get(
            articulation,
            [],
        )

        midi = work / f"{tag}_{articulation}.mid"
        wav = work / f"{tag}_{articulation}.wav"

        write_events(
            subset,
            midi,
        )

        render_sfz(
            sfz,
            midi,
            wav,
        )

        rendered.append(wav)

    raw = work / f"{tag}_raw.wav"

    inputs = []

    for wav in rendered:
        inputs += ["-i", str(wav)]

    labels = "".join(
        f"[{i}:a]"
        for i in range(len(rendered))
    )

    graph = (
        f"{labels}"
        "amix=inputs=4:"
        "duration=longest:"
        "normalize=0,"
        "volume=8dB,"
        "highpass=f=70,"
        "lowpass=f=9500"
        "[out]"
    )

    run([
        "/usr/bin/ffmpeg",
        "-y",
        *inputs,
        "-filter_complex", graph,
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        str(raw),
        "-loglevel", "error",
    ])

    return raw


def render_bass(events, work: Path):
    grouped = group_by_articulation(events)

    rendered = []

    for articulation, sfz in BASS_SFZ.items():
        subset = grouped.get(
            articulation,
            [],
        )

        midi = work / f"bass_{articulation}.mid"
        wav = work / f"bass_{articulation}.wav"

        write_events(
            subset,
            midi,
        )

        render_sfz(
            sfz,
            midi,
            wav,
        )

        rendered.append(wav)

    out = work / "bass.wav"

    run([
        "/usr/bin/ffmpeg",
        "-y",
        "-i", str(rendered[0]),
        "-i", str(rendered[1]),
        "-filter_complex",
        (
            "[0:a][1:a]"
            "amix=inputs=2:"
            "duration=longest:"
            "normalize=0,"
            "highpass=f=35,"
            "lowpass=f=900,"
            "volume=4dB[out]"
        ),
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        str(out),
        "-loglevel", "error",
    ])

    return out


def render_drums(events, work: Path):
    """
    Render through Virtuosity's actual multi-mic full kit.

    The SFZ itself owns close/OH/mid/room/vintage layering. Sonoris controls
    that acoustic perspective through MIDI CCs rather than post-hoc fake room
    effects.
    """
    midi = work / "drums_virtuosity.mid"

    write_events(
        events,
        midi,
        controllers=VIRTUOSITY_FROST_CC,
    )

    wav = work / "drums_virtuosity_frost.wav"

    render_sfz(
        DRUM_SFZ,
        midi,
        wav,
    )

    return wav

def apply_caps_amp(source: Path, target: Path):
    """
    Use the proven Chainsaw amp/cab wrapper rather than inventing
    another fake distortion chain.
    """
    run([
        "python3",
        str(
            Path.home() /
            "polly-grunge-rocker/scripts/run_caps_thr_amp.py"
        ),
        "--input", str(source),
        "--output", str(target),
    ])


def main():
    data = json.loads(
        PLAN.read_text()
    )

    work = OUT / "physical_render"

    if work.exists():
        import shutil
        shutil.rmtree(work)

    work.mkdir(
        parents=True,
        exist_ok=True,
    )

    guitar = data["roles"]["rhythm_guitar"]
    bass = data["roles"]["bass"]
    drums = data["roles"]["drums"]

    left_raw = render_guitar_performer(
        guitar,
        tag="gtrL",
        seed=2801,
        side="L",
        work=work,
    )

    right_raw = render_guitar_performer(
        guitar,
        tag="gtrR",
        seed=7381,
        side="R",
        work=work,
    )

    left = work / "gtrL_amp.wav"
    right = work / "gtrR_amp.wav"

    apply_caps_amp(
        left_raw,
        left,
    )

    apply_caps_amp(
        right_raw,
        right,
    )

    bass_wav = render_bass(
        bass,
        work,
    )

    drums_wav = render_drums(
        drums,
        work,
    )

    final = OUT / "WHERE_THE_PINES_FORGET_PHYSICAL_V3.wav"

    graph = (
        "[0:a]"
        "pan=stereo|c0=0.92*c0|c1=0.08*c1,"
        "volume=-2.5dB[gL];"

        "[1:a]"
        "pan=stereo|c0=0.08*c0|c1=0.92*c1,"
        "volume=-2.5dB[gR];"

        "[2:a]"
        "pan=stereo|c0=0.5*c0|c1=0.5*c1,"
        "volume=0dB[b];"

        "[3:a]"
        "pan=stereo|c0=0.7*c0|c1=0.7*c1,"
        "highpass=f=35,""equalizer=f=78:t=q:w=0.8:g=2.5,""equalizer=f=210:t=q:w=1.0:g=1.5,""equalizer=f=2400:t=q:w=1.1:g=2.8,""equalizer=f=6500:t=q:w=1.0:g=2.5,""acompressor=threshold=0.12:ratio=2.2:attack=8:release=70:makeup=1.4,""volume=4.5dB[d];"

        "[gL][gR][b][d]"
        "amix=inputs=4:"
        "duration=longest:"
        "normalize=0,"
        "alimiter=limit=0.94[out]"
    )

    run([
        "/usr/bin/ffmpeg",
        "-y",
        "-i", str(left),
        "-i", str(right),
        "-i", str(bass_wav),
        "-i", str(drums_wav),
        "-filter_complex", graph,
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        str(final),
        "-loglevel", "error",
    ])

    print(json.dumps({
        "state": "SONORIS_PHYSICAL_RENDER_COMPLETE",
        "wav": str(final),
        "guitar_events": len(guitar),
        "bass_events": len(bass),
        "drum_events": len(drums),
    }, indent=2))


if __name__ == "__main__":
    main()
