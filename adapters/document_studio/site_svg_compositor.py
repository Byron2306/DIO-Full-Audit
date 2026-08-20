from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any


WIDTH = 1440
HEIGHT = 900


class SiteSvgCompositorError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _clean(value: Any, limit: int = 260) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit].rstrip()


def _wrap(value: Any, width: int = 28, max_lines: int = 3) -> list[str]:
    words = _clean(value, 500).split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and len(candidate) > width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    return lines or [""]


def _text(lines: list[str], *, x: int, y: int, size: int, fill: str, weight: int = 700, gap: int | None = None, anchor: str = "start") -> str:
    line_gap = gap or round(size * 1.12)
    return "\n".join(
        f'<text x="{x}" y="{y + index * line_gap}" text-anchor="{anchor}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}">{_esc(line)}</text>'
        for index, line in enumerate(lines)
    )


def _palette(art: dict[str, Any]) -> dict[str, str]:
    raw = dict(art.get("format_core_palette") or {})

    def colour(key: str, fallback: str) -> str:
        value = str(raw.get(key) or fallback).strip().lstrip("#")
        return "#" + value if re.fullmatch(r"[0-9A-Fa-f]{6}", value) else fallback

    return {
        "ink": colour("ink", "#17212B"),
        "accent": colour("accent", "#146A6F"),
        "accent2": colour("accent_2", "#A13D2D"),
        "muted": colour("muted", "#5F6B76"),
        "line": colour("line", "#A8B7B5"),
        "paper": colour("paper", "#FFFFFF"),
        "fill": colour("fill", "#E8F0EE"),
        "night": "#0B1115",
        "warm": "#E8C47A",
        "white": "#FFFFFF",
    }


def _defs(p: dict[str, str]) -> str:
    return f"""
<defs>
  <linearGradient id="wash" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{p['night']}"/>
    <stop offset="1" stop-color="{p['ink']}"/>
  </linearGradient>
  <linearGradient id="signal" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{p['accent']}"/>
    <stop offset="1" stop-color="{p['warm']}"/>
  </linearGradient>
  <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
    <feDropShadow dx="0" dy="16" stdDeviation="18" flood-color="#000000" flood-opacity="0.22"/>
  </filter>
  <pattern id="grain" width="24" height="24" patternUnits="userSpaceOnUse">
    <circle cx="4" cy="7" r="1" fill="#ffffff" opacity="0.035"/>
    <circle cx="17" cy="15" r="1" fill="#ffffff" opacity="0.025"/>
    <circle cx="8" cy="21" r="0.8" fill="#ffffff" opacity="0.03"/>
  </pattern>
  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M 0 0 L 10 5 L 0 10 z" fill="{p['accent']}"/>
  </marker>
</defs>"""


