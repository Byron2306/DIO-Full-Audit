#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WIDTH = 1600
HEIGHT = 900


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run(args: list[str], timeout: int = 180) -> None:
    result = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        detail = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{detail}")


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def label(text: str, x: int, y: int, size: int, *, fill: str = "#f7fafc", weight: int = 760, anchor: str = "start") -> str:
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'font-family="Inter, Arial, sans-serif" font-size="{size}" font-weight="{weight}" '
        f'letter-spacing="0" fill="{fill}">{esc(text)}</text>'
    )


def small_label(text: str, x: int, y: int, *, fill: str = "#b9c4c9", anchor: str = "start") -> str:
    return label(text, x, y, 29, fill=fill, weight=620, anchor=anchor)


def document_stack(x: int, y: int, count: int, *, spread: int = 36, danger: bool = False) -> str:
    parts = []
    for index in range(count):
        dx = int(math.sin(index * 1.7) * spread)
        dy = index * 19
        rot = -10 + (index * 7) % 24
        fill = "#fff7df" if index % 2 else "#f6fbff"
        stroke = "#ef9c57" if danger and index % 3 == 0 else "#49616a"
        parts.append(
            f'<g transform="translate({x + dx} {y + dy}) rotate({rot})">'
            f'<rect x="0" y="0" width="170" height="218" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="3"/>'
            f'<rect x="22" y="31" width="88" height="12" rx="6" fill="#27363d" opacity="0.35"/>'
            f'<rect x="22" y="62" width="124" height="8" rx="4" fill="#71848c" opacity="0.45"/>'
            f'<rect x="22" y="86" width="102" height="8" rx="4" fill="#71848c" opacity="0.45"/>'
            f'<rect x="22" y="110" width="132" height="8" rx="4" fill="#71848c" opacity="0.45"/>'
            f'<circle cx="133" cy="172" r="22" fill="#ef594f" opacity="{0.55 if danger else 0.18}"/>'
            "</g>"
        )
    return "".join(parts)


def evidence_table(x: int, y: int, rows: int = 5) -> str:
    parts = [
        f'<g transform="translate({x} {y})">',
        '<rect x="0" y="0" width="520" height="310" rx="24" fill="#f8fbf5" stroke="#b7c7ba" stroke-width="4"/>',
        '<rect x="28" y="28" width="464" height="50" rx="13" fill="#17252b"/>',
        label("Evidence table", 52, 62, 27, fill="#e8fff3", weight=760),
    ]
    for row in range(rows):
        yy = 104 + row * 37
        color = "#e9f4ef" if row % 2 else "#fffaf0"
        parts.append(f'<rect x="30" y="{yy}" width="460" height="27" rx="8" fill="{color}"/>')
        parts.append(f'<circle cx="55" cy="{yy + 14}" r="7" fill="#38a169"/>')
        parts.append(f'<rect x="78" y="{yy + 8}" width="{145 + row * 18}" height="8" rx="4" fill="#455c61" opacity="0.65"/>')
        parts.append(f'<rect x="310" y="{yy + 8}" width="{85 + row * 6}" height="8" rx="4" fill="#c08a2c" opacity="0.75"/>')
    parts.append("</g>")
    return "".join(parts)


def zip_box(x: int, y: int, *, scale: float = 1.0) -> str:
    w = int(240 * scale)
    h = int(190 * scale)
    return (
        f'<g transform="translate({x} {y})">'
        f'<rect x="0" y="30" width="{w}" height="{h}" rx="22" fill="#f3b64b" stroke="#7b4b12" stroke-width="5"/>'
        f'<rect x="{int(w * 0.18)}" y="0" width="{int(w * 0.34)}" height="60" rx="15" fill="#ffd98a" stroke="#7b4b12" stroke-width="5"/>'
        f'<rect x="{int(w * 0.53)}" y="44" width="{int(w * 0.12)}" height="{h - 30}" rx="5" fill="#533419" opacity="0.78"/>'
        f'<rect x="{int(w * 0.54)}" y="54" width="{int(w * 0.10)}" height="10" rx="3" fill="#ffe7a6"/>'
        f'<rect x="{int(w * 0.54)}" y="78" width="{int(w * 0.10)}" height="10" rx="3" fill="#ffe7a6"/>'
        f'<rect x="{int(w * 0.54)}" y="102" width="{int(w * 0.10)}" height="10" rx="3" fill="#ffe7a6"/>'
        + label("ZIP", int(w * 0.22), int(h * 0.75), int(45 * scale), fill="#3b2510", weight=850)
        + "</g>"
    )


