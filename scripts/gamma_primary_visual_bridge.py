from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from scripts import nichefoundry_visual_spine as spine


TRUTHY = {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return str(os.environ.get("DIO_GAMMA_VISUAL_CANDIDATE") or "0").strip().casefold() in TRUTHY


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _gamma_cards(variant: dict[str, Any], scene_count: int) -> list[Path]:
    if not _enabled():
        return []
    gamma = dict(variant.get("gamma") or {})
    receipt_path = Path(str(gamma.get("receipt") or "")).expanduser()
    if not receipt_path.is_file():
        return []
    receipt = _read_json(receipt_path)
    if receipt.get("state") != "ready":
        return []
    if gamma.get("request_hash") and receipt.get("request_hash") != gamma.get("request_hash"):
        return []
    cards = list(receipt.get("cards") or [])
    if len(cards) != scene_count:
        return []
    paths = [Path(str(card.get("path") or "")).expanduser().resolve() for card in cards]
    if any(not path.is_file() for path in paths):
        return []
    return paths


def install_gamma_primary_visual_bridge(factory_module: Any) -> None:
    """Prefer art-directed Gamma scene cards when the operator enables them.

    Document Studio remains the semantic/art-direction authority. Gamma is only a
    representational executor and never receives publication, spend or market-
    validation authority. If Gamma is unavailable or stale, the governed local
    compositor remains the non-blocking fallback.
    """
    if getattr(factory_module, "_dio_gamma_primary_visual_bridge_installed", False):
        return

    original_scene_images = spine._local_scene_images
    original_renderer = spine.render_art_directed_campaign_media
    original_build_family = factory_module.build_family

    def selected_scene_images(variant: dict[str, Any], scene_count: int) -> list[Path]:
        cards = _gamma_cards(variant, scene_count)
        if cards:
            return cards
        return original_scene_images(variant, scene_count)

    def render_with_truthful_visual_source(
        request_path: Path,
        *,
        nichefoundry_root: Path | None = None,
    ) -> dict[str, Any]:
        request = _read_json(request_path)
        selected_by_surface: dict[str, str] = {}
        for surface, variant in dict(request.get("variants") or {}).items():
            scene_count = len(list((variant.get("story") or {}).get("scenes") or []))
            selected_by_surface[surface] = (
                "gamma_art_directed_candidate"
                if _gamma_cards(dict(variant), scene_count)
                else "document_studio_local_compositor"
            )

        receipt = original_renderer(request_path, nichefoundry_root=nichefoundry_root)
        variants = dict(receipt.get("variants") or {})
        for surface, row in variants.items():
            source = selected_by_surface.get(surface, "document_studio_local_compositor")
            visual_source = dict(row.get("visual_source") or {})
            visual_source["selected"] = source
            visual_source["document_studio_art_direction_bound"] = True
            visual_source["local_compositor_fallback_available"] = True
            visual_source["gamma_selected"] = source == "gamma_art_directed_candidate"
            row["visual_source"] = visual_source

        gamma_selected = any(value == "gamma_art_directed_candidate" for value in selected_by_surface.values())
        governance = dict(receipt.get("governance") or {})
        governance["document_studio_local_compositor_primary"] = not gamma_selected
        governance["document_studio_local_compositor_fallback"] = True
        governance["gamma_selected_for_visuals"] = gamma_selected
        governance["gamma_required_for_media"] = False
        governance["publication"] = "held_for_operator_approval"
        governance["spend"] = "disabled"
        governance["market_validation_claimed"] = False
        governance["authority_created"] = False
        receipt["governance"] = governance

        qa = dict(receipt.get("document_studio_visual_qa") or {})
        qa["selected_visual_source_by_surface"] = selected_by_surface
        qa["local_compositor_primary"] = not gamma_selected
        qa["local_compositor_fallback_available"] = True
        qa["gamma_required_for_media"] = False
        receipt["document_studio_visual_qa"] = qa
        receipt["selected_visual_source_by_surface"] = selected_by_surface

        receipt_path = request_path.parent / "media" / "CAMPAIGN_MEDIA_RECEIPT.json"
        _write_json(receipt_path, receipt)
        return receipt

    def build_family(
        product: dict[str, Any],
        audience: dict[str, Any],
        channels: dict[str, Any],
        output_root: Path,
        render_reels: bool,
    ) -> dict[str, Any]:
        family = original_build_family(product, audience, channels, output_root, render_reels)
        if not render_reels:
            return family

        directory = output_root / factory_module.slug(product["id"]) / factory_module.slug(audience["id"])
        receipt_path = directory / "media" / "CAMPAIGN_MEDIA_RECEIPT.json"
        receipt = _read_json(receipt_path)
        selected = dict(receipt.get("selected_visual_source_by_surface") or {})
        gamma_selected = any(value == "gamma_art_directed_candidate" for value in selected.values())

        pipeline = dict(family.get("visual_pipeline") or {})
        pipeline["primary_compositor"] = (
            "gamma_art_directed_candidate" if gamma_selected else "document_studio_local_compositor"
        )
        pipeline["selected_visual_source_by_surface"] = selected
        pipeline["document_studio_art_direction_bound"] = True
        pipeline["local_compositor_fallback_available"] = True
        pipeline["gamma_required_for_media"] = False
        pipeline["human_visual_release"] = "NEEDS_YOU"
        family["visual_pipeline"] = pipeline

        gamma = dict(family.get("gamma") or {})
        gamma["selected_for_media"] = gamma_selected
        gamma["required_for_media"] = False
        family["gamma"] = gamma

        governance = dict(family.get("governance") or {})
        governance["document_studio_local_compositor_primary"] = not gamma_selected
        governance["document_studio_local_compositor_fallback"] = True
        governance["gamma_selected_for_visuals"] = gamma_selected
        governance["gamma_required_for_media"] = False
        governance["human_visual_release"] = "NEEDS_YOU"
        family["governance"] = governance

        factory_module.write_json(directory / "FAMILY.json", family)
        return family

    spine._local_scene_images = selected_scene_images
    spine.render_art_directed_campaign_media = render_with_truthful_visual_source
    factory_module.build_family = build_family
    factory_module._dio_gamma_primary_visual_bridge_installed = True
