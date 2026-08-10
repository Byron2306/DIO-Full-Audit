from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from adapters.sophia.product_integrity import (
    _integrity_findings,
    _load_project_store,
    _map_claim_records,
    _support_state,
    load_json,
    rebuild_archive,
    sha256_file,
    utc_now,
    write_json,
    write_text,
)
from adapters.sophia.review_pipeline import extract_document_text


REGISTRY_SCHEMA = "dio.sophia_longitudinal_registry.v1"
EXPORT_SCHEMA = "dio.sophia_longitudinal_speculum.v1"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "because", "been", "being", "by",
    "can", "could", "did", "do", "does", "for", "from", "had", "has", "have", "if",
    "in", "into", "is", "it", "its", "may", "might", "more", "most", "not", "of", "on",
    "or", "our", "should", "that", "the", "their", "there", "these", "this", "those", "to",
    "using", "was", "were", "will", "with", "would",
}

CANONICAL_TOKENS = {
    "students": "learner", "student": "learner", "learners": "learner",
    "pupils": "learner", "pupil": "learner",
    "improves": "improve", "improved": "improve", "improving": "improve",
    "enhances": "improve", "enhanced": "improve", "enhancing": "improve",
    "increases": "increase", "increased": "increase", "increasing": "increase",
    "raises": "increase", "raised": "increase",
    "reduces": "reduce", "reduced": "reduce", "reducing": "reduce",
    "decreases": "reduce", "decreased": "reduce", "lowered": "reduce", "lowers": "reduce",
    "causes": "cause", "caused": "cause", "causing": "cause",
    "results": "result", "resulted": "result", "resulting": "result",
    "leads": "lead", "leading": "lead", "led": "lead",
    "demonstrates": "indicate", "demonstrated": "indicate", "demonstrate": "indicate",
    "shows": "indicate", "showed": "indicate", "shown": "indicate", "show": "indicate",
    "suggests": "suggest", "suggested": "suggest", "suggesting": "suggest",
    "associated": "associate", "association": "associate", "associations": "associate",
    "correlated": "correlate", "correlation": "correlate", "correlations": "correlate",
    "evidence": "evidence", "sources": "source", "source": "source",
    "feedback": "feedback", "commentary": "feedback",
}

CAUSAL_MARKERS = {
    "cause", "causes", "caused", "because", "lead to", "leads to", "result in", "results in",
    "effect of", "impact of", "improves", "improved", "increases", "reduces", "produces",
}
UNIVERSAL_MARKERS = {
    "all ", "every ", "always", "never", "proves", "proof", "guarantees", "eliminates",
    "solves", "definitively", "across all", "in every", "without exception",
}
HEDGING_MARKERS = {
    "may", "might", "suggest", "suggests", "associated", "association", "correlat", "appears",
    "preliminary", "possible", "could", "in this sample", "in this context",
}

SUPPORT_RANK = {
    "does_not_support": 0,
    "unmapped": 0,
    "background_only": 1,
    "partial_support": 2,
    "support_ready": 3,
}
RISK_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

ALLOWED_AUTHOR_DECISIONS = {
    "keep",
    "revise",
    "narrow",
    "strengthen_evidence",
    "retain_with_limitation",
    "remove",
    "defer",
    "dispute",
}


@dataclass
class MatchResult:
    lineage_id: str
    link_state: str
    score: float
    candidate_parent_lineage_id: str
    burden_changes: list[str]
    match_basis: dict[str, Any]


def _sha(value: str, length: int = 24) -> str:
    return hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()[:length]


