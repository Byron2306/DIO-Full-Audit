from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from adapters.document_studio.studio_sales import (
    render_finance_readiness_pack,
    render_publication_pack,
    render_studio_sales_asset,
)
from adapters.evidex_studio import (
    build_campaign_proof,
    build_editorial_proof,
    build_readiness_gap_map,
    build_studio_intake,
)
from presence_core.studio_release import prepare_studio_release
from products.commercial_truth_studio import evaluate_studio_truth
from products.studio_native_activation import activate_studio_case, verify_native_execution_proof
from scripts.nichefoundry_studio_adapter import position_site_studio

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_TOKEN = "DIO_STUDIO_NATIVE_CLOSURE_READY"


class StudioNativeClosureError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _pack_content(manifest: dict[str, Any]) -> tuple[str, str]:
    contract = manifest["artifact_contract"]
    kind = contract["kind"]
    if kind == "site":
        title = str(contract["brand"]["title"])
        body = "\n".join([
            str(contract["brand"]["headline"]),
            str(contract["brand"]["subhead"]),
            *[f"{row['title']}: {row['body']}" for row in contract["sections"]],
            "CONTROLLED REVIEW ASSET. Human publication authority remains required.",
        ])
        return title, body
    if kind == "correspondence":
        draft = contract["draft"]
        return str(draft["subject"]), "\n".join(str(row) for row in draft["body_lines"])
    if kind == "finance_readiness":
        venture = contract["venture"]
        body = "\n".join([
            str(contract["purpose"]),
            f"Funding need: {venture['funding_need']}",
            *[f"Published requirement {row['requirement_id']}: {row['label']}" for row in contract["published_requirements_fixture"]],
            *[f"Assumption: {row}" for row in contract["assumptions"]],
            str(contract["decision_boundary"]),
        ])
        return f"{venture['name']} Finance Readiness Pack", body
    if kind == "article":
        body = "\n".join([
            str(contract["standfirst"]),
            *[f"{row['heading']}: {row['body']}" for row in contract["sections"]],
            *[f"Reference: {row['citation']}" for row in contract["source_fixture"]],
            "DRAFT ONLY. Human editorial review and publication authority remain required.",
        ])
        return str(contract["headline"]), body
    raise StudioNativeClosureError(f"unsupported Studio closure kind: {kind}")


def _release_entrypoint(kind: str) -> str:
    if kind == "site":
        return "native_base/composition/marketfront/index.html"
    if kind == "correspondence":
        return "native_base/composition/correspondence/RESPONSE_BRIEF.html"
    if kind == "finance_readiness":
        return "native_base/composition/finance/READINESS_REPORT.html"
    if kind == "article":
        return "native_base/composition/publication/ARTICLE_DRAFT.html"
    raise StudioNativeClosureError(f"unsupported Presence release kind: {kind}")


