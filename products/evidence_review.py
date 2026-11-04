from __future__ import annotations

import copy
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from products.governed_case import (
    add_evidence,
    add_requirement,
    canonical_hash,
    derive_case_status,
    link_evidence,
    raise_challenge,
    recalculate_requirement_state,
    validate_case,
)

PROFILE_SCHEMA = "dio.evidence_review.profile.v1"
PROCESSING_META_PRODUCTS = ("meta_evidence", "meta_assurance", "meta_room")
RELEASE_GUARD_META_PRODUCT = "meta_authority"

ALLOWED_REQUIREMENT_KINDS = {
    "framework",
    "control",
    "contract",
    "obligation",
    "policy",
    "request",
    "evidence_input",
}
ALLOWED_CHALLENGE_TYPES = {
    "contradiction",
    "missing_evidence",
    "stale_evidence",
    "authority",
    "scope",
    "alternative_hypothesis",
    "world_state",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write(path: Path, value: bytes) -> str:
    path.write_bytes(value)
    return _sha(value)


def _digest(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).removeprefix("sha256:")


def _gate(case: dict[str, Any], gate_id: str) -> dict[str, Any]:
    return next(row for row in case["gates"] if row["gate_id"] == gate_id)


def validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ValueError(f"Evidence review profile requires schema={PROFILE_SCHEMA}.")
    product_id = str(profile.get("product_id") or "").strip()
    profile_id = str(profile.get("profile_id") or "").strip()
    if not product_id or not profile_id:
        raise ValueError("Evidence review profile requires product_id and profile_id.")
    if tuple(profile.get("required_meta_products") or []) != PROCESSING_META_PRODUCTS:
        raise ValueError(
            "Evidence review profile must bind meta_evidence, meta_assurance and meta_room in canonical order."
        )
    if profile.get("release_guard_meta_product") != RELEASE_GUARD_META_PRODUCT:
        raise ValueError("Evidence review profile must retain meta_authority as release guard.")
    if profile.get("authority_created") is not False:
        raise ValueError("Evidence review profile cannot create authority.")
    if profile.get("external_effects") is not False:
        raise ValueError("Evidence review profile cannot create external effects.")
    if profile.get("external_release") is not False:
        raise ValueError("Evidence review profile cannot grant external release.")


def _materialize_requirements(
    case: dict[str, Any],
    *,
    profile: dict[str, Any],
    requirements: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    external: dict[str, dict[str, Any]] = {}
    source = {str(row.get("requirement_key") or ""): row for row in requirements}
    if not source or "" in source or len(source) != len(requirements):
        raise ValueError("Evidence review requirements require unique non-empty requirement_key values.")

    pending = set(source)
    while pending:
        ready = sorted(
            key
            for key in pending
            if set(str(item) for item in source[key].get("dependency_requirement_keys") or []).issubset(external)
        )
        if not ready:
            unknown = {
                key: list(source[key].get("dependency_requirement_keys") or [])
                for key in sorted(pending)
            }
            raise ValueError(f"Evidence review requirement dependency cycle or unknown dependency: {unknown}")

        for key in ready:
            row = source[key]
            statement = str(row.get("statement") or "").strip()
            if not statement:
                raise ValueError(f"Evidence review requirement {key} requires a statement.")
            kind = str(row.get("kind") or profile.get("default_requirement_kind") or "request")
            if kind not in ALLOWED_REQUIREMENT_KINDS:
                raise ValueError(f"Unsupported evidence review requirement kind: {kind}")
            dependencies = [
                external[str(item)]["requirement_id"]
                for item in row.get("dependency_requirement_keys") or []
            ]
            requirement = add_requirement(
                case,
                statement=statement,
                kind=kind,
                source_ref=str(
                    row.get("source_ref")
                    or f"{profile['profile_id']}://requirement/{key}"
                ),
                mandatory=bool(row.get("mandatory", True)),
                dependency_ids=dependencies,
                due_at=row.get("due_at"),
                expires_at=row.get("expires_at"),
            )
            external[key] = requirement
            pending.remove(key)
    return external


def _map_evidence(
    case: dict[str, Any],
    *,
    requirements: dict[str, dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    operator_id: str,
) -> None:
    for index, item in enumerate(evidence_inputs, 1):
        targets = [str(value) for value in item.get("target_requirement_keys") or []]
        if not targets or any(target not in requirements for target in targets):
            raise ValueError(
                f"Evidence review input {index} requires known target_requirement_keys."
            )

        relation = str(item.get("relation") or "supports")
        if relation not in {"supports", "contradicts"}:
            raise ValueError("Evidence review relation must be supports or contradicts.")

        evidence = add_evidence(
            case,
            kind=str(item.get("evidence_kind") or "source_record"),
            source_ref=str(item.get("source_ref") or f"evidence://review/{index}"),
            sha256=_digest(item.get("sha256")),
            observed_at=item.get("observed_at"),
            effective_at=item.get("effective_at"),
            expires_at=item.get("expires_at"),
            authority_grade=str(item.get("authority_grade") or "source_backed"),
            trust_state=str(item.get("trust_state") or "captured_untrusted"),
            freshness_state=str(item.get("freshness_state") or "unknown"),
        )

        for key in targets:
            requirement_id = requirements[key]["requirement_id"]
            if relation == "supports":
                link_evidence(
                    case,
                    evidence_id=evidence["evidence_id"],
                    requirement_id=requirement_id,
                    relation="supports",
                )
            else:
                raise_challenge(
                    case,
                    target_type="requirement",
                    target_id=requirement_id,
                    challenge_type="contradiction",
                    severity=str(item.get("severity") or "material"),
                    hypothesis=str(
                        item.get("hypothesis")
                        or f"Evidence {evidence['evidence_id']} contradicts requirement {key}."
                    ),
                    raised_by=operator_id,
                    evidence_ids=[evidence["evidence_id"]],
                )

            if evidence["freshness_state"] in {"stale", "expired"}:
                raise_challenge(
                    case,
                    target_type="requirement",
                    target_id=requirement_id,
                    challenge_type="stale_evidence",
                    severity="material",
                    hypothesis=f"Requirement {key} relies on stale or expired evidence.",
                    raised_by=operator_id,
                    evidence_ids=[evidence["evidence_id"]],
                )


def _raise_declared_issues(
    case: dict[str, Any],
    *,
    requirements: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    operator_id: str,
) -> None:
    for index, issue in enumerate(issues, 1):
        key = str(issue.get("requirement_key") or "")
        if key not in requirements:
            raise ValueError(
                f"Evidence review issue {index} references unknown requirement_key: {key}"
            )
        challenge_type = str(issue.get("challenge_type") or "missing_evidence")
        if challenge_type not in ALLOWED_CHALLENGE_TYPES:
            raise ValueError(f"Unsupported evidence review issue type: {challenge_type}")
        raise_challenge(
            case,
            target_type="requirement",
            target_id=requirements[key]["requirement_id"],
            challenge_type=challenge_type,
            severity=str(issue.get("severity") or "material"),
            hypothesis=str(
                issue.get("hypothesis")
                or issue.get("question")
                or f"Declared evidence review issue for {key}."
            ),
            raised_by=operator_id,
            evidence_ids=[str(item) for item in issue.get("evidence_ids") or []],
        )


def _review_state(case: dict[str, Any], requirement: dict[str, Any]) -> str:
    evidence = {row["evidence_id"]: row for row in case["evidence"]}
    challenges = [
        row
        for row in case["challenges"]
        if row["target_type"] == "requirement"
        and row["target_id"] == requirement["requirement_id"]
        and row["state"] == "open"
        and row["severity"] in {"material", "blocking"}
    ]
    types = {row["challenge_type"] for row in challenges}
    linked = [evidence[item] for item in requirement["evidence_ids"] if item in evidence]
    usable = [
        row
        for row in linked
        if row["trust_state"] == "trusted_for_review"
        and row["freshness_state"] not in {"stale", "expired"}
    ]

    if types.intersection(
        {"contradiction", "authority", "scope", "alternative_hypothesis", "world_state"}
    ):
        return "CONTESTED"
    if "stale_evidence" in types and linked and not usable:
        return "STALE"
    if "missing_evidence" in types and not usable:
        return "UNKNOWN"
    if "missing_evidence" in types and usable:
        return "PARTIAL"
    if requirement["state"] == "supported":
        return "SUPPORTED"
    if requirement["state"] == "challenged":
        return "CONTESTED"
    return "UNKNOWN"


def materialize_controlled_evidence_review(
    case: dict[str, Any],
    *,
    profile: dict[str, Any],
    requirements: list[dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    issues: list[dict[str, Any]] | None,
    operator_id: str,
) -> dict[str, Any]:
    validate_profile(profile)
    if case.get("product") != profile["product_id"]:
        raise ValueError(
            f"Evidence review profile {profile['profile_id']} requires product={profile['product_id']}."
        )
    if not str(operator_id or "").strip():
        raise ValueError("Controlled evidence review requires an explicit operator_id.")

    before = {
        "gates": copy.deepcopy(case["gates"]),
        "actions": copy.deepcopy(case["actions"]),
        "decisions": copy.deepcopy(case["decisions"]),
        "outputs": copy.deepcopy(case["outputs"]),
    }

    mapped = _materialize_requirements(
        case,
        profile=profile,
        requirements=requirements,
    )
    _map_evidence(
        case,
        requirements=mapped,
        evidence_inputs=evidence_inputs,
        operator_id=operator_id,
    )
    _raise_declared_issues(
        case,
        requirements=mapped,
        issues=list(issues or []),
        operator_id=operator_id,
    )

    recalculate_requirement_state(case)
    derive_case_status(case)
    validate_case(case)

    for field in ("gates", "actions", "decisions", "outputs"):
        if before[field] != case[field]:
            raise RuntimeError(f"Controlled evidence review illegally mutated case {field}.")

    matrix: list[dict[str, Any]] = []
    for key in sorted(mapped):
        requirement = mapped[key]
        open_challenges = [
            row
            for row in case["challenges"]
            if row["target_type"] == "requirement"
            and row["target_id"] == requirement["requirement_id"]
            and row["state"] == "open"
        ]
        matrix.append(
            {
                "requirement_key": key,
                "requirement_id": requirement["requirement_id"],
                "statement": requirement["statement"],
                "case_state": requirement["state"],
                "review_state": _review_state(case, requirement),
                "evidence_ids": list(requirement["evidence_ids"]),
                "open_challenge_ids": [row["challenge_id"] for row in open_challenges],
            }
        )

    return {
        "schema": "dio.evidence_review.materialization_receipt.v1",
        "profile_id": profile["profile_id"],
        "product_id": profile["product_id"],
        "case_id": case["case_id"],
        "requirement_evidence_matrix": matrix,
        "authority_created": False,
        "execution_performed": False,
        "external_effects": False,
        "external_release": False,
    }


def _issue_register(
    case: dict[str, Any],
    matrix: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    keys = {
        row["requirement_id"]: row["requirement_key"]
        for row in matrix
    }
    result: list[dict[str, Any]] = []
    for challenge in case["challenges"]:
        if challenge["state"] != "open":
            continue
        key = keys.get(challenge["target_id"])
        if not key:
            continue
        result.append(
            {
                "requirement_key": key,
                "challenge_id": challenge["challenge_id"],
                "challenge_type": challenge["challenge_type"],
                "severity": challenge["severity"],
                "hypothesis": challenge["hypothesis"],
                "evidence_ids": list(challenge["evidence_ids"]),
            }
        )
    return sorted(result, key=lambda row: (row["requirement_key"], row["challenge_id"]))


def _review_pack(
    case: dict[str, Any],
    *,
    profile: dict[str, Any],
    materialization: dict[str, Any],
) -> dict[str, Any]:
    matrix = materialization["requirement_evidence_matrix"]
    issues = _issue_register(case, matrix)
    open_questions = [
        {
            "requirement_key": row["requirement_key"],
            "challenge_id": row["challenge_id"],
            "question": row["hypothesis"],
            "state": "NEEDS_YOU",
        }
        for row in issues
    ]
    return {
        "schema": "dio.evidence_review.pack.v1",
        "profile_id": profile["profile_id"],
        "product_id": profile["product_id"],
        "case_id": case["case_id"],
        "meta_composition": {
            "required_meta_products": list(PROCESSING_META_PRODUCTS),
            "release_guard_meta_product": RELEASE_GUARD_META_PRODUCT,
        },
        "requirement_evidence_matrix": matrix,
        "issue_register": issues,
        "open_question_list": open_questions,
        "human_review": {
            "evidence_review": "NEEDS_YOU",
            "final_domain_decision": "NEEDS_YOU",
            "decision_receipt_created": False,
        },
        "forbidden_outcomes_created": {
            str(name): False for name in profile.get("forbidden_outcomes") or []
        },
        "authority_created": False,
        "external_effects": False,
        "external_release": "REFUSE",
    }


def _html_pack(pack: dict[str, Any], *, title: str) -> bytes:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    issues_by_key: dict[str, list[dict[str, Any]]] = {}
    for issue in pack.get("issue_register") or []:
        issues_by_key.setdefault(str(issue.get("requirement_key") or ""), []).append(issue)
    rows = []
    for position, row in enumerate(pack["requirement_evidence_matrix"]):
        provenance = row.get("source_provenance") or []
        source_html = "".join(
            "<li><strong>" + esc(binding.get("source_ref") or "Source locator not supplied") + "</strong>"+
            ("<br>Source bytes [" + str(binding.get("source_byte_start")) + ", " +
             str(binding.get("source_byte_end_exclusive")) + ")" if binding.get("source_byte_start") is not None else "")+
            "<br>File SHA-256: <code>" + esc(binding.get("source_file_sha256") or "Not supplied") +
            "</code><br>Row SHA-256: <code>" + esc(binding.get("source_row_sha256") or "Not supplied") +
            "</code><br>Trust: " + esc(binding.get("trust_state") or "Not declared") +
            " · freshness: " + esc(binding.get("freshness_state") or "Unknown")+
            ("<br>Attachment: " + esc((binding.get("source_attachment") or {}).get("source_ref"))+
             " · attachment hash: " + esc((binding.get("source_attachment") or {}).get("source_file_sha256"))+
             " · validation: " + esc((binding.get("source_attachment") or {}).get("content_validation"))
             if binding.get("source_attachment") else "") + "</li>"
            for binding in provenance
        ) or "<li>No source locator supplied.</li>"
        challenges = "".join(
            "<li><strong>" + esc(issue.get("challenge_id")) + " · " + esc(issue.get("severity")) +
            "</strong>: " + esc(issue.get("hypothesis")) + "</li>"
            for issue in issues_by_key.get(str(row["requirement_key"]), [])
        ) or "<li>No open challenge recorded.</li>"
        rows.append(
            "<tr data-index='" + str(position) + "'><th scope='row'>" + esc(row["requirement_key"]) +
            "<small>" + esc(row["requirement_id"]) + "</small></th><td><strong class='state'>" +
            esc(row["review_state"]) + "</strong><small>" + str(len(row.get("evidence_ids") or [])) +
            " evidence · " + str(len(row.get("open_challenge_ids") or [])) + " open issues</small></td><td>"+
            esc(row["statement"]) + "<details><summary>Source provenance</summary><ul>" + source_html +
            "</ul></details><details><summary>Open questions</summary><ul>" + challenges +
            "</ul></details></td><td><label>Reviewer disposition<select data-field='reviewer_disposition'>"+
            "<option value=''>Pending review</option><option>VERIFIED_NO_CHANGE</option>"+
            "<option>NEEDS_EVIDENCE</option><option>CHALLENGE</option><option>HOLD</option></select></label>"+
            "<label>Reviewer<input data-field='reviewer_name' autocomplete='name'></label>"+
            "<label>Rationale<textarea data-field='rationale' rows='2'></textarea></label>"+
            "<label>Follow-up evidence requested<textarea data-field='follow_up' rows='2'></textarea></label></td></tr>"
        )
    rows_json = json.dumps(pack["requirement_evidence_matrix"], ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    issues_json = json.dumps(pack.get("issue_register") or [], ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    page = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{esc(title)}</title><style>
:root{{--ink:#1a2b2d;--muted:#556864;--line:#ccd7d2;--paper:#f3f5f2;--green:#194b46;--gold:#bd8740}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}main{{max-width:1500px;margin:auto;padding:clamp(1rem,4vw,3rem)}}h1{{font-size:clamp(2rem,4vw,3.1rem);line-height:1.1;max-width:1000px}}h2{{font-size:1.35rem}}.eyebrow{{font-size:.8rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}}.notice{{border-left:5px solid var(--gold);background:#fff8e9;padding:1rem 1.2rem}}.stats{{display:flex;gap:.8rem;flex-wrap:wrap;margin:1.2rem 0}}.stats span{{background:white;border:1px solid var(--line);padding:.65rem .9rem;border-radius:.3rem}}.toolbar,.actions{{display:flex;gap:.8rem;align-items:end;flex-wrap:wrap;margin:1rem 0}}label{{display:block;font-size:.9rem;font-weight:600;margin:.4rem 0}}input,select,textarea,button{{font:inherit}}input[type=search],select,textarea{{display:block;width:100%;padding:.55rem;border:1px solid #81958f;border-radius:.25rem;background:white;color:var(--ink)}}input[type=search]{{min-width:min(24rem,80vw)}}button{{background:var(--green);color:white;border:0;border-radius:.3rem;padding:.7rem 1rem;font-weight:700;cursor:pointer}}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,summary:focus-visible{{outline:3px solid var(--gold);outline-offset:3px}}.scroll{{overflow:auto;background:white;border:1px solid var(--line);border-radius:.35rem}}table{{border-collapse:collapse;width:100%;min-width:1100px}}caption{{text-align:left;font-weight:700;padding:1rem}}th,td{{padding:.8rem;vertical-align:top;border-bottom:1px solid var(--line);text-align:left}}thead th{{background:var(--green);color:white;position:sticky;top:0}}tbody th{{min-width:8rem}}tbody td:nth-child(3){{min-width:25rem}}td small{{display:block;color:var(--muted);overflow-wrap:anywhere}}td code{{overflow-wrap:anywhere}}details{{margin:.6rem 0}}summary{{cursor:pointer;font-weight:650}}#status{{min-height:1.5em;color:var(--muted)}}footer{{margin-top:2rem;color:var(--muted);max-width:1050px}}.skip{{position:absolute;left:-10000px}}.skip:focus{{left:1rem;top:1rem;background:white;padding:.8rem;z-index:2}}[hidden]{{display:none!important}}@media print{{body{{background:white}}main{{padding:0}}.toolbar,.actions,label{{display:none!important}}table{{min-width:0;font-size:9pt}}td,th{{padding:4pt}}}}
</style></head><body><a class='skip' href='#requirements'>Skip to requirements</a><main><p class='eyebrow'>Controlled evidence review · {esc(pack.get('profile_id'))}</p>
<h1>{esc(title)}</h1><p class='notice'><strong>Human review required. External release refused.</strong> These states organize supplied evidence and open questions; they are not a compliance, certification, legal, or other domain decision. Reviewer fields below are notes only and do not change the evidence pack.</p>
<div class='stats'><span><strong>{len(pack['requirement_evidence_matrix'])}</strong> requirements</span><span><strong>{len(pack.get('issue_register') or [])}</strong> open questions</span><span>Evidence review: <strong>NEEDS YOU</strong></span><span>Final domain decision: <strong>NEEDS YOU</strong></span></div>
<p>Filter the register, inspect each source locator and hash, and record reviewer disposition, rationale, or follow-up evidence. Download the worksheet to retain the review; nothing is uploaded or submitted.</p>
<section class='toolbar' aria-label='Review tools'><label for='filter'>Find a requirement<input id='filter' type='search' placeholder='Search key, statement, state, challenge or source'></label><span id='count' aria-live='polite'></span></section>
<div class='scroll' id='requirements' tabindex='0' role='region' aria-label='Scrollable evidence review register'><table><caption>Requirement and evidence review register</caption><thead><tr><th scope='col'>Requirement</th><th scope='col'>Review state</th><th scope='col'>Statement, provenance and open questions</th><th scope='col'>Reviewer worksheet fields</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<div class='actions'><button id='download' type='button'>Download review worksheet CSV</button><span id='status' role='status' aria-live='polite'></span></div>
<footer>This controlled review pack creates no domain decision, score, approval, contracting action, authority, external effect, or release authority. Source provenance establishes the recorded locator and hash; it does not verify source truth, completeness, authenticity, applicability, or sufficiency. Independent review remains necessary.</footer>
<script type='application/json' id='matrix-data'>{rows_json}</script><script type='application/json' id='issue-data'>{issues_json}</script><script>
const matrix=JSON.parse(document.querySelector('#matrix-data').textContent);const issues=JSON.parse(document.querySelector('#issue-data').textContent);const rows=[...document.querySelectorAll('tbody tr')];
document.querySelector('#count').textContent=rows.length+' requirements shown';document.querySelector('#filter').addEventListener('input',event=>{{const term=event.target.value.trim().toLowerCase();let shown=0;for(const row of rows){{row.hidden=Boolean(term)&&!row.textContent.toLowerCase().includes(term);if(!row.hidden)shown++}}document.querySelector('#count').textContent=shown+' of '+rows.length+' requirements shown'}});
const q=value=>'"'+String(value??'').replaceAll('"','""')+'"';document.querySelector('#download').addEventListener('click',()=>{{const headers=['requirement_key','requirement_id','review_state','statement','evidence_ids','open_challenge_ids','source_refs','source_hashes','trust_states','reviewer_disposition','reviewer_name','rationale','follow_up'];const lines=[headers.map(q).join(',')];for(const row of rows){{const item=matrix[Number(row.dataset.index)];const source=item.source_provenance||[];const related=issues.filter(issue=>issue.requirement_key===item.requirement_key);const value=field=>row.querySelector('[data-field="'+field+'"]')?.value||'';const data={{requirement_key:item.requirement_key,requirement_id:item.requirement_id,review_state:item.review_state,statement:item.statement,evidence_ids:(item.evidence_ids||[]).join(';'),open_challenge_ids:(item.open_challenge_ids||[]).join(';'),source_refs:source.map(x=>x.source_ref).join(';'),source_hashes:source.map(x=>x.source_file_sha256+' / '+x.source_row_sha256).join(';'),trust_states:source.map(x=>x.trust_state+' / '+x.freshness_state).join(';'),reviewer_disposition:value('reviewer_disposition'),reviewer_name:value('reviewer_name'),rationale:value('rationale'),follow_up:value('follow_up')}};lines.push(headers.map(key=>q(data[key])).join(','))}}const blob=new Blob(['\\ufeff'+lines.join('\\r\\n')],{{type:'text/csv;charset=utf-8'}});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='EVIDENCE_REVIEW_WORKSHEET.csv';a.click();URL.revokeObjectURL(url);document.querySelector('#status').textContent='Review worksheet downloaded. No evidence state or release decision was changed.'}});
</script></main></body></html>"""
    return page.encode("utf-8")


def run_controlled_evidence_review(
    case: dict[str, Any],
    *,
    profile: dict[str, Any],
    requirements: list[dict[str, Any]],
    evidence_inputs: list[dict[str, Any]],
    issues: list[dict[str, Any]] | None,
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    validate_profile(profile)
    if not str(operator_id or "").strip():
        raise ValueError("Controlled evidence review requires an explicit operator_id.")
    if _gate(case, "intake_authority")["state"] != "allow":
        raise RuntimeError("Controlled evidence review requires approved intake authority.")
    if _gate(case, "generic_executor")["state"] != "refuse":
        raise RuntimeError("Generic executor boundary drifted before controlled evidence review.")
    if _gate(case, "external_release")["state"] == "allow":
        raise RuntimeError("Controlled evidence review cannot start with external release ALLOW.")

    materialization = materialize_controlled_evidence_review(
        case,
        profile=profile,
        requirements=requirements,
        evidence_inputs=evidence_inputs,
        issues=issues,
        operator_id=operator_id,
    )
    pack = _review_pack(case, profile=profile, materialization=materialization)
    for row in pack["requirement_evidence_matrix"]:
        target_key = row["requirement_key"]
        row["source_provenance"] = [
            {
                "source_ref": item.get("source_ref"),
                "source_file_sha256": item.get("source_file_sha256") or item.get("sha256"),
                "source_row_sha256": item.get("source_row_sha256"),
                "source_statement_sha256": item.get("source_statement_sha256"),
                "source_byte_start": item.get("source_byte_start"),
                "source_byte_end_exclusive": item.get("source_byte_end_exclusive"),
                "source_attachment": item.get("source_attachment"),
                "trust_state": item.get("trust_state", "not_declared"),
                "freshness_state": item.get("freshness_state", "unknown"),
            }
            for item in evidence_inputs
            if target_key in (item.get("target_requirement_keys") or [])
        ]
    validate_case(case)

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = str(profile.get("artifact_prefix") or profile["profile_id"]).upper().replace("-", "_")
    title = str(profile.get("review_pack_title") or f"{profile['profile_id']} Controlled Review Pack")
    rendered = {
        "JSON": (
            f"{prefix}_REVIEW_PACK.json",
            json.dumps(pack, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n",
        ),
        "HTML": (
            f"{prefix}_REVIEW_PACK.html",
            _html_pack(pack, title=title),
        ),
    }
    artifacts = [
        {
            "artifact_type": kind,
            "filename": filename,
            "sha256": _write(output_dir / filename, body),
        }
        for kind, (filename, body) in rendered.items()
    ]

    pack_fingerprint = "sha256:" + _sha(_canonical(pack))
    proof = {
        "schema": "dio.evidence_review.controlled_proof_manifest.v1",
        "provider_id": "controlled_evidence_review_v1",
        "profile_id": profile["profile_id"],
        "product_id": profile["product_id"],
        "artifact_type": "proof_room_manifest",
        "case_id": case["case_id"],
        "review_pack_fingerprint": pack_fingerprint,
        "meta_composition": pack["meta_composition"],
        "case_sha256": canonical_hash(case),
        "artifacts": artifacts,
        "human_gate": {
            "state": "NEEDS_YOU",
            "reason": str(profile.get("human_gate_reason") or "Domain review and any consequential decision remain human-authority bound."),
        },
        "forbidden_outcomes_created": pack["forbidden_outcomes_created"],
        "authority_created": False,
        "execution_performed": False,
        "external_effects": False,
        "external_release": False,
    }
    proof["proof_fingerprint"] = "sha256:" + _sha(_canonical(proof))
    _write(
        output_dir / "PROOF_MANIFEST.json",
        json.dumps(proof, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )

    receipt = {
        "schema": "dio.evidence_review.controlled_processing_receipt.v1",
        "processor_id": "controlled_evidence_review_v1",
        "profile_id": profile["profile_id"],
        "product_id": profile["product_id"],
        "case_id": case["case_id"],
        "operator_id": operator_id,
        "processed_at": now,
        "review_pack_fingerprint": pack_fingerprint,
        "proof_fingerprint": proof["proof_fingerprint"],
        "internal_processing": "COMPLETE",
        "generic_executor_gate": _gate(case, "generic_executor")["state"],
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "domain_decision_created": False,
        "domain_score_created": False,
        "forbidden_outcomes_created": pack["forbidden_outcomes_created"],
        "authority_created": False,
        "execution_performed": False,
        "external_effects": False,
        "external_release": False,
    }
    _write(
        output_dir / f"{prefix}_PROCESSING_RECEIPT.json",
        json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    return {
        "case": case,
        "materialization": materialization,
        "review_pack": pack,
        "proof_manifest": proof,
        "receipt": receipt,
        "output_dir": str(output_dir),
    }
