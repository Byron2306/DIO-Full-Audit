#!/usr/bin/env python3
"""Create an isolated current-profile canon materialization for strict ProductGrade.

The preserved October canon snapshot is never modified. This command creates a
new profile-derived identity surface, materialization receipt, and proof seal in
a fresh evidence root, all bound to the unchanged historical 53x3 anchor.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.canon_extension_native_profiles import NATIVE_CANON_EXTENSION_PROFILES
from products.canon_extension_product_grade import CANON_EXTENSIONS
from products.canon_extension_proof_seal import SEAL_FILENAME, SEAL_SCHEMA

ANCHOR_REL = Path("evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json")
MATERIALIZATION_FILENAME = "CANON_EXTENSION_MATERIALIZATION_RECEIPT.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _flatten(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            label = f"{prefix} / {key}" if prefix else str(key)
            rows.extend(_flatten(child, label))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_flatten(child, prefix))
    elif value is not None:
        rows.append((prefix or "Profile detail", str(value)))
    return rows


def _surface(profile: dict[str, Any], canon_id: str) -> str:
    baseline = profile["baseline"]
    detail_rows = _flatten({k: v for k, v in baseline.items() if k != "subject"})
    details = "\n".join(
        f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>"
        for label, value in detail_rows
    )
    limits = "\n".join(f"<li>{html.escape(str(item))}</li>" for item in profile["forbidden_claims"])
    boundary = {
        "publication_professional": "Draft preparation only; the responsible professional retains interpretation and release authority.",
        "readiness_assurance": "Evidence readiness only; no legal, regulatory, lending, or compliance decision is made.",
        "opportunity_venture": "Opportunity preparation only; eligibility, investor interest, awards, and commercial outcomes remain unverified.",
        "launch_orchestration": "Planning only; publication, media spend, performance, and channel authority remain held.",
    }[profile["family"]]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(profile['name'])} · controlled product profile</title>
<style>
:root{{color-scheme:light;--ink:#182b2a;--muted:#52655e;--line:#cbd4ce;--gold:#b57a20;--paper:#fff;--wash:#f5f4ef}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--wash);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}
main{{max-width:960px;margin:0 auto;padding:clamp(24px,5vw,64px) 24px}}
.kicker{{color:var(--gold);font-size:.78rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase}}
h1{{font-size:clamp(2rem,5vw,3.3rem);line-height:1.1;margin:.4rem 0 1rem}}
.panel{{background:var(--paper);border:1px solid var(--line);padding:clamp(18px,3vw,30px);margin:18px 0}}
.meta{{color:var(--muted)}}dl{{display:grid;grid-template-columns:minmax(150px, .36fr) 1fr;gap:8px 20px}}dt{{font-weight:700}}dd{{margin:0;overflow-wrap:anywhere}}
.boundary{{border-left:4px solid var(--gold);background:#fff7e8;padding:16px 18px}}
footer{{color:var(--muted);font-size:.85rem;margin-top:26px}}@media(max-width:600px){{dl{{grid-template-columns:1fr;gap:2px}}dd{{margin-bottom:12px}}}}
</style></head><body><main>
<p class="kicker">DIO · controlled product profile</p>
<h1>{html.escape(profile['name'])}</h1>
<p class="meta">Canon identity: {html.escape(canon_id)} · Profile family: {html.escape(profile['family'])}</p>
<section class="panel"><h2>Intended buyer</h2><p>{html.escape(profile['buyer'])}</p>
<h2>Controlled baseline example</h2><p><strong>{html.escape(str(baseline.get('subject') or profile['baseline_anchor']))}</strong></p>
<p>{html.escape(str(baseline.get('purpose') or baseline.get('objective') or baseline.get('proposition') or 'Controlled profile example for review.'))}</p>
<h2>Profile facts and boundaries</h2><dl>{details}</dl></section>
<section class="boundary"><h2>Review and release boundary</h2><p>{html.escape(boundary)} This profile uses synthetic controlled material and does not prove customer acceptance or professional qualification.</p>
<p>Do not claim:</p><ul>{limits}</ul></section>
<footer>Generated from the current native profile and bound to a historical lineage anchor. The anchor is not evidence that this extension was part of the historical 53-product corpus. Human review and external-release approval remain required.</footer>
</main></body></html>"""