def _base_execution(base: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in base["ledger"]["organs"]:
        caps = list(row.get("executed_capabilities") or [])
        if caps:
            result[row["engine_id"]] = {
                "capabilities": set(caps),
                "provider_refs": [str(row.get("provider_ref") or "")],
                "receipt_refs": [str(row.get("receipt_ref") or "")],
            }
    return result


def _add_execution(executed: dict[str, dict[str, Any]], engine_id: str, capabilities: list[str], provider_ref: str, receipt_ref: str) -> None:
    row = executed.setdefault(engine_id, {"capabilities": set(), "provider_refs": [], "receipt_refs": []})
    row["capabilities"].update(capabilities)
    if provider_ref and provider_ref not in row["provider_refs"]:
        row["provider_refs"].append(provider_ref)
    if receipt_ref and receipt_ref not in row["receipt_refs"]:
        row["receipt_refs"].append(receipt_ref)


def _ledger(manifest: dict[str, Any], executed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for organ in manifest["required_organs"]:
        engine_id = str(organ["engine_id"])
        required = list(organ.get("capabilities") or [])
        actual = executed.get(engine_id) or {"capabilities": set(), "provider_refs": [], "receipt_refs": []}
        capabilities = sorted(actual["capabilities"])
        unexpected = [cap for cap in capabilities if cap not in required]
        if unexpected:
            raise StudioNativeClosureError(f"{engine_id} closure claimed undeclared capabilities: {unexpected}")
        missing = [cap for cap in required if cap not in capabilities]
        state = "NATIVE_EXECUTED" if not missing else ("PARTIAL_NATIVE_EXECUTION" if capabilities else "SOURCE_BOUND_ONLY")
        rows.append({
            "engine_id": engine_id,
            "required_capabilities": required,
            "executed_capabilities": capabilities,
            "missing_capabilities": missing,
            "execution_state": state,
            "provider_refs": list(actual["provider_refs"]),
            "receipt_refs": list(actual["receipt_refs"]),
        })
    native = [row for row in rows if row["execution_state"] == "NATIVE_EXECUTED"]
    partial = [row for row in rows if row["execution_state"] == "PARTIAL_NATIVE_EXECUTION"]
    pending = [row for row in rows if row["execution_state"] == "SOURCE_BOUND_ONLY"]
    truth = "NATIVE_MULTI_ORGAN_EXECUTION_PROVED" if len(native) == len(rows) else "NATIVE_MULTI_ORGAN_EXECUTION_PROVED_WITH_AUXILIARY_GAPS"
    return {
        "schema": "dio.studio_native_capability_closure_ledger.v1",
        "studio_id": manifest["studio_id"],
        "organs": rows,
        "native_organ_count": len(native),
        "partial_organ_count": len(partial),
        "source_bound_only_count": len(pending),
        "organ_execution_truth": truth,
        "all_declared_capabilities_executed": len(native) == len(rows),
        "new_engine_created": False,
    }


def _normalize_pack_path(pack: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    result = dict(pack)
    result["output_path"] = str(Path(str(result["output_path"])).relative_to(output_dir))
    return result


def close_studio_case(*, manifest_path: Path, output_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    base = activate_studio_case(manifest_path=manifest_path, output_dir=output_dir / "native_base", root=root)
    verify_native_execution_proof(Path(base["output_dir"]), base["proof_manifest"])
    manifest = base["manifest"]
    closure = output_dir / "closure"
    closure.mkdir(parents=True, exist_ok=True)
    executed = _base_execution(base)
    kind = manifest["artifact_contract"]["kind"]

    release = prepare_studio_release(studio_id=manifest["studio_id"], entrypoint=_release_entrypoint(kind))
    _write_json(closure / "presence" / "PRESENCE_STUDIO_RELEASE.json", release)
    _add_execution(executed, "vesper", ["presence.release.prepare"], "presence_core/studio_release.py", "closure/presence/PRESENCE_STUDIO_RELEASE.json")

    commercial = evaluate_studio_truth(studio_id=manifest["studio_id"], root=root)
    _write_json(closure / "commercial_truth" / "COMMERCIAL_TRUTH_STUDIO.json", commercial)
    declared_commercial = next(row for row in manifest["required_organs"] if row["engine_id"] == "commercial_truth")["capabilities"]
    commercial_caps = [cap for cap in commercial["capabilities_executed"] if cap in declared_commercial]
    _add_execution(executed, "commercial_truth", commercial_caps, "products/commercial_truth_studio.py", "closure/commercial_truth/COMMERCIAL_TRUTH_STUDIO.json")

    intake = build_studio_intake(manifest)
    _write_json(closure / "evidex" / "EVIDEX_STUDIO_INTAKE.json", intake)
    _add_execution(executed, "evidex", ["evidence.intake.structure"], "adapters/evidex_studio.py", "closure/evidex/EVIDEX_STUDIO_INTAKE.json")

    title, body = _pack_content(manifest)
    audience = str(manifest["job"]["buyer"])

    if kind == "site":
        niche = position_site_studio(manifest)
        _write_json(closure / "nichefoundry" / "NICHEFOUNDRY_STUDIO_EXECUTION.json", niche)
        _add_execution(executed, "nichefoundry", list(niche["capabilities_executed"]), "scripts/nichefoundry_studio_adapter.py", "closure/nichefoundry/NICHEFOUNDRY_STUDIO_EXECUTION.json")

        sales_dir = closure / "document_studio" / "sales_asset"
        sales = render_studio_sales_asset(
            studio_id=manifest["studio_id"], title=title, body=body, audience=audience, out_dir=sales_dir, source_root=root
        )
        sales = _normalize_pack_path(sales, output_dir)
        _write_json(closure / "document_studio" / "DOCUMENT_STUDIO_SALES_RECEIPT.json", sales)
        _add_execution(executed, "document_studio", ["document.sales_assets"], "adapters/document_studio/studio_sales.py", "closure/document_studio/DOCUMENT_STUDIO_SALES_RECEIPT.json")

        campaign_proof = build_campaign_proof(manifest, base["composition"]["proof_manifest"], Path(base["composition"]["output_dir"]))
        _write_json(closure / "evidex" / "EVIDEX_CAMPAIGN_PROOF.json", campaign_proof)
        _add_execution(executed, "evidex", ["evidence.campaign.proof"], "adapters/evidex_studio.py", "closure/evidex/EVIDEX_CAMPAIGN_PROOF.json")

    elif kind == "finance_readiness":
        pack_dir = closure / "document_studio" / "finance_readiness_pack"
        pack = render_finance_readiness_pack(
            studio_id=manifest["studio_id"], title=title, body=body, audience=audience, out_dir=pack_dir, source_root=root
        )
        pack = _normalize_pack_path(pack, output_dir)
        _write_json(closure / "document_studio" / "DOCUMENT_STUDIO_FINANCE_PACK_RECEIPT.json", pack)
        _add_execution(executed, "document_studio", ["document.finance_readiness_pack"], "adapters/document_studio/studio_sales.py", "closure/document_studio/DOCUMENT_STUDIO_FINANCE_PACK_RECEIPT.json")

        gap_map = build_readiness_gap_map(manifest)
        _write_json(closure / "evidex" / "EVIDEX_READINESS_GAP_MAP.json", gap_map)
        _add_execution(executed, "evidex", ["evidence.readiness.gap_map"], "adapters/evidex_studio.py", "closure/evidex/EVIDEX_READINESS_GAP_MAP.json")

    elif kind == "article":
        pack_dir = closure / "document_studio" / "publication_pack"
        pack = render_publication_pack(
            studio_id=manifest["studio_id"], title=title, body=body, audience=audience, out_dir=pack_dir, source_root=root
        )
        pack = _normalize_pack_path(pack, output_dir)
        _write_json(closure / "document_studio" / "DOCUMENT_STUDIO_PUBLICATION_PACK_RECEIPT.json", pack)
        _add_execution(executed, "document_studio", ["document.publication_pack"], "adapters/document_studio/studio_sales.py", "closure/document_studio/DOCUMENT_STUDIO_PUBLICATION_PACK_RECEIPT.json")

        editorial_proof = build_editorial_proof(manifest, base["composition"]["proof_manifest"], Path(base["composition"]["output_dir"]))
        _write_json(closure / "evidex" / "EVIDEX_EDITORIAL_PROOF.json", editorial_proof)
        _add_execution(executed, "evidex", ["evidence.editorial.proof"], "adapters/evidex_studio.py", "closure/evidex/EVIDEX_EDITORIAL_PROOF.json")

    elif kind != "correspondence":
        raise StudioNativeClosureError(f"unsupported native closure kind: {kind}")

    ledger = _ledger(manifest, executed)
    _write_json(output_dir / "NATIVE_CAPABILITY_CLOSURE_LEDGER.json", ledger)
    if not ledger["all_declared_capabilities_executed"]:
        missing = {row["engine_id"]: row["missing_capabilities"] for row in ledger["organs"] if row["missing_capabilities"]}
        raise StudioNativeClosureError(f"Studio native closure incomplete: {missing}")

    artifacts = []
    for path in sorted(p for p in closure.rglob("*") if p.is_file()):
        artifacts.append({"path": str(path.relative_to(output_dir)), "sha256": _sha(path), "bytes": path.stat().st_size})
    ledger_path = output_dir / "NATIVE_CAPABILITY_CLOSURE_LEDGER.json"
    artifacts.append({"path": ledger_path.name, "sha256": _sha(ledger_path), "bytes": ledger_path.stat().st_size})
    proof = {
        "schema": "dio.studio_native_closure_proof_manifest.v1",
        "studio_id": manifest["studio_id"],
        "base_native_execution_fingerprint": base["receipt"]["native_execution_fingerprint"],
        "base_proof_fingerprint": base["proof_manifest"]["proof_fingerprint"],
        "artifacts": artifacts,
        "organ_execution_truth": ledger["organ_execution_truth"],
        "native_organ_count": ledger["native_organ_count"],
        "partial_organ_count": ledger["partial_organ_count"],
        "source_bound_only_count": ledger["source_bound_only_count"],
        "all_declared_capabilities_executed": True,
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "new_engine_created": False,
    }
    proof["proof_fingerprint"] = _fingerprint(proof)
    _write_json(output_dir / "NATIVE_CLOSURE_PROOF_MANIFEST.json", proof)
    receipt = {
        "schema": "dio.studio_native_closure_receipt.v1",
        "studio_id": manifest["studio_id"],
        "studio_name": manifest["name"],
        "native_capability_closure": "PASS",
        "organ_execution_truth": ledger["organ_execution_truth"],
        "native_organ_count": ledger["native_organ_count"],
        "partial_organ_count": 0,
        "source_bound_only_count": 0,
        "all_declared_capabilities_executed": True,
        "proof_fingerprint": proof["proof_fingerprint"],
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "payment": "REFUSE",
        "human_gate": "NEEDS_YOU",
        "authority_created": False,
        "external_effects": False,
        "new_engine_created": False,
    }
    receipt["native_closure_fingerprint"] = _fingerprint(receipt)
    _write_json(output_dir / "NATIVE_CLOSURE_RECEIPT.json", receipt)
    return {
        "manifest": manifest,
        "base": base,
        "ledger": ledger,
        "proof_manifest": proof,
        "receipt": receipt,
        "output_dir": str(output_dir),
    }


def verify_native_closure_proof(output_dir: Path, proof: dict[str, Any]) -> None:
    root = output_dir.resolve()
    for row in proof.get("artifacts") or []:
        path = (root / str(row["path"])).resolve()
        if not path.is_relative_to(root) or not path.is_file() or _sha(path) != row["sha256"]:
            raise StudioNativeClosureError(f"native closure artifact integrity failure: {row.get('path')}")
