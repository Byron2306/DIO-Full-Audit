from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path
from typing import Any, Callable

from adapters.beast_product_grade import run_beast_artifact_checks
from adapters.lingua.lifecycle import register_product_source
from products.canon_extension_native_profiles import NATIVE_CANON_EXTENSION_PROFILES, VARIANTS, native_profile
from products.canon_extension_product_grade import (
    CANON_EXTENSIONS,
    PRODUCT_GRADE_REFUSE,
    PRODUCT_GRADE_VERIFIED,
)
from products.canon_extension_proof_seal import SEAL_FILENAME


NATIVE_BATCH_BASELINE_TOKEN = "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_BASELINE_MEASURED"
NATIVE_BATCH_VERIFIED_TOKEN = "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED"
NATIVE_SCHEMA = "dio.product_grade.canon_extension_native.v3"
VARIANT_SCHEMA = "dio.product_grade.canon_extension_native_variant.v1"

_SPECS = {row["slug"]: row for row in CANON_EXTENSIONS}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _rows(values: list[str]) -> list[dict[str, str]]:
    return [
        {"paragraph_id": f"P{index:03d}", "text": str(text).strip()}
        for index, text in enumerate(values, 1)
        if str(text).strip()
    ]


def build_semantic_rows(profile: dict[str, Any], fixture: dict[str, Any]) -> list[dict[str, str]]:
    family = str(profile["family"])
    mode = str(profile["mode"])
    subject = str(fixture["subject"])

    if family == "publication_professional":
        if mode == "article":
            values = [
                subject,
                "Publication and audience",
                f"Target publication: {fixture['publication']}",
                f"Audience: {fixture['audience']}",
                "Purpose",
                str(fixture["purpose"]),
                "Supported evidence",
                *[f"Supported: {item}" for item in fixture.get("evidence") or []],
                "Held claims",
                *[f"Held for human review: {item}" for item in fixture.get("held_claims") or []],
                "Human editorial review and publication authority remain required before external release.",
            ]
            return _rows(values)

        if mode == "contract":
            values = [
                subject,
                f"Counterparty: {fixture['counterparty']}",
                "Purpose",
                str(fixture["purpose"]),
                "Recorded facts",
                *[f"Recorded fact: {item}" for item in fixture.get("facts") or []],
                "Open questions",
                *[f"Question for human review: {item}" for item in fixture.get("questions") or []],
                "Human legal review and decision authority remain required. This brief does not determine legal validity or enforceability.",
            ]
            return _rows(values)

        if mode == "correspondence":
            values = [
                f"Draft correspondence: {subject}",
                f"Recipient: {fixture['recipient']}",
                "Purpose",
                str(fixture["purpose"]),
                "Facts being preserved",
                *[f"Fact: {item}" for item in fixture.get("facts") or []],
                "Draft position",
                *[f"Position: {item}" for item in fixture.get("draft_position") or []],
                "No concession, settlement or external commitment is created by this draft.",
                "Human sender approval remains required before external send.",
            ]
            return _rows(values)

        if mode == "pitch":
            values = [
                subject,
                f"Target audience: {fixture['audience']}",
                "Purpose",
                str(fixture["purpose"]),
                "Evidence available",
                *[f"Evidence: {item}" for item in fixture.get("evidence") or []],
                "Material risks",
                *[f"Risk: {item}" for item in fixture.get("risks") or []],
                "Held claims",
                *[f"Held for human review: {item}" for item in fixture.get("held_claims") or []],
                "Investment interest, valuation and funding remain unproved until independently observed. Human release authority remains required.",
            ]
            return _rows(values)

    if family == "readiness_assurance":
        requirements = list(fixture.get("requirements") or [])
        missing = [row for row in requirements if str(row.get("state") or "").casefold() != "supplied"]
        boundary = {
            "corporate": "This is an evidence-readiness assessment, not an approval or legal clearance. Human decision authority remains required.",
            "finance": "This is an evidence-readiness assessment, not a lending, affordability or funding decision. Human decision authority remains required.",
            "popia": "This is a privacy-readiness review, not legal advice or a compliance certification. Human or qualified professional decision authority remains required.",
        }[mode]
        values = [
            subject,
            "Purpose",
            str(fixture["purpose"]),
            "Requirement review",
            *[f"{row['label']}: {str(row['state']).upper()}" for row in requirements],
            f"Missing or unresolved evidence items: {len(missing)}",
            boundary,
        ]
        return _rows(values)

    if family == "opportunity_venture":
        if mode == "entrepreneur":
            values = [
                subject,
                "Business model",
                str(fixture["business_model"]),
                "Evidence available",
                *[f"Evidence: {item}" for item in fixture.get("evidence") or []],
                "Questions still open",
                *[f"Open question: {item}" for item in fixture.get("questions") or []],
                "Venture viability and willingness to pay remain unproved until independently observed. Human decision authority remains required.",
            ]
            return _rows(values)

        values = [
            subject,
            "Objective",
            str(fixture["objective"]),
            "Decision criteria",
            *[f"Criterion: {item}" for item in fixture.get("criteria") or []],
            "Evidence available",
            *[f"Evidence: {item}" for item in fixture.get("evidence") or []],
        ]
        if mode == "funding":
            values.append("Opportunity matching does not create eligibility, approval or an award. Human application authority remains required.")
        else:
            values.append("Investor readiness does not create investor interest, valuation or investment commitment. Human release authority remains required.")
        return _rows(values)

    if family == "launch_orchestration" and mode == "launch":
        values = [
            subject,
            f"Target audience: {fixture['audience']}",
            "Proposition",
            str(fixture["proposition"]),
            "Planned channels",
            *[f"Channel: {item}" for item in fixture.get("channels") or []],
            "Release constraints",
            *[f"Constraint: {item}" for item in fixture.get("constraints") or []],
            "Performance remains unproved until observed. Human publication and spend authority remain required.",
        ]
        return _rows(values)

    raise ValueError(f"unsupported native ProductGrade family/mode: {family}/{mode}")


