from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from pathlib import Path
from typing import Any

from adapters.document_studio.art_direction import build_art_direction
from adapters.format_core.site_visual_compositor import render_site_visual_assets
from products.portfolio_customer_surface import load_crosswalk
from products.professional_evidence_corpus import CASES


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "portfolio_suite_studio.json"

MODEL_SCHEMA = "dio.portfolio.suite_surface_model.v1"
RECEIPT_SCHEMA = "dio.portfolio.suite_site_receipt.v1"
EXECUTION_SCHEMA = "dio.professional_evidence.multitier_53_receipt.v1"
READINESS_SCHEMA = "dio.portfolio.production_readiness_receipt.v1"
CUSTOMER_SURFACE_SCHEMA = "dio.portfolio.customer_surface_gauntlet_receipt.v1"

EXECUTION_TOKEN = "DIO_PROFESSIONAL_EVIDENCE_53_X3_VERIFIED"
BUYER_READY = "BUYER_PRODUCTION_READY_BOUNDED"
INTERNAL_READY = "INTERNAL_PRODUCTION_READY"
NEEDS_SELLABILITY = "NEEDS_SELLABILITY_GRADE"
REFUSE = "REFUSE_PRODUCTION_READINESS"

SUITE_READY = "SUITE_PRODUCTION_READY_BOUNDED"
SUITE_PENDING = "ENGINEERING_VERIFIED_NEEDS_SELLABILITY"
SUITE_REFUSE = "REFUSE_SUITE_PRODUCTION"


class PortfolioSuiteStudioError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "surface"


