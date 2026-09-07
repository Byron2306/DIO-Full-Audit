from __future__ import annotations

import hashlib
import html
import json
from dataclasses import asdict, dataclass
from pathlib import Path


T22_HTML_PROOF_SURFACE_GENERATION_VERSION = (
    "DIO_METAMORPHIC_ADAPTATION_T22_HTML_PROOF_SURFACE_GENERATION_GATE_V1"
)
T22_HTML_PROOF_SURFACE_GENERATION_READY_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T22_HTML_PROOF_SURFACE_GENERATION_READY"
)
T22_HTML_PROOF_SURFACE_GENERATION_REFUSED_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T22_HTML_PROOF_SURFACE_GENERATION_REFUSED"
)

T21_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_T21_HUMAN_DECISION_APPLICATION_READY"
T21_APPROVED_LOCAL_RC_ONLY = "T21_HUMAN_APPROVED_LOCAL_RC_ONLY"
T22_CLAIM_TIER = "T22_INTERNAL_HTML_PROOF_SURFACE_GENERATED"


@dataclass(frozen=True)
class T22HtmlProofSurfaceGenerationReceipt:
    gate_version: str
    status: str
    allowed_claim_tier: str
    inherited_t21_claim_tier: str
    t21_status: str
    t21_receipt_sha256: str
    source_bound: bool
    selected_product: str
    evidence_chain: list[str]
    human_decision_applied: str
    human_approval_state_after_decision: str
    local_rc_approved: bool
    synthetic_dry_run_evidence: bool
    synthetic_inputs_processed: int
    draft_dossiers_written: int
    dry_run_receipts_written: int
    human_gate_checks_written: int
    human_gates_preserved: bool
    html_proof_surface_generated: bool
    local_html_preview_authorized: bool
    index_html_path: str
    proof_manifest_path: str
    readme_path: str
    actual_product_execution_authorized: bool
    product_capability_execution_authorized: bool
    external_use_authorized: bool
    external_deployment_authorized: bool
    autonomous_development_authorized: bool
    autonomous_action_claim_authorized: bool
    commercial_validation_claim_authorized: bool
    product_market_fit_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    agi_claim_authorized: bool
    world_first_claim_authorized: bool
    authority_expansion_authorized: bool
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return int(value or 0)


def _bool(value: object) -> bool:
    return value is True


def _build_manifest(t21: dict, t21_sha256: str) -> dict:
    return {
        "status": T22_HTML_PROOF_SURFACE_GENERATION_READY_TOKEN,
        "claim_tier": T22_CLAIM_TIER,
        "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
        "surface_type": "internal_local_static_html_proof",
        "evidence_chain": ["T16", "T17", "T18", "T19", "T20", "T21", "T22"],
        "t21_receipt_sha256": t21_sha256,
        "human_decision_applied": str(t21.get("human_decision_applied", "")),
        "human_approval_state_after_decision": str(
            t21.get("human_approval_state_after_decision", "")
        ),
        "synthetic_dry_run_evidence": _bool(t21.get("synthetic_dry_run_evidence")),
        "synthetic_inputs_processed": _as_int(t21.get("synthetic_inputs_processed")),
        "draft_dossiers_written": _as_int(t21.get("draft_dossiers_written")),
        "dry_run_receipts_written": _as_int(t21.get("dry_run_receipts_written")),
        "human_gate_checks_written": _as_int(t21.get("human_gate_checks_written")),
        "human_gates_preserved": _bool(t21.get("human_gates_preserved")),
        "local_html_preview_authorized": True,
        "actual_product_execution_authorized": False,
        "product_capability_execution_authorized": False,
        "external_use_authorized": False,
        "external_deployment_authorized": False,
        "commercial_validation_claim_authorized": False,
        "product_market_fit_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "agi_claim_authorized": False,
        "world_first_claim_authorized": False,
        "authority_expansion_authorized": False,
    }


