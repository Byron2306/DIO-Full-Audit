from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .beast_semantic_governance import assess_expression_evidence
from .expression import ACT_CONTRACTS, EXPRESSION_SCHEMA, CommunicativeAct
from .semantic import assert_valid_commercial_semantic_object


SCHEMA = "dio.semantic_judgement.v1"
JUDGEMENT_ROOT = Path("state/semantic_judgements")

DIRECT_EXTERNAL_KINDS = {
    "mail_send",
    "invoice_send",
    "delivery_send",
    "public_publish",
    "paid_media_publish",
}

SENSITIVE_CONTEXT_SOURCES: dict[str, tuple[str, ...]] = {
    "price": ("quote:", "order:", "pricing:", "operator_price:"),
    "amount": ("invoice:", "order:", "payment:", "commerce:"),
    "invoice_reference": ("invoice:", "order:", "commerce:"),
    "job_reference": ("product_job:", "workflow:", "job:"),
    "proof_summary": ("proof:", "artifact:", "review:"),
}

PROHIBITED_DEPENDENCY_PATHS: dict[str, tuple[str, ...]] = {
    "customer_budget": ("commercial.budget", "subject.budget"),
    "customer_urgency": ("need.why_now", "need.trigger"),
    "customer_workflow_pain": ("need.workflow_pain",),
    "agreed_scope": ("commercial.scope",),
    "processing_authority": ("subject.consent_state",),
    "unverified_scope_authority": ("commercial.scope",),
}


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_relative(root: Path, path: Path) -> tuple[Path, str]:
    root = root.resolve()
    resolved = path.expanduser().resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Semantic judgement source must remain under DIO root: {resolved}")
    return resolved, str(resolved.relative_to(root))


def source_state_bindings(root: Path, paths: Iterable[Path]) -> list[dict[str, Any]]:
    bindings = []
    for candidate in paths:
        resolved, relative = _safe_relative(root, candidate)
        if not resolved.is_file():
            raise FileNotFoundError(f"Semantic judgement source state is missing: {resolved}")
        bindings.append({
            "path": relative,
            "sha256": file_digest(resolved),
            "size": resolved.stat().st_size,
        })
    return bindings


def mail_execution_payload(intent: dict[str, Any]) -> dict[str, Any]:
    binding = intent.get("semantic_binding") or {}
    return {
        "mail_intent_id": intent.get("mail_intent_id"),
        "purpose": intent.get("purpose"),
        "recipient": intent.get("recipient"),
        "subject": intent.get("subject"),
        "body": intent.get("body"),
        "body_html": intent.get("body_html"),
        "body_path": intent.get("body_path"),
        "attachments": list(intent.get("attachments") or []),
        "conversation_id": intent.get("conversation_id"),
        "source_message_id": intent.get("source_message_id"),
        "communicative_act": intent.get("communicative_act") or binding.get("communicative_act"),
        "semantic_object_id": binding.get("semantic_object_id"),
        "conversation_context_id": binding.get("conversation_context_id"),
    }


def mail_execution_digest(intent: dict[str, Any]) -> str:
    return canonical_digest(mail_execution_payload(intent))


def _execution_kind(expression: dict[str, Any], requested: str) -> str:
    act = str(expression.get("communicative_act") or "")
    if requested == "mail_send" and act == CommunicativeAct.INVOICE_NOTICE.value:
        return "invoice_send"
    if requested == "mail_send" and act == CommunicativeAct.DELIVERY.value:
        return "delivery_send"
    if requested == "public_publish" and act == CommunicativeAct.PAID_AD.value:
        return "paid_media_publish"
    return requested


