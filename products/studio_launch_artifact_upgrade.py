from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any

from adapters.format_core.renderer import build_paragraph_semantic_content, render_semantic_asset
from presence_core.studio_release import prepare_studio_release
from products import studio_native_closure as closure


_ORIGINAL_CLOSE = closure.close_studio_case


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_correspondence_customer_artifact(result: dict[str, Any]) -> str:
    """Turn the controlled correspondence draft into a real Document Studio review surface.

    The current proof fixture is English-only. Translation/edit-and-translate are exposed as
    governed on-demand Document Studio routes, but are not falsely claimed as executed in this
    English fixture. External send remains human-held.
    """
    output_dir = Path(result["output_dir"]).resolve()
    manifest = result["manifest"]
    contract = manifest["artifact_contract"]
    draft = contract["draft"]
    customer_dir = output_dir / "closure" / "customer"
    render_dir = customer_dir / "document_studio_correspondence"
    customer_dir.mkdir(parents=True, exist_ok=True)

    rows = [{"paragraph_id": "P1", "text": str(draft["subject"])}]
    rows.extend(
        {"paragraph_id": f"P{index}", "text": str(line)}
        for index, line in enumerate(draft["body_lines"], 2)
    )
    semantic = build_paragraph_semantic_content(
        object_id=f"CORRESPONDENCE-{manifest['studio_id'].upper()}",
        version=str(manifest.get("studio_version") or "1.0.0"),
        title=str(draft["subject"]),
        source_language="English",
        source_rows=rows,
        context={
            "product": manifest["studio_id"],
            "artifact_type": "professional_correspondence_review",
            "audience": str(manifest["job"]["buyer"]),
            "purpose": str(contract["purpose"]),
        },
    )
    receipt = render_semantic_asset(
        semantic,
        render_dir,
        style_profile="dio_professional",
        delivery_profile="editable_review",
        language="English",
        channels=["html"],
        release_mode=False,
        source_root=closure.ROOT,
    )
    html_row = next((row for row in receipt.get("outputs") or [] if row.get("channel") == "html"), None)
    if not html_row or receipt.get("status") != "rendered_review_candidate" or not (receipt.get("qa") or {}).get("passed"):
        raise closure.StudioNativeClosureError("Document Studio correspondence review surface failed render QA")
    source = render_dir / str(html_row["path"])
    target = customer_dir / "PROFESSIONAL_CORRESPONDENCE_REVIEW.html"
    shutil.copyfile(source, target)
    (render_dir / "FORMAT_CORE_RECEIPT.json").unlink(missing_ok=True)

    route = {
        "schema": "dio.correspondence_document_studio_route.v1",
        "studio_id": manifest["studio_id"],
        "technical_formatting": {
            "state": "EXECUTED",
            "engine": "document_studio",
            "style_profile": "dio_professional",
            "delivery_profile": "editable_review",
            "qa_passed": True,
        },
        "technical_edit": {
            "state": "AVAILABLE_ON_AUTHORISED_REQUEST",
            "service": "technical_edit",
            "engine": "adapters.document_studio.pipeline.run_document_studio",
        },
        "translation": {
            "state": "AVAILABLE_ON_AUTHORISED_REQUEST_NOT_EXECUTED_IN_THIS_ENGLISH_FIXTURE",
            "services": ["translation", "edit_and_translate"],
            "requirements": [
                "target language selected",
                "document owner authorises processing",
                "proficient target-language reviewer supplied",
                "human final approval recorded",
            ],
            "engine": "adapters.document_studio.pipeline.run_document_studio",
            "possible_review_artifacts": [
                "CLEAN_EDITED_COPY.docx",
                "REDLINE_REVIEW_COPY.docx",
                "TRANSLATED_CLEAN_COPY.docx",
                "BILINGUAL_REVIEW_COPY.docx",
                "PDF review copies",
                "accessible HTML",
                "change ledger",
                "terminology glossary",
                "QA and human approval pack",
            ],
        },
        "outlook": {
            "state": "DRAFT_ONLY",
            "external_send": "REFUSE",
        },
        "human_gate": "NEEDS_YOU",
        "authority_created": False,
    }
    _write_json(customer_dir / "DOCUMENT_STUDIO_CORRESPONDENCE_ROUTE.json", route)
    _write_json(
        customer_dir / "DOCUMENT_STUDIO_CORRESPONDENCE_PRODUCT_RECEIPT.json",
        {
            "schema": "dio.correspondence_customer_artifact_receipt.v1",
            "studio_id": manifest["studio_id"],
            "customer_artifact": str(target.relative_to(output_dir)),
            "document_studio_formatting_executed": True,
            "translation_executed_in_this_fixture": False,
            "translation_route_available": True,
            "human_gate": "NEEDS_YOU",
            "external_send": "REFUSE",
            "authority_created": False,
        },
    )
    return str(target.relative_to(output_dir))


