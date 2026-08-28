from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


class ProductExplainerError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _fingerprint(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load_media_style_profile(
    profile_id: str,
    *,
    root: Path = ROOT,
    require_assets: bool = True,
) -> tuple[dict[str, Any], str]:
    registry_path = Path(root) / "config" / "media_style_profiles.json"
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            f"invalid media style profile registry: {registry_path}",
        ) from exc

    if registry.get("schema") != "dio.media.style_profile_registry.v1":
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            "unsupported media style profile registry schema",
        )

    source_profile = (registry.get("profiles") or {}).get(profile_id)
    if not isinstance(source_profile, dict) or source_profile.get("schema") != "dio.media.style_profile.v1":
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            f"unknown or invalid media style profile: {profile_id}",
        )

    profile = json.loads(json.dumps(source_profile))
    release = profile.get("release") or {}
    if (
        release.get("automatic_external_publication") is not False
        or release.get("automatic_media_spend") is not False
    ):
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            "style profile may not create publication or spend authority",
        )

    typography = profile.get("typography") or {}
    if typography.get("silent_font_fallback") is not False:
        raise ProductExplainerError(
            "STYLE_PROFILE_INVALID",
            "silent font fallback must remain disabled",
        )

    if require_assets:
        try:
            required = [
                profile["golden_reference"]["master"],
                typography["wordmark"],
                typography["sigil"],
            ]
        except (KeyError, TypeError) as exc:
            raise ProductExplainerError(
                "STYLE_PROFILE_INVALID",
                "style profile is missing required asset bindings",
            ) from exc
        missing = [value for value in required if not (Path(root) / value).is_file()]
        if missing:
            raise ProductExplainerError(
                "STYLE_ASSET_MISSING",
                "required DIO brand assets are missing",
                {"missing": missing},
            )
        master_path = Path(root) / profile["golden_reference"]["master"]
        actual_master_sha = "sha256:" + hashlib.sha256(master_path.read_bytes()).hexdigest()
        declared_master_sha = profile["golden_reference"].get("sha256")
        if declared_master_sha in {None, "", "BOUND_AT_RUNTIME"}:
            profile["golden_reference"]["sha256"] = actual_master_sha
        elif declared_master_sha != actual_master_sha:
            raise ProductExplainerError(
                "STYLE_ASSET_HASH_MISMATCH",
                "golden reference master hash does not match the bound asset",
                {"expected": declared_master_sha, "actual": actual_master_sha},
            )

    return profile, _fingerprint(profile)

PORTFOLIO_EXACT_NAMES = (
    "DIO_META_PORTFOLIO_ATLAS_RUNTIME.json",
    "DIO_META_PORTFOLIO_ATLAS.json",
)


def _normalize_identifier(value: Any) -> str:
    return "".join(character for character in str(value or "").lower() if character.isalnum())


def _sha256_path(path: Path) -> str:
    path = Path(path)
    if path.is_file():
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    if path.is_dir():
        digest = hashlib.sha256()
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            digest.update(str(child.relative_to(path)).encode("utf-8"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(child.read_bytes()).digest())
        return "sha256:" + digest.hexdigest()
    raise FileNotFoundError(path)


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(path.resolve())


def _portfolio_candidates(root: Path) -> list[Path]:
    base = Path(root) / "state" / "product_portfolio"
    exact = [base / name for name in PORTFOLIO_EXACT_NAMES if (base / name).is_file()]
    if exact:
        return exact
    return sorted(base.glob("DIO_META_PORTFOLIO_ATLAS*.json")) if base.is_dir() else []


def _portfolio_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("incarnations", "products", "candidates", "suites"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, dict))
    return rows


def _row_matches_product(row: dict[str, Any], product_key: str) -> bool:
    fields = (
        row.get("Suite"),
        row.get("Incarnation"),
        row.get("product_id"),
        row.get("id"),
        row.get("name"),
    )
    normalized = [_normalize_identifier(value) for value in fields if value]
    return any(value == product_key or value.startswith(product_key) for value in normalized)


