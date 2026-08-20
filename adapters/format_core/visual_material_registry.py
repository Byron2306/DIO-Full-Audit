from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = ROOT / "config" / "visual_material_registry.json"
MATERIAL_SCHEMA = "dio.format_core.visual_material.v1"
REGISTRY_SCHEMA = "dio.format_core.visual_material_registry.v1"

MATERIAL_KINDS = {
    "native_renderer",
    "artifact_render",
    "curated_photo",
    "curated_illustration",
    "texture",
    "icon",
    "generated_editorial",
}
FILE_MATERIAL_KINDS = MATERIAL_KINDS - {"native_renderer"}
ALLOWED_LICENSE_STATES = {
    "INTERNAL_ORIGINAL",
    "COMMERCIAL_ALLOWED",
    "PUBLIC_DOMAIN",
    "DIO_GENERATED",
}
ALLOWED_APPROVAL_STATES = {"SYSTEM", "APPROVED", "NEEDS_REVIEW", "REFUSE"}
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class VisualMaterialRegistryError(RuntimeError):
    pass


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _safe_relative_path(value: Any) -> Path | None:
    raw = _clean(value)
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path


def validate_visual_material(material: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if material.get("schema") != MATERIAL_SCHEMA:
        errors.append(f"schema must be {MATERIAL_SCHEMA}")
    material_id = _clean(material.get("material_id"))
    if not material_id:
        errors.append("material_id is required")
    kind = _clean(material.get("material_kind"))
    if kind not in MATERIAL_KINDS:
        errors.append(f"unsupported material_kind: {kind or '(missing)'}")

    visual_kinds = [str(row) for row in material.get("semantic_visual_kinds") or [] if _clean(row)]
    surfaces = [str(row) for row in material.get("surface_suitability") or [] if _clean(row)]
    if not visual_kinds:
        errors.append("semantic_visual_kinds must not be empty")
    if not surfaces:
        errors.append("surface_suitability must not be empty")

    approval = dict(material.get("approval") or {})
    approval_state = _clean(approval.get("state"))
    if approval_state not in ALLOWED_APPROVAL_STATES:
        errors.append(f"unsupported approval state: {approval_state or '(missing)'}")

    license_row = dict(material.get("license") or {})
    license_state = _clean(license_row.get("status"))
    if license_state not in ALLOWED_LICENSE_STATES:
        errors.append(f"unsupported license status: {license_state or '(missing)'}")
    if license_row.get("commercial_use") is not True:
        errors.append("commercial_use must be true")
    if not isinstance(license_row.get("attribution_required"), bool):
        errors.append("attribution_required must be boolean")

    external = kind in {"curated_photo", "curated_illustration", "texture", "icon"}
    if external and approval_state != "APPROVED":
        errors.append("external curated material must be APPROVED before selection")
    if external and license_state not in {"COMMERCIAL_ALLOWED", "PUBLIC_DOMAIN"}:
        errors.append("external curated material requires COMMERCIAL_ALLOWED or PUBLIC_DOMAIN license")
    if kind == "generated_editorial" and license_state != "DIO_GENERATED":
        errors.append("generated_editorial material requires DIO_GENERATED license state")
    if kind == "artifact_render" and license_state not in {"INTERNAL_ORIGINAL", "DIO_GENERATED"}:
        errors.append("artifact_render must be INTERNAL_ORIGINAL or DIO_GENERATED")
    if kind == "native_renderer" and approval_state != "SYSTEM":
        errors.append("native_renderer approval state must be SYSTEM")

    payload = dict(material.get("payload") or {})
    if kind in FILE_MATERIAL_KINDS:
        relative = _safe_relative_path(payload.get("path"))
        if relative is None:
            errors.append("file material requires a safe repository-relative payload.path")
        elif relative.suffix.casefold() not in ALLOWED_IMAGE_SUFFIXES:
            errors.append(f"unsupported image suffix: {relative.suffix or '(missing)'}")
        expected_hash = _clean(payload.get("sha256"))
        if not expected_hash.startswith("sha256:"):
            errors.append("file material requires payload.sha256")
        if root is not None and relative is not None:
            candidate = (root / relative).resolve()
            root_resolved = root.resolve()
            try:
                candidate.relative_to(root_resolved)
            except ValueError:
                errors.append("payload.path escapes material root")
            else:
                if not candidate.is_file():
                    errors.append(f"material payload missing: {relative.as_posix()}")
                elif expected_hash and sha256_file(candidate) != expected_hash:
                    errors.append(f"material payload hash mismatch: {relative.as_posix()}")
    elif payload.get("path"):
        warnings.append("native_renderer ignores payload.path")

    composition = dict(material.get("composition") or {})
    if composition:
        orientation = _clean(composition.get("orientation"))
        if orientation and orientation not in {"landscape", "portrait", "square", "flexible"}:
            errors.append(f"unsupported composition.orientation: {orientation}")
        negative_space = _clean(composition.get("negative_space"))
        if negative_space and negative_space not in {"left", "right", "top", "bottom", "balanced", "none"}:
            errors.append(f"unsupported composition.negative_space: {negative_space}")
        subject_bias = _clean(composition.get("subject_bias"))
        if subject_bias and subject_bias not in {"left", "right", "center", "top", "bottom", "balanced"}:
            errors.append(f"unsupported composition.subject_bias: {subject_bias}")
        if "crop_safe" in composition and not isinstance(composition.get("crop_safe"), bool):
            errors.append("composition.crop_safe must be boolean")

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "material_id": material_id,
        "material_kind": kind,
        "selectable": not errors and approval_state in {"SYSTEM", "APPROVED"},
    }