def _frame(scene: dict[str, Any], p: dict[str, str], body: str, *, dark: bool = True) -> str:
    scene_id = _esc(scene.get("scene_id"))
    role = _clean(scene.get("role"), 60).replace("_", " ").upper()
    bg = "url(#wash)" if dark else p["paper"]
    label_fill = p["accent"] if dark else p["accent2"]
    title_fill = p["white"] if dark else p["ink"]
    title = _wrap(scene.get("display_copy") or scene.get("screen_text"), 28, 3)
    title_size = 54 if max(len(line) for line in title) < 25 else 46
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title-{scene_id} desc-{scene_id}">
<title id="title-{scene_id}">{_esc(scene.get('display_copy') or scene.get('screen_text'))}</title>
<desc id="desc-{scene_id}">{_esc(scene.get('visual_subject') or scene.get('visual'))}</desc>
{_defs(p)}
<rect width="{WIDTH}" height="{HEIGHT}" fill="{bg}"/>
<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#grain)"/>
<rect x="72" y="68" width="12" height="96" fill="{label_fill}"/>
<text x="112" y="94" font-family="Arial, Helvetica, sans-serif" font-size="18" font-weight="800" letter-spacing="3" fill="{label_fill}">{_esc(role)}</text>
{_text(title, x=112, y=150, size=title_size, fill=title_fill, weight=800, gap=round(title_size * 1.02))}
{body}
<text x="1368" y="844" text-anchor="end" font-family="Arial, Helvetica, sans-serif" font-size="14" font-weight="700" letter-spacing="2" fill="{p['muted']}">DIO · DOCUMENT STUDIO SVG</text>
</svg>"""


def _hook(scene: dict[str, Any], p: dict[str, str]) -> str:
    docs = []
    for index, (x, y, w, h, angle) in enumerate(((760, 210, 310, 390, -7), (955, 280, 330, 410, 5), (680, 390, 340, 330, -2)), 1):
        docs.append(f'<g transform="rotate({angle} {x + w/2} {y + h/2})" filter="url(#shadow)"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{p["paper"]}"/><rect x="{x + 26}" y="{y + 32}" width="{w - 52}" height="12" fill="{p["accent"]}" opacity="{0.25 + index * 0.12}"/><rect x="{x + 26}" y="{y + 74}" width="{w - 110}" height="8" fill="{p["line"]}"/><rect x="{x + 26}" y="{y + 104}" width="{w - 70}" height="8" fill="{p["line"]}"/><rect x="{x + 26}" y="{y + 134}" width="{w - 128}" height="8" fill="{p["line"]}"/><circle cx="{x + w - 52}" cy="{y + h - 52}" r="19" fill="none" stroke="{p["accent2"]}" stroke-width="4"/></g>')
    body = "".join(docs) + f'<path d="M585 520 C720 420 820 720 1030 600 S1290 480 1360 560" fill="none" stroke="{p["accent"]}" stroke-width="5" opacity=".75"/><circle cx="585" cy="520" r="10" fill="{p["warm"]}"/><circle cx="1360" cy="560" r="10" fill="{p["warm"]}"/>'
    return _frame(scene, p, body, dark=True)


def _strategy(scene: dict[str, Any], p: dict[str, str]) -> str:
    body = f"""
<circle cx="910" cy="465" r="104" fill="none" stroke="{p['accent']}" stroke-width="5"/>
<circle cx="910" cy="465" r="66" fill="{p['accent']}" opacity=".14"/>
<text x="910" y="455" text-anchor="middle" font-family="Arial" font-size="20" font-weight="800" fill="{p['ink']}">DECISION</text>
<text x="910" y="484" text-anchor="middle" font-family="Arial" font-size="16" fill="{p['muted']}">question</text>
<path d="M910 355 L760 245 M1010 390 L1180 275 M1010 540 L1200 650 M810 540 L650 665" fill="none" stroke="{p['line']}" stroke-width="3"/>
<g filter="url(#shadow)"><rect x="600" y="175" width="250" height="125" rx="8" fill="{p['paper']}"/><rect x="1070" y="185" width="260" height="125" rx="8" fill="{p['paper']}"/><rect x="1090" y="615" width="260" height="125" rx="8" fill="{p['paper']}"/><rect x="530" y="620" width="260" height="125" rx="8" fill="{p['paper']}"/></g>
<text x="630" y="218" font-family="Arial" font-size="18" font-weight="800" fill="{p['ink']}">SOURCE</text><text x="630" y="252" font-family="Arial" font-size="15" fill="{p['muted']}">context / constraint</text>
<text x="1100" y="228" font-family="Arial" font-size="18" font-weight="800" fill="{p['ink']}">STAKEHOLDER</text><text x="1100" y="262" font-family="Arial" font-size="15" fill="{p['muted']}">need / consequence</text>
<text x="1120" y="658" font-family="Arial" font-size="18" font-weight="800" fill="{p['ink']}">EVIDENCE</text><text x="1120" y="692" font-family="Arial" font-size="15" fill="{p['muted']}">support / uncertainty</text>
<text x="560" y="663" font-family="Arial" font-size="18" font-weight="800" fill="{p['ink']}">BOUNDARY</text><text x="560" y="697" font-family="Arial" font-size="15" fill="{p['muted']}">what remains unknown</text>"""
    return _frame(scene, p, body, dark=False)


def _synthesis(scene: dict[str, Any], p: dict[str, str]) -> str:
    fragments = []
    for index, (x, y, w) in enumerate(((620, 225, 300), (1010, 205, 280), (700, 610, 280), (1050, 590, 260)), 1):
        fragments.append(f'<g filter="url(#shadow)"><rect x="{x}" y="{y}" width="{w}" height="150" rx="8" fill="{p["paper"]}"/><rect x="{x + 20}" y="{y + 26}" width="{w - 40}" height="9" fill="{p["accent"]}" opacity=".22"/><rect x="{x + 20}" y="{y + 58}" width="{w - 72}" height="7" fill="{p["line"]}"/><rect x="{x + 20}" y="{y + 84}" width="{w - 45}" height="7" fill="{p["line"]}"/><text x="{x + 20}" y="{y + 128}" font-family="Arial" font-size="13" font-weight="800" fill="{p["muted"]}">SRC-{index:02d}</text></g>')
    body = "".join(fragments) + f'<path d="M920 350 C930 430 900 470 950 520 M1120 350 C1100 430 1040 470 990 520 M840 610 C875 560 900 545 950 520 M1170 590 C1120 550 1080 535 990 520" fill="none" stroke="{p["accent"]}" stroke-width="4"/><circle cx="970" cy="520" r="72" fill="{p["accent"]}"/><text x="970" y="512" text-anchor="middle" font-family="Arial" font-size="18" font-weight="800" fill="white">SYNTHESIS</text><text x="970" y="540" text-anchor="middle" font-family="Arial" font-size="14" fill="white">inspectable trail</text>'
    return _frame(scene, p, body, dark=True)


def _handoff(scene: dict[str, Any], p: dict[str, str]) -> str:
    body = f"""