def _render_html(manifest: dict) -> str:
    selected_product = html.escape(str(manifest["selected_product"]))
    chain = " → ".join(manifest["evidence_chain"])
    rows = [
        ("Status", "Internal local HTML proof surface"),
        ("Selected product", selected_product),
        ("Evidence chain", html.escape(chain)),
        ("Human decision", html.escape(str(manifest["human_decision_applied"]))),
        (
            "Human approval state",
            html.escape(str(manifest["human_approval_state_after_decision"])),
        ),
        ("Synthetic dry-run evidence", str(manifest["synthetic_dry_run_evidence"]).lower()),
        ("Synthetic inputs processed", str(manifest["synthetic_inputs_processed"])),
        ("Draft dossiers written", str(manifest["draft_dossiers_written"])),
        ("Dry-run receipts written", str(manifest["dry_run_receipts_written"])),
        ("Human gate checks written", str(manifest["human_gate_checks_written"])),
        ("Human gates preserved", str(manifest["human_gates_preserved"]).lower()),
        (
            "Actual product execution authorized",
            str(manifest["actual_product_execution_authorized"]).lower(),
        ),
        (
            "External deployment authorized",
            str(manifest["external_deployment_authorized"]).lower(),
        ),
        (
            "Commercial validation authorized",
            str(manifest["commercial_validation_claim_authorized"]).lower(),
        ),
        (
            "Authority expansion authorized",
            str(manifest["authority_expansion_authorized"]).lower(),
        ),
    ]
    row_html = "\n".join(
        f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in rows
    )
    boundary_facts = "\n".join(
        [
            "Actual product execution authorized: false",
            "External deployment authorized: false",
            "Commercial validation authorized: false",
            "Authority expansion authorized: false",
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{selected_product} · DIO T22 HTML Proof Surface</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
    body {{ margin: 0; background: #090b10; color: #f5f7fb; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 56px 22px; }}
    .card {{ border: 1px solid #273246; border-radius: 24px; padding: 28px; background: linear-gradient(145deg, #111827, #0c1018); box-shadow: 0 24px 70px rgba(0,0,0,.38); }}
    .eyebrow {{ color: #93a4c8; letter-spacing: .14em; text-transform: uppercase; font-size: 12px; }}
    h1 {{ margin: 10px 0 12px; font-size: clamp(34px, 7vw, 64px); line-height: .96; }}
    p {{ color: #cbd5e1; font-size: 18px; line-height: 1.65; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 28px; overflow: hidden; border-radius: 18px; }}
    th, td {{ padding: 13px 15px; border-bottom: 1px solid #253047; text-align: left; vertical-align: top; }}
    th {{ color: #aab7d4; width: 38%; font-weight: 650; }}
    .lock {{ margin-top: 28px; padding: 18px; border-radius: 18px; background: #161b27; border: 1px solid #2d3a56; color: #dbeafe; }}
    pre {{ white-space: pre-wrap; margin: 14px 0 0; color: #fef3c7; }}
  </style>
</head>
<body>
<main>
  <section class="card">
    <div class="eyebrow">DIO Metamorphic Adaptation · T22</div>
    <h1>{selected_product}</h1>
    <p>DIO generated this local, receipt-bound static HTML proof surface for a human-gated product candidate. It is a readable proof surface, not a deployed product, commercial validation event, autonomous execution event, or authority-expansion event.</p>
    <table aria-label="DIO proof facts">
      {row_html}
    </table>
    <div class="lock">
      <strong>Boundary lock:</strong> This proof surface may be inspected locally. It does not authorize actual product execution, external use, deployment, publication, spend, fulfilment, product-market-fit claims, commercial validation, professional approval, AGI claims, world-first claims, or authority expansion.
      <pre>{boundary_facts}</pre>
    </div>
  </section>
</main>
</body>
</html>
"""


def _render_readme(manifest: dict) -> str:
    return "\n".join(
        [
            "# DIO_TRUST_DOSSIER_STUDIO T22 HTML Proof Surface",
            "",
            "This folder is an internal local static HTML proof surface generated from the source-bound T21 human decision application receipt.",
            "",
            "It is not a deployed product, production implementation, commercial validation, professional approval, AGI claim, world-first claim, or authority expansion.",
            "",
            "Open `index.html` locally to inspect the proof surface.",
            "Read `proof_manifest.json` for the receipt-bound proof facts.",
            "",
            f"Evidence chain: {' -> '.join(manifest['evidence_chain'])}",
            f"Selected product: {manifest['selected_product']}",
            "External deployment authorized: false",
            "Commercial validation authorized: false",
            "Authority expansion authorized: false",
            "",
        ]
    )


def build_t22_html_proof_surface(
    *,
    t21_receipt_path: Path,
    output_dir: Path,
    receipt_output_path: Path,
) -> T22HtmlProofSurfaceGenerationReceipt:
    t21 = _load_json(t21_receipt_path)
    receipt_output_path.parent.mkdir(parents=True, exist_ok=True)

    source_bound = t21_receipt_path.exists() and t21_receipt_path.is_file()
    t21_status = str(t21.get("status", ""))
    inherited_tier = str(t21.get("allowed_claim_tier", ""))
    selected_product = str(t21.get("selected_product", ""))

    ready = (
        source_bound
        and t21_status == T21_READY_TOKEN
        and inherited_tier == T21_APPROVED_LOCAL_RC_ONLY
        and selected_product == "DIO_TRUST_DOSSIER_STUDIO"
        and str(t21.get("human_decision_applied", "")) == "APPROVE_LOCAL_RC"
        and str(t21.get("human_approval_state_after_decision", "")) == "APPROVED_LOCAL_RC_ONLY"
        and t21.get("local_rc_approved") is True
        and t21.get("release_approved") is True
        and t21.get("local_release_candidate_claim_authorized") is True
        and t21.get("release_candidate_packaging_authorized") is True
        and t21.get("human_gates_preserved") is True
        and _as_int(t21.get("synthetic_inputs_processed")) >= 3
        and _as_int(t21.get("draft_dossiers_written")) >= 3
        and _as_int(t21.get("dry_run_receipts_written")) >= 3
        and _as_int(t21.get("human_gate_checks_written")) >= 3
        and t21.get("actual_product_execution_authorized") is False
        and t21.get("product_capability_execution_authorized") is False
        and t21.get("external_use_authorized") is False
        and t21.get("external_deployment_authorized") is False
        and t21.get("commercial_validation_claim_authorized") is False
        and t21.get("authority_expansion_authorized") is False
    )

    t21_sha = _sha256_path(t21_receipt_path)
    index_html_path = output_dir / "index.html"
    proof_manifest_path = output_dir / "proof_manifest.json"
    readme_path = output_dir / "README.md"

    if ready:
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest = _build_manifest(t21, t21_sha)
        proof_manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        index_html_path.write_text(_render_html(manifest))
        readme_path.write_text(_render_readme(manifest))

    receipt = T22HtmlProofSurfaceGenerationReceipt(
        gate_version=T22_HTML_PROOF_SURFACE_GENERATION_VERSION,
        status=(
            T22_HTML_PROOF_SURFACE_GENERATION_READY_TOKEN
            if ready
            else T22_HTML_PROOF_SURFACE_GENERATION_REFUSED_TOKEN
        ),
        allowed_claim_tier=T22_CLAIM_TIER if ready else "T22_REFUSED_NO_HTML_PROOF_SURFACE",
        inherited_t21_claim_tier=inherited_tier,
        t21_status=t21_status,
        t21_receipt_sha256=t21_sha,
        source_bound=source_bound,
        selected_product=selected_product,
        evidence_chain=["T16", "T17", "T18", "T19", "T20", "T21", "T22"],
        human_decision_applied=str(t21.get("human_decision_applied", "")),
        human_approval_state_after_decision=str(t21.get("human_approval_state_after_decision", "")),
        local_rc_approved=t21.get("local_rc_approved") is True,
        synthetic_dry_run_evidence=t21.get("synthetic_dry_run_evidence") is True,
        synthetic_inputs_processed=_as_int(t21.get("synthetic_inputs_processed")),
        draft_dossiers_written=_as_int(t21.get("draft_dossiers_written")),
        dry_run_receipts_written=_as_int(t21.get("dry_run_receipts_written")),
        human_gate_checks_written=_as_int(t21.get("human_gate_checks_written")),
        human_gates_preserved=t21.get("human_gates_preserved") is True,
        html_proof_surface_generated=ready,
        local_html_preview_authorized=ready,
        index_html_path=str(index_html_path) if ready else "",
        proof_manifest_path=str(proof_manifest_path) if ready else "",
        readme_path=str(readme_path) if ready else "",
        actual_product_execution_authorized=False,
        product_capability_execution_authorized=False,
        external_use_authorized=False,
        external_deployment_authorized=False,
        autonomous_development_authorized=False,
        autonomous_action_claim_authorized=False,
        commercial_validation_claim_authorized=False,
        product_market_fit_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        agi_claim_authorized=False,
        world_first_claim_authorized=False,
        authority_expansion_authorized=False,
        boundary=(
            "This T22 gate converts a source-bound T21 APPROVE_LOCAL_RC decision into an internal "
            "local static HTML proof surface for DIO_TRUST_DOSSIER_STUDIO. It authorizes only local "
            "HTML preview of receipt-bound proof facts. It does not authorize actual product execution, "
            "product capability execution, external use, external deployment, autonomous development, "
            "commercial validation, product-market fit, professional approval, publication, spend, "
            "fulfilment, AGI, world-first status, autonomous consequential action, or authority expansion."
            if ready
            else "T22 HTML proof surface generation refused because the T21 receipt did not carry an "
            "approved-local-RC-only human decision with preserved boundary locks. No local proof surface, "
            "release, execution, deployment, commercial, professional, publication, spend, fulfilment, AGI, "
            "world-first, autonomous-action, or authority-expansion claims are authorized."
        ),
    )

    receipt_output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
