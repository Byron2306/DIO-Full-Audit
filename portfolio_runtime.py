from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CROSSWALK = ROOT / "config" / "atlas" / "dio_meta_incarnation_crosswalk.csv"
STATE_PATH = ROOT / "state" / "product_portfolio" / "DIO_META_PORTFOLIO_ATLAS_IMPORT.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _lane(primary_family: str) -> dict[str, Any]:
    text = primary_family.casefold()
    if "evidex" in text:
        return {"lane": "EVIDEX", "job_api": "/api/control/product/action", "fresh_intake": "product_job_required"}
    if "homs" in text:
        return {"lane": "HOMS", "job_api": "/api/control/product/action", "fresh_intake": "product_job_required"}
    if "sophia" in text:
        return {"lane": "SOPHIA", "job_api": "/api/control/sophia/action", "fresh_intake": "sophia_job_required"}
    if "vamp" in text:
        return {"lane": "VAMP", "job_api": "/api/control/vamp/action", "fresh_intake": "vamp_job_required"}
    if "document studio" in text or "format core" in text:
        return {"lane": "DOCUMENT_STUDIO", "job_api": "/api/control/document-studio/action", "fresh_intake": "document_job_required"}
    if "nichefoundry" in text or "hivenance" in text:
        return {"lane": "MARKET_FACTORY", "job_api": "/api/control/creative-factory/action", "fresh_intake": "campaign_or_creative_brief_required"}
    return {"lane": "PACKAGE_GATE_ONLY", "job_api": None, "fresh_intake": "verified_output_required"}


def import_portfolio(*, force: bool = False) -> dict[str, Any]:
    if not CROSSWALK.is_file():
        raise FileNotFoundError(f"Canonical portfolio crosswalk not found: {CROSSWALK}")
    source_sha = _sha256(CROSSWALK)
    if STATE_PATH.is_file() and not force:
        try:
            current = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if current.get("source", {}).get("sha256") == source_sha:
                return current
        except (OSError, json.JSONDecodeError):
            pass

    rows: list[dict[str, Any]] = []
    with CROSSWALK.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            incarnation = str(raw.get("incarnation") or "").strip()
            if not incarnation:
                continue
            suite = str(raw.get("suite") or "").strip()
            family = str(raw.get("primary_family") or "").strip()
            maturity = str(raw.get("source_maturity") or "").strip()
            truth = str(raw.get("execution_truth_class") or "").strip()
            row = {key: (value or "") for key, value in raw.items()}
            row.update(
                {
                    "Incarnation": incarnation,
                    "Suite": suite,
                    "Product Family": family,
                    "Maturity": maturity,
                    "Readiness": maturity,
                    "execution_truth_class": truth,
                    "production_lane": _lane(family),
                    "portfolio_identity": "canonical_incarnation",
                    "candidate_product": False,
                    "authority_created": False,
                }
            )
            rows.append(row)

    payload = {
        "schema": "dio.meta_portfolio.atlas_import.v2",
        "generated_at": utc_now(),
        "source": {"path": str(CROSSWALK), "sha256": source_sha, "kind": "canonical_incarnation_crosswalk"},
        "canonical_incarnation_count": len(rows),
        "candidate_incarnations_imported": 0,
        "candidate_boundary": "ATLAS governed candidate incarnations are not imported into this executable portfolio registry.",
        "incarnations": rows,
        "authority_created": False,
    }
    _atomic_json(STATE_PATH, payload)
    return payload


def load_portfolio(*, auto_import: bool = True) -> dict[str, Any]:
    if auto_import:
        return import_portfolio(force=False)
    if not STATE_PATH.is_file():
        return {"schema": "dio.meta_portfolio.atlas_import.v2", "incarnations": [], "canonical_incarnation_count": 0}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))