<path d="M610 470 H1220" stroke="{p['accent']}" stroke-width="5" marker-end="url(#arrow)"/>
<g filter="url(#shadow)"><rect x="585" y="360" width="235" height="220" rx="10" fill="{p['paper']}"/><rect x="900" y="330" width="245" height="275" rx="10" fill="{p['paper']}"/></g>
<text x="615" y="405" font-family="Arial" font-size="18" font-weight="800" fill="{p['ink']}">EVIDENCE</text><rect x="615" y="438" width="150" height="8" fill="{p['line']}"/><rect x="615" y="468" width="170" height="8" fill="{p['line']}"/><rect x="615" y="498" width="125" height="8" fill="{p['line']}"/>
<text x="930" y="378" font-family="Arial" font-size="18" font-weight="800" fill="{p['ink']}">DECISION BRIEF</text><rect x="930" y="414" width="165" height="9" fill="{p['accent']}" opacity=".35"/><rect x="930" y="452" width="155" height="8" fill="{p['line']}"/><rect x="930" y="482" width="140" height="8" fill="{p['line']}"/><rect x="930" y="535" width="72" height="30" rx="15" fill="{p['accent']}"/><text x="966" y="555" text-anchor="middle" font-family="Arial" font-size="12" font-weight="800" fill="white">REVIEW</text>
<circle cx="1255" cy="470" r="72" fill="none" stroke="{p['warm']}" stroke-width="5"/><circle cx="1255" cy="442" r="22" fill="{p['warm']}"/><path d="M1208 520 Q1255 475 1302 520" fill="none" stroke="{p['warm']}" stroke-width="12" stroke-linecap="round"/>
<text x="1255" y="575" text-anchor="middle" font-family="Arial" font-size="14" font-weight="800" fill="{p['warm']}">HUMAN JUDGMENT</text>"""
    return _frame(scene, p, body, dark=True)


def _method(scene: dict[str, Any], p: dict[str, str]) -> str:
    labels = ["QUESTION", "SOURCE", "MAP", "REVIEW", "HANDOFF"]
    xs = [600, 770, 940, 1110, 1280]
    parts = [f'<path d="M600 500 H1280" stroke="{p["line"]}" stroke-width="4"/>']
    for index, (label, x) in enumerate(zip(labels, xs), 1):
        r = 38 if index not in {1, 5} else 48
        parts.append(f'<circle cx="{x}" cy="500" r="{r}" fill="{p["paper"]}" stroke="{p["accent"]}" stroke-width="4"/><text x="{x}" y="506" text-anchor="middle" font-family="Arial" font-size="{12 if len(label)>6 else 14}" font-weight="800" fill="{p["ink"]}">{label}</text><text x="{x}" y="580" text-anchor="middle" font-family="Arial" font-size="13" font-weight="700" fill="{p["muted"]}">0{index}</text>')
    return _frame(scene, p, "".join(parts), dark=False)


def _proof(scene: dict[str, Any], p: dict[str, str]) -> str:
    hashes = ["SEMANTIC LAW", "PROJECTION", "ART DIRECTION", "VISUAL QA"]
    parts = []
    y = 270
    for index, label in enumerate(hashes):
        x = 660 + index * 155
        parts.append(f'<g><rect x="{x}" y="{y + index*80}" width="310" height="92" rx="8" fill="{p["paper"]}" stroke="{p["line"]}"/><text x="{x+22}" y="{y+35+index*80}" font-family="Arial" font-size="15" font-weight="800" fill="{p["ink"]}">{label}</text><text x="{x+22}" y="{y+64+index*80}" font-family="monospace" font-size="12" fill="{p["muted"]}">sha256:{hashlib.sha256(label.encode()).hexdigest()[:18]}…</text></g>')
        if index:
            parts.append(f'<path d="M{x-95} {y+index*80+46} H{x}" stroke="{p["accent"]}" stroke-width="3" marker-end="url(#arrow)"/>')
    parts.append(f'<circle cx="1245" cy="640" r="72" fill="{p["accent"]}"/><text x="1245" y="630" text-anchor="middle" font-family="Arial" font-size="15" font-weight="800" fill="white">PROOF</text><text x="1245" y="654" text-anchor="middle" font-family="Arial" font-size="12" fill="white">inspectable</text>')
    return _frame(scene, p, "".join(parts), dark=True)


def _authority(scene: dict[str, Any], p: dict[str, str]) -> str:
    body = f"""
