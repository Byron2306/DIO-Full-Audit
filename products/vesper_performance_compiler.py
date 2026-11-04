"""Deterministic phoneme-to-viseme compiler for Vera/VESPER.

This module compiles already-aligned phoneme events. It does not synthesize or
alter Vera's audio, infer phonemes, or render a face. Its output is a sampled
ARKit-compatible facial-control timeline for a downstream face/mouth renderer.
"""

from __future__ import annotations

import argparse
import json
import re
from bisect import bisect_right
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "config" / "vesper" / "viseme_contract_v1.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
VOICE_PROFILE_ID = CONTRACT["authority"]["voice_profile_id"]
VISEMES = CONTRACT["visemes"]
PHONEME_MAP = {
    _phoneme: _name
    for _name, _viseme in VISEMES.items()
    for _phoneme in _viseme["phonemes"]
}
FALLBACK_PHONEMES = set(CONTRACT["phoneme_fallbacks"]["phonemes"])
DEFAULT_FPS = CONTRACT["timing"]["default_fps"]
DEFAULT_COARTICULATION_MS = CONTRACT["timing"]["default_coarticulation_ms"]


def _normalize_phoneme(value: Any) -> str:
    """Normalize ARPAbet stress suffixes and case (e.g. AH0 -> AH)."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("phoneme symbol must be a non-empty string")
    return re.sub(r"[0-2]$", "", value.strip().upper())


def _viseme_for(phoneme: str) -> str:
    return PHONEME_MAP.get(phoneme, "EE" if phoneme in FALLBACK_PHONEMES else "REST")


def _shape(viseme: str) -> dict[str, float]:
    return dict(VISEMES[viseme]["blendshapes"])


def _mix(left: dict[str, float], right: dict[str, float], amount: float) -> dict[str, float]:
    """Smoothly blend two sparse ARKit control vectors."""
    amount = min(1.0, max(0.0, amount))
    eased = amount * amount * (3.0 - 2.0 * amount)
    keys = left.keys() | right.keys()
    return {
        key: round(left.get(key, 0.0) * (1.0 - eased) + right.get(key, 0.0) * eased, 4)
        for key in sorted(keys)
        if left.get(key, 0.0) * (1.0 - eased) + right.get(key, 0.0) * eased > 0.00005
    }


def compile_performance(
    phonemes: list[dict[str, Any]],
    *,
    audio_sha256: str,
    fps: int = DEFAULT_FPS,
    coarticulation_ms: int = DEFAULT_COARTICULATION_MS,
    voice_profile_id: str = VOICE_PROFILE_ID,
) -> dict[str, Any]:
    """Compile aligned ARPAbet events into a deterministic frame timeline.

    Each input event has ``phoneme``, ``start_s`` and ``end_s``. ``audio_sha256``
    binds the performance to the canonical Vera audio without carrying audio
    bytes through the compiler.
    """
    if voice_profile_id != VOICE_PROFILE_ID:
        raise ValueError(f"voice_profile_id must be canonical Vera profile {VOICE_PROFILE_ID!r}")
    if not isinstance(audio_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", audio_sha256):
        raise ValueError("audio_sha256 must be a 64-character SHA-256 digest")
    if isinstance(fps, bool) or not isinstance(fps, int) or not 1 <= fps <= 120:
        raise ValueError("fps must be an integer from 1 to 120")
    if isinstance(coarticulation_ms, bool) or not isinstance(coarticulation_ms, int) or not 0 <= coarticulation_ms <= 300:
        raise ValueError("coarticulation_ms must be an integer from 0 to 300")
    if not isinstance(phonemes, list) or not phonemes:
        raise ValueError("phonemes must be a non-empty list of aligned events")

    events: list[dict[str, Any]] = []
    previous_end = 0.0
    for index, raw in enumerate(phonemes):
        if not isinstance(raw, dict):
            raise ValueError(f"phonemes[{index}] must be an object")
        phoneme = _normalize_phoneme(raw.get("phoneme"))
        try:
            start_s, end_s = float(raw["start_s"]), float(raw["end_s"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"phonemes[{index}] requires numeric start_s and end_s") from exc
        if start_s < 0 or end_s <= start_s:
            raise ValueError(f"phonemes[{index}] must have 0 <= start_s < end_s")
        if index and start_s < previous_end - 1e-7:
            raise ValueError("phoneme events must be ordered and may not overlap")
        events.append({
            "phoneme": phoneme,
            "viseme": _viseme_for(phoneme),
            "start_s": start_s,
            "end_s": end_s,
        })
        previous_end = end_s

    duration_s = events[-1]["end_s"]
    frame_count = int(duration_s * fps) + 1
    starts = [event["start_s"] for event in events]
    half_transition_s = coarticulation_ms / 2000.0
    frames: list[dict[str, Any]] = []

    for frame_index in range(frame_count):
        time_s = frame_index / fps
        event_index = bisect_right(starts, time_s) - 1
        event = events[event_index] if event_index >= 0 else None
        if event is None or time_s >= event["end_s"]:
            active_viseme = "REST"
            controls: dict[str, float] = {}
            transition = None
        else:
            active_viseme = event["viseme"]
            controls = _shape(active_viseme)
            transition = None
            if half_transition_s > 0:
                previous = events[event_index - 1] if event_index > 0 else None
                following = events[event_index + 1] if event_index + 1 < len(events) else None
                # Blend across actual shared phoneme boundaries. Silence gaps
                # remain REST and do not cause a premature transition.
                start_contiguous = previous is not None and abs(previous["end_s"] - event["start_s"]) < 1e-4
                end_contiguous = following is not None and abs(event["end_s"] - following["start_s"]) < 1e-4
                if time_s < event["start_s"] + half_transition_s:
                    amount = (time_s - (event["start_s"] - half_transition_s)) / (2 * half_transition_s)
                    from_viseme = previous["viseme"] if start_contiguous else "REST"
                    controls = _mix(_shape(from_viseme), controls, amount)
                    transition = f"{from_viseme}->{active_viseme}"
                elif time_s >= event["end_s"] - half_transition_s:
                    amount = (time_s - (event["end_s"] - half_transition_s)) / (2 * half_transition_s)
                    to_viseme = following["viseme"] if end_contiguous else "REST"
                    controls = _mix(controls, _shape(to_viseme), amount)
                    transition = f"{active_viseme}->{to_viseme}"
        frames.append({
            "frame": frame_index,
            "time_s": round(time_s, 4),
            "viseme": active_viseme,
            "transition": transition,
            "blendshapes": controls,
        })

    return {
        "schema": "dio.vesper.performance.v1",
        "voice_profile_id": voice_profile_id,
        "audio_sha256": audio_sha256.lower(),
        "source_phoneme_count": len(events),
        "duration_s": round(duration_s, 4),
        "fps": fps,
        "coarticulation_ms": coarticulation_ms,
        "geometry_contract": "ComfyUI MediaPipe Face Landmarker v2 / ARKit-52 / lips mask",
        "frames": frames,
        "limitations": [
            "Phoneme alignment is supplied by an upstream aligner; this compiler does not infer speech timing.",
            "The ARKit-compatible profile is a renderer target, not a raster-image morph operation.",
            "TH/DH tongue placement is approximate because ARKit-52 has no tongue-out control.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON with audio_sha256 and phonemes[]")
    parser.add_argument("output", type=Path, help="Path for the compiled performance JSON")
    args = parser.parse_args()
    request = json.loads(args.input.read_text(encoding="utf-8"))
    result = compile_performance(
        request["phonemes"],
        audio_sha256=request["audio_sha256"],
        fps=request.get("fps", DEFAULT_FPS),
        coarticulation_ms=request.get("coarticulation_ms", DEFAULT_COARTICULATION_MS),
        voice_profile_id=request.get("voice_profile_id", VOICE_PROFILE_ID),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