def pipeline_nodes() -> str:
    nodes = [
        ("ROUTE", 330, 372, "#ffcf72"),
        ("REVIEW", 620, 372, "#6edbc0"),
        ("PACK", 910, 372, "#f4f7fb"),
        ("SEND", 1200, 372, "#84c4ff"),
    ]
    parts = ['<g filter="url(#softShadow)">']
    for text, x, y, fill in nodes:
        parts.append(f'<rect x="{x}" y="{y}" width="190" height="116" rx="20" fill="{fill}" stroke="#10212a" stroke-width="4"/>')
        parts.append(label(text, x + 95, y + 70, 32, fill="#10212a", weight=860, anchor="middle"))
    for x in [530, 820, 1110]:
        parts.append(f'<path d="M{x} 430 H{x + 70}" stroke="#e9fff7" stroke-width="9" stroke-linecap="round"/>')
        parts.append(f'<path d="M{x + 52} 407 L{x + 82} 430 L{x + 52} 453" fill="none" stroke="#e9fff7" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>')
    parts.append("</g>")
    return "".join(parts)


def base_svg(body: str, *, accent: str = "#24d3a0") -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#071114"/>
      <stop offset="45%" stop-color="#13272b"/>
      <stop offset="100%" stop-color="#f4c45c"/>
    </linearGradient>
    <radialGradient id="glow" cx="74%" cy="42%" r="48%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.65"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0"/>
    </radialGradient>
    <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="20" stdDeviation="18" flood-color="#000000" flood-opacity="0.35"/>
    </filter>
    <filter id="hotShadow" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="0" stdDeviation="20" flood-color="{accent}" flood-opacity="0.45"/>
    </filter>
  </defs>
  <rect width="1600" height="900" fill="url(#bg)"/>
  <rect width="1600" height="900" fill="url(#glow)"/>
  <path d="M0 760 C240 690 410 820 690 722 C970 625 1190 695 1600 575 V900 H0 Z" fill="#071114" opacity="0.36"/>
  <g opacity="0.17" stroke="#d9fff4" stroke-width="2">
    <path d="M90 140 H1510"/><path d="M90 260 H1510"/><path d="M90 380 H1510"/><path d="M90 500 H1510"/>
    <path d="M200 80 V820"/><path d="M480 80 V820"/><path d="M760 80 V820"/><path d="M1040 80 V820"/><path d="M1320 80 V820"/>
  </g>
  {body}
