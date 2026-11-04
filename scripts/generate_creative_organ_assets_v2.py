#!/usr/bin/env python3
"""One revised Pictora attempt using the general SD 1.5 checkpoint for object-focused art."""
from __future__ import annotations
import importlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
base = importlib.import_module("scripts.generate_creative_organ_assets")
base.PACK = base.ROOT / "media/product_asset_packs/dio_creative_organs_v2"
base.CHECKPOINT = "v1-5-pruned-emaonly.safetensors"
base.BRIEFS = [
    {
        "id": "sonoris", "seed": 2026102821,
        "filename": "SONORIS_MUSICAL_MORPHOLOGY_HERO_V2.png",
        "prompt": (
            "Wide landscape technology product illustration, abstract instrument sculpture only, absolutely no humans, "
            "no faces, no bodies, no portraits, no hands. On a near-black obsidian ground, a beautiful precise gold "
            "orbital mechanism combines a small electric piano keyboard, analog synthesizer oscillator, curved saxophone "
            "bell, silver flute and violin strings as one coherent musical machine. Thin luminous gold strings become "
            "a rising sound-wave gesture, grounded by a circular bass pulse and cymbal-like rings. Premium DIO website "
            "art direction: restrained gold filaments, deep black space, one bright focal point, elegant and legible "
            "silhouette, crafted instrument design, cinematic wide hero image. No readable text, no letters, no logo, no watermark."
        )
    },
    {
        "id": "pictora", "seed": 2026102822,
        "filename": "PICTORA_LOCAL_IMAGE_FORGE_HERO_V2.png",
        "prompt": (
            "Wide landscape technology product illustration, abstract image-making machine only, absolutely no humans, "
            "no faces, no bodies, no portraits, no hands. In a black obsidian studio a precise gold orbital frame "
            "projects one floating rectangular image canvas; inside the canvas a coherent miniature imagined world "
            "contains an indigo mountain, emerald leaf and small amber sun, rendered as elegant painterly detail. "
            "Fine gold geometry resolves around the canvas like a local creative engine assembling an image. Premium "
            "DIO website art direction, restrained champagne gold, deep black space, one luminous focal point, polished "
            "editorial technology artwork, clean horizontal composition. No readable text, no letters, no logo, no watermark."
        )
    }
]

_original_workflow = base._workflow
def _workflow(brief):
    workflow = _original_workflow(brief)
    workflow["3"]["inputs"]["text"] += ", humans, people, portrait, face, body, fashion, hands, figure, person, model"
    workflow["5"]["inputs"]["steps"] = 21
    workflow["5"]["inputs"]["cfg"] = 7.0
    return workflow
base._workflow = _workflow
base.main()