def _clean(value: Any, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text if limit is None else text[:limit].rstrip()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortfolioSuiteStudioError(f"unable to read JSON evidence {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PortfolioSuiteStudioError(f"expected JSON object: {path}")
    return value


def load_contract(path: Path | None = None) -> dict[str, Any]:
    target = Path(path or CONTRACT_PATH)
    value = load_json(target)
    if value.get("schema") != "dio.portfolio.suite_studio_contract.v1":
        raise PortfolioSuiteStudioError("invalid Portfolio Suite Studio contract schema")
    suites = list(value.get("suites") or [])
    if len(suites) != int(value.get("suite_count") or 0):
        raise PortfolioSuiteStudioError("Portfolio Suite Studio contract suite count mismatch")
    names = [str(row.get("name") or "") for row in suites]
    if len(set(names)) != len(names) or any(not name for name in names):
        raise PortfolioSuiteStudioError("Portfolio Suite Studio suite names must be unique and non-empty")
    return value


def _verify_fingerprint(receipt: dict[str, Any], key: str) -> bool:
    observed = str(receipt.get(key) or "")
    if not observed:
        return False
    basis = dict(receipt)
    basis.pop(key, None)
    return observed == _fingerprint(basis)


def _validate_execution(receipt: dict[str, Any], crosswalk: dict[str, dict[str, str]]) -> None:
    if receipt.get("schema") != EXECUTION_SCHEMA:
        raise PortfolioSuiteStudioError("canonical x3 execution receipt schema mismatch")
    checks = {
        "acceptance_token": receipt.get("acceptance_token") == EXECUTION_TOKEN,
        "all_53_x3_verified": receipt.get("all_53_x3_verified") is True,
        "canonical_incarnation_count": int(receipt.get("canonical_incarnation_count") or 0) == 53,
        "journey_count": int(receipt.get("journey_count") or 0) == 159,
        "verified_journey_count": int(receipt.get("verified_journey_count") or 0) == 159,
        "refused_journey_count": int(receipt.get("refused_journey_count") or 0) == 0,
        "failure_count": int(receipt.get("failure_count") or 0) == 0,
        "failures_empty": not list(receipt.get("failures") or []),
        "authority_created": receipt.get("authority_created") is False,
        "external_effects": receipt.get("external_effects") is False,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise PortfolioSuiteStudioError("canonical x3 execution proof refused: " + ", ".join(failed))

    by_incarnation = dict(receipt.get("by_incarnation") or {})
    if set(by_incarnation) != set(crosswalk):
        missing = sorted(set(crosswalk) - set(by_incarnation))
        extra = sorted(set(by_incarnation) - set(crosswalk))
        raise PortfolioSuiteStudioError(f"execution identity mismatch; missing={missing}, extra={extra}")

    for incarnation, row in by_incarnation.items():
        variants = dict((row or {}).get("variants") or {})
        if set(variants) != {"normal", "messy", "adversarial"}:
            raise PortfolioSuiteStudioError(f"{incarnation} does not expose exactly normal/messy/adversarial execution")
        if row.get("all_variants_verified") is not True or int(row.get("verified_count") or 0) != 3:
            raise PortfolioSuiteStudioError(f"{incarnation} is not fully verified across x3 execution")
        for variant, result in variants.items():
            if result.get("passed") is not True or result.get("status") != "PASS_FULL_PIPELINE":
                raise PortfolioSuiteStudioError(f"{incarnation}::{variant} is not PASS_FULL_PIPELINE")
            if result.get("authority_created") is not False or result.get("external_effects") is not False:
                raise PortfolioSuiteStudioError(f"{incarnation}::{variant} violates authority/effects boundary")


def _validate_readiness(receipt: dict[str, Any], crosswalk: dict[str, dict[str, str]]) -> None:
    if receipt.get("schema") != READINESS_SCHEMA:
        raise PortfolioSuiteStudioError("production-readiness receipt schema mismatch")
    if int(receipt.get("surface_count") or 0) != 57:
        raise PortfolioSuiteStudioError("production-readiness receipt must contain 57 surfaces")
    if not _verify_fingerprint(receipt, "receipt_fingerprint"):
        raise PortfolioSuiteStudioError("production-readiness receipt fingerprint mismatch")
    if receipt.get("authority_created") is not False or receipt.get("external_effects") is not False:
        raise PortfolioSuiteStudioError("production-readiness receipt violates authority/effects boundary")
    rows = dict(receipt.get("rows") or {})
    if len(rows) != 57:
        raise PortfolioSuiteStudioError("production-readiness receipt row count mismatch")
    if not set(crosswalk).issubset(rows):
        raise PortfolioSuiteStudioError("production-readiness receipt is missing canonical products")


def _validate_customer_surface(receipt: dict[str, Any], expected_ids: set[str]) -> None:
    if receipt.get("schema") != CUSTOMER_SURFACE_SCHEMA:
        raise PortfolioSuiteStudioError("customer-surface receipt schema mismatch")
    if receipt.get("wave") != "full57" or int(receipt.get("surface_count") or 0) != 57:
        raise PortfolioSuiteStudioError("Portfolio Suite Studio requires a full57 customer-surface receipt")
    if not _verify_fingerprint(receipt, "receipt_fingerprint"):
        raise PortfolioSuiteStudioError("customer-surface receipt fingerprint mismatch")
    if receipt.get("authority_created") is not False or receipt.get("external_effects") is not False:
        raise PortfolioSuiteStudioError("customer-surface receipt violates authority/effects boundary")
    rows = {
        str(row.get("surface_id")): dict(row)
        for row in receipt.get("rows") or []
        if isinstance(row, dict) and row.get("surface_id")
    }
    if set(rows) != expected_ids:
        missing = sorted(expected_ids - set(rows))
        extra = sorted(set(rows) - expected_ids)
        raise PortfolioSuiteStudioError(f"customer-surface identity mismatch; missing={missing}, extra={extra}")


def _artifact_summary(surface: dict[str, Any]) -> list[dict[str, Any]]:
    selected = list((surface.get("customer_surface_gate") or {}).get("selected") or [])
    rows: list[dict[str, Any]] = []
    for artifact in selected:
        if not isinstance(artifact, dict):
            continue
        rows.append(
            {
                "name": str(artifact.get("name") or Path(str(artifact.get("path") or "artifact")).name),
                "suffix": str(artifact.get("suffix") or ""),
                "bytes": int(artifact.get("bytes") or 0),
                "sha256": artifact.get("sha256"),
            }
        )
    return rows


def _execution_summary(row: dict[str, Any]) -> dict[str, Any]:
    variants = dict(row.get("variants") or {})
    artifact_kinds = sorted(
        {
            str(result.get("terminal_artifact_kind") or "")
            for result in variants.values()
            if str(result.get("terminal_artifact_kind") or "")
        }
    )
    executors = sorted(
        {
            str(result.get("executor") or "")
            for result in variants.values()
            if str(result.get("executor") or "")
        }
    )
    return {
        "variant_count": len(variants),
        "verified_variant_count": sum(result.get("passed") is True for result in variants.values()),
        "terminal_artifact_kinds": artifact_kinds,
        "executors": executors,
        "vesper_first": all(result.get("vesper_web_chat_front_door_verified") is True for result in variants.values()),
        "product_consumed_quarantined_bytes": all(
            result.get("product_consumed_vesper_quarantined_bytes") is True for result in variants.values()
        ),
    }


def _pattern_tokens(product: dict[str, Any]) -> list[str]:
    return [token.strip() for token in str(product.get("source_work_patterns") or "").split(";") if token.strip()]


def _cluster_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for product in products:
        for token in _pattern_tokens(product):
            counts[token] = counts.get(token, 0) + 1
    ranked = [name for name, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))]
    if len(ranked) < 3:
        raise PortfolioSuiteStudioError("suite does not expose at least three distinct ATLAS work-pattern labels")
    labels = ranked[:3]
    clusters = [
        {"cluster_id": f"service_{index}", "label": label, "products": []}
        for index, label in enumerate(labels, 1)
    ]
    for product in products:
        tokens = set(_pattern_tokens(product))
        eligible = [cluster for cluster in clusters if cluster["label"] in tokens]
        if eligible:
            selected = min(eligible, key=lambda row: (len(row["products"]), labels.index(row["label"])))
        else:
            selected = min(clusters, key=lambda row: (len(row["products"]), labels.index(row["label"])))
        selected["products"].append(product["incarnation"])

    empty = [cluster for cluster in clusters if not cluster["products"]]
    for cluster in empty:
        donor = max(clusters, key=lambda row: len(row["products"]))
        if len(donor["products"]) <= 1:
            raise PortfolioSuiteStudioError("unable to build three non-empty suite work-pattern clusters")
        cluster["products"].append(donor["products"].pop())

    return clusters


def _suite_story(suite: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    scenes = [
        {
            "scene_id": f"{suite['suite_id']}_hook",
            "role": "site_hook",
            "semantic_focus": "problem_and_category",
            "screen_text": str(suite["name"]),
            "narration": str(suite["promise"]),
            "visual": "Open on the real professional work context for this suite, with source material and human judgement visible rather than decorative software chrome.",
        }
    ]
    for index, cluster in enumerate(suite["clusters"], 1):
        names = list(cluster["products"])
        scenes.append(
            {
                "scene_id": f"{suite['suite_id']}_service_{index}",
                "role": f"service_{index}",
                "semantic_focus": f"service_{index}",
                "screen_text": f"{cluster['label']} work",
                "narration": f"{len(names)} execution-verified products connect to the ATLAS {cluster['label']} work pattern: {', '.join(names)}.",
                "visual": f"Show tangible evidence objects and working materials associated with {cluster['label']} work. Keep the composition grounded in professional practice and avoid generic dashboard UI.",
            }
        )
    scenes.extend(
        [
            {
                "scene_id": f"{suite['suite_id']}_method",
                "role": "method",
                "semantic_focus": "method",
                "screen_text": "One governed execution law",
                "narration": "Every canonical product is routed through the same Vesper-first custody and authority boundaries before its own governed executor produces a reviewable artifact.",
                "visual": "Show the handoff from customer material to governed execution to reviewable artifact as real work objects, not a decorative node-link diagram.",
            },
            {
                "scene_id": f"{suite['suite_id']}_proof",
                "role": "proof",
                "semantic_focus": "proof",
                "screen_text": "Three conditions. Every product.",
                "narration": f"The canonical evidence receipt records {model['execution_verified_journey_count']} verified journeys with normal, messy and adversarial input conditions.",
                "visual": "Make the execution receipt and resulting review artifacts the visual protagonists, with normal, messy and adversarial evidence visibly distinct.",
            },
            {
                "scene_id": f"{suite['suite_id']}_authority",
                "role": "human_authority",
                "semantic_focus": "authority",
                "screen_text": "Authority stays human",
                "narration": str(model["claim_boundary"]),
                "visual": "Show a human reviewer actively exercising judgement over a prepared evidence artifact. Authority must be visible in the work, not buried in disclaimer text.",
            },
            {
                "scene_id": f"{suite['suite_id']}_cta",
                "role": "cta",
                "semantic_focus": "bounded_next_step",
                "screen_text": "Inspect products and proof",
                "narration": "Review the individual product jobs, evidence surfaces and current readiness states before any external release.",
                "visual": "Resolve on a calm inspectable handoff: a product artifact, its evidence trail and one clear human next action with generous negative space.",
            },
        ]
    )
    core = {
        "schema": "dio.site_studio.portfolio_suite_story.v1",
        "family_id": f"portfolio-suite:{suite['suite_id']}",
        "surface": "website",
        "title": str(suite["name"]),
        "semantic_law_hash": model["model_fingerprint"],
        "projection_hash": model["model_fingerprint"],
        "creative_direction": {
            "audience_archetype": str(suite.get("audience_archetype") or "general_professional"),
            "tone": ["credible", "evidence_bound", "professional"],
            "pacing": "progressive_scroll",
            "visual_grammar": "proof_carrying_portfolio_editorial",
            "motion_grammar": "static_site_with_governed_scene_assets",
        },
        "semantic_guardrails": {
            "commercial_validation": "UNPROVED",
            "publication": "REFUSE",
            "authority_created": False,
            "external_effects": False,
        },
        "scenes": scenes,
    }
    return {**core, "story_hash": _fingerprint(core)}


def _suite_state(products: list[dict[str, Any]]) -> str:
    statuses = {str(row.get("production_readiness_status") or "") for row in products}
    if REFUSE in statuses:
        return SUITE_REFUSE
    if NEEDS_SELLABILITY in statuses:
        return SUITE_PENDING
    permitted = {BUYER_READY, INTERNAL_READY}
    if statuses and statuses.issubset(permitted):
        return SUITE_READY
    return SUITE_REFUSE


def build_suite_model(
    *,
    execution_receipt: dict[str, Any],
    readiness_receipt: dict[str, Any],
    customer_surface_receipt: dict[str, Any],
    contract: dict[str, Any] | None = None,
    crosswalk: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    contract = dict(contract or load_contract())
    crosswalk = dict(crosswalk or load_crosswalk())

    configured_suites = [str(row["name"]) for row in contract["suites"]]
    observed_suites = {str(row.get("suite") or "") for row in crosswalk.values()}
    if observed_suites != set(configured_suites):
        raise PortfolioSuiteStudioError(
            f"ATLAS suite taxonomy differs from Suite Studio contract; observed={sorted(observed_suites)}"
        )

    if set(CASES) != set(crosswalk):
        missing = sorted(set(crosswalk) - set(CASES))
        extra = sorted(set(CASES) - set(crosswalk))
        raise PortfolioSuiteStudioError(f"professional-evidence corpus identity mismatch; missing={missing}, extra={extra}")

    readiness_rows = dict(readiness_receipt.get("rows") or {})
    studio_ids = set(readiness_rows) - set(crosswalk)
    if len(studio_ids) != 4:
        raise PortfolioSuiteStudioError(f"expected four full-grade Studios, found {sorted(studio_ids)}")
    expected_ids = set(crosswalk) | studio_ids

    _validate_execution(execution_receipt, crosswalk)
    _validate_readiness(readiness_receipt, crosswalk)
    _validate_customer_surface(customer_surface_receipt, expected_ids)

    customer_rows = {
        str(row.get("surface_id")): dict(row)
        for row in customer_surface_receipt.get("rows") or []
        if isinstance(row, dict) and row.get("surface_id")
    }
    execution_rows = dict(execution_receipt.get("by_incarnation") or {})

    products: dict[str, dict[str, Any]] = {}
    for incarnation, atlas in crosswalk.items():
        readiness = dict(readiness_rows[incarnation])
        surface = dict(customer_rows[incarnation])
        case = dict(CASES[incarnation])
        status = str(readiness.get("production_readiness_status") or "")
        if status not in {BUYER_READY, INTERNAL_READY, NEEDS_SELLABILITY, REFUSE}:
            raise PortfolioSuiteStudioError(f"{incarnation} has unknown production-readiness status {status!r}")

        products[incarnation] = {
            "incarnation": incarnation,
            "slug": _slug(incarnation),
            "suite": atlas.get("suite"),
            "primary_family": atlas.get("primary_family"),
            "source_work_patterns": atlas.get("source_work_patterns"),
            "category": readiness.get("category"),
            "buyer": case.get("buyer"),
            "organisation_archetype": case.get("organisation"),
            "buyer_job": case.get("request"),
            "buyer_context": case.get("context"),
            "exception_case": case.get("exception"),
            "prohibited_outcomes": list(case.get("prohibited_outcomes") or []),
            "execution": _execution_summary(dict(execution_rows[incarnation])),
            "surface_label": surface.get("surface_label"),
            "engineering_surface_status": surface.get("engineering_surface_status"),
            "customer_artifacts": _artifact_summary(surface),
            "sellability_status": readiness.get("sellability_status"),
            "production_readiness_status": status,
            "critical_blockers": list(readiness.get("critical_blockers") or []),
            "authority_created": False,
            "external_effects": False,
            "commercial_validation": "UNPROVED",
        }

    suites: list[dict[str, Any]] = []
    for suite_config in contract["suites"]:
        suite_name = str(suite_config["name"])
        rows = [products[name] for name in crosswalk if products[name]["suite"] == suite_name]
        if not rows:
            raise PortfolioSuiteStudioError(f"suite has no canonical products: {suite_name}")
        state = _suite_state(rows)
        suites.append(
            {
                "suite_id": suite_config["suite_id"],
                "name": suite_name,
                "eyebrow": suite_config["eyebrow"],
                "promise": suite_config["promise"],
                "audience_archetype": suite_config.get("audience_archetype") or "general_professional",
                "suite_state": state,
                "clusters": _cluster_products(rows),
                "product_count": len(rows),
                "buyer_facing_count": sum(str(row["category"]).startswith("buyer_facing") for row in rows),
                "internal_capability_count": sum(row["category"] == "internal_operating_capability" for row in rows),
                "buyer_ready_count": sum(row["production_readiness_status"] == BUYER_READY for row in rows),
                "buyer_needs_sellability_count": sum(row["production_readiness_status"] == NEEDS_SELLABILITY for row in rows),
                "internal_ready_count": sum(row["production_readiness_status"] == INTERNAL_READY for row in rows),
                "refuse_count": sum(row["production_readiness_status"] == REFUSE for row in rows),
                "products": rows,
            }
        )

    studios = []
    for studio_id in sorted(studio_ids):
        readiness = dict(readiness_rows[studio_id])
        surface = dict(customer_rows[studio_id])
        studios.append(
            {
                "studio_id": studio_id,
                "surface_name": surface.get("surface_name") or studio_id,
                "surface_label": surface.get("surface_label"),
                "production_readiness_status": readiness.get("production_readiness_status"),
                "sellability_status": readiness.get("sellability_status"),
                "product_grade_status": readiness.get("product_grade_status"),
                "product_grade_score": readiness.get("product_grade_score"),
                "customer_artifacts": _artifact_summary(surface),
                "critical_blockers": list(readiness.get("critical_blockers") or []),
                "authority_created": False,
                "external_effects": False,
                "commercial_validation": "UNPROVED",
            }
        )

    model = {
        "schema": MODEL_SCHEMA,
        "suite_count": len(suites),
        "canonical_product_count": len(products),
        "all_canonical_execution_verified": True,
        "execution_journey_count": int(execution_receipt.get("journey_count") or 0),
        "execution_verified_journey_count": int(execution_receipt.get("verified_journey_count") or 0),
        "portfolio_production_ready": readiness_receipt.get("portfolio_production_ready") is True,
        "buyer_production_ready_count": int(readiness_receipt.get("buyer_production_ready_count") or 0),
        "buyer_needs_sellability_grade_count": int(readiness_receipt.get("buyer_needs_sellability_grade_count") or 0),
        "buyer_refuse_count": int(readiness_receipt.get("buyer_refuse_count") or 0),
        "internal_production_ready_count": int(readiness_receipt.get("internal_production_ready_count") or 0),
        "internal_refuse_count": int(readiness_receipt.get("internal_refuse_count") or 0),
        "suites": suites,
        "studios": studios,
        "status_copy": dict(contract.get("status_copy") or {}),
        "suite_status_copy": dict(contract.get("suite_status_copy") or {}),
        "input_evidence": {
            "execution_receipt_fingerprint": _fingerprint(execution_receipt),
            "customer_surface_receipt_fingerprint": customer_surface_receipt.get("receipt_fingerprint"),
            "production_readiness_receipt_fingerprint": readiness_receipt.get("receipt_fingerprint"),
            "atlas_crosswalk_fingerprint": _fingerprint(crosswalk),
            "professional_evidence_corpus_fingerprint": _fingerprint(CASES),
        },
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": str(readiness_receipt.get("commercial_validation") or "UNPROVED"),
        "publication": str(contract.get("publication") or "REFUSE"),
        "human_release": str(contract.get("human_release") or "NEEDS_YOU"),
        "claim_boundary": contract.get("claim_boundary"),
    }
    model["model_fingerprint"] = _fingerprint(model)
    return model


def _status_class(status: str) -> str:
    if status in {BUYER_READY, INTERNAL_READY, SUITE_READY}:
        return "ready"
    if status in {NEEDS_SELLABILITY, SUITE_PENDING}:
        return "pending"
    return "refuse"


def _status_text(model: dict[str, Any], status: str, *, suite: bool = False) -> str:
    key = "suite_status_copy" if suite else "status_copy"
    return str((model.get(key) or {}).get(status) or status.replace("_", " ").title())


def _artifact_links(
    *,
    product: dict[str, Any],
    source_surface: dict[str, Any],
    artifact_root: Path,
    customer_root: Path,
    bundle_artifacts: bool,
) -> list[dict[str, Any]]:
    selected = list((source_surface.get("customer_surface_gate") or {}).get("selected") or [])
    linked: list[dict[str, Any]] = []
    for index, artifact in enumerate(selected, 1):
        if not isinstance(artifact, dict):
            continue
        source_raw = str(artifact.get("path") or "")
        name = str(artifact.get("name") or Path(source_raw or f"artifact-{index}").name)
        row = {
            "name": name,
            "bytes": int(artifact.get("bytes") or 0),
            "sha256": artifact.get("sha256"),
            "href": None,
        }
        if bundle_artifacts:
            source = Path(source_raw)
            if not source.is_file():
                raise PortfolioSuiteStudioError(f"customer artifact is missing during suite bundling: {source}")
            expected_hash = str(artifact.get("sha256") or "")
            observed_hash = _sha256(source)
            if expected_hash and observed_hash != expected_hash:
                raise PortfolioSuiteStudioError(f"customer artifact hash changed before suite bundling: {source}")
            target_dir = artifact_root / str(product["slug"])
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / name
            if target.exists():
                target = target_dir / f"{index:02d}-{name}"
            shutil.copy2(source, target)
            row["href"] = "../../" + str(target.relative_to(customer_root))
        linked.append(row)
    return linked


def _render_product_card(model: dict[str, Any], product: dict[str, Any], artifacts: list[dict[str, Any]]) -> str:
    status = str(product["production_readiness_status"])
    artifact_html = ""
    if artifacts:
        bits = []
        for row in artifacts:
            label = html.escape(str(row["name"]))
            if row.get("href"):
                bits.append(f'<a href="{html.escape(str(row["href"]))}">{label}</a>')
            else:
                bits.append(f"<span>{label}</span>")
        artifact_html = '<div class="artifacts"><strong>Review artifacts</strong>' + "".join(bits) + "</div>"
    blockers = list(product.get("critical_blockers") or [])
    blocker_html = ""
    if blockers:
        blocker_html = '<div class="blockers"><strong>Remaining gate</strong> ' + html.escape(", ".join(map(str, blockers))) + "</div>"
    terminal = ", ".join(product["execution"].get("terminal_artifact_kinds") or []) or "governed customer artifact"
    return f'''
<article class="product-card">
  <div class="product-topline">
    <span class="family">{html.escape(_clean(product.get("primary_family"), 80))}</span>
    <span class="pill {_status_class(status)}">{html.escape(_status_text(model, status))}</span>
  </div>
  <h3>{html.escape(str(product["incarnation"]))}</h3>
  <p class="buyer"><strong>For:</strong> {html.escape(_clean(product.get("buyer"), 150))}</p>
  <p>{html.escape(_clean(product.get("buyer_job"), 520))}</p>
  <div class="proof-line"><strong>Execution:</strong> 3/3 normal · messy · adversarial · {html.escape(terminal)}</div>
  {artifact_html}
  {blocker_html}
</article>'''


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def render_suite_site(
    *,
    model: dict[str, Any],
    execution_receipt: dict[str, Any],
    customer_surface_receipt: dict[str, Any],
    readiness_receipt: dict[str, Any],
    output_dir: Path,
    contract: dict[str, Any] | None = None,
    bundle_artifacts: bool = True,
    render_visuals: bool = True,
) -> dict[str, Any]:
    contract = dict(contract or load_contract())
    output_dir = Path(output_dir).resolve()
    customer_root = output_dir / "customer" / "PORTFOLIO_SUITE_SITE"
    proof_root = output_dir / "proof"
    evidence_root = proof_root / "input_evidence"
    artifact_root = customer_root / "artifacts"
    visual_root = customer_root / "assets" / "svg"
    suites_root = customer_root / "suites"
    customer_root.mkdir(parents=True, exist_ok=True)
    proof_root.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)
    suites_root.mkdir(parents=True, exist_ok=True)

    evidence_snapshots = {
        "PROFESSIONAL_EVIDENCE_53_X3_RECEIPT.json": execution_receipt,
        "PORTFOLIO_CUSTOMER_SURFACE_GAUNTLET_RECEIPT.json": customer_surface_receipt,
        "PORTFOLIO_PRODUCTION_READINESS_RECEIPT.json": readiness_receipt,
    }
    evidence_rows = []
    for name, payload in evidence_snapshots.items():
        path = evidence_root / name
        _write_json(path, payload)
        evidence_rows.append(
            {"path": str(path.relative_to(output_dir)), "sha256": _sha256(path), "bytes": path.stat().st_size}
        )

    customer_rows = {
        str(row.get("surface_id")): dict(row)
        for row in customer_surface_receipt.get("rows") or []
        if isinstance(row, dict) and row.get("surface_id")
    }

    css = r'''
:root{color-scheme:dark;--bg:#071014;--panel:#0d171d;--ink:#eef6f5;--muted:#9eb0b4;--line:#203139;--accent:#5fd1d8;--ok:#8ee7b1;--warn:#f1d48a;--bad:#f5a0a0}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 20% 0,#10262c 0,#071014 35rem);color:var(--ink);font:16px/1.55 Inter,ui-sans-serif,system-ui,sans-serif}
a{color:inherit}.shell{width:min(1180px,calc(100% - 32px));margin:auto}.hero{padding:72px 0 42px;border-bottom:1px solid var(--line)}
.eyebrow{color:var(--accent);font-weight:800;text-transform:uppercase;letter-spacing:.12em;font-size:.72rem}h1{font-size:clamp(2.3rem,6vw,5rem);line-height:.98;margin:.18em 0 .35em;max-width:920px}
h2{font-size:clamp(1.6rem,3vw,2.6rem);margin:0 0 .35em}h3{font-size:1.2rem;margin:.55rem 0}.lede{max-width:820px;color:#c5d2d4;font-size:1.1rem}
.evidence-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin-top:30px}.evidence-strip div{background:#0a1419;padding:18px}.evidence-strip strong{display:block;font-size:1.55rem}
.suite-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:18px;padding:42px 0}.suite-card,.product-card,.studio-card{background:linear-gradient(180deg,#0f1a20,#0a1318);border:1px solid var(--line);border-radius:16px;padding:22px}
.suite-card{display:flex;flex-direction:column;min-height:270px}.suite-card p{color:#b7c6c8}.suite-card .open{margin-top:auto;font-weight:800;color:var(--accent);text-decoration:none}
.pill{display:inline-flex;padding:6px 9px;border-radius:999px;font-size:.68rem;font-weight:900;letter-spacing:.05em;text-transform:uppercase;border:1px solid}.pill.ready{color:var(--ok);border-color:#8ee7b155;background:#8ee7b10d}.pill.pending{color:var(--warn);border-color:#f1d48a55;background:#f1d48a0d}.pill.refuse{color:var(--bad);border-color:#f5a0a055;background:#f5a0a00d}
.meta{display:flex;gap:10px;flex-wrap:wrap;color:var(--muted);font-size:.85rem}.section{padding:48px 0}.product-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}.product-topline{display:flex;justify-content:space-between;gap:12px;align-items:start}.family{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.08em}
.buyer,.proof-line,.artifacts,.blockers{font-size:.88rem;color:#bdcacc}.proof-line,.artifacts,.blockers{border-top:1px solid var(--line);padding-top:11px;margin-top:12px}.artifacts{display:flex;gap:8px;flex-wrap:wrap}.artifacts strong{width:100%}.artifacts a,.artifacts span{font-size:.76rem;background:#13242b;padding:5px 8px;border-radius:7px;text-decoration:none}
.studios{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.boundary{margin:50px 0;padding:22px;border:1px solid #37515d;border-radius:14px;color:#b9c9cc;background:#0b171d}
.back{display:inline-block;margin:25px 0;text-decoration:none;color:var(--accent);font-weight:800}.suite-visual{margin:28px 0;border:1px solid var(--line);border-radius:16px;overflow:hidden;background:#081217}.suite-visual img{display:block;width:100%;height:auto}.visual-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:34px 0}.cluster{padding:34px 0;border-top:1px solid var(--line)}
footer{border-top:1px solid var(--line);padding:30px 0 50px;color:var(--muted);font-size:.82rem}
@media(max-width:800px){.suite-grid,.product-grid,.visual-grid{grid-template-columns:1fr}.studios{grid-template-columns:1fr 1fr}.evidence-strip{grid-template-columns:1fr 1fr}}
@media(max-width:520px){.studios,.evidence-strip{grid-template-columns:1fr}.product-topline{display:block}.pill{margin-top:8px}}
'''
    (customer_root / "styles.css").write_text(css.strip() + "\n", encoding="utf-8")

    suite_cards = []
    page_rows = []
    visual_receipts = []

    for suite in model["suites"]:
        suite_id = str(suite["suite_id"])
        suite_dir = suites_root / suite_id
        suite_dir.mkdir(parents=True, exist_ok=True)

        assets_by_role: dict[str, dict[str, Any]] = {}
        if render_visuals:
            story = _suite_story(suite, model)
            art = build_art_direction(story)
            suite_visual_dir = visual_root / suite_id
            compositor = render_site_visual_assets(
                story=story,
                art=art,
                output_dir=suite_visual_dir,
                material_root=ROOT,
            )
            assets_by_role = {str(row["role"]): dict(row) for row in compositor.get("assets") or []}
            if set(assets_by_role) != {
                "site_hook", "service_1", "service_2", "service_3",
                "method", "proof", "human_authority", "cta",
            }:
                raise PortfolioSuiteStudioError(f"Format Core suite visual role mismatch: {suite['name']}")
            story_path = proof_root / "site_studio" / suite_id / "SITE_STORY_ARCHITECTURE.json"
            art_path = proof_root / "site_studio" / suite_id / "DOCUMENT_STUDIO_SITE_ART_DIRECTION.json"
            compositor_path = proof_root / "site_studio" / suite_id / "FORMAT_CORE_SITE_VISUAL_COMPOSITOR_RECEIPT.json"
            _write_json(story_path, story)
            _write_json(art_path, art)
            _write_json(compositor_path, compositor)
            visual_receipts.append(
                {
                    "suite": suite["name"],
                    "story": str(story_path.relative_to(output_dir)),
                    "art_direction": str(art_path.relative_to(output_dir)),
                    "compositor_receipt": str(compositor_path.relative_to(output_dir)),
                    "compositor_fingerprint": compositor.get("compositor_fingerprint"),
                    "scene_count": compositor.get("scene_count"),
                    "format_core_visual_composition": compositor.get("format_core_visual_composition"),
                    "site_semantic_authority": compositor.get("site_semantic_authority"),
                    "geometry_authority": compositor.get("geometry_authority"),
                    "publication": compositor.get("publication"),
                }
            )

        product_by_name = {str(row["incarnation"]): row for row in suite["products"]}
        cluster_sections = []
        for index, cluster in enumerate(suite["clusters"], 1):
            product_cards = []
            for name in cluster["products"]:
                product = product_by_name[str(name)]
                source_surface = customer_rows[str(product["incarnation"])]
                artifacts = _artifact_links(
                    product=product,
                    source_surface=source_surface,
                    artifact_root=artifact_root,
                    customer_root=customer_root,
                    bundle_artifacts=bundle_artifacts,
                )
                product_cards.append(_render_product_card(model, product, artifacts))
            visual_html = ""
            role = f"service_{index}"
            if role in assets_by_role:
                asset = assets_by_role[role]
                visual_html = (
                    f'<figure class="suite-visual"><img src="../../assets/svg/{html.escape(suite_id)}/'
                    f'{html.escape(str(asset["path"]))}" alt="{html.escape(str(asset.get("alt_text") or cluster["label"]))}"></figure>'
                )
            cluster_sections.append(
                f'''<section class="cluster"><div class="eyebrow">ATLAS work cluster</div>
<h2>{html.escape(str(cluster["label"]))}</h2>{visual_html}
<div class="product-grid">{"".join(product_cards)}</div></section>'''
            )

        hero_visual = ""
        if "site_hook" in assets_by_role:
            asset = assets_by_role["site_hook"]
            hero_visual = (
                f'<figure class="suite-visual"><img src="../../assets/svg/{html.escape(suite_id)}/'
                f'{html.escape(str(asset["path"]))}" alt="{html.escape(str(asset.get("alt_text") or suite["name"]))}"></figure>'
            )

        closing_visuals = []
        for role in ("method", "proof", "human_authority", "cta"):
            if role not in assets_by_role:
                continue
            asset = assets_by_role[role]
            closing_visuals.append(
                f'<figure class="suite-visual"><img src="../../assets/svg/{html.escape(suite_id)}/'
                f'{html.escape(str(asset["path"]))}" alt="{html.escape(str(asset.get("alt_text") or role))}"></figure>'
            )

        suite_status = str(suite["suite_state"])
        page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(str(suite["name"]))} · DIO Workflows</title><link rel="stylesheet" href="../../styles.css"></head>
<body><main class="shell">
<a class="back" href="../../index.html">← All suites</a>
<section class="hero">
<div class="eyebrow">{html.escape(str(suite["eyebrow"]))}</div>
<h1>{html.escape(str(suite["name"]))}</h1>
<p class="lede">{html.escape(str(suite["promise"]))}</p>
<span class="pill {_status_class(suite_status)}">{html.escape(_status_text(model, suite_status, suite=True))}</span>
<div class="meta"><span>{suite["product_count"]} canonical products</span><span>{suite["buyer_ready_count"]} buyer-ready</span><span>{suite["buyer_needs_sellability_count"]} sellability pending</span><span>{suite["internal_ready_count"]} internal-ready</span></div>
{hero_visual}
</section>
{"".join(cluster_sections)}
<section class="section"><div class="eyebrow">Method, proof and authority</div><div class="visual-grid">{"".join(closing_visuals)}</div></section>
<div class="boundary"><strong>Evidence boundary.</strong> {html.escape(str(model["claim_boundary"]))}</div>
</main><footer><div class="shell">DIO Site Studio · portfolio suite mode · Format Core visual geometry · automatic publication REFUSE</div></footer></body></html>'''
        index_path = suite_dir / "index.html"
        index_path.write_text(page, encoding="utf-8")
        page_rows.append({"path": str(index_path.relative_to(customer_root)), "sha256": _sha256(index_path)})
        suite_cards.append(
            f'''<article class="suite-card"><div class="eyebrow">{html.escape(str(suite["eyebrow"]))}</div>
<h2>{html.escape(str(suite["name"]))}</h2><p>{html.escape(str(suite["promise"]))}</p>
<div class="meta"><span>{suite["product_count"]} products</span><span>{suite["buyer_needs_sellability_count"]} sellability pending</span><span>{suite["internal_ready_count"]} internal-ready</span></div>
<p><span class="pill {_status_class(suite_status)}">{html.escape(_status_text(model, suite_status, suite=True))}</span></p>
<a class="open" href="suites/{html.escape(suite_id)}/index.html">Open suite →</a></article>'''
        )

    studio_cards = []
    for studio in model.get("studios") or []:
        status = str(studio.get("production_readiness_status") or REFUSE)
        studio_cards.append(
            f'''<article class="studio-card"><div class="eyebrow">Full-grade Studio</div><h3>{html.escape(str(studio["surface_name"]))}</h3>
<span class="pill {_status_class(status)}">{html.escape(_status_text(model, status))}</span>
<p class="meta">{html.escape(_clean(studio.get("surface_label"), 140))}</p></article>'''
        )

    index = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DIO Production Suites</title><link rel="stylesheet" href="styles.css"></head>
<body><main class="shell">
<section class="hero"><div class="eyebrow">DIO Workflows · evidence-built portfolio</div>
<h1>Six suites. Fifty-three execution-verified products. One truth rail.</h1>
<p class="lede">Site Studio portfolio mode turns ATLAS membership and governed receipts into the product website. Readiness labels are evidence projections, not marketing copy.</p>
<div class="evidence-strip"><div><strong>53</strong>canonical products</div><div><strong>159/159</strong>execution journeys verified</div><div><strong>{model["buyer_production_ready_count"]}</strong>buyer-ready surfaces</div><div><strong>{model["internal_production_ready_count"]}</strong>internal-ready capabilities</div></div>
</section>
<section class="suite-grid">{"".join(suite_cards)}</section>
<section class="section"><div class="eyebrow">Production instruments</div><h2>{html.escape(str(contract["studio_band"]["title"]))}</h2><p class="lede">{html.escape(str(contract["studio_band"]["description"]))}</p><div class="studios">{"".join(studio_cards)}</div></section>
<div class="boundary"><strong>Commercial validation:</strong> {html.escape(str(model["commercial_validation"]))}. <strong>Evidence boundary:</strong> {html.escape(str(model["claim_boundary"]))}</div>
</main><footer><div class="shell">DIO Site Studio · portfolio suite mode · human release NEEDS_YOU · automatic publication REFUSE</div></footer></body></html>'''
    index_path = customer_root / "index.html"
    index_path.write_text(index, encoding="utf-8")
    page_rows.append({"path": "index.html", "sha256": _sha256(index_path)})
    page_rows.append({"path": "styles.css", "sha256": _sha256(customer_root / "styles.css")})

    proof_model_path = proof_root / "PORTFOLIO_SUITE_SURFACE_MODEL.json"
    _write_json(proof_model_path, model)

    artifact_files = sorted(path for path in artifact_root.rglob("*") if path.is_file()) if artifact_root.exists() else []
    visual_files = sorted(path for path in visual_root.rglob("*") if path.is_file()) if visual_root.exists() else []
    visual_pass = (
        render_visuals
        and len(visual_receipts) == len(model["suites"])
        and all(row.get("format_core_visual_composition") == "PASS" for row in visual_receipts)
        and all(row.get("site_semantic_authority") == "DIO_SITE_STUDIO" for row in visual_receipts)
        and all(row.get("geometry_authority") == "DIO_FORMAT_CORE" for row in visual_receipts)
    )
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "acceptance_token": contract["build_acceptance_token"] if visual_pass else None,
        "suite_count": len(model["suites"]),
        "canonical_product_count": model["canonical_product_count"],
        "all_canonical_execution_verified": model["all_canonical_execution_verified"],
        "execution_verified_journey_count": model["execution_verified_journey_count"],
        "portfolio_production_ready": model["portfolio_production_ready"],
        "suite_states": {str(row["name"]): str(row["suite_state"]) for row in model["suites"]},
        "page_count": 1 + len(model["suites"]),
        "page_assets": page_rows,
        "input_evidence_snapshots": evidence_rows,
        "bundled_customer_artifact_count": len(artifact_files),
        "bundled_customer_artifact_hashes": [
            {"path": str(path.relative_to(customer_root)), "sha256": _sha256(path)} for path in artifact_files
        ],
        "site_studio_suite_visual_receipts": visual_receipts,
        "format_core_visual_asset_count": len(visual_files),
        "format_core_visual_composition": "PASS" if visual_pass else "NOT_RUN",
        "site_semantic_authority": "DIO_SITE_STUDIO" if visual_pass else None,
        "visual_geometry_authority": "DIO_FORMAT_CORE" if visual_pass else None,
        "all_visible_statuses_receipt_bound": True,
        "model_fingerprint": model["model_fingerprint"],
        "publication": "REFUSE",
        "human_release": "NEEDS_YOU",
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": model["commercial_validation"],
        "claim_boundary": contract["claim_boundary"],
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    receipt_path = output_dir / "PORTFOLIO_SUITE_SITE_RECEIPT.json"
    _write_json(receipt_path, receipt)
    return {
        "receipt": receipt,
        "receipt_path": receipt_path,
        "customer_site": customer_root,
        "proof_model": proof_model_path,
    }


__all__ = [
    "MODEL_SCHEMA",
    "PortfolioSuiteStudioError",
    "RECEIPT_SCHEMA",
    "build_suite_model",
    "load_contract",
    "load_json",
    "render_suite_site",
]
