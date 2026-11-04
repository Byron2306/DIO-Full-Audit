from __future__ import annotations

import copy
import hashlib
import html
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from products.governed_case import canonical_hash, validate_case


PROFILE_SCHEMA = "dio.dossier_assembly.profile.v1"
PROCESSOR_ID = "controlled_dossier_assembly_v1"
ARTIFACT_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{1,79}")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path: Path, value: bytes) -> str:
    path.write_bytes(value)
    return _sha_bytes(value)


def _gate(case: dict[str, Any], gate_id: str) -> dict[str, Any]:
    return next(row for row in case["gates"] if row["gate_id"] == gate_id)


def _digest(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).removeprefix("sha256:")


def validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ValueError(f"Dossier assembly profile requires schema={PROFILE_SCHEMA}.")
    if not str(profile.get("profile_id") or "").strip():
        raise ValueError("Dossier assembly profile requires profile_id.")
    if not str(profile.get("product_id") or "").strip():
        raise ValueError("Dossier assembly profile requires product_id.")
    if profile.get("identity_state") != "genuine_profile_extension_unpromoted":
        raise ValueError("Dossier assembly profile must remain an unpromoted genuine profile extension.")
    if profile.get("canonical_portfolio_registration") is not False:
        raise ValueError("Dossier assembly profile cannot claim canonical portfolio registration.")
    if profile.get("document_studio_receipt_schema") != "dio.document_studio.receipt.v1":
        raise ValueError("Dossier assembly profile must bind the controlled Document Studio receipt schema.")
    if profile.get("authority_created") is not False:
        raise ValueError("Dossier assembly profile cannot create authority.")
    if profile.get("external_effects") is not False:
        raise ValueError("Dossier assembly profile cannot create external effects.")
    if profile.get("external_release") is not False:
        raise ValueError("Dossier assembly profile cannot grant external release.")


