from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any


_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "capability_id": "format_core.semantic_finish",
        "name": "Format Core",
        "purpose": "Render governed semantic content into review-ready formats.",
        "provider_id": "dio.shared.format_core",
        "provider_kind": "native_python",
        "source_path": "adapters/format_core/renderer.py",
        "entrypoint": "render_semantic_asset",
        "activation_gate": "bounded_fulfilment_request",
    },
    {
        "capability_id": "production_studio.customer_delivery",
        "name": "Production Studio",
        "purpose": "Package customer-facing artifacts and their delivery boundary.",
        "provider_id": "dio.shared.production_studio",
        "provider_kind": "native_python",
        "source_path": "presence_core/shared_production_finish.py",
        "entrypoint": "finish_fulfilment_for_review",
        "activation_gate": "bounded_fulfilment_request",
    },
    {
        "capability_id": "document_studio.document_pipeline",
        "name": "Document Studio",
        "purpose": "Compose governed document, publication, and correspondence bundles.",
        "provider_id": "dio.shared.document_studio",
        "provider_kind": "native_python",
        "source_path": "adapters/document_studio/pipeline.py",
        "entrypoint": "run_document_studio",
        "activation_gate": "approved_document_request",
    },
    {
        "capability_id": "nichefoundry.campaign_materials",
        "name": "NicheFoundry",
        "purpose": "Prepare approved campaign briefs, copy packs, and governed media requests.",
        "provider_id": "dio.shared.nichefoundry",
        "provider_kind": "native_python",
        "source_path": "scripts/run_nichefoundry_jobs.py",
        "entrypoint": "write_job",
        "activation_gate": "approved_media_request",
    },
)

_DOCUMENT_REQUIRED_ROUTES = frozenset({"homs_learning", "document_studio"})
_NICHEFOUNDRY_REQUIRED_ROUTES = frozenset({"nichefoundry_campaign"})


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_shared_capability_registry(root: Path) -> dict[str, dict[str, Any]]:
    """Resolve the four portfolio-wide professional production providers."""

    root = Path(root).resolve()
    result: dict[str, dict[str, Any]] = {}
    for definition in _CAPABILITIES:
        source_path = str(definition["source_path"])
        source = root / source_path
        if not source.is_file():
            raise ValueError(
                "shared capability provider source is missing: "
                f"{definition['capability_id']} ({source_path})"
            )
        provider = {
            "provider_id": definition["provider_id"],
            "provider_kind": definition["provider_kind"],
            "source_path": source_path,
            "entrypoint": definition["entrypoint"],
            "source_sha256": _file_sha256(source),
            "execution_capable": True,
            "product_scope": "canonical_68",
        }
        result[str(definition["name"]).casefold().replace(" ", "_")] = {
            "capability_id": definition["capability_id"],
            "name": definition["name"],
            "purpose": definition["purpose"],
            "resolution_state": "RESOLVED",
            "availability": "AVAILABLE_TO_ALL_CANONICAL_PRODUCTS",
            "activation_gate": definition["activation_gate"],
            "provider": provider,
            "authority_created": False,
            "external_send_authority": False,
            "publication_authority": False,
            "spend_authority": False,
        }
    return result


def build_route_capability_plan(
    root: Path,
    route_id: str,
    route_provider: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build the ordered execution and optional-assistance plan for one route."""

    shared = build_shared_capability_registry(root)
    route_source = Path(root).resolve() / str(route_provider.get("source_path") or "")
    if route_provider.get("execution_class") == "native" and not route_source.is_file():
        raise ValueError(f"native route provider source is missing: {route_id}")

    route_step = {
        "capability_id": f"customer_journey.fulfilment.{route_id}",
        "name": "Native product fulfilment route",
        "purpose": "Produce the product-specific substance and proof artifacts.",
        "sequence": 10,
        "execution_required": True,
        "resolution_state": "RESOLVED",
        "activation_gate": "bounded_fulfilment_request",
        "depends_on": [],
        "provider": {
            "provider_id": route_provider["adapter_id"],
            "provider_kind": route_provider["execution_class"],
            "source_path": route_provider["source_path"],
            "source_sha256": route_provider.get("source_sha256"),
            "execution_capable": True,
            "repository": route_provider.get("repository"),
            "repository_commit": route_provider.get("repository_commit"),
            "route_fingerprint": route_provider["route_fingerprint"],
        },
        "authority_created": False,
        "external_send_authority": False,
    }
    plan = [route_step]
    rules = (
        (
            "document_studio",
            False,
            15,
            [route_step["capability_id"]],
        ),
        (
            "nichefoundry",
            False,
            16,
            [route_step["capability_id"]],
        ),
        ("format_core", True, 20, [route_step["capability_id"]]),
        ("production_studio", True, 30, ["format_core.semantic_finish"]),
    )
    for key, required, sequence, dependencies in rules:
        capability = deepcopy(shared[key])
        capability.update(
            {
                "sequence": sequence,
                "execution_required": required,
                "depends_on": dependencies,
                "route_requirement": (
                    "REQUIRED_WITHIN_NATIVE_ROUTE"
                    if (
                        key == "document_studio"
                        and route_id in _DOCUMENT_REQUIRED_ROUTES
                    )
                    or (
                        key == "nichefoundry"
                        and route_id in _NICHEFOUNDRY_REQUIRED_ROUTES
                    )
                    else "AVAILABLE_ON_APPROVED_REQUEST"
                ),
            }
        )
        plan.append(capability)
    return plan

