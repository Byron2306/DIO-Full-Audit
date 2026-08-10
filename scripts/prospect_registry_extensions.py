#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "prospect_registry_extensions.json"

ALLOWED_OUTREACH_CLASSES = {
    "CHANNEL_OK",
    "CONSENT_REQUEST_ONLY",
    "RESEARCH_ONLY",
    "BLOCKED",
}


def load_registry_extensions(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_registry_extensions(payload)
    return payload


def validate_registry_extensions(payload: dict[str, Any]) -> None:
    if payload.get("schema") != "dio.prospect_registry.extensions.v1":
        raise ValueError("Unsupported prospect registry extension schema")

    weights = payload.get("score_weights") or {}
    if sum(int(value) for value in weights.values()) != 100:
        raise ValueError("Prospect score weights must sum to 100")

    seen: set[str] = set()
    for row in payload.get("records") or []:
        record_id = row.get("registry_extension_id")
        if not record_id or record_id in seen:
            raise ValueError(f"Missing or duplicate registry_extension_id: {record_id!r}")
        seen.add(record_id)

        outreach_class = row.get("outreach_class")
        if outreach_class not in ALLOWED_OUTREACH_CLASSES:
            raise ValueError(f"Invalid outreach_class for {record_id}: {outreach_class!r}")

        scores = row.get("scores") or {}
        for key, max_value in weights.items():
            value = int(scores.get(key, -1))
            if value < 0 or value > int(max_value):
                raise ValueError(
                    f"Score {key} for {record_id} must be between 0 and {max_value}; got {value}"
                )

        if row.get("do_not_contact") and outreach_class != "BLOCKED":
            raise ValueError(f"Do-not-contact record {record_id} must use BLOCKED outreach_class")


def lead_score(row: dict[str, Any]) -> int:
    return sum(int(value) for value in (row.get("scores") or {}).values())


def governance_gate(row: dict[str, Any]) -> dict[str, Any]:
    outreach_class = row["outreach_class"]
    permission_state = row.get("permission_state") or "unknown"
    blocked = bool(row.get("do_not_contact")) or outreach_class == "BLOCKED"

    return {
        "research_allowed": not blocked,
        "channel_submission_allowed": outreach_class == "CHANNEL_OK" and not blocked,
        "consent_request_allowed": outreach_class == "CONSENT_REQUEST_ONLY" and not blocked,
        "sales_outreach_allowed": permission_state in {"consented", "existing_customer"} and not blocked,
        "operator_review_required": True,
        "public_source_is_permission": False,
    }


def ranked_records(
    payload: dict[str, Any],
    *,
    product: str | None = None,
    outreach_class: str | None = None,
) -> list[dict[str, Any]]:
    records = []
    for source in payload.get("records") or []:
        if product and product not in (source.get("product_fit") or []):
            continue
        if outreach_class and source.get("outreach_class") != outreach_class:
            continue
        row = dict(source)
        row["lead_score"] = lead_score(row)
        row["governance"] = governance_gate(row)
        records.append(row)
    return sorted(records, key=lambda item: (-item["lead_score"], item["organisation"]))


def export_compact(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "registry_extension_id": row["registry_extension_id"],
            "organisation": row["organisation"],
            "product_fit": row.get("product_fit"),
            "buyer_role": row.get("buyer_role"),
            "reason_now": row.get("reason_now"),
            "pilot_hypothesis": row.get("pilot_hypothesis"),
            "network_reach": row.get("network_reach"),
            "lead_score": row["lead_score"],
            "outreach_class": row["outreach_class"],
            "permission_state": row.get("permission_state"),
            "sales_outreach_allowed": row["governance"]["sales_outreach_allowed"],
            "consent_request_allowed": row["governance"]["consent_request_allowed"],
            "channel_submission_allowed": row["governance"]["channel_submission_allowed"],
        }
        for row in records
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect DIO prospect-registry commercial intelligence extensions")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--product", choices=["HOMS", "EVIDEX"])
    parser.add_argument("--outreach-class", choices=sorted(ALLOWED_OUTREACH_CLASSES))
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    payload = load_registry_extensions(args.config)
    records = ranked_records(payload, product=args.product, outreach_class=args.outreach_class)[: max(args.top, 0)]
    result = records if args.full else export_compact(records)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
