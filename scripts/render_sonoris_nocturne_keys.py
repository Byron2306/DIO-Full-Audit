from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf

from products.sonoris_nocturne_engine_v4 import (
    SR,
    _echo,
    _note,
    _space,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    request = json.loads(
        Path(args.request).read_text()
    )

    bpm = float(request["bpm"])
    bars = int(request["bars"])
    voice = str(request["voice"])
    timbre = dict(request["timbre"])
    events = list(request["events"])
    seed = int(request.get("seed", 1993))

    seconds_per_beat = 60.0 / bpm

    song_seconds = (
        bars * 4 * seconds_per_beat
    )

    event_end = max(
        (
            (
                float(e["beat"])
                + float(e["duration"])
            )
            * seconds_per_beat
            for e in events
        ),
        default=0.0,
    )

    duration = max(
        song_seconds,
        event_end + 2.5,
    )

    n = int(
        round(duration * SR)
    )

    audio = np.zeros(
        (n, 2),
        dtype=np.float32,
    )

    rng = np.random.default_rng(seed)

    for event in events:
        velocity = float(
            event.get(
                "velocity",
                58,
            )
        )

        if velocity > 1:
            velocity /= 127.0

        _note(
            audio,
            float(event["beat"])
            * seconds_per_beat,

            float(event["duration"])
            * seconds_per_beat,

            float(event["pitch"]),

            max(
                0.01,
                min(
                    1.0,
                    velocity,
                ),
            ),

            kind=voice,
            rng=rng,
            timbre=timbre,
        )

    if voice == "motif":
        audio = _echo(
            audio,
            .375,
            wet=.31,
        )

        audio = _space(
            audio,
            wet=.48,
        )

    elif voice == "pad":
        audio = _echo(
            audio,
            .53,
            wet=.42,
        )

        audio = _space(
            audio,
            wet=1.70,
        )

    peak = float(
        np.max(
            np.abs(audio)
        )
    )

    if peak > .96:
        audio *= (
            .96 / peak
        )

    output = Path(args.output)

    sf.write(
        output,
        audio,
        SR,
        subtype="PCM_16",
    )

    print(
        json.dumps(
            {
                "state": "PASS",
                "engine":
                    "sonoris_nocturne_engine_v4",
                "voice":
                    voice,
                "events":
                    len(events),
                "output":
                    str(output),
            }
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