def validate_visual_material_registry(registry: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if registry.get("schema") != REGISTRY_SCHEMA:
        errors.append(f"schema must be {REGISTRY_SCHEMA}")
    materials = list(registry.get("materials") or [])
    if not materials:
        errors.append("registry must contain at least one material")

    seen: set[str] = set()
    validations: list[dict[str, Any]] = []
    for index, material in enumerate(materials, 1):
        validation = validate_visual_material(dict(material), root=root)
        validations.append(validation)
        material_id = validation["material_id"]
        if material_id in seen:
            errors.append(f"duplicate material_id: {material_id}")
        seen.add(material_id)
        errors.extend(f"material {index}: {error}" for error in validation["errors"])
        warnings.extend(f"material {index}: {warning}" for warning in validation["warnings"])

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "material_count": len(materials),
        "selectable_count": sum(bool(row["selectable"]) for row in validations),
    }


def load_visual_material_registry(path: Path | None = None, *, root: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_REGISTRY_PATH
    registry = json.loads(target.read_text(encoding="utf-8"))
    validation = validate_visual_material_registry(registry, root=root)
    if not validation["passed"]:
        raise VisualMaterialRegistryError("Invalid visual material registry: " + "; ".join(validation["errors"]))
    return registry


def material_index(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["material_id"]): dict(row) for row in registry.get("materials") or []}


def material_data_uri(material: dict[str, Any], *, root: Path) -> str:
    validation = validate_visual_material(material, root=root)
    if not validation["passed"]:
        raise VisualMaterialRegistryError("Material is not renderable: " + "; ".join(validation["errors"]))
    if validation["material_kind"] not in FILE_MATERIAL_KINDS:
        raise VisualMaterialRegistryError("native_renderer does not expose image bytes")
    relative = _safe_relative_path((material.get("payload") or {}).get("path"))
    if relative is None:
        raise VisualMaterialRegistryError("material payload path is invalid")
    path = (root / relative).resolve()
    mime, _ = mimetypes.guess_type(path.name)
    mime = mime or "application/octet-stream"
    if mime not in {"image/png", "image/jpeg", "image/webp"}:
        raise VisualMaterialRegistryError(f"unsupported material MIME type: {mime}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


__all__ = [
    "ALLOWED_APPROVAL_STATES",
    "ALLOWED_LICENSE_STATES",
    "DEFAULT_REGISTRY_PATH",
    "FILE_MATERIAL_KINDS",
    "MATERIAL_KINDS",
    "MATERIAL_SCHEMA",
    "REGISTRY_SCHEMA",
    "VisualMaterialRegistryError",
    "content_hash",
    "load_visual_material_registry",
    "material_data_uri",
    "material_index",
    "sha256_file",
    "validate_visual_material",
    "validate_visual_material_registry",
]
