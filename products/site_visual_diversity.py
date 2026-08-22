from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "site_visual_diversity.json"
SCHEMA = "dio.site_visual_diversity_receipt.v1"


class SiteVisualDiversityError(RuntimeError):
    pass


def _load_contract(path: Path | None = None) -> dict[str, Any]:
    target = Path(path or CONTRACT_PATH)
    value = json.loads(target.read_text(encoding="utf-8"))
    if value.get("schema") != "dio.site_visual_diversity_contract.v1":
        raise SiteVisualDiversityError("site visual diversity contract schema mismatch")
    return value


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _canonical_geometry(element: ElementTree.Element, *, ignored_elements: set[str], ignored_attributes: set[str]) -> Any:
    name = _local_name(element.tag)
    if name in ignored_elements:
        return None
    attrs = tuple(
        sorted(
            (str(key).rsplit("}", 1)[-1], str(value))
            for key, value in element.attrib.items()
            if str(key).rsplit("}", 1)[-1] not in ignored_attributes
            and not str(key).rsplit("}", 1)[-1].startswith("data-")
            and not str(key).rsplit("}", 1)[-1].startswith("aria-")
        )
    )
    children = []
    for child in list(element):
        canonical = _canonical_geometry(
            child,
            ignored_elements=ignored_elements,
            ignored_attributes=ignored_attributes,
        )
        if canonical is not None:
            children.append(canonical)
    return (name, attrs, tuple(children))


def geometry_hash(path: Path, *, contract: dict[str, Any] | None = None) -> str:
    contract = dict(contract or _load_contract())
    try:
        root = ElementTree.fromstring(Path(path).read_text(encoding="utf-8", errors="replace"))
    except (OSError, ElementTree.ParseError) as exc:
        raise SiteVisualDiversityError(f"unable to parse SVG {path}: {exc}") from exc
    canonical = _canonical_geometry(
        root,
        ignored_elements={str(row) for row in contract.get("ignore_svg_elements") or []},
        ignored_attributes={str(row) for row in contract.get("ignore_svg_attributes") or []},
    )
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def audit_suite_visual_diversity(visual_root: Path, *, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = dict(contract or _load_contract())
    visual_root = Path(visual_root).resolve()
    files = sorted(visual_root.glob("*/*.svg")) if visual_root.is_dir() else []
    rows: list[dict[str, Any]] = []
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in files:
        relative = path.relative_to(visual_root)
        if len(relative.parts) < 2:
            continue
        suite = relative.parts[0]
        role = path.stem
        row = {
            "suite": suite,
            "role": role,
            "path": str(relative),
            "geometry_hash": geometry_hash(path, contract=contract),
        }
        rows.append(row)
        by_role[role].append(row)

    min_role_ratio = float(contract.get("minimum_unique_geometry_ratio_per_repeated_role") or 1.0)
    max_identical = int(contract.get("maximum_identical_geometry_reuse_per_role") or 1)
    role_results: dict[str, Any] = {}
    repeated_role_passes: list[bool] = []
    for role, role_rows in sorted(by_role.items()):
        hashes = [str(row["geometry_hash"]) for row in role_rows]
        unique_count = len(set(hashes))
        reuse = Counter(hashes)
        unique_ratio = round(unique_count / len(role_rows), 4) if role_rows else 0.0
        repeated = len(role_rows) > 1
        passed = (
            not repeated
            or (
                unique_ratio >= min_role_ratio
                and max(reuse.values(), default=0) <= max_identical
            )
        )
        if repeated:
            repeated_role_passes.append(passed)
        role_results[role] = {
            "asset_count": len(role_rows),
            "unique_geometry_count": unique_count,
            "unique_geometry_ratio": unique_ratio,
            "maximum_identical_reuse": max(reuse.values(), default=0),
            "passed": passed,
        }

    all_hashes = [str(row["geometry_hash"]) for row in rows]
    portfolio_unique = len(set(all_hashes))
    portfolio_ratio = round(portfolio_unique / len(rows), 4) if rows else 0.0
    min_portfolio_ratio = float(contract.get("minimum_unique_geometry_ratio_portfolio") or 1.0)
    checks = {
        "visual_assets_present": bool(rows),
        "repeated_roles_present": bool(repeated_role_passes),
        "all_repeated_roles_diverse": bool(repeated_role_passes) and all(repeated_role_passes),
        "portfolio_geometry_ratio": portfolio_ratio >= min_portfolio_ratio,
    }
    passed = all(checks.values())
    receipt = {
        "schema": SCHEMA,
        "visual_root": str(visual_root),
        "svg_asset_count": len(rows),
        "unique_geometry_count": portfolio_unique,
        "unique_geometry_ratio": portfolio_ratio,
        "role_results": role_results,
        "assets": rows,
        "checks": checks,
        "visual_diversity_verified": passed,
        "site_acceptance_allowed": passed,
        "authority_created": False,
        "external_effects": False,
        "acceptance_token": "DIO_SITE_VISUAL_DIVERSITY_VERIFIED" if passed else "DIO_SITE_VISUAL_DIVERSITY_REFUSED",
    }
    return receipt


__all__ = ["CONTRACT_PATH", "SCHEMA", "SiteVisualDiversityError", "audit_suite_visual_diversity", "geometry_hash"]