<circle cx="1020" cy="360" r="72" fill="{p['warm']}" opacity=".92"/><path d="M875 660 Q1020 460 1165 660" fill="none" stroke="{p['warm']}" stroke-width="58" stroke-linecap="round"/>
<g filter="url(#shadow)"><rect x="625" y="300" width="315" height="390" rx="12" fill="{p['paper']}"/></g>
<text x="655" y="350" font-family="Arial" font-size="17" font-weight="800" fill="{p['ink']}">REVIEW COPY</text><rect x="655" y="390" width="220" height="8" fill="{p['line']}"/><rect x="655" y="420" width="245" height="8" fill="{p['line']}"/><rect x="655" y="450" width="185" height="8" fill="{p['line']}"/><path d="M690 520 l22 22 l48 -54" fill="none" stroke="{p['accent']}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><text x="655" y="600" font-family="Arial" font-size="14" font-weight="800" fill="{p['accent2']}">FINAL AUTHORITY</text><text x="655" y="630" font-family="Arial" font-size="22" font-weight="800" fill="{p['ink']}">HUMAN HELD</text>
<path d="M940 510 H1030" stroke="{p['accent']}" stroke-width="4" marker-end="url(#arrow)"/>"""
    return _frame(scene, p, body, dark=True)


def _cta(scene: dict[str, Any], p: dict[str, str]) -> str:
    body = f"""