def _metatron_judgement(
    cso: dict[str, Any],
    expression: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    obligations: list[dict[str, str]] = []

    def violation(code: str, message: str) -> None:
        violations.append({"code": code, "message": message})

    def obligation(code: str, message: str, satisfied_by: str) -> None:
        obligations.append({"code": code, "message": message, "satisfied_by": satisfied_by})

    try:
        assert_valid_commercial_semantic_object(cso)
    except ValueError as exc:
        violation("INVALID_COMMERCIAL_SEMANTIC_OBJECT", str(exc))

    if expression.get("schema") != EXPRESSION_SCHEMA:
        violation("INVALID_EXPRESSION_SCHEMA", f"Expression schema must equal {EXPRESSION_SCHEMA}")
    if expression.get("semantic_object_id") != cso.get("object_id"):
        violation("SEMANTIC_OBJECT_MISMATCH", "Expression is not bound to the supplied Commercial Semantic Object.")

    act_value = str(expression.get("communicative_act") or "")
    try:
        act = CommunicativeAct(act_value)
        contract = ACT_CONTRACTS[act]
    except ValueError:
        act = None
        contract = None
        violation("UNKNOWN_COMMUNICATIVE_ACT", f"Unknown communicative act: {act_value}")

    plan = expression.get("plan") or {}
    if str(plan.get("communicative_act") or "") != act_value:
        violation("PLAN_ACT_MISMATCH", "Expression and expression plan disagree on communicative act.")
    if str(plan.get("semantic_object_id") or "") != str(cso.get("object_id") or ""):
        violation("PLAN_OBJECT_MISMATCH", "Expression plan is bound to a different Commercial Semantic Object.")

    execution_kind = str(execution.get("kind") or "")
    if not execution_kind:
        violation("EXECUTION_KIND_MISSING", "Semantic judgement requires an explicit execution kind.")
    expected_channel = str((contract.channel if contract else "") or "")
    execution_channel = str(execution.get("channel") or "")
    if execution_kind in {"mail_send", "invoice_send", "delivery_send", "outlook_draft"} and expected_channel not in {"email", "document_or_email"}:
        violation("CHANNEL_AUTHORITY_MISMATCH", f"{act_value} is not contracted for Outlook/email execution.")
    if execution_channel and expected_channel and execution_channel not in {expected_channel, "email" if expected_channel == "document_or_email" else expected_channel}:
        violation("EXECUTION_CHANNEL_MISMATCH", f"Execution channel {execution_channel} does not match act channel {expected_channel}.")

    authority_state = str((cso.get("authority") or {}).get("authority_state") or "")
    if execution_kind in DIRECT_EXTERNAL_KINDS and authority_state in {"research_only", "market_strategy_public_content_only"}:
        if execution_kind not in {"public_publish", "paid_media_publish"} or authority_state == "research_only":
            violation("AUTHORITY_STATE_REFUSAL", f"authority_state={authority_state} cannot authorise {execution_kind}.")

    if execution_kind in DIRECT_EXTERNAL_KINDS:
        if not bool(expression.get("human_approval_required")):
            violation("HUMAN_APPROVAL_CONTRACT_MISSING", "External execution must preserve the C3 human approval requirement.")
        else:
            obligation(
                "HUMAN_APPROVAL_REQUIRED",
                "A semantic ALLOW does not create send/publish authority; the existing human execution lease remains required.",
                "mail_intent.approval.state=approved" if execution_kind in {"mail_send", "invoice_send", "delivery_send"} else "explicit_operator_execution_approval",
            )

    lineage_conversation = str((cso.get("lineage") or {}).get("conversation_id") or "").strip()
    execution_conversation = str(execution.get("conversation_id") or "").strip()
    if lineage_conversation and execution_conversation and lineage_conversation != execution_conversation:
        violation("CONVERSATION_LINEAGE_MISMATCH", "Execution conversation differs from CSO lineage.")

    verified_context = (plan.get("verified_context") or {}) if isinstance(plan, dict) else {}
    for name, prefixes in SENSITIVE_CONTEXT_SOURCES.items():
        item = verified_context.get(name)
        if not isinstance(item, dict):
            continue
        refs = [str(ref) for ref in item.get("source_refs") or []]
        authority = str(item.get("authority") or "")
        if authority == "caller_verified_context" and refs and not any(any(ref.startswith(prefix) for prefix in prefixes) for ref in refs):
            violation(
                "SENSITIVE_CONTEXT_AUTHORITY_THIN",
                f"verified_context.{name} has generic caller authority and no recognised authoritative source class.",
            )

    status = "BLOCK" if violations else "ALLOW"
    return {
        "schema": "dio.metatron_semantic_judgement.v1",
        "status": status,
        "jurisdiction": {
            "communicative_act": act_value,
            "execution_kind": execution_kind,
            "authority_state": authority_state,
            "expected_channel": expected_channel or None,
        },
        "violations": violations,
        "obligations": obligations,
        "principle": "Metatron governs jurisdiction and authority; it does not write prose.",
    }


def _loki_judgement(cso: dict[str, Any], expression: dict[str, Any]) -> dict[str, Any]:
    challenges: list[dict[str, Any]] = []
    vetoes: list[dict[str, Any]] = []

    def challenge(code: str, message: str, **extra: Any) -> None:
        row = {"code": code, "message": message}
        row.update(extra)
        challenges.append(row)

    def veto(code: str, message: str, **extra: Any) -> None:
        row = {"code": code, "message": message}
        row.update(extra)
        vetoes.append(row)

    plan = expression.get("plan") or {}
    generation = plan.get("generation_policy") or {}
    strict_flags = {
        "may_add_facts": False,
        "may_promote_inference_to_fact": False,
        "may_fill_unknowns": False,
        "must_preserve_claim_status": True,
        "must_preserve_source_refs": True,
    }
    for field, expected in strict_flags.items():
        if generation.get(field) is not expected:
            veto("GENERATION_POLICY_RELAXED", f"generation_policy.{field} must remain {expected}.", field=field)

    plan_sources = {
        (str(row.get("path") or ""), str(row.get("status") or ""), tuple(str(ref) for ref in row.get("source_refs") or []))
        for row in [*(plan.get("facts") or []), *(plan.get("hypotheses") or [])]
    }
    claim_sources = list(expression.get("claim_sources") or [])
    for row in claim_sources:
        key = (str(row.get("path") or ""), str(row.get("status") or ""), tuple(str(ref) for ref in row.get("source_refs") or []))
        if key not in plan_sources:
            veto("CLAIM_MANIFEST_TAMPERED", "Expression claim source is absent from the governed expression plan.", claim_source=row)

    act_value = str(expression.get("communicative_act") or "")
    try:
        contract = ACT_CONTRACTS[CommunicativeAct(act_value)]
    except ValueError:
        contract = None
    inferred_paths = [str(row.get("path") or "") for row in claim_sources if row.get("status") == "inferred"]
    if inferred_paths:
        if contract is not None and not (contract.allow_inferred_need or contract.allow_inferred_strategy):
            veto("INFERENCE_NOT_ALLOWED_FOR_ACT", f"{act_value} does not permit inferred dependencies.", paths=inferred_paths)
        else:
            challenge("INFERENCE_REQUIRES_REVIEW", "Inferred dependencies are present and must not be expressed as settled customer facts.", paths=inferred_paths)

    prohibited = set(str(value) for value in (cso.get("proof") or {}).get("prohibited_claims") or [])
    dependency_paths = {str(row.get("path") or "") for row in claim_sources}
    for claim in sorted(prohibited):
        forbidden_paths = PROHIBITED_DEPENDENCY_PATHS.get(claim, ())
        collisions = sorted(path for path in forbidden_paths if path in dependency_paths)
        if collisions:
            veto(
                "PROHIBITED_CLAIM_DEPENDENCY",
                f"Expression depends on semantic fields prohibited by claim policy: {claim}.",
                prohibited_claim=claim,
                paths=collisions,
            )

    conversation = plan.get("conversation_context")
    if isinstance(conversation, dict):
        authority = conversation.get("authority") or {}
        forbidden_true = (
            "may_establish_commercial_fact",
            "may_grant_consent",
            "may_set_scope",
            "may_set_budget",
            "may_set_payment_state",
            "may_confirm_identity",
            "may_grant_execution_authority",
        )
        for field in forbidden_true:
            if authority.get(field) is not False:
                veto("CONVERSATION_AUTHORITY_LAUNDERING", f"Conversation Context attempted to acquire {field}.")

    if not str(expression.get("body") or "").strip():
        veto("EMPTY_EXPRESSION", "There is no expression body to judge.")
    if not claim_sources:
        veto("UNBOUND_EXPRESSION", "Expression contains prose but no declared semantic dependency manifest.")

    status = "VETO" if vetoes else "CHALLENGE" if challenges else "CLEAR"
    return {
        "schema": "dio.loki_semantic_judgement.v1",
        "status": status,
        "vetoes": vetoes,
        "challenges": challenges,
        "alternative_hypotheses": [
            "The message may be stale because newer source state exists.",
            "The recipient may interpret an inferred dependency as a settled fact.",
            "A valid expression may still lack execution authority.",
            "The customer may be continuing an existing workflow rather than authorising a new commercial step.",
        ],
        "principle": "Loki searches for unsupported claims and authority laundering; it does not rewrite the message.",
    }


def judge_expression(
    cso: dict[str, Any],
    expression: dict[str, Any],
    *,
    execution: dict[str, Any],
    source_states: list[dict[str, Any]] | None = None,
    repeat_count: int = 1,
    active_negative_capabilities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    execution = dict(execution)
    execution["kind"] = _execution_kind(expression, str(execution.get("kind") or ""))
    metatron = _metatron_judgement(cso, expression, execution)
    loki = _loki_judgement(cso, expression)
    beast = assess_expression_evidence(
        cso,
        expression,
        execution_kind=execution["kind"],
        repeat_count=repeat_count,
        active_negative_capabilities=active_negative_capabilities,
    )

    obligations = list(metatron.get("obligations") or [])
    if loki["status"] == "CHALLENGE":
        obligations.append({
            "code": "LOKI_CHALLENGE_REVIEW",
            "message": "A human reviewer must explicitly inspect Loki challenges before execution.",
            "satisfied_by": "mail_intent.approval.state=approved" if execution["kind"] in {"mail_send", "invoice_send", "delivery_send"} else "explicit_operator_execution_approval",
        })
    if beast["status"] == "CAUTION":
        obligations.append({
            "code": "BEAST_UNCERTAINTY_REVIEW",
            "message": "BEAST evidence caution must remain visible to the execution reviewer.",
            "satisfied_by": "mail_intent.approval.state=approved" if execution["kind"] in {"mail_send", "invoice_send", "delivery_send"} else "explicit_operator_execution_approval",
        })

    if metatron["status"] == "BLOCK" or loki["status"] == "VETO" or beast["status"] == "BLOCK":
        verdict = "BLOCK"
    elif obligations:
        verdict = "ALLOW_WITH_OBLIGATIONS"
    else:
        verdict = "ALLOW"

    cso_sha = canonical_digest(cso)
    expression_sha = canonical_digest(expression)
    execution_sha = str(execution.get("binding_sha256") or canonical_digest(execution))
    source_states = list(source_states or [])
    judgement_seed = {
        "cso_sha256": cso_sha,
        "expression_sha256": expression_sha,
        "execution_binding_sha256": execution_sha,
        "source_states": source_states,
        "verdict": verdict,
    }
    judgement_id = "JUDGE-" + hashlib.sha256(json.dumps(judgement_seed, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:20].upper()
    return {
        "schema": SCHEMA,
        "judgement_id": judgement_id,
        "created_at": timestamp(),
        "verdict": verdict,
        "semantic_object_id": cso.get("object_id"),
        "communicative_act": expression.get("communicative_act"),
        "execution": execution,
        "bindings": {
            "commercial_semantic_object_sha256": cso_sha,
            "expression_sha256": expression_sha,
            "execution_binding_sha256": execution_sha,
            "source_states": source_states,
        },
        "triune": {
            "metatron": metatron,
            "loki": loki,
            "beast": beast,
        },
        "obligations": obligations,
        "execution_authority_granted": False,
        "constitution": {
            "deterministic_meaning": True,
            "probabilistic_expression_permitted": True,
            "governed_execution": True,
            "human_approval_not_replaced": True,
            "source_change_invalidates_judgement": True,
        },
    }


def persist_judgement(root: Path, judgement: dict[str, Any]) -> Path:
    if judgement.get("schema") != SCHEMA or not str(judgement.get("judgement_id") or "").startswith("JUDGE-"):
        raise ValueError("Invalid semantic judgement receipt")
    target = root.resolve() / JUDGEMENT_ROOT / f"{judgement['judgement_id']}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(judgement, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    if target.exists():
        if target.read_text(encoding="utf-8") != payload:
            raise ValueError("Judgement id collision with different receipt content")
        return target
    target.write_text(payload, encoding="utf-8")
    return target


def judge_mail_intent(
    root: Path,
    cso: dict[str, Any],
    expression: dict[str, Any],
    intent: dict[str, Any],
    *,
    source_paths: Iterable[Path],
    repeat_count: int = 1,
    active_negative_capabilities: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], Path]:
    source_states = source_state_bindings(root, source_paths)
    execution = {
        "kind": "mail_send",
        "channel": "email",
        "mail_intent_id": intent.get("mail_intent_id"),
        "conversation_id": intent.get("conversation_id"),
        "source_message_id": intent.get("source_message_id"),
        "recipient": intent.get("recipient"),
        "binding_sha256": mail_execution_digest(intent),
    }
    judgement = judge_expression(
        cso,
        expression,
        execution=execution,
        source_states=source_states,
        repeat_count=repeat_count,
        active_negative_capabilities=active_negative_capabilities,
    )
    path = persist_judgement(root, judgement)
    return judgement, path


def _judgement_path(root: Path, reference: str) -> Path:
    root = root.resolve()
    candidate = (root / reference).resolve()
    expected = (root / JUDGEMENT_ROOT).resolve()
    if not candidate.is_relative_to(expected) or candidate.suffix != ".json":
        raise ValueError("Semantic judgement path escapes the governed judgement store")
    return candidate


def assert_mail_semantic_judgement_current(
    root: Path,
    intent: dict[str, Any],
    *,
    require_execution_ready: bool,
) -> dict[str, Any] | None:
    """Verify exact proof-carrying judgement before Outlook draft/send.

    Legacy mail intents with no semantic binding remain readable under the pre-C5 path.
    Once an intent declares a semantic binding, however, judgement becomes mandatory.
    """
    if not intent.get("semantic_binding"):
        return None
    reference = intent.get("semantic_judgement") or {}
    judgement_id = str(reference.get("judgement_id") or "")
    path_value = str(reference.get("path") or "")
    if not judgement_id or not path_value:
        raise ValueError("SEMANTIC_JUDGEMENT_REFUSED: semantically bound mail has no judgement receipt.")
    path = _judgement_path(root, path_value)
    if not path.is_file():
        raise ValueError("SEMANTIC_JUDGEMENT_REFUSED: judgement receipt is missing.")
    judgement = json.loads(path.read_text(encoding="utf-8"))
    if judgement.get("schema") != SCHEMA or judgement.get("judgement_id") != judgement_id:
        raise ValueError("SEMANTIC_JUDGEMENT_REFUSED: judgement receipt identity is invalid.")
    if judgement.get("verdict") == "BLOCK":
        raise ValueError("SEMANTIC_JUDGEMENT_REFUSED: Triune verdict is BLOCK.")

    current_execution_sha = mail_execution_digest(intent)
    expected_execution_sha = str((judgement.get("bindings") or {}).get("execution_binding_sha256") or "")
    if current_execution_sha != expected_execution_sha:
        raise ValueError("SEMANTIC_JUDGEMENT_STALE: mail subject/body/recipient/attachments or semantic binding changed after judgement.")

    for row in (judgement.get("bindings") or {}).get("source_states") or []:
        source, _ = _safe_relative(root, root / str(row.get("path") or ""))
        if not source.is_file() or file_digest(source) != row.get("sha256"):
            raise ValueError(f"SEMANTIC_JUDGEMENT_STALE: source state changed after judgement: {row.get('path')}")

    if require_execution_ready:
        approval = intent.get("approval") or {}
        if approval.get("state") != "approved":
            raise ValueError("SEMANTIC_JUDGEMENT_OBLIGATION_UNMET: human approval remains required.")
        for obligation in judgement.get("obligations") or []:
            satisfied_by = str(obligation.get("satisfied_by") or "")
            if satisfied_by == "mail_intent.approval.state=approved":
                continue
            raise ValueError(f"SEMANTIC_JUDGEMENT_OBLIGATION_UNMET: {obligation.get('code')}")
    return judgement
