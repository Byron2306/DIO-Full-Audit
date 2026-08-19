from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from portfolio_runtime import ROOT, load_portfolio

MATRIX_PATH = ROOT / "config" / "marketing_audience_matrix.json"
DOMAIN_REGISTRY = ROOT / "config" / "atlas" / "dio_atlas_universal_domain_registry.csv"
COCKPIT_PATH = ROOT / "state" / "market_sensorium" / "COMMERCIAL_COCKPIT.json"

PROFILE_COMPATIBILITY: dict[str, set[str]] = {
    "EVIDEX_PACK": {"Evidex EvidenceOps"},
    "HOMS_ASSESS": {"HOMS Assess"},
    "HOMS_LEARNING": {"HOMS Learning Studio"},
    "SOPHIA_REVIEW": {"Sophia Review"},
    "VAMP_ACADEMIC": {"VAMP Performance"},
    "DOCUMENT_STUDIO": {"Document Studio Edit", "Document Studio Localize", "Document Studio Publish"},
}

SUITE_AUDIENCES = {
    "Education & Research": "education, research and academic operations teams",
    "Enterprise Operations": "operations, HR and professional-services teams",
    "Evidence & Assurance": "assurance, compliance, audit and evidence teams",
    "Public & Programme Ops": "programme, public-sector and funding operations teams",
    "AI & Digital Trust": "AI governance, risk and digital-assurance teams",
    "Demand & Presence": "marketing, communications and digital-operations teams",
}

PATTERN_PROBLEMS = {
    "Evidence": "evidence is scattered across files, systems and human memory, making review slow and difficult to verify",
    "Assessment": "assessment preparation, marking and review consume specialist time and are difficult to standardise",
    "Quality": "quality checks are repetitive and inconsistent when evidence, criteria and review decisions live in separate places",
    "Learning": "learning material must be repeatedly adapted, aligned and reviewed for the actual audience and context",
    "Obligation": "requirements, deadlines, obligations and supporting evidence are difficult to reconcile before a decision or submission",
    "Achievement": "performance and achievement evidence is fragmented, making review preparation unnecessarily manual",
    "Integrity": "claims, sources and integrity issues require careful checking without taking authority away from the human author or reviewer",
    "Assurance": "assurance work is slowed when controls, evidence, gaps and review decisions cannot be traced together",
    "Authority": "permissions and consequential decisions need an explicit human authority boundary rather than silent automation",
    "Document": "document editing, transformation, localisation and publication require repeated technical work while meaning must remain intact",
    "Proof": "turning raw work into a review-ready proof package requires provenance, gap visibility and integrity checks",
    "Intake": "incoming work must be triaged and routed without losing context, risk or human approval boundaries",
    "Market": "market signals are fragmented across sources, making opportunity comparison and bounded next-step selection difficult",
}

PATTERN_OUTCOMES = {
    "Evidence": "a reviewable evidence map with provenance and gaps made visible",
    "Assessment": "assessment work prepared for specialist review with criteria and evidence kept visible",
    "Quality": "a consistent review trail showing checks, exceptions and human decisions",
    "Learning": "context-aware learning material prepared for educator or specialist review",
    "Obligation": "a structured obligation-and-evidence view with deadlines, gaps and decisions separated",
    "Achievement": "a concise performance-evidence view that shows what supports each objective and what is still missing",
    "Integrity": "a source-grounded review that separates findings, uncertainty and human authorship decisions",
    "Assurance": "an auditable assurance view linking controls, evidence, gaps and review state",
    "Authority": "a bounded workflow where authority remains explicit and consequential action stays human-gated",
    "Document": "a technically prepared document with meaning, terminology and review changes kept traceable",
    "Proof": "a review-ready proof package with integrity and provenance receipts",
    "Intake": "a governed intake record with routing, risk and next actions made explicit",
    "Market": "a source-bound market brief that separates observations, hypotheses and permitted next tests",
}

STOPWORDS = {
    "and", "the", "for", "with", "from", "that", "this", "into", "your", "their", "one", "are", "our",
    "ready", "review", "human", "work", "team", "teams", "a", "an", "to", "of", "in", "on", "or", "is",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _matrix() -> dict[str, Any]:
    return _load_json(MATRIX_PATH)


def _domains() -> dict[str, dict[str, str]]:
    if not DOMAIN_REGISTRY.is_file():
        return {}
    with DOMAIN_REGISTRY.open("r", encoding="utf-8", newline="") as handle:
        return {str(row.get("domain_id") or ""): row for row in csv.DictReader(handle) if row.get("domain_id")}


def _incarnation(name: str) -> dict[str, Any]:
    row = next((item for item in load_portfolio()["incarnations"] if item.get("Incarnation") == name), None)
    if not row:
        raise ValueError("Select a canonical imported portfolio incarnation")
    return row


def _split(value: Any) -> list[str]:
    return [part.strip() for part in re.split(r"[|;]", str(value or "")) if part.strip()]


def _tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").casefold())
        if len(token) > 2 and token not in STOPWORDS
    }


