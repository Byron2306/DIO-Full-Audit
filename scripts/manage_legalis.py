#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.legalis import authorize_valinor_boundary, evaluate_capability, load_json

DEFAULT_IDENTITY = ROOT / "config" / "legalis" / "legal_identity.json"
DEFAULT_REGISTRY = ROOT / "config" / "legalis" / "requirement_registry.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate DIO Legalis configured prerequisites and optionally ask Valinor for kernel authorization.")
    parser.add_argument("request")
    parser.add_argument("--identity", default=str(DEFAULT_IDENTITY))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--out")
    parser.add_argument("--workspace-root", default="/home/byron/DIO")
    parser.add_argument("--authorize-valinor", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    request = load_json(args.request)
    identity = load_json(args.identity)
    registry = load_json(args.registry)
    capability_id = str(request.get("capability_id") or "")
    if not capability_id:
        print("REFUSE legalis: request requires capability_id.")
        return 2
    decision = evaluate_capability(
        capability_id=capability_id,
        identity=identity,
        registry=registry,
        evidence=list(request.get("evidence") or []),
        operator_checks=dict(request.get("operator_checks") or {}),
        now=request.get("now"),
    )
    envelope: dict[str, object] = {"decision": decision}
    if args.authorize_valinor and not args.dry_run:
        valinor = request.get("valinor") or {}
        entity_id = str(valinor.get("entity_id") or request.get("entity_id") or "")
        operation = str(valinor.get("operation") or "")
        if not entity_id or not operation:
            print("REFUSE legalis: --authorize-valinor requires valinor.entity_id and valinor.operation.")
            return 2
        envelope["valinor_authorization"] = authorize_valinor_boundary(
            decision=decision,
            entity_id=entity_id,
            operation=operation,
            target=valinor.get("target"),
            workspace_root=args.workspace_root,
        )
    if args.out and not args.dry_run:
        out = Path(args.out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        temp = out.with_suffix(out.suffix + ".tmp")
        temp.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(out)
        try:
            out.chmod(0o600)
        except OSError:
            pass
        envelope["receipt_path"] = str(out)
    print(json.dumps(envelope, indent=2, sort_keys=True))
    if decision["verdict"] == "REFUSE":
        return 2
    if decision["verdict"] == "NEEDS_YOU":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