def _render_article_customer_artifact(result: dict[str, Any]) -> str:
    """Make Sophia's source/claim judgment part of the article the customer sees."""
    output_dir = Path(result["output_dir"]).resolve()
    manifest = result["manifest"]
    contract = manifest["artifact_contract"]
    sophia_path = Path(result["base"]["output_dir"]) / "native" / "sophia" / "SOPHIA_ARTICLE_LINEAGE.json"
    if not sophia_path.is_file():
        raise closure.StudioNativeClosureError("Article Studio final artifact requires Sophia lineage audit")
    sophia = json.loads(sophia_path.read_text(encoding="utf-8"))
    if sophia.get("source_reference_audit") != "PASS" or sophia.get("claim_lineage_audit") != "PASS":
        raise closure.StudioNativeClosureError("Sophia did not clear Article Studio lineage for human editorial review")

    customer_dir = output_dir / "closure" / "customer"
    customer_dir.mkdir(parents=True, exist_ok=True)
    target = customer_dir / "ARTICLE_PUBLICATION_REVIEW.html"

    sections = "".join(
        f"<section><h2>{html.escape(str(row['heading']))}</h2><p>{html.escape(str(row['body']))}</p></section>"
        for row in contract.get("sections") or []
    )
    reference_rows = "".join(
        "<li><strong>{}</strong><br><span>{}</span><br><small>Reference key: {} · supports {}</small></li>".format(
            html.escape(str(row.get("source_id") or "")),
            html.escape(str(row.get("citation") or "")),
            html.escape(str(row.get("reference_key") or "")),
            html.escape(", ".join(row.get("supports") or []) or "no declared claims"),
        )
        for row in sophia.get("references") or []
    )
    claim_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td><span class='state {}'>{}</span></td><td>{}</td></tr>".format(
            html.escape(str(row.get("claim_id") or "")),
            html.escape(str(row.get("text") or "")),
            "refused" if str(row.get("epistemic_state")) == "REFUSE" else "supported",
            html.escape(str(row.get("epistemic_state") or "")),
            html.escape(", ".join(row.get("evidence_ids") or []) or "None"),
        )
        for row in sophia.get("claims") or []
    )
    refused = [row for row in sophia.get("claims") or [] if str(row.get("epistemic_state")) == "REFUSE"]
    refused_list = "".join(f"<li>{html.escape(str(row.get('text') or ''))}</li>" for row in refused) or "<li>None in this controlled proof.</li>"

    page = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{html.escape(str(contract['headline']))}</title>