<circle cx="1075" cy="500" r="220" fill="none" stroke="{p['accent']}" stroke-width="2" opacity=".55"/>
<circle cx="1075" cy="500" r="160" fill="none" stroke="{p['warm']}" stroke-width="3" opacity=".8"/>
<circle cx="1075" cy="500" r="88" fill="{p['accent']}"/>
<path d="M1035 500 H1110 M1080 470 L1110 500 L1080 530" fill="none" stroke="white" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
<text x="1075" y="760" text-anchor="middle" font-family="Arial" font-size="15" font-weight="800" letter-spacing="2" fill="{p['muted']}">ONE BOUNDED NEXT STEP</text>"""
    return _frame(scene, p, body, dark=False)


def render_site_svg_assets(*, story: dict[str, Any], art: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Render one deterministic SVG per website semantic scene.

    This generalises the vector-composition approach proven in HOMS while keeping
    Site Studio semantics and art direction as the controlling inputs. Gamma or any
    other generative visual provider may later contribute image material, but never
    controls typography, geometry, text, section structure or release authority.
    """
    scenes = list(story.get("scenes") or [])
    art_scenes = list(art.get("scenes") or [])
    if story.get("surface") != "website":
        raise SiteSvgCompositorError("Site SVG compositor requires a website story surface")
    if len(scenes) != len(art_scenes) or not scenes:
        raise SiteSvgCompositorError("website story and art direction must expose the same non-zero scene count")
    if art.get("source_story_hash") != story.get("story_hash"):
        raise SiteSvgCompositorError("art direction is not bound to the supplied website story")

    output_dir.mkdir(parents=True, exist_ok=True)
    p = _palette(art)
    renderers = {
        "site_hook": _hook,
        "service_1": _strategy,
        "service_2": _synthesis,
        "service_3": _handoff,
        "method": _method,
        "proof": _proof,
        "human_authority": _authority,
        "cta": _cta,
    }
    assets: list[dict[str, Any]] = []
    for index, (semantic, directed) in enumerate(zip(scenes, art_scenes), 1):
        role = str(semantic.get("role") or "")
        if role != str(directed.get("role") or ""):
            raise SiteSvgCompositorError(f"scene role mismatch at index {index}: {role!r}")
        merged = {**semantic, **directed}
        renderer = renderers.get(role)
        if renderer is None:
            raise SiteSvgCompositorError(f"no deterministic SVG renderer exists for website role: {role}")
        svg = renderer(merged, p)
        if "<script" in svg.casefold() or "<foreignobject" in svg.casefold():
            raise SiteSvgCompositorError("SVG compositor emitted forbidden executable/foreign content")
        path = output_dir / f"{index:02d}-{role.replace('_', '-')}.svg"
        path.write_text(svg.rstrip() + "\n", encoding="utf-8")
        assets.append({
            "scene_id": semantic.get("scene_id"),
            "role": role,
            "layout_family": directed.get("layout_family"),
            "display_copy": directed.get("display_copy"),
            "visual_subject": directed.get("visual_subject"),
            "path": path.name,
            "sha256": _sha(path),
            "bytes": path.stat().st_size,
            "alt_text": _clean(semantic.get("visual") or directed.get("visual_subject"), 500),
            "text_authority": "DIO_DOCUMENT_STUDIO",
            "geometry_authority": "DIO_DOCUMENT_STUDIO",
            "external_visual_provider_layout_authority": "REFUSE",
        })

    receipt = {
        "schema": "dio.document_studio.site_svg_compositor_receipt.v1",
        "source": "homs_vector_composition_pattern_generalized",
        "surface": "website",
        "story_hash": story.get("story_hash"),
        "art_direction_hash": art.get("art_direction_hash"),
        "scene_count": len(assets),
        "assets": assets,
        "all_scene_roles_bound": len({row["role"] for row in assets}) == len(assets),
        "gamma_layout_authority": "REFUSE",
        "gamma_text_authority": "REFUSE",
        "gamma_role": "OPTIONAL_IMAGE_MATERIAL_ONLY",
        "automatic_selection": "REFUSE",
        "human_visual_release": "NEEDS_YOU",
        "publication": "REFUSE",
        "authority_created": False,
    }
    receipt["compositor_fingerprint"] = _fingerprint(receipt)
    return receipt


__all__ = ["SiteSvgCompositorError", "render_site_svg_assets"]