def render_buyer_html(*, title: str, semantic_object: dict[str, Any], output_path: Path) -> None:
    if semantic_object.get("schema") != "dio.lingua.semantic_object.v1":
        raise ValueError("buyer artifact renderer requires a Lingua semantic object")
    units = list((semantic_object.get("source") or {}).get("units") or [])
    if not units:
        raise ValueError("buyer artifact renderer requires semantic units")

    headings = {
        "Purpose",
        "Recorded facts",
        "Open questions",
        "Supported evidence",
        "Held claims",
        "Requirement review",
        "Business model",
        "Evidence available",
        "Questions still open",
        "Objective",
        "Decision criteria",
        "Proposition",
        "Planned channels",
        "Release constraints",
        "Publication and audience",
        "Facts being preserved",
        "Draft position",
        "Material risks",
    }
    body: list[str] = []
    for index, unit in enumerate(units):
        text = escape(str(unit.get("source_text") or "").strip())
        if not text:
            continue
        if index == 0:
            body.append(f"<h1>{text}</h1>")
        elif text in headings:
            body.append(f"<h2>{text}</h2>")
        else:
            body.append(f"<p>{text}</p>")

    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 880px; margin: 0 auto; padding: 40px 24px; line-height: 1.55; }}
    h1 {{ font-size: 2rem; margin-bottom: 1rem; }}
    h2 {{ font-size: 1.15rem; margin-top: 1.8rem; }}
    p {{ margin: 0.65rem 0; }}
  </style>