<style>
:root{{--ink:#171a20;--paper:#fbfaf6;--line:#d8d5cb;--accent:#184f52;--warn:#8a4a00;--ok:#17633d;--bad:#8b2635}}
*{{box-sizing:border-box}}body{{margin:0;background:#eceeea;color:var(--ink);font:17px/1.65 Georgia,serif}}
main{{width:min(1120px,calc(100% - 32px));margin:28px auto;background:var(--paper);box-shadow:0 18px 55px #1d2b2d20}}
.hero{{padding:52px 7% 34px;border-bottom:1px solid var(--line)}}.eyebrow{{font:800 .78rem/1.2 system-ui,sans-serif;letter-spacing:.12em;color:var(--accent)}}
h1{{font:750 clamp(2.7rem,6vw,5.4rem)/.96 system-ui,sans-serif;letter-spacing:-.055em;margin:.25em 0}}.standfirst{{font-size:1.25rem;color:#555;max-width:820px}}
.grid{{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(300px,.75fr);gap:0}}.article{{padding:38px 7% 56px}}.article h2{{font:750 1.45rem/1.2 system-ui,sans-serif;margin-top:2.1em;color:#223}}
.sophia{{padding:38px 32px;background:#f1f5f3;border-left:1px solid var(--line)}}.sophia h2,.sophia h3{{font-family:system-ui,sans-serif;color:var(--accent)}}
.gate{{padding:14px 16px;background:#fff0d7;border-left:5px solid #c47b00;font:700 .9rem/1.45 system-ui,sans-serif}}
table{{width:100%;border-collapse:collapse;font:14px/1.4 system-ui,sans-serif;margin:18px 0 28px}}th,td{{border:1px solid var(--line);padding:9px;vertical-align:top;text-align:left}}th{{background:#eef1ee}}
.state{{font-weight:800}}.state.supported{{color:var(--ok)}}.state.refused{{color:var(--bad)}}ol,ul{{padding-left:1.3em}}small{{color:#667}}
.truth{{padding:18px;border:1px solid #d8c49f;background:#fff8e8;font:14px/1.5 system-ui,sans-serif}}
@media(max-width:860px){{.grid{{grid-template-columns:1fr}}.sophia{{border-left:0;border-top:1px solid var(--line)}}}}
</style>
</head>
<body><main>
<header class='hero'><div class='eyebrow'>DIO ARTICLE & PUBLICATION STUDIO · SOPHIA-GOVERNED REVIEW</div>
<h1>{html.escape(str(contract['headline']))}</h1><p class='standfirst'>{html.escape(str(contract['standfirst']))}</p>
<p class='gate'>DRAFT ONLY. Sophia governs source/claim integrity; final wording, authorship and publication authority remain human-held.</p></header>
<div class='grid'><article class='article'>{sections}
<h2>References in this controlled proof</h2><ol>{reference_rows}</ol>
<div class='truth'><strong>Proof-input truth:</strong> these citations are controlled fixture records used to prove the editorial pipeline. This artifact does not assert that the named fixture publications exist in the external scholarly record. A customer run must bind the customer's supplied manuscript and source set.</div>
</article>
<aside class='sophia'><div class='eyebrow'>SOPHIA EDITORIAL GOVERNANCE</div><h2>Claim/source judgment</h2>
<p><strong>Reference audit:</strong> {html.escape(str(sophia.get('source_reference_audit')))}<br><strong>Claim lineage:</strong> {html.escape(str(sophia.get('claim_lineage_audit')))}</p>
<table><thead><tr><th>Claim</th><th>Text</th><th>State</th><th>Evidence</th></tr></thead><tbody>{claim_rows}</tbody></table>
<h3>Claims Sophia refuses to promote</h3><ul>{refused_list}</ul>
<h3>Authority boundary</h3><p>Sophia may audit sources, references and claim lineage. She does not invent evidence, replace the author's final wording, certify factual truth, or publish the article.</p>
</aside></div></main></body></html>"""
    target.write_text(page, encoding="utf-8")
    _write_json(
        customer_dir / "SOPHIA_PUBLICATION_GOVERNANCE.json",
        {
            "schema": "dio.article_studio_sophia_governance.v1",
            "studio_id": manifest["studio_id"],
            "sophia_audit_fingerprint": sophia.get("audit_fingerprint"),
            "source_reference_audit": sophia.get("source_reference_audit"),
            "claim_lineage_audit": sophia.get("claim_lineage_audit"),
            "refused_claim_count": len(refused),
            "proof_input_truth": "CONTROLLED_FIXTURE_NOT_EXTERNAL_SOURCE_VERIFICATION",
            "customer_runtime_requirement": "Bind the customer's supplied manuscript and source set before any customer-facing claim may be treated as grounded.",
            "authorship": "HUMAN_HELD",
            "publication": "REFUSE",
            "human_gate": "NEEDS_YOU",
            "authority_created": False,
            "customer_artifact": str(target.relative_to(output_dir)),
        },
    )
    return str(target.relative_to(output_dir))


def _refresh_proof(result: dict[str, Any], customer_entrypoint: str) -> dict[str, Any]:
    output_dir = Path(result["output_dir"]).resolve()
    presence_path = output_dir / "closure" / "presence" / "PRESENCE_STUDIO_RELEASE.json"
    release = prepare_studio_release(studio_id=result["manifest"]["studio_id"], entrypoint=customer_entrypoint)
    _write_json(presence_path, release)

    artifacts = []
    for path in sorted(p for p in (output_dir / "closure").rglob("*") if p.is_file()):
        artifacts.append({"path": str(path.relative_to(output_dir)), "sha256": closure._sha(path), "bytes": path.stat().st_size})
    ledger_path = output_dir / "NATIVE_CAPABILITY_CLOSURE_LEDGER.json"
    artifacts.append({"path": ledger_path.name, "sha256": closure._sha(ledger_path), "bytes": ledger_path.stat().st_size})

    proof = dict(result["proof_manifest"])
    proof["artifacts"] = artifacts
    proof["customer_artifact_entrypoint"] = customer_entrypoint
    proof["customer_artifact_gate"] = "PASS"
    proof.pop("proof_fingerprint", None)
    proof["proof_fingerprint"] = closure._fingerprint(proof)
    _write_json(output_dir / "NATIVE_CLOSURE_PROOF_MANIFEST.json", proof)

    receipt = dict(result["receipt"])
    receipt["proof_fingerprint"] = proof["proof_fingerprint"]
    receipt["customer_artifact_entrypoint"] = customer_entrypoint
    receipt["customer_artifact_gate"] = "PASS"
    receipt.pop("native_closure_fingerprint", None)
    receipt["native_closure_fingerprint"] = closure._fingerprint(receipt)
    _write_json(output_dir / "NATIVE_CLOSURE_RECEIPT.json", receipt)

    result["proof_manifest"] = proof
    result["receipt"] = receipt
    return result


def close_studio_case(*, manifest_path: Path, output_dir: Path, root: Path = closure.ROOT) -> dict[str, Any]:
    result = _ORIGINAL_CLOSE(manifest_path=manifest_path, output_dir=output_dir, root=root)
    kind = result["manifest"]["artifact_contract"]["kind"]
    if kind == "correspondence":
        entrypoint = _render_correspondence_customer_artifact(result)
        return _refresh_proof(result, entrypoint)
    if kind == "article":
        entrypoint = _render_article_customer_artifact(result)
        return _refresh_proof(result, entrypoint)
    return result


def install() -> None:
    """Install the launch artifact upgrade before the closure gauntlet imports its runner."""
    if getattr(closure, "_dio_launch_artifact_upgrade_installed", False):
        return
    closure.close_studio_case = close_studio_case
    closure._dio_launch_artifact_upgrade_installed = True


__all__ = ["close_studio_case", "install"]
