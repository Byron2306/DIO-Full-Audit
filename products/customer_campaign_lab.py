"""Customer source-bound brief execution for the held Campaign Lab pipeline."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{1,47}\Z")
_HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _field(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value.strip()


def build_campaign_lab_package(packet: Mapping[str, Any], output_dir: str | Path) -> dict[str, Any]:
    """Render a source-anchored multichannel campaign for customer review.

    Product, audience and proof statements must occur verbatim in the supplied
    brief source. An owner-supplied visual is required. This workflow renders
    campaign media, but it does not publish content or authorize advertising
    spend.
    """
    if packet.get("owner_authorized") is not True:
        raise ValueError("owner_authorized=true is required for customer-source processing")
    if packet.get("brand_rights_confirmed") is not True:
        raise ValueError("brand_rights_confirmed=true is required for the supplied image and brand")
    source_text = _field(packet.get("source_text"), "source_text")
    product_input = packet.get("product")
    audience_input = packet.get("audience")
    if not isinstance(product_input, Mapping) or not isinstance(audience_input, Mapping):
        raise ValueError("product and audience objects are required")

    product = dict(product_input)
    audience = dict(audience_input)
    for key in ("name", "short_name", "offer", "promise", "proof", "cta", "brand_owner"):
        product[key] = _field(product.get(key), f"product.{key}")
        if product[key] not in source_text:
            raise ValueError(f"product.{key} is not an exact statement in source_text")
    product["id"] = _field(product.get("id"), "product.id")
    for key in ("name", "pain", "outcome"):
        audience[key] = _field(audience.get(key), f"audience.{key}")
        if audience[key] not in source_text:
            raise ValueError(f"audience.{key} is not an exact statement in source_text")
    audience["id"] = _field(audience.get("id"), "audience.id")
    if not _IDENTIFIER.fullmatch(product["id"]) or not _IDENTIFIER.fullmatch(audience["id"]):
        raise ValueError("product and audience IDs must be safe identifiers")
    accent = str(product.get("accent") or "#c9a227")
    if not _HEX.fullmatch(accent):
        raise ValueError("product.accent must be a six-digit hex color")
    product["accent"] = accent
    product["landing_page"] = str(product.get("landing_page") or "")

    image_raw = Path(_field(packet.get("source_image_path"), "source_image_path")).expanduser().resolve()
    proof_raw = Path(_field(packet.get("proof_asset_path"), "proof_asset_path")).expanduser().resolve()
    if not image_raw.is_file() or not proof_raw.is_file():
        raise FileNotFoundError("source_image_path and proof_asset_path must identify supplied files")
    try:
        from PIL import Image

        with Image.open(image_raw) as image:
            image.verify()
    except Exception as exc:
        raise ValueError(f"source image is not a readable raster image: {exc}") from exc

    out = Path(output_dir).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("Campaign Lab output directory must be empty")
    out.mkdir(parents=True, exist_ok=True)
    sources = out / "customer_sources"
    sources.mkdir()
    proof_copy = sources / ("proof" + (proof_raw.suffix or ".txt"))
    image_copy = sources / ("brand_image" + (image_raw.suffix or ".png"))
    shutil.copyfile(proof_raw, proof_copy)
    shutil.copyfile(image_raw, image_copy)
    brief_path = sources / "customer_brief.txt"
    brief_path.write_text(source_text + "\n", encoding="utf-8")

    matrix = json.loads((ROOT / "config/marketing_audience_matrix.json").read_text(encoding="utf-8"))
    channel_ids = packet.get("channel_ids")
    if channel_ids is None:
        channels = matrix["channels"]
    else:
        if not isinstance(channel_ids, list) or not channel_ids or any(not isinstance(item, str) for item in channel_ids):
            raise ValueError("channel_ids must be a nonempty list of registered channel IDs")
        unknown = sorted(set(channel_ids) - set(matrix["channels"]))
        if unknown:
            raise ValueError(f"unregistered campaign channel IDs: {unknown}")
        channels = {key: matrix["channels"][key] for key in channel_ids}

    product.update({"source_image": str(image_copy), "proof_asset": str(proof_copy)})
    family_id = f"{product['id']}--{audience['id']}"
    from adapters.document_studio import local_media_compositor
    from scripts.build_multichannel_campaign_factory import build_family

    original_resolver = local_media_compositor.resolve_product_audience
    def resolve_customer_family(candidate_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if candidate_id == family_id:
            return product, audience
        return original_resolver(candidate_id)

    original_gamma = os.environ.get("DIO_GAMMA_VISUAL_CANDIDATE")
    local_media_compositor.resolve_product_audience = resolve_customer_family
    os.environ["DIO_GAMMA_VISUAL_CANDIDATE"] = "0"
    try:
        family = build_family(product, audience, channels, out, True)
    finally:
        local_media_compositor.resolve_product_audience = original_resolver
        if original_gamma is None:
            os.environ.pop("DIO_GAMMA_VISUAL_CANDIDATE", None)
        else:
            os.environ["DIO_GAMMA_VISUAL_CANDIDATE"] = original_gamma

    if (family.get("validation") or {}).get("state") != "passed":
        raise RuntimeError("Campaign Lab production validation failed: " + "; ".join((family.get("validation") or {}).get("errors") or []))
    governance = family.get("governance") or {}
    if governance.get("publication") != "held" or governance.get("spend") != "disabled":
        raise RuntimeError("Campaign Lab publication/spend gates changed")
    mp4s = sorted(out.rglob("*.mp4"))
    if len(mp4s) < 2 or any(not path.stat().st_size for path in mp4s):
        raise RuntimeError("Campaign Lab did not produce both nonempty video deliverables")

    # Keep a field-level trace from every customer-provided product/audience
    # statement to its exact span in the source brief. The model and creative
    # pipeline may transform those statements, so this records provenance; it
    # does not claim that every rendered claim is independently verified.
    bound_fields = []
    for namespace, values, keys in (
        ("product", product, ("name", "short_name", "offer", "promise", "proof", "cta", "brand_owner")),
        ("audience", audience, ("name", "pain", "outcome")),
    ):
        for key in keys:
            statement = values[key]
            start = source_text.find(statement)
            if start < 0:
                raise RuntimeError(f"Campaign Lab lost exact source binding for {namespace}.{key}")
            bound_fields.append({
                "field": f"{namespace}.{key}",
                "statement": statement,
                "source_start_utf8_character_offset": start,
                "source_end_utf8_character_offset": start + len(statement),
                "statement_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
                "source_text_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
                "binding": "EXACT_SUBSTRING_OF_CUSTOMER_SUPPLIED_BRIEF",
            })
    binding_path = out / "CUSTOMER_SOURCE_BINDINGS.json"
    binding_path.write_text(json.dumps({
        "schema": "dio.campaign_lab.customer_source_bindings.v1",
        "case_id": str(packet.get("case_id") or family_id),
        "source_text_path": str(brief_path.relative_to(out)),
        "source_text_sha256": _sha(brief_path),
        "bound_field_count": len(bound_fields),
        "fields": bound_fields,
        "interpretation": "Exact source presence is established; truth and market validity remain unverified.",
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    files = [{"path": str(path.relative_to(out)), "bytes": path.stat().st_size, "sha256": _sha(path)}
             for path in sorted(out.rglob("*")) if path.is_file()]
    receipt = {
        "schema": "dio.campaign_lab.customer_package.v1",
        "case_id": str(packet.get("case_id") or family_id),
        "source_text_sha256": _sha(brief_path),
        "source_image_sha256": _sha(image_copy),
        "proof_asset_sha256": _sha(proof_copy),
        "source_binding_receipt": str(binding_path.relative_to(out)),
        "source_binding_receipt_sha256": _sha(binding_path),
        "customer_family": family,
        "artifact_count": len(files),
        "artifacts": files,
        "rendered_video_count": len(mp4s),
        "human_review_required": True,
        "publication_authorized": False,
        "spend_authorized": False,
        "market_validation_claimed": False,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
        "synthetic_acceptance_case": packet.get("synthetic_acceptance_not_customer_evidence") is True,
    }
    (out / "CAMPAIGN_LAB_CUSTOMER_RECEIPT.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt
