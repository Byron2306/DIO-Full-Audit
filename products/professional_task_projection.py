from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from products.professional_task_packets import (
    BASE_MANIFESTS,
    ROOT,
    ProfessionalTaskGauntletError,
    load_json,
    studio_input,
    validate_case_definition,
)


ROUTE_ENVELOPES = {
    "site_studio": "I need a professional website from Site Studio.",
    "professional_correspondence_studio": "I need a professional correspondence reply.",
    "finance_readiness_studio": "I need a finance readiness assessment.",
    "article_publication_studio": "I need a publication-ready article from Article Publication Studio.",
}


def _routeable_request(case: dict[str, Any]) -> str:
    """Wrap the raw buyer request in deterministic Vesper intake grammar.

    This is routing metadata, not answer content. The original customer request is
    preserved verbatim in job.source_request and professional_task_input. The
    envelope contains only the already-known Studio identity and an intake verb;
    it never uses examiner truth, expected facts, prohibited inventions or scores.
    """
    studio_id = str(case["studio_id"])
    try:
        envelope = ROUTE_ENVELOPES[studio_id]
    except KeyError as exc:
        raise ProfessionalTaskGauntletError(f"missing Vesper route envelope for Studio: {studio_id}") from exc
    raw = str(case["job"]["request"]).strip()
    if not raw:
        raise ProfessionalTaskGauntletError(f"{case['case_id']} has an empty professional task request")
    return f"{envelope} {raw}"


def _issue_lines(case: dict[str, Any]) -> list[str]:
    """Build buyer-usable finance findings from visible dossier material only.

    Findings deliberately retain unresolved discrepancies rather than choosing a
    favourable value. Adversarial instruction rows are never promoted into the
    evidence/findings stream. The examiner memo is not consulted here.
    """
    lines: list[str] = []
    for row in case.get("source_documents") or []:
        state = str(row.get("state") or "").casefold()
        if state == "instruction":
            continue

        text = str(row.get("text") or "")
        labelled: list[str] = []
        for raw in text.splitlines():
            clean = raw.strip()
            match = re.search(r"\b(ISSUE|ASSUMPTION)\s*:\s*(.+)$", clean, flags=re.IGNORECASE)
            if match:
                kind = match.group(1).strip().casefold()
                prefix = "Discrepancy / issue" if kind == "issue" else "Forecast assumption"
                # Preserve the whole visible source line, not only the text after
                # ISSUE:/ASSUMPTION:. Material context such as R85,000, 28%→36%
                # or 85% utilisation may appear before the label.
                labelled.append(f"{prefix}: {clean}")
        lines.extend(labelled)

        if state in {"missing", "incomplete", "stale", "contradictory", "unclear"}:
            summary = " ".join(part.strip() for part in text.splitlines() if part.strip())
            if summary:
                label = {
                    "missing": "Missing evidence",
                    "incomplete": "Incomplete evidence",
                    "stale": "Stale evidence",
                    "contradictory": "Contradictory evidence",
                    "unclear": "Unclear evidence",
                }[state]
                lines.append(f"{label}: {summary}")

    deduped: list[str] = []
    seen: set[str] = set()
    for line in lines:
        key = line.casefold()
        if key not in seen:
            seen.add(key)
            deduped.append(line)
    return deduped


