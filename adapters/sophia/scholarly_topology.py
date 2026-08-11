from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

from adapters.sophia.longitudinal_speculum import (
    _load_registry,
    _normalize,
    _similarity,
    _scope_signature,
    build_longitudinal_export,
)
from adapters.sophia.product_integrity import rebuild_archive, utc_now, write_json, write_text


AUDIT_SCHEMA = "dio.sophia_scholarly_topology_audit.v1"
QUEUE_SCHEMA = "dio.sophia_scholarly_decision_queue.v1"
DECISIONS_SCHEMA = "dio.sophia_topology_decisions.v1"
PAIR_THRESHOLD = 0.52
SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical_review": 3, "critical": 3}

TOPOLOGY_DECISIONS = {
    "claim_split_candidate": {"confirm_split", "reject_split", "defer"},
    "claim_merge_candidate": {"confirm_merge", "reject_merge", "defer"},
    "factual_surface_mutation": {"intentional_change", "needs_revision", "false_positive", "defer"},
}
CLOSING_TOPOLOGY_DECISIONS = {
    "claim_split_candidate": {"confirm_split", "reject_split"},
    "claim_merge_candidate": {"confirm_merge", "reject_merge"},
    "factual_surface_mutation": {"intentional_change", "false_positive"},
}

NEGATION = {"no", "not", "never", "none", "without", "neither", "nor"}
MODALITY = {
    "may", "might", "could", "can", "should", "would", "will", "must",
    "always", "never", "likely", "unlikely", "possibly", "probably",
}
QUANTIFIERS = {
    "all", "every", "most", "many", "few", "some", "none", "always", "never",
    "significant", "significantly", "higher", "lower", "greater", "less",
}


def _sha(value: str, length: int = 20) -> str:
    return hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()[:length]


def _load_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.is_file():
        return dict(fallback or {})
    return json.loads(path.read_text(encoding="utf-8"))


def _decisions_path(state_root: Path) -> Path:
    return Path(state_root) / "TOPOLOGY_DECISIONS.json"


def _load_decisions(state_root: Path, project_id: str) -> dict[str, Any]:
    payload = _load_json(
        _decisions_path(state_root),
        {
            "schema": DECISIONS_SCHEMA,
            "project_id": project_id,
            "created_at": utc_now(),
            "decisions": [],
        },
    )
    if payload.get("project_id") != project_id:
        raise ValueError("Topology decision ledger belongs to a different Sophia project.")
    return payload


