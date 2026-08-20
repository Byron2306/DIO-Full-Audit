from __future__ import annotations

import json
import re
from typing import Any, Callable

from adapters.format_core.visual_composer import SCHEMA as COMPOSITION_SCHEMA, content_hash


SEMANTIC_VISUAL_SCHEMA = "dio.format_core.semantic_visual.v1"
SEMANTIC_VISUAL_RENDERER_VERSION = "1.0.0"

# HOMS proved that visual form must follow the thing being represented. These
# are semantic visual kinds, not page-layout names. Site Studio uses the first
# group today; the HOMS-native group is reusable by assessment, learning,
# document, evidence and publication surfaces.
SITE_VISUAL_KINDS = {
    "research_workbench",
    "decision_landscape",
    "evidence_network",
    "communication_outputs",
    "method_map",
    "provenance_stack",
    "human_review_scene",
    "bounded_action",
}
HOMS_NATIVE_VISUAL_KINDS = {
    "quantitative_graph",
    "concept_map",
    "reference_frame",
    "circuit_schematic",
    "geographic_map",
}
SUPPORTED_VISUAL_KINDS = SITE_VISUAL_KINDS | HOMS_NATIVE_VISUAL_KINDS


class SemanticVisualError(RuntimeError):
    pass


def _clean(value: Any, limit: int = 360) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit].rstrip()


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean(value).casefold()).strip()


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
    radius: float = 12,
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