def _profile_for_incarnation(name: str) -> dict[str, Any] | None:
    profile_id = next((pid for pid, names in PROFILE_COMPATIBILITY.items() if name in names), "")
    if not profile_id:
        return None
    return next((row for row in _matrix().get("products") or [] if row.get("id") == profile_id), None)


def _sensorium_context(domain_ids: list[str]) -> dict[str, Any]:
    cockpit = _load_json(COCKPIT_PATH)
    domain_set = set(domain_ids)
    sections = {
        "ranked_targets": [row for row in cockpit.get("ranked_targets") or [] if str(row.get("domain_id") or "") in domain_set],
        "hypotheses": [row for row in cockpit.get("hypotheses") or [] if str(row.get("domain_id") or "") in domain_set],
        "offers": [row for row in cockpit.get("offers") or [] if str(row.get("domain_id") or "") in domain_set],
        "habitats": [row for row in cockpit.get("habitats") or [] if str(row.get("domain_id") or "") in domain_set],
        "learned_queries": [row for row in cockpit.get("learned_queries") or [] if str(row.get("domain_id") or "") in domain_set],
    }
    sections["available"] = bool(cockpit)
    return sections


def _sensorium_text(context: dict[str, Any]) -> str:
    values: list[str] = []
    for row in context.get("ranked_targets") or []:
        values.extend([str(row.get("organisation") or ""), str(row.get("buyer_unit") or "")])
    for row in context.get("hypotheses") or []:
        values.extend([str(row.get("organisation") or ""), str(row.get("selected_hypothesis_type") or "")])
    for row in context.get("offers") or []:
        values.extend([str(row.get("seller") or ""), str(row.get("headline") or "")])
    for row in context.get("habitats") or []:
        values.extend([str(row.get("name") or ""), str(row.get("platform") or "")])
    for row in context.get("learned_queries") or []:
        values.extend([str(row.get("query") or ""), str(row.get("query_kind") or "")])
    return " ".join(values)


