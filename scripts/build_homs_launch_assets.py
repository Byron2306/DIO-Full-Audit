#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_DIR = ROOT / "campaigns" / "phase3" / "homs"
SITE_DIR = ROOT / "sites" / "homs"
ASSET_DIR = SITE_DIR / "assets"
OUTLOOK_DIR = CAMPAIGN_DIR / "commercial_ops" / "outlook_first"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def episode_dir() -> Path:
    receipt = load_json(CAMPAIGN_DIR / "PHASE3_RECEIPT.json")
    path = (receipt.get("episode") or {}).get("episode_dir")
    if not path:
        raise RuntimeError("HOMS campaign has no promoted NicheFoundry episode yet.")
    return Path(path)


def subject_marker() -> str:
    return "HOMS MARKING RELIEF REQUEST"


def mailto() -> str:
    body = "\n".join(
        [
            "Hi HOMS,",
            "",
            "I want to test a non-sensitive marking relief pilot.",
            "",
            "Institution / department:",
            "Assessment type:",
            "Batch size:",
            "Rubric or memo available:",
            "Marksheet / gradebook available:",
            "Deadline:",
            "What output would help most: draft feedback / rubric fill / marks CSV / lecturer summary",
            "",
            "I understand the educator approves final marks and feedback.",
        ]
    )
    return f"mailto:?subject={quote(subject_marker())}&body={quote(body)}"


