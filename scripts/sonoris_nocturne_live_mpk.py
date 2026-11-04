#!/usr/bin/env python3
"""AKAI MPK Mini 3 live Sonoris instrument: Nocturne V4 + electronic darksynth.

Native Nocturne V4 oscillator voices are preserved for Funeral Motif and Choir.
The new Dark Engine and Razor Lead voices use a dedicated synthesized saw/pulse
oscillator, layered sub, filter envelope and saturation, not a GM SoundFont.
Offline note banks are played in real time through PortAudio.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import queue
import sys

import numpy as np
from scipy import signal
import mido
import sounddevice as sd

from products.sonoris_nocturne_engine_v4 import SR, _note, _echo, _space


PATCHES = {
    "motif": {
        "kind": "motif",
        "duration": 2.8,
        "tail": 0.8,
        "release": 0.16,
        "fx": (0.375, 0.31, 0.48),
        "timbre": {
            "oscillator_detune_cents": 18,
            "filter_cutoff_hz": 920,
            "filter_envelope": 1.15,
            "drive": 4.5,
            "stereo_drift": 0.006,
            "noise_texture": 0.004,
            "darkness": 0.90,
            "harmonic_grit": 0.90,
            "dread_motion": 0.78,
            "motif_level": 0.34,
        },
    },
    "darksynth": {
        "kind": "electronic_bass",
        "duration": 3.2,
        "tail": 0.35,
        "release": 0.075,
        "fx": (0.25, 0.08, 0.13),
        "timbre": {
            "oscillator_detune_cents": 9,
            "drive": 5.2,
            "filter_cutoff_hz": 1500,
            "motif_level": 0.65,
        },
    },
    "razor": {
        "kind": "electronic_lead",
        "duration": 3.0,
        "tail": 0.55,
        "release": 0.12,
        "fx": (0.28, 0.18, 0.28),
        "timbre": {
            "oscillator_detune_cents": 18,
            "drive": 5.0,
            "filter_cutoff_hz": 2550,
            "motif_level": 0.64,
        },
    },
    "choir": {
        "kind": "pad",
        "duration": 6.0,
        "tail": 1.5,
        "release": 0.65,
        "fx": (0.53, 0.42, 1.70),
        "timbre": {
            "oscillator_detune_cents": 21,
            "filter_cutoff_hz": 510,
            "filter_envelope": 1.20,
            "drive": 3.7,
            "stereo_drift": 0.008,
            "noise_texture": 0.006,
            "darkness": 0.94,
            "harmonic_grit": 0.92,
            "dread_motion": 0.86,
            "pad_level": 0.105,
        },
    },
}



def synth_electronic(name: str, pitch: int, duration: float, timbre: dict) -> np.ndarray:
    """Fast-attack darksynth. True oscillators, not repitched GM samples.

    Envelope supplies tight 16th-note and triplet articulations; the note-off
    event remains responsible for cutting the active sampled voice.
    """
    n = int(round(SR * duration))
    t = np.arange(n, dtype=np.float64) / SR
    f = 440.0 * 2 ** ((pitch - 69) / 12)
    lead = name == 'razor'
    detune = 2 ** (float(timbre['oscillator_detune_cents']) / 1200)
    ph_l = 2 * np.pi * f * t
    ph_r = 2 * np.pi * f * detune * t + 0.27

    # Pulse + saw + half-frequency undertone: the low register stays thick.
    saw_l = signal.sawtooth(ph_l, 0.50)
    saw_r = signal.sawtooth(ph_r, 0.50)
    pulse_l = signal.square(ph_l, duty=0.36 if lead else 0.43)
    pulse_r = signal.square(ph_r, duty=0.42 if lead else 0.48)
    sub = np.sin(0.5 * ph_l)
    sub_mix = 0.17 if lead else 0.44
    pair = np.column_stack((
        0.68*saw_l + 0.42*pulse_l + sub_mix*sub,
        0.66*saw_r + 0.41*pulse_r + sub_mix*sub,
    ))
    pair = np.tanh(pair * float(timbre['drive']))

    # Keep a darker body behind a dynamically opening high-mid edge.
    cutoff = float(timbre['filter_cutoff_hz'])
    low = signal.sosfilt(signal.butter(2, max(220, cutoff * 0.48),
                                        btype='lowpass', fs=SR, output='sos'), pair, axis=0)
    high = signal.sosfilt(signal.butter(2, min(7500, cutoff * 2.15),
                                         btype='lowpass', fs=SR, output='sos'), pair, axis=0)
    # Each key strike starts open then settles into an industrial growl.
    opening = 0.23 + 0.65*np.exp(-t/(0.14 if lead else 0.19))
    pair = low*(1.0-opening[:, None]) + high*opening[:, None]
    pair = np.tanh(pair * (1.6 if lead else 1.9))

    # Short attack, powerful body; the Player handles separate note-off fade.
    attack = np.minimum(1.0, t/0.003)
    decay = np.exp(-t/(0.21 if lead else 0.18))
    envelope = attack * ((0.57 if lead else 0.71) + (0.43 if lead else 0.29)*decay)
    fade = min(int(SR*.05), n)
    envelope[-fade:] *= np.linspace(1, 0, fade, dtype=np.float64)
    return (pair * envelope[:, None] * float(timbre['motif_level'])).astype(np.float32)


def build_sample(name: str, pitch: int) -> np.ndarray:
    p = PATCHES[name]
    total = p["duration"] + p["tail"]
    buf = np.zeros((int(SR * total), 2), dtype=np.float32)
    rng = np.random.default_rng(1993 + pitch * 97 + (0 if name == "motif" else 733))
    if name in ('darksynth', 'razor'):
        signal_buf = synth_electronic(name, pitch, p['duration'], p['timbre'])
        buf[:len(signal_buf)] += signal_buf
    else:
        _note(buf, 0.0, p["duration"], pitch, 1.0,
              kind=p["kind"], rng=rng, timbre=p["timbre"])
    delay, wet, space = p["fx"]
    buf = _space(_echo(buf, delay, wet=wet), wet=space)
    peak = float(np.max(np.abs(buf)))
    if peak < 1e-6:
        raise RuntimeError(f"SILENT_NOCTURNE_V4_PATCH: {name} {pitch}")
    # Preserve the V4 waveform/timbre while providing a useful live play level.
    # Headroom is handled later by the polyphonic mix soft limiter.
    buf *= min(7.0, 0.56 / peak)
    fade_len = min(int(SR * .05), len(buf))
    buf[-fade_len:] *= np.linspace(1, 0, fade_len, dtype=np.float32)[:, None]
    return np.asarray(buf, dtype=np.float32)


@dataclass
class Voice:
    note: int
    sample: np.ndarray
    velocity: float
    release_seconds: float
    cursor: int = 0
    fade: float = 1.0
    releasing: bool = False


class Player:
    def __init__(self, bank, commands, gain: float):
        self.bank = bank
        self.commands = commands
        self.patch = "darksynth"
        self.voices = []
        self.gain = gain

    def callback(self, outdata, frames, time_info, status):
        try:
            while True:
                kind, val = self.commands.get_nowait()
                if kind == "patch":
                    self.patch = val
                    for voice in self.voices:
                        voice.releasing = True
                elif kind == "on":
                    note, velocity = val
                    sample = self.bank.get((self.patch, note))
                    if sample is not None:
                        for voice in self.voices:
                            if voice.note == note:
                                voice.releasing = True
                        self.voices.append(Voice(note, sample, max(.12, velocity / 127),
                                                 PATCHES[self.patch]["release"]))
                        self.voices = self.voices[-12:]
                elif kind == "off":
                    for voice in self.voices:
                        if voice.note == val:
                            voice.releasing = True
                elif kind == "gain":
                    self.gain = max(.10, min(1.3, val))
        except queue.Empty:
            pass

        mix = np.zeros((frames, 2), dtype=np.float32)
        remaining = []
        for voice in self.voices:
            take = min(frames, len(voice.sample) - voice.cursor)
            if take <= 0:
                continue
            segment = voice.sample[voice.cursor:voice.cursor + take]
            if voice.releasing:
                next_fade = max(0., voice.fade - take / (SR * voice.release_seconds))
                envelope = np.linspace(voice.fade, next_fade, take,
                                       endpoint=False, dtype=np.float32)
                mix[:take] += segment * (envelope[:, None] * voice.velocity)
                voice.fade = next_fade
            else:
                mix[:take] += segment * voice.velocity
            voice.cursor += take
            if voice.cursor < len(voice.sample) and voice.fade > 0.0:
                remaining.append(voice)
        self.voices = remaining
        outdata[:] = np.tanh(mix * self.gain * 1.15) * 0.72


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--midi", help="Substring of AKAI MIDI port name", default="MPK mini 3")
    ap.add_argument("--min-note", type=int, default=24)
    ap.add_argument("--max-note", type=int, default=84)
    ap.add_argument("--gain", type=float, default=0.70)
    ap.add_argument("--device", help="PortAudio output device index or name (optional)")
    args = ap.parse_args()
    if not 0 <= args.min_note <= args.max_note <= 127:
        ap.error("invalid MIDI note range")

    names = mido.get_input_names()
    ports = [x for x in names if args.midi.lower() in x.lower()]
    if not ports:
        print("MIDI_INPUTS:", names, file=sys.stderr)
        raise SystemExit("AKAI_MIDI_PORT_MISSING")
    midi_name = ports[0]

    print("SONORIS_LIVE_BANK: preparing Nocturne V4 and electronic darksynth (no GM piano)...", flush=True)
    cache = Path.home() / ".cache" / "sonoris" / "nocturne-v4-live-02"
    cache.mkdir(parents=True, exist_ok=True)
    bank = {}
    for patch in PATCHES:
        for pitch in range(args.min_note, args.max_note + 1):
            path = cache / f"{patch}-{pitch}.npy"
            if path.is_file():
                audio = np.load(path, allow_pickle=False)
            else:
                audio = build_sample(patch, pitch)
                np.save(path, audio, allow_pickle=False)
            bank[(patch, pitch)] = np.asarray(audio, dtype=np.float32)
        print(f"{patch.upper()}_BANK=READY ({args.min_note}..{args.max_note})", flush=True)

    commands = queue.SimpleQueue()
    player = Player(bank, commands, gain=args.gain)
    midi_device = None
    if args.device is not None:
        midi_device = int(args.device) if args.device.isdigit() else args.device
    print("AUDIO_OUTPUT:", sd.query_devices(midi_device, kind="output")['name'], flush=True)
    print("MIDI_INPUT:", midi_name, flush=True)
    print("AKAI_PADS: 47=FUNERAL  50=CHOIR  48=DARK_ENGINE  55=RAZOR_LEAD", flush=True)
    print("DEFAULT_VOICE=DARK_ENGINE", flush=True)
    print("CC_71=MASTER_GAIN (optional)  Ctrl+C=EXIT", flush=True)
    print("NOCTURNE_V4_LIVE=READY", flush=True)
    with sd.OutputStream(device=midi_device, samplerate=SR, channels=2,
                         dtype="float32", blocksize=512, latency="low",
                         callback=player.callback):
        with mido.open_input(midi_name) as midi:
            for msg in midi:
                if msg.type == "note_on" and msg.velocity > 0:
                    if msg.channel == 9 and msg.note in (47, 50, 48, 55):
                        patch = {47: 'motif', 50: 'choir',
                                 48: 'darksynth', 55: 'razor'}[msg.note]
                        commands.put(("patch", patch))
                        print("VOICE=", patch.upper(), flush=True)
                    elif msg.channel != 9:
                        if args.min_note <= msg.note <= args.max_note:
                            commands.put(("on", (msg.note, msg.velocity)))
                        else:
                            print(f"NOTE_OUT_OF_RANGE={msg.note}", flush=True)
                elif msg.type in ("note_off", "note_on") and msg.channel != 9:
                    commands.put(("off", msg.note))
                elif msg.type == "control_change" and msg.channel != 9 and msg.control == 71:
                    # Current Akai K1 CC71. CC changes master output, not the baked patch.
                    commands.put(("gain", .35 + .85 * msg.value / 127))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nNOCTURNE_V4_LIVE=STOPPED")
