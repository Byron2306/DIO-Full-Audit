#!/usr/bin/env python3
"""Materialize every researched Sonoris song type as an auditable MIDI candidate."""
from __future__ import annotations

import json
import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from products.sonoris_song_engine import SEED_ROOT, compile_song, render_song, studio_catalog
from products.sonoris_genre_compiler import _read_catalog, compile_composition_request

MODULE_DEFAULTS = {
    genre: row.get("default_modules") or {}
    for genre, row in studio_catalog().get("genres", {}).items()
}


def expected_seed_modules(genre: str, song_type: str | None) -> dict[str, str]:
    """Return catalog defaults plus intentional per-variant role choices."""
    expected = dict(MODULE_DEFAULTS.get(genre, {}))
    if genre == "folk_metal":
        expected["folk"] = {"drive": "bagpipe_sampled", "space": "flute_sampled", "fracture": "accordion_sampled"}.get(song_type or "drive", "bagpipe_sampled")
    if genre == "synthwave" and song_type == "dark_aggro":
        expected["keys"] = "native_aggro_triple_saw"
    return expected


def refresh_if_stale(job_id: str, receipt_file: Path, *, refresh: bool) -> dict | None:
    if not receipt_file.is_file():
        return None
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    request = {"genre": receipt["genre"], "song_type": receipt.get("song_type")}
    if receipt["genre"] == "black_metal":
        request["bars"] = {"drive": 88, "space": 96, "fracture": 104}.get(receipt.get("song_type"), 88)
    if receipt["genre"] == "synthwave" and receipt.get("song_type") == "dark_aggro":
        request["bars"] = int(receipt["bars"])
    expected = compile_composition_request(request)["musical_frame"]
    if receipt["genre"] == "synthwave" and receipt.get("song_type") == "dark_aggro":
        expected["tempo_bpm"] = 129  # Dedicated Dark Aggro blueprint, not the catalog's generic synthwave tempo.
    current = (receipt.get("tempo_bpm"), receipt.get("meter"), receipt.get("bars"))
    wanted = (expected["tempo_bpm"], expected["meter"], expected["bars"])
    expected_modules = expected_seed_modules(receipt["genre"], receipt.get("song_type"))
    current_modules = receipt.get("modules") or {}
    modules_stale = any(current_modules.get(role) != module for role, module in expected_modules.items())
    frame_stale = current != wanted
    if not (frame_stale or modules_stale) or not refresh:
        return receipt

    archive = SEED_ROOT / "_catalog_revisions" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") / job_id
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(receipt_file.parent), str(archive))
    regenerate = {"genre": receipt["genre"], "song_type": receipt.get("song_type"),
                  "title": receipt.get("title"), "seed": receipt.get("seed", 2306)}
    if modules_stale:
        # Preserve the exact role configuration in the receipt, applying only
        # catalog updates that are actually stale. This keeps variant-specific
        # instruments such as folk-metal flute/accordion intact.
        regenerate["modules"] = expected_modules
    if receipt["genre"] == "black_metal":
        regenerate["bars"] = int(expected["bars"])
    if receipt["genre"] == "synthwave" and receipt.get("song_type") == "dark_aggro":
        regenerate["bars"] = int(receipt["bars"])
    compile_song(regenerate, output_root=SEED_ROOT, job_id=job_id)
    updated = render_song(job_id, output_root=SEED_ROOT)
    details = []
    if frame_stale:
        details.append(f"frame {current} -> {wanted}")
    if modules_stale:
        details.append("genre instrument defaults refreshed")
    print(f"Refreshed stale {job_id}: {'; '.join(details)}; previous artifacts archived at {archive}")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-stale", action="store_true", help="archive and recompile catalog seeds whose musical frame changed")
    args = parser.parse_args()
    SEED_ROOT.mkdir(parents=True, exist_ok=True)
    rows = []
    for genre, profile in sorted(_read_catalog()["profiles"].items()):
        for variant in profile.get("song_types") or []:
            job_id = f"seed_{genre}_{variant['key']}"
            receipt_file = SEED_ROOT / job_id / "SONORIS_STUDIO_RECEIPT.json"
            if receipt_file.exists():
                receipt = refresh_if_stale(job_id, receipt_file, refresh=args.refresh_stale)
            else:
                request = {"genre": genre, "song_type": variant["key"],
                           "title": f"{profile['label']} — {variant['label']}",
                           "seed": 2306 + len(rows) * 37}
                if genre == "synthwave" and variant["key"] == "dark_aggro":
                    request["bars"] = 48
                receipt = compile_song(request, output_root=SEED_ROOT, job_id=job_id)
            rows.append({key: receipt[key] for key in ("job_id", "genre", "song_type", "title", "tempo_bpm", "meter", "bars", "midi_sha256", "audio_state")})
    # These focused candidates exercise two under-served grammars: Ambient
    # needs long fields without a forced kit, and Fusion needs swing/modal/odd
    # meter versions that remain inspectable beside the baseline catalogue.
    focused = [
        ("ambient", None, "ambient_field_v1", "Ambient • Slowly shifting field", 57101),
        ("jazz_fusion", "drive", "jazz_fusion_electric_pocket_v1", "Jazz Fusion • Electric pocket", 57102),
        ("jazz_fusion", "space", "jazz_fusion_modal_glide_v1", "Jazz Fusion • Modal glide", 57103),
        ("jazz_fusion", "fracture", "jazz_fusion_odd_meter_exchange_v1", "Jazz Fusion • Odd meter exchange", 57104),
    ]
    for genre, song_type, job_id, title, seed in focused:
        receipt_file = SEED_ROOT / job_id / "SONORIS_STUDIO_RECEIPT.json"
        if receipt_file.exists():
            receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
        else:
            request = {"genre": genre, "title": title, "seed": seed, "mood": "genre grammar study"}
            if song_type:
                request["song_type"] = song_type
            receipt = compile_song(request, output_root=SEED_ROOT, job_id=job_id)
        rows.append({key: receipt[key] for key in ("job_id", "genre", "song_type", "title", "tempo_bpm", "meter", "bars", "midi_sha256", "audio_state")})
    known_jobs = {row["job_id"] for row in rows}
    for receipt_file in sorted(SEED_ROOT.glob("*/SONORIS_STUDIO_RECEIPT.json")):
        receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
        if receipt.get("job_id") in known_jobs:
            continue
        rows.append({key: receipt.get(key) for key in ("job_id", "genre", "song_type", "title", "tempo_bpm", "meter", "bars", "midi_sha256", "audio_state")})
        known_jobs.add(receipt["job_id"])
    manifest = {"schema": "dio.sonoris.genre_seed_library.v2", "song_count": len(rows),
                "genre_count": len({row["genre"] for row in rows}), "songs": rows,
                "claim_boundary": "Original algorithmic MIDI sketches; genre quality and rights require listening and review."}
    (SEED_ROOT / "LIBRARY_MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(f"Seeded {len(rows)} song types across {manifest['genre_count']} genres in {SEED_ROOT}")


if __name__ == "__main__":
    main()
