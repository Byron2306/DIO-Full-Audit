from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from adapters.document_studio.art_direction import ANTI_PATTERNS, build_art_direction
from adapters.format_core.renderer import build_paragraph_semantic_content, render_semantic_asset
from adapters.sophia.review_pipeline import run_review
from lingua.product_projection import build_projection_plan
from lingua.semantic_law import build_semantic_law, validate_projection
from lingua.storyline_planner import project_story
from presence_core.studio_release import prepare_studio_release
from scripts.beast_visual_memory import resolve_visual_memory

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_TOKEN = "DIO_STUDIO_FULL_GRADE_CONVERGENCE_READY"


class StudioFullGradeError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StudioFullGradeError(f"invalid or missing JSON: {path}") from exc
    if not isinstance(value, dict):
        raise StudioFullGradeError(f"expected object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _base_native_closure(manifest_path: Path, output_dir: Path, root: Path) -> dict[str, Any]:
    # Install the customer-visible upgrade first, then bind the current closure.
    from products.studio_launch_artifact_upgrade import install as install_launch_upgrade
    install_launch_upgrade()
    from products import studio_native_closure as closure

    return closure.close_studio_case(
        manifest_path=manifest_path,
        output_dir=output_dir,
        root=root,
    )


def _site_product_audience(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = manifest["artifact_contract"]
    brand = contract["brand"]
    positioning = contract["positioning"]
    product = {
        "id": manifest["studio_id"],
        "short_name": str(brand["title"]),
        "name": str(brand["title"]),
        "offer": str(positioning["category"]),
        "promise": str(positioning["desired_outcome"]),
        "proof": (
            "The final site package exposes its semantic law, art direction, visual QA, "
            "proof manifest and human release boundary beside the customer-facing site."
        ),
        "cta": "Start a bounded website brief",
    }
    audience = {
        "id": "site-buyer",
        "name": str(manifest["job"]["buyer"]),
        "pain": str(positioning["buyer_problem"]),
        "outcome": str(positioning["desired_outcome"]),
    }
    return product, audience


def _apply_visual_memory(art: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
    updated = json.loads(json.dumps(art))
    language = dict(updated.get("art_language") or {})
    allowed = {
        "aesthetic",
        "palette_behavior",
        "photography",
        "typography",
        "texture",
        "proof_treatment",
        "rhythm",
    }
    applied: list[dict[str, Any]] = []
    for row in memory.get("approved_patterns") or []:
        pattern = dict(row.get("design_pattern") or {})
        accepted = {key: pattern[key] for key in allowed if key in pattern and pattern[key]}
        if accepted:
            language.update(accepted)
            applied.append({"credit_id": row.get("credit_id"), "fields": sorted(accepted)})
    updated["art_language"] = language

    anti = list(updated.get("anti_patterns") or [])
    for row in memory.get("negative_patterns") or []:
        detail = ""
        if isinstance(row, dict):
            for key in ("detail", "failure_category", "pattern", "failure_code", "reason"):
                detail = str(row.get(key) or "").strip()
                if detail:
                    break
        else:
            detail = str(row).strip()
        if detail and detail not in anti:
            anti.append(detail)
    updated["anti_patterns"] = anti
    updated["beast_visual_memory"] = {
        "state": memory.get("state"),
        "approved_crystal_refs": list(memory.get("approved_crystal_refs") or []),
        "applied_crystals": applied,
        "negative_patterns": list(memory.get("negative_patterns") or []),
        "authority": "representational_context_only",
    }
    core = {key: value for key, value in updated.items() if key != "art_direction_hash"}
    updated["art_direction_hash"] = _fingerprint(core)
    return updated


def _layout_class(layout: str, index: int) -> str:
    token = layout.casefold()
    if any(part in token for part in ("full_bleed", "provocation", "hook", "mission")):
        return "hero-band"
    if any(part in token for part in ("source", "context", "observation", "collage")):
        return "split-band"
    if any(part in token for part in ("method", "process", "workflow", "route", "trace")):
        return "process-band"
    if any(part in token for part in ("proof", "evidence", "macro", "result")):
        return "proof-band"
    if any(part in token for part in ("authority", "handoff", "portrait", "reviewer")):
        return "authority-band"
    if any(part in token for part in ("resolve", "release", "cta")):
        return "resolve-band"
    return ("split-band", "process-band", "proof-band", "authority-band")[index % 4]


def _site_visual_qa(
    *,
    law: dict[str, Any],
    projection: dict[str, Any],
    art: dict[str, Any],
    html_text: str,
    css_text: str,
) -> dict[str, Any]:
    layouts = [str(row.get("layout_family") or "") for row in art.get("scenes") or []]
    required_anti = {
        "four_quadrant_saas_card_grid",
        "repeated_photo_left_text_right",
        "generic_white_grey_corporate_canvas",
        "default_gradient_wallpaper",
        "same_layout_on_adjacent_scenes",
    }
    anti = set(art.get("anti_patterns") or [])
    checks = {
        "semantic_projection_valid": not validate_projection(law, projection),
        "art_direction_bound": bool(art.get("art_direction_hash")),
        "minimum_layout_diversity": len({row for row in layouts if row}) >= min(4, max(1, len(layouts))),
        "no_adjacent_layout_clone": all(left != right for left, right in zip(layouts, layouts[1:])),
        "required_anti_patterns_present": required_anti.issubset(anti),
        "responsive_viewport": 'name="viewport"' in html_text,
        "semantic_main": "<main" in html_text,
        "evidence_surface_embedded": "Proof & provenance" in html_text and "proof/SITE_PROOF_MANIFEST.json" in html_text,
        "responsive_css_present": "@media" in css_text,
        "saas_repeat_grid_not_hardcoded": "grid-template-columns:repeat(3,1fr)" not in css_text.replace(" ", ""),
        "publication_not_authorized": projection.get("governance", {}).get("publication") == "held",
        "spend_not_authorized": projection.get("governance", {}).get("spend") == "disabled",
    }
    return {
        "schema": "dio.site_studio_full_grade_visual_qa.v1",
        "checks": checks,
        "passed": all(checks.values()),
        "layout_families": layouts,
        "distinct_layout_count": len({row for row in layouts if row}),
        "anti_patterns": sorted(anti),
        "human_visual_release": "NEEDS_YOU",
    }


def _render_site(
    manifest: dict[str, Any],
    *,
    law: dict[str, Any],
    projection: dict[str, Any],
    story: dict[str, Any],
    art: dict[str, Any],
    package_dir: Path,
) -> tuple[Path, str, str]:
    contract = manifest["artifact_contract"]
    brand = contract["brand"]
    positioning = contract["positioning"]
    declared = list(contract.get("sections") or [])
    art_scenes = list(art.get("scenes") or [])
    story_scenes = list(story.get("scenes") or [])

    sections: list[dict[str, str]] = []
    for index, row in enumerate(declared):
        scene = art_scenes[(index + 1) % len(art_scenes)] if art_scenes else {}
        sections.append({
            "layout": _layout_class(str(scene.get("layout_family") or ""), index),
            "eyebrow": f"0{index + 1} / SERVICE",
            "title": str(row["title"]),
            "body": str(row["body"]),
        })
    sections.extend([
        {
            "layout": "process-band",
            "eyebrow": "HOW THE WORK MOVES",
            "title": "From question to decision-ready evidence",
            "body": (
                "The engagement begins with the decision context, binds the supplied material, "
                "makes uncertainty visible, and prepares a reviewable handoff rather than hiding "
                "judgment behind automation."
            ),
        },
        {
            "layout": "proof-band",
            "eyebrow": "PROOF & BOUNDARY",
            "title": "Evidence stays inspectable",
            "body": (
                "The website package carries its semantic law, visual direction, QA and proof "
                "manifest. Unsupported outcomes, invented clients, fabricated testimonials and "
                "automatic publication remain refused."
            ),
        },
        {
            "layout": "authority-band",
            "eyebrow": "HUMAN AUTHORITY",
            "title": "The site can explain the work. It cannot invent authority.",
            "body": (
                "Claims remain bounded to supplied evidence and approved positioning. Publication "
                "and consequential commitments stay with the human owner."
            ),
        },
    ])

    story_labels = [
        str(row.get("screen_text") or "").strip()
        for row in story_scenes
        if str(row.get("screen_text") or "").strip()
    ][:4]
    story_strip = "".join(f"<li>{html.escape(value)}</li>" for value in story_labels)

    section_html = "".join(
        f"""
<section class="scene {html.escape(row['layout'])}">
  <div class="wrap scene-grid">
    <div class="scene-meta">{html.escape(row['eyebrow'])}</div>
    <div class="scene-copy"><h2>{html.escape(row['title'])}</h2><p>{html.escape(row['body'])}</p></div>
  </div>
</section>"""
        for row in sections
    )

    proof_links = [
        ("Semantic law", "proof/LINGUA_SEMANTIC_LAW.json"),
        ("Site projection", "proof/LINGUA_SITE_PROJECTION.json"),
        ("Art direction", "proof/DOCUMENT_STUDIO_SITE_ART_DIRECTION.json"),
        ("Visual memory", "proof/BEAST_SITE_VISUAL_MEMORY.json"),
        ("Visual QA", "proof/SITE_VISUAL_QA.json"),
        ("Proof manifest", "proof/SITE_PROOF_MANIFEST.json"),
    ]
    proof_html = "".join(
        f'<a class="proof-link" href="{href}"><span>{html.escape(label)}</span><strong>OPEN ↗</strong></a>'
        for label, href in proof_links
    )

    css = """
:root{--ink:#0b1115;--paper:#f4efe6;--paper2:#e9e1d4;--signal:#22d3c5;--amber:#eab464;--muted:#a8b7b8;--line:#ffffff1f}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--ink);color:#f7faf9;font-family:Inter,ui-sans-serif,system-ui,sans-serif}
a{color:inherit}.wrap{width:min(1180px,calc(100% - 40px));margin:auto}
nav{display:flex;justify-content:space-between;align-items:center;padding:24px 0}.brand{font-weight:900;letter-spacing:.12em}.tag{font-size:.72rem;letter-spacing:.12em;color:var(--signal)}
.hero{min-height:88vh;display:grid;align-items:end;padding:9vh 0 8vh;position:relative;overflow:hidden}
.hero:before{content:'';position:absolute;inset:8% -12% auto 54%;height:55vw;max-height:720px;border:1px solid #22d3c533;border-radius:50%;box-shadow:0 0 100px #22d3c51a inset;transform:rotate(-12deg)}
.kicker,.scene-meta{font-size:.72rem;font-weight:900;letter-spacing:.16em;color:var(--signal);text-transform:uppercase}
h1{font-size:clamp(3.4rem,9vw,8.8rem);line-height:.86;letter-spacing:-.065em;max-width:980px;margin:.22em 0}
.lead{font:400 clamp(1.1rem,2vw,1.45rem)/1.6 Georgia,serif;max-width:760px;color:#cad5d5}.cta{display:inline-flex;margin-top:28px;padding:14px 18px;border:1px solid #ffffff44;text-decoration:none;font-weight:800}
.scene{padding:96px 0;border-top:1px solid var(--line)}.scene-grid{display:grid;grid-template-columns:.32fr 1.68fr;gap:44px}.scene-copy{max-width:860px}
.scene h2{font-size:clamp(2.2rem,5vw,5rem);line-height:.95;letter-spacing:-.045em;margin:0 0 20px}.scene p{font:400 1.12rem/1.75 Georgia,serif;max-width:780px}
.split-band{background:var(--paper);color:#152126}.split-band .scene-meta{color:#0a7770}.split-band .scene-grid{grid-template-columns:.6fr 1.4fr}
.process-band{background:#132229}.process-band .scene-copy{margin-left:auto}.process-band h2{max-width:760px}
.proof-band{background:var(--paper2);color:#182024}.proof-band{border-left:10px solid var(--amber)}
.authority-band{background:#17191c}.authority-band .scene-grid{grid-template-columns:1fr 1fr}.authority-band .scene-copy{border-left:1px solid #ffffff33;padding-left:34px}
.resolve-band{background:var(--signal);color:#07100f}.hero-band{background:#0d151b}
.story-strip{list-style:none;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:#ffffff25;margin:40px 0 0}.story-strip li{background:#0f181e;padding:18px}
.proof{background:#070b0e;padding:90px 0}.proof h2{font-size:clamp(2.5rem,5vw,5.2rem);letter-spacing:-.05em}.proof-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.proof-link{display:flex;justify-content:space-between;gap:22px;padding:18px 0;border-bottom:1px solid #ffffff2d;text-decoration:none}.proof-link strong{color:var(--signal)}
.design-note{max-width:900px;color:#aebdbd;font-size:.92rem;line-height:1.65}.intake{padding:92px 0;background:#efe9df;color:#142126}
.intake-grid{display:grid;grid-template-columns:.7fr 1.3fr;gap:44px}.intake form{display:grid;gap:13px}.intake input,.intake textarea{width:100%;padding:14px;border:1px solid #17222633;background:#fff}.intake button{padding:14px 18px;background:#102229;color:white;border:0;font-weight:900;cursor:pointer}
footer{padding:34px 0;color:#91a1a2;border-top:1px solid var(--line)}
@media(max-width:820px){.scene-grid,.split-band .scene-grid,.authority-band .scene-grid,.intake-grid{grid-template-columns:1fr}.authority-band .scene-copy{border-left:0;padding-left:0}.proof-grid,.story-strip{grid-template-columns:1fr}h1{font-size:clamp(3.2rem,17vw,6.4rem)}}
"""
    js = f"""
const form=document.querySelector('#site-brief');
const status=document.querySelector('#site-status');
form.addEventListener('submit',event=>{{
  event.preventDefault();
  const draft={{
    schema:'dio.site_studio.full_grade_intake.v1',
    studio_id:{json.dumps(manifest["studio_id"])},
    organisation:document.querySelector('#org').value,
    contact:document.querySelector('#contact').value,
    goal:document.querySelector('#goal').value,
    state:'LOCAL_DRAFT_ONLY',
    publication:'REFUSE',
    human_gate:'NEEDS_YOU'
  }};
  const blob=new Blob([JSON.stringify(draft,null,2)],{{type:'application/json'}});
  const link=document.createElement('a');
  link.href=URL.createObjectURL(blob);
  link.download='SITE_STUDIO_BRIEF.json';
  link.click();
  URL.revokeObjectURL(link.href);
  status.textContent='Local brief prepared. Nothing was published or sent.';
}});
"""
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(str(brand['title']))}</title>
<meta name="description" content="{html.escape(str(brand['subhead']))}">
<link rel="stylesheet" href="styles.css">
</head>
<body>
<header class="hero"><div class="wrap">
<nav><div class="brand">{html.escape(str(brand['title']).upper())}</div><div class="tag">EVIDENCE-BOUND SITE</div></nav>
<div class="kicker">{html.escape(str(brand['eyebrow']))}</div>
<h1>{html.escape(str(brand['headline']))}</h1>
<p class="lead">{html.escape(str(brand['subhead']))}</p>
<a class="cta" href="#work-with-us">Discuss the work</a>
<ul class="story-strip">{story_strip}</ul>
</div></header>
<main>
{section_html}
<section class="proof"><div class="wrap">
<div class="kicker">SITE STUDIO EVIDENCE SURFACE</div>
<h2>Proof & provenance</h2>
<p class="design-note">This site was projected from a LINGUA semantic law, Document Studio art direction and BEAST visual-memory context. These records describe the site-generation process. They do not create customer, professional or publication authority.</p>
<div class="proof-grid">{proof_html}</div>
</div></section>
<section class="intake" id="work-with-us"><div class="wrap intake-grid">
<div><div class="kicker">BOUNDED NEXT STEP</div><h2>Start with the decision context.</h2><p>{html.escape(str(positioning['buyer_problem']))}</p></div>
<form id="site-brief"><label>Organisation<input id="org" required></label><label>Contact<input id="contact" required></label><label>What must the site help people understand or decide?<textarea id="goal" rows="5" required></textarea></label><button type="submit">Prepare local website brief</button><p id="site-status" aria-live="polite"></p></form>
</div></section>
</main>
<footer><div class="wrap">{html.escape(str(brand['title']))} · Human publication authority preserved · DIO Site Studio proof-carrying package.</div></footer>
<script src="app.js"></script>
</body></html>"""

    package_dir.mkdir(parents=True, exist_ok=True)
    index_path = package_dir / "index.html"
    _write_text(index_path, page)
    _write_text(package_dir / "styles.css", css)
    _write_text(package_dir / "app.js", js)
    return index_path, page, css


def run_site_full_grade(*, manifest_path: Path, output_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = manifest_path if manifest_path.is_absolute() else root / manifest_path
    manifest = _load(manifest_path.resolve())
    if manifest.get("artifact_contract", {}).get("kind") != "site":
        raise StudioFullGradeError("Site full-grade runner requires a site Studio manifest")

    output_dir = output_dir.resolve()
    base = _base_native_closure(manifest_path, output_dir / "base", root)
    product, audience = _site_product_audience(manifest)
    law = build_semantic_law(product, audience)
    channels = {"WEBSITE": {"format": "responsive_proof_carrying_site"}}
    projection = build_projection_plan(law, product, audience, channels)
    projection_errors = validate_projection(law, projection)
    if projection_errors:
        raise StudioFullGradeError("LINGUA Site projection refused: " + "; ".join(projection_errors))
    story = project_story(law, projection, product, audience, "landscape_explainer")
    surface = projection["surfaces"]["landscape_explainer"]
    memory = resolve_visual_memory(
        audience_archetype=str(projection.get("audience_archetype") or "general_professional"),
        surface="website",
        visual_grammar=str(surface.get("visual_grammar") or ""),
    )
    art = _apply_visual_memory(build_art_direction(story, beast_memory=memory), memory)

    package_dir = output_dir / "customer" / "FULL_GRADE_SITE"
    proof_dir = package_dir / "proof"
    _write_json(proof_dir / "LINGUA_SEMANTIC_LAW.json", law)
    _write_json(proof_dir / "LINGUA_SITE_PROJECTION.json", projection)
    _write_json(proof_dir / "SITE_STORY_ARCHITECTURE.json", story)
    _write_json(proof_dir / "DOCUMENT_STUDIO_SITE_ART_DIRECTION.json", art)
    _write_json(proof_dir / "BEAST_SITE_VISUAL_MEMORY.json", memory)

    index_path, page, css = _render_site(
        manifest,
        law=law,
        projection=projection,
        story=story,
        art=art,
        package_dir=package_dir,
    )
    qa = _site_visual_qa(law=law, projection=projection, art=art, html_text=page, css_text=css)
    _write_json(proof_dir / "SITE_VISUAL_QA.json", qa)
    if not qa["passed"]:
        raise StudioFullGradeError(
            "Site full-grade visual QA refused: "
            + ", ".join(key for key, passed in qa["checks"].items() if not passed)
        )

    manifest_rows = []
    for path in sorted(p for p in package_dir.rglob("*") if p.is_file() and p.name != "SITE_PROOF_MANIFEST.json"):
        manifest_rows.append({
            "path": str(path.relative_to(package_dir)),
            "sha256": _sha(path),
            "bytes": path.stat().st_size,
        })
    proof_manifest = {
        "schema": "dio.site_studio.full_grade_proof_manifest.v1",
        "studio_id": manifest["studio_id"],
        "semantic_law_hash": law["semantic_law_hash"],
        "projection_hash": projection["projection_hash"],
        "story_hash": story["story_hash"],
        "art_direction_hash": art["art_direction_hash"],
        "beast_visual_memory_state": memory.get("state"),
        "visual_qa": "PASS",
        "base_native_closure_fingerprint": base["receipt"]["native_closure_fingerprint"],
        "artifacts": manifest_rows,
        "human_gate": "NEEDS_YOU",
        "external_publication": "REFUSE",
        "authority_created": False,
    }
    proof_manifest["proof_fingerprint"] = _fingerprint(proof_manifest)
    _write_json(proof_dir / "SITE_PROOF_MANIFEST.json", proof_manifest)

    release = prepare_studio_release(
        studio_id=manifest["studio_id"],
        entrypoint=str(index_path.relative_to(output_dir)),
    )
    _write_json(output_dir / "presence" / "PRESENCE_FULL_GRADE_SITE_RELEASE.json", release)

    receipt = {
        "schema": "dio.site_studio.full_grade_receipt.v1",
        "studio_id": manifest["studio_id"],
        "base_native_closure": "PASS",
        "lingua_semantic_projection": "PASS",
        "document_studio_art_direction": "PASS",
        "beast_visual_memory": "RESOLVED",
        "beast_visual_memory_state": memory.get("state"),
        "site_visual_qa": "PASS",
        "proof_carrying_customer_site": "PASS",
        "customer_artifact": str(index_path.relative_to(output_dir)),
        "proof_fingerprint": proof_manifest["proof_fingerprint"],
        "human_gate": "NEEDS_YOU",
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "authority_created": False,
        "full_grade_state": "PASS",
    }
    receipt["full_grade_fingerprint"] = _fingerprint(receipt)
    _write_json(output_dir / "SITE_STUDIO_FULL_GRADE_RECEIPT.json", receipt)
    return receipt


def _fixture_manuscript(manifest: dict[str, Any]) -> str:
    contract = manifest["artifact_contract"]
    claims = {row["claim_id"]: row for row in contract.get("claim_fixture") or []}
    source_rows = list(contract.get("source_fixture") or [])
    citation_by_id: dict[str, str] = {}
    for source in source_rows:
        citation = str(source["citation"])
        match = re.match(r"^([A-Z][A-Za-z'’-]+).*?\(((?:19|20)\d{2}[a-z]?)\)", citation)
        if match:
            citation_by_id[str(source["source_id"])] = f"{match.group(1)} ({match.group(2)})"

    paragraphs = [f"# {contract['headline']}", "", str(contract["standfirst"]), ""]
    section_claims = [
        ("CL-01", "CL-02"),
        ("CL-02", "CL-03"),
        ("CL-03",),
    ]
    for index, section in enumerate(contract.get("sections") or []):
        paragraphs.extend([f"## {section['heading']}", "", str(section["body"])])
        extras = []
        for claim_id in section_claims[index] if index < len(section_claims) else ():
            claim = claims.get(claim_id)
            if not claim:
                continue
            keys = [citation_by_id.get(evidence_id) for evidence_id in claim.get("evidence_ids") or []]
            keys = [key for key in keys if key]
            suffix = f" ({'; '.join(keys)})" if keys else ""
            extras.append(str(claim["text"]).rstrip(".") + suffix + ".")
        if extras:
            paragraphs.extend(["", " ".join(extras)])
        paragraphs.append("")
    paragraphs.extend(["## References", ""])
    paragraphs.extend(str(row["citation"]) + "\n" for row in source_rows)
    return "\n".join(paragraphs)


def _article_semantic_content(
    *,
    manifest: dict[str, Any],
    manuscript_text: str,
    review_dir: Path,
) -> dict[str, Any]:
    contract = manifest["artifact_contract"]
    commentary_path = review_dir / "REVIEWER_COMMENTARY.md"
    commentary = commentary_path.read_text(encoding="utf-8") if commentary_path.is_file() else ""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", manuscript_text) if part.strip()]
    rows = [{"paragraph_id": "P1", "text": str(contract["headline"])}]
    for index, paragraph in enumerate(paragraphs, 2):
        rows.append({"paragraph_id": f"P{index}", "text": paragraph})
    if commentary:
        rows.extend([
            {"paragraph_id": f"P{len(rows)+1}", "text": "Sophia reviewer commentary"},
            {"paragraph_id": f"P{len(rows)+2}", "text": commentary},
        ])
    return build_paragraph_semantic_content(
        object_id=f"ARTICLE-FULL-GRADE-{manifest['studio_id'].upper()}",
        version=str(manifest.get("studio_version") or "1.0.0"),
        title=str(contract["headline"]),
        source_language="English",
        source_rows=rows,
        context={
            "product": manifest["studio_id"],
            "artifact_type": "sophia_governed_publication_review",
            "audience": str(contract.get("audience") or manifest["job"]["buyer"]),
        },
    )


def run_article_full_grade(
    *,
    manifest_path: Path,
    output_dir: Path,
    root: Path = ROOT,
    manuscript_path: Path | None = None,
    sophia_root: Path = Path("/home/byron/Integritas-Mechanicus"),
    sophia_base_url: str = "http://127.0.0.1:7070",
    remote_review_approved: bool = False,
    gemini_model: str = "gemini-flash-lite-latest",
) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = manifest_path if manifest_path.is_absolute() else root / manifest_path
    manifest = _load(manifest_path.resolve())
    if manifest.get("artifact_contract", {}).get("kind") != "article":
        raise StudioFullGradeError("Article full-grade runner requires an article Studio manifest")

    output_dir = output_dir.resolve()
    base = _base_native_closure(manifest_path, output_dir / "base", root)
    source_dir = output_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    if manuscript_path is None:
        manuscript_path = source_dir / "CONTROLLED_ARTICLE_MANUSCRIPT.md"
        _write_text(manuscript_path, _fixture_manuscript(manifest))
        input_truth = "CONTROLLED_FIXTURE"
        # The controlled fixture contains no customer data, so remote review is safe to opt into
        # for this gauntlet. Real customer manuscripts still require explicit approval.
        approved = True
    else:
        manuscript_path = manuscript_path.expanduser().resolve()
        if not manuscript_path.is_file():
            raise StudioFullGradeError(f"customer manuscript missing: {manuscript_path}")
        input_truth = "CUSTOMER_SUPPLIED_MANUSCRIPT"
        approved = bool(remote_review_approved)

    request = {
        "job_id": "ARTICLE-FULL-GRADE",
        "document_path": str(manuscript_path),
        "title": manifest["artifact_contract"]["headline"],
        "research_question": manifest["job"]["request"],
        "citation_style": "APA 7",
        "literature_queries": [],
        "external_retrieval": False,
        "gemini_review_approved": approved,
        "gemini_model": gemini_model,
    }
    request_path = source_dir / "SOPHIA_FULL_REVIEW_REQUEST.json"
    _write_json(request_path, request)
    review_dir = run_review(
        request,
        request_path,
        output_dir / "sophia_full_review",
        sophia_base_url,
        sophia_root.expanduser().resolve(),
    )
    receipt = _load(review_dir / "SOPHIA_REVIEW_RECEIPT.json")
    commentary = _load(review_dir / "REVIEWER_COMMENTARY.json")
    sophia_checks = {
        "reviewer_completed": commentary.get("status") == "completed",
        "reasoned_integrity_lane": commentary.get("source") == "reasoned_integrity_lane",
        "grounding_passed": bool((commentary.get("validation") or {}).get("passed")),
        "mandos_passed": bool((commentary.get("mandos_judgment") or {}).get("passed")),
        "genesis_articles_passed": bool(
            ((commentary.get("article_conformity") or {}).get("summary") or {}).get("all_passed")
        ),
        "delivery_not_released": receipt.get("delivery_released") is False,
    }
    if not all(sophia_checks.values()):
        raise StudioFullGradeError(
            "Full Sophia Article review refused: "
            + ", ".join(key for key, passed in sophia_checks.items() if not passed)
        )

    manuscript_text = manuscript_path.read_text(encoding="utf-8", errors="replace")
    content = _article_semantic_content(
        manifest=manifest,
        manuscript_text=manuscript_text,
        review_dir=review_dir,
    )
    publication_dir = output_dir / "customer" / "PUBLICATION_PACK"
    format_receipt = render_semantic_asset(
        content,
        publication_dir,
        style_profile="institutional_academic",
        delivery_profile="editable_review",
        language="English",
        channels=["html", "docx", "pdf"],
        release_mode=False,
        source_root=root,
    )
    if format_receipt.get("status") != "rendered_review_candidate" or not (format_receipt.get("qa") or {}).get("passed"):
        raise StudioFullGradeError("Document Studio publication manufacturing failed review QA")

    # Copy Sophia's human-readable review pack into the customer package.
    review_pack = publication_dir / "sophia_review"
    review_pack.mkdir(parents=True, exist_ok=True)
    for name in (
        "LITERATURE_MAP.md",
        "REFERENCE_AUDIT.md",
        "CLAIM_SOURCE_LEDGER.md",
        "REVIEWER_COMMENTARY.md",
        "HUMAN_APPROVAL.md",
        "SOPHIA_REVIEW_RECEIPT.json",
    ):
        source = review_dir / name
        if source.is_file():
            shutil.copyfile(source, review_pack / name)

    artifact_rows = []
    for path in sorted(p for p in publication_dir.rglob("*") if p.is_file()):
        artifact_rows.append({
            "path": str(path.relative_to(publication_dir)),
            "sha256": _sha(path),
            "bytes": path.stat().st_size,
        })
    proof = {
        "schema": "dio.article_studio.full_grade_proof_manifest.v1",
        "studio_id": manifest["studio_id"],
        "input_truth": input_truth,
        "full_sophia_review": "PASS",
        "sophia_checks": sophia_checks,
        "document_studio_publication_pack": "PASS",
        "base_native_closure_fingerprint": base["receipt"]["native_closure_fingerprint"],
        "artifacts": artifact_rows,
        "human_gate": "NEEDS_YOU",
        "external_publication": "REFUSE",
        "authority_created": False,
    }
    proof["proof_fingerprint"] = _fingerprint(proof)
    _write_json(publication_dir / "ARTICLE_FULL_GRADE_PROOF_MANIFEST.json", proof)

    html_output = next(
        (row for row in format_receipt.get("outputs") or [] if row.get("channel") == "html"),
        None,
    )
    if not html_output:
        raise StudioFullGradeError("Document Studio publication pack did not expose an HTML review entrypoint")
    customer_entrypoint = publication_dir / str(html_output["path"])
    release = prepare_studio_release(
        studio_id=manifest["studio_id"],
        entrypoint=str(customer_entrypoint.relative_to(output_dir)),
    )
    _write_json(output_dir / "presence" / "PRESENCE_FULL_GRADE_ARTICLE_RELEASE.json", release)

    full_launch_grade = input_truth == "CUSTOMER_SUPPLIED_MANUSCRIPT" and approved
    final_receipt = {
        "schema": "dio.article_studio.full_grade_receipt.v1",
        "studio_id": manifest["studio_id"],
        "input_truth": input_truth,
        "base_native_closure": "PASS",
        "full_sophia_review": "PASS",
        "mandos_genesis_grounding": "PASS",
        "document_studio_publication_manufacturing": "PASS",
        "customer_publication_pack": "PASS",
        "customer_artifact": str(customer_entrypoint.relative_to(output_dir)),
        "proof_fingerprint": proof["proof_fingerprint"],
        "human_gate": "NEEDS_YOU",
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "authority_created": False,
        "full_grade_state": "PASS",
        "launch_grade_customer_input": "PASS" if full_launch_grade else "CONTROLLED_PROOF_ONLY",
    }
    final_receipt["full_grade_fingerprint"] = _fingerprint(final_receipt)
    _write_json(output_dir / "ARTICLE_STUDIO_FULL_GRADE_RECEIPT.json", final_receipt)
    return final_receipt


def run_full_grade_gauntlet(
    *,
    output_dir: Path,
    root: Path = ROOT,
    article_manuscript: Path | None = None,
    sophia_root: Path = Path("/home/byron/Integritas-Mechanicus"),
    sophia_base_url: str = "http://127.0.0.1:7070",
    remote_review_approved: bool = False,
    gemini_model: str = "gemini-flash-lite-latest",
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    site = run_site_full_grade(
        manifest_path=root / "config/studio_harvest/site_studio.json",
        output_dir=output_dir / "site_studio",
        root=root,
    )
    article = run_article_full_grade(
        manifest_path=root / "config/studio_harvest/article_publication_studio.json",
        output_dir=output_dir / "article_publication_studio",
        root=root,
        manuscript_path=article_manuscript,
        sophia_root=sophia_root,
        sophia_base_url=sophia_base_url,
        remote_review_approved=remote_review_approved,
        gemini_model=gemini_model,
    )
    result = {
        "schema": "dio.studio_full_grade_convergence_gauntlet_receipt.v1",
        "acceptance_token": ACCEPTANCE_TOKEN,
        "site_studio": site,
        "article_publication_studio": article,
        "site_full_grade": site.get("full_grade_state") == "PASS",
        "article_full_grade": article.get("full_grade_state") == "PASS",
        "external_effects": False,
        "authority_created": False,
    }
    result["passed"] = bool(result["site_full_grade"] and result["article_full_grade"])
    return result
