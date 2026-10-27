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


class MusicSourceUnavailable(RuntimeError):
    """The external music source could not be reached; this is not a rights verdict."""


def _tokens(value: Any) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", str(value or "").casefold()) if len(token) > 2}


def _slug(value: str) -> str:
    return "-".join(part for part in re.sub(r"[^a-z0-9]+", "-", value.casefold()).split("-") if part)[:100] or "projection"


def _catalog() -> list[dict[str, Any]]:
    catalog_path = ROOT / "config" / "media" / "music_catalog.json"
    rows: list[dict[str, Any]] = []
    if catalog_path.is_file():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"DIO music catalog is unreadable: {catalog_path}") from exc
        for track in catalog.get("tracks") or []:
            music = (ROOT / str(track.get("path") or "")).resolve()
            attribution = (ROOT / str(track.get("attribution") or "")).resolve()
            receipt = (ROOT / str(track.get("rights_receipt") or "")).resolve()
            if not all(path.is_relative_to(ROOT) for path in (music, attribution, receipt)):
                raise RuntimeError("DIO music catalog path escapes the repository.")
            if not music.is_file() or not attribution.is_file() or not receipt.is_file():
                continue
            rights = track.get("rights") or {}
            if not rights.get("commercial_use") or not rights.get("adaptation_allowed") or not rights.get("attribution_required"):
                continue
            if _file_sha256(music) != track.get("sha256"):
                raise RuntimeError(f"DIO music catalog hash mismatch: {track.get('id')}")
            rows.append({
                "path": music,
                "attribution": attribution,
                "receipt": receipt,
                "metadata": track.get("metadata") or "",
                "title": track.get("title"),
                "artist": track.get("artist"),
                "licence": track.get("licence_name"),
            })
    episodes = FOUNDRY / "episodes"
    if not episodes.is_dir():
        return rows
    for receipt_path in sorted(episodes.glob("*/imports/music_choices/COMMERCIAL_MUSIC_RECEIPT.json")):
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        selected = receipt.get("selected") or {}
        rights = selected.get("rights") or {}
        if rights.get("passed") is not True:
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


def _projection_music_query(plan: dict[str, Any], product: dict[str, Any], audience: dict[str, Any]) -> str:
    return " ".join(
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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cached_projection_music(
    *, plan: dict[str, Any], product: dict[str, Any], audience: dict[str, Any], family_id: str,
) -> dict[str, Any] | None:
    """Reuse a byte-verified, cleared track for this exact family and sourcing context."""
    cache_root = (ROOT / "state" / "marketing_music_cache").resolve()
    family_root = (cache_root / _slug(family_id)).resolve()
    if family_root.parent != cache_root or not family_root.is_dir():
        return None
    query = _projection_music_query(plan, product, audience)
    for receipt_path in sorted(family_root.glob("*/imports/music_choices/COMMERCIAL_MUSIC_RECEIPT.json")):
        try:
            if not receipt_path.resolve().is_relative_to(family_root):
                continue
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if not isinstance(receipt, dict) or receipt.get("schema") != "nichefoundry.commercial_music_selection.v1" or receipt.get("topic") != query:
                continue
            selected = receipt.get("selected")
            if not isinstance(selected, dict) or not isinstance(selected.get("rights"), dict) or selected["rights"].get("passed") is not True:
                continue
            promoted = str(selected.get("promoted_path") or "").strip()
            if not promoted or Path(promoted).is_absolute():
                continue
            episode = receipt_path.parents[2].resolve()
            music = (episode / promoted).resolve()
            attribution = (episode / "imports" / "MUSIC_ATTRIBUTION.md").resolve()
            if not music.is_relative_to(episode) or not attribution.is_relative_to(episode):
                continue
            if not music.is_file() or not attribution.is_file() or music.stat().st_size == 0 or attribution.stat().st_size == 0:
                continue
            music_sha = _file_sha256(music)
            if music_sha != selected.get("sha256"):
                continue
            return {
                **plan,
                "mode": "rights_recorded",
                "path": str(music),
                "attribution": str(attribution),
                "rights_receipt": str(receipt_path.resolve()),
                "title": selected.get("title"),
                "artist": selected.get("artist"),
                "licence": selected.get("licence_name"),
                "selection_basis": "exact_audience_projection_cache_match",
                "search_query": query,
                "music_sha256": music_sha,
                "rights_receipt_sha256": _file_sha256(receipt_path),
                "attribution_sha256": _file_sha256(attribution),
            }
        except (OSError, json.JSONDecodeError):
            continue
    return None


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
    query = _projection_music_query(plan, product, audience)
    path_entries = [
        str(Path.home() / ".local" / "bin"),
        str(Path.home() / "bin"),
        os.environ.get("PATH", ""),
    ]
    source_env = {
        **os.environ,
        "PATH": os.pathsep.join(entry for entry in path_entries if entry),
    }
    try:
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
            env=source_env,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired as exc:
        raise MusicSourceUnavailable("NicheFoundry music source unavailable: sourcing request timed out.") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "music source command failed").strip()[-2400:]
        if "No commercially reusable music found." in detail:
            return None
        if "TypeError: fetch failed" in detail:
            raise MusicSourceUnavailable("NicheFoundry music source unavailable: network fetch failed.")
        raise RuntimeError(f"NicheFoundry commercial music sourcing failed: {detail}")

    receipt_path = cache / "imports" / "music_choices" / "COMMERCIAL_MUSIC_RECEIPT.json"
    attribution = cache / "imports" / "MUSIC_ATTRIBUTION.md"
    if not receipt_path.is_file() or not attribution.is_file():
        raise RuntimeError("NicheFoundry music sourcing completed without its rights receipt and attribution.")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"NicheFoundry music rights receipt is unreadable: {receipt_path}") from exc
    selected = receipt.get("selected") or {}
    promoted = str(selected.get("promoted_path") or "").strip()
    music = cache / promoted if promoted else None
    if not music or not music.is_file():
        raise RuntimeError("NicheFoundry music receipt does not reference an existing promoted track.")
    rights = selected.get("rights") or {}
    if rights.get("passed") is not True:
        raise RuntimeError("NicheFoundry selected track did not pass the commercial-use rights gate.")
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
    """Select verified, pinned local music for canonical production marketing."""
    from products.canonical_marketing_media import approved_music
    plan = dict(surface_plan["music"])
    explicit = str(os.environ.get("DIO_CAMPAIGN_MUSIC") or "").strip()
    selected = approved_music(root=ROOT)
    if explicit and Path(explicit).expanduser().resolve() != Path(selected["path"]):
        raise ValueError("DIO_CAMPAIGN_MUSIC must select canonical music with verified rights")
    return {**plan, **selected}