def materialize(*, output_root: Path, anchor_source: Path) -> dict[str, Any]:
    output_root = output_root.resolve()
    anchor_source = anchor_source.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty evidence root: {output_root}")
    if not anchor_source.is_file():
        raise FileNotFoundError(anchor_source)
    anchor_data = json.loads(anchor_source.read_text(encoding="utf-8"))
    if (anchor_data.get("schema") != "dio.historical_evidence_anchor.v1"
            or anchor_data.get("acceptance_token") != "DIO_PROFESSIONAL_EVIDENCE_53_X3_VERIFIED"
            or anchor_data.get("authority_created") is not False
            or anchor_data.get("external_effects") is not False):
        raise ValueError("historical 53x3 anchor failed identity or authority checks")
    anchor = output_root / ANCHOR_REL
    anchor.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(anchor_source, anchor)
    anchor_sha = _sha(anchor)
    profiles = {str(row["slug"]): row for row in NATIVE_CANON_EXTENSION_PROFILES}
    specs = {str(row["slug"]): row for row in CANON_EXTENSIONS if row["proof_kind"] == "receipt_bound"}
    if set(profiles) != set(specs) or len(profiles) != 11:
        raise ValueError("current native profile registry and receipt-bound canon registry differ")
    materialized: dict[str, Any] = {}
    for slug, profile in profiles.items():
        spec = specs[slug]
        artifact = output_root / str(spec["primary_artifact"])
        site = artifact.parent
        site.mkdir(parents=True, exist_ok=True)
        artifact.write_text(_surface(profile, str(spec["canon_id"])), encoding="utf-8")
        generation_path = site / MATERIALIZATION_FILENAME
        generation = {
            "schema": "dio.canon_extension.materialization_receipt.v1",
            "status": "PASS",
            "canon_id": str(spec["canon_id"]),
            "name": str(spec["name"]),
            "slug": slug,
            "primary_artifact": str(artifact.relative_to(output_root)),
            "primary_artifact_sha256": _sha(artifact),
            "profile_fingerprint": _fingerprint(profile),
            "historical_anchor": ANCHOR_REL.as_posix(),
            "historical_anchor_sha256": anchor_sha,
            "lineage_note": "The historical 53x3 anchor is a lineage root only; it does not evidence this extension in that corpus.",
            "authority_created": False,
            "external_effects": False,
            "commercial_validation": "UNPROVED",
            "claim_boundary": "Current-profile identity materialization and lineage only; not independent ProductGrade, buyer acceptance, or professional approval.",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        generation_path.write_text(json.dumps(generation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        gamma_path = site / Path(str(spec["proof_receipt"])).name
        gamma = {
            "schema": "dio.canon_extension.current_profile_generation.v1",
            "status": "PASS",
            "canon_id": str(spec["canon_id"]),
            "name": str(spec["name"]),
            "slug": slug,
            "primary_artifact": str(artifact.relative_to(output_root)),
            "primary_artifact_sha256": _sha(artifact),
            "source_generation_receipt": str(generation_path.relative_to(output_root)),
            "source_generation_receipt_sha256": _sha(generation_path),
            "source_generation_receipt_schema": generation["schema"],
            "authority_created": False,
            "external_effects": False,
            "commercial_validation": "UNPROVED",
            "claim_boundary": "Current-profile Gamma receipt binds the canon artifact and chains to its strict materialization receipt.",
        }
        gamma_path.write_text(json.dumps(gamma, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        seal_path = site / SEAL_FILENAME
        seal = {
            "schema": SEAL_SCHEMA,
            "status": "PASS",
            "canon_id": str(spec["canon_id"]),
            "name": str(spec["name"]),
            "slug": slug,
            "primary_artifact": str(artifact.relative_to(output_root)),
            "current_artifact_sha256": _sha(artifact),
            "source_generation_receipt": str(gamma_path.relative_to(output_root)),
            "source_generation_receipt_sha256": _sha(gamma_path),
            "source_generation_receipt_schema": gamma["schema"],
            "strict_materialization_binding": True,
            "source_receipt_artifact_bound": True,
            "authority_created": False,
            "external_effects": False,
            "commercial_validation": "UNPROVED",
            "claim_boundary": "Proof seal binds the isolated current-profile artifact and materialization receipt; it grants no publication or professional authority.",
        }
        seal["receipt_fingerprint"] = _fingerprint(seal)
        seal_path.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        materialized[slug] = {
            "name": str(spec["name"]),
            "profile_fingerprint": generation["profile_fingerprint"],
            "artifact_sha256": generation["primary_artifact_sha256"],
            "materialization_receipt_sha256": _sha(generation_path),
            "gamma_receipt_sha256": _sha(gamma_path),
            "proof_seal_sha256": _sha(seal_path),
        }
    batch = {
        "schema": "dio.canon_extension.current_profile_materialization_batch.v1",
        "status": "PASS" if len(materialized) == 11 else "REFUSE",
        "target_count": 11,
        "materialized_count": len(materialized),
        "historical_anchor": str(ANCHOR_REL),
        "historical_anchor_sha256": anchor_sha,
        "isolated_root": str(output_root),
        "products": materialized,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
        "claim_boundary": "Generated isolated profile identity surfaces, not customer-accepted products. Historical source remains unchanged.",
    }
    batch["batch_fingerprint"] = _fingerprint(batch)
    (output_root / "CURRENT_PROFILE_MATERIALIZATION_BATCH_RECEIPT.json").write_text(
        json.dumps(batch, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return batch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--anchor-source", type=Path,
        default=ROOT / "acceptance_runs/68-product-integration-20261027/extensions-preserved-canon/isolated-root/evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json",
    )
    args = parser.parse_args()
    batch = materialize(output_root=args.output_root, anchor_source=args.anchor_source)
    print(json.dumps(batch, indent=2, sort_keys=True))
    return 0 if batch["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
