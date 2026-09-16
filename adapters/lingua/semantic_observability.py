from __future__ import annotations

from pathlib import Path
from typing import Any

from .conversation_crystals import registry_path_for_role
from .semantic_lifecycle import lifecycle_inventory


def build_semantic_memory_status(
    *,
    root: Path,
) -> dict[str, Any]:
    """Return read-only Vesper semantic-memory health truth.

    This surface is observational only:
    - no promotion
    - no revocation
    - no replacement
    - no authority creation
    - no external effects
    """

    root = Path(root)

    roles: dict[str, Any] = {}

    total_active = 0
    total_revoked = 0

    for role in ("public", "operator"):
        path = registry_path_for_role(
            root=root,
            role=role,
        )

        if path.exists():
            inventory = lifecycle_inventory(
                registry_path=path
            )
        else:
            inventory = {
                "schema":
                    "dio.vesper.semantic_lifecycle."
                    "inventory.v1",
                "records": [],
                "active": 0,
                "revoked": 0,
                "authority_created": False,
                "external_effects": False,
            }

        rows = []

        for row in inventory["records"]:
            rows.append(
                {
                    "crystal_id":
                        row["crystal_id"],

                    "lifecycle_state":
                        row["lifecycle_state"],

                    "semantic_key_digest":
                        row["semantic_key_digest"],

                    "promotion_receipt_digest":
                        row["promotion_receipt_digest"],

                    "verifier_version":
                        row["verifier_version"],

                    "expires_at":
                        row["expires_at"],

                    "revoked_reason":
                        row["revoked_reason"],

                    "health_state":
                        (
                            "ACTIVE"
                            if row["lifecycle_state"]
                            == "active"
                            else "REVOKED"
                        ),
                }
            )

        active = int(
            inventory.get("active", 0)
        )

        revoked = int(
            inventory.get("revoked", 0)
        )

        total_active += active
        total_revoked += revoked

        roles[role] = {
            "registry_path":
                str(path),

            "active":
                active,

            "revoked":
                revoked,

            "records":
                rows,
        }

    return {
        "schema":
            "dio.vesper.semantic_memory_status.v1",

        "roles":
            roles,

        "summary": {
            "active":
                total_active,

            "revoked":
                total_revoked,

            "total":
                total_active
                + total_revoked,
        },

        "mutation_authority":
            False,

        "promotion_authority":
            False,

        "revocation_authority":
            False,

        "replacement_authority":
            False,

        "authority_created":
            False,

        "external_effects":
            False,
    }
