from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

EXTENSION_SCHEMA = "dio.product_grade.canon_extension_gauntlet_receipt.v1"
PRODUCT_GRADE_TOKEN = "DIO_CANON_EXTENSION_PRODUCT_GRADE_VERIFIED"
EXTENSION_15_X3_SCHEMA = "dio.product_grade.canon_extension_gauntlet_receipt.v2"
PRODUCT_GRADE_15_X3_TOKEN = "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED"
PROOF_TOKEN = "DIO_CANON_EXTENSION_PROOF_VERIFIED"
PRODUCT_GRADE_STATUS = "PRODUCT_GRADE_VERIFIED"
PROOF_STATUS = "CANON_EXTENSION_PROOF_VERIFIED"


def _has_supported_summary_provenance(receipt: dict[str, Any]) -> bool:
    if (
        receipt.get("schema") == EXTENSION_SCHEMA
        and receipt.get("acceptance_token") == PRODUCT_GRADE_TOKEN
    ):
        return True
    return (
        receipt.get("schema") == EXTENSION_15_X3_SCHEMA
        and receipt.get("acceptance_token") == PRODUCT_GRADE_15_X3_TOKEN
        and receipt.get("variants_per_extension") == 3
        and receipt.get("controlled_journey_count") == 45
        and receipt.get("verified_journey_count") == 45
        and receipt.get("refused_journey_count") == 0
        and receipt.get("product_grade_refuse_count") == 0
        and receipt.get("canon_extension_proof_refuse_count") == 0
    )


def summary_is_publishable(receipt: dict[str, Any]) -> bool:
    extensions = receipt.get("extensions")
    is_15_x3 = receipt.get("schema") == EXTENSION_15_X3_SCHEMA
    if not (
        _has_supported_summary_provenance(receipt)
        and receipt.get("proof_acceptance_token") == PROOF_TOKEN
        and receipt.get("extension_count") == 15
        and receipt.get("product_grade_verified_count") == 15
        and receipt.get("canon_extension_proof_verified_count") == 15
        and receipt.get("all_product_grade_verified") is True
        and receipt.get("all_canon_extension_proof_verified") is True
        and receipt.get("commercial_validation") == "UNPROVED"
        and receipt.get("authority_created") is False
        and receipt.get("external_effects") is False
        and isinstance(extensions, dict)
        and len(extensions) == 15
    ):
        return False

    seen_ids: set[str] = set()
    seen_slugs: set[str] = set()
    for key, row in extensions.items():
        if not isinstance(row, dict):
            return False
        canon_id = str(row.get("canon_id") or "").strip()
        slug = str(row.get("slug") or key).strip()
        if (
            not canon_id
            or not slug
            or canon_id in seen_ids
            or slug in seen_slugs
            or row.get("status") != PRODUCT_GRADE_STATUS
            or row.get("proof_status") != PROOF_STATUS
            or bool(row.get("critical_blockers"))
            or row.get("customers_will_pay") != "UNPROVED"
            or row.get("verified_payment") != "UNPROVED"
            or (
                is_15_x3
                and (
                    row.get("variant_count") != 3
                    or row.get("verified_variant_count") != 3
                )
            )
        ):
            return False
        seen_ids.add(canon_id)
        seen_slugs.add(slug)
    return True


def persist_verified_summary(receipt: dict[str, Any], path: Path) -> bool:
    if not summary_is_publishable(receipt):
        return False
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return True