def _validate_document_studio_receipt(
    path: Path,
    *,
    expected_schema: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Document Studio receipt is not valid UTF-8 JSON: {path.name}") from exc

    if payload.get("schema") != expected_schema:
        raise ValueError("DossierOps requires a recognised Document Studio receipt schema.")
    if payload.get("status") != "human_review_required":
        raise ValueError("DossierOps only binds Document Studio artifacts that remain human-review gated.")

    release = payload.get("release") or {}
    if release.get("delivery_released") is not False:
        raise ValueError("DossierOps refuses a Document Studio receipt that claims delivery release.")
    if release.get("human_approval_required") is not True:
        raise ValueError("DossierOps requires Document Studio human approval to remain explicit.")
    if release.get("release_readiness") != "blocked_pending_human_approval":
        raise ValueError("DossierOps requires Document Studio release readiness to remain blocked.")

    return {
        "job_id": payload.get("job_id"),
        "status": payload.get("status"),
        "delivery_released": False,
        "human_approval_required": True,
        "release_readiness": release.get("release_readiness"),
    }


def _safe_artifact_id(value: Any) -> str:
    artifact_id = str(value or "").strip()
    if not ARTIFACT_ID_PATTERN.fullmatch(artifact_id):
        raise ValueError(
            "Dossier artifact_id must contain 2-80 letters, numbers, dots, underscores, or hyphens."
        )
    return artifact_id


def _render_index_html(index: dict[str, Any], *, title: str) -> bytes:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    rows = []
    for position, row in enumerate(index["items"]):
        copied_path = str(row["copied_path"])
        rows.append(
            f"<tr data-index='{position}'>"
            f"<th scope='row'>{esc(row['artifact_id'])}</th>"
            f"<td>{esc(row['artifact_type'])}</td>"
            f"<td>{esc(row['source_system'])}</td>"
            f"<td>{esc(row['approval_state'])}</td>"
            f"<td><a href='{esc(copied_path)}'>Open included file</a><small>{esc(row['source_name'])}</small></td>"
            f"<td><code>{esc(row['sha256'])}</code></td>"
            "<td><label class='review-label'>Decision"
            "<select data-field='reviewer_decision'><option value=''>Pending review</option>"
            "<option>ACCEPT_FOR_DOSSIER</option><option>REQUEST_CORRECTION</option>"
            "<option>HOLD</option><option>REJECT</option></select></label>"
            "<label class='review-label'>Reviewer<input data-field='reviewer_name' autocomplete='name'></label>"
            "<label class='review-label'>Rationale<textarea data-field='rationale' rows='2'></textarea></label></td>"
            "</tr>"
        )
    item_json = json.dumps(index["items"], ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    page = f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{esc(title)}</title>
<style>
:root{{color-scheme:light;--ink:#172b29;--muted:#536862;--line:#cbd5d0;--paper:#f2f5f2;--green:#174b43;--gold:#bd8740;}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}
main{{max-width:1500px;margin:auto;padding:clamp(1rem,4vw,3rem)}}h1{{font-size:clamp(1.8rem,4vw,3rem);line-height:1.1;max-width:950px}}
.eyebrow{{font-size:.8rem;letter-spacing:.11em;text-transform:uppercase;color:var(--muted)}}
.hold{{border-left:5px solid var(--gold);background:#fff8e9;padding:1rem 1.2rem;font-weight:650}}
.summary{{display:flex;gap:.8rem;flex-wrap:wrap;margin:1.2rem 0}}.summary span{{background:white;border:1px solid var(--line);padding:.65rem .9rem;border-radius:.35rem}}
.toolbar{{display:flex;gap:.8rem;align-items:end;flex-wrap:wrap;margin:1.4rem 0}}label{{display:block;font-size:.9rem;font-weight:600}}
input,select,textarea,button{{font:inherit}}input[type=search],select,textarea{{display:block;width:100%;padding:.55rem;border:1px solid #80948d;border-radius:.25rem;background:white;color:var(--ink)}}
input[type=search]{{min-width:min(22rem,80vw)}}button{{border:0;border-radius:.3rem;background:var(--green);color:white;padding:.7rem 1rem;font-weight:650;cursor:pointer}}
a{{color:#075e70}}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{{outline:3px solid var(--gold);outline-offset:3px}}
.scroll{{overflow:auto;background:white;border:1px solid var(--line);border-radius:.4rem}}table{{border-collapse:collapse;width:100%;min-width:1120px}}caption{{text-align:left;padding:1rem;font-weight:650}}
th,td{{padding:.8rem;vertical-align:top;border-bottom:1px solid var(--line);text-align:left}}thead th{{background:var(--green);color:white;position:sticky;top:0}}tbody th{{min-width:8rem}}td small{{display:block;color:var(--muted);overflow-wrap:anywhere}}
td code{{font-size:.82rem;overflow-wrap:anywhere}}.review-label{{margin:.45rem 0}}.actions{{display:flex;gap:.8rem;flex-wrap:wrap;align-items:center;margin:1rem 0}}#status{{min-height:1.5em;color:var(--muted)}}
.boundary{{color:var(--muted);max-width:1000px;margin-top:2rem}}.skip{{position:absolute;left:-10000px;top:auto}}.skip:focus{{left:1rem;top:1rem;background:white;padding:.8rem;z-index:10}}
[hidden]{{display:none!important}}@media print{{body{{background:white}}main{{max-width:none;padding:0}}.toolbar,.actions,.review-label{{display:none!important}}table{{min-width:0;font-size:9pt}}td,th{{padding:4pt}}}}
</style></head><body><a class='skip' href='#records'>Skip to dossier records</a><main>
<p class='eyebrow'>DossierOps · controlled assembly</p><h1>{esc(title)}</h1>
<p class='hold'>Human dossier review required. External release is refused.</p>
<p>This index lists and hash-binds supplied files. Review decisions below are local to this page; download the worksheet to retain them. Nothing is submitted, approved, or transmitted.</p>
<div class='summary'><span><strong>{len(index['items'])}</strong> indexed artifacts</span><span>Completeness and sufficiency: <strong>NEEDS YOU</strong></span><span>Final release: <strong>NEEDS YOU</strong></span></div>
<section class='toolbar' aria-label='Dossier tools'><label for='filter'>Find an artifact<input id='filter' type='search' placeholder='ID, type, source or filename'></label><p id='count' aria-live='polite'>{len(index['items'])} artifacts shown</p></section>
<div class='scroll' id='records' tabindex='0' role='region' aria-label='Scrollable dossier artifact and review table'>
<table><caption>Included artifacts and reviewer worksheet</caption><thead><tr><th scope='col'>Artifact ID</th><th scope='col'>Type</th><th scope='col'>Source</th><th scope='col'>Supplied approval state</th><th scope='col'>File</th><th scope='col'>SHA-256</th><th scope='col'>Human review fields</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<div class='actions'><button id='download' type='button'>Download review worksheet CSV</button><span id='status' role='status' aria-live='polite'></span></div>
<p class='boundary'>This assembly does not determine completeness, sufficiency, authenticity, legal effect, retention, submission, or release. Source and approval labels are carried from supplied records and remain unverified. A reviewer must validate the files and obtain separate release authority.</p>
<script type='application/json' id='dossier-data'>{item_json}</script>
<script>
const records=JSON.parse(document.querySelector('#dossier-data').textContent);
const filter=document.querySelector('#filter');
filter.addEventListener('input',()=>{{const term=filter.value.trim().toLowerCase();let shown=0;for(const row of document.querySelectorAll('tbody tr')){{const item=records[Number(row.dataset.index)];const hay=[item.artifact_id,item.artifact_type,item.source_system,item.approval_state,item.source_name,item.copied_path].join(' ').toLowerCase();row.hidden=Boolean(term)&&!hay.includes(term);if(!row.hidden)shown++}}document.querySelector('#count').textContent=shown+' of '+records.length+' artifacts shown'}});
const csvCell=value=>'"'+String(value??'').replaceAll('"','""')+'"';
document.querySelector('#download').addEventListener('click',()=>{{const headers=['artifact_id','artifact_type','source_system','approval_state','source_name','copied_path','sha256','reviewer_decision','reviewer_name','rationale'];const lines=[headers.map(csvCell).join(',')];for(const row of document.querySelectorAll('tbody tr')){{const item=records[Number(row.dataset.index)];const values={{...item}};for(const field of ['reviewer_decision','reviewer_name','rationale'])values[field]=row.querySelector('[data-field="'+field+'"]')?.value||'';lines.push(headers.map(key=>csvCell(values[key])).join(','))}}const blob=new Blob(['\\ufeff'+lines.join('\\r\\n')],{{type:'text/csv;charset=utf-8'}});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='DOSSIEROPS_REVIEW_WORKSHEET.csv';link.click();URL.revokeObjectURL(url);document.querySelector('#status').textContent='Review worksheet downloaded. Decisions remain on your device.'}});
</script></main></body></html>"""
    return page.encode("utf-8")


def run_controlled_dossier_assembly(
    case: dict[str, Any],
    *,
    profile: dict[str, Any],
    artifact_inputs: list[dict[str, Any]],
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    validate_profile(profile)
    if case.get("product") != profile["product_id"]:
        raise ValueError(
            f"Dossier assembly profile {profile['profile_id']} requires product={profile['product_id']}."
        )
    if not str(operator_id or "").strip():
        raise ValueError("Controlled dossier assembly requires an explicit operator_id.")
    if _gate(case, "intake_authority")["state"] != "allow":
        raise RuntimeError("Controlled dossier assembly requires approved intake authority.")
    if _gate(case, "generic_executor")["state"] != "refuse":
        raise RuntimeError("Generic executor boundary drifted before controlled dossier assembly.")
    if _gate(case, "external_release")["state"] == "allow":
        raise RuntimeError("Controlled dossier assembly cannot start with external release ALLOW.")
    if not artifact_inputs:
        raise ValueError("Controlled dossier assembly requires at least one artifact input.")

    before = {
        field: copy.deepcopy(case[field])
        for field in ("gates", "actions", "decisions", "outputs")
    }
    validate_case(case)

    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("Controlled dossier assembly output_dir must be empty.")
    items_dir = output_dir / "items"
    items_dir.mkdir(parents=True, exist_ok=True)

    ids: set[str] = set()
    items: list[dict[str, Any]] = []
    document_studio_receipts: list[dict[str, Any]] = []

    for item in artifact_inputs:
        artifact_id = _safe_artifact_id(item.get("artifact_id"))
        if artifact_id in ids:
            raise ValueError(f"Duplicate dossier artifact_id: {artifact_id}")
        ids.add(artifact_id)

        source_path = Path(str(item.get("path") or "")).expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Dossier artifact not found: {source_path}")
        if output_dir == source_path or output_dir in source_path.parents:
            raise ValueError("Dossier input artifacts cannot originate inside the assembly output directory.")

        source_sha = _sha_file(source_path)
        expected_sha = _digest(item.get("sha256"))
        if expected_sha and expected_sha != source_sha:
            raise ValueError(f"Dossier artifact hash mismatch: {artifact_id}")

        source_system = str(item.get("source_system") or "source_record").strip()
        artifact_type = str(item.get("artifact_type") or "record").strip()
        approval_state = str(item.get("approval_state") or "review_candidate").strip()

        document_studio_binding = None
        if source_system == "document_studio" and artifact_type == "document_studio_receipt":
            document_studio_binding = _validate_document_studio_receipt(
                source_path,
                expected_schema=str(profile["document_studio_receipt_schema"]),
            )
            document_studio_receipts.append(
                {
                    "artifact_id": artifact_id,
                    **document_studio_binding,
                }
            )

        suffix = "".join(source_path.suffixes) or ".bin"
        copied_name = f"{artifact_id}{suffix}"
        copied_path = items_dir / copied_name
        shutil.copyfile(source_path, copied_path)
        copied_sha = _sha_file(copied_path)
        if copied_sha != source_sha:
            raise RuntimeError(f"Dossier artifact copy hash drifted: {artifact_id}")

        items.append(
            {
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "source_system": source_system,
                "approval_state": approval_state,
                "source_name": source_path.name,
                "copied_path": str(copied_path.relative_to(output_dir)),
                "sha256": copied_sha,
                "document_studio_binding": document_studio_binding,
            }
        )

    items.sort(key=lambda row: row["artifact_id"])
    forbidden = {
        str(name): False for name in profile.get("forbidden_outcomes") or []
    }
    index = {
        "schema": "dio.dossier_assembly.index.v1",
        "profile_id": profile["profile_id"],
        "product_id": profile["product_id"],
        "case_id": case["case_id"],
        "items": items,
        "document_studio_binding": {
            "receipt_count": len(document_studio_receipts),
            "receipts": document_studio_receipts,
            "document_studio_execution_performed": False,
            "binding_kind": "validated_review_artifact_input",
        },
        "human_review": {
            "dossier_completeness": "NEEDS_YOU",
            "record_sufficiency": "NEEDS_YOU",
            "final_release": "NEEDS_YOU",
        },
        "forbidden_outcomes_created": forbidden,
        "authority_created": False,
        "external_effects": False,
        "external_release": "REFUSE",
    }

    prefix = str(profile.get("artifact_prefix") or profile["profile_id"]).upper().replace("-", "_")
    title = str(
        profile.get("review_pack_title")
        or f"{profile['profile_id']} Controlled Assembly Pack"
    )
    index_json_name = f"{prefix}_DOSSIER_INDEX.json"
    index_html_name = f"{prefix}_DOSSIER_INDEX.html"
    index_json = json.dumps(index, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
    index_html = _render_index_html(index, title=title)
    index_json_sha = _write(output_dir / index_json_name, index_json)
    index_html_sha = _write(output_dir / index_html_name, index_html)

    proof_artifacts = [
        {
            "artifact_type": "DOSSIER_ITEM",
            "filename": row["copied_path"],
            "sha256": row["sha256"],
        }
        for row in items
    ]
    proof_artifacts.extend(
        [
            {
                "artifact_type": "DOSSIER_INDEX_JSON",
                "filename": index_json_name,
                "sha256": index_json_sha,
            },
            {
                "artifact_type": "DOSSIER_INDEX_HTML",
                "filename": index_html_name,
                "sha256": index_html_sha,
            },
        ]
    )

    proof = {
        "schema": "dio.dossier_assembly.controlled_proof_manifest.v1",
        "processor_id": PROCESSOR_ID,
        "profile_id": profile["profile_id"],
        "product_id": profile["product_id"],
        "case_id": case["case_id"],
        "case_sha256": canonical_hash(case),
        "index_fingerprint": "sha256:" + _sha_bytes(_canonical(index)),
        "artifacts": proof_artifacts,
        "document_studio_binding": index["document_studio_binding"],
        "human_gate": {
            "state": "NEEDS_YOU",
            "reason": str(
                profile.get("human_gate_reason")
                or "Dossier review and release remain human-authority bound."
            ),
        },
        "forbidden_outcomes_created": forbidden,
        "authority_created": False,
        "execution_performed": False,
        "external_effects": False,
        "external_release": False,
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    proof_name = "PROOF_MANIFEST.json"
    proof_sha = _write(
        output_dir / proof_name,
        json.dumps(proof, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n",
    )

    # Give reviewers a portable integrity check after the ZIP leaves this
    # workspace. The manifest lists every other ZIP member by path, size, and
    # SHA-256; the outer processing receipt binds the manifest and full bundle.
    bundle_members = [
        {"path": row["copied_path"], "bytes": (output_dir / row["copied_path"]).stat().st_size,
         "sha256": row["sha256"], "artifact_type": "DOSSIER_ITEM"}
        for row in items
    ]
    bundle_members.extend([
        {"path": index_json_name, "bytes": len(index_json), "sha256": index_json_sha, "artifact_type": "DOSSIER_INDEX_JSON"},
        {"path": index_html_name, "bytes": len(index_html), "sha256": index_html_sha, "artifact_type": "DOSSIER_INDEX_HTML"},
        {"path": proof_name, "bytes": (output_dir / proof_name).stat().st_size, "sha256": proof_sha, "artifact_type": "PROOF_MANIFEST"},
    ])
    bundle_manifest = {
        "schema": "dio.dossier_assembly.bundle_manifest.v1",
        "profile_id": profile["profile_id"],
        "product_id": profile["product_id"],
        "case_id": case["case_id"],
        "index_fingerprint": proof["index_fingerprint"],
        "bound_proof_fingerprint": proof["proof_fingerprint"],
        "members": bundle_members,
        "member_count": len(bundle_members),
        "verification": "Recompute each listed member SHA-256 and byte count after extraction.",
        "processing_receipt_included": False,
    }
    manifest_name = "DOSSIER_BUNDLE_MANIFEST.json"
    manifest_bytes = json.dumps(bundle_manifest, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
    manifest_sha = _write(output_dir / manifest_name, manifest_bytes)

    bundle_name = f"{prefix}_CONTROLLED_DOSSIER.zip"
    bundle_path = output_dir / bundle_name
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for row in items:
            bundle.write(output_dir / row["copied_path"], row["copied_path"])
        bundle.write(output_dir / index_json_name, index_json_name)
        bundle.write(output_dir / index_html_name, index_html_name)
        bundle.write(output_dir / proof_name, proof_name)
        bundle.write(output_dir / manifest_name, manifest_name)
    bundle_sha = _sha_file(bundle_path)

    receipt = {
        "schema": "dio.dossier_assembly.controlled_processing_receipt.v1",
        "processor_id": PROCESSOR_ID,
        "profile_id": profile["profile_id"],
        "product_id": profile["product_id"],
        "case_id": case["case_id"],
        "operator_id": operator_id,
        "processed_at": now,
        "internal_processing": "COMPLETE",
        "assembly_performed": True,
        "product_execution_proved": False,
        "generic_executor_gate": _gate(case, "generic_executor")["state"],
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "document_studio_receipt_count": len(document_studio_receipts),
        "document_studio_execution_performed": False,
        "index_fingerprint": proof["index_fingerprint"],
        "proof_fingerprint": proof["proof_fingerprint"],
        "proof_manifest_sha256": proof_sha,
        "bundle_manifest": {"filename": manifest_name, "sha256": manifest_sha, "member_count": len(bundle_members)},
        "bundle": {
            "filename": bundle_name,
            "sha256": bundle_sha,
            "contains_processing_receipt": False,
        },
        "forbidden_outcomes_created": forbidden,
        "authority_created": False,
        "execution_performed": False,
        "external_effects": False,
        "external_release": False,
    }
    receipt_name = f"{prefix}_PROCESSING_RECEIPT.json"
    _write(
        output_dir / receipt_name,
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n",
    )

    for field in before:
        if case[field] != before[field]:
            raise RuntimeError(f"Controlled dossier assembly illegally mutated case {field}.")
    validate_case(case)

    return {
        "case": case,
        "dossier_index": index,
        "proof_manifest": proof,
        "receipt": receipt,
        "output_dir": str(output_dir),
        "bundle_path": str(bundle_path),
    }
