from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any
import zipfile

from adapters.format_core.renderer import build_paragraph_semantic_content, render_semantic_asset


class EvidexStudioFinishError(RuntimeError):
    """Raised when an Evidex pack cannot be finished without weakening its review boundary."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_held_review(pack_dir: Path) -> dict[str, Any]:
    review_path = pack_dir / "SOURCE_REVIEW.json"
    try:
        review = json.loads(review_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        raise EvidexStudioFinishError(f"invalid Evidex source review: {exc}") from exc
    if not isinstance(review, dict):
        raise EvidexStudioFinishError("Evidex source review must be a JSON object")
    claims = review.get("claims")

    def valid_claim(claim: Any) -> bool:
        if not isinstance(claim, dict):
            return False
        required = {"kpi_name", "declared_target", "declared_actual", "epistemic_state", "source_bindings"}
        if not required.issubset(claim):
            return False
        if not str(claim["kpi_name"]).strip() or not str(claim["epistemic_state"]).strip():
            return False
        bindings = claim["source_bindings"]
        return isinstance(bindings, list) and all(isinstance(binding, dict) for binding in bindings)

    if (
        review.get("schema") != "dio.evidex.source_review.v1"
        or review.get("release_authorized") is not False
        or review.get("human_review_required") is not True
        or not isinstance(claims, list)
        or not claims
        or any(not valid_claim(claim) for claim in claims)
    ):
        raise EvidexStudioFinishError("Evidex source review is not a held, claim-bearing review record")
    return review


def build_evidex_semantic_content(
    *, pack_dir: Path, intake: dict[str, Any]
) -> dict[str, Any]:
    pack_dir = Path(pack_dir).resolve()
    review = _read_held_review(pack_dir)
    pack = intake.get("pack") if isinstance(intake, dict) else None
    client = intake.get("client") if isinstance(intake, dict) else None
    pack = pack if isinstance(pack, dict) else {}
    client = client if isinstance(client, dict) else {}
    title = str(pack.get("project_name") or pack_dir.name).strip()
    organisation = str(client.get("organization") or "Client organisation to confirm").strip()
    purpose = str(pack.get("purpose") or "Evidence pack review").strip()
    period = pack.get("reporting_period") if isinstance(pack.get("reporting_period"), dict) else {}
    period_text = f"{period.get('start') or 'start to confirm'} to {period.get('end') or 'end to confirm'}"
    rows = [
        {"paragraph_id": "P1", "text": f"{title} — Evidence Pack Review"},
        {"paragraph_id": "P2", "text": "HUMAN REVIEW REQUIRED"},
        {"paragraph_id": "P3", "text": f"Client: {organisation}"},
        {"paragraph_id": "P4", "text": f"Purpose: {purpose}"},
        {"paragraph_id": "P5", "text": f"Reporting period: {period_text}"},
        {
            "paragraph_id": "P6",
            "text": "Release is not authorized. Review every claim against its bound source before delivery.",
        },
    ]
    for index, claim in enumerate(review["claims"], 1):
        kpi_name = str(claim["kpi_name"]).strip()
        target = str(claim["declared_target"]).strip()
        actual = str(claim["declared_actual"]).strip()
        state = str(claim.get("epistemic_state") or "UNVERIFIED").strip().upper()
        rows.append(
            {
                "paragraph_id": f"C{index}",
                "text": (
                    f"KPI {kpi_name} — {state} — "
                    f"Declared target: {target} — Declared actual: {actual}"
                ),
            }
        )
    customer_review = intake.get("_customer_evidence_review")
    if customer_review:
        if customer_review.get("schema") != "dio.evidex.customer_record_review.v1" or customer_review.get("support_adjudicated") is not False or customer_review.get("release_authorized") is not False:
            raise EvidexStudioFinishError("customer record review cannot grant evidence or release authority")
        extra = ["Customer claims and documentary leads", customer_review["scope"]]
        for record in customer_review["source_records"]:
            if record["record_id"] in customer_review["quarantined_record_ids"]:
                extra.append(f"Source {record['record_id']}: embedded instruction captured and quarantined; excluded from claim analysis.")
            else:
                extra.append(f"Source {record['record_id']} ({record['source_filename']}, SHA-256 {record['sha256']}): {record['text']}")
        for comparison in customer_review["quantity_comparisons"]:
            extra.append(f"Claim {comparison['claim_id']}: declared {comparison['declared_value']}; record {comparison['candidate_record_id']} reports {comparison['reported_record_value']}; arithmetic difference {comparison['difference']}. {comparison['state']}. {comparison['comparability']}")
        extra.append("Questions and records to obtain")
        extra.extend(f"{action['record_id']}: {action['question']}" for action in customer_review["review_actions"])
        rows.extend({"paragraph_id": f"R{i:04d}", "text": text} for i, text in enumerate(extra, 1))
    return build_paragraph_semantic_content(
        object_id=f"EVIDEX-{pack_dir.name}",
        version="1.0.0",
        title=f"{title} — Evidence Pack Review",
        source_language="English",
        source_rows=rows,
        context={
            "product": "evidex",
            "artifact_type": "evidence_pack_customer_review",
            "audience": organisation,
            "purpose": purpose,
        },
    )


def finish_evidex_pack(
    *, pack_dir: Path, intake: dict[str, Any], source_root: Path
) -> dict[str, Any]:
    pack_dir = Path(pack_dir).resolve()
    if not pack_dir.is_dir():
        raise EvidexStudioFinishError(f"Evidex pack directory does not exist: {pack_dir}")
    review = _read_held_review(pack_dir)
    if intake.get("_customer_evidence_review"):
        (pack_dir / "CUSTOMER_EVIDENCE_REVIEW.json").write_text(
            json.dumps(intake["_customer_evidence_review"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    finish_dir = pack_dir / "05_STUDIO_FINISH"
    render_dir = finish_dir / "FORMAT_CORE"
    semantic = build_evidex_semantic_content(pack_dir=pack_dir, intake=intake)
    try:
        format_receipt = render_semantic_asset(
            semantic,
            render_dir,
            style_profile="dio_professional",
            delivery_profile="editable_review",
            language="English",
            channels=["docx", "html"],
            release_mode=False,
            source_root=Path(source_root),
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise EvidexStudioFinishError(f"Format Core failed to finish Evidex pack: {exc}") from exc
    qa = format_receipt.get("qa") or {}
    if format_receipt.get("status") != "rendered_review_candidate" or qa.get("passed") is not True:
        raise EvidexStudioFinishError("Format Core did not produce a QA-passed review candidate")
    outputs: list[dict[str, Any]] = []
    for row in format_receipt.get("outputs") or []:
        output = render_dir / str(row["path"])
        if not output.is_file():
            raise EvidexStudioFinishError(f"Format Core output is missing: {output}")
        outputs.append(
            {
                "channel": str(row["channel"]),
                "path": str(output.relative_to(finish_dir)),
                "sha256": _sha256(output),
                "bytes": output.stat().st_size,
            }
        )
    format_receipt_path = render_dir / "FORMAT_CORE_RECEIPT.json"
    if not format_receipt_path.is_file():
        raise EvidexStudioFinishError("Format Core receipt is missing")
    outputs.append(
        {
            "channel": "receipt",
            "path": str(format_receipt_path.relative_to(finish_dir)),
            "sha256": _sha256(format_receipt_path),
            "bytes": format_receipt_path.stat().st_size,
        }
    )
    receipt = {
        "schema": "dio.evidex_studio_finish.v1",
        "pack": pack_dir.name,
        "source_review_sha256": _sha256(pack_dir / "SOURCE_REVIEW.json"),
        "review_boundary": {
            "human_review_required": review["human_review_required"],
            "release_authorized": review["release_authorized"],
        },
        "format_core": {
            "schema": format_receipt.get("schema"),
            "status": format_receipt.get("status"),
            "style_profile": format_receipt.get("style_profile"),
            "style_profile_hash": format_receipt.get("style_profile_hash"),
            "delivery_profile": format_receipt.get("delivery_profile"),
            "delivery_profile_hash": format_receipt.get("delivery_profile_hash"),
            "semantic_source_hash": format_receipt.get("semantic_source_hash"),
            "qa_passed": True,
            "release_mode": False,
            "outputs": outputs,
        },
        "production_studio": {
            "state": "CUSTOMER_REVIEW_PACKAGE_PREPARED",
            "customer_artifact_separated_from_proof": True,
        },
        "nichefoundry": {
            "state": "AVAILABLE_ON_APPROVED_BRAND_REQUEST",
            "executed": False,
        },
        "external_delivery": "REFUSE",
        "publication": "REFUSE",
        "spend": "REFUSE",
        "authority_created": False,
    }
    receipt_path = finish_dir / "EVIDEX_STUDIO_FINISH_RECEIPT.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(receipt_path)
    return receipt


def _regular_pack_files(pack_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(pack_dir.rglob("*")):
        if path.is_symlink():
            raise EvidexStudioFinishError(f"Evidex pack contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise EvidexStudioFinishError(f"Evidex pack contains a non-regular entry: {path}")
        relative = path.relative_to(pack_dir)
        if relative.is_absolute() or ".." in relative.parts:
            raise EvidexStudioFinishError(f"Evidex pack contains an unsafe path: {path}")
        files.append(path)
    return files


def finish_evidex_archive(
    *, archive_path: Path, intake: dict[str, Any], source_root: Path, pack_dir: Path | None = None
) -> dict[str, Any]:
    archive_path = Path(archive_path).resolve()
    if not archive_path.is_file():
        raise EvidexStudioFinishError(f"Evidex archive does not exist: {archive_path}")
    pack_dir = Path(pack_dir).resolve() if pack_dir is not None else archive_path.with_suffix("")
    if not pack_dir.is_dir():
        raise EvidexStudioFinishError(f"Evidex pack directory does not exist beside archive: {pack_dir}")
    _regular_pack_files(pack_dir)
    finish_receipt = finish_evidex_pack(pack_dir=pack_dir, intake=intake, source_root=source_root)
    files = _regular_pack_files(pack_dir)
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{archive_path.stem}-studio-finish-",
        suffix=".zip",
        dir=archive_path.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    handle.close()
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in files:
                bundle.write(path, path.relative_to(pack_dir).as_posix())
        temporary.replace(archive_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return {
        "status": "finished_review_candidate",
        "archive_path": str(archive_path),
        "archive_sha256": _sha256(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "receipt_path": str(pack_dir / "05_STUDIO_FINISH/EVIDEX_STUDIO_FINISH_RECEIPT.json"),
        "review_boundary": finish_receipt["review_boundary"],
        "format_core": finish_receipt["format_core"],
        "production_studio": finish_receipt["production_studio"],
        "nichefoundry": finish_receipt["nichefoundry"],
        "external_delivery": finish_receipt["external_delivery"],
        "publication": finish_receipt["publication"],
        "spend": finish_receipt["spend"],
        "authority_created": finish_receipt["authority_created"],
    }
