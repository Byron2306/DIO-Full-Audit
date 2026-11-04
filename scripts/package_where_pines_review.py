"""Package the existing Sonoris physical render for a local listening review."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "media/sonoris/releases/black_metal_where_pines_forget_v3"
SOURCE = OUT / "WHERE_THE_PINES_FORGET_PHYSICAL_V3.wav"
MASTER = OUT / "WHERE_THE_PINES_FORGET_REVIEW_MASTER_V4.wav"
MP3 = OUT / "WHERE_THE_PINES_FORGET_REVIEW_MASTER_V4.mp3"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan = json.loads((OUT / "SONORIS_GOVERNED_COMPOSITION_PLAN.json").read_text())
    performance = json.loads((OUT / "SONORIS_PHYSICAL_PERFORMANCE_PLAN.json").read_text())
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(SOURCE),
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=8:linear=true", "-ar", "48000",
                    "-c:a", "pcm_s24le", str(MASTER)], check=True)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(MASTER),
                    "-c:a", "libmp3lame", "-b:a", "256k", "-metadata", "title=Where the Pines Forget",
                    "-metadata", "artist=DIO Sonoris", str(MP3)], check=True)
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=sample_rate,channels", "-of", "json", str(MASTER)]))
    loudness = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(MASTER),
        "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True,
        text=True, check=True).stderr.rsplit("Summary:", 1)[-1]
    integrated = re.search(r"\bI:\s*([-\d.]+) LUFS", loudness)
    true_peak = re.search(r"\bPeak:\s*([-\d.]+) dBFS", loudness)
    if not integrated or not true_peak:
        raise RuntimeError("Could not measure packaged master loudness")
    receipt = {
        "schema": "dio.sonoris.local_listening_review.v4",
        "title": "Where the Pines Forget",
        "genre_intent": plan["grammar"]["primary"]["id"],
        "composition": {"tempo_bpm": plan["musical_frame"]["tempo_bpm"],
                        "meter": plan["musical_frame"]["meter"],
                        "tonal_center": plan["musical_frame"]["tonal_center"],
                        "sections": [{"name": s["section"], "gesture": s["gesture"], "bars": s["bars"]}
                                     for s in plan["sections"]]},
        "performance_plan_schema": performance.get("schema"),
        "mastering": {"target_integrated_lufs": -16, "true_peak_ceiling_dbfs": -1.5,
                       "loudness_range_lu": 8, "source_preserved": True},
        "audio_probe": probe,
        "measured_master": {"integrated_lufs": float(integrated.group(1)),
                            "true_peak_dbfs": float(true_peak.group(1))},
        "artifacts": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p), "bytes": p.stat().st_size}
                      for p in (SOURCE, MASTER, MP3)],
        "rights": {"metal_gtx": "UNVERIFIED", "commercial_release": "HELD"},
        "human_listening_review": "REQUIRED",
        "release_authorized": False,
    }
    (OUT / "SONORIS_LOCAL_REVIEW_RECEIPT_V4.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"master": str(MASTER), "preview": str(MP3), "receipt": str(OUT / "SONORIS_LOCAL_REVIEW_RECEIPT_V4.json")}))


if __name__ == "__main__":
    main()
