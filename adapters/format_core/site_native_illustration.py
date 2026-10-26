from __future__ import annotations

from typing import Any, Callable

from adapters.format_core.visual_composer import SCHEMA as COMPOSITION_SCHEMA, content_hash


SITE_ILLUSTRATION_RENDERER_VERSION = "1.1.0"
SITE_ILLUSTRATION_KINDS = {
    "research_workbench",
    "decision_landscape",
    "evidence_network",
    "communication_outputs",
    "method_map",
    "provenance_stack",
    "human_review_scene",
    "bounded_action",
}


ILLUSTRATION_TREATMENTS = {
    "research_workbench": {
        "density_band": "dense",
        "dominant_object": "overlapping_source_material",
        "edge_bleed": True,
        "composition_energy": "asymmetric_tactile",
    },
    "decision_landscape": {
        "density_band": "medium",
        "dominant_object": "research_strategy_canvas",
        "edge_bleed": False,
        "composition_energy": "editorial_planning",
    },
    "evidence_network": {
        "density_band": "dense",
        "dominant_object": "evidence_matrix",
        "edge_bleed": True,
        "composition_energy": "analytical_dense",
    },
    "communication_outputs": {
        "density_band": "medium",
        "dominant_object": "layered_professional_outputs",
        "edge_bleed": True,
        "composition_energy": "layered_editorial",
    },
    "method_map": {
        "density_band": "dense",
        "dominant_object": "annotated_working_wall",
        "edge_bleed": True,
        "composition_energy": "tactile_workflow",
    },
    "provenance_stack": {
        "density_band": "dense",
        "dominant_object": "inspectable_ledger",
        "edge_bleed": True,
        "composition_energy": "inspection_closeup",
    },
    "human_review_scene": {
        "density_band": "medium",
        "dominant_object": "reviewer_and_document",
        "edge_bleed": True,
        "composition_energy": "figurative_asymmetric",
    },
    "bounded_action": {
        "density_band": "sparse",
        "dominant_object": "single_intake_form",
        "edge_bleed": False,
        "composition_energy": "quiet_focal",
    },
}


class SiteNativeIllustrationError(RuntimeError):
    pass


def _clean(value: Any, limit: int = 360) -> str:
    return " ".join(str(value or "").split())[:limit].rstrip()


def _text(
    component_id: str,
    x: float,
    y: float,
    text: str,
    *,
    size: int = 18,
    weight: str = "700",
    fill: str = "$ink",
    anchor: str = "start",
    wrap_chars: int = 0,
    max_lines: int = 1,
    line_gap: int | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": component_id,
        "kind": "text",
        "x": x,
        "y": y,
        "text": _clean(text, 500),
        "size": size,
        "weight": weight,
        "fill": fill,
        "anchor": anchor,
        "max_lines": max_lines,
    }
    if wrap_chars:
        row["wrap_chars"] = wrap_chars
    if line_gap is not None:
        row["line_gap"] = line_gap
    return row


def _panel(
    component_id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    fill: str = "$surface",
    stroke: str = "$line",
    stroke_width: float = 1.5,
    radius: float = 6,
    opacity: float | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": component_id,
        "kind": "panel",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "fill": fill,
        "stroke": stroke,
        "stroke_width": stroke_width,
        "radius": radius,
    }
    if opacity is not None:
        row["opacity"] = opacity
    return row


def _line(
    component_id: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    stroke: str = "$line",
    stroke_width: float = 2,
) -> dict[str, Any]:
    return {
        "id": component_id,
        "kind": "line",
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "stroke": stroke,
        "stroke_width": stroke_width,
    }


def _circle(
    component_id: str,
    cx: float,
    cy: float,
    r: float,
    *,
    fill: str = "$surface",
    stroke: str = "$line",
    stroke_width: float = 2,
) -> dict[str, Any]:
    return {
        "id": component_id,
        "kind": "circle",
        "cx": cx,
        "cy": cy,
        "r": r,
        "fill": fill,
        "stroke": stroke,
        "stroke_width": stroke_width,
    }