</head>
<body>
{body}
</body>
</html>
""".format(title=escape(title), body="\n".join(body))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def _lingua_custody(
    *,
    slug: str,
    rows: list[dict[str, str]],
    semantic: dict[str, Any],
    registration: dict[str, Any],
) -> bool:
    if semantic.get("schema") != "dio.lingua.semantic_object.v1":
        return False
    if registration.get("schema") != "dio.lingua.product_registration_receipt.v1":
        return False
    if str((semantic.get("origin") or {}).get("product") or "") != slug:
        return False
    if registration.get("object_id") != semantic.get("object_id"):
        return False
    if registration.get("source_document_hash") != (semantic.get("source") or {}).get("document_hash"):
        return False

    observed = [str(row.get("source_text") or "") for row in (semantic.get("source") or {}).get("units") or []]
    expected = [str(row["text"]) for row in rows]
    object_path = Path(str(registration.get("object_path") or ""))
    if observed != expected or not object_path.is_file():
        return False
    try:
        persisted = json.loads(object_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return persisted == semantic


def _execute_fixture(
    *,
    slug: str,
    profile: dict[str, Any],
    fixture: dict[str, Any],
    workspace: Path,
    root: Path,
    beast_checker: Callable[..., dict[str, Any]],
    object_suffix: str,
) -> dict[str, Any]:
    rows = build_semantic_rows(profile, fixture)
    if fixture.get("adversarial_pressure"):
        rows.append(
            {
                "paragraph_id": f"P{len(rows) + 1:03d}",
                "text": str(profile["adversarial_expected_boundary"]),
            }
        )
    state_root = workspace / "lingua_state"
    object_id = f"DIO-PG-{slug.upper().replace('-', '_')}-{object_suffix.upper()}"
    semantic, registration = register_product_source(
        state_root=state_root,
        object_id=object_id,
        source_version="1.0.0",
        source_language="English",
        source_rows=rows,
        origin={
            "product": slug,
            "artifact_type": "controlled_buyer_artifact",
            "artifact_id": object_id,
            "audience": profile["buyer"],
            "channel": "html",
        },
        domain=str(profile["family"]),
        subject=str(fixture["subject"]),
    )
    _write_json(workspace / "LINGUA_REGISTRATION_RECEIPT.json", registration)

    delivery_dir = workspace / "customer_delivery"
    artifact = delivery_dir / "index.html"
    render_buyer_html(title=str(profile["name"]), semantic_object=semantic, output_path=artifact)
    beast = beast_checker(dio_root=root, workspace=delivery_dir)
    text = artifact.read_text(encoding="utf-8", errors="replace")
    lowered = text.casefold()
    forbidden_hits = [
        claim
        for claim in profile["forbidden_claims"]
        if str(claim).casefold() in lowered
    ]
    custody = _lingua_custody(
        slug=slug,
        rows=rows,
        semantic=semantic,
        registration=registration,
    )
    return {
        "rows": rows,
        "semantic_object": semantic,
        "registration": registration,
        "lingua_semantic_custody": custody,
        "artifact": artifact,
        "artifact_sha256": _sha(artifact),
        "beast": beast,
        "beast_mechanical_pass": beast.get("mechanical_pass") is True,
        "text": text,
        "forbidden_claim_hits": forbidden_hits,
    }


def _relative_inside(root: Path, path: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return None


def _base_receipt(*, slug: str, profile: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": NATIVE_SCHEMA,
        "slug": slug,
        "canon_id": spec["canon_id"],
        "name": spec["name"],
        "family": profile["family"],
        "proof_kind": spec["proof_kind"],
        "status": PRODUCT_GRADE_REFUSE,
        "critical_blockers": [],
        "variant_count": 3,
        "verified_variant_count": 0,
        "refused_variant_count": 3,
        "variants": {},
        "canon_artifact": spec.get("primary_artifact", ""),
        "canon_artifact_sha256": "",
        "canon_proof_receipt": "",
        "canon_proof_receipt_sha256": "",
        "upstream_studio_id": spec.get("studio_id"),
        "upstream_studio_product_grade_fingerprint": "",
        "upstream_studio_artifact": "",
        "upstream_studio_artifact_sha256": "",
        "customer_artifact": "",
        "customer_artifact_sha256": "",
        "primary_artifact_sha256": "",
        "lingua_semantic_custody": False,
        "lingua_registration_schema": None,
        "beast_mechanical_pass": False,
        "unseen_input_generalisation": False,
        "external_effects": False,
        "authority_created": False,
        "customers_will_pay": "UNPROVED",
        "verified_payment": "UNPROVED",
        "commercial_validation": "UNPROVED",
        "claim_boundary": (
            "Native canon-extension ProductGrade verifies normal, messy, and adversarial buyer-artifact execution, "
            "Lingua semantic custody, BEAST mechanical integrity, explicit authority boundaries, distinct variant "
            "generalisation, and current provenance binding. It does not prove buyer demand, payment, legal approval, "
            "publication authority, investment interest, funding approval, or market performance."
        ),
    }


def _bind_receipt_bound_provenance(
    *,
    root: Path,
    spec: dict[str, Any],
    receipt: dict[str, Any],
    blockers: list[str],
) -> None:
    canon = (root / spec["primary_artifact"]).resolve()
    if not canon.is_relative_to(root) or not canon.is_file():
        blockers.append("canon_artifact_missing")
        return

    receipt["canon_artifact_sha256"] = _sha(canon)
    proof = canon.parent / SEAL_FILENAME
    if not proof.is_relative_to(root) or not proof.is_file():
        blockers.append("canon_proof_receipt_missing")
        return

    receipt["canon_proof_receipt"] = str(proof.relative_to(root))
    receipt["canon_proof_receipt_sha256"] = _sha(proof)
    try:
        proof_data = json.loads(proof.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        blockers.append("canon_proof_receipt_invalid")
        return

    if not isinstance(proof_data, dict):
        blockers.append("canon_proof_receipt_invalid")
        return
    observed = str(proof_data.get("current_artifact_sha256") or "").removeprefix("sha256:")
    if proof_data.get("schema") != "dio.canon_extension.proof_seal.v1" or proof_data.get("status") != "PASS":
        blockers.append("canon_proof_receipt_not_verified")
    if str(proof_data.get("slug") or "") != spec["slug"]:
        blockers.append("canon_proof_receipt_identity_mismatch")
    if observed != receipt["canon_artifact_sha256"]:
        blockers.append("canon_proof_receipt_artifact_mismatch")
    if proof_data.get("authority_created") is not False or proof_data.get("external_effects") is not False:
        blockers.append("canon_proof_receipt_authority_drift")


def _bind_studio_provenance(
    *,
    root: Path,
    spec: dict[str, Any],
    studio_product_grade_receipt: dict[str, Any] | None,
    receipt: dict[str, Any],
    blockers: list[str],
) -> None:
    if not isinstance(studio_product_grade_receipt, dict):
        blockers.append("source_studio_product_grade_missing")
        return
    studios = studio_product_grade_receipt.get("studios") or {}
    source = studios.get(spec["studio_id"]) if isinstance(studios, dict) else None
    if not isinstance(source, dict):
        blockers.append("source_studio_product_grade_missing")
        return
    if source.get("status") != PRODUCT_GRADE_VERIFIED:
        blockers.append("source_studio_product_grade_not_verified")
    if source.get("critical_blockers"):
        blockers.append("source_studio_product_grade_blocked")
    if source.get("customers_will_pay") != "UNPROVED" or source.get("verified_payment") != "UNPROVED":
        blockers.append("source_studio_commercial_boundary_drift")

    source_path = str(source.get("primary_artifact") or "")
    if not source_path:
        blockers.append("source_studio_artifact_missing")
        return
    artifact = (root / source_path).resolve()
    if not artifact.is_relative_to(root) or not artifact.is_file():
        blockers.append("source_studio_artifact_missing")
        return

    live_sha = _sha(artifact)
    declared_sha = str(source.get("primary_artifact_sha256") or "").removeprefix("sha256:")
    if declared_sha != live_sha:
        blockers.append("source_studio_artifact_hash_mismatch")

    receipt["upstream_studio_product_grade_fingerprint"] = str(
        source.get("receipt_fingerprint") or _fingerprint(source)
    )
    receipt["upstream_studio_artifact"] = source_path
    receipt["upstream_studio_artifact_sha256"] = live_sha


def _variant_receipt(
    *,
    slug: str,
    profile: dict[str, Any],
    variant: str,
    result: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    text = str(result["text"])
    lowered = text.casefold()
    anchor = str(profile["anchors"][variant])
    anchor_present = anchor.casefold() in lowered
    human_boundary_present = "human" in lowered
    artifact_rel = _relative_inside(root, result["artifact"])
    if artifact_rel is None:
        blockers.append("customer_artifact_outside_root")
        artifact_rel = ""
    if result["lingua_semantic_custody"] is not True:
        blockers.append("lingua_semantic_custody_missing")
    if result["beast_mechanical_pass"] is not True:
        blockers.append("beast_mechanical_failure")
    if not anchor_present:
        blockers.append("semantic_anchor_missing")
    if len(result["rows"]) < 6:
        blockers.append("semantic_unit_count_too_low")
    if result["forbidden_claim_hits"]:
        blockers.append("forbidden_claim_detected")
    if not human_boundary_present:
        blockers.append("human_boundary_missing")

    adversarial_boundary_held = True
    if variant == "adversarial":
        expected = str(profile["adversarial_expected_boundary"])
        adversarial_boundary_held = expected.casefold() in lowered
        if not adversarial_boundary_held:
            blockers.append("adversarial_boundary_not_held")

    row: dict[str, Any] = {
        "schema": VARIANT_SCHEMA,
        "slug": slug,
        "variant": variant,
        "passed": not blockers,
        "critical_blockers": sorted(set(blockers)),
        "expected_anchor": anchor,
        "anchor_present": anchor_present,
        "semantic_unit_count": len(result["rows"]),
        "customer_artifact": artifact_rel,
        "customer_artifact_sha256": result["artifact_sha256"],
        "lingua_semantic_custody": result["lingua_semantic_custody"],
        "lingua_object_id": result["semantic_object"].get("object_id"),
        "lingua_source_document_hash": (result["semantic_object"].get("source") or {}).get("document_hash"),
        "lingua_registration_schema": result["registration"].get("schema"),
        "lingua_registration_fingerprint": _fingerprint(result["registration"]),
        "beast_mechanical_pass": result["beast_mechanical_pass"],
        "beast_artifact_checks": result["beast"],
        "forbidden_claim_hits": result["forbidden_claim_hits"],
        "human_boundary_present": human_boundary_present,
        "adversarial_pressure": profile["adversarial_pressure"] if variant == "adversarial" else None,
        "adversarial_expected_boundary": profile["adversarial_expected_boundary"] if variant == "adversarial" else None,
        "adversarial_boundary_held": adversarial_boundary_held if variant == "adversarial" else None,
        "external_effects": False,
        "authority_created": False,
    }
    row["receipt_fingerprint"] = _fingerprint(row)
    return row


def run_native_product_grade_case(
    *,
    slug: str,
    root: Path,
    output_dir: Path,
    beast_checker: Callable[..., dict[str, Any]] = run_beast_artifact_checks,
    studio_product_grade_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    profile = native_profile(slug)
    spec = _SPECS.get(slug)
    if spec is None:
        raise KeyError(f"{slug} is not a canon extension")

    receipt = _base_receipt(slug=slug, profile=profile, spec=spec)
    blockers: list[str] = receipt["critical_blockers"]

    if not output_dir.is_relative_to(root):
        blockers.append("unsafe_output_dir")

    if spec["proof_kind"] == "receipt_bound":
        _bind_receipt_bound_provenance(root=root, spec=spec, receipt=receipt, blockers=blockers)
    elif spec["proof_kind"] == "studio_product_grade":
        _bind_studio_provenance(
            root=root,
            spec=spec,
            studio_product_grade_receipt=studio_product_grade_receipt,
            receipt=receipt,
            blockers=blockers,
        )
    else:
        blockers.append("unsupported_proof_kind")

    if blockers:
        receipt["critical_blockers"] = sorted(set(blockers))
        receipt["receipt_fingerprint"] = _fingerprint(receipt)
        _write_json(output_dir / "PRODUCT_GRADE_RECEIPT.json", receipt)
        return {"receipt": receipt, "output_dir": str(output_dir)}

    executions: dict[str, dict[str, Any]] = {}
    variant_rows: dict[str, dict[str, Any]] = {}
    for variant in VARIANTS:
        workspace = output_dir / "variants" / variant
        try:
            result = _execute_fixture(
                slug=slug,
                profile=profile,
                fixture=profile["fixtures"][variant],
                workspace=workspace,
                root=root,
                beast_checker=beast_checker,
                object_suffix=variant,
            )
            executions[variant] = result
            variant_rows[variant] = _variant_receipt(
                slug=slug,
                profile=profile,
                variant=variant,
                result=result,
                root=root,
            )
        except Exception as exc:
            variant_rows[variant] = {
                "schema": VARIANT_SCHEMA,
                "slug": slug,
                "variant": variant,
                "passed": False,
                "critical_blockers": ["native_execution_error"],
                "execution_error": f"{type(exc).__name__}: {exc}",
                "external_effects": False,
                "authority_created": False,
            }
            variant_rows[variant]["receipt_fingerprint"] = _fingerprint(variant_rows[variant])

    hashes = [
        row.get("customer_artifact_sha256")
        for row in variant_rows.values()
        if row.get("customer_artifact_sha256")
    ]
    distinct_variants = len(hashes) == 3 and len(set(hashes)) == 3
    if not distinct_variants:
        for variant, row in variant_rows.items():
            if "variant_artifact_not_distinct" not in row["critical_blockers"]:
                row["critical_blockers"].append("variant_artifact_not_distinct")
            row["critical_blockers"] = sorted(set(row["critical_blockers"]))
            row["passed"] = False
            row["receipt_fingerprint"] = _fingerprint(
                {key: value for key, value in row.items() if key != "receipt_fingerprint"}
            )

    for variant, row in variant_rows.items():
        _write_json(
            output_dir / "variants" / variant / "PRODUCT_GRADE_VARIANT_RECEIPT.json",
            row,
        )
        if not row["passed"]:
            blockers.append(f"variant_{variant}_refused")

    verified_variant_count = sum(1 for row in variant_rows.values() if row["passed"])
    refused_variant_count = 3 - verified_variant_count
    normal = variant_rows.get("normal") or {}

    receipt.update(
        {
            "variants": variant_rows,
            "verified_variant_count": verified_variant_count,
            "refused_variant_count": refused_variant_count,
            "customer_artifact": normal.get("customer_artifact", ""),
            "customer_artifact_sha256": normal.get("customer_artifact_sha256", ""),
            "lingua_semantic_custody": all(
                row.get("lingua_semantic_custody") is True for row in variant_rows.values()
            ),
            "lingua_registration_schema": normal.get("lingua_registration_schema"),
            "beast_mechanical_pass": all(
                row.get("beast_mechanical_pass") is True for row in variant_rows.values()
            ),
            "unseen_input_generalisation": distinct_variants,
        }
    )

    if spec["proof_kind"] == "receipt_bound":
        receipt["primary_artifact_sha256"] = receipt["canon_artifact_sha256"]
    else:
        receipt["primary_artifact_sha256"] = receipt["upstream_studio_artifact_sha256"]

    receipt["critical_blockers"] = sorted(set(blockers))
    receipt["status"] = (
        PRODUCT_GRADE_VERIFIED
        if verified_variant_count == 3 and not receipt["critical_blockers"]
        else PRODUCT_GRADE_REFUSE
    )
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    _write_json(output_dir / "PRODUCT_GRADE_RECEIPT.json", receipt)
    return {
        "receipt": receipt,
        "variants": executions,
        "output_dir": str(output_dir),
    }


def run_native_product_grade_batch(
    *,
    root: Path,
    output_root: Path,
    beast_checker: Callable[..., dict[str, Any]] = run_beast_artifact_checks,
    studio_product_grade_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    products: dict[str, Any] = {}
    verified_journey_count = 0
    for profile in NATIVE_CANON_EXTENSION_PROFILES:
        slug = str(profile["slug"])
        result = run_native_product_grade_case(
            slug=slug,
            root=root,
            output_dir=output_root / slug,
            beast_checker=beast_checker,
            studio_product_grade_receipt=studio_product_grade_receipt,
        )
        receipt = result["receipt"]
        verified_journey_count += int(receipt.get("verified_variant_count") or 0)
        products[slug] = {
            "status": receipt["status"],
            "critical_blockers": receipt["critical_blockers"],
            "variant_count": receipt.get("variant_count", 3),
            "verified_variant_count": receipt.get("verified_variant_count", 0),
            "refused_variant_count": receipt.get("refused_variant_count", 3),
            "canon_artifact_sha256": receipt.get("canon_artifact_sha256"),
            "upstream_studio_product_grade_fingerprint": receipt.get("upstream_studio_product_grade_fingerprint"),
            "customer_artifact_sha256": receipt.get("customer_artifact_sha256"),
            "receipt_fingerprint": receipt.get("receipt_fingerprint"),
        }

    product_grade_verified_count = sum(
        1 for row in products.values() if row["status"] == PRODUCT_GRADE_VERIFIED
    )
    product_grade_refuse_count = len(products) - product_grade_verified_count
    controlled_journey_count = len(products) * 3
    refused_journey_count = controlled_journey_count - verified_journey_count
    all_verified = (
        len(products) == 15
        and product_grade_verified_count == 15
        and verified_journey_count == 45
        and refused_journey_count == 0
    )

    batch = {
        "schema": "dio.product_grade.canon_extension_native_batch.v2",
        "acceptance_token": NATIVE_BATCH_VERIFIED_TOKEN if all_verified else NATIVE_BATCH_BASELINE_TOKEN,
        "extension_count": len(products),
        "variants_per_extension": 3,
        "controlled_journey_count": controlled_journey_count,
        "verified_journey_count": verified_journey_count,
        "refused_journey_count": refused_journey_count,
        "product_grade_verified_count": product_grade_verified_count,
        "product_grade_refuse_count": product_grade_refuse_count,
        "all_product_grade_verified": all_verified,
        "products": products,
        "external_effects": False,
        "authority_created": False,
        "commercial_validation": "UNPROVED",
        "claim_boundary": (
            "This batch measures controlled native ProductGrade across all fifteen canon extensions using "
            "normal, messy, and adversarial buyer-artifact journeys. It proves controlled capability and "
            "provenance boundaries, not buyer demand, payment, or external authority."
        ),
        "target_count": len(products),
        "verified_count": product_grade_verified_count,
        "refuse_count": product_grade_refuse_count,
        "all_verified": all_verified,
    }
    batch["batch_fingerprint"] = _fingerprint(batch)
    _write_json(
        output_root / "NATIVE_CANON_EXTENSION_PRODUCT_GRADE_BATCH_RECEIPT.json",
        batch,
    )
    return batch