def _version_occurrences(registry: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    mapping: dict[str, list[dict[str, Any]]] = {}
    for lineage_id, lineage in (registry.get("lineages") or {}).items():
        for occurrence in lineage.get("occurrences") or []:
            row = dict(occurrence)
            row["lineage_id"] = lineage_id
            mapping.setdefault(str(row.get("draft_version_id") or ""), []).append(row)
    return mapping


def _issue_id(kind: str, *parts: Any) -> str:
    material = "|".join(str(part or "") for part in (kind, *parts))
    return f"TI-{_sha(material, 18)}"


def _token_set(text: str, vocabulary: set[str]) -> list[str]:
    tokens = set(re.findall(r"\b[a-zA-Z]+\b", str(text or "").lower()))
    return sorted(tokens & vocabulary)


def _numbers(text: str) -> list[str]:
    return sorted(set(re.findall(r"(?<!\w)\d+(?:\.\d+)?%?(?!\w)", str(text or ""))))


def _citation_surface(text: str) -> list[str]:
    return sorted(
        set(
            re.findall(
                r"\b[A-Z][A-Za-z'-]+(?:\s+(?:&|and)\s+[A-Z][A-Za-z'-]+)?\s*\(?\d{4}[a-z]?\)?",
                str(text or ""),
            )
        )
    )


def _source_identity(row: dict[str, Any]) -> str:
    doi = str(row.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    source = _normalize(row.get("source_name"))
    return f"source:{source}" if source else ""


def _factual_mutations(prior: dict[str, Any], current: dict[str, Any]) -> list[str]:
    old_text = str(prior.get("claim") or "")
    new_text = str(current.get("claim") or "")
    changes: list[str] = []
    if _numbers(old_text) != _numbers(new_text):
        changes.append(f"numeric_surface:{_numbers(old_text)}->{_numbers(new_text)}")
    if _token_set(old_text, NEGATION) != _token_set(new_text, NEGATION):
        changes.append(f"negation_surface:{_token_set(old_text, NEGATION)}->{_token_set(new_text, NEGATION)}")
    if _token_set(old_text, MODALITY) != _token_set(new_text, MODALITY):
        changes.append(f"modality_surface:{_token_set(old_text, MODALITY)}->{_token_set(new_text, MODALITY)}")
    if _token_set(old_text, QUANTIFIERS) != _token_set(new_text, QUANTIFIERS):
        changes.append(f"quantifier_surface:{_token_set(old_text, QUANTIFIERS)}->{_token_set(new_text, QUANTIFIERS)}")
    if _citation_surface(old_text) != _citation_surface(new_text):
        changes.append("citation_surface_changed")
    old_source = _source_identity(prior)
    new_source = _source_identity(current)
    if old_source and new_source and old_source != new_source:
        changes.append(f"evidence_source_changed:{old_source}->{new_source}")
    old_scope = _scope_signature(old_text, str(prior.get("claim_type") or "unknown"))
    new_scope = _scope_signature(new_text, str(current.get("claim_type") or "unknown"))
    if old_scope.get("causal") != new_scope.get("causal"):
        changes.append(f"causal_surface:{old_scope.get('causal')}->{new_scope.get('causal')}")
    if old_scope.get("universal") != new_scope.get("universal"):
        changes.append(f"universal_surface:{old_scope.get('universal')}->{new_scope.get('universal')}")
    return changes


def _topology_pairs(
    prior_rows: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    similarities: list[tuple[float, dict[str, Any], dict[str, Any], dict[str, float]]] = []
    for prior in prior_rows:
        for current in current_rows:
            metrics = _similarity(prior, current)
            if metrics["score"] >= PAIR_THRESHOLD:
                similarities.append((metrics["score"], prior, current, metrics))

    split_issues: list[dict[str, Any]] = []
    for prior in prior_rows:
        related = sorted(
            [item for item in similarities if item[1].get("record_id") == prior.get("record_id")],
            key=lambda item: -item[0],
        )
        unique_current = []
        seen = set()
        for score, _prior, current, metrics in related:
            key = str(current.get("record_id") or current.get("claim_hash") or current.get("claim"))
            if key in seen:
                continue
            seen.add(key)
            unique_current.append((score, current, metrics))
        if len(unique_current) >= 2:
            issue_id = _issue_id(
                "claim_split_candidate",
                prior.get("draft_version_id"),
                prior.get("record_id"),
                *[row[1].get("record_id") for row in unique_current[:4]],
            )
            split_issues.append({
                "issue_id": issue_id,
                "kind": "claim_split_candidate",
                "severity": "medium",
                "prior_lineage_id": prior.get("lineage_id"),
                "prior_claim": prior.get("claim"),
                "candidate_children": [
                    {
                        "lineage_id": current.get("lineage_id"),
                        "claim": current.get("claim"),
                        "score": score,
                        "match_basis": metrics,
                    }
                    for score, current, metrics in unique_current[:4]
                ],
                "interpretation": (
                    "One earlier scholarly claim is materially similar to multiple claims in the next reviewed version. "
                    "This may be a split, elaboration, or coincidental overlap; human interpretation is required."
                ),
            })

    merge_issues: list[dict[str, Any]] = []
    for current in current_rows:
        related = sorted(
            [item for item in similarities if item[2].get("record_id") == current.get("record_id")],
            key=lambda item: -item[0],
        )
        unique_prior = []
        seen = set()
        for score, prior, _current, metrics in related:
            key = str(prior.get("record_id") or prior.get("claim_hash") or prior.get("claim"))
            if key in seen:
                continue
            seen.add(key)
            unique_prior.append((score, prior, metrics))
        if len(unique_prior) >= 2:
            issue_id = _issue_id(
                "claim_merge_candidate",
                current.get("draft_version_id"),
                current.get("record_id"),
                *[row[1].get("record_id") for row in unique_prior[:4]],
            )
            merge_issues.append({
                "issue_id": issue_id,
                "kind": "claim_merge_candidate",
                "severity": "medium",
                "current_lineage_id": current.get("lineage_id"),
                "current_claim": current.get("claim"),
                "candidate_parents": [
                    {
                        "lineage_id": prior.get("lineage_id"),
                        "claim": prior.get("claim"),
                        "score": score,
                        "match_basis": metrics,
                    }
                    for score, prior, metrics in unique_prior[:4]
                ],
                "interpretation": (
                    "One current scholarly claim is materially similar to multiple earlier claims. "
                    "This may be a merge, synthesis, or coincidental overlap; human interpretation is required."
                ),
            })
    return split_issues, merge_issues


def _decision_for_issue(decisions: dict[str, Any], issue_id: str) -> dict[str, Any] | None:
    matches = [row for row in decisions.get("decisions") or [] if row.get("issue_id") == issue_id]
    return matches[-1] if matches else None


def _author_decision_for_lineage(
    longitudinal: dict[str, Any],
    lineage_id: str,
    draft_version_id: str | None = None,
) -> dict[str, Any] | None:
    rows = [row for row in longitudinal.get("author_decisions") or [] if row.get("lineage_id") == lineage_id]
    if draft_version_id:
        scoped = [row for row in rows if row.get("draft_version_id") == draft_version_id]
        return scoped[-1] if scoped else None
    return rows[-1] if rows else None


def _topology_decision_closes(issue_kind: str, decision: dict[str, Any] | None) -> bool:
    if not decision:
        return False
    allowed = CLOSING_TOPOLOGY_DECISIONS.get(issue_kind, set())
    return str(decision.get("decision") or "") in allowed


def build_topology_audit(
    *,
    state_root: Path,
    project_id: str,
    sophia_root: Path | None = None,
) -> dict[str, Any]:
    state_root = Path(state_root).resolve()
    registry = _load_registry(state_root, project_id)
    longitudinal = build_longitudinal_export(
        state_root=state_root,
        project_id=project_id,
        sophia_root=sophia_root,
    )
    decisions = _load_decisions(state_root, project_id)
    versions = list(registry.get("versions") or [])
    occurrence_map = _version_occurrences(registry)
    topology_issues: list[dict[str, Any]] = []

    for index in range(1, len(versions)):
        prior_version = str(versions[index - 1].get("draft_version_id") or "")
        current_version = str(versions[index].get("draft_version_id") or "")
        prior_rows = occurrence_map.get(prior_version, [])
        current_rows = occurrence_map.get(current_version, [])
        splits, merges = _topology_pairs(prior_rows, current_rows)
        for row in splits + merges:
            row["transition"] = {
                "from_version": prior_version,
                "to_version": current_version,
                "from_label": versions[index - 1].get("revision_label"),
                "to_label": versions[index].get("revision_label"),
            }
            topology_issues.append(row)

    for lineage in longitudinal.get("lineages") or []:
        occurrences = list(lineage.get("occurrences") or [])
        for index in range(1, len(occurrences)):
            prior = occurrences[index - 1]
            current = occurrences[index]
            mutations = _factual_mutations(prior, current)
            if not mutations:
                continue
            severity = "high" if any(
                token.startswith(("numeric_surface", "negation_surface", "causal_surface", "universal_surface"))
                for token in mutations
            ) else "medium"
            topology_issues.append({
                "issue_id": _issue_id(
                    "factual_surface_mutation",
                    lineage.get("lineage_id"),
                    prior.get("draft_version_id"),
                    current.get("draft_version_id"),
                    *mutations,
                ),
                "kind": "factual_surface_mutation",
                "severity": severity,
                "lineage_id": lineage.get("lineage_id"),
                "prior_claim": prior.get("claim"),
                "current_claim": current.get("claim"),
                "mutations": mutations,
                "transition": {
                    "from_version": prior.get("draft_version_id"),
                    "to_version": current.get("draft_version_id"),
                    "from_label": prior.get("revision_label"),
                    "to_label": current.get("revision_label"),
                },
                "interpretation": (
                    "The visible claim surface changed in a way that may alter factual, modal, quantitative, causal, or evidentiary meaning. "
                    "This is a review signal, not a finding of error or intent."
                ),
            })

    for issue in topology_issues:
        decision = _decision_for_issue(decisions, str(issue["issue_id"]))
        issue["human_topology_decision"] = decision
        if _topology_decision_closes(str(issue.get("kind") or ""), decision):
            issue["state"] = "human_resolved"
        elif decision:
            issue["state"] = "human_action_open"
        else:
            issue["state"] = "open"

    payload = {
        "schema": AUDIT_SCHEMA,
        "generated_at": utc_now(),
        "project_id": project_id,
        "version_count": len(versions),
        "issue_count": len(topology_issues),
        "open_issue_count": sum(1 for row in topology_issues if row.get("state") != "human_resolved"),
        "issues": topology_issues,
        "human_topology_decisions": decisions.get("decisions") or [],
        "authority_boundary": (
            "Topology signals are scholarly continuity and revision hypotheses, not findings of author intent, factual falsity, plagiarism, AI authorship, or misconduct."
        ),
    }
    material = dict(payload)
    payload["topology_audit_hash"] = hashlib.sha256(
        json.dumps(material, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()
    return payload


def build_decision_queue(
    *,
    state_root: Path,
    project_id: str,
    sophia_root: Path | None = None,
) -> dict[str, Any]:
    longitudinal = build_longitudinal_export(
        state_root=state_root,
        project_id=project_id,
        sophia_root=sophia_root,
    )
    topology = build_topology_audit(
        state_root=state_root,
        project_id=project_id,
        sophia_root=sophia_root,
    )
    versions = list(longitudinal.get("versions") or [])
    latest_version = str(versions[-1].get("draft_version_id") or "") if versions else ""
    latest_label = str(versions[-1].get("revision_label") or "") if versions else ""
    queue: list[dict[str, Any]] = []

    for lineage in longitudinal.get("unresolved_continuity_candidates") or []:
        queue.append({
            "queue_id": f"DQ-{_sha('lineage|' + str(lineage.get('lineage_id')), 16)}",
            "kind": "lineage_confirmation_required",
            "severity": "high",
            "lineage_id": lineage.get("lineage_id"),
            "state": "open",
            "reason": "Ambiguous claim continuity remains unresolved.",
            "required_action": "Confirm continuation or confirm a genuinely new claim through the C10 lineage-resolution route.",
        })

    for lineage in longitudinal.get("lineages") or []:
        lineage_id = str(lineage.get("lineage_id") or "")
        occurrences = list(lineage.get("occurrences") or [])
        latest_occurrence = occurrences[-1] if occurrences else {}
        latest_version_id = str(latest_occurrence.get("draft_version_id") or "")
        latest_decision = _author_decision_for_lineage(longitudinal, lineage_id, latest_version_id)
        any_decision = _author_decision_for_lineage(longitudinal, lineage_id)

        if latest_occurrence.get("burden_changes") and not latest_decision:
            queue.append({
                "queue_id": f"DQ-{_sha('burden|' + lineage_id + '|' + latest_version_id, 16)}",
                "kind": "author_decision_required_for_burden_mutation",
                "severity": "high",
                "lineage_id": lineage_id,
                "state": "open",
                "reason": "The claim's epistemic burden increased or changed, but no author decision is recorded for this occurrence.",
                "details": latest_occurrence.get("burden_changes") or [],
                "required_action": "Record the author's decision to revise, narrow, strengthen evidence, retain with limitation, remove, defer, or dispute.",
            })

        if (
            latest_version
            and lineage.get("state") == "absent_latest_revision"
            and str(latest_occurrence.get("evidence_risk") or "").lower() == "high"
        ):
            if not any_decision or any_decision.get("decision") not in {"remove", "defer"}:
                queue.append({
                    "queue_id": f"DQ-{_sha('absence|' + lineage_id + '|' + latest_version, 16)}",
                    "kind": "high_risk_claim_disappearance_needs_author_decision",
                    "severity": "high",
                    "lineage_id": lineage_id,
                    "state": "open",
                    "reason": "A high-risk scholarly claim is absent from the latest reviewed version without an explicit author removal/defer decision.",
                    "required_action": "Record whether the author intentionally removed the claim or deferred it. Absence alone is not treated as resolution.",
                })

        if (
            latest_version
            and len(occurrences) == 1
            and latest_version_id == latest_version
            and str(latest_occurrence.get("evidence_risk") or "").lower() == "high"
            and not latest_decision
        ):
            queue.append({
                "queue_id": f"DQ-{_sha('newhigh|' + lineage_id + '|' + latest_version, 16)}",
                "kind": "new_high_risk_claim_needs_author_decision",
                "severity": "high",
                "lineage_id": lineage_id,
                "state": "open",
                "reason": "A new high-risk scholarly claim appeared in the latest reviewed version without an explicit author decision.",
                "required_action": "Record how the author intends to handle the new high-risk claim before release.",
            })

        if (
            latest_version
            and len(occurrences) > 1
            and latest_version_id == latest_version
            and str(latest_occurrence.get("evidence_risk") or "").lower() == "high"
            and not any_decision
        ):
            queue.append({
                "queue_id": f"DQ-{_sha('persistenthigh|' + lineage_id + '|' + latest_version, 16)}",
                "kind": "persistent_high_risk_claim_needs_author_decision",
                "severity": "high",
                "lineage_id": lineage_id,
                "state": "open",
                "reason": "A high-risk scholarly claim persists into the latest reviewed version without any recorded author decision on the lineage.",
                "required_action": "Record whether the author intends to retain, narrow, strengthen evidence for, qualify, remove, defer, or dispute the claim.",
            })

    for issue in topology.get("issues") or []:
        if issue.get("state") == "human_resolved":
            continue
        lineage_id = str(issue.get("lineage_id") or "")
        if issue.get("kind") == "factual_surface_mutation" and lineage_id and issue.get("state") == "open":
            transition = issue.get("transition") or {}
            decision = _author_decision_for_lineage(longitudinal, lineage_id, str(transition.get("to_version") or ""))
            if decision:
                continue
        human_topology_decision = issue.get("human_topology_decision") or {}
        queue.append({
            "queue_id": f"DQ-{_sha('topology|' + str(issue.get('issue_id')), 16)}",
            "kind": f"topology:{issue.get('kind')}",
            "severity": issue.get("severity") or "medium",
            "lineage_id": issue.get("lineage_id") or issue.get("current_lineage_id") or issue.get("prior_lineage_id"),
            "topology_issue_id": issue.get("issue_id"),
            "state": "open",
            "reason": issue.get("interpretation"),
            "prior_human_topology_decision": human_topology_decision.get("decision") or None,
            "required_action": (
                "The prior human topology decision did not close this issue; record a resolving decision when the scholarly question is settled."
                if human_topology_decision
                else "Record a human topology decision for this structural revision question."
                if issue.get("kind") in {"claim_split_candidate", "claim_merge_candidate"}
                else "Record an author decision or a human topology interpretation for this material surface change."
            ),
        })

    severity_counts: dict[str, int] = {}
    for row in queue:
        severity = str(row.get("severity") or "medium")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    blocking = [row for row in queue if SEVERITY_RANK.get(str(row.get("severity") or "medium"), 1) >= 1]
    payload = {
        "schema": QUEUE_SCHEMA,
        "generated_at": utc_now(),
        "project_id": project_id,
        "latest_version_id": latest_version,
        "latest_revision_label": latest_label,
        "open_count": len(queue),
        "blocking_count": len(blocking),
        "severity_counts": severity_counts,
        "items": queue,
        "topology_audit_hash": topology.get("topology_audit_hash"),
        "longitudinal_speculum_hash": longitudinal.get("longitudinal_speculum_hash"),
        "release_rule": (
            "C10 revision release should remain held while the blocking scholarly decision queue is non-zero. "
            "Human decisions clear obligations only when they actually resolve the current scholarly change; silence never counts as scholarly intent."
        ),
        "authority_boundary": (
            "Decision-queue items are review obligations, not findings of misconduct or automated judgments about author intent."
        ),
    }
    material = dict(payload)
    payload["decision_queue_hash"] = hashlib.sha256(
        json.dumps(material, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()
    return payload


def record_topology_decision(
    *,
    state_root: Path,
    project_id: str,
    issue_id: str,
    decision: str,
    actor: str,
    rationale: str,
    sophia_root: Path | None = None,
) -> dict[str, Any]:
    if not rationale.strip():
        raise ValueError("Topology decisions require a human rationale.")
    audit = build_topology_audit(state_root=state_root, project_id=project_id, sophia_root=sophia_root)
    issue = next((row for row in audit.get("issues") or [] if row.get("issue_id") == issue_id), None)
    if not issue:
        raise ValueError(f"Unknown scholarly topology issue: {issue_id}")
    allowed = TOPOLOGY_DECISIONS.get(str(issue.get("kind") or ""), set())
    if decision not in allowed:
        raise ValueError(f"Decision '{decision}' is not valid for {issue.get('kind')}. Allowed: {sorted(allowed)}")
    ledger = _load_decisions(state_root, project_id)
    ledger.setdefault("decisions", []).append({
        "issue_id": issue_id,
        "issue_kind": issue.get("kind"),
        "decision": decision,
        "actor": actor,
        "rationale": rationale.strip(),
        "recorded_at": utc_now(),
        "authority": "human_topology_interpretation",
        "closes_issue": decision in CLOSING_TOPOLOGY_DECISIONS.get(str(issue.get("kind") or ""), set()),
    })
    ledger["updated_at"] = utc_now()
    write_json(_decisions_path(state_root), ledger)
    return build_and_write_topology(state_root=state_root, project_id=project_id, sophia_root=sophia_root)


def _markdown_audit(payload: dict[str, Any]) -> str:
    lines = [
        "# Sophia Scholarly Topology Audit",
        "",
        f"Project: `{payload.get('project_id')}`",
        f"Open topology questions: **{payload.get('open_issue_count')}**",
        "",
        "> These are topology hypotheses, not findings of author intent, factual falsity, plagiarism, AI authorship, or misconduct.",
        "",
    ]
    for row in payload.get("issues") or []:
        lines.extend([
            f"## {row.get('issue_id')} · {row.get('kind')} · {row.get('state')}",
            "",
            f"- Severity: {row.get('severity')}",
            f"- Interpretation: {row.get('interpretation')}",
            f"- Human decision: {(row.get('human_topology_decision') or {}).get('decision') or 'pending'}",
            "",
        ])
    return "\n".join(lines)


def _markdown_queue(payload: dict[str, Any]) -> str:
    lines = [
        "# Sophia Scholarly Decision Queue",
        "",
        f"Blocking human decisions: **{payload.get('blocking_count')}**",
        "",
        "> Silence is not scholarly intent. A material revision obligation remains open until a human records a decision that resolves the current scholarly change.",
        "",
    ]
    for row in payload.get("items") or []:
        lines.extend([
            f"## {row.get('queue_id')} · {row.get('kind')}",
            "",
            f"- Severity: {row.get('severity')}",
            f"- Reason: {row.get('reason')}",
            f"- Required action: {row.get('required_action')}",
            "",
        ])
    if not payload.get("items"):
        lines.append("- No open scholarly decision obligations.")
    return "\n".join(lines)


def supervisor_command_html(audit: dict[str, Any], queue: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value or ""), quote=True)

    queue_rows = "".join(
        "<tr>"
        f"<td><code>{esc(row.get('queue_id'))}</code></td>"
        f"<td>{esc(row.get('severity'))}</td>"
        f"<td>{esc(row.get('kind'))}</td>"
        f"<td>{esc(row.get('reason'))}</td>"
        f"<td>{esc(row.get('required_action'))}</td>"
        "</tr>"
        for row in queue.get("items") or []
    ) or "<tr><td colspan='5'>No open decision obligations.</td></tr>"
    issue_rows = "".join(
        "<tr>"
        f"<td><code>{esc(row.get('issue_id'))}</code></td>"
        f"<td>{esc(row.get('kind'))}</td>"
        f"<td>{esc(row.get('state'))}</td>"
        f"<td>{esc(row.get('interpretation'))}</td>"
        "</tr>"
        for row in audit.get("issues") or []
    ) or "<tr><td colspan='4'>No topology questions detected.</td></tr>"
    return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Sophia Supervisor Command Brief</title><style>
body{{margin:0;background:#f1ece2;color:#211d18;font-family:Inter,Arial,sans-serif}}header{{background:#102a27;color:#fff;padding:32px}}
main{{max-width:1320px;margin:auto;padding:26px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}
.card,section{{background:#fffaf1;border:1px solid #d8cbb8;border-radius:14px;padding:16px;margin-bottom:18px}}.card strong{{display:block;font:700 30px Georgia,serif}}
table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:10px;border-bottom:1px solid #ded2c2;text-align:left;vertical-align:top}}th{{background:#eadfce}}
.block{{border-left:5px solid #9c3e32}}code{{background:#eadfce;padding:2px 5px;border-radius:4px}}
</style></head><body><header><h1>Sophia Supervisor Command Brief</h1><p>What changed, what is ambiguous, and what now requires human scholarly ownership.</p></header><main>
<div class='grid'><div class='card'><span>Blocking decisions</span><strong>{esc(queue.get('blocking_count'))}</strong></div><div class='card'><span>Topology questions</span><strong>{esc(audit.get('open_issue_count'))}</strong></div><div class='card'><span>Latest revision</span><strong>{esc(queue.get('latest_revision_label'))}</strong></div></div>
<section class='block'><h2>Needs a human decision</h2><table><thead><tr><th>ID</th><th>Severity</th><th>Kind</th><th>Why</th><th>Action</th></tr></thead><tbody>{queue_rows}</tbody></table></section>
<section><h2>Scholarly topology</h2><table><thead><tr><th>ID</th><th>Kind</th><th>State</th><th>Interpretation</th></tr></thead><tbody>{issue_rows}</tbody></table></section>
<section><strong>Authority boundary.</strong> {esc(queue.get('authority_boundary'))}</section></main></body></html>"""


def build_and_write_topology(
    *,
    state_root: Path,
    project_id: str,
    sophia_root: Path | None = None,
) -> dict[str, Any]:
    state_root = Path(state_root).resolve()
    audit = build_topology_audit(state_root=state_root, project_id=project_id, sophia_root=sophia_root)
    queue = build_decision_queue(state_root=state_root, project_id=project_id, sophia_root=sophia_root)
    write_json(state_root / "SCHOLARLY_TOPOLOGY_AUDIT.json", audit)
    write_text(state_root / "SCHOLARLY_TOPOLOGY_AUDIT.md", _markdown_audit(audit))
    write_json(state_root / "SCHOLARLY_DECISION_QUEUE.json", queue)
    write_text(state_root / "SCHOLARLY_DECISION_QUEUE.md", _markdown_queue(queue))
    write_text(state_root / "SUPERVISOR_COMMAND_BRIEF.html", supervisor_command_html(audit, queue))

    registry = _load_registry(state_root, project_id)
    latest = (registry.get("versions") or [{}])[-1]
    output_dir = Path(str(latest.get("output_dir") or "")) if latest.get("output_dir") else None
    review_id = str(latest.get("review_id") or "")
    if output_dir and output_dir.is_dir():
        for name in (
            "SCHOLARLY_TOPOLOGY_AUDIT.json",
            "SCHOLARLY_TOPOLOGY_AUDIT.md",
            "SCHOLARLY_DECISION_QUEUE.json",
            "SCHOLARLY_DECISION_QUEUE.md",
            "SUPERVISOR_COMMAND_BRIEF.html",
        ):
            target = output_dir / name
            source = state_root / name
            target.write_bytes(source.read_bytes())
        if review_id:
            rebuild_archive(output_dir, review_id)

    return {
        "state": "scholarly_topology_ready",
        "project_id": project_id,
        "topology_issue_count": audit.get("issue_count"),
        "open_topology_issues": audit.get("open_issue_count"),
        "blocking_decision_queue": queue.get("blocking_count"),
        "topology_audit_hash": audit.get("topology_audit_hash"),
        "decision_queue_hash": queue.get("decision_queue_hash"),
        "latest_revision_label": queue.get("latest_revision_label"),
    }