</svg>
'''


def scene_svg(card_id: str, scene: dict[str, Any]) -> str:
    text = scene.get("on_screen_text", card_id)
    if card_id == "01_hook":
        body = (
            document_stack(70, 160, 8, danger=True)
            + '<path d="M445 485 C610 350 760 270 970 300" fill="none" stroke="#ebfff7" stroke-width="12" stroke-linecap="round" opacity="0.82"/>'
            + '<path d="M920 258 L1000 303 L922 348" fill="none" stroke="#ebfff7" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" opacity="0.82"/>'
            + evidence_table(930, 250, 4)
            + label("Evidex", 96, 104, 72, fill="#ffffff", weight=880)
            + label("Evidence Pack", 96, 174, 54, fill="#ffcf72", weight=820)
            + small_label("A pipeline for proof, not another folder mess.", 99, 792, fill="#e8fff3")
        )
    elif card_id == "02_pain":
        body = (
            document_stack(120, 130, 10, danger=True)
            + '<g opacity="0.85">' + document_stack(660, 120, 7, spread=58, danger=True) + "</g>"
            + label("Scattered proof", 940, 150, 64, fill="#ffffff", weight=880)
            + small_label("emails, screenshots, spreadsheets, old folders", 945, 210, fill="#ffddb5")
            + '<path d="M956 330 C1080 300 1200 392 1320 350 C1420 315 1494 356 1540 410" fill="none" stroke="#ef594f" stroke-width="9" stroke-linecap="round" opacity="0.82"/>'
            + '<path d="M958 430 C1090 485 1235 420 1370 500" fill="none" stroke="#ef594f" stroke-width="9" stroke-linecap="round" opacity="0.72"/>'
        )
    elif card_id == "03_workflow":
        body = (
            pipeline_nodes()
            + label("Small controlled flow", 96, 145, 64, fill="#ffffff", weight=860)
            + small_label("Route the job. Review the evidence. Package the output.", 100, 205, fill="#ddfff5")
            + '<rect x="145" y="600" width="1310" height="78" rx="22" fill="#071114" opacity="0.62" stroke="#6edbc0" stroke-width="3"/>'
            + small_label("Operator approval stays visible at every release point.", 184, 649, fill="#f7fafc")
        )
    elif card_id == "04_promise":
        body = (
            evidence_table(110, 190, 6)
            + zip_box(1070, 510, scale=1.15)
            + '<g filter="url(#hotShadow)"><circle cx="1130" cy="260" r="112" fill="#38a169"/><path d="M1072 263 L1110 304 L1194 210" fill="none" stroke="#ffffff" stroke-width="24" stroke-linecap="round" stroke-linejoin="round"/></g>'
            + label("Review-ready output", 690, 155, 62, fill="#ffffff", weight=880)
            + small_label("table, source index, narrative, QA receipt, delivery ZIP", 694, 215, fill="#fff1c8")
            + '<path d="M665 360 C820 328 925 390 1028 548" fill="none" stroke="#fff7df" stroke-width="10" stroke-linecap="round" opacity="0.74"/>'
        )
    elif card_id == "05_boundary":
        body = (
            '<rect x="150" y="130" width="560" height="560" rx="42" fill="#f7fafc" opacity="0.94" filter="url(#softShadow)"/>'
            + '<rect x="220" y="210" width="420" height="56" rx="14" fill="#17252b"/>'
            + '<rect x="220" y="315" width="350" height="20" rx="10" fill="#536a71" opacity="0.55"/>'
            + '<rect x="220" y="370" width="405" height="20" rx="10" fill="#536a71" opacity="0.55"/>'
            + '<rect x="220" y="425" width="320" height="20" rx="10" fill="#536a71" opacity="0.55"/>'
            + '<g transform="translate(332 522) rotate(-8)"><rect x="0" y="0" width="275" height="96" rx="16" fill="none" stroke="#ef594f" stroke-width="10"/>' 
            + label("REVIEW", 138, 61, 37, fill="#ef594f", weight=900, anchor="middle") + "</g>"
            + label("Human approval stays", 805, 225, 62, fill="#ffffff", weight=870)
            + small_label("Evidex prepares the pack. People sign it off.", 812, 286, fill="#e8fff3")
            + '<path d="M830 458 L1035 650 L1455 265" fill="none" stroke="#6edbc0" stroke-width="30" stroke-linecap="round" stroke-linejoin="round" filter="url(#hotShadow)"/>'
        )
    else:
        body = (
            document_stack(110, 270, 5, danger=False)
            + zip_box(650, 310, scale=1.25)
            + '<g filter="url(#hotShadow)"><rect x="1010" y="318" width="430" height="130" rx="26" fill="#f7fafc"/>' 
            + label("PILOT PACK", 1225, 401, 48, fill="#10212a", weight=900, anchor="middle") + "</g>"
            + label("Send one safe folder", 120, 150, 62, fill="#ffffff", weight=860)
            + small_label("Get a proof pack you can review, price, and sell.", 124, 212, fill="#fff1c8")
            + '<path d="M450 470 H610" stroke="#f7fafc" stroke-width="14" stroke-linecap="round"/>'
            + '<path d="M586 435 L635 470 L586 505" fill="none" stroke="#f7fafc" stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    return base_svg(body)


def thumbnail_svg() -> str:
    body = (
        document_stack(40, 130, 11, spread=70, danger=True)
        + '<rect x="0" y="0" width="1600" height="900" fill="#071114" opacity="0.22"/>'
        + '<path d="M445 525 C650 330 855 270 1075 350" fill="none" stroke="#ffffff" stroke-width="18" stroke-linecap="round" opacity="0.9"/>'
        + '<path d="M1018 290 L1118 356 L1018 414" fill="none" stroke="#ffffff" stroke-width="18" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>'
        + zip_box(1090, 470, scale=1.25)
        + '<g filter="url(#hotShadow)"><rect x="780" y="126" width="700" height="250" rx="34" fill="#f7fafc"/>' 
        + label("PROOF PACK", 1130, 230, 89, fill="#071114", weight=930, anchor="middle")
        + label("INSTEAD OF CHAOS", 1130, 315, 47, fill="#9b3d31", weight=870, anchor="middle")
        + "</g>"
        + '<rect x="92" y="702" width="530" height="92" rx="22" fill="#071114" opacity="0.78" stroke="#ffcf72" stroke-width="4"/>'
        + label("EVIDEX", 126, 766, 55, fill="#ffcf72", weight=920)
    )
    return base_svg(body, accent="#ffcf72")


def gamma_handoff(episode_dir: Path, scenes: list[dict[str, Any]], visual_dir: Path) -> None:
    gamma_dir = episode_dir / "imports" / "gamma"
    prompt_lines = [
        "# Evidex Gamma Visual Upgrade Handoff",
        "",
        "Use these prompts to replace the local placeholder art with generated full-bleed cinematic visuals.",
        "Style: high contrast practical B2B evidence workflow, real documents, inbox clutter, source pack, QA approval marks, no stock-photo smiles, no abstract gradient-only design.",
        "",
    ]
    pages = []
    for scene in scenes:
        prompt = (
            f"16:9 cinematic product explainer frame for Evidex Evidence Pack. "
            f"Scene: {scene['on_screen_text']}. Voiceover: {scene['voiceover']} "
            "Show tangible evidence workflow objects: emails, spreadsheets, documents, source table, review marks, delivery ZIP. "
            "Make it concrete, dramatic, and inspection-friendly. Minimal text, no generic office stock photo."
        )
        pages.append({"scene_id": scene["scene_id"], "card_id": scene["card_id"], "prompt": prompt})
        prompt_lines.extend([f"## {scene['card_id']}", prompt, ""])
    pages.append(
        {
            "scene_id": "thumbnail",
            "card_id": "thumbnail_striking",
            "prompt": "Striking 16:9 thumbnail for Evidex Evidence Pack: chaotic donor reporting documents on the left transform into a glowing proof ZIP and evidence table on the right. Large readable text: PROOF PACK. High contrast, urgent but credible.",
        }
    )
    payload = {
        "schema": "knowedge.gamma_visual_handoff.v1",
        "created_at": utc_now(),
        "episode_dir": str(episode_dir),
        "local_visuals_dir": str(visual_dir),
        "provider_note": "NicheFoundry has Gamma wiring; keep API keys in the NicheFoundry environment and do not paste secrets into this file.",
        "pages": pages,
    }
    write_json(gamma_dir / "gamma_visual_request.json", payload)
    (gamma_dir / "gamma_prompts.md").write_text("\n".join(prompt_lines), encoding="utf-8")


def build_assets(episode_dir: Path) -> dict[str, Any]:
    script_manifest = load_json(episode_dir / "script_manifest.json")
    visual_dir = episode_dir / "imports" / "visuals"
    visual_dir.mkdir(parents=True, exist_ok=True)

    assets = []
    for scene in script_manifest["scenes"]:
        svg_path = visual_dir / f"{scene['card_id']}.svg"
        png_path = visual_dir / f"{scene['card_id']}.png"
        svg_path.write_text(scene_svg(scene["card_id"], scene), encoding="utf-8")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(svg_path), "-frames:v", "1", str(png_path)])
        assets.append({"scene_id": scene["scene_id"], "card_id": scene["card_id"], "svg": str(svg_path), "png": str(png_path)})

    thumb_svg = visual_dir / "thumbnail_striking.svg"
    thumb_png = visual_dir / "thumbnail_striking.png"
    thumb_svg.write_text(thumbnail_svg(), encoding="utf-8")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(thumb_svg), "-frames:v", "1", str(thumb_png)])
    root_thumb = episode_dir / "thumbnail.png"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(thumb_png), "-vf", "scale=1280:720", "-frames:v", "1", str(root_thumb)])

    gamma_handoff(episode_dir, script_manifest["scenes"], visual_dir)

    receipt = {
        "schema": "knowedge.evidex_visual_assets.v1",
        "created_at": utc_now(),
        "episode_id": script_manifest["episode_id"],
        "status": "passed",
        "mode": "local_svg_cinematic_visuals_plus_gamma_handoff",
        "visual_dir": str(visual_dir),
        "assets": assets,
        "thumbnail": {"svg": str(thumb_svg), "png": str(thumb_png), "episode_thumbnail": str(root_thumb)},
        "gamma_handoff": str(episode_dir / "imports" / "gamma" / "gamma_visual_request.json"),
    }
    write_json(episode_dir / "VISUAL_ASSET_RECEIPT.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Build non-template Evidex visuals for a promoted NicheFoundry episode.")
    parser.add_argument("--episode", required=True, help="Path to promoted Evidex episode directory.")
    args = parser.parse_args()
    receipt = build_assets(Path(args.episode).expanduser().resolve())
    print(json.dumps({"status": receipt["status"], "visual_dir": receipt["visual_dir"], "thumbnail": receipt["thumbnail"]["episode_thumbnail"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