def _normalize(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _stem(token: str) -> str:
    token = CANONICAL_TOKENS.get(token, token)
    for suffix in ("ization", "isation", "ments", "ment", "ingly", "edly", "ation", "ions", "ion", "ies", "ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            token = token[: -len(suffix)]
            break
    return CANONICAL_TOKENS.get(token, token)


def _tokens(text: Any) -> list[str]:
    raw = re.findall(r"[a-z][a-z0-9'-]{2,}", _normalize(text))
    return [_stem(token) for token in raw if token not in STOPWORDS]


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _scope_signature(text: str, claim_type: str) -> dict[str, Any]:
    lowered = _normalize(text)
    causal = any(marker in lowered for marker in CAUSAL_MARKERS) or claim_type.lower() == "causal"
    universal = any(marker in lowered for marker in UNIVERSAL_MARKERS)
    hedged = any(marker in lowered for marker in HEDGING_MARKERS)
    if universal and causal:
        strength = 4
    elif universal:
        strength = 3
    elif causal and not hedged:
        strength = 3
    elif causal or not hedged:
        strength = 2
    else:
        strength = 1
    return {
        "causal": causal,
        "universal": universal,
        "hedged": hedged,
        "strength": strength,
    }


def _burden_signature(record: dict[str, Any]) -> dict[str, Any]:
    claim_type = str(record.get("claim_type") or "unknown").lower()
    evidence_risk = str(record.get("evidence_risk") or "medium").lower()
    evidence_standard = _normalize(record.get("evidence_standard"))
    return {
        "claim_type": claim_type,
        "evidence_risk": evidence_risk,
        "evidence_standard": evidence_standard,
        "scope": _scope_signature(str(record.get("claim") or ""), claim_type),
    }


def _burden_changes(prior: dict[str, Any], current: dict[str, Any]) -> list[str]:
    old = _burden_signature(prior)
    new = _burden_signature(current)
    changes: list[str] = []
    if old["claim_type"] != new["claim_type"] and "unknown" not in {old["claim_type"], new["claim_type"]}:
        changes.append(f"claim_type:{old['claim_type']}->{new['claim_type']}")
    if RISK_RANK.get(new["evidence_risk"], 1) > RISK_RANK.get(old["evidence_risk"], 1):
        changes.append(f"evidence_risk_increased:{old['evidence_risk']}->{new['evidence_risk']}")
    if int(new["scope"]["strength"]) > int(old["scope"]["strength"]):
        changes.append(f"scope_strengthened:{old['scope']['strength']}->{new['scope']['strength']}")
    if new["scope"]["causal"] and not old["scope"]["causal"]:
        changes.append("causal_burden_introduced")
    if new["scope"]["universal"] and not old["scope"]["universal"]:
        changes.append("universal_scope_introduced")
    return changes


def _source_identity(record: dict[str, Any]) -> str:
    doi = _normalize(record.get("doi"))
    if doi:
        return f"doi:{doi}"
    source = _normalize(record.get("source_name"))
    return f"source:{source}" if source else ""


def _similarity(prior: dict[str, Any], current: dict[str, Any]) -> dict[str, float]:
    prior_text = _normalize(prior.get("claim"))
    current_text = _normalize(current.get("claim"))
    seq = SequenceMatcher(a=prior_text, b=current_text).ratio() if prior_text and current_text else 0.0
    jac = _jaccard(_tokens(prior_text), _tokens(current_text))
    type_match = 1.0 if str(prior.get("claim_type") or "") == str(current.get("claim_type") or "") else 0.0
    prior_scope = _scope_signature(prior_text, str(prior.get("claim_type") or ""))
    current_scope = _scope_signature(current_text, str(current.get("claim_type") or ""))
    scope_match = 1.0 if (prior_scope["causal"], prior_scope["universal"]) == (current_scope["causal"], current_scope["universal"]) else 0.0
    source_match = 1.0 if _source_identity(prior) and _source_identity(prior) == _source_identity(current) else 0.0
    score = min(1.0, seq * 0.42 + jac * 0.38 + type_match * 0.08 + scope_match * 0.06 + source_match * 0.06)
    return {
        "score": round(score, 4),
        "sequence": round(seq, 4),
        "token_jaccard": round(jac, 4),
        "claim_type_match": type_match,
        "scope_match": scope_match,
        "source_match": source_match,
    }


def _new_lineage_id(project_id: str, draft_version_id: str, index: int, claim: str) -> str:
    return f"lineage-{_sha(f'{project_id}|{draft_version_id}|{index}|{claim}', 18)}"


def _registry_path(state_root: Path) -> Path:
    return Path(state_root) / "LONGITUDINAL_REGISTRY.json"


def _load_registry(state_root: Path, project_id: str) -> dict[str, Any]:
    path = _registry_path(state_root)
    if path.is_file():
        payload = load_json(path)
        if payload.get("project_id") != project_id:
            raise ValueError("Longitudinal state root belongs to a different Sophia project.")
        return payload
    return {
        "schema": REGISTRY_SCHEMA,
        "project_id": project_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "versions": [],
        "lineages": {},
        "author_decisions": [],
        "lineage_resolution_events": [],
    }


def _save_registry(state_root: Path, registry: dict[str, Any]) -> None:
    registry["updated_at"] = utc_now()
    write_json(_registry_path(state_root), registry)


def _latest_occurrence(lineage: dict[str, Any]) -> dict[str, Any]:
    occurrences = list(lineage.get("occurrences") or [])
    return occurrences[-1] if occurrences else {}


def _prior_candidates(registry: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    for lineage_id, lineage in (registry.get("lineages") or {}).items():
        if lineage.get("state") == "provisional_continuity_candidate":
            continue
        latest = _latest_occurrence(lineage)
        if latest:
            candidates.append((lineage_id, latest))
    return candidates


def _match_claim(
    *,
    project_id: str,
    draft_version_id: str,
    index: int,
    current: dict[str, Any],
    registry: dict[str, Any],
    previous_version_id: str,
) -> MatchResult:
    candidates = []
    current_norm = _normalize(current.get("claim"))
    for lineage_id, prior in _prior_candidates(registry):
        metrics = _similarity(prior, current)
        burden = _burden_changes(prior, current)
        candidates.append((metrics["score"], lineage_id, prior, metrics, burden))
    candidates.sort(key=lambda row: (-row[0], row[1]))

    new_id = _new_lineage_id(project_id, draft_version_id, index, str(current.get("claim") or ""))
    if not candidates:
        return MatchResult(new_id, "new_claim", 0.0, "", [], {"reason": "no_prior_lineages"})

    best_score, best_id, best_prior, best_metrics, burden = candidates[0]
    second_score = candidates[1][0] if len(candidates) > 1 else 0.0
    margin = best_score - second_score
    exact = bool(current_norm) and current_norm == _normalize(best_prior.get("claim"))
    immediate = str(best_prior.get("draft_version_id") or "") == previous_version_id

    if exact or (best_score >= 0.66 and margin >= 0.08):
        if burden:
            state = "burden_mutation"
        elif immediate:
            state = "continued_claim"
        else:
            state = "reintroduced_claim"
        return MatchResult(
            best_id,
            state,
            round(best_score, 4),
            "",
            burden,
            {**best_metrics, "margin_to_second": round(margin, 4), "exact_text": exact},
        )

    if best_score >= 0.47:
        return MatchResult(
            new_id,
            "continuation_candidate_needs_confirmation",
            round(best_score, 4),
            best_id,
            burden,
            {**best_metrics, "margin_to_second": round(margin, 4), "exact_text": exact},
        )

    return MatchResult(
        new_id,
        "new_claim",
        round(best_score, 4),
        "",
        [],
        {**best_metrics, "margin_to_second": round(margin, 4), "exact_text": exact},
    )


def _version_order(registry: dict[str, Any]) -> dict[str, int]:
    return {str(row.get("draft_version_id")): index for index, row in enumerate(registry.get("versions") or [])}


def _support_state_for_record(record: dict[str, Any]) -> str:
    return _support_state(record.get("support_label"), record.get("entailment_status"))


def _occurrence(
    *,
    record: dict[str, Any],
    draft_version_id: str,
    revision_label: str,
    record_id: str,
    match: MatchResult,
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "claim_lineage_id": match.lineage_id,
        "draft_version_id": draft_version_id,
        "revision_label": revision_label,
        "claim_hash": _sha(str(record.get("claim") or ""), 24),
        "claim": str(record.get("claim") or "")[:1200],
        "claim_type": record.get("claim_type") or "unknown",
        "evidence_risk": record.get("evidence_risk") or "medium",
        "evidence_standard": record.get("evidence_standard") or "",
        "support_state": _support_state_for_record(record),
        "support_label": record.get("support_label") or "",
        "entailment_status": record.get("entailment_status") or "",
        "source_name": record.get("source_name") or "",
        "doi": record.get("doi") or "",
        "status": record.get("status") or "",
        "link_state": match.link_state,
        "lineage_match_score": match.score,
        "candidate_parent_lineage_id": match.candidate_parent_lineage_id,
        "burden_changes": match.burden_changes,
        "match_basis": match.match_basis,
        "captured_at": utc_now(),
    }


def _decorate_record(record: dict[str, Any], occurrence: dict[str, Any]) -> dict[str, Any]:
    payload = dict(record)
    payload.update({
        "record_id": occurrence["record_id"],
        "claim_lineage_id": occurrence["claim_lineage_id"],
        "revision_label": occurrence["revision_label"],
        "lineage_link_state": occurrence["link_state"],
        "lineage_match_score": occurrence["lineage_match_score"],
        "candidate_parent_lineage_id": occurrence["candidate_parent_lineage_id"],
        "burden_changes": occurrence["burden_changes"],
        "lineage_match_basis": occurrence["match_basis"],
    })
    return payload


def _append_occurrence(registry: dict[str, Any], occurrence: dict[str, Any]) -> None:
    lineage_id = occurrence["claim_lineage_id"]
    lineages = registry.setdefault("lineages", {})
    lineage = lineages.get(lineage_id)
    if lineage is None:
        lineage = {
            "lineage_id": lineage_id,
            "state": (
                "provisional_continuity_candidate"
                if occurrence["link_state"] == "continuation_candidate_needs_confirmation"
                else "active"
            ),
            "created_at": utc_now(),
            "candidate_parent_lineage_id": occurrence.get("candidate_parent_lineage_id") or "",
            "occurrences": [],
        }
        lineages[lineage_id] = lineage
    lineage.setdefault("occurrences", []).append(occurrence)
    lineage["updated_at"] = utc_now()


def _source_records(claim_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in claim_payload.get("claims") or []:
        for source in (item.get("source_map") or {}).get("results") or []:
            rows.append({
                "name": source.get("source_name") or "Unnamed source",
                "category": source.get("source_type") or "scholarly_lead",
                "text": source.get("exact_span") or "",
            })
    return rows


def _render_lineage(lineage: dict[str, Any], latest_version_id: str) -> dict[str, Any]:
    occurrences = list(lineage.get("occurrences") or [])
    support_trajectory = [row.get("support_state") for row in occurrences]
    burden_mutations = [
        {"revision_label": row.get("revision_label"), "changes": row.get("burden_changes") or []}
        for row in occurrences if row.get("burden_changes")
    ]
    latest = occurrences[-1] if occurrences else {}
    first = occurrences[0] if occurrences else {}
    if lineage.get("state") == "provisional_continuity_candidate":
        state = "continuity_uncertain"
    elif latest and latest.get("draft_version_id") != latest_version_id:
        state = "absent_latest_revision"
    elif latest.get("link_state") == "burden_mutation":
        state = "burden_mutated"
    elif len(occurrences) == 1:
        state = "single_observation"
    else:
        old_rank = SUPPORT_RANK.get(str(first.get("support_state") or "unmapped"), 0)
        new_rank = SUPPORT_RANK.get(str(latest.get("support_state") or "unmapped"), 0)
        if new_rank > old_rank:
            state = "evidence_strengthened"
        elif new_rank < old_rank:
            state = "evidence_regressed"
        elif latest.get("link_state") == "reintroduced_claim":
            state = "reintroduced"
        else:
            state = "continued"
    return {
        "lineage_id": lineage.get("lineage_id"),
        "state": state,
        "registry_state": lineage.get("state"),
        "candidate_parent_lineage_id": lineage.get("candidate_parent_lineage_id") or "",
        "occurrence_count": len(occurrences),
        "first_revision": first.get("revision_label") or "",
        "latest_revision": latest.get("revision_label") or "",
        "latest_claim": latest.get("claim") or "",
        "latest_claim_type": latest.get("claim_type") or "",
        "latest_evidence_risk": latest.get("evidence_risk") or "",
        "latest_support_state": latest.get("support_state") or "",
        "support_trajectory": support_trajectory,
        "burden_mutations": burden_mutations,
        "occurrences": occurrences,
    }


def build_longitudinal_export(
    *,
    state_root: Path,
    project_id: str,
    sophia_root: Path | None = None,
) -> dict[str, Any]:
    registry = _load_registry(state_root, project_id)
    ProjectStore, resolved_root = _load_project_store(sophia_root)
    store = ProjectStore(Path(state_root) / "project_store")
    native = store.export_integrity_record(project_id=project_id)
    latest_version_id = str((registry.get("versions") or [{}])[-1].get("draft_version_id") or "")
    lineages = [
        _render_lineage(lineage, latest_version_id)
        for _lineage_id, lineage in sorted((registry.get("lineages") or {}).items())
    ]
    counts: dict[str, int] = {}
    for lineage in lineages:
        state = str(lineage.get("state") or "unknown")
        counts[state] = counts.get(state, 0) + 1
    unresolved = [row for row in lineages if row.get("state") == "continuity_uncertain"]
    burden_mutations = [row for row in lineages if row.get("burden_mutations")]
    payload = {
        "schema": EXPORT_SCHEMA,
        "generated_at": utc_now(),
        "project_id": project_id,
        "sophia_root": str(resolved_root),
        "version_count": len(registry.get("versions") or []),
        "lineage_count": len(lineages),
        "versions": registry.get("versions") or [],
        "lineage_state_counts": counts,
        "unresolved_continuity_candidates": unresolved,
        "burden_mutation_lineages": burden_mutations,
        "author_decisions": registry.get("author_decisions") or [],
        "lineage_resolution_events": registry.get("lineage_resolution_events") or [],
        "lineages": lineages,
        "native_integrity_record_hash": native.get("integrity_record_hash") or "",
        "native_authorship_preservation_index": native.get("authorship_preservation_index") or {},
        "authority_boundary": (
            "Claim lineage is a governed scholarly-memory aid, not a forensic authorship or misconduct determination. "
            "Ambiguous continuity remains unresolved until a human confirms or rejects it."
        ),
    }
    hash_material = dict(payload)
    payload["longitudinal_speculum_hash"] = hashlib.sha256(
        json.dumps(hash_material, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()
    return payload


def markdown_longitudinal(payload: dict[str, Any]) -> str:
    lines = [
        "# Sophia Longitudinal Speculum",
        "",
        f"Project: `{payload.get('project_id')}`",
        f"Versions: **{payload.get('version_count')}**",
        f"Claim lineages: **{payload.get('lineage_count')}**",
        f"Speculum hash: `{payload.get('longitudinal_speculum_hash')}`",
        "",
        "> Claim continuity is diagnostic. Ambiguous paraphrases remain unresolved until a human confirms or rejects the proposed lineage.",
        "",
        "## Lineage Summary",
        "",
        "| Lineage | State | First → latest | Support trajectory | Latest claim |",
        "|---|---|---|---|---|",
    ]
    for lineage in payload.get("lineages") or []:
        trajectory = " → ".join(str(x) for x in lineage.get("support_trajectory") or [])
        claim = str(lineage.get("latest_claim") or "").replace("|", "/")[:180]
        lines.append(
            f"| `{lineage.get('lineage_id')}` | {lineage.get('state')} | "
            f"{lineage.get('first_revision')} → {lineage.get('latest_revision')} | {trajectory} | {claim} |"
        )
    lines.extend(["", "## Burden Mutations", ""])
    if payload.get("burden_mutation_lineages"):
        for lineage in payload["burden_mutation_lineages"]:
            for mutation in lineage.get("burden_mutations") or []:
                lines.append(
                    f"- `{lineage.get('lineage_id')}` at {mutation.get('revision_label')}: "
                    + ", ".join(mutation.get("changes") or [])
                )
    else:
        lines.append("- None recorded.")
    lines.extend(["", "## Unresolved Continuity Candidates", ""])
    if payload.get("unresolved_continuity_candidates"):
        for lineage in payload["unresolved_continuity_candidates"]:
            lines.append(
                f"- `{lineage.get('lineage_id')}` may continue `{lineage.get('candidate_parent_lineage_id')}`. Human confirmation required."
            )
    else:
        lines.append("- None.")
    lines.extend(["", "## Author Decisions", ""])
    if payload.get("author_decisions"):
        for decision in payload["author_decisions"]:
            lines.append(
                f"- `{decision.get('lineage_id')}`: **{decision.get('decision')}** — {decision.get('rationale') or 'No rationale recorded.'}"
            )
    else:
        lines.append("- No author decisions recorded yet.")
    lines.extend(["", "## Authority Boundary", "", str(payload.get("authority_boundary") or "")])
    return "\n".join(lines)


def supervisor_dashboard_html(payload: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value or ""), quote=True)

    cards = "".join(
        f"<div class='metric'><span>{esc(label)}</span><strong>{esc(value)}</strong></div>"
        for label, value in (
            ("Versions", payload.get("version_count")),
            ("Lineages", payload.get("lineage_count")),
            ("Continuity questions", len(payload.get("unresolved_continuity_candidates") or [])),
            ("Burden mutations", len(payload.get("burden_mutation_lineages") or [])),
            ("Author decisions", len(payload.get("author_decisions") or [])),
        )
    )
    rows = []
    for lineage in payload.get("lineages") or []:
        trajectory = " → ".join(str(x) for x in lineage.get("support_trajectory") or [])
        rows.append(
            "<tr>"
            f"<td><code>{esc(lineage.get('lineage_id'))}</code></td>"
            f"<td>{esc(lineage.get('state'))}</td>"
            f"<td>{esc(lineage.get('first_revision'))} → {esc(lineage.get('latest_revision'))}</td>"
            f"<td>{esc(trajectory)}</td>"
            f"<td>{esc(lineage.get('latest_claim'))}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Sophia Longitudinal Speculum</title>
<style>
body{{margin:0;background:#f4efe6;color:#211d18;font-family:Inter,Arial,sans-serif}}
header{{background:#17312d;color:#fff;padding:34px}}
main{{max-width:1240px;margin:auto;padding:28px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}}
.metric,section{{background:#fffaf1;border:1px solid #d9cdbb;border-radius:14px;padding:16px;margin-bottom:18px}}
.metric span{{display:block;font-size:12px;text-transform:uppercase;color:#6f6456}}
.metric strong{{font:700 30px Georgia,serif}}
table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:10px;border-bottom:1px solid #ded2c2;text-align:left;vertical-align:top}}th{{background:#eee3d3}}
code{{background:#eee3d3;padding:2px 5px;border-radius:4px}}.warn{{border-left:4px solid #a65f2d}}
</style>
</head>
<body>
<header><h1>Sophia Longitudinal Speculum</h1><p>Living claim, evidence and human-decision history for <code>{esc(payload.get('project_id'))}</code>.</p></header>
<main>
<div class='grid'>{cards}</div>
<section class='warn'><strong>Authority boundary.</strong> {esc(payload.get('authority_boundary'))}</section>
<section><h2>Claim Lineages</h2><table><thead><tr><th>Lineage</th><th>State</th><th>Versions</th><th>Evidence</th><th>Latest claim</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section><h2>Hashes</h2><p>Longitudinal Speculum: <code>{esc(payload.get('longitudinal_speculum_hash'))}</code></p><p>Native integrity record: <code>{esc(payload.get('native_integrity_record_hash'))}</code></p></section>
</main></body></html>"""


def _write_exports(
    *,
    state_root: Path,
    output_dir: Path | None,
    payload: dict[str, Any],
    review_id: str | None,
) -> None:
    state_root = Path(state_root)
    write_json(state_root / "LONGITUDINAL_SPECULUM.json", payload)
    write_text(state_root / "LONGITUDINAL_SPECULUM.md", markdown_longitudinal(payload))
    write_text(state_root / "SUPERVISOR_SPECULUM.html", supervisor_dashboard_html(payload))
    if output_dir:
        output_dir = Path(output_dir)
        write_json(output_dir / "LONGITUDINAL_SPECULUM.json", payload)
        write_text(output_dir / "LONGITUDINAL_SPECULUM.md", markdown_longitudinal(payload))
        write_text(output_dir / "SUPERVISOR_SPECULUM.html", supervisor_dashboard_html(payload))
        if review_id:
            rebuild_archive(output_dir, review_id)


def ingest_review_pack(
    *,
    project_id: str,
    state_root: Path,
    output_dir: Path,
    manuscript_path: Path,
    revision_label: str,
    review_id: str,
    sophia_root: Path | None = None,
) -> dict[str, Any]:
    state_root = Path(state_root).resolve()
    output_dir = Path(output_dir).resolve()
    manuscript_path = Path(manuscript_path).resolve()
    state_root.mkdir(parents=True, exist_ok=True)
    if not manuscript_path.is_file():
        raise FileNotFoundError(manuscript_path)
    required = [
        "CLAIM_SOURCE_LEDGER.json",
        "LITERATURE_MAP.json",
        "REFERENCE_AUDIT.json",
        "REVIEWER_COMMENTARY.json",
        "SCHOLARLY_RISK_REGISTER.json",
    ]
    missing = [name for name in required if not (output_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"C10 requires a completed C9 review pack; missing: {', '.join(missing)}")

    registry = _load_registry(state_root, project_id)
    ProjectStore, _resolved_root = _load_project_store(sophia_root)
    store = ProjectStore(state_root / "project_store")
    text, _parser = extract_document_text(manuscript_path)
    store.upsert_project(
        project_id=project_id,
        document_name=manuscript_path.name,
        document_hash=sha256_file(manuscript_path),
        mandos_category="writing_desk",
    )
    version = store.add_draft_version(
        project_id=project_id,
        draft_text=text,
        source=f"dio_sophia_c10_{revision_label}",
    )
    draft_version_id = str(version["version_id"])

    existing_version = next(
        (row for row in registry.get("versions") or [] if row.get("draft_version_id") == draft_version_id),
        None,
    )
    if existing_version:
        payload = build_longitudinal_export(state_root=state_root, project_id=project_id, sophia_root=sophia_root)
        _write_exports(state_root=state_root, output_dir=output_dir, payload=payload, review_id=review_id)
        return {
            "state": "longitudinal_speculum_ready",
            "idempotent": True,
            "project_id": project_id,
            "draft_version_id": draft_version_id,
            "version_count": payload["version_count"],
            "lineage_count": payload["lineage_count"],
            "unresolved_continuity_candidates": len(payload["unresolved_continuity_candidates"]),
            "longitudinal_speculum_hash": payload["longitudinal_speculum_hash"],
        }

    claim_payload = load_json(output_dir / "CLAIM_SOURCE_LEDGER.json")
    literature_payload = load_json(output_dir / "LITERATURE_MAP.json")
    commentary = load_json(output_dir / "REVIEWER_COMMENTARY.json")
    risk_register = load_json(output_dir / "SCHOLARLY_RISK_REGISTER.json")
    mapped_records = _map_claim_records(claim_payload)
    previous_version_id = str((registry.get("versions") or [{}])[-1].get("draft_version_id") or "")

    store.append_retrieved_sources(
        project_id=project_id,
        sources=literature_payload.get("deduplicated_sources") or [],
    )
    store.append_source_records(project_id=project_id, sources=_source_records(claim_payload))

    decorated_records: list[dict[str, Any]] = []
    for index, record in enumerate(mapped_records, 1):
        match = _match_claim(
            project_id=project_id,
            draft_version_id=draft_version_id,
            index=index,
            current=record,
            registry=registry,
            previous_version_id=previous_version_id,
        )
        record_id = f"claimocc-{_sha(f'{project_id}|{draft_version_id}|{index}|{record.get("claim")}', 20)}"
        occurrence = _occurrence(
            record=record,
            draft_version_id=draft_version_id,
            revision_label=revision_label,
            record_id=record_id,
            match=match,
        )
        _append_occurrence(registry, occurrence)
        decorated_records.append(_decorate_record(record, occurrence))

    store.append_claim_records(
        project_id=project_id,
        draft_version_id=draft_version_id,
        records=decorated_records,
    )
    release_ledger = {
        "mandos_judgment": commentary.get("mandos_judgment") or {},
        "article_conformity": commentary.get("article_conformity") or {},
        "validation": commentary.get("validation") or {},
        "provider": commentary.get("provider"),
        "model": commentary.get("model"),
    }
    store.append_intervention_record(
        project_id=project_id,
        draft_version_id=draft_version_id,
        record={
            "intervention_id": f"c10-{_sha(project_id + '|' + draft_version_id, 18)}",
            "task": "longitudinal_scholarly_integrity_review",
            "task_label": f"Sophia Longitudinal Speculum · {revision_label}",
            "selected_excerpt": "Whole reviewed manuscript section",
            "findings": _integrity_findings(risk_register),
            "pedagogical_move": "Office: integrity auditor. Move: preserve claim ancestry, evidence burden, uncertainty and human revision authority across drafts.",
            "next_revision_move": "Resolve the highest-risk scholarly issues and explicitly record author decisions on material claim changes.",
            "authorship_boundary": "Sophia tracks scholarly lineage and evidence state; the human author owns every final wording, source and submission decision.",
            "pedagogical_plan": {
                "selected_office": "integrity_auditor",
                "assessment_layer": "ipsative",
                "zpd_level": "advanced_academic",
                "bloom_target": "evaluate",
                "scaffold_intensity": "medium",
                "feedback_style": "longitudinal_claim_evidence_lineage",
                "pedagogical_need_state": "revision_integrity_memory",
            },
            "response_source": "hybrid_model_with_constitutional_judgment" if commentary.get("provider") else "runtime_synthesis",
            "response_source_detail": f"{commentary.get('provider') or 'local'} / {commentary.get('model') or 'deterministic'}",
            "repair_steps": commentary.get("repair_steps") or [],
            "response_release_ledger": release_ledger,
            "repair_without_rewriting": [
                "verify evidence", "narrow scope", "record author decision", "add limitation", "strengthen source support"
            ],
        },
    )

    registry.setdefault("versions", []).append({
        "draft_version_id": draft_version_id,
        "revision_label": revision_label,
        "review_id": review_id,
        "document_name": manuscript_path.name,
        "document_sha256": sha256_file(manuscript_path),
        "output_dir": str(output_dir),
        "captured_at": utc_now(),
    })
    _save_registry(state_root, registry)

    payload = build_longitudinal_export(state_root=state_root, project_id=project_id, sophia_root=sophia_root)
    _write_exports(state_root=state_root, output_dir=output_dir, payload=payload, review_id=review_id)
    return {
        "state": "longitudinal_speculum_ready",
        "idempotent": False,
        "project_id": project_id,
        "draft_version_id": draft_version_id,
        "version_count": payload["version_count"],
        "lineage_count": payload["lineage_count"],
        "unresolved_continuity_candidates": len(payload["unresolved_continuity_candidates"]),
        "burden_mutation_lineages": len(payload["burden_mutation_lineages"]),
        "longitudinal_speculum_hash": payload["longitudinal_speculum_hash"],
        "native_integrity_record_hash": payload["native_integrity_record_hash"],
    }


def record_author_decision(
    *,
    project_id: str,
    state_root: Path,
    lineage_id: str,
    decision: str,
    rationale: str,
    actor: str,
    sophia_root: Path | None = None,
) -> dict[str, Any]:
    decision = str(decision or "").strip().lower()
    if decision not in ALLOWED_AUTHOR_DECISIONS:
        raise ValueError(f"Unsupported author decision: {decision}. Allowed: {', '.join(sorted(ALLOWED_AUTHOR_DECISIONS))}")
    registry = _load_registry(state_root, project_id)
    lineage = (registry.get("lineages") or {}).get(lineage_id)
    if not lineage:
        raise ValueError(f"Unknown claim lineage: {lineage_id}")
    occurrence = _latest_occurrence(lineage)
    if not occurrence:
        raise ValueError("Claim lineage has no recorded occurrence.")
    ProjectStore, _resolved_root = _load_project_store(sophia_root)
    store = ProjectStore(Path(state_root) / "project_store")
    result = store.append_final_decision(
        project_id=project_id,
        draft_version_id=str(occurrence.get("draft_version_id") or ""),
        decision={
            "claim_record_id": occurrence.get("record_id"),
            "claim_lineage_id": lineage_id,
            "decision": decision,
            "rationale": rationale,
            "actor": actor,
            "final_text_hash": occurrence.get("claim_hash") or "",
            "authorship_assertion": "human_final_decision",
        },
    )
    registry.setdefault("author_decisions", []).append({
        "decision_id": result.get("decision_id"),
        "lineage_id": lineage_id,
        "record_id": occurrence.get("record_id"),
        "draft_version_id": occurrence.get("draft_version_id"),
        "decision": decision,
        "rationale": rationale,
        "actor": actor,
        "recorded_at": utc_now(),
    })
    lineage["latest_author_decision"] = decision
    lineage["updated_at"] = utc_now()
    _save_registry(state_root, registry)
    payload = build_longitudinal_export(state_root=state_root, project_id=project_id, sophia_root=sophia_root)
    _write_exports(state_root=state_root, output_dir=None, payload=payload, review_id=None)
    return payload


def resolve_lineage_candidate(
    *,
    project_id: str,
    state_root: Path,
    provisional_lineage_id: str,
    accept_parent: bool,
    actor: str,
    rationale: str,
    sophia_root: Path | None = None,
) -> dict[str, Any]:
    registry = _load_registry(state_root, project_id)
    lineages = registry.get("lineages") or {}
    provisional = lineages.get(provisional_lineage_id)
    if not provisional or provisional.get("state") != "provisional_continuity_candidate":
        raise ValueError("Requested lineage is not an unresolved continuity candidate.")
    parent_id = str(provisional.get("candidate_parent_lineage_id") or "")
    if not parent_id or parent_id not in lineages:
        raise ValueError("Continuity candidate has no valid parent lineage.")
    occurrence = _latest_occurrence(provisional)
    ProjectStore, _resolved_root = _load_project_store(sophia_root)
    store = ProjectStore(Path(state_root) / "project_store")
    project = store.load_project(project_id)
    raw = next(
        (row for row in project.get("claim_ledger") or [] if row.get("record_id") == occurrence.get("record_id")),
        None,
    )
    if raw is None:
        raise ValueError("Version-scoped claim occurrence is missing from the native ProjectStore.")

    if accept_parent:
        parent = lineages[parent_id]
        if any(row.get("draft_version_id") == occurrence.get("draft_version_id") for row in parent.get("occurrences") or []):
            raise ValueError("Parent lineage already has a claim occurrence in this draft version.")
        occurrence["claim_lineage_id"] = parent_id
        occurrence["link_state"] = "human_confirmed_continuation"
        occurrence["candidate_parent_lineage_id"] = ""
        occurrence["confirmed_by"] = actor
        occurrence["confirmation_rationale"] = rationale
        raw.update({
            "claim_lineage_id": parent_id,
            "lineage_link_state": "human_confirmed_continuation",
            "candidate_parent_lineage_id": "",
            "lineage_confirmation_actor": actor,
            "lineage_confirmation_rationale": rationale,
        })
        store.append_claim_records(
            project_id=project_id,
            draft_version_id=str(raw.get("draft_version_id") or occurrence.get("draft_version_id") or ""),
            records=[raw],
        )
        parent.setdefault("occurrences", []).append(occurrence)
        parent["updated_at"] = utc_now()
        del lineages[provisional_lineage_id]
        resolution = "human_confirmed_continuation"
        resolved_lineage_id = parent_id
    else:
        provisional["state"] = "active"
        provisional["candidate_parent_lineage_id"] = ""
        occurrence["link_state"] = "human_confirmed_new_claim"
        occurrence["candidate_parent_lineage_id"] = ""
        occurrence["confirmed_by"] = actor
        occurrence["confirmation_rationale"] = rationale
        raw.update({
            "lineage_link_state": "human_confirmed_new_claim",
            "candidate_parent_lineage_id": "",
            "lineage_confirmation_actor": actor,
            "lineage_confirmation_rationale": rationale,
        })
        store.append_claim_records(
            project_id=project_id,
            draft_version_id=str(raw.get("draft_version_id") or occurrence.get("draft_version_id") or ""),
            records=[raw],
        )
        resolution = "human_confirmed_new_claim"
        resolved_lineage_id = provisional_lineage_id

    registry.setdefault("lineage_resolution_events", []).append({
        "provisional_lineage_id": provisional_lineage_id,
        "candidate_parent_lineage_id": parent_id,
        "resolved_lineage_id": resolved_lineage_id,
        "resolution": resolution,
        "actor": actor,
        "rationale": rationale,
        "recorded_at": utc_now(),
    })
    _save_registry(state_root, registry)
    payload = build_longitudinal_export(state_root=state_root, project_id=project_id, sophia_root=sophia_root)
    _write_exports(state_root=state_root, output_dir=None, payload=payload, review_id=None)
    return payload
