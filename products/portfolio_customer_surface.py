from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "portfolio_customer_surface_gauntlet.json"
CROSSWALK_PATH = ROOT / "config" / "atlas" / "dio_meta_incarnation_crosswalk.csv"
SCHEMA = "dio.portfolio.customer_surface_evaluation.v1"
PORTAL_SCHEMA = "dio.portfolio.customer_surface_review_portal.v1"
READY = "ENGINEERING_READY_NEEDS_BUYER_REVIEW"
REFUSE_PIPELINE = "REFUSE_PIPELINE"
REFUSE_SURFACE = "REFUSE_NO_CUSTOMER_SURFACE"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean(value).casefold()).strip()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "surface"


def content_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_contract(path: Path | None = None) -> dict[str, Any]:
    target = path or CONTRACT_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("schema") != "dio.portfolio.customer_surface_gauntlet.v1":
        raise ValueError("invalid portfolio customer-surface contract schema")
    return payload


def load_crosswalk(path: Path | None = None) -> dict[str, dict[str, str]]:
    target = path or CROSSWALK_PATH
    with target.open("r", encoding="utf-8", newline="") as handle:
        rows = {str(row["incarnation"]): dict(row) for row in csv.DictReader(handle)}
    if len(rows) != 53:
        raise ValueError(f"expected 53 canonical incarnations, found {len(rows)}")
    return rows


def resolve_wave(contract: dict[str, Any], crosswalk: dict[str, dict[str, str]], wave: str) -> dict[str, list[str]]:
    definition = dict((contract.get("waves") or {}).get(wave) or {})
    if not definition:
        raise ValueError(f"unknown customer-surface wave: {wave}")
    canonical_raw = definition.get("canonical")
    if canonical_raw == "__ALL_CANONICAL__":
        canonical = list(crosswalk)
    else:
        canonical = [str(value) for value in canonical_raw or []]
    unknown = sorted(set(canonical) - set(crosswalk))
    if unknown:
        raise ValueError(f"wave {wave} contains unknown canonical incarnations: {unknown}")
    studios = [str(value) for value in definition.get("studios") or []]
    known_studios = set((contract.get("studio_policies") or {}).keys())
    unknown_studios = sorted(set(studios) - known_studios)
    if unknown_studios:
        raise ValueError(f"wave {wave} contains unknown Studios: {unknown_studios}")
    return {"canonical": canonical, "studios": studios}


