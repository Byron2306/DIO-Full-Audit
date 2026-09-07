from __future__ import annotations

import hashlib
import html
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


T23_HTML_PROOF_SURFACE_DOSSIER_LINKING_VERSION = (
    "DIO_METAMORPHIC_ADAPTATION_T23_HTML_PROOF_SURFACE_DOSSIER_LINKING_GATE_V1"
)
T23_HTML_PROOF_SURFACE_DOSSIER_LINKING_READY_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T23_HTML_PROOF_SURFACE_DOSSIER_LINKING_READY"
)
T23_HTML_PROOF_SURFACE_DOSSIER_LINKING_REFUSED_TOKEN = (
    "DIO_METAMORPHIC_ADAPTATION_T23_HTML_PROOF_SURFACE_DOSSIER_LINKING_REFUSED"
)

T22_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_T22_HTML_PROOF_SURFACE_GENERATION_READY"
T22_CLAIM_TIER = "T22_INTERNAL_HTML_PROOF_SURFACE_GENERATED"
T23_CLAIM_TIER = "T23_INTERNAL_HTML_PROOF_SURFACE_DOSSIERS_LINKED"


@dataclass(frozen=True)
class LinkedDossier:
    source_path: str
    copied_path: str
    link_href: str
    sha256: str


@dataclass(frozen=True)
class T23HtmlProofSurfaceDossierLinkingReceipt:
    gate_version: str
    status: str
    allowed_claim_tier: str
    inherited_t22_claim_tier: str
    t22_status: str
    t22_receipt_sha256: str
    source_bound: bool
    t18_dossier_source_bound: bool
    t22_surface_source_bound: bool
    selected_product: str
    evidence_chain: list[str]
    dossiers_discovered: int
    dossiers_linked: int
    linked_dossiers: list[dict]
    dossier_index_path: str
    index_html_path: str
    dossier_links_written: bool
    local_html_preview_authorized: bool
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


def _is_dossier_candidate(path: Path) -> bool:
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    if not path.is_file():
        return False
    if path.suffix.lower() not in {".md", ".json", ".txt", ".html"}:
        return False
    if "dossier" not in name:
        return False
    if "receipt" in name or "receipts" in parts or "human_gates" in parts:
        return False
    return True


def _discover_dossiers(t18_dry_run_dir: Path) -> list[Path]:
    return sorted(path for path in t18_dry_run_dir.rglob("*") if _is_dossier_candidate(path))


def _safe_copy_name(source: Path, index: int) -> str:
    stem = source.stem.replace(" ", "_")
    suffix = source.suffix.lower() or ".txt"
    return f"{index:02d}_{stem}{suffix}"


def _copy_dossiers(dossiers: list[Path], proof_surface_dir: Path) -> list[LinkedDossier]:
    target_dir = proof_surface_dir / "dossiers"
    target_dir.mkdir(parents=True, exist_ok=True)
    linked: list[LinkedDossier] = []
    for index, source in enumerate(dossiers, start=1):
        target = target_dir / _safe_copy_name(source, index)
        shutil.copy2(source, target)
        linked.append(
            LinkedDossier(
                source_path=str(source),
                copied_path=str(target),
                link_href=f"dossiers/{target.name}",
                sha256=_sha256_path(target),
            )
        )
    return linked


def _append_dossier_section(index_html_path: Path, linked: list[LinkedDossier]) -> None:
    html_text = index_html_path.read_text()
    links = "\n".join(
        f'<li><a href="{html.escape(item.link_href)}">{html.escape(Path(item.link_href).name)}</a></li>'
        for item in linked
    )
    section = f"""
    <div class=\"lock\">
      <strong>Draft dossiers:</strong>
      <ul>
        {links}
      </ul>
      <p>Actual product execution authorized: false<br />External deployment authorized: false<br />Commercial validation authorized: false<br />Authority expansion authorized: false</p>
    </div>
"""
    if "Draft dossiers:" in html_text:
        return
    if "</section>" in html_text:
        html_text = html_text.replace("</section>", section + "  </section>", 1)
    else:
        html_text += section
    index_html_path.write_text(html_text)