def visual_svg(scene: dict, index: int) -> str:
    title = html.escape(scene["screen_text"])
    narration = html.escape(scene["narration"])
    palette = [
        ("#102a36", "#f7fafc", "#f3b64b", "#59c3b0"),
        ("#f4f0e8", "#172026", "#b64a3d", "#225c7a"),
        ("#13251f", "#f8faf7", "#72d6a8", "#f3b64b"),
        ("#f8faf7", "#111827", "#2f6f9f", "#38a169"),
        ("#1c2024", "#f7fafc", "#f3b64b", "#b8d8c1"),
        ("#f7f7f4", "#141b1f", "#225c7a", "#f3b64b"),
    ][index % 6]
    bg, ink, accent, accent2 = palette
    files = "".join(
        f"""
        <g transform="translate({690 + i * 82},{136 + (i % 2) * 34}) rotate({-5 + i * 4})">
          <rect width="76" height="108" rx="6" fill="#ffffff" opacity="0.92"/>
          <rect x="12" y="18" width="52" height="7" rx="3" fill="{accent}" opacity="0.85"/>
          <rect x="12" y="36" width="44" height="6" rx="3" fill="#6b7280" opacity="0.55"/>
          <rect x="12" y="52" width="50" height="6" rx="3" fill="#6b7280" opacity="0.38"/>
          <circle cx="55" cy="84" r="10" fill="{accent2}" opacity="0.82"/>
        </g>
        """
        for i in range(5)
    )
    rubric_rows = "".join(
        f"""
        <rect x="88" y="{312 + i * 38}" width="332" height="24" rx="5" fill="#ffffff" opacity="{0.18 + i * 0.04}"/>
        <rect x="104" y="{319 + i * 38}" width="{120 + i * 34}" height="8" rx="4" fill="{accent2}" opacity="0.82"/>
        """
        for i in range(5)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="{bg}"/>
  <path d="M0 596 C240 520 372 665 610 590 C856 512 1006 575 1280 496 L1280 720 L0 720 Z" fill="{accent}" opacity="0.17"/>
  <circle cx="1108" cy="110" r="156" fill="{accent2}" opacity="0.18"/>
  <rect x="64" y="72" width="528" height="540" rx="18" fill="#000000" opacity="0.16"/>
  <rect x="88" y="96" width="480" height="492" rx="14" fill="#ffffff" opacity="0.10" stroke="#ffffff" stroke-opacity="0.24"/>
  <text x="96" y="166" font-family="Inter, Arial, sans-serif" font-size="58" font-weight="900" fill="{ink}">{title}</text>
  <foreignObject x="98" y="198" width="420" height="116">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Inter,Arial,sans-serif;font-size:25px;line-height:1.22;font-weight:700;color:{ink};opacity:.82">{narration}</div>
  </foreignObject>
  {rubric_rows}
  <g transform="translate(658,410)">
    <rect width="460" height="144" rx="16" fill="#ffffff" opacity="0.94"/>
    <rect x="30" y="28" width="170" height="18" rx="9" fill="{accent}"/>
    <rect x="30" y="66" width="274" height="12" rx="6" fill="#64748b" opacity="0.42"/>
    <rect x="30" y="94" width="222" height="12" rx="6" fill="#64748b" opacity="0.32"/>
    <path d="M350 46 l28 28 l56 -62" fill="none" stroke="{accent2}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  {files}
  <g transform="translate(718,286)">
    <rect width="360" height="62" rx="31" fill="{accent}" opacity="0.94"/>
    <text x="180" y="41" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="24" font-weight="900" fill="#ffffff">batch -> rubric -> review</text>
  </g>
</svg>
"""


def render_png(svg_path: Path, png_path: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(svg_path), "-frames:v", "1", str(png_path)],
        text=True,
        capture_output=True,
    )
    return result.returncode == 0 and png_path.exists()


def build_visuals(ep: Path) -> dict:
    storyboard = load_json(CAMPAIGN_DIR / "storyboard.json")
    visual_dir = ep / "imports" / "visuals"
    visual_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for index, scene in enumerate(storyboard["scenes"]):
        card_id = f"{index + 1:02d}_{scene['role']}"
        svg_path = visual_dir / f"{card_id}.svg"
        png_path = visual_dir / f"{card_id}.png"
        scene_svg_path = visual_dir / f"{scene['scene_id']}.svg"
        svg = visual_svg(scene, index)
        svg_path.write_text(svg, encoding="utf-8")
        scene_svg_path.write_text(svg, encoding="utf-8")
        render_png(svg_path, png_path)
        outputs.append(str(png_path if png_path.exists() else svg_path))

    thumbnail_svg = ep / "thumbnail.svg"
    thumbnail_png = ep / "thumbnail.png"
    thumbnail_svg.write_text(visual_svg(storyboard["scenes"][0], 0), encoding="utf-8")
    render_png(thumbnail_svg, thumbnail_png)
    receipt = {
        "schema": "knowedge.homs_visual_assets.v1",
        "created_at": utc_now(),
        "status": "ready",
        "mode": "local_svg_workflow_visuals",
        "visual_dir": str(visual_dir),
        "thumbnail": str(thumbnail_png if thumbnail_png.exists() else thumbnail_svg),
        "scene_assets": outputs,
    }
    write_json(ep / "HOMS_VISUAL_ASSET_RECEIPT.json", receipt)
    return receipt


def link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        os.symlink(source, target)
    except OSError:
        shutil.copy2(source, target)


def build_site(ep: Path, visual_receipt: dict) -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    preview = ep / "free_preview.mp4"
    thumbnail = Path(visual_receipt["thumbnail"])
    output = Path(visual_receipt["scene_assets"][3])
    link_or_copy(preview, ASSET_DIR / "free_preview.mp4")
    link_or_copy(thumbnail, ASSET_DIR / thumbnail.name)
    link_or_copy(output, ASSET_DIR / output.name)
    thumb_ref = f"assets/{thumbnail.name}"
    output_ref = f"assets/{output.name}"
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HOMS Marking Relief Pack</title>
  <style>
    :root {{ --ink:#111827; --paper:#f7f7f4; --muted:#5d625f; --line:#d9ddd7; --blue:#225c7a; --gold:#f3b64b; --green:#1f6b3a; --red:#b64a3d; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:var(--paper); }}
    a {{ color:inherit; }}
    .hero {{ min-height:88vh; display:grid; align-items:end; color:#fff; position:relative; isolation:isolate; background:#111827 url("{thumb_ref}") center / cover no-repeat; overflow:hidden; }}
    .hero::before {{ content:""; position:absolute; inset:0; z-index:-1; background:linear-gradient(90deg,rgba(17,24,39,.94),rgba(17,24,39,.68) 45%,rgba(17,24,39,.18)),linear-gradient(0deg,rgba(17,24,39,.86),rgba(17,24,39,.08) 48%); }}
    .nav {{ position:absolute; inset:0 0 auto; display:flex; justify-content:space-between; gap:18px; padding:20px clamp(18px,5vw,64px); font-size:14px; font-weight:800; color:rgba(255,255,255,.9); }}
    .nav-links {{ display:flex; gap:18px; flex-wrap:wrap; justify-content:flex-end; }}
    .nav a {{ text-decoration:none; border-bottom:1px solid transparent; }}
    .nav a:hover {{ border-color:currentColor; }}
    .hero-inner {{ width:min(1120px,calc(100% - 36px)); margin:0 auto; padding:112px 0 58px; }}
    h1 {{ margin:0; font-size:clamp(46px,9vw,112px); line-height:.88; letter-spacing:0; max-width:880px; }}
    h2 {{ margin:0 0 16px; font-size:clamp(31px,5vw,56px); line-height:1; letter-spacing:0; }}
    p {{ color:var(--muted); font-size:18px; line-height:1.55; }}
    .hero-copy {{ margin:26px 0 0; max-width:720px; font-size:clamp(20px,3vw,32px); line-height:1.18; font-weight:780; color:#fff4d7; }}
    .hero-actions,.form-actions {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:30px; align-items:center; }}
    .button {{ border:1px solid transparent; border-radius:8px; min-height:48px; padding:13px 18px; font:inherit; font-weight:850; text-decoration:none; cursor:pointer; display:inline-flex; align-items:center; justify-content:center; }}
    .primary {{ background:var(--gold); color:#201403; }}
    .secondary {{ color:#fff; background:rgba(17,24,39,.48); border-color:rgba(255,255,255,.58); }}
    main {{ display:grid; }}
    section {{ padding:68px clamp(18px,5vw,64px); border-top:1px solid var(--line); }}
    .section-inner {{ width:min(1120px,100%); margin:0 auto; }}
    .lead {{ max-width:820px; font-size:clamp(20px,2.4vw,27px); line-height:1.34; color:#293535; font-weight:700; }}
    .proof-grid {{ display:grid; grid-template-columns:minmax(0,1.2fr) minmax(280px,.8fr); gap:24px; align-items:start; }}
    video,.visual {{ width:100%; border:1px solid #1f2937; border-radius:8px; background:#111827; box-shadow:0 20px 70px rgba(17,24,39,.18); }}
    .facts,.offer-grid {{ display:grid; gap:12px; }}
    .facts {{ list-style:none; padding:0; margin:0; }}
    .facts li {{ background:#fff; border-left:5px solid var(--blue); padding:14px 16px; font-size:17px; font-weight:750; line-height:1.35; }}
    .offer-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); margin-top:28px; }}
    .tile {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:20px; }}
    .tile strong {{ display:block; margin-bottom:8px; font-size:18px; }}
    .price {{ font-size:28px; font-weight:950; color:var(--blue); }}
    .boundary {{ background:#1c2024; color:#f7fafc; }}
    .boundary p {{ color:#d9e8e4; }}
    .boundary .facts li {{ background:rgba(255,255,255,.07); color:#f7fafc; border-color:var(--gold); }}
    form {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; margin-top:24px; }}
    label {{ display:grid; gap:7px; color:#263634; font-size:14px; font-weight:850; }}
    input,select,textarea {{ width:100%; border:1px solid #becbc4; border-radius:8px; background:#fff; color:var(--ink); font:inherit; min-height:46px; padding:11px 12px; }}
    textarea {{ min-height:126px; resize:vertical; }}
    .full,.form-actions,.result {{ grid-column:1 / -1; }}
    .form-actions .secondary {{ color:var(--ink); border-color:#becbc4; background:#fff; }}
    .result {{ min-height:24px; color:var(--green); font-weight:850; }}
    footer {{ padding:28px clamp(18px,5vw,64px); background:#111827; color:rgba(255,255,255,.72); font-size:14px; }}
    @media (max-width:820px) {{ .hero{{min-height:86vh}} .nav{{align-items:flex-start}} .proof-grid,.offer-grid,form{{grid-template-columns:1fr}} .hero-inner{{padding-top:118px}} section{{padding-top:52px;padding-bottom:52px}} }}
  </style>
</head>
<body>
  <header class="hero">
    <nav class="nav" aria-label="Primary"><a href="#top">HOMS</a><div class="nav-links"><a href="#proof">Proof</a><a href="#offer">Offer</a><a href="#intake">Pilot</a></div></nav>
    <div class="hero-inner" id="top">
      <h1>HOMS Marking Relief Pack</h1>
      <p class="hero-copy">Send the batch, rubric, memo, and marksheet. Get structured marking support back.</p>
      <div class="hero-actions"><a class="button primary" href="#intake">Request a Marking Pilot</a><a class="button secondary" id="heroOutlookDraftLink" href="{mailto()}">Open Outlook draft</a><a class="button secondary" href="#proof">Watch the proof preview</a></div>
    </div>
  </header>
  <main>
    <section><div class="section-inner"><h2>The backlog is not just volume.</h2><p class="lead">It is consistency, feedback quality, rubric traceability, gradebook collation, and the final human review that still has to happen under pressure.</p></div></section>
    <section id="proof"><div class="section-inner proof-grid"><div><h2>Preview</h2><p>Generated from the AutoRelease HOMS campaign, promoted into NicheFoundry, rendered with free local/Edge narration and HOMS-specific workflow visuals.</p><video controls poster="{thumb_ref}" preload="metadata"><source src="assets/free_preview.mp4" type="video/mp4"></video></div><div><img class="visual" src="{output_ref}" alt="HOMS review-ready marking output visual"><ul class="facts"><li>Built for lecturers, teachers, tutors, markers, and departments.</li><li>Starts with fake, redacted, or non-sensitive sample batches.</li><li>Returns marking support for educator review, never final authority.</li></ul></div></div></section>
    <section id="offer"><div class="section-inner"><h2>Marking Relief Pilot</h2><p class="lead">Small batch in. Structured first-pass support out. The educator remains the final assessor.</p><div class="offer-grid"><div class="tile"><strong>Tiny fake batch</strong><div class="price">R350-R750</div><p>5-10 dummy or redacted submissions, rubric fit check, sample feedback shape.</p></div><div class="tile"><strong>Normal pilot batch</strong><div class="price">R950-R1,800</div><p>Batch intake, rubric mapping, draft feedback, marks CSV, lecturer review notes.</p></div><div class="tile"><strong>Deadline rescue</strong><div class="price">R2,500-R6,500</div><p>Messy batch cleanup and structured review support for urgent marking windows.</p></div></div></div></section>
    <section class="boundary"><div class="section-inner"><h2>Support, not substitution.</h2><p class="lead">HOMS prepares marking support. It does not replace academic judgement, institutional policy, moderation, or the educator's final approval.</p><ul class="facts"><li>Fake, redacted, or non-sensitive pilots first.</li><li>Rubric and memo required before useful output.</li><li>Final marks and feedback stay human-approved.</li></ul></div></section>
    <section id="intake"><div class="section-inner"><h2>Request a pilot</h2><p class="lead">Reply through Outlook for the fastest route, or download a local intake JSON for the HOMS adapter.</p><form id="intakeForm">
      <label>Name<input name="name" autocomplete="name" required></label><label>Email<input name="email" type="email" autocomplete="email" required></label>
      <label>Institution<input name="institution"></label><label>Deadline<input name="deadline" type="date"></label>
      <label>Assessment type<input name="assessment_type" placeholder="essay, quiz, portfolio, exam"></label><label>Batch size<input name="batch_size" placeholder="10, 30, 80"></label>
      <label>Rubric or memo?<select name="rubric"><option>Yes, rubric/memo exists</option><option>Partial guide only</option><option>Not yet</option></select></label>
      <label>Marksheet?<select name="marksheet"><option>CSV/Excel available</option><option>Need a marksheet created</option><option>Not needed for pilot</option></select></label>
      <label class="full">Desired output<textarea name="desired_output" placeholder="Draft feedback, rubric fill, marks CSV, lecturer summary..."></textarea></label>
      <label class="full">Delivery arrangement<textarea name="delivery" placeholder="How will the fake/redacted sample be supplied?"></textarea></label>
      <div class="form-actions"><button class="button primary" type="submit">Download intake JSON</button><a class="button secondary" id="intakeOutlookDraftLink" href="{mailto()}">Open Outlook draft</a></div>
      <div class="result" id="result" role="status" aria-live="polite"></div>
    </form></div></section>
  </main>
  <footer>HOMS Marking Relief Pack. Pilot workflow asset generated by KnowEdge AutoRelease on 2026-08-07.</footer>
  <script>
    const form = document.querySelector("#intakeForm");
    const result = document.querySelector("#result");
    form.addEventListener("submit", (event) => {{
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      const payload = {{ schema:"knowedge.homs_pilot_intake.v1", created_at:new Date().toISOString(), route:"homs", requested_offer:"Marking Relief Pilot", client:{{ name:data.name, email:data.email, institution:data.institution }}, intake:data, operator_boundary:"Educator approves final marks and feedback. Use fake, redacted, or non-sensitive samples for first pilot." }};
      const blob = new Blob([JSON.stringify(payload,null,2)], {{type:"application/json"}});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const safeName = (data.institution || data.name || "homs").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");
      link.href = url; link.download = `${{safeName || "homs"}}-marking-pilot-intake.json`; document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
      result.textContent = "Intake JSON created. Outlook replies can feed HOMS triage immediately.";
    }});
  </script>
</body>
</html>
"""
    (SITE_DIR / "index.html").write_text(html_doc, encoding="utf-8")


def dummy_outlook_items() -> dict:
    marker = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {
        "schema": "knowedge.outlook_triage_export.v1",
        "created_at": utc_now(),
        "items": [
            {
                "message_id": f"dummy-homs-outlook-{marker}",
                "thread_ref": f"dummy-homs-thread-{marker}",
                "source": "outlook_triage_dummy",
                "folder": "Inbox",
                "subject": "HOMS Marking Relief Request - EDU221 Essay Batch",
                "sender": "Lecturer <pilot.lecturer@example.edu>",
                "received_at": utc_now(),
                "urgency": "high",
                "intent": "marking_support_request",
                "risk": "moderate",
                "lane": "homs",
                "draft_status": "draft_ready",
                "approval_required": "true",
                "safe_send_rating": "caution",
                "recommended_action": "Route to HOMS marking relief pilot and request fake or redacted sample batch.",
                "next_step": "Prepare HOMS marking request for batch, rubric, memo, marksheet, and lecturer review summary.",
                "attachment_names": "edu221-essay-batch.zip; rubric.pdf; memo.docx; marksheet.csv",
                "body": (
                    "I have a marking backlog and want a HOMS marking relief pilot. "
                    "The batch includes essay submissions, a rubric, a memo, and a marksheet. "
                    "I need draft feedback, rubric mapping, marks CSV support, and a lecturer review summary. "
                    "The sample can be fake or redacted; I will approve final marks and feedback."
                ),
            }
        ],
    }


def write_outlook_docs() -> dict:
    OUTLOOK_DIR.mkdir(parents=True, exist_ok=True)
    dummy_path = OUTLOOK_DIR / "dummy_outlook_homs_intake.json"
    write_json(dummy_path, dummy_outlook_items())
    guide = OUTLOOK_DIR / "OUTLOOK_FIRST_INTAKE.md"
    guide.write_text(
        "\n".join(
            [
                "# HOMS Outlook-First Intake",
                "",
                f"Updated: {utc_now()}",
                "",
                "## Live Spine",
                "",
                "```text",
                "ad or direct message",
                f"-> prospect replies with {subject_marker()}",
                "-> Outlook bot triages mailbox or JSON/exported messages",
                "-> triage_summary.csv",
                "-> scripts/route_intake.py",
                "-> HOMS job envelope",
                "-> HOMS marking request",
                "-> educator/operator approval",
                "```",
                "",
                "## Boundary",
                "",
                "HOMS prepares marking support. Educator approval remains required for final marks and feedback.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ad = OUTLOOK_DIR / "OUTLOOK_FIRST_AD.md"
    ad.write_text(
        "\n".join(
            [
                "# HOMS Outlook-First Push Ad",
                "",
                f"Updated: {utc_now()}",
                "",
                "## Copy",
                "",
                "```text",
                "Marking backlog piling up?",
                "",
                "HOMS turns a batch, rubric, memo, and marksheet into structured marking support:",
                "",
                "- draft feedback",
                "- rubric mapping",
                "- marks CSV support",
                "- lecturer review summary",
                "- return-ready request pack",
                "",
                "Start with one fake, redacted, or non-sensitive pilot batch.",
                "",
                f"Reply with: {subject_marker()}",
                "",
                "Educator approval stays final.",
                "```",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"guide": str(guide.relative_to(ROOT)), "ad": str(ad.relative_to(ROOT)), "dummy": str(dummy_path.relative_to(ROOT))}


def main() -> int:
    ep = episode_dir()
    visuals = build_visuals(ep)
    build_site(ep, visuals)
    outlook = write_outlook_docs()
    receipt = {
        "schema": "knowedge.homs_launch_assets.v1",
        "created_at": utc_now(),
        "status": "homs_launch_assets_ready",
        "episode_dir": str(ep),
        "visual_receipt": str(ep / "HOMS_VISUAL_ASSET_RECEIPT.json"),
        "site": "sites/homs/index.html",
        "outlook_first": outlook,
        "subject_marker": subject_marker(),
    }
    write_json(CAMPAIGN_DIR / "commercial_ops" / "HOMS_COMMERCIAL_OPS_RECEIPT.json", receipt)
    print(json.dumps({"status": receipt["status"], "site": receipt["site"], "episode": str(ep)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
