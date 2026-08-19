from __future__ import annotations

import re
from typing import Any

REQUIRED_ANTI_PATTERNS = {
    "four_quadrant_saas_card_grid",
    "repeated_photo_left_text_right",
    "body_paragraphs_on_video_frames",
    "static_slide_deck_as_video",
}


def _visible_word_count(block: str) -> int:
    cleaned = re.sub(r"^[#\s]+", "", str(block or "").strip())
    return len([word for word in cleaned.split() if word])


def validate_visual_contract(request: dict[str, Any], media_receipt: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not request.get("art_direction_hash"):
        errors.append("missing_document_studio_art_direction_hash")

    direction = dict(request.get("creative_direction") or {})
    scenes = list(direction.get("scene_directions") or [])
    anti_patterns = set(direction.get("anti_patterns") or [])
    if not scenes:
        errors.append("missing_scene_art_direction")
    else:
        layouts = [str(row.get("layout_family") or "") for row in scenes]
        distinct = len({layout for layout in layouts if layout})
        minimum = min(4, len(scenes))
        if distinct < minimum:
            errors.append(f"insufficient_layout_diversity:{distinct}<{minimum}")
        for left, right in zip(layouts, layouts[1:], strict=False):
            if left and left == right:
                errors.append(f"adjacent_layout_repetition:{left}")
        for row in scenes:
            display = str(row.get("display_copy") or "")
            limit = int(row.get("max_display_words") or 10)
            if len(display.split()) > limit:
                errors.append(f"display_copy_budget_exceeded:{row.get('scene_id')}")

    missing_anti = sorted(REQUIRED_ANTI_PATTERNS - anti_patterns)
    if missing_anti:
        errors.append("missing_visual_anti_patterns:" + ",".join(missing_anti))

    input_text = str(request.get("input_text") or "")
    if "Visual direction:" in input_text or "Story role:" in input_text:
        errors.append("visual_instruction_leaked_into_visible_copy")
    blocks = [block for block in re.split(r"\n\s*---\s*\n", input_text) if block.strip()]
    if blocks and any(_visible_word_count(block) > 10 for block in blocks):
        errors.append("gamma_visible_copy_is_paragraphic")

    variants = dict(media_receipt.get("variants") or {})
    for surface in ("vertical_short", "landscape_explainer"):
        variant = dict(variants.get(surface) or {})
        output = dict(variant.get("output") or {})
        if output.get("motion_state") != "executed":
            errors.append(f"motion_not_executed:{surface}")
        if output.get("static_slide_deck") is not False:
            errors.append(f"static_slide_deck_not_refused:{surface}")
        motions = list(output.get("motion_receipts") or [])
        if not motions:
            errors.append(f"missing_motion_receipts:{surface}")

    governance = dict(media_receipt.get("governance") or {})
    if governance.get("semantic_law_preserved") is not True:
        errors.append("semantic_law_not_preserved")
    return errors
