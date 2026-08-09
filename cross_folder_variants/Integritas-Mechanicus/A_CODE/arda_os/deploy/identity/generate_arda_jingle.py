#!/usr/bin/env python3
"""Generate a short ceremonial ARDA awakening jingle."""

from __future__ import annotations

import argparse
import math
import wave
from pathlib import Path


SAMPLE_RATE = 44_100


def envelope(t: float, duration: float, attack: float, decay: float, sustain: float, release: float) -> float:
    if t < 0.0 or t > duration:
        return 0.0
    if t < attack:
        return t / max(attack, 1e-6)
    if t < attack + decay:
        return 1.0 - (1.0 - sustain) * ((t - attack) / max(decay, 1e-6))
    if t < duration - release:
        return sustain
    return sustain * max(0.0, 1.0 - (t - (duration - release)) / max(release, 1e-6))


def sine(freq: float, t: float) -> float:
    return math.sin(2.0 * math.pi * freq * t)


def bell_tone(freq: float, t: float, duration: float) -> float:
    env = envelope(t, duration, 0.015, 0.55, 0.58, 0.85)
    partials = (
        0.86 * sine(freq, t)
        + 0.28 * sine(freq * 2.0, t)
        + 0.12 * sine(freq * 3.0, t)
        + 0.07 * sine(freq * 4.0, t)
    )
    shimmer = 0.03 * sine(freq * 0.75, t) * sine(freq * 5.0, t)
    return env * (partials + shimmer)


def choir_tone(freq: float, t: float, duration: float) -> float:
    env = envelope(t, duration, 0.12, 0.48, 0.78, 0.75)
    voices = (
        0.82 * sine(freq, t)
        + 0.31 * sine(freq * 2.0, t)
        + 0.10 * sine(freq * 3.0, t)
    )
    return env * voices


def pad_tone(freq: float, t: float, duration: float) -> float:
    env = envelope(t, duration, 0.35, 0.8, 0.38, 1.0)
    return env * (
        0.62 * sine(freq, t)
        + 0.16 * sine(freq * 2.0, t)
        + 0.05 * sine(freq * 0.5, t)
    )


def add_note(buf: list[float], start: float, duration: float, freq: float, gain: float, tone) -> None:
    start_i = int(start * SAMPLE_RATE)
    end_i = min(len(buf), int((start + duration) * SAMPLE_RATE))
    for i in range(start_i, end_i):
        t = i / SAMPLE_RATE - start
        buf[i] += gain * tone(freq, t, duration)


def render(duration: float) -> list[float]:
    frames = int(duration * SAMPLE_RATE)
    buf = [0.0] * frames

    # Key center: D major with a Lydian silver lift via G#.
    d4 = 293.66
    fs4 = 369.99
    a4 = 440.00
    b4 = 493.88
    d5 = 587.33
    e5 = 659.25
    fs5 = 739.99
    gs5 = 830.61

    # Airy foundation, not a dark drone.
    add_note(buf, 0.00, 4.4, d4, 0.08, pad_tone)
    add_note(buf, 0.18, 4.0, a4 / 2.0, 0.05, pad_tone)

    # Clear heraldic bells.
    add_note(buf, 0.04, 1.9, d5, 0.26, bell_tone)
    add_note(buf, 0.52, 1.8, fs5, 0.20, bell_tone)
    add_note(buf, 1.02, 1.8, a4, 0.18, bell_tone)

    # Noble choir ascent.
    add_note(buf, 0.38, 2.3, d4, 0.13, choir_tone)
    add_note(buf, 0.70, 2.2, fs4, 0.13, choir_tone)
    add_note(buf, 1.00, 2.3, a4, 0.12, choir_tone)
    add_note(buf, 1.42, 2.2, d5, 0.10, choir_tone)

    # Elven silver flare: the raised fourth gives lift instead of dread.
    add_note(buf, 2.02, 1.9, b4, 0.11, choir_tone)
    add_note(buf, 2.16, 1.8, e5, 0.12, choir_tone)
    add_note(buf, 2.28, 1.8, gs5, 0.10, bell_tone)
    add_note(buf, 2.56, 1.8, fs5, 0.12, bell_tone)

    # Coronation resolve.
    add_note(buf, 3.00, 1.7, d4, 0.15, choir_tone)
    add_note(buf, 3.00, 1.7, a4, 0.13, choir_tone)
    add_note(buf, 3.00, 1.7, d5, 0.12, bell_tone)
    add_note(buf, 3.18, 1.6, fs5, 0.10, bell_tone)

    # Normalize conservatively.
    peak = max(max(buf), -min(buf), 1e-6)
    scale = 0.78 / peak
    return [sample * scale for sample in buf]


def write_wav(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for sample in samples:
            value = max(-1.0, min(1.0, sample))
            pcm = int(value * 32767.0)
            frames.extend(pcm.to_bytes(2, "little", signed=True))
        wav_file.writeframes(bytes(frames))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the ARDA awakening jingle")
    parser.add_argument("--output", required=True, help="Output .wav path")
    parser.add_argument("--duration", type=float, default=5.0, help="Length in seconds")
    args = parser.parse_args()

    samples = render(max(3.5, args.duration))
    write_wav(Path(args.output), samples)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
