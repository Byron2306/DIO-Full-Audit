#!/usr/bin/env python3
"""Render the embodied-grammar Jazz Synth Fusion prototype, Glass Meridian."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
from pathlib import Path

import mido

TPQ = 480
BARS = 44
BPM = 108
OUT_DEFAULT = Path("/data/byron/sonoris/rendered/glass-meridian-v002")
SF2_DEFAULT = Path("/usr/share/sounds/sf2/FluidR3_GM.sf2")
FORM = [("opening", 0, 4, "GLIDE"), ("pocket_theme", 4, 8, "LOCK"),
        ("fracture", 12, 8, "FRACTURE"), ("synth_improvisation", 20, 8, "ORBIT"),
        ("handoff", 28, 4, "HANDOFF"), ("return_transformed", 32, 8, "LIFT"),
        ("coda", 40, 4, "RELEASE")]
CHORDS = [
    [50, 53, 57, 60, 64], [55, 59, 65, 69, 74], [48, 52, 55, 59, 62], [45, 49, 54, 55, 64],
    [50, 53, 57, 60, 64], [55, 59, 65, 69, 74], [46, 50, 53, 57, 60], [51, 55, 58, 61, 69],
    [50, 53, 57, 60, 64], [55, 59, 65, 69, 74], [48, 52, 55, 59, 62], [45, 49, 54, 55, 64],
    [52, 55, 59, 62, 66], [45, 49, 52, 55, 64], [50, 54, 57, 61, 64], [42, 46, 49, 52, 56],
    [47, 50, 54, 57, 61], [40, 44, 50, 54, 61], [50, 53, 57, 60, 64], [45, 49, 54, 55, 64],
    [50, 53, 57, 60, 64], [55, 59, 65, 69, 74], [48, 52, 55, 59, 62], [45, 49, 54, 55, 64],
    [50, 53, 57, 60, 64], [46, 50, 53, 57, 60], [51, 55, 58, 61, 69], [45, 49, 54, 55, 64],
    [50, 53, 57, 60, 64], [55, 59, 65, 69, 74], [48, 52, 55, 59, 62], [45, 49, 54, 55, 64],
    [52, 55, 59, 62, 66], [45, 49, 52, 55, 64], [50, 54, 57, 61, 64], [42, 46, 49, 52, 56],
    [47, 50, 54, 57, 61], [40, 44, 50, 54, 61], [50, 53, 57, 60, 64], [45, 49, 54, 55, 64],
    [50, 53, 57, 60, 64], [55, 59, 65, 69, 74], [48, 52, 55, 59, 62], [50, 53, 57, 60, 62],
]


def bar_start(bar: int) -> int: return bar * TPQ * 4


def section_for(bar: int) -> str:
    return next(name for name, start, count, _ in FORM if start <= bar < start + count)


def gesture_for(bar: int) -> str:
    return next(gesture for _, start, count, gesture in FORM if start <= bar < start + count)


def _track(name: str, channel: int, program: int | None, events: list[tuple[int, int, mido.Message]], markers=()):
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=name, time=0))
    if program is not None: track.append(mido.Message("program_change", channel=channel, program=program, time=0))
    absolute = [(tick, order, msg) for tick, order, msg in events]
    for tick, label in markers: absolute.append((tick, -2, mido.MetaMessage("marker", text=label)))
    absolute.sort(key=lambda row: (row[0], row[1], row[2].type))
    previous = 0
    for tick, _, msg in absolute:
        msg.time = max(0, tick - previous)
        track.append(msg)
        previous = tick
    track.append(mido.MetaMessage("end_of_track", time=1))
    return track


def _note(events, channel, pitch, start, duration, velocity, *, humanize=0, rng=None):
    if rng is not None and humanize:
        start = max(0, start + rng.randint(-humanize, humanize))
    velocity = max(1, min(127, velocity))
    events.append((start, 1, mido.Message("note_on", channel=channel, note=pitch, velocity=velocity)))
    events.append((start + duration, 0, mido.Message("note_off", channel=channel, note=pitch, velocity=0)))


def _phrase_lead(bar: int, gesture: str):
    start = bar_start(bar)
    if 4 <= bar < 12:
        # M1: syncopated rising fourth, step down, then a suspended color tone.
        variants = [(0, 74, 270), (600, 77, 170), (960, 79, 420), (1560, 81, 260)]
        return [(start+t, p, d, 88 if t == 0 else 76) for t,p,d in variants]
    if 12 <= bar < 20:
        # M2: chromatic descending answer with gaps that expose the ensemble.
        seed = 83 if bar % 2 == 0 else 81
        return [(start, seed, 170, 78), (300, seed-1, 150, 72), (720, seed-4, 260, 84), (1320, seed-7, 220, 74)]
    if 20 <= bar < 28:
        # ORBIT: M1 fragments expanded into short modal runs, not a repeated hook.
        base = [74, 77, 79, 81, 84, 81, 79, 77]
        shift = 0 if bar < 24 else 2
        slots = [0, 180, 480, 780, 1080, 1320, 1560, 1740]
        return [(start+t, p+shift, 105 if i in (1, 4, 7) else 155,
                 70 + (i % 3)*7) for i,(t,p) in enumerate(zip(slots, base))]
    if 32 <= bar < 40:
        # Return transformed: M1 moved up a whole step and opened into longer notes.
        return [(start, 76, 360, 91), (600, 79, 220, 77), (960, 81, 360, 86), (1560, 83, 330, 100)]
    return []


def build_midi(path: Path) -> dict:
    rng = random.Random(20261028)
    midi = mido.MidiFile(type=1, ticks_per_beat=TPQ)
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("track_name", name="Glass Meridian | embodied jazz synth fusion prototype", time=0))
    meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(BPM), time=0))
    meta.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    meta.append(mido.MetaMessage("key_signature", key="Dm", time=0))
    previous = 0
    for name, start, bars, gesture in FORM:
        msg = mido.MetaMessage("marker", text=f"{name.upper()} | {gesture}", time=bar_start(start)-previous)
        meta.append(msg); previous = bar_start(start)
    meta.append(mido.MetaMessage("end_of_track", time=1)); midi.tracks.append(meta)

    keys, bass, drums, synth, sax, flute = [], [], [], [], [], []
    for bar in range(BARS):
        t = bar_start(bar); gesture = gesture_for(bar); chord = CHORDS[bar]
        # EP comping: space at the opening/coda; off-beat answers to kick in the pocket.
        if bar < 4 or bar >= 40:
            _note(keys, 0, chord[0]+12, t, TPQ*3, 61 if bar < 40 else 50, humanize=5, rng=rng)
            for i, pitch in enumerate(chord[1:]): _note(keys, 0, pitch+12, t, TPQ*3, 43, humanize=4, rng=rng)
        else:
            hits = [180, 720, 1260] if gesture in ("LOCK", "ORBIT") else [0, 660, 1440]
            if gesture == "FRACTURE": hits = [120, 570, 990, 1530]
            if gesture == "LIFT": hits = [0, 540, 1080, 1560]
            for hit_i, offset in enumerate(hits):
                voicing = chord[1:] if hit_i % 2 == 0 else chord[1:4]
                for pitch in voicing:
                    _note(keys, 0, pitch+12, t+offset, 210 if gesture != "RELEASE" else 420,
                          53 + (hit_i == 0)*9 + rng.randint(-4, 4), humanize=7, rng=rng)

        # Bass has a recognizable two-bar lock, chromatic pickups, and intentional escape fills.
        root = chord[0]-12
        if bar < 4 or bar >= 40:
            _note(bass, 1, root, t, TPQ*3, 65 if bar < 40 else 48, humanize=6, rng=rng)
        elif gesture == "FRACTURE":
            for offset, pitch, dur, vel in [(0,root,300,87),(420,root+7,180,69),(870,root+10,180,76),(1440,root+11,180,81)]:
                _note(bass, 1, pitch, t+offset, dur, vel, humanize=8, rng=rng)
        else:
            for beat in range(4):
                offset = beat*TPQ
                pitch = [root, root+7, root+10, root+11 if beat == 3 else root+7][beat]
                _note(bass, 1, pitch, t+offset, 285, 82 if beat in (0,2) else 68, humanize=7, rng=rng)
                if gesture in ("LOCK", "ORBIT", "LIFT") and beat in (1,3):
                    _note(bass, 1, pitch+12, t+offset+300, 110, 59, humanize=5, rng=rng)

        # Kit follows the gesture: ride pocket, syncopated breaks, transition fills, and release.
        if bar < 4 or bar >= 40:
            if bar < 4:
                for beat in (0,2): _note(drums, 9, 36, t+beat*TPQ, 65, 54, rng=None)
                for beat in range(4): _note(drums, 9, 51, t+beat*TPQ, 60, 50, rng=None)
            elif bar == 43:
                _note(drums, 9, 49, t, 220, 48, rng=None)
        else:
            for beat in range(4):
                swing = 315
                if gesture != "FRACTURE": _note(drums, 9, 51, t+beat*TPQ, 55, 63 if beat in (0,2) else 49, rng=None)
                if gesture == "FRACTURE" and beat in (1,3): _note(drums, 9, 42, t+beat*TPQ, 45, 38, rng=None)
                else: _note(drums, 9, 42, t+beat*TPQ, 45, 47, rng=None)
                if beat in (0,2): _note(drums, 9, 36, t+beat*TPQ, 75, 76 if gesture != "FRACTURE" else 66, rng=None)
                if beat in (1,3) and gesture != "FRACTURE": _note(drums, 9, 38, t+beat*TPQ, 80, 71, rng=None)
                if gesture in ("LOCK", "ORBIT", "LIFT") and beat in (0,2):
                    _note(drums, 9, 51, t+beat*TPQ+swing, 40, 43, rng=None)
            if gesture == "FRACTURE":
                for off, note in [(510,38),(1110,45),(1710,47)]: _note(drums,9,note,t+off,65,58,rng=None)
            if bar in (11,19,27,31,39):
                for off,note in [(1440,45),(1560,47),(1680,50),(1800,49)]: _note(drums,9,note,t+off,70,65,rng=None)

        # Foreground identity changes instrument while the hook motif remains recognizable.
        if 4 <= bar < 12 or 12 <= bar < 20 or 20 <= bar < 28 or 32 <= bar < 40:
            for start, pitch, dur, vel in _phrase_lead(bar, gesture):
                _note(synth, 2, pitch, start, dur, vel, humanize=5, rng=rng)
        if 24 <= bar < 28:
            # Tenor sax begins answering the synth before the explicit handoff.
            for start, pitch, dur, vel in _phrase_lead(bar, "ORBIT"):
                _note(sax, 4, pitch-12, start, dur+40, vel-7, humanize=8, rng=rng)
        if bar < 4 or 28 <= bar < 32 or 40 <= bar < 44:
            # Flute carries M0 as a sparse rising fourth and then a held color tone.
            motif = [(0,74,420),(720,79,360),(1320,81,420)]
            if bar >= 40: motif = [(0,74,TPQ*2)] if bar in (40,42) else []
            if bar % 2 == 0:
                for offset, pitch, dur in motif:
                    _note(flute, 5, pitch, t+offset, dur, 57 if bar < 4 else 68, humanize=10, rng=rng)

    midi.tracks.extend([
        _track("Electric piano | harmonic bed / syncopated comp", 0, 4, keys),
        _track("Electric bass | lock / push / escape", 1, 33, bass),
        _track("Drum kit | groove interlocutor", 9, None, drums),
        _track("Synth lead | M1 / M2 foreground", 2, 81, synth),
        _track("Tenor saxophone | motif response", 4, 66, sax),
        _track("Flute | motif atmosphere / handoff", 5, 73, flute),
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    midi.save(path)
    return {"bars": BARS, "bpm": BPM, "duration_s_estimate": round(BARS*4*60/BPM, 2),
            "meter": "4/4", "tracks": [t.name for t in midi.tracks[1:]], "seed": 20261028}


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024), b""): h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--out",type=Path,default=Path("/data/byron/sonoris/rendered/glass-meridian-v002")); p.add_argument("--sf2",type=Path,default=SF2_DEFAULT); a=p.parse_args()
    if a.out.exists() and any(a.out.iterdir()): raise SystemExit(f"Refusing non-empty output directory: {a.out}")
    if not a.sf2.is_file(): raise SystemExit(f"Missing soundfont: {a.sf2}")
    a.out.mkdir(parents=True,exist_ok=True)
    midi_path=a.out/"GLASS_MERIDIAN_JAZZ_SYNTH_FUSION.mid"
    info=build_midi(midi_path)
    wav_path=a.out/"GLASS_MERIDIAN_LISTENING_RENDER.wav"
    subprocess.run(["fluidsynth","-ni","-g","0.65","-r","48000",str(a.sf2),str(midi_path),"-F",str(wav_path),"-O","s16"],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    quality_run = subprocess.run(["ffmpeg","-hide_banner","-i",str(wav_path),"-filter_complex","ebur128=peak=true","-f","null","-"],capture_output=True,text=True,check=True)
    quality_text = quality_run.stderr
    integrated = re.findall(r"I:\s+(-?\d+\.\d+) LUFS", quality_text)
    loudness_range = re.findall(r"LRA:\s+(\d+\.\d+) LU", quality_text)
    true_peak = re.findall(r"Peak:\s+(-?\d+\.\d+) dBFS", quality_text)
    preview_path=a.out/"GLASS_MERIDIAN_AUDITION.mp3"
    subprocess.run(["ffmpeg","-hide_banner","-y","-i",str(wav_path),"-af","loudnorm=I=-18:TP=-1.0:LRA=9","-c:a","libmp3lame","-b:a","192k",str(preview_path)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    composition={"schema":"dio.sonoris.embodied_composition.v1","title":"Glass Meridian","status":"experimental_authored_prototype","grammar":"jazz-synth-fusion-experimental-v1","gesture_arc":[{"section":n,"start_bar":s,"bars":b,"gesture":g} for n,s,b,g in FORM],**info,
      "instrument_behavior":{"electric_piano":"sparse suspended color then syncopated comp","electric_bass":"locks to kick; fractures with chromatic pushes and brief escape fills","drums":"ride answers groove; syncopated hits and transition fills shape section changes","synth_lead":"carries M1/M2 and improvises around M1","tenor_saxophone":"answers and inherits motif","flute":"opens space and receives/returns M0"},
      "render":{"engine":"FluidSynth 2.4.4","soundfont":str(a.sf2),"soundfont_license":"MIT; retain attribution and notice for redistribution","soundfont_sha256":sha(a.sf2),"local_only":True,"commercial_clearance":"instrument source is MIT; composition is original prototype; release review and notices still required","sonic_review":"PENDING_OWNER_LISTENING"},
      "measured_audio_quality":{"integrated_lufs":float(integrated[-1]) if integrated else None,"loudness_range_lu":float(loudness_range[-1]) if loudness_range else None,"true_peak_dbtp":float(true_peak[-1]) if true_peak else None,"mix_note":"Listening render sits near full-scale peak and needs mastering headroom before release; normalized MP3 is an audition copy only."}}
    plan=a.out/"COMPOSITION_PLAN_AND_RENDER_RECEIPT.json"; plan.write_text(json.dumps(composition,indent=2)+"\n",encoding="utf-8")
    for path in (midi_path,wav_path,preview_path): composition.setdefault("artifacts",[]).append({"path":path.name,"bytes":path.stat().st_size,"sha256":sha(path)})
    plan.write_text(json.dumps(composition,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output_dir":str(a.out),"artifacts":composition["artifacts"],"duration_s_estimate":info["duration_s_estimate"],"status":composition["status"]},indent=2))


if __name__=="__main__": main()
