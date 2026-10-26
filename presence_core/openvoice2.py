from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def convert_tone_color(
    *,
    source_wav: Path,
    output_wav: Path,
    converter_dir: Path,
    target_embedding: Path,
    device: str | None = None,
    watermark: str = "@DIO-Vesper",
) -> dict[str, Any]:
    """Apply a consented/reviewed OpenVoice V2 tone identity to existing speech.

    The source speech must already contain the approved words. OpenVoice is a rendering layer only;
    it does not translate, choose copy, create send authority or establish identity authority.
    """
    try:
        import torch
        from openvoice.api import ToneColorConverter
    except Exception as exc:  # pragma: no cover - dependency is optional in CI
        raise RuntimeError(f"OpenVoice2 dependencies unavailable: {exc}") from exc

    source_wav = Path(source_wav)
    output_wav = Path(output_wav)
    converter_dir = Path(converter_dir)
    target_embedding = Path(target_embedding)
    for required in (source_wav, converter_dir / "config.json", converter_dir / "checkpoint.pth", target_embedding):
        if not required.exists():
            raise FileNotFoundError(str(required))

    resolved_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    converter = ToneColorConverter(str(converter_dir / "config.json"), device=resolved_device)
    converter.load_ckpt(str(converter_dir / "checkpoint.pth"))
    target_se = torch.load(target_embedding, map_location=resolved_device)
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    converter.convert(
        audio_src_path=str(source_wav),
        src_se=None,
        tgt_se=target_se,
        output_path=str(output_wav),
        message=watermark,
    )
    if not output_wav.exists() or output_wav.stat().st_size < 44:
        raise RuntimeError("OpenVoice2 did not produce a usable WAV")
    return {
        "schema": "dio.vesper.openvoice2_render_receipt.v1",
        "rendered_at": _now(),
        "device": resolved_device,
        "source_audio_sha256": _sha256(source_wav),
        "target_embedding_sha256": _sha256(target_embedding),
        "output_audio_sha256": _sha256(output_wav),
        "output_path": str(output_wav),
        "output_bytes": output_wav.stat().st_size,
        "watermark": watermark,
        "semantic_text_changed": False,
        "translation_performed": False,
        "external_action_executed": False,
        "send_authorized": False,
        "identity_authority_created": False,
        "consent_provenance_required": True,
    }
