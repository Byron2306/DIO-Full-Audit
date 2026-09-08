from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path
from typing import Any

from products.canon_extension_native_profiles import native_profile
from products.canon_extension_product_grade import CANON_EXTENSIONS


MATERIALIZATION_SCHEMA = "dio.canon_extension.materialization_receipt.v1"
MATERIALIZATION_FILENAME = "CANON_EXTENSION_MATERIALIZATION_RECEIPT.json"
MATERIALIZED_TOKEN = "DIO_CANON_EXTENSION_11_MATERIALIZED"
REFUSE_TOKEN = "DIO_CANON_EXTENSION_MATERIALIZATION_REFUSE"
ANCHOR_REL = Path("evidence/historical/PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json")


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
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _label(value: str) -> str:
    return str(value).replace("_", " ").strip().title()


def _render_value(value: Any) -> list[str]:
    if isinstance(value, list):
        rows: list[str] = []
        for item in value:
            if isinstance(item, dict):
                parts = [f"{_label(str(key))}: {item[key]}" for key in item]
                rows.append("; ".join(parts))
            else:
                rows.append(str(item))
        return rows
    if isinstance(value, dict):
        return [f"{_label(str(key))}: {value[key]}" for key in value]
    return [str(value)]


def render_canon_html(*, spec: dict[str, Any], profile: dict[str, Any]) -> str:
    normal = dict(profile.get("fixtures", {}).get("normal") or {})
    if not normal:
        raise CanonExtensionMaterializationError(f"normal fixture missing for {spec['slug']}")

    sections: list[str] = [
        f"<h1>{escape(str(spec['name']))}</h1>",
        '<p class="eyebrow">DIO governed canon extension</p>',
        f"<p><strong>Buyer:</strong> {escape(str(profile['buyer']))}</p>",
        f"<p><strong>Family:</strong> {escape(str(profile['family']))}</p>",
        f"<p><strong>Mode:</strong> {escape(str(profile['mode']))}</p>",
    ]

    for key, value in normal.items():
        sections.append(f"<h2>{escape(_label(str(key)))}</h2>")
        for row in _render_value(value):
            sections.append(f"<p>{escape(row)}</p>")

    sections.extend(
        [
            "<h2>Authority boundary</h2>",
            (
                "<p>This canonical surface is a deterministic product-definition artifact. "
                "Human decision and release authority remain required. It creates no external effect, "
                "approval, certification, payment, commitment, or commercial validation.</p>"
            ),
        ]
    )

    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 880px; margin: 0 auto; padding: 40px 24px; line-height: 1.55; }}
    .eyebrow {{ text-transform: uppercase; letter-spacing: .08em; font-size: .78rem; font-weight: 700; }}
    h1 {{ font-size: 2rem; margin-bottom: .35rem; }}
    h2 {{ font-size: 1.1rem; margin-top: 1.7rem; }}
    p {{ margin: .6rem 0; }}
  </style>
</head>
<body>
{body}
</body>
</html>
""".format(title=escape(str(spec["name"])), body="\n".join(sections))


def materialize_receipt_bound_extension(*, spec: dict[str, Any], root: Path) -> dict[str, Any]:
    if spec.get("proof_kind") != "receipt_bound":
        raise CanonExtensionMaterializationError(f"{spec.get('slug')} is not receipt_bound")

    root = Path(root).resolve()
    anchor = (root / ANCHOR_REL).resolve()
    artifact = (root / str(spec["primary_artifact"])).resolve()

    if not anchor.is_relative_to(root) or not artifact.is_relative_to(root):
        raise CanonExtensionMaterializationError("unsafe canon-extension materialization path")
    if not anchor.is_file():
        raise CanonExtensionMaterializationError(f"historical anchor missing: {anchor}")

    profile = native_profile(str(spec["slug"]))
    html = render_canon_html(spec=spec, profile=profile)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(html, encoding="utf-8")

    receipt: dict[str, Any] = {
        "schema": MATERIALIZATION_SCHEMA,
        "status": "PASS",
        "canon_id": str(spec["canon_id"]),
        "name": str(spec["name"]),
        "slug": str(spec["slug"]),
        "primary_artifact": str(artifact.relative_to(root)),
        "primary_artifact_sha256": _sha(artifact),
        "profile_fingerprint": _fingerprint(profile),
        "historical_anchor": ANCHOR_REL.as_posix(),
        "historical_anchor_sha256": _sha(anchor),
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
        "claim_boundary": (
            "This receipt proves deterministic materialization of the current canon-extension surface from its "
            "configured native profile while binding lineage to the immutable historical 53x3 anchor. It does not "
            "claim that the extension existed in the historical 53-product corpus and does not create ProductGrade, "
            "buyer demand, payment, legal approval, publication authority, investment interest, funding approval, "
            "market performance, or commercial validation."
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
        except (CanonExtensionMaterializationError, OSError, ValueError, KeyError) as exc:
            failures[slug] = f"{type(exc).__name__}: {exc}"

    all_materialized = len(targets) == 11 and len(materializations) == 11 and not failures
    return {
        "schema": "dio.canon_extension.materialization_batch.v1",
        "acceptance_token": MATERIALIZED_TOKEN if all_materialized else REFUSE_TOKEN,
        "target_count": len(targets),
        "materialized_count": len(materializations),
        "refuse_count": len(failures),
        "materializations": materializations,
        "failures": failures,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
    }