def link_t23_dossiers_into_html_proof_surface(
    *,
    t22_receipt_path: Path,
    t18_dry_run_dir: Path,
    proof_surface_dir: Path,
    receipt_output_path: Path,
) -> T23HtmlProofSurfaceDossierLinkingReceipt:
    t22 = _load_json(t22_receipt_path)
    receipt_output_path.parent.mkdir(parents=True, exist_ok=True)

    index_html_path = proof_surface_dir / "index.html"
    dossier_index_path = proof_surface_dir / "dossier_index.json"

    t22_source_bound = t22_receipt_path.exists() and t22_receipt_path.is_file()
    t18_source_bound = t18_dry_run_dir.exists() and t18_dry_run_dir.is_dir()
    surface_source_bound = (
        proof_surface_dir.exists()
        and index_html_path.exists()
        and (proof_surface_dir / "proof_manifest.json").exists()
    )
    t22_status = str(t22.get("status", ""))
    inherited_tier = str(t22.get("allowed_claim_tier", ""))
    selected_product = str(t22.get("selected_product", ""))
    dossiers = _discover_dossiers(t18_dry_run_dir) if t18_source_bound else []

    ready = (
        t22_source_bound
        and t18_source_bound
        and surface_source_bound
        and t22_status == T22_READY_TOKEN
        and inherited_tier == T22_CLAIM_TIER
        and selected_product == "DIO_TRUST_DOSSIER_STUDIO"
        and t22.get("html_proof_surface_generated") is True
        and t22.get("local_html_preview_authorized") is True
        and str(t22.get("human_decision_applied", "")) == "APPROVE_LOCAL_RC"
        and str(t22.get("human_approval_state_after_decision", "")) == "APPROVED_LOCAL_RC_ONLY"
        and len(dossiers) >= 3
        and t22.get("actual_product_execution_authorized") is False
        and t22.get("product_capability_execution_authorized") is False
        and t22.get("external_deployment_authorized") is False
        and t22.get("external_use_authorized") is False
        and t22.get("commercial_validation_claim_authorized") is False
        and t22.get("authority_expansion_authorized") is False
    )

    linked: list[LinkedDossier] = []
    if ready:
        linked = _copy_dossiers(dossiers[:3], proof_surface_dir)
        dossier_index = {
            "status": T23_HTML_PROOF_SURFACE_DOSSIER_LINKING_READY_TOKEN,
            "claim_tier": T23_CLAIM_TIER,
            "selected_product": selected_product,
            "dossiers_linked": len(linked),
            "linked_dossiers": [asdict(item) for item in linked],
            "actual_product_execution_authorized": False,
            "external_deployment_authorized": False,
            "commercial_validation_claim_authorized": False,
            "authority_expansion_authorized": False,
        }
        dossier_index_path.write_text(json.dumps(dossier_index, indent=2, sort_keys=True) + "\n")
        _append_dossier_section(index_html_path, linked)

    receipt = T23HtmlProofSurfaceDossierLinkingReceipt(
        gate_version=T23_HTML_PROOF_SURFACE_DOSSIER_LINKING_VERSION,
        status=(
            T23_HTML_PROOF_SURFACE_DOSSIER_LINKING_READY_TOKEN
            if ready
            else T23_HTML_PROOF_SURFACE_DOSSIER_LINKING_REFUSED_TOKEN
        ),
        allowed_claim_tier=T23_CLAIM_TIER if ready else "T23_REFUSED_NO_DOSSIER_LINKING",
        inherited_t22_claim_tier=inherited_tier,
        t22_status=t22_status,
        t22_receipt_sha256=_sha256_path(t22_receipt_path) if t22_source_bound else "",
        source_bound=t22_source_bound and t18_source_bound and surface_source_bound,
        t18_dossier_source_bound=t18_source_bound,
        t22_surface_source_bound=surface_source_bound,
        selected_product=selected_product,
        evidence_chain=["T16", "T17", "T18", "T19", "T20", "T21", "T22", "T23"],
        dossiers_discovered=len(dossiers),
        dossiers_linked=len(linked),
        linked_dossiers=[asdict(item) for item in linked],
        dossier_index_path=str(dossier_index_path) if ready else "",
        index_html_path=str(index_html_path) if ready else "",
        dossier_links_written=ready,
        local_html_preview_authorized=ready,
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
            "This T23 gate links source-bound T18 draft dossier artifacts into the local T22 HTML proof "
            "surface for DIO_TRUST_DOSSIER_STUDIO. It authorizes only local inspection of linked draft "
            "dossiers inside the proof surface. It does not authorize actual product execution, product "
            "capability execution, external use, external deployment, autonomous development, commercial "
            "validation, product-market fit, professional approval, publication, spend, fulfilment, AGI, "
            "world-first status, autonomous consequential action, or authority expansion."
            if ready
            else "T23 HTML proof surface dossier linking refused because the T22 proof surface, T22 receipt, "
            "or T18 dossier source was not source-bound and ready. No execution, deployment, commercial, "
            "professional, publication, spend, fulfilment, AGI, world-first, autonomous-action, or "
            "authority-expansion claims are authorized."
        ),
    )

    receipt_output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
