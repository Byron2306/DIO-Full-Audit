from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


PHOTO_KINDS = {"curated_photo", "generated_editorial"}
DEFAULT_MAX_EDGE = 1920
DEFAULT_WEBP_QUALITY = 82
MAX_EMBEDDED_BYTES = 3_000_000


class VisualMaterialOptimizerError(RuntimeError):
    pass


def optimize_visual_material(
    source: Path,
    destination: Path,
    *,
    material_kind: str,
    max_edge: int = DEFAULT_MAX_EDGE,
    quality: int = DEFAULT_WEBP_QUALITY,
) -> dict:
    """Create a bounded customer-web payload for photo-like material.

    Non-photo material is copied byte-for-byte. Curated/generated photography is
    converted to WebP through ffmpeg with no upscaling beyond the source edge.
    """
    source = source.resolve()
    if not source.is_file():
        raise VisualMaterialOptimizerError(f"source material does not exist: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    if material_kind not in PHOTO_KINDS:
        shutil.copy2(source, destination)
        if destination.stat().st_size > MAX_EMBEDDED_BYTES:
            raise VisualMaterialOptimizerError(
                f"non-photo visual material exceeds {MAX_EMBEDDED_BYTES} bytes; prepare a smaller customer projection first"
            )
        return {
            "optimized": False,
            "path": destination,
            "bytes": destination.stat().st_size,
            "format": destination.suffix.casefold().lstrip("."),
            "max_edge": None,
            "quality": None,
        }

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise VisualMaterialOptimizerError("ffmpeg is required to optimize photo-like visual material")
    if max_edge < 640 or max_edge > 4096:
        raise VisualMaterialOptimizerError("max_edge must be between 640 and 4096")
    if quality < 40 or quality > 100:
        raise VisualMaterialOptimizerError("quality must be between 40 and 100")

    target = destination.with_suffix(".webp")
    filter_expr = f"scale='min({max_edge},iw)':'min({max_edge},ih)':force_original_aspect_ratio=decrease"
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            filter_expr,
            "-frames:v",
            "1",
            "-c:v",
            "libwebp",
            "-quality",
            str(quality),
            "-compression_level",
            "6",
            str(target),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0 or not target.is_file():
        raise VisualMaterialOptimizerError("ffmpeg photo optimization failed: " + result.stderr.strip()[:1200])
    if target.stat().st_size > MAX_EMBEDDED_BYTES:
        target.unlink(missing_ok=True)
        raise VisualMaterialOptimizerError(
            f"optimized visual material still exceeds {MAX_EMBEDDED_BYTES} bytes; use a tighter crop or lower-resolution source"
        )
    return {
        "optimized": True,
        "path": target,
        "bytes": target.stat().st_size,
        "format": "webp",
        "max_edge": max_edge,
        "quality": quality,
    }


__all__ = [
    "DEFAULT_MAX_EDGE",
    "DEFAULT_WEBP_QUALITY",
    "MAX_EMBEDDED_BYTES",
    "PHOTO_KINDS",
    "VisualMaterialOptimizerError",
    "optimize_visual_material",
]
