from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path
from typing import Any

from products.canon_extension_native_profiles import native_profile
from products.canon_extension_product_grade import CANON_EXTENSIONS


MATERIALIZATION_SCHEMA = "dio.canon_extension.materialization_receipt.v1"
MATERIALIZATION_BATCH_SCHEMA = "dio.canon_extension.materialization_batch.v1"
MATERIALIZATION_FILENAME = "CANON_EXTENSION_MATERIALIZATION_RECEIPT.json"
MATERIALIZATION_BATCH_FILENAME = "CANON_EXTENSION_MATERIALIZATION_BATCH_RECEIPT.json"
MATERIALIZED_TOKEN = "DIO_CANON_EXTENSION_11_MATERIALIZED"
MATERIALIZATION_REFUSE_TOKEN = "DIO_CANON_EXTENSION_MATERIALIZATION_REFUSE"
HISTORICAL_ANCHOR = Path("evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json")


class CanonExtensionMaterializationError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _render_value(label: str, value: Any) -> str:
    if value is None or value == "" or value == []:
        return ""
    heading = f"<h2>{escape(label)}</h2>"
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = "; ".join(f"{key.replace('_', ' ').title()}: {child}" for key, child in item.items())
            else:
                text = str(item)
            items.append(f"<li>{escape(text)}</li>")
        return heading + "\n<ul>" + "".join(items) + "</ul>"
    return heading + f"\n<p>{escape(str(value))}</p>"


def render_canon_extension_html(*, spec: dict[str, Any], profile: dict[str, Any]) -> str:
    fixture = dict(profile["fixtures"]["normal"])
    subject = str(fixture.pop("subject", spec["name"]))
    purpose = fixture.pop("purpose", None)

    sections = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        f"  <title>{escape(str(spec['name']))}</title>",
        "  <style>",
        "    body { font-family: Arial, sans-serif; max-width: 920px; margin: 0 auto; padding: 40px 24px; line-height: 1.55; }",
        "    .meta { color: #555; margin-bottom: 1.5rem; }",
        "    h1 { font-size: 2rem; margin-bottom: .35rem; }",
        "    h2 { font-size: 1.12rem; margin-top: 1.6rem; }",
        "    li { margin: .35rem 0; }",
        "    .boundary { border-top: 1px solid #bbb; margin-top: 2rem; padding-top: 1rem; font-weight: 600; }",
        "  </style>",
        "</head>",
        "<body>",
        f"<h1>{escape(str(spec['name']))}</h1>",
        f'<p class="meta">Canon extension · {escape(str(profile["family"]))} / {escape(str(profile["mode"]))} · Buyer: {escape(str(profile["buyer"]))}</p>',
        f"<h2>Reference buyer job</h2>\n<p>{escape(subject)}</p>",
    ]
    if purpose:
        sections.append(_render_value("Purpose", purpose))

    for key, value in fixture.items():
        sections.append(_render_value(key.replace("_", " ").title(), value))

    sections.extend(
        [
            '<p class="boundary">Human authority remains required. This canonical engineering materialization creates no external effect, decision, certification, approval, commitment, publication, spend, payment, legal conclusion, funding decision, investment commitment, or commercial validation.</p>',
            "</body>",
            "</html>",
            "",
        ]
    )
    return "\n".join(part for part in sections if part)


def materialize_receipt_bound_extension(*, spec: dict[str, Any], root: Path) -> dict[str, Any]:
    if spec.get("proof_kind") != "receipt_bound":
        raise CanonExtensionMaterializationError(f"not a receipt-bound canon extension: {spec.get('slug')}")

    root = Path(root).resolve()
    anchor = (root / HISTORICAL_ANCHOR).resolve()
    artifact = (root / str(spec["primary_artifact"])).resolve()
    if not anchor.is_relative_to(root) or not artifact.is_relative_to(root):
        raise CanonExtensionMaterializationError("unsafe canon-extension materialization path")
    if not anchor.is_file():
        raise CanonExtensionMaterializationError(f"historical anchor missing: {anchor}")

    profile = native_profile(str(spec["slug"]))
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(render_canon_extension_html(spec=spec, profile=profile), encoding="utf-8")

    receipt: dict[str, Any] = {
        "schema": MATERIALIZATION_SCHEMA,
        "status": "PASS",
        "canon_id": str(spec["canon_id"]),
        "name": str(spec["name"]),
        "slug": str(spec["slug"]),
        "primary_artifact": str(artifact.relative_to(root)),
        "primary_artifact_sha256": _sha(artifact),
        "profile_fingerprint": _fingerprint(profile),
        "historical_anchor": str(HISTORICAL_ANCHOR),
        "historical_anchor_sha256": _sha(anchor),
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
        "claim_boundary": (
            "This receipt proves deterministic canon-extension materialization from the current extension spec and "
            "native profile while binding lineage to the immutable historical 53x3 evidence anchor. The historical "
            "anchor is a lineage root, not evidence that this extension existed in the historical 53-product corpus. "
            "No buyer demand, payment, legal approval, publication authority, investment interest, funding approval, "
            "market performance, or commercial validation is created."
        ),
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    _write_json(artifact.parent / MATERIALIZATION_FILENAME, receipt)
    return receipt


def materialize_receipt_bound_extensions(*, root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    targets = [row for row in CANON_EXTENSIONS if row.get("proof_kind") == "receipt_bound"]
    materializations: dict[str, Any] = {}
    failures: dict[str, str] = {}

    for spec in targets:
        slug = str(spec["slug"])
        try:
            materializations[slug] = materialize_receipt_bound_extension(spec=spec, root=root)
        except (CanonExtensionMaterializationError, OSError, KeyError, TypeError, ValueError) as exc:
            failures[slug] = f"{type(exc).__name__}: {exc}"

    passed = len(targets) == 11 and len(materializations) == 11 and not failures
    batch: dict[str, Any] = {
        "schema": MATERIALIZATION_BATCH_SCHEMA,
        "acceptance_token": MATERIALIZED_TOKEN if passed else MATERIALIZATION_REFUSE_TOKEN,
        "target_count": len(targets),
        "materialized_count": len(materializations),
        "refuse_count": len(failures),
        "materializations": materializations,
        "failures": failures,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
    }
    batch["receipt_fingerprint"] = _fingerprint(batch)
    batch_path = root / "state/product_portfolio/canon_extensions" / MATERIALIZATION_BATCH_FILENAME
    _write_json(batch_path, batch)
    return batch