def _header(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Small orientation header. The visual, not a slide title, owns the canvas."""
    title = _clean(spec.get("title") or spec.get("visual_kind"), 110)
    summary = _clean(spec.get("summary"), 190)
    components = [
        _text("semantic-title", 58, 58, title, size=26, weight="900", wrap_chars=54, max_lines=1),
        _text(
            "semantic-kind",
            1222,
            58,
            str(spec.get("visual_kind") or "").replace("_", " ").upper(),
            size=12,
            weight="900",
            fill="$accent",
            anchor="end",
        ),
        _line("semantic-rule", 58, 82, 1222, 82, stroke="$line", stroke_width=1.5),
    ]
    if summary:
        components.append(_text("semantic-summary", 58, 110, summary, size=14, weight="600", fill="$muted", wrap_chars=110, max_lines=1))
    return components


def _entity_labels(spec: dict[str, Any]) -> list[str]:
    return [_clean(row.get("label"), 48) for row in spec.get("entities") or [] if _clean(row.get("label"), 48)]


def _render_research_workbench(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _header(spec)
    # A literal research desk: overlapping source sheets, marginalia, a decision
    # question and a bounded output. This deliberately does not read as a UI.
    c.extend(
        [
            _panel("source-sheet-a", 72, 182, 360, 392, fill="$surface", stroke="$line", radius=2),
            _panel("source-sheet-b", 112, 154, 360, 392, fill="$surface_alt", stroke="$line", radius=2),
            _text("source-a-label", 142, 198, "SOURCE MATERIAL", size=14, weight="900", fill="$accent"),
            _line("source-a-line1", 142, 230, 414, 230),
            _line("source-a-line2", 142, 257, 392, 257),
            _line("source-a-line3", 142, 284, 428, 284),
            _line("source-a-line4", 142, 338, 392, 338),
            _line("source-a-line5", 142, 365, 420, 365),
            _path("annotation-ring", "M156 309 C205 281 285 282 344 309 C286 336 205 337 156 309 Z", stroke="$warning", stroke_width=3),
            _text("annotation-note", 152, 422, "uncertainty\nmarked, not erased", size=18, weight="800", fill="$warning", wrap_chars=20, max_lines=2, line_gap=22),
            _circle("question-lens", 680, 334, 134, fill="$paper", stroke="$accent", stroke_width=5),
            _text("question-label", 680, 314, "QUESTION", size=15, weight="900", fill="$accent", anchor="middle"),
            _text("question-body", 680, 355, "What decision\nmust this evidence support?", size=22, weight="900", anchor="middle", wrap_chars=20, max_lines=2, line_gap=28),
            _panel("decision-sheet", 902, 188, 300, 358, fill="$surface", stroke="$accent", stroke_width=2.5, radius=4),
            _text("decision-kicker", 932, 228, "DECISION BRIEF", size=15, weight="900", fill="$accent"),
            _text("decision-title", 932, 278, "Evidence translated\ninto a usable decision", size=24, weight="900", wrap_chars=22, max_lines=2, line_gap=30),
            _line("decision-rule1", 932, 360, 1162, 360),
            _line("decision-rule2", 932, 392, 1128, 392),
            _line("decision-rule3", 932, 424, 1150, 424),
            _circle("decision-gate", 1060, 492, 24, fill="$paper", stroke="$warning", stroke_width=4),
            _text("decision-gate-label", 1098, 499, "HUMAN REVIEW", size=14, weight="900", fill="$warning"),
            _text("desk-caption", 72, 642, "Evidence is handled as material with provenance, gaps and consequence, not as decorative dashboard content.", size=16, weight="700", fill="$muted", wrap_chars=104, max_lines=2),
        ]
    )
    return c


def _render_decision_landscape(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _header(spec)
    c.extend(
        [
            _line("axis-horizontal", 112, 384, 1168, 384, stroke="$line", stroke_width=2),
            _line("axis-vertical", 640, 160, 640, 620, stroke="$line", stroke_width=2),
            _circle("decision-core", 640, 384, 116, fill="$surface_alt", stroke="$accent", stroke_width=4),
            _text("decision-core-k", 640, 356, "DECISION", size=14, weight="900", fill="$accent", anchor="middle"),
            _text("decision-core-v", 640, 397, "What must be\nknown to act?", size=23, weight="900", anchor="middle", wrap_chars=15, max_lines=2, line_gap=28),
            _circle("evidence-node", 306, 258, 78, fill="$surface", stroke="$accent", stroke_width=3),
            _text("evidence-node-label", 306, 250, "EVIDENCE", size=16, weight="900", fill="$accent", anchor="middle"),
            _text("evidence-node-sub", 306, 282, "what is known", size=13, weight="700", fill="$muted", anchor="middle"),
            _circle("stakeholder-node", 974, 258, 78, fill="$surface", stroke="$warning", stroke_width=3),
            _text("stakeholder-node-label", 974, 250, "STAKEHOLDER", size=15, weight="900", fill="$warning", anchor="middle"),
            _text("stakeholder-node-sub", 974, 282, "who carries it", size=13, weight="700", fill="$muted", anchor="middle"),
            _circle("uncertainty-node", 306, 520, 78, fill="$paper", stroke="$warning", stroke_width=3),
            _text("uncertainty-node-label", 306, 512, "UNCERTAINTY", size=15, weight="900", fill="$warning", anchor="middle"),
            _text("uncertainty-node-sub", 306, 544, "what is missing", size=13, weight="700", fill="$muted", anchor="middle"),
            _circle("boundary-node", 974, 520, 78, fill="$paper", stroke="$accent", stroke_width=3),
            _text("boundary-node-label", 974, 512, "BOUNDARY", size=15, weight="900", fill="$accent", anchor="middle"),
            _text("boundary-node-sub", 974, 544, "what remains human", size=13, weight="700", fill="$muted", anchor="middle"),
            _line("landscape-link-a", 372, 300, 540, 348, stroke="$accent", stroke_width=2.5),
            _line("landscape-link-b", 908, 300, 740, 348, stroke="$warning", stroke_width=2.5),
            _line("landscape-link-c", 372, 478, 540, 420, stroke="$warning", stroke_width=2.5),
            _line("landscape-link-d", 908, 478, 740, 420, stroke="$accent", stroke_width=2.5),
        ]
    )
    return c


def _render_evidence_network(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _header(spec)
    # Network topology: different node types and relationship semantics. No
    # start/end ordering is implied.
    nodes = {
        "source-a": (158, 238, "SOURCE A", "$accent"),
        "source-b": (158, 500, "SOURCE B", "$accent"),
        "claim": (470, 300, "CLAIM", "$ink"),
        "contradiction": (470, 478, "TENSION", "$warning"),
        "synthesis": (770, 384, "SYNTHESIS", "$accent"),
        "reviewer": (1092, 384, "REVIEWER", "$warning"),
    }
    links = [
        ("link-a", 222, 238, 408, 300, "$accent", "supports", 306, 252),
        ("link-b", 222, 500, 408, 478, "$warning", "conflicts", 306, 474),
        ("link-c", 532, 300, 690, 358, "$line", "tested", 610, 314),
        ("link-d", 532, 478, 690, 410, "$warning", "retained", 608, 454),
        ("link-e", 850, 384, 1014, 384, "$accent", "reviewed by", 928, 366),
    ]
    for component_id, x1, y1, x2, y2, stroke, label, lx, ly in links:
        c.append(_line(component_id, x1, y1, x2, y2, stroke=stroke, stroke_width=3))
        c.append(_text(component_id + "-label", lx, ly, label, size=12, weight="800", fill=stroke, anchor="middle"))
    for node_id, (cx, cy, label, stroke) in nodes.items():
        radius = 76 if node_id in {"synthesis", "reviewer"} else 62
        c.append(_circle(node_id, cx, cy, radius, fill="$surface", stroke=stroke, stroke_width=3.5))
        c.append(_text(node_id + "-label", cx, cy + 6, label, size=15, weight="900", fill=stroke, anchor="middle"))
    c.append(_text("network-caption", 640, 620, "Agreement and contradiction remain visible in the same evidence field.", size=17, weight="800", fill="$muted", anchor="middle"))
    return c


def _render_communication_outputs(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _header(spec)
    # One governed meaning expressed through three genuinely different output
    # objects: report page, presentation canvas and public explanation.
    c.extend(
        [
            _circle("meaning-core", 278, 384, 108, fill="$surface_alt", stroke="$accent", stroke_width=4),
            _text("meaning-core-a", 278, 368, "GOVERNED", size=14, weight="900", fill="$accent", anchor="middle"),
            _text("meaning-core-b", 278, 404, "MEANING", size=24, weight="900", anchor="middle"),
            _line("meaning-ray-a", 386, 326, 540, 245, stroke="$line", stroke_width=2.5),
            _line("meaning-ray-b", 386, 384, 540, 384, stroke="$line", stroke_width=2.5),
            _line("meaning-ray-c", 386, 442, 540, 523, stroke="$line", stroke_width=2.5),
            _panel("report-sheet", 556, 170, 220, 178, fill="$surface", stroke="$accent", stroke_width=2.5, radius=3),
            _text("report-label", 578, 202, "REPORT", size=14, weight="900", fill="$accent"),
            _line("report-line1", 578, 232, 744, 232),
            _line("report-line2", 578, 258, 724, 258),
            _line("report-line3", 578, 284, 740, 284),
            _line("report-line4", 578, 310, 700, 310),
            _panel("presentation-screen", 556, 362, 284, 148, fill="$surface_alt", stroke="$warning", stroke_width=2.5, radius=4),
            _text("presentation-label", 698, 412, "PRESENTATION", size=16, weight="900", fill="$warning", anchor="middle"),
            _path("presentation-mark", "M612 472 L652 438 L692 456 L748 408 L786 430", stroke="$accent", stroke_width=5),
            _panel("public-field", 880, 214, 300, 308, fill="$paper", stroke="$line", stroke_width=2, radius=20),
            _circle("public-person", 950, 310, 34, fill="$surface_alt", stroke="$ink", stroke_width=3),
            _path("public-body", "M904 426 C914 366 986 366 996 426", fill="$surface_alt", stroke="$ink", stroke_width=3),
            _text("public-label", 1080, 300, "PUBLIC", size=14, weight="900", fill="$accent", anchor="middle"),
            _text("public-body-label", 1080, 340, "EXPLANATION", size=17, weight="900", anchor="middle"),
            _text("public-sub", 1080, 390, "same meaning\nnew surface", size=14, weight="700", fill="$muted", anchor="middle", wrap_chars=14, max_lines=2, line_gap=19),
            _text("communication-caption", 640, 610, "Surface changes. Meaning, provenance and human release boundary do not.", size=17, weight="800", fill="$muted", anchor="middle"),
        ]
    )
    return c


def _render_method_map(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _header(spec)
    # Spatial method map. It has relationships, but no single horizontal
    # timeline. The review state is the semantic centre.
    c.extend(
        [
            _circle("method-core", 650, 390, 112, fill="$surface_alt", stroke="$accent", stroke_width=4),
            _text("method-core-a", 650, 370, "REVIEWABLE", size=15, weight="900", fill="$accent", anchor="middle"),
            _text("method-core-b", 650, 410, "HANDOFF", size=23, weight="900", anchor="middle"),
            _panel("method-question", 90, 190, 280, 146, fill="$surface", stroke="$line", radius=5),
            _text("method-question-k", 116, 226, "QUESTION", size=14, weight="900", fill="$accent"),
            _text("method-question-v", 116, 268, "Decision context\nbefore automation", size=20, weight="900", wrap_chars=21, max_lines=2, line_gap=25),
            _panel("method-source", 94, 462, 320, 142, fill="$surface", stroke="$line", radius=3),
            _text("method-source-k", 120, 498, "SUPPLIED MATERIAL", size=14, weight="900", fill="$accent"),
            _line("method-source-l1", 120, 532, 360, 532),
            _line("method-source-l2", 120, 558, 330, 558),
            _circle("method-gap", 1024, 226, 72, fill="$paper", stroke="$warning", stroke_width=4),
            _text("method-gap-k", 1024, 220, "GAPS", size=15, weight="900", fill="$warning", anchor="middle"),
            _text("method-gap-v", 1024, 250, "exposed", size=13, weight="700", fill="$muted", anchor="middle"),
            _panel("method-reviewer", 910, 452, 270, 144, fill="$surface", stroke="$warning", stroke_width=2.5, radius=18),
            _circle("method-reviewer-head", 960, 504, 24, fill="$surface_alt", stroke="$ink", stroke_width=2.5),
            _path("method-reviewer-body", "M928 574 C934 532 986 532 992 574", fill="$surface_alt", stroke="$ink", stroke_width=2.5),
            _text("method-reviewer-label", 1080, 520, "HUMAN", size=14, weight="900", fill="$warning", anchor="middle"),
            _text("method-reviewer-sub", 1080, 550, "judgement", size=15, weight="800", anchor="middle"),
            _line("method-link-a", 370, 284, 548, 348, stroke="$line", stroke_width=2.5),
            _line("method-link-b", 414, 520, 548, 438, stroke="$accent", stroke_width=2.5),
            _line("method-link-c", 762, 344, 952, 252, stroke="$warning", stroke_width=2.5),
            _line("method-link-d", 762, 438, 910, 516, stroke="$accent", stroke_width=2.5),
        ]
    )
    return c


def _render_provenance_stack(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _header(spec)
    sheets = [
        (168, 214, 560, 324, "$line", "SOURCE MATERIAL", "hash-bound input"),
        (212, 242, 560, 324, "$warning", "SEMANTIC LAW", "meaning versioned"),
        (256, 270, 560, 324, "$accent", "PROJECTION", "customer surface traceable"),
    ]
    for index, (x, y, w, h, stroke, label, sub) in enumerate(sheets, 1):
        c.append(_panel(f"prov-sheet-{index}", x, y, w, h, fill="$surface", stroke=stroke, stroke_width=2.5, radius=3))
        c.append(_text(f"prov-label-{index}", x + 30, y + 42, label, size=15, weight="900", fill=stroke))
        c.append(_text(f"prov-sub-{index}", x + 30, y + 76, sub, size=14, weight="700", fill="$muted"))
        c.append(_line(f"prov-line-{index}-a", x + 30, y + 116, x + w - 36, y + 116))
        c.append(_line(f"prov-line-{index}-b", x + 30, y + 146, x + w - 80, y + 146))
    c.extend(
        [
            _circle("prov-inspection", 1008, 360, 124, fill="$paper", stroke="$accent", stroke_width=5),
            _text("prov-inspection-k", 1008, 334, "INSPECT", size=15, weight="900", fill="$accent", anchor="middle"),
            _text("prov-inspection-v", 1008, 378, "claim → source", size=20, weight="900", anchor="middle"),
            _text("prov-inspection-h", 1008, 414, "without losing lineage", size=13, weight="700", fill="$muted", anchor="middle"),
            _path("prov-bracket", "M862 218 L900 218 L900 528 L862 528", stroke="$warning", stroke_width=4),
            _text("prov-bracket-label", 920, 548, "review boundary", size=14, weight="900", fill="$warning"),
        ]
    )
    return c


def _render_human_review_scene(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _header(spec)
    c.extend(
        [
            _panel("review-document", 98, 178, 500, 388, fill="$surface", stroke="$accent", stroke_width=2.5, radius=4),
            _text("review-doc-k", 132, 222, "PREPARED WORK", size=15, weight="900", fill="$accent"),
            _line("review-doc-l1", 132, 262, 548, 262),
            _line("review-doc-l2", 132, 294, 508, 294),
            _line("review-doc-l3", 132, 326, 536, 326),
            _path("review-mark-a", "M150 410 L176 436 L224 378", stroke="$accent", stroke_width=6),
            _path("review-mark-b", "M306 398 L354 446 M354 398 L306 446", stroke="$warning", stroke_width=6),
            _text("review-mark-a-label", 150, 482, "accept", size=14, weight="800", fill="$accent"),
            _text("review-mark-b-label", 306, 482, "change", size=14, weight="800", fill="$warning"),
            _circle("review-human-head", 908, 260, 62, fill="$surface_alt", stroke="$ink", stroke_width=4),
            _path("review-human-body", "M786 536 C800 360 1016 360 1030 536", fill="$surface_alt", stroke="$ink", stroke_width=4),
            _text("review-human-k", 908, 590, "AUTHORISED HUMAN", size=17, weight="900", fill="$warning", anchor="middle"),
            _line("review-gaze", 598, 356, 764, 332, stroke="$line", stroke_width=3),
            _circle("review-release", 1112, 464, 50, fill="$paper", stroke="$warning", stroke_width=4),
            _text("review-release-a", 1112, 456, "RELEASE", size=12, weight="900", fill="$warning", anchor="middle"),
            _text("review-release-b", 1112, 480, "HELD", size=15, weight="900", anchor="middle"),
        ]
    )
    return c


def _render_bounded_action(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _header(spec)
    c.extend(
        [
            _panel("action-intake", 110, 176, 570, 392, fill="$surface", stroke="$accent", stroke_width=3, radius=4),
            _text("action-intake-k", 148, 218, "ONE REAL JOB", size=15, weight="900", fill="$accent"),
            _text("action-intake-v", 148, 270, "Decision context", size=28, weight="900"),
            _line("action-field-a", 148, 318, 626, 318),
            _text("action-field-a-label", 148, 348, "supplied material", size=13, weight="800", fill="$muted"),
            _line("action-field-b", 148, 394, 626, 394),
            _text("action-field-b-label", 148, 424, "what needs deciding", size=13, weight="800", fill="$muted"),
            _line("action-field-c", 148, 470, 626, 470),
            _text("action-field-c-label", 148, 500, "who has authority", size=13, weight="800", fill="$muted"),
            _circle("action-gate", 972, 356, 152, fill="$surface_alt", stroke="$accent", stroke_width=5),
            _text("action-gate-k", 972, 326, "BOUNDED", size=15, weight="900", fill="$accent", anchor="middle"),
            _text("action-gate-v", 972, 370, "START", size=34, weight="900", anchor="middle"),
            _text("action-gate-sub", 972, 410, "one artifact\none review", size=14, weight="800", fill="$muted", anchor="middle", wrap_chars=14, max_lines=2, line_gap=19),
            _path("action-check", "M900 514 L930 544 L1000 474", stroke="$accent", stroke_width=8),
            _text("action-caption", 972, 586, "No automatic release", size=15, weight="900", fill="$warning", anchor="middle"),
        ]
    )
    return c


def _render_quantitative_graph(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _header(spec)
    data = dict(spec.get("data") or {})
    points = list(data.get("points") or [(0, 0), (1, 2), (2, 3), (3, 5)])
    left, top, right, bottom = 150, 176, 1168, 602
    c.extend([
        _line("graph-x", left, bottom, right, bottom, stroke="$ink", stroke_width=4),
        _line("graph-y", left, bottom, left, top, stroke="$ink", stroke_width=4),
        _text("graph-x-label", right, 650, str(data.get("x_label") or "x"), size=16, weight="900", anchor="end"),
        _text("graph-y-label", 72, top, str(data.get("y_label") or "y"), size=16, weight="900"),
    ])
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    xspan = xmax - xmin or 1.0
    yspan = ymax - ymin or 1.0
    coords: list[tuple[float, float]] = []
    for x, y in zip(xs, ys):
        px = left + (x - xmin) / xspan * (right - left)
        py = bottom - (y - ymin) / yspan * (bottom - top)
        coords.append((px, py))
    for index, ((x1, y1), (x2, y2)) in enumerate(zip(coords, coords[1:]), 1):
        c.append(_line(f"graph-segment-{index}", x1, y1, x2, y2, stroke="$accent", stroke_width=5))
    for index, (px, py) in enumerate(coords, 1):
        c.append(_circle(f"graph-point-{index}", px, py, 8, fill="$warning", stroke="$ink", stroke_width=2))
    return c


def _render_concept_map(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _header(spec)
    labels = _entity_labels(spec) or ["Input A", "Input B", "Core concept", "Output A", "Output B"]
    labels = (labels + ["Input A", "Input B", "Core concept", "Output A", "Output B"])[:5]
    positions = [(210, 230), (210, 520), (640, 374), (1070, 230), (1070, 520)]
    for index, ((cx, cy), label) in enumerate(zip(positions, labels), 1):
        if index == 3:
            c.append(_panel(f"concept-node-{index}", cx - 130, cy - 62, 260, 124, fill="$surface_alt", stroke="$accent", stroke_width=3, radius=12))
            c.append(_text(f"concept-label-{index}", cx, cy + 8, label, size=22, weight="900", anchor="middle", wrap_chars=20, max_lines=2, line_gap=25))
        else:
            c.append(_panel(f"concept-node-{index}", cx - 120, cy - 54, 240, 108, fill="$surface", stroke="$accent", stroke_width=2.5, radius=12))
            c.append(_text(f"concept-label-{index}", cx, cy + 8, label, size=18, weight="900", anchor="middle", wrap_chars=18, max_lines=2, line_gap=22))
    for index, (x1, y1, x2, y2) in enumerate([(330, 230, 510, 340), (330, 520, 510, 410), (770, 340, 950, 230), (770, 410, 950, 520)], 1):
        c.append(_line(f"concept-link-{index}", x1, y1, x2, y2, stroke="$accent", stroke_width=3))
    return c


def _render_reference_frame(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _header(spec)
    y = 390
    c.extend([
        _line("ref-axis", 120, y, 1160, y, stroke="$ink", stroke_width=5),
        _path("ref-arrow-east", "M1160 390 L1124 370 L1124 410 Z", fill="$accent", stroke="$accent", stroke_width=1),
        _text("ref-west", 120, 338, "WEST (-)", size=18, weight="900", fill="$warning"),
        _text("ref-east", 1160, 338, "EAST (+)", size=18, weight="900", fill="$accent", anchor="end"),
        _panel("ref-object", 564, 260, 180, 90, fill="$warning", stroke="$ink", stroke_width=3, radius=4),
        _circle("ref-wheel-a", 606, 350, 25, fill="$ink", stroke="$ink"),
        _circle("ref-wheel-b", 704, 350, 25, fill="$ink", stroke="$ink"),
        _text("ref-object-label", 654, 312, str((spec.get("data") or {}).get("object") or "OBJECT"), size=21, weight="900", anchor="middle"),
        _line("ref-velocity", 650, 220, 896, 220, stroke="$accent", stroke_width=6),
        _path("ref-velocity-arrow", "M896 220 L858 200 L858 240 Z", fill="$accent", stroke="$accent", stroke_width=1),
        _text("ref-velocity-label", 654, 192, "positive direction", size=17, weight="900", fill="$accent"),
    ])
    for index, value in enumerate([-20, -10, 0, 10, 20, 30]):
        x = 300 + index * 145
        c.append(_line(f"ref-tick-{index}", x, y - 16, x, y + 16, stroke="$ink", stroke_width=3))
        c.append(_text(f"ref-tick-label-{index}", x, y + 48, f"{value}", size=15, weight="800", anchor="middle"))
    return c


def _render_circuit_schematic(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _header(spec)
    # Deliberately schematic rather than card-based: cell, ammeter, resistor,
    # external loop and voltmeter branch.
    c.extend([
        _line("circuit-top-a", 120, 270, 310, 270, stroke="$ink", stroke_width=5),
        _line("circuit-cell-long", 310, 228, 310, 312, stroke="$ink", stroke_width=4),
        _line("circuit-cell-short", 338, 244, 338, 296, stroke="$ink", stroke_width=8),
        _line("circuit-top-b", 338, 270, 500, 270, stroke="$ink", stroke_width=5),
        _circle("circuit-ammeter", 555, 270, 52, fill="$paper", stroke="$ink", stroke_width=5),
        _text("circuit-ammeter-label", 555, 279, "A", size=28, weight="900", anchor="middle"),
        _line("circuit-top-c", 607, 270, 760, 270, stroke="$ink", stroke_width=5),
        _panel("circuit-resistor", 760, 232, 244, 76, fill="$paper", stroke="$ink", stroke_width=4, radius=0),
        _text("circuit-resistor-label", 882, 279, "VARIABLE RESISTOR", size=16, weight="900", anchor="middle"),
        _path("circuit-resistor-arrow", "M800 340 L968 202 M968 202 L934 214 M968 202 L952 236", stroke="$warning", stroke_width=5),
        _line("circuit-top-d", 1004, 270, 1140, 270, stroke="$ink", stroke_width=5),
        _line("circuit-right", 1140, 270, 1140, 494, stroke="$ink", stroke_width=5),
        _line("circuit-bottom", 1140, 494, 120, 494, stroke="$ink", stroke_width=5),
        _line("circuit-left", 120, 494, 120, 270, stroke="$ink", stroke_width=5),
        _line("circuit-volt-a", 310, 312, 310, 570, stroke="$accent", stroke_width=4),
        _line("circuit-volt-b", 310, 570, 500, 570, stroke="$accent", stroke_width=4),
        _circle("circuit-voltmeter", 555, 570, 52, fill="$paper", stroke="$accent", stroke_width=5),
        _text("circuit-voltmeter-label", 555, 579, "V", size=28, weight="900", fill="$accent", anchor="middle"),
        _line("circuit-volt-c", 607, 570, 607, 494, stroke="$accent", stroke_width=4),
    ])
    return c


def _render_geographic_map(spec: dict[str, Any]) -> list[dict[str, Any]]:
    c = _header(spec)
    left, top, right, bottom = 82, 160, 930, 620
    c.append(_panel("map-frame", left, top, right - left, bottom - top, fill="$paper", stroke="$ink", stroke_width=3, radius=0))
    for i in range(1, 6):
        x = left + i * (right - left) / 6
        c.append(_line(f"map-grid-v-{i}", x, top, x, bottom, stroke="$line", stroke_width=1))
    for i in range(1, 4):
        y = top + i * (bottom - top) / 4
        c.append(_line(f"map-grid-h-{i}", left, y, right, y, stroke="$line", stroke_width=1))
    c.extend([
        _path("map-river", "M140 180 C240 246 310 310 430 352 C548 395 654 486 876 570", stroke="$accent", stroke_width=9),
        _path("map-road", "M110 548 C300 520 420 468 530 352 C650 226 760 220 870 180", stroke="$warning", stroke_width=7),
        _line("map-rail-a", 154, 430, 820, 430, stroke="$muted", stroke_width=6),
        _circle("map-mine", 200, 430, 34, fill="$warning", stroke="$ink", stroke_width=3),
        _panel("map-zone", 590, 344, 150, 104, fill="$surface_alt", stroke="$warning", stroke_width=3, radius=0),
        _text("map-zone-label", 665, 392, "ZONE", size=17, weight="900", fill="$warning", anchor="middle"),
        _panel("map-port", 824, 394, 64, 64, fill="$surface", stroke="$ink", stroke_width=3, radius=0),
        _text("map-port-label", 856, 432, "PORT", size=12, weight="900", anchor="middle"),
        _panel("map-legend", 972, 210, 226, 260, fill="$surface", stroke="$ink", stroke_width=2.5, radius=2),
        _text("map-legend-title", 994, 246, "LEGEND", size=18, weight="900"),
        _line("map-legend-river", 996, 294, 1034, 294, stroke="$accent", stroke_width=7),
        _text("map-legend-river-t", 1050, 300, "river", size=14, weight="700"),
        _line("map-legend-road", 996, 338, 1034, 338, stroke="$warning", stroke_width=7),
        _text("map-legend-road-t", 1050, 344, "road", size=14, weight="700"),
        _circle("map-legend-mine", 1015, 382, 11, fill="$warning", stroke="$ink", stroke_width=1.5),
        _text("map-legend-mine-t", 1050, 388, "site", size=14, weight="700"),
        _line("map-north", 1084, 570, 1084, 510, stroke="$ink", stroke_width=5),
        _path("map-north-arrow", "M1084 486 L1068 518 L1100 518 Z", fill="$ink", stroke="$ink", stroke_width=1),
        _text("map-north-label", 1084, 604, "N", size=18, weight="900", anchor="middle"),
        _line("map-scale", 976, 642, 1168, 642, stroke="$ink", stroke_width=5),
        _line("map-scale-a", 976, 630, 976, 654, stroke="$ink", stroke_width=3),
        _line("map-scale-b", 1072, 630, 1072, 654, stroke="$ink", stroke_width=3),
        _line("map-scale-c", 1168, 630, 1168, 654, stroke="$ink", stroke_width=3),
        _text("map-scale-label", 1072, 680, "0      10      20 km", size=13, weight="800", anchor="middle"),
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
    "quantitative_graph": _render_quantitative_graph,
    "concept_map": _render_concept_map,
    "reference_frame": _render_reference_frame,
    "circuit_schematic": _render_circuit_schematic,
    "geographic_map": _render_geographic_map,
}


def validate_semantic_visual(spec: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if spec.get("schema") != SEMANTIC_VISUAL_SCHEMA:
        errors.append(f"schema must be {SEMANTIC_VISUAL_SCHEMA}")
    if not _clean(spec.get("visual_id")):
        errors.append("visual_id is required")
    kind = str(spec.get("visual_kind") or "")
    if kind not in SUPPORTED_VISUAL_KINDS:
        errors.append(f"unsupported visual_kind: {kind or '(missing)'}")
    if not _clean(spec.get("semantic_intent")):
        errors.append("semantic_intent is required")
    source = dict(spec.get("source") or {})
    if source.get("role_selects_geometry") is not False:
        errors.append("role_selects_geometry must be false")
    if spec.get("geometry_selector") != "semantic_visual_kind_registry":
        errors.append("geometry_selector must be semantic_visual_kind_registry")
    return {"passed": not errors, "errors": errors, "visual_kind": kind}


def _site_visual_kind(scene: dict[str, Any]) -> tuple[str, str]:
    """Resolve semantic visual kind from meaning, never from role identity.

    Role is intentionally absent from this selector. The same role can compile to
    different geometry when its semantic content changes.
    """
    title = _norm(scene.get("display_copy") or scene.get("screen_text"))
    narration = _norm(scene.get("narration"))
    subject = _norm(scene.get("visual_subject") or scene.get("visual"))
    focus = _norm(scene.get("semantic_focus"))
    text = " ".join([title, narration, subject, focus])

    if any(token in text for token in ["professional judgment", "professional judgement", "human authority", "human review moment", "authority visibly exercised"]):
        return "human_review_scene", "show where consequential judgement and release authority physically sit"
    if any(token in text for token in ["inspect the trail", "source lineage", "provenance", "proof object", "traceability"]):
        return "provenance_stack", "make source lineage and proof inspection the visual subject"
    if any(token in text for token in ["evidence synthesis", "source fragments", "compared and synthesised", "claims sources", "contradiction"]):
        return "evidence_network", "show sources, claims, tensions, synthesis and review as a non-linear evidence field"
    if any(token in text for token in ["decision communication", "reports presentations", "public facing explanations", "translate governed meaning"]):
        return "communication_outputs", "show one governed meaning projected into distinct professional communication artifacts"
    if any(token in text for token in ["research strategy", "frame complex questions", "evidence needs", "decision contexts"]):
        return "decision_landscape", "show the decision context as evidence, stakeholder, uncertainty and authority dimensions"
    if any(token in text for token in ["from question to reviewable handoff", "work begins with the decision context", "binds supplied material", "exposes uncertainty"]):
        return "method_map", "show the method as a spatial working system rather than a timeline"
    if any(token in text for token in ["start with the decision context", "one calm concrete next action", "bounded next step", "one real workflow"]):
        return "bounded_action", "make the next customer action a single bounded intake object"
    return "research_workbench", "show the actual research workbench: source material, uncertainty, question and decision artifact"


def _site_entities(kind: str) -> list[dict[str, str]]:
    presets: dict[str, list[tuple[str, str, str]]] = {
        "research_workbench": [
            ("source", "Source material", "evidence_object"),
            ("uncertainty", "Uncertainty", "annotation"),
            ("question", "Decision question", "decision_context"),
            ("brief", "Decision brief", "customer_artifact"),
            ("review", "Human review", "authority"),
        ],
        "decision_landscape": [
            ("evidence", "Evidence", "evidence"),
            ("stakeholder", "Stakeholder", "actor"),
            ("uncertainty", "Uncertainty", "gap"),
            ("boundary", "Boundary", "authority"),
            ("decision", "Decision", "decision"),
        ],
        "evidence_network": [
            ("source_a", "Source A", "source"),
            ("source_b", "Source B", "source"),
            ("claim", "Claim", "claim"),
            ("tension", "Contradiction", "exception"),
            ("synthesis", "Synthesis", "analysis"),
            ("reviewer", "Reviewer", "authority"),
        ],
        "communication_outputs": [
            ("meaning", "Governed meaning", "semantic_object"),
            ("report", "Report", "document"),
            ("presentation", "Presentation", "presentation"),
            ("public", "Public explanation", "public_surface"),
        ],
        "method_map": [
            ("question", "Decision context", "question"),
            ("source", "Supplied material", "source"),
            ("gap", "Uncertainty", "gap"),
            ("handoff", "Reviewable handoff", "artifact"),
            ("reviewer", "Human judgement", "authority"),
        ],
        "provenance_stack": [
            ("source", "Source material", "source"),
            ("law", "Semantic law", "semantic_contract"),
            ("projection", "Projection", "surface"),
            ("inspection", "Inspection", "proof"),
        ],
        "human_review_scene": [
            ("prepared", "Prepared work", "artifact"),
            ("reviewer", "Authorised human", "authority"),
            ("release", "Release held", "gate"),
        ],
        "bounded_action": [
            ("job", "One real job", "intake"),
            ("context", "Decision context", "context"),
            ("authority", "Named authority", "authority"),
            ("gate", "Bounded start", "gate"),
        ],
    }
    return [{"id": item_id, "label": label, "kind": entity_kind} for item_id, label, entity_kind in presets.get(kind, [])]


def compile_site_semantic_visual(
    *,
    scene: dict[str, Any],
    story: dict[str, Any],
    directed: dict[str, Any],
) -> dict[str, Any]:
    merged = {**scene, **directed}
    kind, intent = _site_visual_kind(merged)
    title = _clean(directed.get("display_copy") or scene.get("screen_text") or kind, 120)
    summary = _clean(directed.get("visual_subject") or scene.get("visual") or scene.get("narration"), 240)
    core = {
        "schema": SEMANTIC_VISUAL_SCHEMA,
        "renderer_version": SEMANTIC_VISUAL_RENDERER_VERSION,
        "visual_id": f"SITE-{_clean(scene.get('scene_id') or 'scene', 80)}",
        "surface": "website",
        "visual_kind": kind,
        "semantic_intent": intent,
        "title": title,
        "summary": summary,
        "entities": _site_entities(kind),
        "relationships": [],
        "geometry_selector": "semantic_visual_kind_registry",
        "source": {
            "scene_id": scene.get("scene_id"),
            "role": scene.get("role"),
            "semantic_focus": scene.get("semantic_focus"),
            "story_hash": story.get("story_hash"),
            "directed_layout_family": directed.get("layout_family"),
            "role_selects_geometry": False,
        },
        "governance": {
            "semantic_authority": "DIO_SITE_STUDIO",
            "visual_semantic_compiler": "DIO_FORMAT_CORE",
            "geometry_authority": "DIO_FORMAT_CORE",
            "external_provider_layout_authority": "REFUSE",
            "authority_created": False,
        },
    }
    spec = {**core, "semantic_visual_hash": content_hash(core)}
    validation = validate_semantic_visual(spec)
    if not validation["passed"]:
        raise SemanticVisualError("invalid Site semantic visual: " + "; ".join(validation["errors"]))
    return spec


def semantic_visual_to_composition(
    spec: dict[str, Any],
    *,
    profile_id: str,
    width: int = 1280,
    height: int = 720,
    binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validation = validate_semantic_visual(spec)
    if not validation["passed"]:
        raise SemanticVisualError("invalid semantic visual: " + "; ".join(validation["errors"]))
    kind = str(spec["visual_kind"])
    components = _RENDERERS[kind](spec)
    composition = {
        "schema": COMPOSITION_SCHEMA,
        "composition_id": str(spec["visual_id"]),
        "title": _clean(spec.get("title") or kind, 120),
        "profile_id": profile_id,
        "canvas": {"width": width, "height": height, "background": "$paper"},
        "components": components,
        "binding": {
            "semantic_visual_schema": SEMANTIC_VISUAL_SCHEMA,
            "semantic_visual_hash": spec.get("semantic_visual_hash") or content_hash(spec),
            "visual_kind": kind,
            "semantic_intent": spec.get("semantic_intent"),
            "geometry_selector": "semantic_visual_kind_registry",
            "role_selects_geometry": False,
            **dict(binding or {}),
        },
    }
    return composition


__all__ = [
    "HOMS_NATIVE_VISUAL_KINDS",
    "SEMANTIC_VISUAL_RENDERER_VERSION",
    "SEMANTIC_VISUAL_SCHEMA",
    "SITE_VISUAL_KINDS",
    "SUPPORTED_VISUAL_KINDS",
    "SemanticVisualError",
    "compile_site_semantic_visual",
    "semantic_visual_to_composition",
    "validate_semantic_visual",
]