def _path(
    component_id: str,
    d: str,
    *,
    fill: str = "none",
    stroke: str = "$ink",
    stroke_width: float = 2,
) -> dict[str, Any]:
    return {
        "id": component_id,
        "kind": "path",
        "d": d,
        "fill": fill,
        "stroke": stroke,
        "stroke_width": stroke_width,
    }


def _orientation(spec: dict[str, Any], *, title_x: int = 62, title_y: int = 64) -> list[dict[str, Any]]:
    """Small orientation marks only. The depicted object owns the canvas."""
    return [
        _text(
            "orientation-title",
            title_x,
            title_y,
            str(spec.get("title") or ""),
            size=25,
            weight="900",
            wrap_chars=50,
            max_lines=1,
        ),
        _text(
            "orientation-kind",
            1218,
            title_y,
            str(spec.get("visual_kind") or "").replace("_", " ").upper(),
            size=10,
            weight="900",
            fill="$accent",
            anchor="end",
        ),
    ]


def _paper_lines(
    prefix: str,
    x: int,
    y: int,
    widths: list[int],
    *,
    gap: int = 24,
    stroke: str = "$line",
) -> list[dict[str, Any]]:
    return [
        _line(
            f"{prefix}-{index}",
            x,
            y + (index - 1) * gap,
            x + width,
            y + (index - 1) * gap,
            stroke=stroke,
            stroke_width=1.7,
        )
        for index, width in enumerate(widths, 1)
    ]