def _article_claims(case: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    claim_no = 1
    unsafe = re.compile(
        r"\b(proves?|caused?|always|universally|#1|leading|guarantee[sd]?|request:|proposed headline)\b",
        flags=re.IGNORECASE,
    )

    for index, row in enumerate(case.get("source_documents") or [], 1):
        source_id = f"SRC-{index:02d}"
        citation = str(row.get("citation") or row.get("filename") or source_id)
        sources.append({"source_id": source_id, "citation": citation, "supports": []})
        candidates: list[str] = []
        for raw in str(row.get("text") or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            labelled = re.match(
                r"^(?:Key finding|Limitation|Sample|Professor [^:]+|Dr [^:]+|Patel cautioned|She said|He said)\s*:\s*(.+)$",
                line, flags=re.IGNORECASE,
            )
            if labelled:
                candidates.append(labelled.group(1).strip())
            elif "%" in line or re.search(
                r"\b(?:observational|non-randomised|not randomised|not directly comparable|cannot establish|expires?)\b",
                line, flags=re.IGNORECASE,
            ):
                candidates.append(line)

        for text_value in candidates:
            if len(text_value) < 20:
                continue
            state = "REFUSE" if unsafe.search(text_value) else "SUPPORTED"
            claim_id = f"CL-{claim_no:02d}"
            claim_no += 1
            claims.append(
                {
                    "claim_id": claim_id,
                    "text": text_value.rstrip(".") + ".",
                    "state": state,
                    "evidence_ids": [] if state == "REFUSE" else [source_id],
                }
            )
            if state == "SUPPORTED":
                sources[-1]["supports"].append(claim_id)

    if len([row for row in claims if row["state"] == "SUPPORTED"]) < 2:
        for index, row in enumerate(case.get("source_documents") or [], 1):
            source_id = f"SRC-{index:02d}"
            for sentence in re.split(r"(?<=[.!?])\s+", str(row.get("text") or "")):
                sentence = sentence.strip()
                if len(sentence) < 35 or unsafe.search(sentence):
                    continue
                claim_id = f"CL-{claim_no:02d}"
                claim_no += 1
                claims.append(
                    {
                        "claim_id": claim_id,
                        "text": sentence.rstrip(".") + ".",
                        "state": "SUPPORTED",
                        "evidence_ids": [source_id],
                    }
                )
                sources[index - 1]["supports"].append(claim_id)
                if len([x for x in claims if x["state"] == "SUPPORTED"]) >= 3:
                    break
            if len([x for x in claims if x["state"] == "SUPPORTED"]) >= 3:
                break
    return sources, claims


def build_task_manifest(case: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    """Project a raw professional task into the existing Studio manifest.

    The projection may use only customer-visible task material. Expected facts,
    prohibited inventions and acceptance scores are examiner-only. Vesper routing
    receives a deterministic intake envelope, while the raw buyer request remains
    separately preserved for audit and task fidelity.
    """
    validate_case_definition(case)
    root = Path(root).resolve()
    base_path = root / "config" / "studio_harvest" / BASE_MANIFESTS[str(case["studio_id"])]
    manifest = copy.deepcopy(load_json(base_path))
    raw_request = str(case["job"]["request"])
    manifest["job"]["buyer"] = str(case["job"]["buyer"])
    manifest["job"]["source_request"] = raw_request
    manifest["job"]["request"] = _routeable_request(case)
    manifest["professional_task_input"] = studio_input(case)

    contract = manifest["artifact_contract"]
    context = case["case_context"]
    constraints = [str(row) for row in case.get("constraints") or []]

    if case["studio_id"] == "site_studio":
        contract["brand"]["title"] = str(context["business_name"])
        contract["positioning"]["category"] = str(context["category"])
        contract["positioning"]["buyer_problem"] = str(context["buyer_problem"])
        contract["positioning"]["desired_outcome"] = str(context["desired_outcome"])
        contract["positioning"]["forbidden_claims"] = constraints

    elif case["studio_id"] == "professional_correspondence_studio":
        contract["purpose"] = raw_request
        contract["must_preserve"] = constraints[:]
        if not any("review" in row.casefold() for row in contract["must_preserve"]):
            contract["must_preserve"].append("the matter requires review")
        contract["must_not_invent"] = constraints[:]

    elif case["studio_id"] == "finance_readiness_studio":
        contract["purpose"] = (
            raw_request
            + " Use this report as a pre-submission action list: separate evidence already on file from missing, "
              "stale or incomplete records; retain both sides of unresolved contradictions; reconcile material "
              "scope or amount differences; document the basis for material forecast assumptions; and replace or "
              "refresh evidence where necessary before presenting the dossier to a finance provider. These findings "
              "assess readiness only and do not determine affordability, creditworthiness or lender approval."
        )
        contract["venture"] = copy.deepcopy(context["venture"])
        contract["published_requirements_fixture"] = copy.deepcopy(context["requirements"])
        supplied = []
        for index, row in enumerate(case.get("source_documents") or [], 1):
            if str(row.get("state") or "").casefold() != "supplied":
                continue
            supports = [str(value) for value in row.get("supports") or []]
            if supports:
                supplied.append(
                    {
                        "evidence_id": f"EV-{index:02d}",
                        "supports": supports,
                        "label": str(row.get("filename") or f"evidence-{index}"),
                        "state": "supplied",
                    }
                )
        contract["supplied_evidence_fixture"] = supplied
        contract["assumptions"] = _issue_lines(case) or [
            "No lender approval, affordability or underwriting outcome is known."
        ]
        contract["assumptions"].append(
            "Before submission, reconcile every flagged discrepancy, replace missing or stale evidence, validate "
            "unsupported forecast assumptions against source records, and keep unresolved differences visible rather "
            "than selecting the more favourable figure."
        )
        contract["decision_boundary"] = str(context["decision_boundary"])
        contract["forbidden_claims"] = constraints

    elif case["studio_id"] == "article_publication_studio":
        contract["publication"] = str(context["publication"])
        contract["audience"] = str(context["audience"])
        contract["editorial_register"] = [str(row) for row in context.get("editorial_register") or []]
        sources, claims = _article_claims(case)
        contract["source_fixture"] = sources
        contract["claim_fixture"] = claims
        contract["forbidden_claims"] = constraints

    else:
        raise ProfessionalTaskGauntletError(f"unsupported Studio: {case['studio_id']}")

    serialized = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
    for examiner_key in ("expected_facts", "prohibited_inventions", "acceptance_rubric"):
        if f'"{examiner_key}"' in serialized:
            raise ProfessionalTaskGauntletError(f"examiner field leaked into Studio input: {examiner_key}")
    return manifest
