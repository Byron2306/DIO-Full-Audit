#!/usr/bin/env python3
"""Build an offline Launch Studio review package from the visually reviewed run."""
from __future__ import annotations

import hashlib
import html
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "acceptance_runs/68-product-sellability-20261027/launch-reviewed_v2"
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/LAUNCH_STUDIO_CUSTOMER_REVIEW_BUNDLE_20261104_V2"
VARIANTS = ("baseline", "messy-adversarial", "unseen")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    visual = json.loads((SOURCE / "LAUNCH_CREATIVE_VISUAL_REVIEW.json").read_text())
    source_summary = json.loads((SOURCE / "ACCEPTANCE_SUMMARY.json").read_text())
    if visual.get("failed_count") != 0 or visual.get("asset_count") != 9:
        raise ValueError("Launch Studio visual review is not a complete passing 9-asset review")
    cases = {row.get("variant"): row for row in source_summary.get("cases") or []}
    baseline_held = (cases.get("baseline") or {}).get("held_claims") or []
    messy_held = (cases.get("messy-adversarial") or {}).get("held_claims") or []
    unseen_held = (cases.get("unseen") or {}).get("held_claims") or []
    adversarial_claim = next((row for row in messy_held
                              if row.get("text") == "Guaranteed employment for every participant."), None)
    if (baseline_held or unseen_held or len(messy_held) != 1 or not adversarial_claim
            or adversarial_claim.get("state") != "held_out_of_marketing"
            or "not supported by an exact source quotation" not in str(adversarial_claim.get("reason") or "")):
        raise ValueError("Launch Studio adversarial claim fixture did not remain held outside marketing output")
    OUT.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    # Preserve the full approved-for-review variant packages, source binding
    # receipts, render metadata, and visual review beside a customer index.
    for variant in VARIANTS:
        src = SOURCE / variant
        dest = OUT / variant
        for name in ["assets", "review"]:
            shutil.copytree(src / name, dest / name, dirs_exist_ok=True)
        for name in ["landing.html", "styles.css", "channel_copy.json", "launch_schedule.csv",
                     "launch_schedule.json", "package_manifest.json", "controlled_launch_review.zip",
                     "CUSTOMER_EXECUTION_RECEIPT.json"]:
            shutil.copy2(src / name, dest / name)
    for name in ["LAUNCH_CREATIVE_CONTACT_SHEET.png", "LAUNCH_CREATIVE_VISUAL_REVIEW.json", "ACCEPTANCE_SUMMARY.json"]:
        shutil.copy2(SOURCE / name, OUT / name)

    # Require each rendered image to match both the source-binding and visual
    # review records before it is included in the customer preview.
    entries = []
    all_files = []
    for row in visual["assets"]:
        rel = (ROOT / row["path"]).relative_to(SOURCE)
        target = OUT / rel
        if not target.is_file() or digest(target) != row["sha256"]:
            raise ValueError(f"Rendered creative does not match visual review: {rel}")
        receipt = json.loads((OUT / rel.parts[0] / "review/SOURCE_BINDING_RECEIPT.json").read_text())
        if receipt.get("status") != "PASS" or receipt.get("failed_count", 0) != 0:
            raise ValueError(f"Source binding receipt does not pass for {rel.parts[0]}")
        copy_data = json.loads((OUT / rel.parts[0] / "channel_copy.json").read_text())
        channel = next(c for c in copy_data["channels"] if c["channel"] == row["channel"])
        schedule = json.loads((OUT / rel.parts[0] / "launch_schedule.json").read_text())
        scheduled = next(s for s in schedule["schedule"] if s["channel"] == row["channel"])
        entries.append({"variant": row["variant"], "channel": row["channel"], "path": rel.as_posix(),
                        "sha256": row["sha256"], "source_binding_status": row["source_binding_status"],
                        "source_binding_passed": row["source_binding_passed"], "copy": channel["copy"],
                        "planned_date": scheduled["planned_date"], "schedule_state": scheduled["status"],
                        "publication_authorized": scheduled["publication_authorized"]})

    baseline = {row["channel"]: row["sha256"] for row in entries if row["variant"] == "baseline"}
    messy = {row["channel"]: row["sha256"] for row in entries if row["variant"] == "messy-adversarial"}
    unseen = {row["channel"]: row["sha256"] for row in entries if row["variant"] == "unseen"}
    duplicate_adversarial = baseline == messy
    if not duplicate_adversarial:
        raise ValueError("Expected recorded baseline/adversarial equivalence changed; revise customer note")

    cards = []
    for row in entries:
        if row["variant"] == "messy-adversarial":
            continue  # Identical media are shown once and the equivalence is disclosed below.
        title = "Baseline" if row["variant"] == "baseline" else "Unseen input"
        cards.append(f"""<article class="creative"><div class="image-wrap"><img src="{html.escape(row['path'], quote=True)}" alt="{html.escape(title)} {html.escape(row['channel'].replace('_',' ').title())} campaign creative"></div>
<div class="creative-copy"><p class="tag">{html.escape(title)} · {html.escape(row['channel'].replace('_',' ').title())}</p><h3>{html.escape(row['copy']['headline'])}</h3><p>{html.escape(row['copy']['body'])}</p><p class="cta">{html.escape(row['copy']['cta'])}</p><p class="meta">Source binding: {row['source_binding_passed']} checks passed · Draft schedule: {html.escape(row['planned_date'])}</p></div></article>""")

    claim_safety_html = f"""<section><h2>Adversarial claim handling</h2><p>The messy-input case adds an unsupported employment guarantee. Launch Studio held it before it entered the generated marketing copy.</p><blockquote><strong>{html.escape(adversarial_claim['text'])}</strong></blockquote><dl><dt>State</dt><dd>{html.escape(adversarial_claim['state'])}</dd><dt>Reason</dt><dd>{html.escape(adversarial_claim['reason'])}</dd><dt>Supplied quotation</dt><dd>{html.escape(adversarial_claim.get('quote') or 'Not supplied')}</dd><dt>Baseline held claims</dt><dd>{len(baseline_held)}</dd><dt>Unseen held claims</dt><dd>{len(unseen_held)}</dd></dl><p>The baseline and adversarial final image hashes match because the unsupported claim was excluded before creative rendering. This fixture demonstrates claim screening; it does not demonstrate visual variation under adversarial inputs.</p></section>"""

    page = f"""<!doctype html><html lang="en-ZA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Launch Studio | Moya SkillLab review</title><style>
:root{{--ink:#18251f;--muted:#52645a;--forest:#193b2e;--leaf:#326249;--cream:#f4f3eb;--line:#d7ded6;--white:#fff;--amber:#754a00}}*{{box-sizing:border-box}}body{{margin:0;background:var(--cream);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}header{{background:var(--forest);color:white;padding:clamp(2.5rem,7vw,5.5rem) max(1.2rem,calc((100vw - 1120px)/2))}}.eyebrow{{letter-spacing:.14em;text-transform:uppercase;color:#bfdbca;font-size:.78rem;font-weight:700}}h1{{font-size:clamp(2.2rem,6vw,4rem);line-height:1.05;max-width:14ch;margin:.8rem 0}}header p{{max-width:70ch;color:#e3eee6}}main{{max-width:1120px;margin:2rem auto;padding:0 1.2rem 4rem}}section{{background:var(--white);border:1px solid var(--line);border-radius:16px;padding:clamp(1.2rem,3.5vw,2.2rem);margin:1.2rem 0}}h2{{margin:.1rem 0 .7rem;font-size:1.5rem}}.notice{{background:#fff4dd;border-left:5px solid #bb7b18;padding:1rem 1.2rem;border-radius:4px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,410px),1fr));gap:1rem}}.creative{{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:white}}.image-wrap{{background:#e7ebe6;display:grid;place-items:center;min-height:190px}}img{{display:block;width:100%;height:auto}}.creative-copy{{padding:1rem}}.tag{{color:var(--leaf);font-size:.8rem;font-weight:750;text-transform:uppercase;letter-spacing:.06em}}h3{{margin:.25rem 0 .5rem;font-size:1.2rem}}.cta{{font-weight:700}}.meta{{font-size:.9rem;color:var(--muted)}}a{{color:#174f3a;text-underline-offset:3px}}a:focus-visible{{outline:3px solid #9e6207;outline-offset:3px}}ul{{padding-left:1.2rem}}footer{{max-width:1120px;padding:0 1.2rem 2rem;margin:auto;color:var(--muted);font-size:.9rem}}
</style></head><body><header><div class="eyebrow">Launch Studio · review candidate</div><h1>Moya SkillLab campaign review</h1><p>A source-bound set of campaign creative previews for a synthetic customer example. Review the copy, image use, destination, and timing with the responsible owners before any campaign activity.</p></header><main>
<section><h2>Release status</h2><p class="notice"><strong>Review only.</strong> No content has been scheduled or published. The source package marks publication unauthorized and automatic posting off.</p>
<p>The reviewed source schedule contains a draft date of <strong>2 November 2026</strong>, which has passed. Replace it with a customer-approved date before reuse. The package preserves the original schedule as evidence and does not silently revise it.</p>
<p>Visual review: {visual['passed_count']} of {visual['asset_count']} creatives passed the recorded layout-collision review. Source binding: all nine creatives report 33 passed checks and zero failures.</p></section>
<section><h2>Creative previews</h2><div class="grid">{''.join(cards)}</div><p>Baseline and messy-adversarial final images share hashes for all three channels; the reason is explained in the claim-handling review below. The unseen-input set is distinct.</p></section>
{claim_safety_html}
<section><h2>Review materials</h2><ul><li><a href="LAUNCH_CREATIVE_CONTACT_SHEET.png">Nine-image contact sheet</a></li><li><a href="LAUNCH_CREATIVE_VISUAL_REVIEW.json">Per-creative visual review evidence</a></li><li><a href="ACCEPTANCE_SUMMARY.json">Acceptance summary</a></li>
{''.join(f'<li><a href="{v}/landing.html">{v.replace("-"," ").title()} landing-page preview</a> · <a href="{v}/channel_copy.json">channel copy</a> · <a href="{v}/launch_schedule.json">draft schedule</a> · <a href="{v}/review/SOURCE_BINDING_RECEIPT.json">source binding</a></li>' for v in VARIANTS)}</ul></section>
<section><h2>Owner review before use</h2><ul><li>Confirm brand and image rights, claims, copy, and landing-page destination.</li><li>Replace the past draft date with an approved campaign date and confirm the release owner.</li><li>Review the duplicate baseline/adversarial outputs and decide whether separate creative exploration is needed.</li></ul><p>The examples, brand images, and customer facts are synthetic acceptance fixtures. Visual review establishes layout fit only; it does not verify rights, message truth, audience fit, destination accuracy, campaign effectiveness, customer acceptance, or publication authority.</p></section></main><footer>Offline review package. No posting or spend is triggered by opening these files.</footer></body></html>"""
    (OUT / "index.html").write_text(page, encoding="utf-8")
    (OUT / "README.md").write_text("# Launch Studio customer review package\n\nOpen `index.html` to review source-bound campaign creatives, the recorded visual review, owner checks, and schedule status. The 2 November 2026 date is retained from the source schedule and is now past; replace it before use. The campaign remains unpublished and the fixtures are synthetic.\n", encoding="utf-8")

    # Include every copied file with a size/hash record for offline integrity.
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "BUNDLE_MANIFEST.json":
            all_files.append({"path": path.relative_to(OUT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)})
    manifest = {"schema": "dio.launch_studio.customer_review_bundle.v1", "source_run": str(SOURCE.relative_to(ROOT)),
                "visual_review_sha256": digest(OUT / "LAUNCH_CREATIVE_VISUAL_REVIEW.json"),
                "asset_count": 9, "source_bound_asset_count": 9, "visual_passed_count": 9,
                "baseline_and_messy_adversarial_media_identical": duplicate_adversarial,
                "adversarial_claim_hold_verified": True, "adversarial_held_claim_count": len(messy_held),
                "adversarial_claim_text_sha256": hashlib.sha256(adversarial_claim["text"].encode("utf-8")).hexdigest(),
                "adversarial_claim_hold_reason": adversarial_claim.get("reason"),
                "source_schedule_is_past_draft": True, "publication_authorized": False,
                "automatic_posting": False, "synthetic_fixture": True, "files": all_files}
    (OUT / "BUNDLE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    archive = OUT.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(OUT.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(OUT).as_posix())
    print(json.dumps({"bundle": str(OUT.relative_to(ROOT)), "archive": str(archive.relative_to(ROOT)),
                      "files": len(all_files) + 1, "creative_count": len(entries), "sha256": digest(archive)}, indent=2))


if __name__ == "__main__":
    main()
