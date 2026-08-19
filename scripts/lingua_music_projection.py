from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FOUNDRY = Path(os.environ.get("NICHEFOUNDRY_ROOT", "/home/byron/Downloads/NicheFoundry_Phase11"))


def _tokens(value: Any) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", str(value or "").casefold()) if len(token) > 2}


def _slug(value: str) -> str:
    return "-".join(part for part in re.sub(r"[^a-z0-9]+", "-", value.casefold()).split("-") if part)[:100] or "projection"


def _catalog() -> list[dict[str, Any]]:
    episodes = FOUNDRY / "episodes"
    if not episodes.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for receipt_path in sorted(episodes.glob("*/imports/music_choices/COMMERCIAL_MUSIC_RECEIPT.json")):
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        selected = receipt.get("selected") or {}
        rights = selected.get("rights") or {}
        if rights.get("passed") is not True and not selected.get("licence_name"):
            continue
        episode = receipt_path.parents[2]
        promoted = str(selected.get("promoted_path") or "").strip()
        audio = (episode / promoted).resolve() if promoted and (episode / promoted).is_file() else None
        if audio is None:
            for extension in ("ogg", "mp3", "wav", "m4a"):
                candidate = episode / "imports" / f"music_bed.{extension}"
                if candidate.is_file():
                    audio = candidate.resolve()
                    break
        attribution = episode / "imports" / "MUSIC_ATTRIBUTION.md"
        if not audio or not attribution.is_file():
            continue
        metadata = " ".join(
            str(value or "")
            for value in (
                receipt.get("topic"),
                receipt.get("studio"),
                selected.get("title"),
                selected.get("artist"),
                selected.get("attribution"),
            )
        )
        rows.append(
            {
                "path": audio,
                "attribution": attribution.resolve(),
                "receipt": receipt_path.resolve(),
                "metadata": metadata,
                "title": selected.get("title"),
                "artist": selected.get("artist"),
                "licence": selected.get("licence_name"),
            }
        )
    return rows


def _fresh_projection_music(
    *,
    plan: dict[str, Any],
    product: dict[str, Any],
    audience: dict[str, Any],
    family_id: str,
    surface_plan: dict[str, Any],
) -> dict[str, Any] | None:
    source_script = FOUNDRY / "scripts" / "source_commercial_music.js"
    studio = FOUNDRY / "studios" / "builtin" / "practical_open_source.json"
    if not source_script.is_file() or not studio.is_file():
        return None

    cache = ROOT / "state" / "marketing_music_cache" / _slug(family_id) / _slug(str(surface_plan.get("arc_family") or "media"))
    cache.mkdir(parents=True, exist_ok=True)
    query = " ".join(
        part
        for part in (
            str(plan.get("family") or ""),
            " ".join(str(item) for item in plan.get("keywords") or []),
            str(product.get("name") or ""),
            str(audience.get("name") or ""),
            str(audience.get("outcome") or ""),
        )
        if part
    )
    completed = subprocess.run(
        [
            "node",
            str(source_script),
            "--episode",
            str(cache),
            "--studio",
            "practical_open_source",
            "--topic",
            query,
            "--limit",
            "5",
            "--select",
            "1",
            "--provider",
            "openverse",
        ],
        cwd=FOUNDRY,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if completed.returncode != 0:
        return None

    receipt_path = cache / "imports" / "music_choices" / "COMMERCIAL_MUSIC_RECEIPT.json"
    attribution = cache / "imports" / "MUSIC_ATTRIBUTION.md"
    if not receipt_path.is_file() or not attribution.is_file():
        return None
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    selected = receipt.get("selected") or {}
    promoted = str(selected.get("promoted_path") or "").strip()
    music = cache / promoted if promoted else None
    if not music or not music.is_file():
        return None
    rights = selected.get("rights") or {}
    if rights.get("passed") is not True and not selected.get("licence_name"):
        return None
    return {
        **plan,
        "mode": "rights_recorded",
        "path": str(music.resolve()),
        "attribution": str(attribution.resolve()),
        "rights_receipt": str(receipt_path.resolve()),
        "title": selected.get("title"),
        "artist": selected.get("artist"),
        "licence": selected.get("licence_name"),
        "selection_basis": "fresh_audience_projection_openverse_search",
        "match_score": None,
        "search_query": query,
    }


def select_projection_music(surface_plan: dict[str, Any], product: dict[str, Any], audience: dict[str, Any], family_id: str) -> dict[str, Any]:
    """Choose music from semantic fit, source a fresh cleared track, or intentionally use silence.

    Zero-score catalog matches are deliberately NOT used. That is the anti-corporate-sausage rule:
    an available track is not automatically an appropriate track.
    """
    plan = dict(surface_plan["music"])
    explicit = str(os.environ.get("DIO_CAMPAIGN_MUSIC") or "").strip()
    explicit_attr = str(os.environ.get("DIO_CAMPAIGN_MUSIC_ATTRIBUTION") or "").strip()
    if explicit and explicit_attr:
        music = Path(explicit).expanduser().resolve()
        attribution = Path(explicit_attr).expanduser().resolve()
        if music.is_file() and attribution.is_file():
            return {
                **plan,
                "mode": "rights_recorded",
                "path": str(music),
                "attribution": str(attribution),
                "selection_basis": "operator_environment_override",
            }

    wanted = _tokens(
        " ".join(
            [
                str(plan.get("family") or ""),
                " ".join(str(item) for item in plan.get("keywords") or []),
                str(product.get("name") or ""),
                str(audience.get("name") or ""),
                str(audience.get("pain") or ""),
                str(audience.get("outcome") or ""),
            ]
        )
    )
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for row in _catalog():
        score = len(wanted & _tokens(row["metadata"]))
        tie = hashlib.sha256(f"{family_id}:{surface_plan.get('arc_family')}:{row['path']}".encode("utf-8")).hexdigest()
        scored.append((score, tie, row))
    if scored:
        score, _tie, row = max(scored, key=lambda item: (item[0], item[1]))
        if score > 0:
            return {
                **plan,
                "mode": "rights_recorded",
                "path": str(row["path"]),
                "attribution": str(row["attribution"]),
                "rights_receipt": str(row["receipt"]),
                "title": row["title"],
                "artist": row["artist"],
                "licence": row["licence"],
                "selection_basis": "audience_projection_catalog_match",
                "match_score": score,
            }

    sourced = _fresh_projection_music(
        plan=plan,
        product=product,
        audience=audience,
        family_id=family_id,
        surface_plan=surface_plan,
    )
    if sourced:
        return sourced

    if plan.get("allow_silence") is True:
        return {
            **plan,
            "mode": "none",
            "path": "",
            "attribution": "",
            "selection_basis": "intentional_silence_no_semantically_matched_cleared_track",
        }
    raise RuntimeError("LINGUA projection requires an appropriate rights-recorded music asset, and none could be selected or sourced.")
