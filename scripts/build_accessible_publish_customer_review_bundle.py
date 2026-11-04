#!/usr/bin/env python3
"""Assemble a navigable, offline customer review bundle from a held Accessible Publish run."""
from __future__ import annotations

import hashlib
import html
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "acceptance_runs/68-product-sellability-20261027/ACCESSIBLE_PUBLISH_CUSTOMER_EXECUTION_20261104_V10"
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE_20261104_V1"
FILES = [
    "SOURCE.html", "PREPARED_REVIEW.html", "ACCESSIBILITY_REVIEW.html",
    "ACCESSIBILITY_REVIEW.json", "RENDERED_ACCESSIBILITY_REVIEW.json",
    "OWNER_REMEDIATION_REQUEST.md", "OWNER_REMEDIATION_REQUEST.json",
    "ACCESSIBLE_PUBLISH_RECEIPT.json", "CUSTOMER_EXECUTION_RECEIPT.json",
    "RENDERED_ACCESSIBILITY_EXECUTION_EVIDENCE.json",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    review = json.loads((RUN / "ACCESSIBILITY_REVIEW.json").read_text())
    evidence = json.loads((RUN / "RENDERED_ACCESSIBILITY_EXECUTION_EVIDENCE.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        source = RUN / name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copy2(source, OUT / name)

    findings = [row for row in review["before"]["issues"] + review["after"]["issues"]
                if row["state"] == "ACTION_REQUIRED"]
    findings = list({row["check"]: row for row in findings}.values())
    escaped_findings = "".join(
        f"<tr><th scope='row'>{html.escape(row['check'].replace('_', ' ').title())}</th>"
        f"<td>{html.escape(row['state'].replace('_', ' ').title())}</td>"
        f"<td>{html.escape(row['detail'])}</td></tr>" for row in findings
    )
    artifact_links = "".join(
        f"<li><a href='{html.escape(name, quote=True)}'>{html.escape(name.replace('_', ' ').replace('.json', ' data').replace('.html', ' page').replace('.md', ' checklist'))}</a></li>"
        for name in FILES
    )
    page = f"""<!doctype html>
<html lang="en-ZA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Accessible Publish | Review package</title><style>
:root{{color-scheme:light;--ink:#172521;--muted:#4b5d56;--paper:#f4f5ef;--card:#fff;--green:#215b48;--line:#d4ddd6;--amber:#7a4b00;}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
header{{background:#17372d;color:#f7faf5;padding:clamp(2rem,6vw,5rem) max(1.2rem,calc((100vw - 1040px)/2))}}
.kicker{{text-transform:uppercase;letter-spacing:.13em;font-size:.78rem;color:#bbd6c5;font-weight:700}}h1{{font-size:clamp(2rem,5vw,3.6rem);line-height:1.08;max-width:15ch;margin:.7rem 0}}header p{{max-width:70ch;color:#e3eee7}}
main{{max-width:1040px;margin:2rem auto;padding:0 1.2rem 3rem}}section{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:clamp(1.1rem,3vw,2rem);margin:1rem 0;box-shadow:0 8px 25px #132c1d0a}}
h2{{font-size:1.35rem;margin:.1rem 0 .7rem}}.hold{{border-left:5px solid #c28320;background:#fff7e6;padding:1rem 1.2rem;border-radius:5px;color:#382a11}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.8rem}}.stat{{border:1px solid var(--line);border-radius:10px;padding:1rem}}.stat strong{{display:block;font-size:1.5rem;color:var(--green)}}.stat span{{color:var(--muted);font-size:.9rem}}
table{{border-collapse:collapse;width:100%;margin-top:.7rem}}th,td{{border-bottom:1px solid var(--line);padding:.8rem;text-align:left;vertical-align:top}}th{{width:24%;color:var(--green)}}a{{color:#155d46;text-underline-offset:3px}}a:focus-visible{{outline:3px solid #9b5e00;outline-offset:3px}}.links{{columns:2;column-gap:2rem}}.links li{{break-inside:avoid;margin:.35rem 0}}code{{overflow-wrap:anywhere}}footer{{color:var(--muted);font-size:.9rem;margin-top:1.4rem}}
@media(max-width:600px){{.links{{columns:1}}table,tbody,tr,th,td{{display:block}}tr{{padding:.55rem 0}}th{{width:auto;padding-bottom:.1rem}}td{{border:0;padding-top:.2rem}}}}
</style></head><body><header><div class="kicker">Accessible Publish · controlled review</div><h1>Accessibility review package</h1>
<p>A source-bound review of a synthetic page, prepared for owner and accessibility specialist follow-up. This package records findings and review boundaries; it does not certify conformance.</p></header>
<main><section aria-labelledby="status"><h2 id="status">Review status</h2><p class="hold"><strong>Held for human review.</strong> No WCAG conformance, release authorization, or external publication is claimed.</p>
<div class="stats"><div class="stat"><strong>{evidence['viewport_count']}</strong><span>viewport sizes reviewed</span></div><div class="stat"><strong>{evidence['contrast_failure_count']}</strong><span>rendered contrast findings</span></div><div class="stat"><strong>{evidence['focus_failure_count']}</strong><span>focus visibility findings</span></div><div class="stat"><strong>{evidence['script_generated_focusable_delta']}</strong><span>additional scripted focusable controls observed</span></div></div>
<p>All requests were blocked during the isolated scripted browser pass. The review found no horizontal overflow in the four tested viewports. These are bounded observations from this synthetic fixture.</p></section>
<section aria-labelledby="findings"><h2 id="findings">Findings requiring owner review</h2><table><thead><tr><th scope="col">Check</th><th scope="col">State</th><th scope="col">Recorded finding</th></tr></thead><tbody>{escaped_findings}</tbody></table>
<p>Use the owner remediation checklist to provide the missing labels and link purpose, then review contrast and keyboard focus with the responsible accessibility specialist.</p></section>
<section aria-labelledby="limits"><h2 id="limits">What this review does not establish</h2><ul><li>It does not establish full WCAG conformance, screen-reader behavior, PDF/UA, or user acceptance.</li><li>It does not verify destination correctness, server responses, complete journeys, or all dynamic behavior.</li><li>The example is synthetic and does not represent an audit of a real customer website.</li></ul></section>
<section aria-labelledby="files"><h2 id="files">Review files</h2><ul class="links">{artifact_links}</ul><p>Reviewed source SHA-256: <code>{html.escape(review['source_sha256'])}</code></p></section>
<footer>Prepared from the held customer execution dated 4 November 2026. Review details and source files are retained alongside this package.</footer></main></body></html>"""
    (OUT / "index.html").write_text(page, encoding="utf-8")
    (OUT / "README.md").write_text(
        "# Accessible Publish customer review package\n\n"
        "Open `index.html` for the navigable review summary. The page, findings, owner checklist, source, and execution evidence are included. "
        "This is a controlled synthetic example held for human accessibility review; it makes no conformance or publication claim.\n",
        encoding="utf-8")
    manifest = {"schema": "dio.accessible_publish.customer_review_bundle.v1", "source_run": str(RUN.relative_to(ROOT)),
                "source_sha256": review["source_sha256"], "release_authorized": False,
                "external_publication": False, "conformance_claim": "NONE",
                "files": [{"path": p.name, "bytes": p.stat().st_size, "sha256": sha(p)}
                          for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "BUNDLE_MANIFEST.json"]}
    (OUT / "BUNDLE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    archive = OUT.parent / "ACCESSIBLE_PUBLISH_CUSTOMER_REVIEW_BUNDLE_20261104_V1.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(OUT.iterdir()):
            if p.is_file():
                zf.write(p, arcname=p.name)
    print(json.dumps({"bundle": str(OUT.relative_to(ROOT)), "archive": str(archive.relative_to(ROOT)),
                      "files": len(manifest["files"]) + 1, "sha256": sha(archive)}, indent=2))


if __name__ == "__main__":
    main()