def _render_research_workbench(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Dense, top-down working surface. The dominant paper bleeds off the left
    # and bottom edges so the scene reads as a crop of real work, not a slide.
    c.extend(
        [
            _panel("desk", -70, 104, 1420, 650, fill="$surface_alt", stroke="$surface_alt", radius=0),
            _path("paper-back", "M-70 198 L470 132 L530 650 L-16 714 Z", fill="$surface", stroke="$line", stroke_width=2),
            _path("paper-front", "M-24 148 L556 196 L500 748 L-82 692 Z", fill="$surface", stroke="$accent", stroke_width=3),
            _text("paper-kicker", 70, 224, "FIELD NOTES / SOURCE EXTRACT", size=15, weight="900", fill="$accent"),
            *_paper_lines("paper-line", 70, 264, [352, 318, 374, 286, 338, 304, 360], gap=34),
            _path("margin-ring", "M78 392 C180 338 330 342 430 398 C334 452 184 456 78 392 Z", stroke="$warning", stroke_width=4),
            _text("margin-note", 96, 490, "uncertainty remains visible", size=15, weight="900", fill="$warning"),
            _panel("notebook", 548, 164, 344, 414, fill="$paper", stroke="$line", stroke_width=2.5, radius=8),
            _line("notebook-spine", 590, 164, 590, 578, stroke="$accent", stroke_width=5),
            _text("notebook-title", 624, 218, "DECISION QUESTION", size=14, weight="900", fill="$accent"),
            _text("notebook-question", 624, 278, "What must this evidence help somebody decide?", size=27, weight="900", wrap_chars=22, max_lines=4, line_gap=34),
            _path("pencil", "M512 620 L848 570 L868 590 L530 646 Z", fill="$warning", stroke="$warning", stroke_width=1),
            _path("pencil-tip", "M512 620 L482 638 L530 646 Z", fill="$ink", stroke="$ink", stroke_width=1),
            _circle("lens", 1144, 184, 156, fill="$paper", stroke="$accent", stroke_width=6),
            _line("lens-handle", 1228, 298, 1332, 436, stroke="$accent", stroke_width=18),
            _text("lens-label", 1144, 192, "CHECK", size=22, weight="900", fill="$accent", anchor="middle"),
            _panel("brief", 936, 430, 354, 226, fill="$surface", stroke="$warning", stroke_width=3, radius=4),
            _text("brief-k", 968, 476, "DECISION BRIEF", size=15, weight="900", fill="$warning"),
            *_paper_lines("brief-line", 968, 518, [252, 224, 274, 206], gap=30),
            _text("brief-gate", 968, 638, "human review before release", size=13, weight="900", fill="$muted"),
        ]
    )
    return c


def _render_decision_landscape(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Editorial planning canvas. A large decision field is balanced against
    # smaller working notes rather than dividing the page into equal columns.
    c.extend(
        [
            _panel("planning-sheet", 58, 118, 1164, 542, fill="$surface", stroke="$line", stroke_width=2.5, radius=3),
            _text("planning-heading", 96, 168, "RESEARCH STRATEGY CANVAS", size=19, weight="900", fill="$accent"),
            _text("question-k", 96, 222, "QUESTION TO FRAME", size=13, weight="900", fill="$muted"),
            _text("question-v", 96, 268, "What decision does the research need to make possible?", size=30, weight="900", wrap_chars=34, max_lines=3, line_gap=36),
            _text("evidence-h", 100, 418, "EVIDENCE NEEDED", size=14, weight="900", fill="$accent"),
            *_paper_lines("evidence-row", 100, 452, [304, 268, 326], gap=42),
            _panel("stakeholder-note-a", 484, 214, 190, 112, fill="$surface_alt", stroke="$warning", stroke_width=2.5, radius=2),
            _text("stakeholder-a-k", 506, 250, "STAKEHOLDER", size=12, weight="900", fill="$warning"),
            _text("stakeholder-a", 506, 292, "CLIENT", size=22, weight="900"),
            _panel("stakeholder-note-b", 642, 344, 180, 106, fill="$paper", stroke="$accent", stroke_width=2.5, radius=2),
            _text("stakeholder-b-k", 664, 380, "STAKEHOLDER", size=12, weight="900", fill="$accent"),
            _text("stakeholder-b", 664, 418, "PUBLIC", size=22, weight="900"),
            _path("unknown-mark", "M492 514 C584 470 720 472 804 520 C716 570 582 568 492 514 Z", stroke="$warning", stroke_width=4),
            _text("unknown-a", 524, 522, "gap / contradiction", size=16, weight="900", fill="$warning"),
            _panel("decision-box", 850, 190, 318, 386, fill="$paper", stroke="$accent", stroke_width=4, radius=10),
            _text("decision-k", 884, 236, "DECISION TO SUPPORT", size=14, weight="900", fill="$accent"),
            _text("decision-v", 884, 304, "Frame the question before choosing the method.", size=31, weight="900", wrap_chars=22, max_lines=4, line_gap=38),
            _line("decision-rule", 884, 474, 1130, 474, stroke="$line", stroke_width=2),
            _text("decision-foot", 884, 522, "Evidence, uncertainty and authority remain visible together.", size=15, weight="800", fill="$muted", wrap_chars=30, max_lines=2),
        ]
    )
    return c


def _render_evidence_network(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Dense evidence artifact. The matrix deliberately runs past both side
    # margins, echoing HOMS source/data sheets rather than a centered widget.
    c.extend(
        [
            _text("matrix-heading", 40, 126, "EVIDENCE SYNTHESIS MATRIX", size=18, weight="900", fill="$accent"),
            {
                "id": "evidence-matrix",
                "kind": "table",
                "x": -18,
                "y": 154,
                "width": 1316,
                "height": 376,
                "headers": ["Source", "Claim / finding", "Fit", "Tension", "Review state"],
                "rows": [
                    ["Source A", "Supports the central finding", "Strong", "None", "Retain"],
                    ["Source B", "Qualifies the central finding", "Partial", "Context", "Review"],
                    ["Source C", "Conflicts with one assumption", "Mixed", "Material", "Escalate"],
                    ["Source D", "Adds implementation evidence", "Strong", "None", "Retain"],
                ],
                "header_fill": "$surface_alt",
                "fill": "$surface",
                "stroke": "$line",
                "text_fill": "$ink",
                "muted_fill": "$muted",
            },
            _panel("tension-band", -20, 552, 816, 112, fill="$surface_alt", stroke="$warning", stroke_width=3, radius=0),
            _text("tension-k", 34, 590, "TENSION RETAINED", size=13, weight="900", fill="$warning"),
            _text("tension-v", 34, 628, "Contradictory evidence remains visible until a reviewer resolves it.", size=19, weight="900", wrap_chars=58, max_lines=2),
            _panel("review-stamp", 902, 540, 338, 126, fill="$paper", stroke="$warning", stroke_width=4, radius=8),
            _text("review-stamp-k", 1071, 584, "REVIEW REQUIRED", size=19, weight="900", fill="$warning", anchor="middle"),
            _text("review-stamp-v", 1071, 622, "no silent reconciliation", size=14, weight="800", fill="$muted", anchor="middle"),
        ]
    )
    return c


def _render_communication_outputs(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Layered professional outputs with different scale and crop. The browser
    # and report both bleed beyond the canvas to avoid a three-card layout.
    c.extend(
        [
            _path("report-page", "M-40 176 L420 126 L470 706 L4 754 Z", fill="$surface", stroke="$line", stroke_width=3),
            _text("report-k", 62, 198, "REPORT", size=15, weight="900", fill="$accent"),
            _text("report-title", 62, 248, "Finding and implication", size=29, weight="900", wrap_chars=24, max_lines=2, line_gap=34),
            *_paper_lines("report-body", 62, 332, [300, 276, 322, 248, 288, 312], gap=34),
            _panel("report-claim", 62, 552, 282, 54, fill="$surface_alt", stroke="$accent", stroke_width=2.5, radius=2),
            _text("report-claim-v", 203, 586, "same governed claim", size=14, weight="900", fill="$accent", anchor="middle"),
            _panel("slide-screen", 448, 132, 474, 316, fill="$paper", stroke="$accent", stroke_width=4, radius=4),
            _text("slide-k", 482, 176, "PRESENTATION", size=14, weight="900", fill="$accent"),
            _text("slide-title", 482, 228, "What changes the decision?", size=31, weight="900", wrap_chars=26, max_lines=2, line_gap=36),
            _path("slide-chart", "M500 384 L576 320 L652 346 L752 256 L850 304", stroke="$warning", stroke_width=7),
            _line("slide-base", 500, 392, 862, 392, stroke="$line", stroke_width=2),
            _panel("slide-claim", 518, 468, 336, 52, fill="$surface_alt", stroke="$accent", stroke_width=2, radius=2),
            _text("slide-claim-v", 686, 501, "same governed claim", size=14, weight="900", fill="$accent", anchor="middle"),
            _panel("browser", 930, 222, 420, 520, fill="$surface", stroke="$line", stroke_width=3, radius=14),
            _line("browser-top", 930, 280, 1350, 280, stroke="$line", stroke_width=2),
            _circle("browser-dot-a", 960, 250, 7, fill="$warning", stroke="$warning", stroke_width=1),
            _circle("browser-dot-b", 986, 250, 7, fill="$accent", stroke="$accent", stroke_width=1),
            _text("browser-k", 964, 328, "PUBLIC EXPLANATION", size=14, weight="900", fill="$accent"),
            _text("browser-title", 964, 382, "Evidence people can actually use", size=29, weight="900", wrap_chars=22, max_lines=3, line_gap=34),
            *_paper_lines("browser-body", 964, 492, [298, 260, 286, 226], gap=30),
        ]
    )
    return c


def _render_method_map(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Dense working wall. Folder and review envelope crop against opposite
    # edges while the annotated source sheet dominates the middle.
    c.extend(
        [
            _panel("wall", -40, 106, 1380, 630, fill="$surface_alt", stroke="$surface_alt", radius=0),
            _path("folder", "M-56 232 L154 232 L190 184 L430 184 L430 470 L-56 470 Z", fill="$surface", stroke="$accent", stroke_width=4),
            _text("folder-k", 40, 282, "INTAKE", size=15, weight="900", fill="$accent"),
            _text("folder-v", 40, 340, "decision context", size=28, weight="900"),
            _path("source-sheet", "M410 132 L808 188 L744 626 L344 570 Z", fill="$surface", stroke="$line", stroke_width=3),
            _text("source-k", 452, 228, "SUPPLIED MATERIAL", size=15, weight="900", fill="$accent"),
            *_paper_lines("source-lines", 452, 270, [260, 234, 282, 220, 252, 200], gap=34),
            _path("annotation", "M426 436 C528 382 678 386 760 444 C668 502 524 500 426 436 Z", stroke="$warning", stroke_width=4),
            _text("annotation-v", 500, 514, "gaps exposed", size=16, weight="900", fill="$warning"),
            _panel("review-envelope", 858, 262, 500, 330, fill="$paper", stroke="$warning", stroke_width=4, radius=6),
            _path("envelope-fold", "M858 262 L1108 430 L1358 262", stroke="$line", stroke_width=3),
            _text("review-envelope-k", 1098, 492, "REVIEWABLE HANDOFF", size=20, weight="900", fill="$warning", anchor="middle"),
            _text("review-envelope-v", 1098, 534, "human judgement attached", size=15, weight="800", fill="$muted", anchor="middle"),
            _path("pin-a", "M318 592 C318 568 354 568 354 592 C354 616 336 638 336 638 C336 638 318 616 318 592 Z", fill="$accent", stroke="$accent", stroke_width=1),
            _path("pin-b", "M812 156 C812 132 848 132 848 156 C848 180 830 202 830 202 C830 202 812 180 812 156 Z", fill="$warning", stroke="$warning", stroke_width=1),
            _line("workspace-relation-a", 430, 322, 460, 322, stroke="$accent", stroke_width=5),
            _line("workspace-relation-b", 780, 358, 858, 358, stroke="$warning", stroke_width=5),
        ]
    )
    return c


def _render_provenance_stack(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Inspection close-up. Ledger bleeds left and the magnifier is intentionally
    # oversized/cropped on the right so the act of inspection becomes the hero.
    c.extend(
        [
            _panel("ledger", -36, 118, 936, 574, fill="$surface", stroke="$line", stroke_width=3, radius=3),
            _text("ledger-title", 54, 172, "PROVENANCE LEDGER", size=20, weight="900", fill="$accent"),
            _line("ledger-rule", 54, 202, 852, 202, stroke="$line", stroke_width=2),
            _text("ledger-h1", 64, 242, "OBJECT", size=13, weight="900", fill="$muted"),
            _text("ledger-h2", 392, 242, "BOUND STATE", size=13, weight="900", fill="$muted"),
            _text("ledger-h3", 720, 242, "CHECK", size=13, weight="900", fill="$muted"),
        ]
    )
    rows = [
        ("Source material", "hash-bound", "✓", "$accent"),
        ("Semantic law", "versioned", "✓", "$accent"),
        ("Customer projection", "traceable", "✓", "$accent"),
        ("Visual QA", "review required", "!", "$warning"),
    ]
    y = 292
    for index, (obj, state, check, colour) in enumerate(rows, 1):
        c.append(_line(f"ledger-row-{index}", 54, y + 36, 852, y + 36, stroke="$line", stroke_width=1.5))
        c.append(_text(f"ledger-obj-{index}", 64, y, obj, size=18, weight="800"))
        c.append(_text(f"ledger-state-{index}", 392, y, state, size=17, weight="700", fill="$muted"))
        c.append(_text(f"ledger-check-{index}", 744, y, check, size=24, weight="900", fill=colour))
        y += 80
    c.extend(
        [
            _circle("magnifier", 1136, 270, 176, fill="$paper", stroke="$accent", stroke_width=7),
            _line("magnifier-handle", 1242, 408, 1360, 566, stroke="$accent", stroke_width=22),
            _text("magnifier-k", 1136, 250, "CLAIM", size=15, weight="900", fill="$accent", anchor="middle"),
            _text("magnifier-v", 1136, 296, "→ SOURCE", size=24, weight="900", anchor="middle"),
            _panel("boundary-stamp", 946, 526, 300, 120, fill="$paper", stroke="$warning", stroke_width=4, radius=8),
            _text("boundary-k", 1096, 570, "REVIEW BOUNDARY", size=17, weight="900", fill="$warning", anchor="middle"),
            _text("boundary-v", 1096, 608, "release still human", size=14, weight="800", fill="$muted", anchor="middle"),
        ]
    )
    return c


def _render_human_review_scene(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Figurative review scene. The document fills the foreground and reviewer
    # body exits the bottom/right edge, producing a real scene rather than an icon.
    c.extend(
        [
            _panel("desk-surface", -40, 500, 1380, 260, fill="$surface_alt", stroke="$surface_alt", radius=0),
            _path("review-sheet", "M-82 236 L642 270 L590 756 L-138 712 Z", fill="$surface", stroke="$accent", stroke_width=3),
            _text("review-sheet-k", 72, 302, "PREPARED WORK", size=16, weight="900", fill="$accent"),
            *_paper_lines("review-lines", 72, 346, [440, 396, 462, 350, 418, 372], gap=38),
            _path("accept-mark", "M92 606 L132 642 L202 566", stroke="$accent", stroke_width=8),
            _path("change-mark", "M294 582 L362 650 M362 582 L294 650", stroke="$warning", stroke_width=8),
            _circle("reviewer-head", 1038, 178, 94, fill="$surface", stroke="$ink", stroke_width=5),
            _path("reviewer-body", "M814 744 C834 360 1232 360 1260 744", fill="$surface", stroke="$ink", stroke_width=5),
            _path("reviewer-arm", "M852 424 C760 470 684 518 574 540", stroke="$ink", stroke_width=26),
            _path("pen", "M548 544 L684 480 L698 500 L562 568 Z", fill="$warning", stroke="$warning", stroke_width=1),
            _text("reviewer-label", 1038, 334, "AUTHORISED HUMAN", size=18, weight="900", fill="$warning", anchor="middle"),
            _panel("release-stamp", 1080, 500, 218, 112, fill="$paper", stroke="$warning", stroke_width=4, radius=8),
            _text("release-a", 1189, 542, "RELEASE", size=14, weight="900", fill="$warning", anchor="middle"),
            _text("release-b", 1189, 582, "HELD", size=22, weight="900", anchor="middle"),
        ]
    )
    return c


def _render_bounded_action(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Deliberately sparse. One intake object, one pen, one bounded-start stamp.
    # The empty right field is intentional visual quiet, not unused space.
    c.extend(
        [
            _panel("intake-form", 96, 132, 660, 512, fill="$surface", stroke="$accent", stroke_width=3, radius=5),
            _text("intake-k", 136, 184, "ONE REAL JOB", size=15, weight="900", fill="$accent"),
            _text("intake-title", 136, 238, "Decision context", size=32, weight="900"),
            _text("field-a", 136, 314, "What material are you supplying?", size=14, weight="800", fill="$muted"),
            _line("field-a-line", 136, 344, 706, 344, stroke="$line", stroke_width=2),
            _text("field-b", 136, 394, "What needs deciding?", size=14, weight="800", fill="$muted"),
            _line("field-b-line", 136, 424, 706, 424, stroke="$line", stroke_width=2),
            _text("field-c", 136, 474, "Who has authority to release it?", size=14, weight="800", fill="$muted"),
            _line("field-c-line", 136, 504, 706, 504, stroke="$line", stroke_width=2),
            _text("review-box-v", 136, 584, "HUMAN REVIEW REQUIRED", size=14, weight="900", fill="$warning"),
            _path("pen-body", "M868 214 L1018 518 L990 532 L840 228 Z", fill="$accent", stroke="$accent", stroke_width=1),
            _path("pen-tip", "M1018 518 L1040 558 L990 532 Z", fill="$ink", stroke="$ink", stroke_width=1),
            _circle("start-ring", 1120, 500, 118, fill="$paper", stroke="$accent", stroke_width=5),
            _text("start-a", 1120, 482, "BOUNDED", size=16, weight="900", fill="$accent", anchor="middle"),
            _text("start-b", 1120, 522, "START", size=28, weight="900", anchor="middle"),
            _text("start-c", 1120, 558, "one artifact · one review", size=13, weight="800", fill="$muted", anchor="middle"),
        ]
    )
    return c


_RENDERERS: dict[str, Callable[[dict[str, Any]], list[dict[str, Any]]]] = {
    "research_workbench": _render_research_workbench,
    "decision_landscape": _render_decision_landscape,
    "evidence_network": _render_evidence_network,
    "communication_outputs": _render_communication_outputs,
    "method_map": _render_method_map,
    "provenance_stack": _render_provenance_stack,
    "human_review_scene": _render_human_review_scene,
    "bounded_action": _render_bounded_action,
}


REPRESENTATIONAL_MODES = {
    "research_workbench": "top_down_object_scene",
    "decision_landscape": "professional_planning_artifact",
    "evidence_network": "evidence_matrix_artifact",
    "communication_outputs": "multi_artifact_scene",
    "method_map": "annotated_workspace_scene",
    "provenance_stack": "inspectable_ledger_scene",
    "human_review_scene": "human_review_object_scene",
    "bounded_action": "client_intake_object_scene",
}


def site_semantic_visual_to_composition(
    spec: dict[str, Any],
    *,
    profile_id: str,
    width: int = 1280,
    height: int = 720,
    binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kind = str(spec.get("visual_kind") or "")
    if kind not in _RENDERERS:
        raise SiteNativeIllustrationError(f"unsupported Site illustration visual_kind: {kind or '(missing)'}")
    source = dict(spec.get("source") or {})
    if source.get("role_selects_geometry") is not False:
        raise SiteNativeIllustrationError("role_selects_geometry must be false")

    treatment = dict(ILLUSTRATION_TREATMENTS[kind])
    components = _RENDERERS[kind](spec)
    composition = {
        "schema": COMPOSITION_SCHEMA,
        "composition_id": str(spec.get("visual_id") or f"SITE-{kind}"),
        "title": _clean(spec.get("title") or kind, 120),
        "profile_id": profile_id,
        "canvas": {"width": width, "height": height, "background": "$paper"},
        "components": components,
        "binding": {
            "semantic_visual_schema": spec.get("schema"),
            "semantic_visual_hash": spec.get("semantic_visual_hash") or content_hash(spec),
            "visual_kind": kind,
            "semantic_intent": spec.get("semantic_intent"),
            "geometry_selector": "site_native_illustration_registry",
            "role_selects_geometry": False,
            "representational_mode": REPRESENTATIONAL_MODES[kind],
            "illustration_renderer_version": SITE_ILLUSTRATION_RENDERER_VERSION,
            "illustration_density_band": treatment["density_band"],
            "illustration_dominant_object": treatment["dominant_object"],
            "illustration_edge_bleed": treatment["edge_bleed"],
            "illustration_composition_energy": treatment["composition_energy"],
            **dict(binding or {}),
        },
    }
    return composition


__all__ = [
    "ILLUSTRATION_TREATMENTS",
    "REPRESENTATIONAL_MODES",
    "SITE_ILLUSTRATION_KINDS",
    "SITE_ILLUSTRATION_RENDERER_VERSION",
    "SiteNativeIllustrationError",
    "site_semantic_visual_to_composition",
]