def resolve_family_policy(contract: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    haystack = " | ".join(
        [
            str(source.get("primary_family") or ""),
            str(source.get("suite") or ""),
            str(source.get("incarnation") or ""),
        ]
    ).casefold()
    for policy in contract.get("family_surface_policies") or []:
        if any(str(token).casefold() in haystack for token in policy.get("match_any") or []):
            return dict(policy)
    return dict(contract.get("default_surface_policy") or {})


def _visible_text(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix not in {".html", ".htm", ".md", ".txt", ".csv", ".svg"}:
        return ""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")[:250_000]
    except OSError:
        return ""
    if suffix in {".html", ".htm", ".svg"}:
        raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
        raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
        raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def _internal_name(path: Path, gate: dict[str, Any]) -> bool:
    name = _token(path.name)
    return any(_token(token) in name for token in gate.get("internal_name_tokens") or [])


def inspect_artifact(
    path: Path,
    *,
    gate: dict[str, Any],
    policy: dict[str, Any],
    terminal_artifact_kind: str = "",
) -> dict[str, Any]:
    path = path.resolve()
    suffix = path.suffix.casefold()
    minimum_bytes = int(gate.get("minimum_bytes") or 300)
    supported = [str(value).casefold() for value in gate.get("supported_suffixes") or []]
    preferred_global = [str(value).casefold() for value in gate.get("preferred_suffix_order") or []]
    preferred_policy = [str(value).casefold() for value in policy.get("preferred_suffixes") or []]
    reasons: list[str] = []

    if not path.is_file():
        reasons.append("NOT_A_FILE")
        size = 0
    else:
        size = path.stat().st_size
    if suffix not in supported:
        reasons.append("UNSUPPORTED_SUFFIX")
    if size < minimum_bytes:
        reasons.append("TOO_SMALL")
    if _internal_name(path, gate):
        reasons.append("INTERNAL_MACHINERY_NAME")

    visible = _visible_text(path) if path.is_file() else ""
    if suffix in {".html", ".htm", ".md", ".txt", ".csv"} and len(visible) < 120:
        reasons.append("TOO_LITTLE_VISIBLE_CONTENT")

    score = 0
    if not reasons:
        if suffix in preferred_global:
            score += (len(preferred_global) - preferred_global.index(suffix)) * 100
        if suffix in preferred_policy:
            score += (len(preferred_policy) - preferred_policy.index(suffix)) * 180
        score += min(240, int(math.log2(max(2, size))) * 12)

        terminal_tokens = {word for word in _token(terminal_artifact_kind).split() if len(word) >= 4}
        name_tokens = set(_token(path.stem).split())
        score += min(120, len(terminal_tokens & name_tokens) * 30)
        source_like = any(_token(token) in _token(path.name) for token in gate.get("source_like_tokens") or [])
        if source_like:
            score -= 180

    return {
        "state": "PASS" if not reasons else "REFUSE",
        "path": str(path),
        "name": path.name,
        "suffix": suffix,
        "bytes": size,
        "sha256": sha256_file(path) if path.is_file() else None,
        "visible_text_characters": len(visible),
        "score": score,
        "refusal_reasons": reasons,
    }


def scan_customer_surface(
    root: Path,
    *,
    gate: dict[str, Any],
    policy: dict[str, Any],
    terminal_artifact_kind: str = "",
) -> dict[str, Any]:
    root = root.resolve()
    rows: list[dict[str, Any]] = []
    if root.is_file():
        rows = [inspect_artifact(root, gate=gate, policy=policy, terminal_artifact_kind=terminal_artifact_kind)]
    elif root.is_dir():
        for path in sorted(root.rglob("*")):
            if path.is_file():
                rows.append(inspect_artifact(path, gate=gate, policy=policy, terminal_artifact_kind=terminal_artifact_kind))

    passing = [row for row in rows if row["state"] == "PASS"]
    passing.sort(key=lambda row: (-int(row["score"]), -int(row["bytes"]), str(row["path"])))
    limit = int(gate.get("max_review_artifacts_per_product") or 3)
    selected = passing[:limit]
    return {
        "state": "PASS" if selected else "REFUSE",
        "surface_root": str(root),
        "candidate_count": len(passing),
        "inspected_file_count": len(rows),
        "selected": selected,
        "refused_sample": [row for row in rows if row["state"] != "PASS"][:10],
        "claim_boundary": "Automated surface inspection measures substantial buyer-readable artifact presence and presentation signals. It does not judge correctness, buyer acceptance or willingness to pay.",
    }


def evaluate_canonical_surface(
    *,
    incarnation: str,
    source: dict[str, Any],
    multitier_row: dict[str, Any],
    canonical_root: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    policy = resolve_family_policy(contract, {**source, "incarnation": incarnation})
    variants = dict(multitier_row.get("variants") or {})
    normal = dict(variants.get("normal") or {})
    pipeline_pass = multitier_row.get("all_variants_verified") is True
    execution_root = canonical_root / "normal" / slug(incarnation) / "EXECUTION"
    surface = scan_customer_surface(
        execution_root,
        gate=dict(contract.get("artifact_gate") or {}),
        policy=policy,
        terminal_artifact_kind=str(normal.get("terminal_artifact_kind") or ""),
    )
    if not pipeline_pass:
        status = REFUSE_PIPELINE
    elif surface["state"] != "PASS":
        status = REFUSE_SURFACE
    else:
        status = READY
    return {
        "surface_id": incarnation,
        "surface_name": incarnation,
        "surface_origin": "canonical_53",
        "suite": source.get("suite"),
        "primary_family": source.get("primary_family"),
        "source_maturity": source.get("source_maturity"),
        "execution_truth_class": source.get("execution_truth_class"),
        "surface_policy_id": policy.get("policy_id"),
        "surface_label": policy.get("surface_label"),
        "terminal_artifact_kind": normal.get("terminal_artifact_kind"),
        "pipeline_state": "PASS" if pipeline_pass else "REFUSE",
        "pipeline_verified_variants": int(multitier_row.get("verified_count") or 0),
        "customer_surface_gate": surface,
        "engineering_surface_status": status,
        "human_buyer_review": "PENDING" if status == READY else "NOT_ELIGIBLE",
        "buyer_review_dimensions": list(policy.get("buyer_review_dimensions") or []),
        "customer_grade_claimed": False,
        "commercial_validation": "UNPROVED",
        "authority_created": False,
        "external_effects": False,
    }


def evaluate_studio_primary_surface(
    *,
    studio_id: str,
    product_grade_row: dict[str, Any],
    contract: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    studio_policy = dict((contract.get("studio_policies") or {}).get(studio_id) or {})
    primary_raw = str(product_grade_row.get("primary_artifact") or "")
    primary = Path(primary_raw)
    if primary_raw and not primary.is_absolute():
        primary = (root / primary).resolve()
    pg_pass = product_grade_row.get("status") == "PRODUCT_GRADE_VERIFIED"
    required_suffixes = [str(value).casefold() for value in studio_policy.get("required_primary_suffixes") or []]
    general_policy = {
        "policy_id": f"studio_{studio_id}",
        "surface_label": studio_policy.get("surface_label") or "Studio customer artifact",
        "preferred_suffixes": required_suffixes,
        "buyer_review_dimensions": ["buyer-job fidelity", "correctness and trust", "edit burden", "professional presentation", "would use"],
    }
    surface = scan_customer_surface(
        primary,
        gate=dict(contract.get("artifact_gate") or {}),
        policy=general_policy,
        terminal_artifact_kind=str(studio_policy.get("surface_label") or studio_id),
    ) if primary_raw else {"state": "REFUSE", "selected": [], "candidate_count": 0, "surface_root": primary_raw}
    suffix_pass = any(row.get("suffix") in required_suffixes for row in surface.get("selected") or []) if required_suffixes else surface.get("state") == "PASS"
    if not pg_pass:
        status = REFUSE_PIPELINE
    elif surface.get("state") != "PASS" or not suffix_pass:
        status = REFUSE_SURFACE
    else:
        status = READY
    return {
        "surface_id": studio_id,
        "surface_name": studio_policy.get("name") or studio_id,
        "surface_origin": "studio_product_grade",
        "surface_policy_id": general_policy["policy_id"],
        "surface_label": general_policy["surface_label"],
        "product_grade_status": product_grade_row.get("status"),
        "product_grade_score": product_grade_row.get("score"),
        "customer_surface_gate": surface,
        "required_primary_suffixes": required_suffixes,
        "required_primary_suffix_present": suffix_pass,
        "engineering_surface_status": status,
        "human_buyer_review": "PENDING" if status == READY else "NOT_ELIGIBLE",
        "buyer_review_dimensions": general_policy["buyer_review_dimensions"],
        "customer_grade_claimed": False,
        "commercial_validation": "UNPROVED",
        "authority_created": False,
        "external_effects": False,
    }


def evaluate_site_surface(
    *,
    site_root: Path,
    production_summary: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    studio_id = "site_studio"
    studio_policy = dict((contract.get("studio_policies") or {}).get(studio_id) or {})
    index = site_root / "index.html"
    general_policy = {
        "policy_id": "studio_site_studio",
        "surface_label": "customer website",
        "preferred_suffixes": [".html"],
    }
    surface = scan_customer_surface(index, gate=dict(contract.get("artifact_gate") or {}), policy=general_policy, terminal_artifact_kind="customer website")
    pack_state = str(production_summary.get("customer_visual_pack_state") or production_summary.get("customer_visual_pack") or "")
    pack_required = bool(studio_policy.get("requires_customer_visual_pack"))
    pack_pass = (pack_state == "READY_NEEDS_YOU") if pack_required else True
    compositor_pass = (
        production_summary.get("format_core_visual_compositor") == "PASS"
        and production_summary.get("visual_projection_authority") == "DIO_FORMAT_CORE"
        and production_summary.get("role_geometry_selection") == "REFUSE"
        and production_summary.get("role_material_selection") == "REFUSE"
        and production_summary.get("remote_runtime_asset_fetch") == "REFUSE"
    )
    status = READY if surface["state"] == "PASS" and pack_pass and compositor_pass else REFUSE_SURFACE
    return {
        "surface_id": studio_id,
        "surface_name": studio_policy.get("name") or "Site Studio",
        "surface_origin": "site_format_core_customer_pack",
        "surface_policy_id": "studio_site_studio",
        "surface_label": "customer website",
        "customer_surface_gate": surface,
        "customer_visual_pack_state": pack_state or "MISSING",
        "customer_visual_pack_pass": pack_pass,
        "format_core_customer_composition_pass": compositor_pass,
        "mixed_media_scene_count": production_summary.get("mixed_media_scene_count"),
        "material_kind_counts": production_summary.get("material_kind_counts"),
        "engineering_surface_status": status,
        "human_buyer_review": "PENDING" if status == READY else "NOT_ELIGIBLE",
        "buyer_review_dimensions": ["brand credibility", "visual quality", "buyer-job fidelity", "professional presentation", "would hire/buy"],
        "customer_grade_claimed": False,
        "commercial_validation": "UNPROVED",
        "authority_created": False,
        "external_effects": False,
    }


def _copy_review_artifacts(rows: list[dict[str, Any]], review_root: Path, max_bytes: int) -> list[dict[str, Any]]:
    review_root.mkdir(parents=True, exist_ok=True)
    packaged: list[dict[str, Any]] = []
    for row in rows:
        product_dir = review_root / slug(str(row.get("surface_name") or row.get("surface_id") or "surface"))
        selected = list((row.get("customer_surface_gate") or {}).get("selected") or [])
        assets: list[dict[str, Any]] = []
        for index, candidate in enumerate(selected, 1):
            source = Path(str(candidate.get("path") or ""))
            if not source.is_file() or source.stat().st_size > max_bytes:
                continue
            product_dir.mkdir(parents=True, exist_ok=True)
            destination = product_dir / f"{index:02d}-{source.name}"
            shutil.copy2(source, destination)
            assets.append(
                {
                    "source": str(source),
                    "review_path": str(destination.relative_to(review_root.parent)),
                    "suffix": destination.suffix.casefold(),
                    "bytes": destination.stat().st_size,
                    "sha256": sha256_file(destination),
                }
            )
        packaged.append({"surface_id": row.get("surface_id"), "surface_name": row.get("surface_name"), "assets": assets})
    return packaged


def build_review_portal(rows: list[dict[str, Any]], output_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    review_root = output_dir / "review_artifacts"
    max_bytes = int((contract.get("artifact_gate") or {}).get("max_review_copy_bytes") or 25 * 1024 * 1024)
    packaged = _copy_review_artifacts(rows, review_root, max_bytes)
    packaged_by_id = {str(row["surface_id"]): row for row in packaged}

    cards: list[str] = []
    for row in rows:
        surface_id = str(row.get("surface_id") or "")
        status = str(row.get("engineering_surface_status") or "UNKNOWN")
        assets = list((packaged_by_id.get(surface_id) or {}).get("assets") or [])
        previews: list[str] = []
        for asset in assets:
            href = html.escape(str(asset["review_path"]).replace("\\", "/"), quote=True)
            suffix = str(asset.get("suffix") or "")
            label = html.escape(Path(str(asset["review_path"])).name)
            if suffix in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
                previews.append(f'<a class="asset image" href="{href}" target="_blank"><img src="{href}" alt="{label}"><span>{label}</span></a>')
            elif suffix in {".html", ".htm", ".pdf"}:
                previews.append(f'<a class="asset frame" href="{href}" target="_blank"><iframe src="{href}" loading="lazy" title="{label}"></iframe><span>{label}</span></a>')
            elif suffix in {".mp4", ".webm"}:
                previews.append(f'<a class="asset video" href="{href}" target="_blank"><video src="{href}" controls preload="metadata"></video><span>{label}</span></a>')
            else:
                previews.append(f'<a class="asset file" href="{href}" target="_blank"><strong>Open customer artifact</strong><span>{label}</span></a>')
        dimensions = " · ".join(html.escape(str(value)) for value in row.get("buyer_review_dimensions") or [])
        cards.append(
            '<section class="card">'
            f'<div class="meta"><span>{html.escape(str(row.get("surface_origin") or ""))}</span><span>{html.escape(str(row.get("surface_label") or ""))}</span></div>'
            f'<h2>{html.escape(str(row.get("surface_name") or surface_id))}</h2>'
            f'<div class="status {"ready" if status == READY else "refuse"}">{html.escape(status)}</div>'
            f'<p class="rubric"><b>Blind buyer review:</b> {dimensions or "buyer-job fidelity · professional presentation · would use"}</p>'
            f'<div class="assets">{"".join(previews) if previews else "<p class=empty>No eligible buyer artifact packaged.</p>"}</div>'
            '</section>'
        )

    ready_count = sum(row.get("engineering_surface_status") == READY for row in rows)
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DIO Portfolio Customer Surface Review</title>
<style>
:root{{--bg:#071014;--panel:#0e1920;--line:#25343c;--ink:#f5f7f5;--muted:#9db0b8;--accent:#54d6d0;--warn:#ff765e}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,sans-serif}}header{{max-width:1500px;margin:auto;padding:64px 32px 34px}}header b{{color:var(--accent);letter-spacing:.14em;text-transform:uppercase;font-size:.75rem}}h1{{font-size:clamp(2.5rem,6vw,5.5rem);line-height:.94;margin:.5rem 0 1rem;max-width:1000px}}header p{{max-width:850px;color:var(--muted);font-size:1.05rem}}.count{{display:inline-block;margin-top:16px;padding:8px 12px;border:1px solid var(--line)}}main{{max-width:1500px;margin:auto;padding:0 32px 80px;display:grid;gap:28px}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:26px}}.meta{{display:flex;gap:12px;flex-wrap:wrap;color:var(--accent);font-size:.72rem;text-transform:uppercase;letter-spacing:.12em}}h2{{font-size:2rem;margin:.7rem 0}}.status{{display:inline-block;padding:7px 10px;border-left:4px solid var(--warn);background:#ff765e12;font-weight:800;font-size:.78rem}}.status.ready{{border-color:var(--accent);background:#54d6d012}}.rubric{{color:var(--muted)}}.assets{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;margin-top:20px}}.asset{{display:flex;flex-direction:column;min-height:180px;border:1px solid var(--line);background:#081116;color:var(--ink);text-decoration:none;overflow:hidden;border-radius:12px}}.asset img,.asset iframe,.asset video{{width:100%;height:280px;object-fit:contain;border:0;background:white}}.asset span{{padding:10px 12px;color:var(--muted);font-size:.78rem;overflow-wrap:anywhere}}.asset.file{{justify-content:center;align-items:center;padding:32px;text-align:center}}.empty{{color:var(--warn)}}footer{{max-width:1500px;margin:auto;padding:0 32px 70px;color:var(--muted)}}
</style></head><body>
<header><b>DIO · Blind buyer review surface</b><h1>Would you actually hand this to the customer?</h1><p>This portal shows copies of the strongest buyer-facing artifacts emitted by the real governed product routes. Automated readiness is not a customer-grade verdict. Review the artifacts themselves.</p><div class="count">{ready_count}/{len(rows)} engineering-ready for blind buyer review</div></header>
<main>{''.join(cards)}</main>
<footer>Human release remains NEEDS_YOU · automatic publication REFUSE · commercial validation UNPROVED.</footer>
</body></html>'''
    portal_path = output_dir / "CUSTOMER_SURFACE_REVIEW_PORTAL.html"
    portal_path.write_text(document, encoding="utf-8")
    receipt = {
        "schema": PORTAL_SCHEMA,
        "portal": str(portal_path),
        "surface_count": len(rows),
        "engineering_ready_count": ready_count,
        "packaged": packaged,
        "human_buyer_review_required": True,
        "customer_grade_claimed": False,
        "commercial_validation": "UNPROVED",
    }
    receipt["portal_fingerprint"] = content_hash(receipt)
    return receipt


__all__ = [
    "CONTRACT_PATH",
    "CROSSWALK_PATH",
    "READY",
    "REFUSE_PIPELINE",
    "REFUSE_SURFACE",
    "build_review_portal",
    "content_hash",
    "evaluate_canonical_surface",
    "evaluate_site_surface",
    "evaluate_studio_primary_surface",
    "inspect_artifact",
    "load_contract",
    "load_crosswalk",
    "resolve_family_policy",
    "resolve_wave",
    "scan_customer_surface",
    "slug",
]