def _canonical_name(row: dict[str, Any], product_key: str) -> str:
    suite = str(row.get("Suite") or "").strip()
    if suite and _normalize_identifier(suite) == product_key:
        return suite
    for key in ("canonical_name", "name", "Incarnation", "product_id", "id"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return product_key


def _family_name_from_incarnations(rows: list[dict[str, Any]], product_key: str) -> str | None:
    """Return a display family name when every matched incarnation shares the exact queried token prefix."""
    prefixes: list[str] = []
    for row in rows:
        incarnation = str(row.get("Incarnation") or "").strip()
        if not incarnation:
            return None
        tokens = incarnation.split()
        parts: list[str] = []
        matched_prefix: str | None = None
        for token in tokens:
            parts.append(token)
            display = " ".join(parts)
            normalized = _normalize_identifier(display)
            if normalized == product_key:
                matched_prefix = display
                break
            if not product_key.startswith(normalized):
                break
        if matched_prefix is None:
            return None
        prefixes.append(matched_prefix)
    if not prefixes or {_normalize_identifier(value) for value in prefixes} != {product_key}:
        return None
    return prefixes[0]


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        marker = value.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


def _marketing_family_matches(product: dict[str, Any], product_key: str) -> bool:
    values = [
        _normalize_identifier(product.get("id")),
        _normalize_identifier(product.get("name")),
    ]
    return any(value == product_key or value.startswith(product_key) for value in values if value)


def resolve_product_truth(product_id: str, *, root: Path = ROOT) -> dict[str, Any]:
    root = Path(root)
    product_key = _normalize_identifier(product_id)
    if not product_key:
        raise ProductExplainerError("PRODUCT_IDENTITY_UNRESOLVED", "product identifier is empty")

    matched_sources: list[dict[str, Any]] = []
    for path in _portfolio_candidates(root):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProductExplainerError(
                "PRODUCT_TRUTH_INCOMPLETE",
                f"invalid canonical portfolio source: {path}",
            ) from exc
        rows = [row for row in _portfolio_rows(payload) if _row_matches_product(row, product_key)]
        if rows:
            matched_sources.append({"path": path, "rows": rows})

    if not matched_sources:
        raise ProductExplainerError(
            "PRODUCT_IDENTITY_UNRESOLVED",
            f"no canonical portfolio identity found for product: {product_id}",
        )

    canonical_names: set[str] = set()
    descriptions: set[str] = set()
    for source in matched_sources:
        for row in source["rows"]:
            canonical_names.add(_canonical_name(row, product_key).strip())
            description = str(row.get("Description") or row.get("description") or "").strip()
            if description:
                descriptions.add(description)

    normalized_names = {_normalize_identifier(name) for name in canonical_names if name}
    normalized_suite_names = {
        _normalize_identifier(str(row.get("Suite") or ""))
        for source in matched_sources
        for row in source["rows"]
        if str(row.get("Suite") or "").strip()
    }
    matched_rows = [row for source in matched_sources for row in source["rows"]]
    family_name = _family_name_from_incarnations(matched_rows, product_key)
    if len(normalized_suite_names) == 1 and product_key in normalized_suite_names:
        canonical_name = next(
            str(row.get("Suite")).strip()
            for source in matched_sources
            for row in source["rows"]
            if _normalize_identifier(row.get("Suite")) == product_key
        )
    elif len(normalized_names) == 1:
        canonical_name = next(iter(canonical_names))
    elif family_name is not None:
        canonical_name = family_name
    else:
        raise ProductExplainerError(
            "PRODUCT_IDENTITY_AMBIGUOUS",
            f"canonical portfolio sources disagree on product identity for: {product_id}",
            {"sources": [_relative_path(source["path"], root) for source in matched_sources]},
        )

    if len(matched_sources) > 1 and len(descriptions) > 1:
        raise ProductExplainerError(
            "PRODUCT_IDENTITY_AMBIGUOUS",
            f"canonical portfolio sources disagree on product definition for: {product_id}",
            {
                "sources": [_relative_path(source["path"], root) for source in matched_sources],
                "descriptions": sorted(descriptions),
            },
        )

    all_rows = [row for source in matched_sources for row in source["rows"]]
    capabilities = _dedupe(
        [
            item
            for row in all_rows
            for key in ("Capabilities", "capabilities", "Work Patterns", "work_patterns")
            for item in _as_string_list(row.get(key))
        ]
    )
    outputs = _dedupe(
        [
            item
            for row in all_rows
            for key in ("Outputs", "outputs", "Deliverables", "deliverables")
            for item in _as_string_list(row.get(key))
        ]
    )

    source_bindings: list[dict[str, Any]] = [
        {
            "path": _relative_path(source["path"], root),
            "sha256": _sha256_path(source["path"]),
            "role": "canonical_product_identity",
        }
        for source in matched_sources
    ]
    identity_path = matched_sources[0]["path"]

    audience_observations: list[dict[str, Any]] = []
    proof_assets: list[dict[str, Any]] = []
    marketing_path = root / "state" / "marketing_factory" / "CREATIVE_FAMILY_REGISTRY.json"
    if marketing_path.is_file():
        try:
            marketing = json.loads(marketing_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProductExplainerError(
                "PRODUCT_TRUTH_INCOMPLETE",
                f"invalid marketing supplement: {marketing_path}",
            ) from exc
        matching_families = [
            family
            for family in (marketing.get("families") or [])
            if isinstance(family, dict)
            and _marketing_family_matches(family.get("product") or {}, product_key)
        ]
        if matching_families:
            source_bindings.append(
                {
                    "path": _relative_path(marketing_path, root),
                    "sha256": _sha256_path(marketing_path),
                    "role": "marketing_supplement",
                }
            )
        seen_proof: set[str] = set()
        for family in matching_families:
            audience = family.get("audience") or {}
            observation = {
                "audience_id": audience.get("id"),
                "audience": audience.get("name"),
                "pain": audience.get("pain"),
                "outcome": audience.get("outcome"),
                "family_id": family.get("family_id"),
            }
            if any(value for value in observation.values()):
                audience_observations.append(observation)
            proof_value = str(family.get("proof_asset") or "").strip()
            if not proof_value or proof_value in seen_proof:
                continue
            seen_proof.add(proof_value)
            proof_path = Path(proof_value)
            if not proof_path.is_absolute():
                proof_path = root / proof_path
            proof = {
                "path": _relative_path(proof_path, root),
                "exists": proof_path.exists(),
                "sha256": _sha256_path(proof_path) if proof_path.exists() else None,
            }
            proof_assets.append(proof)
            if proof_path.exists():
                source_bindings.append(
                    {
                        "path": proof["path"],
                        "sha256": proof["sha256"],
                        "role": "proof_asset",
                    }
                )

    return {
        "product_id": product_key,
        "canonical_name": canonical_name,
        "description": next(iter(descriptions), ""),
        "identity_source": _relative_path(identity_path, root),
        "identity_sha256": _sha256_path(identity_path),
        "portfolio_rows": all_rows,
        "capabilities": capabilities,
        "outputs": outputs,
        "proof_assets": proof_assets,
        "audience_observations": audience_observations,
        "source_bindings": source_bindings,
    }


# Public semantic/story interfaces live in a focused module; re-export them
# here to preserve the canonical Product Explainer Compiler API.
from .product_explainer_pipeline import (  # noqa: E402
    ASSET_PREFERENCE,
    REQUIRED_EXPLANATION_FIELDS,
    build_claim_envelope,
    build_explainer_script_package,
    build_media_production_request,
    compile_product_explainer,
    semantic_challenge,
)
