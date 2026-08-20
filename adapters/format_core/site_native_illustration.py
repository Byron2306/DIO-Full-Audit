from __future__ import annotations

from typing import Any, Callable

from adapters.format_core.visual_composer import SCHEMA as COMPOSITION_SCHEMA, content_hash


SITE_ILLUSTRATION_RENDERER_VERSION = "1.0.0"
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
) -> dict[str, Any]:
    return {
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


def _line(component_id: str, x1: float, y1: float, x2: float, y2: float, *, stroke: str = "$line", stroke_width: float = 2) -> dict[str, Any]:
    return {"id": component_id, "kind": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "stroke": stroke, "stroke_width": stroke_width}


def _circle(component_id: str, cx: float, cy: float, r: float, *, fill: str = "$surface", stroke: str = "$line", stroke_width: float = 2) -> dict[str, Any]:
    return {"id": component_id, "kind": "circle", "cx": cx, "cy": cy, "r": r, "fill": fill, "stroke": stroke, "stroke_width": stroke_width}


def _path(component_id: str, d: str, *, fill: str = "none", stroke: str = "$ink", stroke_width: float = 2) -> dict[str, Any]:
    return {"id": component_id, "kind": "path", "d": d, "fill": fill, "stroke": stroke, "stroke_width": stroke_width}


def _orientation(spec: dict[str, Any], *, title_x: int = 64, title_y: int = 66) -> list[dict[str, Any]]:
    """A light orientation mark only. The illustration owns the canvas."""
    return [
        _text("orientation-title", title_x, title_y, str(spec.get("title") or ""), size=26, weight="900", wrap_chars=48, max_lines=1),
        _text(
            "orientation-kind",
            1216,
            title_y,
            str(spec.get("visual_kind") or "").replace("_", " ").upper(),
            size=11,
            weight="900",
            fill="$accent",
            anchor="end",
        ),
    ]


def _paper_lines(prefix: str, x: int, y: int, widths: list[int], *, gap: int = 24, stroke: str = "$line") -> list[dict[str, Any]]:
    return [
        _line(f"{prefix}-{index}", x, y + (index - 1) * gap, x + width, y + (index - 1) * gap, stroke=stroke, stroke_width=1.7)
        for index, width in enumerate(widths, 1)
    ]


def _render_research_workbench(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Top-down working desk: source papers, notebook, pencil, magnifier and a
    # prepared decision brief. Deliberately object-first, not node-link UI.
    c.extend([
        _panel("desk", 42, 104, 1196, 566, fill="$surface_alt", stroke="$paper", stroke_width=0, radius=18),
        _path("paper-back", "M92 176 L428 146 L452 500 L116 526 Z", fill="$surface", stroke="$line", stroke_width=2),
        _path("paper-front", "M138 154 L480 182 L452 542 L110 514 Z", fill="$surface", stroke="$accent", stroke_width=2.5),
        _text("paper-kicker", 164, 218, "FIELD NOTES / SOURCE EXTRACT", size=14, weight="900", fill="$accent"),
        *_paper_lines("paper-line", 164, 252, [244, 216, 254, 188, 236, 202], gap=30),
        _path("margin-ring", "M160 364 C220 330 320 334 382 368 C326 402 220 404 160 364 Z", stroke="$warning", stroke_width=3),
        _text("margin-note", 172, 440, "uncertainty remains visible", size=14, weight="900", fill="$warning"),
        _panel("notebook", 548, 176, 274, 338, fill="$paper", stroke="$line", stroke_width=2, radius=8),
        _line("notebook-spine", 582, 176, 582, 514, stroke="$accent", stroke_width=4),
        _text("notebook-title", 612, 226, "DECISION QUESTION", size=14, weight="900", fill="$accent"),
        _text("notebook-question", 612, 278, "What must this evidence help somebody decide?", size=24, weight="900", wrap_chars=22, max_lines=4, line_gap=30),
        _path("pencil", "M510 562 L792 532 L810 548 L526 580 Z", fill="$warning", stroke="$warning", stroke_width=1),
        _path("pencil-tip", "M510 562 L488 574 L526 580 Z", fill="$ink", stroke="$ink", stroke_width=1),
        _circle("lens", 934, 266, 86, fill="$paper", stroke="$accent", stroke_width=5),
        _line("lens-handle", 994, 326, 1086, 418, stroke="$accent", stroke_width=12),
        _text("lens-label", 934, 272, "CHECK", size=18, weight="900", fill="$accent", anchor="middle"),
        _panel("brief", 888, 430, 284, 184, fill="$surface", stroke="$warning", stroke_width=2.5, radius=4),
        _text("brief-k", 914, 466, "DECISION BRIEF", size=14, weight="900", fill="$warning"),
        *_paper_lines("brief-line", 914, 500, [210, 184, 226], gap=27),
        _text("brief-gate", 914, 596, "human review before release", size=13, weight="900", fill="$muted"),
    ])
    return c


def _render_decision_landscape(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Research planning canvas: a real planning sheet with evidence column,
    # stakeholder notes, uncertainty annotations and a decision box.
    c.extend([
        _panel("planning-sheet", 102, 128, 1076, 500, fill="$surface", stroke="$line", stroke_width=2.5, radius=3),
        _text("planning-heading", 140, 174, "RESEARCH STRATEGY CANVAS", size=18, weight="900", fill="$accent"),
        _line("planning-v1", 420, 200, 420, 590, stroke="$line", stroke_width=2),
        _line("planning-v2", 812, 200, 812, 590, stroke="$line", stroke_width=2),
        _text("evidence-h", 150, 232, "EVIDENCE NEEDED", size=14, weight="900", fill="$accent"),
        *_paper_lines("evidence-row", 150, 268, [220, 190, 235, 170], gap=48),
        _text("stakeholder-h", 458, 232, "WHO CARRIES THE DECISION?", size=14, weight="900", fill="$warning"),
        _panel("stakeholder-note-a", 456, 272, 148, 86, fill="$surface_alt", stroke="$warning", stroke_width=2, radius=2),
        _text("stakeholder-a", 474, 314, "CLIENT", size=17, weight="900"),
        _panel("stakeholder-note-b", 624, 324, 146, 86, fill="$paper", stroke="$accent", stroke_width=2, radius=2),
        _text("stakeholder-b", 642, 366, "PUBLIC", size=17, weight="900"),
        _panel("stakeholder-note-c", 486, 430, 178, 92, fill="$surface_alt", stroke="$line", stroke_width=2, radius=2),
        _text("stakeholder-c", 504, 470, "REVIEWER", size=17, weight="900"),
        _text("unknown-h", 846, 232, "WHAT IS STILL UNKNOWN?", size=14, weight="900", fill="$warning"),
        _path("unknown-mark-a", "M850 278 C930 250 1040 254 1102 286 C1040 318 930 320 850 278 Z", stroke="$warning", stroke_width=3),
        _text("unknown-a", 876, 286, "gap / contradiction", size=15, weight="900", fill="$warning"),
        _panel("decision-box", 850, 398, 276, 156, fill="$paper", stroke="$accent", stroke_width=3.5, radius=8),
        _text("decision-k", 876, 438, "DECISION TO SUPPORT", size=14, weight="900", fill="$accent"),
        _text("decision-v", 876, 486, "Frame the question before choosing the method.", size=22, weight="900", wrap_chars=24, max_lines=3, line_gap=27),
    ])
    return c


def _render_evidence_network(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Evidence synthesis as a literature/evidence matrix, because that is the
    # native professional object. No circles, no abstract topology diagram.
    c.extend([
        _text("matrix-heading", 76, 128, "EVIDENCE SYNTHESIS MATRIX", size=18, weight="900", fill="$accent"),
        {
            "id": "evidence-matrix",
            "kind": "table",
            "x": 76,
            "y": 158,
            "width": 1128,
            "height": 336,
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
        _panel("synthesis-note", 76, 532, 724, 104, fill="$surface_alt", stroke="$accent", stroke_width=2.5, radius=6),
        _text("synthesis-note-k", 100, 566, "SYNTHESIS NOTE", size=13, weight="900", fill="$accent"),
        _text("synthesis-note-v", 100, 602, "Agreement, contradiction and uncertainty stay visible together.", size=18, weight="900", wrap_chars=58, max_lines=2),
        _panel("review-stamp", 860, 524, 344, 116, fill="$paper", stroke="$warning", stroke_width=3, radius=8),
        _text("review-stamp-k", 1032, 566, "REVIEW REQUIRED", size=18, weight="900", fill="$warning", anchor="middle"),
        _text("review-stamp-v", 1032, 602, "no silent reconciliation", size=14, weight="800", fill="$muted", anchor="middle"),
    ])
    return c


def _render_communication_outputs(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Three recognisable communication artifacts: report, slide and public web
    # article. Same meaning is shown as a shared highlighted claim strip.
    c.extend([
        _panel("report-page", 74, 142, 320, 430, fill="$surface", stroke="$line", stroke_width=2.5, radius=3),
        _text("report-k", 102, 182, "REPORT", size=15, weight="900", fill="$accent"),
        _text("report-title", 102, 226, "Finding and implication", size=22, weight="900", wrap_chars=24, max_lines=2),
        *_paper_lines("report-body", 102, 286, [244, 220, 254, 232, 190, 246], gap=30),
        _panel("report-claim", 102, 486, 236, 48, fill="$surface_alt", stroke="$accent", stroke_width=2, radius=2),
        _text("report-claim-v", 116, 516, "same governed claim", size=13, weight="900", fill="$accent"),
        _panel("slide-screen", 454, 170, 360, 248, fill="$paper", stroke="$accent", stroke_width=3, radius=4),
        _text("slide-k", 480, 206, "PRESENTATION", size=14, weight="900", fill="$accent"),
        _text("slide-title", 480, 252, "What changes the decision?", size=24, weight="900", wrap_chars=24, max_lines=2),
        _path("slide-chart", "M500 366 L558 326 L614 344 L690 278 L754 310", stroke="$warning", stroke_width=6),
        _line("slide-base", 498, 370, 764, 370, stroke="$line", stroke_width=2),
        _panel("slide-claim", 494, 438, 280, 46, fill="$surface_alt", stroke="$accent", stroke_width=2, radius=2),
        _text("slide-claim-v", 634, 467, "same governed claim", size=13, weight="900", fill="$accent", anchor="middle"),
        _panel("browser", 862, 136, 342, 452, fill="$surface", stroke="$line", stroke_width=2.5, radius=14),
        _line("browser-top", 862, 186, 1204, 186, stroke="$line", stroke_width=2),
        _circle("browser-dot-a", 890, 162, 6, fill="$warning", stroke="$warning", stroke_width=1),
        _circle("browser-dot-b", 912, 162, 6, fill="$accent", stroke="$accent", stroke_width=1),
        _text("browser-k", 890, 224, "PUBLIC EXPLANATION", size=14, weight="900", fill="$accent"),
        _text("browser-title", 890, 274, "Evidence people can actually use", size=24, weight="900", wrap_chars=22, max_lines=3, line_gap=28),
        *_paper_lines("browser-body", 890, 372, [248, 220, 252, 186], gap=28),
        _panel("browser-claim", 890, 502, 260, 50, fill="$surface_alt", stroke="$accent", stroke_width=2, radius=2),
        _text("browser-claim-v", 1020, 533, "same governed claim", size=13, weight="900", fill="$accent", anchor="middle"),
    ])
    return c


def _render_method_map(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # A working wall rather than a timeline: intake folder, source sheets,
    # annotation page and review envelope are connected by physical placement.
    c.extend([
        _panel("wall", 58, 112, 1164, 534, fill="$surface_alt", stroke="$paper", stroke_width=0, radius=12),
        _path("folder", "M94 206 L228 206 L254 174 L430 174 L430 372 L94 372 Z", fill="$surface", stroke="$accent", stroke_width=3),
        _text("folder-k", 122, 250, "INTAKE", size=15, weight="900", fill="$accent"),
        _text("folder-v", 122, 300, "decision context", size=22, weight="900"),
        _path("source-sheet", "M468 152 L718 176 L690 440 L440 416 Z", fill="$surface", stroke="$line", stroke_width=2.5),
        _text("source-k", 486, 218, "SUPPLIED MATERIAL", size=14, weight="900", fill="$accent"),
        *_paper_lines("source-lines", 486, 254, [176, 158, 190, 150], gap=30),
        _path("annotation", "M466 352 C520 326 600 328 654 354 C604 384 522 386 466 352 Z", stroke="$warning", stroke_width=3),
        _text("annotation-v", 500, 402, "gaps exposed", size=14, weight="900", fill="$warning"),
        _panel("review-envelope", 770, 238, 344, 232, fill="$paper", stroke="$warning", stroke_width=3, radius=6),
        _path("envelope-fold", "M770 238 L942 354 L1114 238", stroke="$line", stroke_width=2),
        _text("review-envelope-k", 942, 396, "REVIEWABLE HANDOFF", size=17, weight="900", fill="$warning", anchor="middle"),
        _text("review-envelope-v", 942, 430, "human judgement attached", size=14, weight="800", fill="$muted", anchor="middle"),
        _path("pin-a", "M318 408 C318 388 348 388 348 408 C348 428 333 446 333 446 C333 446 318 428 318 408 Z", fill="$accent", stroke="$accent", stroke_width=1),
        _path("pin-b", "M700 492 C700 472 730 472 730 492 C730 512 715 530 715 530 C715 530 700 512 700 492 Z", fill="$warning", stroke="$warning", stroke_width=1),
        _line("workspace-relation-a", 430, 288, 454, 288, stroke="$accent", stroke_width=4),
        _line("workspace-relation-b", 710, 324, 770, 324, stroke="$warning", stroke_width=4),
    ])
    return c


def _render_provenance_stack(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Provenance as an inspectable ledger with bound records and a magnifier,
    # not a stack of generic rectangles labelled with ontology terms.
    c.extend([
        _panel("ledger", 86, 132, 760, 486, fill="$surface", stroke="$line", stroke_width=2.5, radius=4),
        _text("ledger-title", 118, 178, "PROVENANCE LEDGER", size=18, weight="900", fill="$accent"),
        _line("ledger-rule", 118, 202, 814, 202, stroke="$line", stroke_width=2),
        _text("ledger-h1", 126, 240, "OBJECT", size=13, weight="900", fill="$muted"),
        _text("ledger-h2", 410, 240, "BOUND STATE", size=13, weight="900", fill="$muted"),
        _text("ledger-h3", 650, 240, "CHECK", size=13, weight="900", fill="$muted"),
    ])
    rows = [
        ("Source material", "hash-bound", "✓", "$accent"),
        ("Semantic law", "versioned", "✓", "$accent"),
        ("Customer projection", "traceable", "✓", "$accent"),
        ("Visual QA", "review required", "!", "$warning"),
    ]
    y = 278
    for index, (obj, state, check, colour) in enumerate(rows, 1):
        c.append(_line(f"ledger-row-{index}", 118, y + 32, 814, y + 32, stroke="$line", stroke_width=1.5))
        c.append(_text(f"ledger-obj-{index}", 126, y, obj, size=17, weight="800"))
        c.append(_text(f"ledger-state-{index}", 410, y, state, size=16, weight="700", fill="$muted"))
        c.append(_text(f"ledger-check-{index}", 672, y, check, size=22, weight="900", fill=colour))
        y += 72
    c.extend([
        _circle("magnifier", 1018, 302, 96, fill="$paper", stroke="$accent", stroke_width=5),
        _line("magnifier-handle", 1084, 370, 1174, 460, stroke="$accent", stroke_width=14),
        _text("magnifier-k", 1018, 288, "CLAIM", size=13, weight="900", fill="$accent", anchor="middle"),
        _text("magnifier-v", 1018, 324, "→ SOURCE", size=19, weight="900", anchor="middle"),
        _panel("boundary-stamp", 918, 500, 270, 102, fill="$paper", stroke="$warning", stroke_width=3, radius=8),
        _text("boundary-k", 1053, 538, "REVIEW BOUNDARY", size=15, weight="900", fill="$warning", anchor="middle"),
        _text("boundary-v", 1053, 572, "release still human", size=13, weight="800", fill="$muted", anchor="middle"),
    ])
    return c


def _render_human_review_scene(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # Side-on review desk with a document, hand/pen gesture and reviewer.
    c.extend([
        _panel("desk-surface", 70, 486, 1140, 122, fill="$surface_alt", stroke="$paper", stroke_width=0, radius=6),
        _path("review-sheet", "M126 188 L568 214 L536 520 L94 494 Z", fill="$surface", stroke="$accent", stroke_width=2.5),
        _text("review-sheet-k", 154, 242, "PREPARED WORK", size=15, weight="900", fill="$accent"),
        *_paper_lines("review-lines", 154, 278, [320, 286, 338, 252, 306], gap=32),
        _path("accept-mark", "M166 446 L194 470 L242 416", stroke="$accent", stroke_width=6),
        _path("change-mark", "M314 424 L362 472 M362 424 L314 472", stroke="$warning", stroke_width=6),
        _circle("reviewer-head", 938, 212, 64, fill="$surface", stroke="$ink", stroke_width=4),
        _path("reviewer-body", "M812 482 C826 304 1050 304 1064 482", fill="$surface", stroke="$ink", stroke_width=4),
        _path("reviewer-arm", "M826 374 C744 402 680 440 594 456", stroke="$ink", stroke_width=18),
        _path("pen", "M574 456 L660 418 L670 432 L586 472 Z", fill="$warning", stroke="$warning", stroke_width=1),
        _text("reviewer-label", 938, 542, "AUTHORISED HUMAN", size=17, weight="900", fill="$warning", anchor="middle"),
        _panel("release-stamp", 1030, 414, 150, 92, fill="$paper", stroke="$warning", stroke_width=3, radius=8),
        _text("release-a", 1105, 448, "RELEASE", size=13, weight="900", fill="$warning", anchor="middle"),
        _text("release-b", 1105, 478, "HELD", size=18, weight="900", anchor="middle"),
    ])
    return c


def _render_bounded_action(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _orientation(spec)
    # A concrete client intake form with a physical pen and review stamp.
    c.extend([
        _panel("intake-form", 146, 126, 720, 500, fill="$surface", stroke="$accent", stroke_width=3, radius=5),
        _text("intake-k", 184, 174, "ONE REAL JOB", size=15, weight="900", fill="$accent"),
        _text("intake-title", 184, 222, "Decision context", size=28, weight="900"),
        _text("field-a", 184, 282, "What material are you supplying?", size=14, weight="800", fill="$muted"),
        _line("field-a-line", 184, 310, 812, 310, stroke="$line", stroke_width=2),
        _text("field-b", 184, 354, "What needs deciding?", size=14, weight="800", fill="$muted"),
        _line("field-b-line", 184, 382, 812, 382, stroke="$line", stroke_width=2),
        _text("field-c", 184, 426, "Who has authority to release it?", size=14, weight="800", fill="$muted"),
        _line("field-c-line", 184, 454, 812, 454, stroke="$line", stroke_width=2),
        _panel("review-box", 184, 502, 314, 72, fill="$surface_alt", stroke="$warning", stroke_width=2.5, radius=4),
        _text("review-box-v", 341, 546, "HUMAN REVIEW REQUIRED", size=14, weight="900", fill="$warning", anchor="middle"),
        _path("pen-body", "M928 214 L1084 530 L1056 544 L900 228 Z", fill="$accent", stroke="$accent", stroke_width=1),
        _path("pen-tip", "M1084 530 L1108 574 L1056 544 Z", fill="$ink", stroke="$ink", stroke_width=1),
        _panel("start-stamp", 914, 470, 250, 126, fill="$paper", stroke="$accent", stroke_width=4, radius=10),
        _text("start-a", 1039, 510, "BOUNDED START", size=18, weight="900", fill="$accent", anchor="middle"),
        _text("start-b", 1039, 548, "one artifact · one review", size=13, weight="800", fill="$muted", anchor="middle"),
        _text("no-release", 1039, 590, "NO AUTOMATIC RELEASE", size=12, weight="900", fill="$warning", anchor="middle"),
    ])
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
            **dict(binding or {}),
        },
    }
    return composition


__all__ = [
    "REPRESENTATIONAL_MODES",
    "SITE_ILLUSTRATION_KINDS",
    "SITE_ILLUSTRATION_RENDERER_VERSION",
    "SiteNativeIllustrationError",
    "site_semantic_visual_to_composition",
]
