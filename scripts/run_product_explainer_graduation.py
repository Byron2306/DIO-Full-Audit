from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.product_explainer_compiler import ProductExplainerError
from products.product_explainer_pipeline import (
    build_explainer_script_package,
    build_media_production_request,
    compile_product_explainer,
    semantic_challenge,
)
from products.premium_media_federation import build_premium_media

READY_TOKEN = "DIO_PRODUCT_EXPLAINER_GRADUATION_READY"
REFUSED_TOKEN = "DIO_PRODUCT_EXPLAINER_GRADUATION_REFUSED"
CUSTODY_FILENAMES = (
    "PRODUCT_EXPLAINER_MANIFEST.json",
    "CLAIM_ENVELOPE.json",
    "EXPLAINER_SCRIPT_PACKAGE.json",
    "SEMANTIC_CHALLENGE.json",
    "MEDIA_PRODUCTION_REQUEST.json",
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _receipt(*, product_id: str, semantic_graduation: str, missing: list[str], render_state: str,
             custody_artifacts: list[str] | None = None, render_receipt: dict[str, Any] | None = None,
             error: dict[str, Any] | None = None) -> dict[str, Any]:
    passed = semantic_graduation == "PASS"
    return {
        "schema": "dio.product_explainer.graduation_receipt.v1",
        "product_id": product_id,
        "semantic_graduation": semantic_graduation,
        "missing": list(missing),
        "custody_artifacts": list(custody_artifacts or []),
        "render_state": render_state,
        "render_receipt": render_receipt,
        "error": error,
        "external_publication": "NEEDS_YOU",
        "media_spend": "REFUSE",
        "human_gate": "NEEDS_YOU",
        "acceptance_token": READY_TOKEN if passed else REFUSED_TOKEN,
    }


def run_graduation(*, product_id: str = "homs", root: Path = ROOT, output_dir: Path | None = None,
                   render: bool = False, nichefoundry_root: Path | None = None, provider: str = "auto") -> dict[str, Any]:
    root = Path(root)
    destination = Path(output_dir) if output_dir is not None else root / "state" / "product_explainer_graduation" / product_id.upper()
    destination.mkdir(parents=True, exist_ok=True)

    try:
        compiled = compile_product_explainer(product_id, root=root, output_dir=destination)
    except ProductExplainerError as exc:
        receipt = _receipt(
            product_id=product_id.upper(),
            semantic_graduation="REFUSE",
            missing=[exc.code],
            render_state="REFUSE" if render else "NOT_REQUESTED",
            error={"code": exc.code, "message": str(exc), "details": exc.details},
        )
        _write_json(destination / "GRADUATION_RECEIPT.json", receipt)
        return receipt
    if compiled.get("semantic_readiness") != "READY" or not compiled.get("manifest"):
        receipt = _receipt(
            product_id=product_id.upper(),
            semantic_graduation="REFUSE",
            missing=list(compiled.get("missing") or []),
            render_state="REFUSE" if render else "NOT_REQUESTED",
        )
        _write_json(destination / "GRADUATION_RECEIPT.json", receipt)
        return receipt

    manifest = compiled["manifest"]
    _write_json(destination / "PRODUCT_EXPLAINER_MANIFEST.json", manifest)
    _write_json(destination / "CLAIM_ENVELOPE.json", compiled.get("claim_envelope") or {})

    script_package = build_explainer_script_package(manifest)
    _write_json(destination / "EXPLAINER_SCRIPT_PACKAGE.json", script_package)

    challenge = semantic_challenge(manifest, script_package)
    _write_json(destination / "SEMANTIC_CHALLENGE.json", challenge)
    if challenge.get("state") != "PASS":
        receipt = _receipt(
            product_id=str(manifest.get("product_id") or product_id).upper(),
            semantic_graduation="REFUSE",
            missing=list(challenge.get("codes") or []),
            render_state="REFUSE" if render else "NOT_REQUESTED",
            custody_artifacts=list(CUSTODY_FILENAMES[:4]),
        )
        _write_json(destination / "GRADUATION_RECEIPT.json", receipt)
        return receipt

    production_request = build_media_production_request(compiled, root=root)
    _write_json(destination / "MEDIA_PRODUCTION_REQUEST.json", production_request)

    render_state = "NOT_REQUESTED"
    render_receipt = None
    if render:
        rendered = build_premium_media(
            output_dir=destination / "premium_media",
            nichefoundry_root=nichefoundry_root,
            provider=provider,
            script_package=script_package,
            production_request=production_request,
        )
        render_receipt = rendered.get("receipt") if isinstance(rendered, dict) else None
        render_state = "PASS"

    receipt = _receipt(
        product_id=str(manifest.get("product_id") or product_id).upper(),
        semantic_graduation="PASS",
        missing=[],
        render_state=render_state,
        custody_artifacts=list(CUSTODY_FILENAMES),
        render_receipt=render_receipt,
    )
    _write_json(destination / "GRADUATION_RECEIPT.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile and optionally render a governed DIO product explainer graduation package.")
    parser.add_argument("--product", default="homs")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--nichefoundry-root", type=Path)
    parser.add_argument("--provider", default="auto", choices=["auto", "imported", "voicebox", "kokoro", "piper", "elevenlabs", "openvoice"])
    args = parser.parse_args()
    receipt = run_graduation(
        product_id=args.product,
        root=args.root,
        output_dir=args.output,
        render=args.render,
        nichefoundry_root=args.nichefoundry_root,
        provider=args.provider,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["semantic_graduation"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