def _choose_profile_audience(profile: dict[str, Any], incarnation: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    audiences = list(profile.get("audiences") or [])
    if not audiences:
        raise ValueError(f"Configured marketing profile {profile.get('id')} has no audiences")
    domain_map = _domains()
    domain_names = [domain_map.get(domain_id, {}).get("domain_name", "") for domain_id in _split(incarnation.get("atlas_domain_ids"))]
    semantic_text = " ".join(
        [
            str(incarnation.get("Incarnation") or ""),
            str(incarnation.get("Suite") or ""),
            str(incarnation.get("Product Family") or ""),
            str(incarnation.get("source_work_patterns") or ""),
            *domain_names,
            _sensorium_text(context),
        ]
    )
    semantic_tokens = _tokens(semantic_text)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, audience in enumerate(audiences):
        audience_tokens = _tokens(" ".join(str(audience.get(key) or "") for key in ("name", "pain", "outcome")))
        score = len(semantic_tokens & audience_tokens)
        scored.append((score, -index, audience))
    return max(scored, key=lambda row: (row[0], row[1]))[2]


def _semantic_custom_brief(incarnation: dict[str, Any], context: dict[str, Any]) -> dict[str, str]:
    name = str(incarnation.get("Incarnation") or "DIO product")
    suite = str(incarnation.get("Suite") or "")
    patterns = _split(incarnation.get("source_work_patterns"))
    domain_ids = _split(incarnation.get("atlas_domain_ids"))
    domain_map = _domains()
    domain_names = [domain_map.get(domain_id, {}).get("domain_name", domain_id) for domain_id in domain_ids]
    domain_names = [value for value in domain_names if value]

    buyer_units = [str(row.get("buyer_unit") or "").strip() for row in context.get("ranked_targets") or []]
    buyer_units = list(dict.fromkeys(value for value in buyer_units if value))
    if buyer_units:
        audience = buyer_units[0]
        if domain_names:
            audience = f"{audience} teams working in {domain_names[0].lower()}"
    else:
        audience = SUITE_AUDIENCES.get(suite) or (
            f"professional teams working in {domain_names[0].lower()}" if domain_names else "professional teams responsible for this workflow"
        )

    problem_parts = [PATTERN_PROBLEMS[pattern] for pattern in patterns if pattern in PATTERN_PROBLEMS]
    outcome_parts = [PATTERN_OUTCOMES[pattern] for pattern in patterns if pattern in PATTERN_OUTCOMES]
    problem = problem_parts[0] if problem_parts else "the workflow depends on fragmented information, repeated manual reconciliation and human review"
    if len(problem_parts) > 1:
        problem = problem.rstrip(".") + "; at the same time, " + problem_parts[1]
    outcome = outcome_parts[0] if outcome_parts else "a review-ready result with provenance, limitations and human decisions kept visible"
    if len(outcome_parts) > 1:
        outcome = outcome.rstrip(".") + " plus " + outcome_parts[1]

    maturity = str(incarnation.get("source_maturity") or incarnation.get("Maturity") or "").casefold()
    proofish = any(token in maturity for token in ("proof", "implemented", "capability", "foundation", "core"))
    cta = f"Review a controlled {name} proof workflow" if proofish else f"Explore the bounded {name} workflow concept"
    domain_clause = f" for {', '.join(domain_names[:2])}" if domain_names else ""
    statement = (
        f"{name} is a governed DIO workflow{domain_clause} designed to prepare {outcome.lower()}. "
        "Source provenance, limitations and consequential human authority remain explicit."
    )
    return {
        "audience_name": audience,
        "pain": problem,
        "outcome": outcome,
        "cta": cta,
        "marketing_statement": statement,
    }


def semantic_marketing_brief(incarnation_name: str) -> dict[str, Any]:
    incarnation = _incarnation(incarnation_name)
    domain_ids = _split(incarnation.get("atlas_domain_ids"))
    context = _sensorium_context(domain_ids)
    profile = _profile_for_incarnation(incarnation_name)
    domain_map = _domains()
    domain_names = [domain_map.get(domain_id, {}).get("domain_name", domain_id) for domain_id in domain_ids]

    if profile:
        audience = _choose_profile_audience(profile, incarnation, context)
        brief = {
            "audience_name": str(audience.get("name") or ""),
            "pain": str(audience.get("pain") or ""),
            "outcome": str(audience.get("outcome") or ""),
            "cta": str(profile.get("cta") or ""),
            "marketing_statement": str(profile.get("promise") or ""),
        }
        mode = "CONFIGURED_MARKETING_PROFILE"
        profile_id = str(profile.get("id") or "")
        audience_id = str(audience.get("id") or "")
        proof_asset = str(profile.get("proof_asset") or "")
        source_image = str(profile.get("source_image") or "")
    else:
        brief = _semantic_custom_brief(incarnation, context)
        mode = "ATLAS_SENSORIUM_SEMANTIC_BRIEF"
        profile_id = ""
        audience_id = ""
        source_image = "DIO.png"
        proof_asset = ""
        slug = re.sub(r"[^a-z0-9]+", "-", incarnation_name.casefold()).strip("-")
        candidate_proof = ROOT / "state" / "product_class_packages" / slug / "GOLDEN_PROOF.html"
        if candidate_proof.is_file():
            proof_asset = str(candidate_proof.relative_to(ROOT))

    exact_counts = {
        key: len(context.get(key) or [])
        for key in ("ranked_targets", "hypotheses", "offers", "habitats", "learned_queries")
    }
    return {
        "schema": "dio.semantic_marketing_brief.v1",
        "incarnation": incarnation_name,
        "generation_mode": mode,
        "truth_class": "SEMANTIC_MARKETING_HYPOTHESIS",
        "profile_id": profile_id,
        "audience_id": audience_id,
        "brief": brief,
        "source_image": source_image,
        "proof_asset": proof_asset,
        "evidence_basis": {
            "portfolio_source": "config/atlas/dio_meta_incarnation_crosswalk.csv",
            "suite": incarnation.get("Suite"),
            "primary_family": incarnation.get("Product Family"),
            "work_patterns": _split(incarnation.get("source_work_patterns")),
            "atlas_domain_ids": domain_ids,
            "atlas_domain_names": domain_names,
            "source_maturity": incarnation.get("source_maturity") or incarnation.get("Maturity"),
            "execution_truth_class": incarnation.get("execution_truth_class"),
            "sensorium_cockpit_available": bool(context.get("available")),
            "sensorium_exact_domain_matches": exact_counts,
        },
        "observed_market_demand": False,
        "best_audience_proved": False,
        "willingness_to_pay_proved": False,
        "commercial_success_proved": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "authority_created": False,
    }
